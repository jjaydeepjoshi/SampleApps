import json
import os

import httpx

from .models import ParsedStory

# Groq offers a free API tier (no credit card required) serving open models
# at very low latency. Get a free key at console.groq.com. Groq's available
# model catalog changes over time/per-account (hardcoding one broke twice
# during development with "model_not_found"), so instead of guessing a fixed
# model ID, ask the key's own /models list what it actually has access to
# and pick the best match from there. GROQ_MODEL still forces a specific
# choice if set, skipping the discovery call.
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_PREFERRED_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "llama-3.1-8b-instant",
    "llama3-70b-8192",
    "llama3-8b-8192",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]


def _resolve_model(api_key: str) -> str:
    forced = os.environ.get("GROQ_MODEL")
    if forced:
        return forced

    response = httpx.get(
        f"{_GROQ_BASE_URL}/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"Groq API error {response.status_code} listing models: {response.text}"
        )
    available = [m["id"] for m in response.json().get("data", [])]
    if not available:
        raise RuntimeError("Groq API key has no available chat models")

    for candidate in _PREFERRED_MODELS:
        if candidate in available:
            return candidate
    return available[0]


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

    model = _resolve_model(api_key)

    response = httpx.post(
        f"{_GROQ_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
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
        raise RuntimeError(
            f"Groq API error {response.status_code} (model={model}): {response.text}"
        )
    raw_text = response.json()["choices"][0]["message"]["content"]
    data = json.loads(raw_text)
    return ParsedStory.model_validate(data)
