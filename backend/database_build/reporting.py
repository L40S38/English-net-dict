from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class FieldDiff:
    name: str
    before: Any
    after: Any


def debug_json(value: object, max_len: int = 800) -> str:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def print_diffs(diffs: list[FieldDiff], indent: str = "    ") -> None:
    for diff in diffs:
        print(f"{indent}{diff.name}(before): {debug_json(diff.before)}")
        print(f"{indent}{diff.name}(after):  {debug_json(diff.after)}")


def print_summary(updated: int, skipped: int, errors: int) -> None:
    print("---")
    print(f"UPDATED: {updated}")
    print(f"SKIPPED: {skipped}")
    print(f"ERRORS: {errors}")
