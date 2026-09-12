# Story Dialogue App

Full scaffold of the story → AI video pipeline, built entirely on free
services: parse a story into characters/scenes/dialogue, assign each
character a voice, generate per-line dialogue audio, generate an AI video
clip per scene, and mux it all into one final video.

- `backend/` — FastAPI service: Groq-based story parsing, free Edge-TTS
  voices, Hugging Face scene images animated via ffmpeg, ffmpeg assembly.
  Holds no API keys itself — see `backend/README.md`.
- `android/` — Kotlin/Jetpack Compose app: each user enters their own free
  Groq/Hugging Face API keys in the Settings screen (encrypted on-device),
  then pastes a story, sees the extracted characters, plays each line of
  dialogue, and generates/plays the final assembled video.

## Running locally

1. Start the backend (`cd backend && uvicorn app.main:app --reload`).
2. Open `android/` in Android Studio, run on an emulator — it's preconfigured
   to hit `http://10.0.2.2:8000/` (the host machine's localhost from the
   emulator). For a physical device, change `API_BASE_URL` in
   `android/app/build.gradle.kts` to your machine's LAN IP.
3. On first launch, the app opens straight to Settings — get a free Groq key
   (https://console.groq.com/keys) and, for video, a free Hugging Face token
   (https://huggingface.co/settings/tokens), paste them in, and Save.

### Saved API keys survive app updates

`android/debug.keystore` is committed on purpose and every CI build signs
with it (see `app/build.gradle.kts`). Without a fixed keystore, each new APK
build would be signed differently, Android would treat it as a different
app on install, and installing an update would silently wipe the app's
saved settings — including your API keys. As long as you install new
builds over the existing app (don't manually uninstall first), your saved
keys carry over.
