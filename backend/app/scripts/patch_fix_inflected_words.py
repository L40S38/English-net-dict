"""Fix linked forms for inflected words.

Usage:
    uv run python -m app.scripts.patch_fix_inflected_words [--word WORD] [--limit N] [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from sqlalchemy import func, select

from app.models import Phrase, Word
from app.scripts.patch_base import add_common_args, create_session, load_words, prepare_database, print_summary
from app.services.lemma_service import LemmaCandidate, detect_lemma_candidates, suggest_inflection_action
from app.services.scraper.wiktionary import WiktionaryScraper
from app.services.spelling_suggestions import build_spellchecker, collect_spelling_suggestions

FORM_KEYS = (
    "third_person_singular",
    "present_participle",
    "past_tense",
    "past_participle",
    "plural",
    "comparative",
    "superlative",
)


def _derive_lemma_candidates(word_text: str) -> list[tuple[str, str]]:
    lower = word_text.strip().lower()
    if not lower:
        return []
    out: list[tuple[str, str]] = []
    if lower.endswith("ied") and len(lower) > 4:
        out.append((lower[:-3] + "y", "past_participle"))
    if lower.endswith("ed") and len(lower) > 3:
        stem = lower[:-2]
        out.append((stem, "past_tense"))
        out.append((stem + "e", "past_tense"))
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            out.append((stem[:-1], "past_tense"))
    if lower.endswith("ing") and len(lower) > 4:
        stem = lower[:-3]
        out.append((stem, "present_participle"))
        out.append((stem + "e", "present_participle"))
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            out.append((stem[:-1], "present_participle"))
    if lower.endswith("ies") and len(lower) > 4:
        out.append((lower[:-3] + "y", "plural"))
    if lower.endswith("s") and len(lower) > 2 and not lower.endswith("ss"):
        out.append((lower[:-1], "plural"))
    seen: set[tuple[str, str]] = set()
    deduped: list[tuple[str, str]] = []
    for lemma, inflection_type in out:
        key = (lemma, inflection_type)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((lemma, inflection_type))
    return deduped


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _serialize_lemma_candidates(candidates: list) -> list[dict]:
    return [
        {
            "lemma": item.lemma_word,
            "lemma_word_id": item.lemma_word_id,
            "inflection_type": item.inflection_type,
            "has_own_content": item.has_own_content,
            "confidence": item.confidence,
            "source": item.source,
            "score": item.score,
        }
        for item in candidates
    ]


def _has_empty_etymology(word: Word) -> bool:
    ety = word.etymology
    if not ety:
        return True
    items = getattr(ety, "component_items", None)
    if not isinstance(items, list):
        return True
    return len(items) == 0


async def _build_report_rows(
    words: list[Word],
    db,
    *,
    use_db_near: bool = False,
    spellchecker_merge_db: bool = False,
) -> list[dict[str, str]]:
    by_lower_words = {w.word.lower(): w for w in words}
    by_lower = {w.word.lower(): w.word for w in words}
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
            inflected = by_lower_words.get(inflected_text.lower())
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
                    "lemma_candidates": _json(
                        [
                            {
                                "lemma": base.word,
                                "lemma_word_id": base.id,
                                "inflection_type": key,
                                "has_own_content": False,
                                "confidence": "high",
                                "source": "db_forms",
                                "score": 100,
                            }
                        ]
                    ),
                    "spelling_candidates": _json([]),
                    "selected_spelling": "",
                    "lemma_resolution": "direct",
                    "selected_lemma": base.word,
                    "suggestion": "merge",
                    "action": "",
                }
            )

    seen_words = {row["word"].lower() for row in rows}
    scraper = WiktionaryScraper()
    spellchecker = build_spellchecker([w.word for w in words], merge_db_vocabulary=spellchecker_merge_db)
    for target in sorted(words, key=lambda x: x.word.lower()):
        key = target.word.lower()
        if key in seen_words:
            continue
        if not _has_empty_etymology(target):
            continue

        candidates = await detect_lemma_candidates(target.word, db, scraper=scraper)
        selected = candidates[0] if candidates else None
        selected_spelling = ""
        lemma_resolution = "direct" if selected else "manual"
        spelling_candidates_payload: list[dict] = []

        if not selected:
            for suggestion in collect_spelling_suggestions(
                target.word,
                by_lower,
                spellchecker,
                use_db_near=use_db_near,
            ):
                spelling = suggestion["spelling"]
                spelling_lemmas = await detect_lemma_candidates(spelling, db, scraper=scraper)
                if selected is None and spelling_lemmas:
                    selected = spelling_lemmas[0]
                    selected_spelling = spelling
                    lemma_resolution = (
                        "resolved_from_inflection"
                        if selected.lemma_word.lower() != spelling.lower()
                        else "direct"
                    )
                spelling_candidates_payload.append(
                    {
                        "spelling": spelling,
                        "source": suggestion["source"],
                        "lemma_candidates": _serialize_lemma_candidates(spelling_lemmas),
                        "selected_lemma": spelling_lemmas[0].lemma_word if spelling_lemmas else None,
                        "lemma_resolution": (
                            "resolved_from_inflection"
                            if spelling_lemmas and spelling_lemmas[0].lemma_word.lower() != spelling.lower()
                            else ("direct" if spelling_lemmas else "manual")
                        ),
                    }
                )

        if not selected:
            for lemma_text, inflection_type in _derive_lemma_candidates(target.word):
                row = by_lower_words.get(lemma_text.lower())
                if not row:
                    continue
                selected = LemmaCandidate(
                    lemma_word=row.word,
                    lemma_word_id=row.id,
                    inflection_type=inflection_type,
                    has_own_content=False,
                    confidence="low",
                    source="nltk",
                    score=35,
                )
                lemma_resolution = "manual"
                break

        suggestion = suggest_inflection_action(selected) if selected else "register_as_is"
        selected_lemma = selected.lemma_word if selected else ""
        inflection_type = selected.inflection_type if selected else ""
        rows.append(
            {
                "word": target.word,
                "lemma": selected_lemma,
                "lemma_word_id": str(selected.lemma_word_id) if selected and selected.lemma_word_id else "",
                "inflection_type": inflection_type,
                "has_own_content": str(selected.has_own_content) if selected else "",
                "lemma_candidates": _json(_serialize_lemma_candidates(candidates)),
                "spelling_candidates": _json(spelling_candidates_payload),
                "selected_spelling": selected_spelling,
                "lemma_resolution": lemma_resolution,
                "selected_lemma": selected_lemma,
                "suggestion": suggestion or "",
                "action": "",
            }
        )
        seen_words.add(key)
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
        "spelling_candidates",
        "selected_spelling",
        "lemma_resolution",
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
    use_db_near: bool = False,
    spellchecker_merge_db: bool = False,
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
        rows = await _build_report_rows(
            words,
            db,
            use_db_near=use_db_near,
            spellchecker_merge_db=spellchecker_merge_db,
        )
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
    parser.add_argument(
        "--db-near",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Suggest spellings via difflib close matches against words already in the DB (db_near). Default is off.",
    )
    parser.add_argument(
        "--spellchecker-merge-db",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Load DB words into pyspellchecker vocabulary. Default is off.",
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
            use_db_near=args.db_near,
            spellchecker_merge_db=args.spellchecker_merge_db,
        )
    )


if __name__ == "__main__":
    main()
