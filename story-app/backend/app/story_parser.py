import json
import os

import httpx

from .models import ParsedStory

# Groq offers a free API tier (no credit card required) serving open models
# at very low latency. Get a free key at console.groq.com. Groq periodically
# retires older model IDs (this broke once already - llama-3.3-70b-versatile
# was decommissioned), so the model is overridable via GROQ_MODEL without a
# code change/redeploy if it happens again; check the current list with
# `curl -H "Authorization: Bearer $GROQ_API_KEY" https://api.groq.com/openai/v1/models`.
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

_SYSTEM_PROMPT = """You convert a short story into structured JSON for a dialogue/video pipeline.

Return ONLY valid JSON matching this shape, no prose, no markdown fences:
{
  "language": string (BCP-47 code of the story's own language, e.g. "hi" for Hindi, "en" for English),
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
- Detect the language the story itself is written in and set "language" to it.
- Write every "name", "description", "personality", "setting", scene "description",
  and dialogue "line" in that SAME language as the input story. Do not translate
  to English or any other language, and do not transliterate — if the story is in
  Hindi (Devanagari), keep names and dialogue in Hindi (Devanagari) script.
- Only include characters who actually speak or are clearly named.
- Split the story into scenes by location/time changes.
- Infer emotion per line from context (e.g. "angry", "sad", "excited", "neutral");
  the emotion label itself should stay in English regardless of story language,
  since it drives voice/prosody settings, not narration.
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
    if response.status_code >= 400:
        # httpx's default raise_for_status() message drops the response body,
        # which is where Groq actually explains what went wrong (bad key,
        # decommissioned model, etc.) - surface that instead of a bare status.
        raise RuntimeError(f"Groq API error {response.status_code}: {response.text}")
    raw_text = response.json()["choices"][0]["message"]["content"]
    data = json.loads(raw_text)
    return ParsedStory.model_validate(data)
