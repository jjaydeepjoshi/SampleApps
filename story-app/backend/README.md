# Story Dialogue Backend

Full story-to-video pipeline, built entirely on free services (no paid API
required):

1. **Story parsing** (`app/story_parser.py`) — sends the story to Groq's free
   API (Llama 3.3), gets back structured JSON: detected language, characters,
   scenes, and per-line dialogue with inferred emotion. Names and dialogue
   are kept in the story's original language (no translation).
2. **Voice assignment** (`app/voice_assignment.py`) — maps each character to a
   free Microsoft Edge neural voice based on the detected language plus
   inferred gender/age (e.g. Hindi stories get `hi-IN-MadhurNeural` /
   `hi-IN-SwaraNeural`; unsupported languages fall back to English voices).
3. **Dialogue audio generation** (`app/tts.py`) — uses `edge-tts` (free,
   keyless) to synthesize each dialogue line, approximating emotion via
   rate/pitch, and measures real duration with `ffprobe`.
4. **Scene video generation** (`app/video_gen.py`) — generates one still
   image per scene from Hugging Face's free Inference API (Stable Diffusion
   2.1), then animates it with an `ffmpeg` Ken Burns pan/zoom, timed to match
   that scene's total dialogue duration.
5. **Final video assembly** (`app/assembly.py`) — muxes each scene's dialogue
   audio onto its animated clip and concatenates all scenes into one final
   MP4 via `ffmpeg`.

## Setup

```bash
cd story-app/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`ffmpeg` (with `ffprobe`) must also be installed and on `PATH`
(`apt install ffmpeg` / `brew install ffmpeg`).

### Connecting from a real phone (not an emulator)

`--host 0.0.0.0` is required — without it, uvicorn only accepts connections
from `localhost` and a phone on the same Wi-Fi can't reach it at all. Then:

1. Find your computer's LAN IP (`ipconfig getifaddr en0` on Mac, `ipconfig`
   on Windows, `hostname -I` on Linux).
2. Make sure your phone and computer are on the same Wi-Fi network.
3. In the app's Settings screen, set the backend URL to
   `http://<that-ip>:8000/` (not `10.0.2.2`, which only exists inside the
   Android Emulator).
4. Check your computer's firewall isn't blocking incoming connections on
   port 8000.

### API keys: bring-your-own, per user, from the app

This backend holds **no API keys of its own** — it's a shared/multi-tenant
service. Every caller (the Android app) supplies their own free Groq API key
and Hugging Face token with each request, and the backend just forwards them
to the respective free API. This means:

- Each user signs up for their own free Groq/Hugging Face account in the app's
  Settings screen — no shared secret to manage or leak on the server.
- `/parse-story` requires `groq_api_key` in the request body.
- `/generate-video` requires `huggingface_api_token` in the request body.
- Dialogue voices need no key at all (`edge-tts` is free and keyless).

Getting the free keys: Groq at https://console.groq.com/keys (no credit
card), Hugging Face at https://huggingface.co/settings/tokens (free account).

## Endpoints

- `POST /parse-story` — `{"story": "...", "groq_api_key": "..."}` → characters, scenes, dialogue, voice assignments
- `POST /generate-audio` — `{"parsed_story": <output of /parse-story>}` → base64 audio clips per line
- `POST /generate-video` — `{"parsed_story": ..., "audio_clips": [...], "huggingface_api_token": "..."}` → base64 video clip per scene, timed to match that scene's dialogue
- `POST /assemble-final-video` — `{"video_clips": [...], "audio_clips": [...]}` → base64 final MP4
- `GET /health`

## Notes / trade-offs of the free stack

- Groq's free Llama models are good but not as reliable at strict JSON/reasoning as Claude — occasional malformed output is possible; retry on 502 from `/parse-story` if it happens.
- `edge-tts` has no true emotion control (just rate/pitch approximation) and a fixed voice catalog — see `_VOICE_POOLS` in `voice_assignment.py` to add more languages/voices. Hindi currently only has one male and one female voice (no age variety) since that's all edge-tts ships for `hi-IN`.
- Scene image prompts (for Hugging Face) are built from the setting/description in the story's own language; Stable Diffusion tends to work best with English prompts, so non-English stories may get lower-quality scene images even though dialogue audio is correct.
- There's no free true text-to-video API, so scene "video" here is a still AI image animated with a pan/zoom effect rather than actual generated motion. This is a common, genuinely free technique but won't look like Runway/Pika output. If you later get budget for a real video-gen API, swap `_generate_scene_image` + `_animate_image` in `video_gen.py` for a text-to-video call — the rest of the pipeline (prompt building, duration matching, assembly) carries over unchanged.
- Hugging Face's free Inference API can be slow (model cold starts) and rate-limited; for heavier use, consider running Stable Diffusion locally instead.
