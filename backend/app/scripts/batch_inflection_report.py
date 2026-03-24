"""Generate inflection analysis report for input words.

Usage:
    uv run python -m app.scripts.batch_inflection_report --file app/scripts/words_to_add.txt
    uv run python -m app.scripts.batch_inflection_report --file ... --db-near --spellchecker-merge-db
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Word
from app.scripts.patch_base import add_common_args, create_session, prepare_database
from app.services.lemma_service import (
    detect_lemma_candidates,
    detect_word_has_own_content,
    suggest_inflection_action,
)
from app.services.scraper.wiktionary import WiktionaryScraper
from app.services.spelling_suggestions import build_spellchecker, collect_spelling_suggestions


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _format_spelling_hints(payload: list[dict]) -> str:
    """Short string for console (spelling + source)."""
    if not payload:
        return ""
    parts: list[str] = []
    for item in payload[:10]:
        sp = str(item.get("spelling", "") or "").strip()
        src = str(item.get("source", "") or "").strip()
        if sp:
            parts.append(f"{sp}({src})" if src else sp)
    if not parts:
        return ""
    suffix = " ..." if len(payload) > 10 else ""
    return f" spelling={', '.join(parts)}{suffix}"


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


def _read_word_list(file_path: Path) -> list[str]:
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")
    words: list[str] = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        words.append(text)
    return words


def _read_words_from_db(db: Session) -> list[str]:
    stmt = (
        select(Word.word)
        .where(Word.lemma_word_id.is_(None))
        .order_by(Word.id.asc())
    )
    return [word for word in db.scalars(stmt) if isinstance(word, str) and word.strip()]


def _select_words(words: list[str], word_filter: str | None, limit: int | None) -> list[str]:
    filtered = words
    if word_filter:
        target = word_filter.strip().lower()
        filtered = [w for w in filtered if w.strip().lower() == target]
    if limit is not None:
        filtered = filtered[:limit]
    return filtered


async def run(
    file_path: Path,
    *,
    output_file: Path,
    from_db: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
    word_filter: str | None = None,
    use_db_near: bool = False,
    spellchecker_merge_db: bool = False,
) -> None:
    prepare_database()
    db = create_session()
    scraper = WiktionaryScraper()
    try:
        raw_words = _read_words_from_db(db) if from_db else _read_word_list(file_path)
        targets = _select_words(raw_words, word_filter=word_filter, limit=limit)
        total = len(targets)
        if total == 0:
            print("No target words found in DB." if from_db else "No target words found in input.")
            return
        rows: list[dict[str, str]] = []
        db_words = list(db.scalars(select(Word.word)))
        by_lower = {str(w).strip().lower(): str(w).strip() for w in db_words if str(w).strip()}
        spellchecker = build_spellchecker(list(by_lower.values()), merge_db_vocabulary=spellchecker_merge_db)
        own_content_cache: dict[str, bool] = {}
        mode_parts: list[str] = []
        if use_db_near:
            mode_parts.append("db-near")
        if spellchecker_merge_db:
            mode_parts.append("spell-merge-db")
        mode = f" ({', '.join(mode_parts)})" if mode_parts else " (pure-pyspell)"
        print(f"Targets: {total}" + (" (dry-run)" if dry_run else "") + mode)
        for idx, word in enumerate(targets, start=1):
            word_has_own_content = await detect_word_has_own_content(
                word,
                scraper=scraper,
                cache=own_content_cache,
            )
            candidates = await detect_lemma_candidates(word, db, scraper=scraper)
            selected = candidates[0] if candidates else None
            selected_spelling = ""
            lemma_resolution = "direct" if selected else "manual"
            spelling_candidates_payload: list[dict] = []
            # 語彙コンテンツが薄い lemma のときも、別綴り候補を出す（スペルミス疑いの調査用）
            run_spelling = not selected or (selected is not None and not selected.has_own_content)
            if run_spelling:
                for suggestion in collect_spelling_suggestions(
                    word, by_lower, spellchecker, use_db_near=use_db_near
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
            suggestion = suggest_inflection_action(selected)
            row = {
                "word": word,
                "lemma": selected.lemma_word if selected else "",
                "lemma_word_id": str(selected.lemma_word_id) if selected and selected.lemma_word_id else "",
                "inflection_type": selected.inflection_type if selected else "",
                "has_own_content": str(word_has_own_content),
                "selected_has_own_content": str(selected.has_own_content) if selected else "",
                "lemma_candidates": _json(_serialize_lemma_candidates(candidates)),
                "spelling_candidates": _json(spelling_candidates_payload),
                "selected_spelling": selected_spelling,
                "lemma_resolution": lemma_resolution if selected else "manual",
                "selected_lemma": selected.lemma_word if selected else "",
                "suggestion": suggestion or "",
                "action": "",
            }
            rows.append(row)
            print(
                f"  [{idx}/{total}] {word} -> "
                f"{row['lemma'] or '-'} ({row['inflection_type'] or 'not_inflected'}) "
                f"suggestion={row['suggestion'] or '-'} "
                f"own_content={row['has_own_content']} "
                f"selected_own_content={row['selected_has_own_content'] or '-'}"
                f"{_format_spelling_hints(spelling_candidates_payload)}"
            )

        if dry_run:
            return
        output_file.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "word",
            "lemma",
            "lemma_word_id",
            "inflection_type",
            "has_own_content",
            "selected_has_own_content",
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
        print(f"Report written: {output_file}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate inflection check report for words_to_add style files")
    add_common_args(parser)
    parser.add_argument(
        "--file",
        type=Path,
        default=Path(__file__).resolve().parent / "words_to_add.txt",
        help="Input text file path (one word per line)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "batch_inflection_report.csv",
        help="Output CSV path",
    )
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="Read target words from DB (lemma_word_id IS NULL) instead of --file input.",
    )
    parser.add_argument(
        "--db-near",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Suggest spellings via difflib close matches against words already in the DB (db_near). "
            "Default is off."
        ),
    )
    parser.add_argument(
        "--spellchecker-merge-db",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Load DB words into pyspellchecker vocabulary. "
            "Default is off."
        ),
    )
    args = parser.parse_args()
    asyncio.run(
        run(
            file_path=args.file,
            output_file=args.output,
            from_db=args.from_db,
            dry_run=args.dry_run,
            limit=args.limit,
            word_filter=args.word,
            use_db_near=args.db_near,
            spellchecker_merge_db=args.spellchecker_merge_db,
        )
    )


if __name__ == "__main__":
    main()
