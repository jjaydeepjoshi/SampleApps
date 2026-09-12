from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import AudioRequest, AudioResponse, ParsedStoryWithVoices, StoryRequest
from .story_parser import parse_story
from .tts import generate_dialogue_audio
from .voice_assignment import assign_voices

load_dotenv()

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
    try:
        parsed = parse_story(request.story)
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
