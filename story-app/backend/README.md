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
4. **Scene video generation** (`app/video_gen.py`) — for each dialogue line,
   generates (and caches per character) a portrait of that line's speaker
   from Pollinations.ai's free, keyless text-to-image API, then animates it
   with an `ffmpeg` Ken Burns pan/zoom for exactly that line's audio
   duration; a scene's clip is these per-line clips concatenated, so the
   visual switches to match whoever is speaking. A scene with no dialogue
   falls back to a single setting/description image for the whole scene.
   (Hugging Face's Inference API was tried first but turned out to be
   unreachable from at least this backend's host network — see the
   trade-offs section below.)
5. **Final video assembly** (`app/assembly.py`) — muxes each scene's dialogue
   audio onto its animated clip and concatenates all scenes into one final
   MP4 via `ffmpeg`.

## Setup: running on your own computer

```bash
cd story-app/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`ffmpeg` (with `ffprobe`) must also be installed and on `PATH`
(`apt install ffmpeg` / `brew install ffmpeg`).

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

## Setup: hosting it for free (no computer needed)

If you're only on a phone with no computer to run the backend on, deploy it
to a free always-on-the-internet host instead — the app then talks to a
public URL rather than a LAN IP.

**Render.com (recommended, free tier, no credit card):**

1. Sign up at https://render.com (can connect directly with GitHub).
2. New → **Blueprint** → pick this repo. Render reads `render.yaml` at the
   repo root automatically and builds `story-app/backend/Dockerfile` (which
   already installs `ffmpeg`).
3. Deploy. You'll get a URL like `https://story-dialogue-backend-xxxx.onrender.com`.
4. In the app's Settings screen, set the backend URL to that URL with a
   trailing slash, e.g. `https://story-dialogue-backend-xxxx.onrender.com/`.

Notes:
- Render's free tier spins the service down after ~15 minutes idle. The
  first request after that can take 30-60s to wake it back up — the app's
  network timeout is generous (10 minutes) specifically to survive this,
  so just wait on the first request after a period of inactivity.
- Any other host that runs a Dockerfile (Fly.io, Railway, etc.) works the
  same way — point it at `story-app/backend/Dockerfile`.

### API keys: bring-your-own, per user, from the app

This backend holds **no API key of its own** — it's a shared/multi-tenant
service. Every caller (the Android app) supplies their own free Groq API key
with each request, and the backend just forwards it to Groq. This means:

- Each user signs up for their own free Groq account in the app's Settings
  screen — no shared secret to manage or leak on the server.
- `/parse-story` requires `groq_api_key` in the request body.
- Dialogue voices need no key (`edge-tts` is free and keyless), and neither
  does scene image generation (Pollinations.ai is free and keyless too).

Get a free Groq key at https://console.groq.com/keys (no credit card).

## Endpoints

- `POST /parse-story` — `{"story": "...", "groq_api_key": "..."}` → characters, scenes, dialogue, voice assignments
- `POST /generate-audio` — `{"parsed_story": <output of /parse-story>}` → base64 audio clips per line
- `POST /generate-scene-video` — `{"parsed_story": ..., "audio_clips": [...], "scene_id": N}` → base64 video clip for one scene, timed to match that scene's dialogue. The app calls this once per scene in a loop so it can show "scene X of Y" progress.
- `POST /generate-video` — `{"parsed_story": ..., "audio_clips": [...]}` → base64 video clip per scene for the whole story in one request (kept for callers that don't need per-scene progress)
- `POST /assemble-final-video` — `{"video_clips": [...], "audio_clips": [...]}` → base64 final MP4
- `GET /health`

## Notes / trade-offs of the free stack

- Groq's free Llama models are good but not as reliable at strict JSON/reasoning as Claude — occasional malformed output is possible; retry on 502 from `/parse-story` if it happens.
- Groq retires model IDs over time (`llama-3.3-70b-versatile` was already decommissioned once during development — error was `model_not_found`). If `/parse-story` starts failing with that error again, set a `GROQ_MODEL` env var on your host to a currently-supported model ID (check with `curl -H "Authorization: Bearer $GROQ_API_KEY" https://api.groq.com/openai/v1/models`) — no code change needed.
- `edge-tts` has no true emotion control (just rate/pitch approximation) and a fixed voice catalog — see `_VOICE_POOLS` in `voice_assignment.py` to add more languages/voices. Hindi currently only has one male and one female voice (no age variety) since that's all edge-tts ships for `hi-IN`.
- Scene image prompts are built from the setting/description in the story's own language; most text-to-image models work best with English prompts, so non-English stories may get lower-quality scene images even though dialogue audio is correct.
- There's no free true text-to-video API, so scene "video" here is a still AI image animated with a pan/zoom effect rather than actual generated motion. This is a common, genuinely free technique but won't look like Runway/Pika output. If you later get budget for a real video-gen API, swap `_generate_scene_image` + `_animate_image` in `video_gen.py` for a text-to-video call — the rest of the pipeline (prompt building, duration matching, assembly) carries over unchanged.
- Per-line character portraits are not lip-synced or animated faces — no free service does that. It's a per-character still image switched in time with the dialogue audio, which at least shows the right character while they're speaking instead of one static scene image throughout. Real lip-synced/animated talking video would need a paid service (e.g. HeyGen, D-ID) or a locally-run model with real compute (e.g. SadTalker/Wav2Lip on a GPU), neither of which fits the free/keyless constraint this stack is built around.
- `_portrait_cache` is a plain in-memory dict, per backend process, never evicted — fine for personal/low-traffic use, but would grow unbounded with many distinct characters across many stories on a long-running shared instance.
- **Why Pollinations.ai instead of Hugging Face**: Hugging Face's Inference API (both the legacy `api-inference.huggingface.co` host and the newer `router.huggingface.co`) was unreachable from a real Render deployment — DNS resolution failed persistently ("[Errno -5] No address associated with hostname") even with retries and forced IPv4, while Groq and edge-tts worked fine from the same instance. That pattern (one third-party's domains specifically unreachable, others fine) is consistent with the host's IP range being blocked by that provider's anti-abuse system rather than a bug in this code. Pollinations.ai needs no API key/account, which also removed a whole Settings field from the app.
