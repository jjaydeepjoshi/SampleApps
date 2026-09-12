# Story Dialogue App

Scaffold for steps 1–3 of the story → AI video pipeline (see planning
discussion): parse a story into characters/scenes/dialogue, assign each
character a voice, and generate per-line dialogue audio.

- `backend/` — FastAPI service: Claude-based story parsing, voice assignment,
  ElevenLabs TTS. See `backend/README.md` for setup.
- `android/` — Kotlin/Jetpack Compose app: paste a story, hit the backend,
  see the extracted characters, and play each line of generated dialogue.

Video generation (turning scenes into AI-generated clips) is not built yet —
that's the next milestone once this dialogue pipeline is verified end to end.

## Running locally

1. Start the backend (`cd backend && uvicorn app.main:app --reload`).
2. Open `android/` in Android Studio, run on an emulator — it's preconfigured
   to hit `http://10.0.2.2:8000/` (the host machine's localhost from the
   emulator). For a physical device, change `API_BASE_URL` in
   `android/app/build.gradle.kts` to your machine's LAN IP.
