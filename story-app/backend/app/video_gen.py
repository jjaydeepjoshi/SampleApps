import base64
import os
import subprocess
import tempfile

import httpx

from .models import AudioClip, Character, ParsedStoryWithVoices, Scene, VideoClip

# Hugging Face's free Inference API (requires only a free account + token,
# see https://huggingface.co/settings/tokens). No paid video-gen API needed:
# we generate one still image per scene, then animate it with a Ken Burns
# pan/zoom via ffmpeg, which is free and runs entirely locally.
_HF_MODEL = "stabilityai/stable-diffusion-2-1"
# Hugging Face has been migrating serverless inference off the legacy
# api-inference.huggingface.co host onto a newer unified router - a real
# test hit "[Errno -5] No address associated with hostname" (a DNS failure,
# not an HTTP error) on the old host, consistent with it being retired for
# at least some accounts/models. Try the modern endpoint first, fall back
# to the legacy one, so this keeps working regardless of which is actually
# live for a given account.
_HF_URLS = [
    f"https://router.huggingface.co/hf-inference/models/{_HF_MODEL}",
    f"https://api-inference.huggingface.co/models/{_HF_MODEL}",
]

_MIN_SCENE_SECONDS = 4.0
_FRAME_RATE = 25


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


async def _generate_scene_image(client: httpx.AsyncClient, api_token: str, prompt: str) -> bytes:
    last_error: Exception | None = None
    for url in _HF_URLS:
        try:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_token}"},
                json={"inputs": prompt, "options": {"wait_for_model": True}},
                timeout=120.0,
            )
        except httpx.ConnectError as exc:
            last_error = exc
            continue
        if response.status_code >= 400:
            last_error = RuntimeError(
                f"Hugging Face API error {response.status_code} ({url}): {response.text}"
            )
            continue
        return response.content

    raise RuntimeError(f"Hugging Face API unreachable on all known endpoints: {last_error}")


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


async def generate_scene_videos(
    parsed: ParsedStoryWithVoices, audio_clips: list[AudioClip], api_token: str
) -> list[VideoClip]:
    if not api_token:
        raise RuntimeError(
            "a Hugging Face API token is required (set it in the app's Settings screen)"
        )

    characters_by_name = {c.name: c for c in parsed.characters}
    clips: list[VideoClip] = []

    with tempfile.TemporaryDirectory() as tmp:
        async with httpx.AsyncClient() as client:
            for scene in parsed.scenes:
                prompt = _scene_prompt(scene, characters_by_name)
                image_bytes = await _generate_scene_image(client, api_token, prompt)

                image_path = os.path.join(tmp, f"scene_{scene.id}.png")
                with open(image_path, "wb") as f:
                    f.write(image_bytes)

                duration = _scene_duration_seconds(scene.id, audio_clips)
                video_path = os.path.join(tmp, f"scene_{scene.id}.mp4")
                _animate_image(image_path, duration, video_path)

                with open(video_path, "rb") as f:
                    video_bytes = f.read()

                clips.append(
                    VideoClip(
                        scene_id=scene.id,
                        prompt=prompt,
                        video_base64=base64.b64encode(video_bytes).decode("ascii"),
                    )
                )
    return clips
