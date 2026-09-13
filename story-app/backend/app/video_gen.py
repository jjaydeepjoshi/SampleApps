import asyncio
import base64
import os
import subprocess
import tempfile
import urllib.parse

import httpx

from .models import AudioClip, Character, ParsedStoryWithVoices, Scene, VideoClip

# Scene images come from Pollinations.ai's free, keyless text-to-image API.
# We tried Hugging Face's Inference API first (both the legacy
# api-inference.huggingface.co host and the newer router.huggingface.co),
# but a real deployment on Render hit "[Errno -5] No address associated
# with hostname" persistently on BOTH, across retries, with IPv4 forced -
# while Groq and edge-tts worked fine from the same instance. That points
# to Hugging Face's inference domains specifically being unreachable from
# Render's network (cloud-host IP ranges are a common target for anti-abuse
# blocking on free inference APIs), not a transient or code-level issue.
# Pollinations requires no API key/account at all, which also simplifies
# the app - no Hugging Face token setting needed anymore.
_IMAGE_API_URL = "https://image.pollinations.ai/prompt/{prompt}"

_MIN_SCENE_SECONDS = 4.0
_MIN_LINE_SECONDS = 1.0
_MAX_SCENE_SECONDS = 20.0
# Render's free tier has very little RAM, and a silent container restart
# with zero error logged (no Python traceback - just the process vanishing
# mid-request) is the signature of an OOM kill, not a code exception. Encoding
# at 1280x720/25fps was almost certainly the cause: lower resolution and
# frame rate cut ffmpeg's memory footprint substantially for the same clip.
_VIDEO_WIDTH = 854
_VIDEO_HEIGHT = 480
_FRAME_RATE = 15
_RETRY_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 2.0


def _scene_prompt(scene: Scene, characters_by_name: dict[str, Character]) -> str:
    speakers = dict.fromkeys(line.speaker for line in scene.dialogue)
    character_bits = [
        f"{name} ({characters_by_name[name].description})"
        for name in speakers
        if name in characters_by_name
    ]
    parts = [scene.setting, scene.description]
    if character_bits:
        parts.append("Characters present: " + "; ".join(character_bits))
    return "cinematic still frame, " + ". ".join(part for part in parts if part)


async def _generate_scene_image(client: httpx.AsyncClient, prompt: str) -> bytes:
    url = _IMAGE_API_URL.format(prompt=urllib.parse.quote(prompt))
    last_error: Exception | None = None

    for attempt in range(_RETRY_ATTEMPTS):
        try:
            response = await client.get(
                url,
                params={"width": _VIDEO_WIDTH, "height": _VIDEO_HEIGHT, "nologo": "true"},
                timeout=120.0,
            )
        except httpx.TransportError as exc:
            last_error = exc
        else:
            if response.status_code < 400:
                return response.content
            last_error = RuntimeError(
                f"Pollinations API error {response.status_code}: {response.text[:500]}"
            )

        if attempt < _RETRY_ATTEMPTS - 1:
            await asyncio.sleep(_RETRY_DELAY_SECONDS)

    raise RuntimeError(f"Scene image generation failed: {last_error}")


# A still scene image can't show who's actually speaking, so instead each
# dialogue line gets its speaking character's own portrait for that line's
# exact audio duration, switching portraits as the speaker changes. Not
# lip-synced (no free service does that), but the visual now actually
# tracks who is talking instead of showing one static random scene image
# throughout. Portraits are cached per character (in-memory, per backend
# process) since the same character speaks in multiple scenes/lines and
# would otherwise be re-generated identically every time.
_portrait_cache: dict[str, bytes] = {}


def _portrait_prompt(character: Character) -> str:
    return (
        "cinematic close-up portrait photo of a person talking, headshot, "
        f"looking at camera. {character.description}. {character.personality}."
    )


async def _get_character_portrait(client: httpx.AsyncClient, character: Character) -> bytes:
    cached = _portrait_cache.get(character.name)
    if cached is not None:
        return cached
    image_bytes = await _generate_scene_image(client, _portrait_prompt(character))
    _portrait_cache[character.name] = image_bytes
    return image_bytes


def _concat_videos(video_paths: list[str], out_path: str) -> None:
    tmp_dir = os.path.dirname(out_path)
    list_path = os.path.join(tmp_dir, "concat_list.txt")
    with open(list_path, "w") as f:
        for path in video_paths:
            f.write(f"file '{path}'\n")
    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out_path],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed: {result.stderr[-2000:]}")


