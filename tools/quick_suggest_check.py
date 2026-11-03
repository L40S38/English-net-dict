from __future__ import annotations

from app.database import SessionLocal
from app.services.group_suggest_service import suggest_group_candidates


def main() -> int:
    keywords = [
        "会社の部署",
        "end with department",
        "department",
    ]
    with SessionLocal() as db:
        result = suggest_group_candidates(db, keywords, limit=30)
    print("keywords:", result.keywords)
    print("candidates:", len(result.candidates))
    for c in result.candidates[:30]:
        if c.item_type == "word":
            label = c.word
        elif c.item_type == "phrase":
            label = f"{c.phrase_text} / {c.phrase_meaning or ''}"
        else:
            label = f"{c.word}: {c.example_en or ''}"
        print(f"- {label} (type={c.item_type}, score={c.score})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
