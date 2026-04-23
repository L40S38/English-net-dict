from __future__ import annotations

from core.models import Phrase
from core.services.gpt_service import translate_phrase_definitions
from core.services.phrase_meaning_service import resolve_meaning_ja
from core.services.phrase_service import replace_definitions


def _pick_definition_items(scraped: dict) -> list[dict]:
    raw = scraped.get("definitions")
    if not isinstance(raw, list):
        return []
    picked: list[dict] = []
    preferred = {"phrase": 0, "verb": 1, "noun": 2, "adjective": 3, "adverb": 4}
    for item in raw:
        if not isinstance(item, dict):
            continue
        meaning_en = str(item.get("meaning_en", "")).strip()
        if not meaning_en:
            continue
        pos = str(item.get("part_of_speech", "phrase")).strip().lower() or "phrase"
        picked.append(
            {
                "part_of_speech": pos,
                "meaning_en": meaning_en,
                "example_en": str(item.get("example_en", "")).strip(),
                "_priority": preferred.get(pos, 99),
            }
        )
    picked.sort(key=lambda row: (row["_priority"], row["part_of_speech"], row["meaning_en"]))
    return picked[:12]


async def enrich_phrase(db, phrase: Phrase, *, scraper, cache: dict[str, str | None]) -> Phrase:
    phrase.meaning = (await resolve_meaning_ja(phrase.text, scraper, cache)) or phrase.meaning or ""

    scraped = await scraper.scrape(phrase.text)
    items = _pick_definition_items(scraped if isinstance(scraped, dict) else {})

    translated = translate_phrase_definitions(
        phrase.text,
        [{"meaning_en": item["meaning_en"], "example_en": item["example_en"]} for item in items],
    )

    definitions: list[dict] = []
    for idx, item in enumerate(items):
        tr = translated[idx] if idx < len(translated) else {}
        definitions.append(
            {
                "part_of_speech": item["part_of_speech"],
                "meaning_en": item["meaning_en"],
                "meaning_ja": str(tr.get("meaning_ja", "")).strip(),
                "example_en": item["example_en"],
                "example_ja": str(tr.get("example_ja", "")).strip(),
                "sort_order": idx,
            }
        )

    if not definitions:
        definitions = [
            {
                "part_of_speech": "phrase",
                "meaning_en": "",
                "meaning_ja": phrase.meaning or "",
                "example_en": "",
                "example_ja": "",
                "sort_order": 0,
            }
        ]

    replace_definitions(db, phrase, definitions)
    db.flush()
    return phrase
