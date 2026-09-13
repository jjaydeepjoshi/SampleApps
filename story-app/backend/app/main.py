import base64

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .assembly import assemble_final_video
from .models import (
    AudioRequest,
    AudioResponse,
    FinalVideoRequest,
    FinalVideoResponse,
    ParsedStoryWithVoices,
    StoryRequest,
    VideoRequest,
    VideoResponse,
)
from .story_parser import parse_story
from .tts import generate_dialogue_audio
from .video_gen import generate_scene_videos
from .voice_assignment import assign_voices

app = FastAPI(title="Story Dialogue API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/parse-story", response_model=ParsedStoryWithVoices)
def parse_story_endpoint(request: StoryRequest) -> ParsedStoryWithVoices:
    if not request.story.strip():
        raise HTTPException(status_code=400, detail="story text is required")
    if not request.groq_api_key.strip():
        raise HTTPException(status_code=400, detail="groq_api_key is required")
    try:
        parsed = parse_story(request.story, request.groq_api_key)
    except Exception as exc:  # noqa: BLE001 - surfaced to the client
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return assign_voices(parsed)


@app.post("/generate-audio", response_model=AudioResponse)
async def generate_audio_endpoint(request: AudioRequest) -> AudioResponse:
    try:
        clips = await generate_dialogue_audio(request.parsed_story)
    except Exception as exc:  # noqa: BLE001 - surfaced to the client
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AudioResponse(clips=clips)


@app.post("/generate-video", response_model=VideoResponse)
async def generate_video_endpoint(request: VideoRequest) -> VideoResponse:
    try:
        clips = await generate_scene_videos(request.parsed_story, request.audio_clips)
    except Exception as exc:  # noqa: BLE001 - surfaced to the client
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return VideoResponse(clips=clips)


@app.post("/assemble-final-video", response_model=FinalVideoResponse)
def assemble_final_video_endpoint(request: FinalVideoRequest) -> FinalVideoResponse:
    try:
        video_bytes = assemble_final_video(request.video_clips, request.audio_clips)
    except Exception as exc:  # noqa: BLE001 - surfaced to the client
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return FinalVideoResponse(video_base64=base64.b64encode(video_bytes).decode("ascii"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
