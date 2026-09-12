import json
import os

from anthropic import Anthropic

from .models import ParsedStory

_SYSTEM_PROMPT = """You convert a short story into structured JSON for a dialogue/video pipeline.

Return ONLY valid JSON matching this shape, no prose, no markdown fences:
{
  "characters": [
    {
      "name": string,
      "description": string,
      "personality": string,
      "voice_gender": "male" | "female" | "neutral",
      "voice_age": "child" | "young_adult" | "adult" | "elderly",
      "voice_tone": string (e.g. "warm and calm", "gruff and sharp")
    }
  ],
  "scenes": [
    {
      "id": integer starting at 1,
      "setting": string (where/when the scene takes place),
      "description": string (what happens, for a video generator),
      "dialogue": [
        {"speaker": string (must match a character name), "line": string, "emotion": string}
      ]
    }
  ]
}

Rules:
- Only include characters who actually speak or are clearly named.
- Split the story into scenes by location/time changes.
- Infer emotion per line from context (e.g. "angry", "sad", "excited", "neutral").
- Keep descriptions concise (1-2 sentences).
"""


def _client() -> Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return Anthropic(api_key=api_key)


def parse_story(story_text: str) -> ParsedStory:
    client = _client()
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": story_text}],
    )
    raw_text = "".join(
        block.text for block in response.content if block.type == "text"
    )
    data = json.loads(raw_text)
    return ParsedStory.model_validate(data)
