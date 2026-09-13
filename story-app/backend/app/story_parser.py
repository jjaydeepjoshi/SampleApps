import json
import os
import re
import time

import httpx
from json_repair import repair_json

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
# Groq's /models list mixes chat-completion models in with audio (TTS/STT),
# moderation, and other non-chat model types - picking blindly from it once
# returned an actual text-to-speech model. Exclude anything matching these
# known non-chat naming patterns before considering a model as a candidate.
_NON_CHAT_HINTS = ("whisper", "tts", "orpheus", "guard", "moderation", "playai")
# Prefer well-known plain (non chain-of-thought) chat model families when
# nothing on the preferred list matches, since a reasoning/"thinking" model
# needs special handling (see _extract_json) and more tokens for the same
# answer - fine as a fallback, just not the first choice among unknowns.
_CHAT_FAMILY_HINTS = ("llama", "gpt", "gemma", "mixtral", "deepseek", "qwen", "kimi")


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

    chat_candidates = [
        m for m in available if not any(hint in m.lower() for hint in _NON_CHAT_HINTS)
    ] or available

    for candidate in _PREFERRED_MODELS:
        if candidate in chat_candidates:
            return candidate

    for candidate in chat_candidates:
        if any(hint in candidate.lower() for hint in _CHAT_FAMILY_HINTS):
            return candidate

    return chat_candidates[0]


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
- If you reason before answering, keep it to a few short sentences at most -
  most of your output budget must go to the JSON itself, not to reasoning.
"""


def _extract_json(raw_text: str) -> dict:
    # Not every model on Groq honors response_format's strict JSON-schema
    # enforcement equally well (one already outright rejected it as
    # unparsable), so don't rely on that mode at all - just ask for JSON in
    # the prompt and parse defensively, tolerant of markdown fences or
    # leading/trailing prose a model might still add despite instructions.
    #
    # Reasoning models (one got auto-selected in testing: qwen/qwen3.6-27b)
    # emit a <think>...</think> chain-of-thought block before their real
    # answer. Strip a *closed* block outright; an unclosed one means the
    # response got cut off mid-thought before ever reaching the JSON, which
    # a bigger max_tokens (set on the request) should prevent going forward
    # - but if it still happens, there is no JSON left to recover here.
    text = raw_text.strip()
    if "<think>" in text and "</think>" not in text:
        raise RuntimeError(
            "Groq response was cut off mid-reasoning before producing any JSON "
            f"(response was truncated): {raw_text[:500]}"
        )
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start, end = text.find("{"), text.rfind("}")
    candidate = text[start : end + 1] if start != -1 and end != -1 and end > start else text

    # Small/fast models frequently produce near-valid JSON with a missing
    # comma or an unescaped quote inside a dialogue line (especially with
    # mixed-script text) - repair_json fixes exactly that class of mistake
    # rather than failing outright on a single stray character.
    repaired = repair_json(candidate)
    try:
        parsed = json.loads(repaired)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Groq response was not valid JSON: {raw_text[:500]}") from exc

    # repair_json degrades ungrammatical input (e.g. plain prose with no
    # JSON structure at all) to "" or similar rather than raising, so a
    # non-dict result means there was never real JSON here to recover.
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Groq response was not valid JSON: {raw_text[:500]}")
    return parsed


_OTPM_LIMIT_RE = re.compile(r"output tokens per minute \(OTPM\): Limit (\d+)")
_RETRY_AFTER_RE = re.compile(r"[Pp]lease try again in ([\d.]+)s")
_MAX_RATE_LIMIT_WAIT_SECONDS = 60.0


def parse_story(story_text: str, api_key: str) -> ParsedStory:
    if not api_key:
        raise RuntimeError("a Groq API key is required (set it in the app's Settings screen)")

    model = _resolve_model(api_key)

    def post(max_tokens: int) -> httpx.Response:
        return httpx.post(
            f"{_GROQ_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": story_text},
                ],
                "temperature": 0.4,
                # Generous headroom by default: a reasoning model's <think>
                # block alone can run to several thousand tokens before it
                # even starts the actual JSON answer. Some free-tier
                # accounts cap output-tokens-per-minute well below this
                # though (see the 429 retry below), in which case this gets
                # reduced automatically to whatever that account allows.
                "max_tokens": max_tokens,
            },
            timeout=90.0,
        )

    response = post(8192)

    for _ in range(2):
        if response.status_code != 429:
            break

        # Real test: the account had already used most of its per-minute
        # output-token budget from earlier attempts (Used 739/1000), so
        # simply shrinking max_tokens to "under the limit" doesn't help -
        # there just isn't enough budget left THIS minute regardless of
        # request size. Groq's error names exactly how long until the
        # window resets ("Please try again in 42.4s") - waiting that out is
        # the actual fix, not guessing at a smaller max_tokens.
        retry_after = _RETRY_AFTER_RE.search(response.text)
        if retry_after:
            wait_seconds = min(float(retry_after.group(1)) + 1.0, _MAX_RATE_LIMIT_WAIT_SECONDS)
            time.sleep(wait_seconds)
            response = post(8192)
            continue

        otpm_limit = _OTPM_LIMIT_RE.search(response.text)
        if otpm_limit:
            # No explicit wait time given - fall back to sizing the request
            # to fit the account's per-minute cap instead.
            retry_max_tokens = max(256, int(otpm_limit.group(1)) - 32)
            response = post(retry_max_tokens)
            continue

        break

    if response.status_code >= 400:
        # httpx's default raise_for_status() message drops the response body,
        # which is where Groq actually explains what went wrong (bad key,
        # decommissioned model, etc.) - surface that instead of a bare status.
        raise RuntimeError(
            f"Groq API error {response.status_code} (model={model}): {response.text}"
        )
    raw_text = response.json()["choices"][0]["message"]["content"]
    data = _extract_json(raw_text)
    return ParsedStory.model_validate(data)
