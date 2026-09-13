from .models import Character, ParsedStory, ParsedStoryWithVoices, VoiceAssignment

# Free Microsoft Edge neural voices (used via edge-tts, no API key required).
# Run `edge-tts --list-voices` for the full catalog. Keyed by (language, gender,
# age); languages fall back to "en" if the detected language has no pool below.
_VOICE_POOLS: dict[str, dict[tuple[str, str], list[str]]] = {
    "en": {
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
    },
    # edge-tts only ships one male and one female Hindi neural voice today, so
    # every age bucket maps to the same pair — still gives distinct voices per
    # character via _pick_voice's round-robin, just no age variety.
    "hi": {
        ("male", "child"): ["hi-IN-MadhurNeural"],
        ("male", "young_adult"): ["hi-IN-MadhurNeural"],
        ("male", "adult"): ["hi-IN-MadhurNeural"],
        ("male", "elderly"): ["hi-IN-MadhurNeural"],
        ("female", "child"): ["hi-IN-SwaraNeural"],
        ("female", "young_adult"): ["hi-IN-SwaraNeural"],
        ("female", "adult"): ["hi-IN-SwaraNeural"],
        ("female", "elderly"): ["hi-IN-SwaraNeural"],
        ("neutral", "child"): ["hi-IN-SwaraNeural"],
        ("neutral", "young_adult"): ["hi-IN-SwaraNeural"],
        ("neutral", "adult"): ["hi-IN-SwaraNeural"],
        ("neutral", "elderly"): ["hi-IN-MadhurNeural"],
    },
}


def _pick_voice(character: Character, language: str, used: set[str]) -> str:
    pool = _VOICE_POOLS.get(language.split("-")[0].lower(), _VOICE_POOLS["en"])
    bucket = pool.get(
        (character.voice_gender, character.voice_age),
        pool[("neutral", "adult")],
    )
    for voice_id in bucket:
        if voice_id not in used:
            return voice_id
    return bucket[0]


def assign_voices(parsed: ParsedStory) -> ParsedStoryWithVoices:
    used: set[str] = set()
    assignments: list[VoiceAssignment] = []
    for character in parsed.characters:
        voice_id = _pick_voice(character, parsed.language, used)
        used.add(voice_id)
        assignments.append(VoiceAssignment(character=character.name, voice_id=voice_id))
    return ParsedStoryWithVoices(
        language=parsed.language,
        characters=parsed.characters,
        scenes=parsed.scenes,
        voice_assignments=assignments,
    )
