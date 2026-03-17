from __future__ import annotations

from typing import Any

from ftfy import fix_text

MOJIBAKE_MARKERS = ("縺", "繧", "隱", "譁", "�")


def _looks_mojibake(text: str) -> bool:
    return any(marker in text for marker in MOJIBAKE_MARKERS)


def has_suspected_mojibake(text: str | None) -> bool:
    if not text:
        return False
    sample = text.strip()
    if any(0xE000 <= ord(ch) <= 0xF8FF for ch in sample):
        return True
    marker_count = sum(sample.count(marker) for marker in MOJIBAKE_MARKERS)
    return marker_count > 0 and marker_count >= max(2, len(sample) // 8)


def repair_text(value: str | None) -> str:
    if not value:
        return ""

    text = fix_text(value).replace("\x00", "").strip()
    if not _looks_mojibake(text):
        return text

    candidates = [text]
    for src, dst in (("cp932", "utf-8"), ("shift_jis", "utf-8"), ("latin1", "utf-8")):
        try:
            fixed = text.encode(src, errors="ignore").decode(dst, errors="ignore").strip()
            if fixed:
                candidates.append(fixed)
        except Exception:  # noqa: BLE001
            continue

    candidates = sorted(candidates, key=lambda x: x.count("�") + x.count("縺") + x.count("繧"))
    best = candidates[0]
    return best if best else text


def repair_nested_strings(data: Any) -> Any:
    if isinstance(data, str):
        return repair_text(data)
    if isinstance(data, list):
        return [repair_nested_strings(x) for x in data]
    if isinstance(data, dict):
        return {k: repair_nested_strings(v) for k, v in data.items()}
    return data
