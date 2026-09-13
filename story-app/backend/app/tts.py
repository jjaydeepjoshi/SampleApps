import base64
import json
import os
import subprocess
import tempfile

import edge_tts

from .models import AudioClip, ParsedStoryWithVoices

# edge-tts is Microsoft Edge's free, keyless text-to-speech service. It has no
# per-emotion control, so emotion is approximated with rate/pitch tweaks.
_EMOTION_PROSODY = {
    "angry": ("+15%", "+20Hz"),
    "sad": ("-15%", "-20Hz"),
    "excited": ("+20%", "+15Hz"),
    "scared": ("+10%", "+30Hz"),
    "neutral": ("+0%", "+0Hz"),
}


def _prosody_for(emotion: str) -> tuple[str, str]:
    return _EMOTION_PROSODY.get(emotion.lower(), ("+0%", "+0Hz"))


def _probe_duration_seconds(path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


async def _synthesize_line(voice_id: str, text: str, emotion: str, out_path: str) -> None:
    rate, pitch = _prosody_for(emotion)
    communicate = edge_tts.Communicate(text, voice=voice_id, rate=rate, pitch=pitch)
    await communicate.save(out_path)


async def generate_dialogue_audio(parsed: ParsedStoryWithVoices) -> list[AudioClip]:
    voice_by_character = {va.character: va.voice_id for va in parsed.voice_assignments}
    clips: list[AudioClip] = []

    with tempfile.TemporaryDirectory() as tmp:
        for scene in parsed.scenes:
            for i, line in enumerate(scene.dialogue):
                voice_id = voice_by_character.get(line.speaker)
                if not voice_id:
                    continue
                out_path = os.path.join(tmp, f"scene_{scene.id}_line_{i}.mp3")
                await _synthesize_line(voice_id, line.line, line.emotion, out_path)

                with open(out_path, "rb") as f:
                    audio_bytes = f.read()

                clips.append(
                    AudioClip(
                        scene_id=scene.id,
                        speaker=line.speaker,
                        line=line.line,
                        audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
                        duration_seconds=_probe_duration_seconds(out_path),
                    )
                )
    return clips
