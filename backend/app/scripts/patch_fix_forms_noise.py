"""Clean obvious noise tokens from inflection forms.

Usage:
    uv run python -m app.scripts.patch_fix_forms_noise [--word WORD] [--limit N] [--dry-run]
"""

from __future__ import annotations

import argparse
import json

from app.scripts.patch_base import add_common_args, create_session, load_words, prepare_database, print_summary
from app.services.scraper.wiktionary import WiktionaryScraper

NOISE_TOKENS = {"of", "from", "for", "to", "by", "and", "or", "the", "a", "an"}
FORM_KEYS = (
    "third_person_singular",
    "present_participle",
    "past_tense",
    "past_participle",
    "plural",
    "comparative",
    "superlative",
)


def _has_noise(forms: object) -> bool:
    if not isinstance(forms, dict):
        return False
    for key in FORM_KEYS:
        value = forms.get(key)
        if isinstance(value, str) and value.strip().lower() in NOISE_TOKENS:
            return True
    return False


async def run(dry_run: bool = False, limit: int | None = None, word_filter: str | None = None) -> None:
    prepare_database()
    db = create_session()
    updated = 0
    skipped = 0
    errors = 0
    scraper = WiktionaryScraper()

    try:
        words = load_words(db, word_filter=word_filter, limit=limit)
        total = len(words)
        print(f"Targets: {total}" + (" (dry-run)" if dry_run else ""))
        for idx, word in enumerate(words, start=1):
            current_forms = dict(word.forms or {})
            if not _has_noise(current_forms):
                skipped += 1
                continue
            try:
                scraped = await scraper.scrape(word.word)
                next_forms = scraped.get("forms", {}) if isinstance(scraped, dict) else {}
                if not isinstance(next_forms, dict):
                    next_forms = {}
                if _has_noise(next_forms):
                    for k in FORM_KEYS:
                        v = next_forms.get(k)
                        if isinstance(v, str) and v.strip().lower() in NOISE_TOKENS:
                            next_forms.pop(k, None)
                if next_forms == current_forms:
                    skipped += 1
                    continue

                print(
                    f"  [{idx}/{total}] {word.word} forms:\n"
                    f"    before={json.dumps(current_forms, ensure_ascii=False)}\n"
                    f"    after ={json.dumps(next_forms, ensure_ascii=False)}"
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
                print(f"  [{idx}/{total}] {word.word} ERROR: {exc}")
    finally:
        db.close()

    print_summary(updated, skipped, errors)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix noisy inflection tokens in words.forms")
    add_common_args(parser)
    args = parser.parse_args()
    import asyncio

    asyncio.run(run(dry_run=args.dry_run, limit=args.limit, word_filter=args.word))


if __name__ == "__main__":
    main()
