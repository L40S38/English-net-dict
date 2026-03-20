from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path

from app.scripts.patch_base import add_common_args, create_session, prepare_database
from app.services.lemma_service import detect_lemma_candidates, suggest_inflection_action
from app.services.scraper.wiktionary import WiktionaryScraper


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
    dry_run: bool = False,
    limit: int | None = None,
    word_filter: str | None = None,
) -> None:
    prepare_database()
    db = create_session()
    scraper = WiktionaryScraper()
    try:
        raw_words = _read_word_list(file_path)
        targets = _select_words(raw_words, word_filter=word_filter, limit=limit)
        total = len(targets)
        if total == 0:
            print("No target words found in input.")
            return
        rows: list[dict[str, str]] = []
        print(f"Targets: {total}" + (" (dry-run)" if dry_run else ""))
        for idx, word in enumerate(targets, start=1):
            candidates = await detect_lemma_candidates(word, db, scraper=scraper)
            selected = candidates[0] if candidates else None
            suggestion = suggest_inflection_action(selected)
            lemma_candidates = "|".join(candidate.lemma_word for candidate in candidates)
            row = {
                "word": word,
                "lemma": selected.lemma_word if selected else "",
                "lemma_word_id": str(selected.lemma_word_id) if selected and selected.lemma_word_id else "",
                "inflection_type": selected.inflection_type if selected else "",
                "has_own_content": str(selected.has_own_content) if selected else "",
                "lemma_candidates": lemma_candidates,
                "selected_lemma": selected.lemma_word if selected else "",
                "suggestion": suggestion or "",
                "action": "",
            }
            rows.append(row)
            print(
                f"  [{idx}/{total}] {word} -> "
                f"{row['lemma'] or '-'} ({row['inflection_type'] or 'not_inflected'}) suggestion={row['suggestion'] or '-'}"
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
            "lemma_candidates",
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
    args = parser.parse_args()
    asyncio.run(
        run(
            file_path=args.file,
            output_file=args.output,
            dry_run=args.dry_run,
            limit=args.limit,
            word_filter=args.word,
        )
    )


if __name__ == "__main__":
    main()
