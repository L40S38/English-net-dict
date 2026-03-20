"""Fix linked forms for inflected words.

Usage:
    uv run python -m app.scripts.patch_fix_inflected_words [--word WORD] [--limit N] [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from sqlalchemy import func, select

from app.models import Phrase, Word
from app.scripts.patch_base import add_common_args, create_session, load_words, prepare_database, print_summary

FORM_KEYS = (
    "third_person_singular",
    "present_participle",
    "past_tense",
    "past_participle",
    "plural",
    "comparative",
    "superlative",
)


def _build_report_rows(words: list[Word]) -> list[dict[str, str]]:
    by_lower = {w.word.lower(): w for w in words}
    pairs_by_type: dict[str, list[tuple[Word, Word]]] = defaultdict(list)
    for base in words:
        forms = base.forms if isinstance(base.forms, dict) else {}
        for key in FORM_KEYS:
            value = forms.get(key)
            if not isinstance(value, str):
                continue
            inflected_text = value.strip()
            if not inflected_text:
                continue
            inflected = by_lower.get(inflected_text.lower())
            if not inflected:
                continue
            if inflected.id == base.id:
                continue
            pairs_by_type[key].append((base, inflected))

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for key in FORM_KEYS:
        for base, inflected in sorted(set(pairs_by_type[key]), key=lambda x: (x[1].word.lower(), x[0].word.lower())):
            dedup_key = (inflected.word.lower(), base.word.lower(), key)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            rows.append(
                {
                    "word": inflected.word,
                    "lemma": base.word,
                    "lemma_word_id": str(base.id),
                    "inflection_type": key,
                    "has_own_content": "False",
                    "lemma_candidates": base.word,
                    "selected_lemma": base.word,
                    "suggestion": "merge",
                    "action": "",
                }
            )
    return rows


def _write_report(output_file: Path, rows: list[dict[str, str]]) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "word",
        "lemma",
        "lemma_word_id",
        "inflection_type",
        "has_own_content",
        "lemma_candidates",
        "selected_lemma",
        "suggestion",
        "action",
    ]
    with output_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


async def run(
    dry_run: bool = False,
    limit: int | None = None,
    word_filter: str | None = None,
    *,
    output_file: Path,
    apply_known_fixes: bool = False,
) -> None:
    prepare_database()
    db = create_session()
    updated = 0
    skipped = 0
    errors = 0
    try:
        if apply_known_fixes:
            a_pos = db.scalar(select(Word).where(func.lower(Word.word) == "a's"))
            if a_pos:
                print("Fixing a's records ...")
                phrase = db.scalar(select(Phrase).where(Phrase.text == "take a's place"))
                if phrase:
                    phrase.text = "take A's place"
                    updated += 1
                    print("  phrase: take a's place -> take A's place")
                db.delete(a_pos)
                updated += 1
                print("  deleted word: a's")
            else:
                skipped += 1

        words = load_words(db, word_filter=word_filter, limit=limit)
        rows = _build_report_rows(words)
        _write_report(output_file, rows)
        print(f"Inflection report written: {output_file}")
        print(f"Rows: {len(rows)}")

        if dry_run:
            db.rollback()
        else:
            db.commit()
    except Exception as exc:  # noqa: BLE001
        errors += 1
        db.rollback()
        print(f"ERROR: {exc}")
    finally:
        db.close()

    print_summary(updated, skipped, errors)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report existing inflection overlaps in DB (CSV), and optionally apply known one-off fixes"
    )
    add_common_args(parser)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "existing_inflection_report.csv",
        help="Output CSV path for existing inflection overlaps",
    )
    parser.add_argument(
        "--apply-known-fixes",
        action="store_true",
        help="Also apply known one-off fixes (delete a's, rename phrase take a's place -> take A's place)",
    )
    args = parser.parse_args()
    import asyncio

    asyncio.run(
        run(
            dry_run=args.dry_run,
            limit=args.limit,
            word_filter=args.word,
            output_file=args.output,
            apply_known_fixes=args.apply_known_fixes,
        )
    )


if __name__ == "__main__":
    main()
