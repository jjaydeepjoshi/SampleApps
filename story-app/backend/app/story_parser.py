import json

import httpx

from .models import ParsedStory

# Groq offers a free API tier (no credit card required) serving open models
# like Llama 3.3 at very low latency. Get a free key at console.groq.com.
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = "llama-3.3-70b-versatile"

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


def parse_story(story_text: str, api_key: str) -> ParsedStory:
    if not api_key:
        raise RuntimeError("a Groq API key is required (set it in the app's Settings screen)")

    response = httpx.post(
        _GROQ_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": _GROQ_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": story_text},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.4,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    raw_text = response.json()["choices"][0]["message"]["content"]
    data = json.loads(raw_text)
    return ParsedStory.model_validate(data)
