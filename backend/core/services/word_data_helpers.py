from __future__ import annotations

import asyncio

from core.services.phrase_meaning_service import needs_one_line_summary, resolve_meaning_ja
from core.utils.text_helpers import is_multi_token, normalize_phrase_entries

_PLACEHOLDER_MEANINGS = {"", "Wiktionaryの派生語"}


def normalize_structured_forms(structured: dict) -> dict:
    if not isinstance(structured, dict):
        return structured
    forms = structured.get("forms")
    if not isinstance(forms, dict):
        return structured
    normalized = normalize_phrase_entries(forms.get("phrases"))
    if not normalized and "phrases" not in forms:
        return structured
    next_structured = dict(structured)
    next_forms = dict(forms)
    next_forms["phrases"] = normalized
    next_structured["forms"] = next_forms
    return next_structured


def normalize_structured_derivations_and_phrases(structured: dict) -> dict:
    if not isinstance(structured, dict):
        return structured
    forms = structured.get("forms")
    derivations = structured.get("derivations")
    if not isinstance(forms, dict) or not isinstance(derivations, list):
        return structured

    phrases = normalize_phrase_entries(forms.get("phrases"))
    phrase_map: dict[str, dict[str, str]] = {
        item["phrase"].strip().lower(): item for item in phrases if item.get("phrase", "").strip()
    }
    kept_derivations: list[dict] = []
    changed = False

    for item in derivations:
        if not isinstance(item, dict):
            changed = True
            continue
        derived_word = str(item.get("derived_word", "")).strip()
        if not derived_word:
            changed = True
            continue
        if is_multi_token(derived_word):
            key = derived_word.lower()
            if key not in phrase_map:
                phrase_map[key] = {"phrase": derived_word, "meaning": ""}
                phrases.append(phrase_map[key])
                changed = True
            meaning = str(item.get("meaning_en", item.get("meaning_ja", ""))).strip()
            if meaning in _PLACEHOLDER_MEANINGS:
                meaning = ""
            if meaning and not phrase_map[key].get("meaning", "").strip():
                phrase_map[key]["meaning"] = meaning
                changed = True
            continue
        kept_derivations.append(item)

    if not changed and phrases == normalize_phrase_entries(forms.get("phrases")) and kept_derivations == derivations:
        return structured

    next_structured = dict(structured)
    next_forms = dict(forms)
    next_forms["phrases"] = phrases
    next_structured["forms"] = next_forms
    next_structured["derivations"] = kept_derivations
    return next_structured


async def enrich_phrase_and_related_meanings(
    structured: dict,
    scraper,
    cache: dict[str, str | None],
) -> None:
    forms = structured.get("forms")
    if isinstance(forms, dict):
        phrases = forms.get("phrases")
        if isinstance(phrases, list):
            for entry in phrases:
                if not isinstance(entry, dict):
                    continue
                phrase = str(entry.get("phrase", "")).strip()
                if not phrase:
                    continue
                existing = str(entry.get("meaning", "")).strip()
                if existing and not needs_one_line_summary(existing):
                    continue
                meaning = await resolve_meaning_ja(
                    phrase,
                    scraper,
                    cache,
                    seed_candidates=[existing] if existing else None,
                )
                if meaning:
                    entry["meaning"] = meaning

    for rel in structured.get("related_words", []):
        if not isinstance(rel, dict):
            continue
        term = str(rel.get("related_word", "")).strip()
        if not term or not is_multi_token(term):
            continue
        note = str(rel.get("note", "")).strip()
        if note and not needs_one_line_summary(note):
            continue
        meaning = await resolve_meaning_ja(
            term,
            scraper,
            cache,
            seed_candidates=[note] if note else None,
        )
        if meaning:
            rel["note"] = meaning


async def enrich_phrase_and_related_meanings_parallel(
    structured: dict,
    scraper,
    cache: dict[str, str | None],
    *,
    concurrency: int = 8,
) -> None:
    semaphore = asyncio.Semaphore(max(1, concurrency))
    tasks: list[asyncio.Task[None]] = []

    async def _resolve_phrase(entry: dict) -> None:
        phrase = str(entry.get("phrase", "")).strip()
        if not phrase:
            return
        existing = str(entry.get("meaning", "")).strip()
        if existing and not needs_one_line_summary(existing):
            return
        async with semaphore:
            meaning = await resolve_meaning_ja(
                phrase,
                scraper,
                cache,
                seed_candidates=[existing] if existing else None,
            )
        if meaning:
            entry["meaning"] = meaning

    async def _resolve_related(rel: dict) -> None:
        term = str(rel.get("related_word", "")).strip()
        if not term or not is_multi_token(term):
            return
        note = str(rel.get("note", "")).strip()
        if note and not needs_one_line_summary(note):
            return
        async with semaphore:
            meaning = await resolve_meaning_ja(
                term,
                scraper,
                cache,
                seed_candidates=[note] if note else None,
            )
        if meaning:
            rel["note"] = meaning

    forms = structured.get("forms")
    if isinstance(forms, dict):
        phrases = forms.get("phrases")
        if isinstance(phrases, list):
            for entry in phrases:
                if isinstance(entry, dict):
                    tasks.append(asyncio.create_task(_resolve_phrase(entry)))

    for rel in structured.get("related_words", []):
        if isinstance(rel, dict):
            tasks.append(asyncio.create_task(_resolve_related(rel)))

    if tasks:
        await asyncio.gather(*tasks)
