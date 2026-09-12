# Story Dialogue App

Full scaffold of the story → AI video pipeline: parse a story into
characters/scenes/dialogue, assign each character a voice, generate
per-line dialogue audio, generate an AI video clip per scene, and mux it
all into one final video.

- `backend/` — FastAPI service: Claude-based story parsing, voice assignment,
  ElevenLabs TTS, Runway scene video generation, ffmpeg assembly. See
  `backend/README.md` for setup.
- `android/` — Kotlin/Jetpack Compose app: paste a story, hit the backend,
  see the extracted characters, play each line of generated dialogue, then
  generate and play the final assembled video.

## Running locally

1. Start the backend (`cd backend && uvicorn app.main:app --reload`).
2. Open `android/` in Android Studio, run on an emulator — it's preconfigured
   to hit `http://10.0.2.2:8000/` (the host machine's localhost from the
   emulator). For a physical device, change `API_BASE_URL` in
   `android/app/build.gradle.kts` to your machine's LAN IP.
