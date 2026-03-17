from __future__ import annotations

POS_LABEL_MAP = {
    "n": "名詞 noun",
    "noun": "名詞 noun",
    "v": "動詞 verb",
    "verb": "動詞 verb",
    "adj": "形容詞 adjective",
    "adjective": "形容詞 adjective",
    "a": "形容詞 adjective",
    "s": "形容詞 adjective",
    "adv": "副詞 adverb",
    "adverb": "副詞 adverb",
}


def normalize_part_of_speech(value: str | None) -> str:
    if not value:
        return "不明 unknown"
    raw = value.strip()
    key = raw.lower()
    if key in POS_LABEL_MAP:
        return POS_LABEL_MAP[key]

    if "noun" in key or "名詞" in raw:
        return POS_LABEL_MAP["noun"]
    if "verb" in key or "動詞" in raw:
        return POS_LABEL_MAP["verb"]
    if "adjective" in key or "形容詞" in raw:
        return POS_LABEL_MAP["adjective"]
    if "adverb" in key or "副詞" in raw:
        return POS_LABEL_MAP["adverb"]
    return f"{raw} ({key})"
