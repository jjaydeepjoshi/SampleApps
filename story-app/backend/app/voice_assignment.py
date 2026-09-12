from .models import Character, ParsedStory, ParsedStoryWithVoices, VoiceAssignment

# Free Microsoft Edge neural voices (used via edge-tts, no API key required).
# Run `edge-tts --list-voices` for the full catalog.
_VOICE_POOL: dict[tuple[str, str], list[str]] = {
    ("male", "child"): ["en-US-AnaNeural"],
    ("male", "young_adult"): ["en-US-GuyNeural", "en-GB-RyanNeural"],
    ("male", "adult"): ["en-US-ChristopherNeural", "en-GB-ThomasNeural"],
    ("male", "elderly"): ["en-US-DavisNeural"],
    ("female", "child"): ["en-US-AnaNeural"],
    ("female", "young_adult"): ["en-US-JennyNeural", "en-GB-SoniaNeural"],
    ("female", "adult"): ["en-US-AriaNeural", "en-GB-LibbyNeural"],
    ("female", "elderly"): ["en-US-MichelleNeural"],
    ("neutral", "child"): ["en-US-AnaNeural"],
    ("neutral", "young_adult"): ["en-US-JennyNeural"],
    ("neutral", "adult"): ["en-US-AriaNeural"],
    ("neutral", "elderly"): ["en-US-DavisNeural"],
}


def _pick_voice(character: Character, used: set[str]) -> str:
    bucket = _VOICE_POOL.get(
        (character.voice_gender, character.voice_age),
        _VOICE_POOL[("neutral", "adult")],
    )
    for voice_id in bucket:
        if voice_id not in used:
            return voice_id
    return bucket[0]


def assign_voices(parsed: ParsedStory) -> ParsedStoryWithVoices:
    used: set[str] = set()
    assignments: list[VoiceAssignment] = []
    for character in parsed.characters:
        voice_id = _pick_voice(character, used)
        used.add(voice_id)
        assignments.append(VoiceAssignment(character=character.name, voice_id=voice_id))
    return ParsedStoryWithVoices(
        characters=parsed.characters,
        scenes=parsed.scenes,
        voice_assignments=assignments,
    )
