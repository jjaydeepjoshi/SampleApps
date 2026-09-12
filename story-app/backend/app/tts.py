import base64
import os

import httpx

from .models import AudioClip, ParsedStoryWithVoices

_ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

_EMOTION_STABILITY = {
    "angry": 0.3,
    "sad": 0.4,
    "excited": 0.25,
    "neutral": 0.5,
}


def _stability_for(emotion: str) -> float:
    return _EMOTION_STABILITY.get(emotion.lower(), 0.45)


async def _synthesize_line(
    client: httpx.AsyncClient, api_key: str, voice_id: str, text: str, emotion: str
) -> bytes:
    response = await client.post(
        _ELEVENLABS_URL.format(voice_id=voice_id),
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": _stability_for(emotion),
                "similarity_boost": 0.75,
            },
        },
        timeout=60.0,
    )
    response.raise_for_status()
    return response.content


async def generate_dialogue_audio(parsed: ParsedStoryWithVoices) -> list[AudioClip]:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")

    voice_by_character = {va.character: va.voice_id for va in parsed.voice_assignments}
    clips: list[AudioClip] = []

    async with httpx.AsyncClient() as client:
        for scene in parsed.scenes:
            for line in scene.dialogue:
                voice_id = voice_by_character.get(line.speaker)
                if not voice_id:
                    continue
                audio_bytes = await _synthesize_line(
                    client, api_key, voice_id, line.line, line.emotion
                )
                clips.append(
                    AudioClip(
                        scene_id=scene.id,
                        speaker=line.speaker,
                        line=line.line,
                        audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
                        # Placeholder estimate; replace with real duration from
                        # audio metadata once you decode the returned MP3/WAV.
                        duration_seconds=max(1.0, len(line.line.split()) / 2.5),
                    )
                )
    return clips
