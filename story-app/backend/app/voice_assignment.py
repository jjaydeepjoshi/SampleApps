from .models import Character, ParsedStory, ParsedStoryWithVoices, VoiceAssignment

# Static pool of ElevenLabs voice IDs bucketed by gender/age. Replace with real
# voice IDs from your ElevenLabs account (or another TTS provider's catalog).
_VOICE_POOL: dict[tuple[str, str], list[str]] = {
    ("male", "child"): ["voice_male_child_1"],
    ("male", "young_adult"): ["voice_male_young_1", "voice_male_young_2"],
    ("male", "adult"): ["voice_male_adult_1", "voice_male_adult_2"],
    ("male", "elderly"): ["voice_male_elderly_1"],
    ("female", "child"): ["voice_female_child_1"],
    ("female", "young_adult"): ["voice_female_young_1", "voice_female_young_2"],
    ("female", "adult"): ["voice_female_adult_1", "voice_female_adult_2"],
    ("female", "elderly"): ["voice_female_elderly_1"],
    ("neutral", "child"): ["voice_neutral_child_1"],
    ("neutral", "young_adult"): ["voice_neutral_young_1"],
    ("neutral", "adult"): ["voice_neutral_adult_1"],
    ("neutral", "elderly"): ["voice_neutral_elderly_1"],
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
