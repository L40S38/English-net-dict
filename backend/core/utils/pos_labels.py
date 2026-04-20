from __future__ import annotations

import re

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
    "pron": "代名詞 pronoun",
    "pronoun": "代名詞 pronoun",
    "prep": "前置詞 preposition",
    "preposition": "前置詞 preposition",
    "conj": "接続詞 conjunction",
    "conjunction": "接続詞 conjunction",
    "interj": "間投詞 interjection",
    "interjection": "間投詞 interjection",
    "det": "限定詞 determiner",
    "determiner": "限定詞 determiner",
    "article": "冠詞 article",
    "num": "数詞 numeral",
    "numeral": "数詞 numeral",
}


def normalize_part_of_speech(value: str | None) -> str:
    if not value:
        return "不明 unknown"
    raw = value.strip()
    # Idempotency: if already normalized label, keep as-is.
    if raw in POS_LABEL_MAP.values():
        return raw

    # Collapse legacy/unknown formatting like: "conjunction (conjunction)" or repeated nesting.
    # Take the left-most base token and normalize again.
    m = re.match(r"^(?P<base>.+?)\s*\((?P<inner>.+?)\)\s*$", raw)
    if m:
        base = (m.group("base") or "").strip()
        inner = (m.group("inner") or "").strip().lower()
        if base and inner and inner == base.lower():
            raw = base
        else:
            # If it looks like nested repeats, keep only the base part.
            raw = base or raw

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
    if "pronoun" in key or "代名詞" in raw:
        return POS_LABEL_MAP["pronoun"]
    if "preposition" in key or "前置詞" in raw:
        return POS_LABEL_MAP["preposition"]
    if "conjunction" in key or "接続詞" in raw:
        return POS_LABEL_MAP["conjunction"]
    if "interjection" in key or "間投詞" in raw:
        return POS_LABEL_MAP["interjection"]
    return f"{raw} ({key})"
