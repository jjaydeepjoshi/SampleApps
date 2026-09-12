# Story Dialogue Backend

Steps 1–3 of the story-to-video pipeline:

1. **Story parsing** (`app/story_parser.py`) — sends the story to Claude, gets
   back structured JSON: characters, scenes, and per-line dialogue with
   inferred emotion.
2. **Voice assignment** (`app/voice_assignment.py`) — maps each character to a
   TTS voice based on inferred gender/age.
3. **Dialogue audio generation** (`app/tts.py`) — calls ElevenLabs per
   dialogue line and returns base64-encoded audio clips.

Video generation (step 4+) is not implemented yet — this backend stops at
parsed story + character audio, which the Android app can already narrate.

## Setup

```bash
cd story-app/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in ANTHROPIC_API_KEY and ELEVENLABS_API_KEY
uvicorn app.main:app --reload
```

## Endpoints

- `POST /parse-story` — `{"story": "..."}` → characters, scenes, dialogue, voice assignments
- `POST /generate-audio` — `{"parsed_story": <output of /parse-story>}` → base64 audio clips per line
- `GET /health`

## Notes / next steps

- `_VOICE_POOL` in `voice_assignment.py` uses placeholder ElevenLabs voice
  IDs — replace with real IDs from your account.
- `duration_seconds` in `tts.py` is a word-count estimate; decode the actual
  audio to get a precise duration once you add scene/video timing.
- Video generation (Runway/Pika/Kling) is intentionally left out of this
  scaffold; it's the next milestone once dialogue + audio are working end to
  end.
