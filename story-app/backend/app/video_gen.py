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
_FRAME_RATE = 25
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
                params={"width": 1280, "height": 720, "nologo": "true"},
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


def _scene_duration_seconds(scene_id: int, audio_clips: list[AudioClip]) -> float:
    total = sum(c.duration_seconds for c in audio_clips if c.scene_id == scene_id)
    return max(_MIN_SCENE_SECONDS, total)


def _animate_image(image_path: str, duration_seconds: float, out_path: str) -> None:
    frames = max(1, int(duration_seconds * _FRAME_RATE))
    zoompan = f"zoompan=z='min(zoom+0.0008,1.2)':d={frames}:s=1280x720:fps={_FRAME_RATE}"
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", image_path,
            "-vf", f"scale=1280:720,{zoompan},format=yuv420p",
            "-t", str(duration_seconds),
            "-r", str(_FRAME_RATE),
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

    with tempfile.TemporaryDirectory() as tmp:
        async with httpx.AsyncClient() as client:
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
