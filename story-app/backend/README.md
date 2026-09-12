# Story Dialogue Backend

Full story-to-video pipeline, built entirely on free services (no paid API
required):

1. **Story parsing** (`app/story_parser.py`) — sends the story to Groq's free
   API (Llama 3.3), gets back structured JSON: characters, scenes, and
   per-line dialogue with inferred emotion.
2. **Voice assignment** (`app/voice_assignment.py`) — maps each character to a
   free Microsoft Edge neural voice based on inferred gender/age.
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
cp .env.example .env  # fill in GROQ_API_KEY and HUGGINGFACE_API_TOKEN (both free)
uvicorn app.main:app --reload
```

`ffmpeg` (with `ffprobe`) must also be installed and on `PATH`
(`apt install ffmpeg` / `brew install ffmpeg`).

### Getting free API keys

- **Groq** (story parsing): sign up at https://console.groq.com/keys — free tier, no credit card.
- **Hugging Face** (scene images): sign up at https://huggingface.co — free account, create a token at https://huggingface.co/settings/tokens. The free Inference API has rate limits and a cold-start delay per model, but no cost.
- Dialogue voices need no key at all (`edge-tts` is free and keyless).

## Endpoints

- `POST /parse-story` — `{"story": "..."}` → characters, scenes, dialogue, voice assignments
- `POST /generate-audio` — `{"parsed_story": <output of /parse-story>}` → base64 audio clips per line
- `POST /generate-video` — `{"parsed_story": ..., "audio_clips": [...]}` → base64 video clip per scene, timed to match that scene's dialogue
- `POST /assemble-final-video` — `{"video_clips": [...], "audio_clips": [...]}` → base64 final MP4
- `GET /health`

## Notes / trade-offs of the free stack

- Groq's free Llama models are good but not as reliable at strict JSON/reasoning as Claude — occasional malformed output is possible; retry on 502 from `/parse-story` if it happens.
- `edge-tts` has no true emotion control (just rate/pitch approximation) and a fixed voice catalog — see `_VOICE_POOL` in `voice_assignment.py` to add more voices.
- There's no free true text-to-video API, so scene "video" here is a still AI image animated with a pan/zoom effect rather than actual generated motion. This is a common, genuinely free technique but won't look like Runway/Pika output. If you later get budget for a real video-gen API, swap `_generate_scene_image` + `_animate_image` in `video_gen.py` for a text-to-video call — the rest of the pipeline (prompt building, duration matching, assembly) carries over unchanged.
- Hugging Face's free Inference API can be slow (model cold starts) and rate-limited; for heavier use, consider running Stable Diffusion locally instead.
