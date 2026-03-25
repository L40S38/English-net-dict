from __future__ import annotations

import re


def normalize_phrase_entries(raw_phrases: object) -> list[dict[str, str]]:
    if not isinstance(raw_phrases, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in raw_phrases:
        if isinstance(item, str):
            phrase = item.strip()
            if phrase:
                normalized.append({"phrase": phrase, "meaning": ""})
            continue
        if not isinstance(item, dict):
            continue
        phrase = str(item.get("phrase", item.get("text", ""))).strip()
        if not phrase:
            continue
        meaning = str(item.get("meaning", item.get("meaning_en", item.get("meaning_ja", "")))).strip()
        normalized.append({"phrase": phrase, "meaning": meaning})
    return normalized


def is_multi_token(text: str) -> bool:
    tokens = [t for t in re.split(r"\s+", text.strip()) if t]
    return len(tokens) >= 2
