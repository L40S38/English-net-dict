from __future__ import annotations

import argparse
import json

from app.scripts.patch_base import add_common_args, create_session, load_words, prepare_database, print_summary

MARKERS = {"er", "est", "more", "most"}


def _regular_adj_forms(word: str) -> tuple[str, str]:
    lower = word.lower()
    if lower.endswith("y") and len(word) > 1 and lower[-2] not in "aeiou":
        return f"{word[:-1]}ier", f"{word[:-1]}iest"
    if lower.endswith("e"):
        return f"{word}r", f"{word}st"
    return f"{word}er", f"{word}est"


def _normalize_markers(word: str, forms: dict) -> dict:
    next_forms = dict(forms)
    c_raw = str(forms.get("comparative", "")).strip()
    s_raw = str(forms.get("superlative", "")).strip()
    c = c_raw.lower()
    s = s_raw.lower()

    if c not in MARKERS and s not in MARKERS:
        return next_forms

    reg_c, reg_s = _regular_adj_forms(word)

    # Known noisy pair seen in DB: comparative=er, superlative=more.
    if c == "er" and s == "more":
        next_forms["comparative"] = f"more {word}"
        next_forms["superlative"] = f"most {word}"
        return next_forms

    if c == "er":
        next_forms["comparative"] = reg_c

    if s == "est":
        next_forms["superlative"] = reg_s

    return next_forms


async def run(dry_run: bool = False, limit: int | None = None, word_filter: str | None = None) -> None:
    prepare_database()
    db = create_session()
    updated = 0
    skipped = 0
    errors = 0
    marker_rows = 0

    try:
        words = load_words(db, word_filter=word_filter, limit=limit)
        total = len(words)
        print(f"Targets: {total}" + (" (dry-run)" if dry_run else ""))
        for idx, word in enumerate(words, start=1):
            forms = dict(word.forms or {})
            if not isinstance(forms, dict):
                skipped += 1
                continue
            c = str(forms.get("comparative", "")).strip().lower()
            s = str(forms.get("superlative", "")).strip().lower()
            if c not in MARKERS and s not in MARKERS:
                skipped += 1
                continue
            marker_rows += 1
            next_forms = _normalize_markers(word.word, forms)
            if next_forms == forms:
                skipped += 1
                continue
            print(
                f"  [{idx}/{total}] {word.word} forms:\n"
                f"    before={json.dumps(forms, ensure_ascii=True)}\n"
                f"    after ={json.dumps(next_forms, ensure_ascii=True)}"
            )
            word.forms = next_forms
            if dry_run:
                db.rollback()
            else:
                db.commit()
            updated += 1
    except Exception as exc:  # noqa: BLE001
        errors += 1
        db.rollback()
        print(f"ERROR: {exc}")
    finally:
        db.close()

    print(f"MARKER_ROWS: {marker_rows}")
    print_summary(updated, skipped, errors)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix marker-only comparative/superlative forms")
    add_common_args(parser)
    args = parser.parse_args()
    import asyncio

    asyncio.run(run(dry_run=args.dry_run, limit=args.limit, word_filter=args.word))


if __name__ == "__main__":
    main()
