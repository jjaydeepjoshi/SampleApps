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
    characters: list[Character]
    scenes: list[Scene]


class StoryRequest(BaseModel):
    story: str


class VoiceAssignment(BaseModel):
    character: str
    voice_id: str


class ParsedStoryWithVoices(BaseModel):
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
