from pydantic import BaseModel


class DialogueLine(BaseModel):
    speaker: str
    line: str
    emotion: str


class Scene(BaseModel):
    id: int
    setting: str
    description: str
    dialogue: list[DialogueLine]


class Character(BaseModel):
    name: str
    description: str
    personality: str
    voice_gender: str
    voice_age: str
    voice_tone: str


class ParsedStory(BaseModel):
    language: str
    characters: list[Character]
    scenes: list[Scene]


class StoryRequest(BaseModel):
    story: str
    groq_api_key: str


class VoiceAssignment(BaseModel):
    character: str
    voice_id: str


class ParsedStoryWithVoices(BaseModel):
    language: str
    characters: list[Character]
    scenes: list[Scene]
    voice_assignments: list[VoiceAssignment]


class AudioRequest(BaseModel):
    parsed_story: ParsedStoryWithVoices


class AudioClip(BaseModel):
    scene_id: int
    speaker: str
    line: str
    audio_base64: str
    duration_seconds: float


class AudioResponse(BaseModel):
    clips: list[AudioClip]


class VideoRequest(BaseModel):
    parsed_story: ParsedStoryWithVoices
    audio_clips: list[AudioClip] = []
    huggingface_api_token: str


class VideoClip(BaseModel):
    scene_id: int
    prompt: str
    video_base64: str


class VideoResponse(BaseModel):
    clips: list[VideoClip]


class FinalVideoRequest(BaseModel):
    video_clips: list[VideoClip]
    audio_clips: list[AudioClip]


class FinalVideoResponse(BaseModel):
    video_base64: str
