import asyncio
import base64
import os

import httpx

from .models import Character, ParsedStoryWithVoices, Scene, VideoClip

_RUNWAY_BASE_URL = "https://api.dev.runwayml.com/v1"
_RUNWAY_API_VERSION = "2024-11-06"
_POLL_INTERVAL_SECONDS = 5
_POLL_TIMEOUT_SECONDS = 300


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
    return ". ".join(part for part in parts if part)


async def _create_task(client: httpx.AsyncClient, api_key: str, prompt: str) -> str:
    response = await client.post(
        f"{_RUNWAY_BASE_URL}/text_to_video",
        headers={
            "Authorization": f"Bearer {api_key}",
            "X-Runway-Version": _RUNWAY_API_VERSION,
            "Content-Type": "application/json",
        },
        json={
            "promptText": prompt,
            "model": "gen3a_turbo",
            "ratio": "1280:768",
            "duration": 5,
        },
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()["id"]


async def _poll_task(client: httpx.AsyncClient, api_key: str, task_id: str) -> str:
    headers = {"Authorization": f"Bearer {api_key}", "X-Runway-Version": _RUNWAY_API_VERSION}
    elapsed = 0
    while elapsed < _POLL_TIMEOUT_SECONDS:
        response = await client.get(f"{_RUNWAY_BASE_URL}/tasks/{task_id}", headers=headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        status = data["status"]
        if status == "SUCCEEDED":
            return data["output"][0]
        if status == "FAILED":
            raise RuntimeError(f"video generation failed for task {task_id}: {data.get('failure')}")
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        elapsed += _POLL_INTERVAL_SECONDS
    raise TimeoutError(f"video generation timed out for task {task_id}")


async def generate_scene_videos(parsed: ParsedStoryWithVoices) -> list[VideoClip]:
    api_key = os.environ.get("RUNWAY_API_KEY")
    if not api_key:
        raise RuntimeError("RUNWAY_API_KEY is not set")

    characters_by_name = {c.name: c for c in parsed.characters}
    clips: list[VideoClip] = []

    async with httpx.AsyncClient() as client:
        for scene in parsed.scenes:
            prompt = _scene_prompt(scene, characters_by_name)
            task_id = await _create_task(client, api_key, prompt)
            video_url = await _poll_task(client, api_key, task_id)
            video_response = await client.get(video_url, timeout=120.0)
            video_response.raise_for_status()
            clips.append(
                VideoClip(
                    scene_id=scene.id,
                    prompt=prompt,
                    video_base64=base64.b64encode(video_response.content).decode("ascii"),
                )
            )
    return clips