def _scene_duration_seconds(scene_id: int, audio_clips: list[AudioClip]) -> float:
    total = sum(c.duration_seconds for c in audio_clips if c.scene_id == scene_id)
    return min(_MAX_SCENE_SECONDS, max(_MIN_SCENE_SECONDS, total))


def _animate_image(image_path: str, duration_seconds: float, out_path: str) -> None:
    frames = max(1, int(duration_seconds * _FRAME_RATE))
    zoompan = (
        f"zoompan=z='min(zoom+0.0008,1.2)':d={frames}:"
        f"s={_VIDEO_WIDTH}x{_VIDEO_HEIGHT}:fps={_FRAME_RATE}"
    )
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", image_path,
            "-vf", f"scale={_VIDEO_WIDTH}:{_VIDEO_HEIGHT},{zoompan},format=yuv420p",
            "-t", str(duration_seconds),
            "-r", str(_FRAME_RATE),
            # Free-tier memory is tight - a single encoder thread and the
            # fastest preset trade a slightly larger file for a much smaller
            # peak memory footprint, which is what actually matters here.
            "-preset", "ultrafast",
            "-threads", "1",
            out_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg animation failed: {result.stderr[-2000:]}")


def _find_scene(parsed: ParsedStoryWithVoices, scene_id: int) -> Scene:
    for scene in parsed.scenes:
        if scene.id == scene_id:
            return scene
    raise RuntimeError(f"story has no scene with id {scene_id}")


async def generate_single_scene_video(
    parsed: ParsedStoryWithVoices, audio_clips: list[AudioClip], scene_id: int
) -> VideoClip:
    # Generating one scene per request (rather than the whole story in one
    # call) lets the app show real progress - "scene 2 of 5" - instead of a
    # single opaque "generating video..." spinner for the whole thing.
    scene = _find_scene(parsed, scene_id)
    characters_by_name = {c.name: c for c in parsed.characters}
    prompt = _scene_prompt(scene, characters_by_name)
    scene_audio = [clip for clip in audio_clips if clip.scene_id == scene_id]

    with tempfile.TemporaryDirectory() as tmp:
        async with httpx.AsyncClient() as client:
            if scene.dialogue and len(scene_audio) == len(scene.dialogue):
                # One clip per dialogue line, using that line's speaker's
                # portrait for that line's own audio duration - see the
                # module docstring above _portrait_cache for why.
                line_paths: list[str] = []
                for i, (line, audio) in enumerate(zip(scene.dialogue, scene_audio)):
                    character = characters_by_name.get(line.speaker)
                    if character is not None:
                        image_bytes = await _get_character_portrait(client, character)
                    else:
                        image_bytes = await _generate_scene_image(client, prompt)

                    image_path = os.path.join(tmp, f"line_{i}.png")
                    with open(image_path, "wb") as f:
                        f.write(image_bytes)

                    line_duration = min(_MAX_SCENE_SECONDS, max(_MIN_LINE_SECONDS, audio.duration_seconds))
                    line_video_path = os.path.join(tmp, f"line_{i}.mp4")
                    _animate_image(image_path, line_duration, line_video_path)
                    line_paths.append(line_video_path)

                video_path = os.path.join(tmp, f"scene_{scene.id}.mp4")
                if len(line_paths) == 1:
                    video_path = line_paths[0]
                else:
                    _concat_videos(line_paths, video_path)
            else:
                # No dialogue in this scene (or audio didn't line up 1:1
                # with it) - fall back to a single scene-setting image for
                # the whole scene, same as before.
                image_bytes = await _generate_scene_image(client, prompt)
                image_path = os.path.join(tmp, f"scene_{scene.id}.png")
                with open(image_path, "wb") as f:
                    f.write(image_bytes)

                duration = _scene_duration_seconds(scene.id, audio_clips)
                video_path = os.path.join(tmp, f"scene_{scene.id}.mp4")
                _animate_image(image_path, duration, video_path)

        with open(video_path, "rb") as f:
            video_bytes = f.read()

    return VideoClip(
        scene_id=scene.id,
        prompt=prompt,
        video_base64=base64.b64encode(video_bytes).decode("ascii"),
    )


async def generate_scene_videos(
    parsed: ParsedStoryWithVoices, audio_clips: list[AudioClip]
) -> list[VideoClip]:
    # Kept for any caller that wants the whole story's video in one request;
    # the app itself now calls generate_single_scene_video per scene instead
    # so it can show progress between scenes.
    return [
        await generate_single_scene_video(parsed, audio_clips, scene.id)
        for scene in parsed.scenes
    ]
