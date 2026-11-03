from __future__ import annotations

import json

from openai import OpenAI

from core.config import settings
from core.utils.prompt_loader import load_prompt
from core.utils.text_repair import repair_nested_strings

_PROMPT_FILE = "read_aloud_feedback.md"


def _strip_json_code_fence(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```json"):
        value = value[len("```json") :].strip()
    elif value.startswith("```"):
        value = value[len("```") :].strip()
    if value.endswith("```"):
        value = value[:-3].strip()
    return value


def generate_pronunciation_feedback(
    *,
    script_text: str,
    transcript: str,
    score: int,
    wrong_words: list[str],
    wrong_phrases: list[str],
) -> dict:
    """Asks an LLM for concrete, phonetics-aware pronunciation advice (which
    sound to focus on, how to link two words smoothly) instead of just
    reporting which words matched — word alignment alone can say *that* a
    word was wrong, not *how* to fix it."""
    if not settings.openai_api_key:
        raise RuntimeError("OpenAI API key is not configured")

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = load_prompt(_PROMPT_FILE)
    payload = {
        "script": script_text,
        "transcript": transcript,
        "score": score,
        "wrong_words": wrong_words,
        "wrong_phrases": wrong_phrases,
    }
    completion = client.responses.create(
        model=settings.openai_model_structured,
        temperature=0.4,
        input=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    )
    text = _strip_json_code_fence(completion.output_text or "")
    data = repair_nested_strings(json.loads(text))
    if not isinstance(data, dict):
        raise ValueError("LLM response was not a JSON object")

    good_points = [str(x).strip() for x in data.get("good_points", []) if str(x).strip()]
    review_points = [str(x).strip() for x in data.get("review_points", []) if str(x).strip()]
    return {"good_points": good_points, "review_points": review_points}
