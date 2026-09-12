# Story Dialogue Backend

Full story-to-video pipeline:

1. **Story parsing** (`app/story_parser.py`) — sends the story to Claude, gets
   back structured JSON: characters, scenes, and per-line dialogue with
   inferred emotion.
2. **Voice assignment** (`app/voice_assignment.py`) — maps each character to a
   TTS voice based on inferred gender/age.
3. **Dialogue audio generation** (`app/tts.py`) — calls ElevenLabs per
   dialogue line and returns base64-encoded audio clips.
4. **Scene video generation** (`app/video_gen.py`) — builds a text-to-video
   prompt per scene (setting + description + characters present) and calls
   Runway's API, polling until each clip is ready.
5. **Final video assembly** (`app/assembly.py`) — muxes each scene's dialogue
   audio onto its generated clip and concatenates all scenes into one final
   MP4 via `ffmpeg`.

## Setup

```bash
cd story-app/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, RUNWAY_API_KEY
uvicorn app.main:app --reload
```

`ffmpeg` must also be installed and on `PATH` (`apt install ffmpeg` / `brew install ffmpeg`) — `assembly.py` shells out to it.

## Endpoints

- `POST /parse-story` — `{"story": "..."}` → characters, scenes, dialogue, voice assignments
- `POST /generate-audio` — `{"parsed_story": <output of /parse-story>}` → base64 audio clips per line
- `POST /generate-video` — `{"parsed_story": <output of /parse-story>}` → base64 video clip per scene
- `POST /assemble-final-video` — `{"video_clips": [...], "audio_clips": [...]}` → base64 final MP4
- `GET /health`

## Notes / next steps

- `_VOICE_POOL` in `voice_assignment.py` uses placeholder ElevenLabs voice
  IDs — replace with real IDs from your account.
- `duration_seconds` in `tts.py` is a word-count estimate; decode the actual
  audio to get a precise duration if you need exact scene timing.
- `video_gen.py` targets Runway's Gen-3 Turbo text-to-video API; swap in
  another provider (Pika, Kling, HeyGen) by replacing `_create_task`/
  `_poll_task` — the rest of the pipeline (prompt building, polling loop
  shape) carries over.
- Scene videos and dialogue lines aren't generated with matching durations
  yet — `assembly.py` mixes audio onto the video with `-shortest`, so a
  scene's dialogue may get cut off if it's longer than the generated clip.
  Tightening this (e.g. requesting longer clips, or looping/extending video
  to match audio length) is the next thing to fix once this is running
  end to end.
