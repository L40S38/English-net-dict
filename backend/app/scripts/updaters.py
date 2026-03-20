"""Reusable update helpers for patch and batch scripts.

Usage:
    Imported from other scripts under app.scripts; not intended as a direct CLI entrypoint.
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.orm import Session

from app.models import Etymology, Word
from app.services.phrase_service import get_or_create_phrase, link_phrase_to_word, normalize_phrase_text
from app.services.gpt_service import enrich_core_image_and_branches, generate_structured_word_data
from app.services.phrase_meaning_service import clean_line, needs_one_line_summary, resolve_meaning_ja
from app.services.scraper.wiktionary import WiktionaryScraper
from app.services.word_service import apply_structured_payload
from app.services.wordnet_service import get_wordnet_snapshot

from app.scripts.patch_base import FieldDiff, is_multi_token, normalize_phrase_entries, scrape_all

_PLACEHOLDER_MEANINGS = {"", "Wiktionaryの派生語"}


def _word_snapshot(word: Word) -> dict[str, Any]:
    ety = word.etymology
    phrases = [{"phrase": p.text, "meaning": p.meaning or ""} for p in sorted(word.phrases, key=lambda x: x.id)]
    branches = []
    if ety:
        branches = [
            {"label": b.label, "meaning_en": b.meaning_en, "meaning_ja": b.meaning_ja}
            for b in sorted(ety.branches, key=lambda x: (x.sort_order, x.id))
        ]
    return {
        "phonetic": word.phonetic,
        "definitions_count": len(word.definitions or []),
        "phrases": phrases,
        "core_image": (ety.core_image if ety else "") or "",
        "branches": branches,
        "derivations_count": len(word.derivations or []),
        "related_words_count": len(word.related_words or []),
    }


def _snapshot_diffs(before: dict[str, Any], after: dict[str, Any], keys: list[str]) -> list[FieldDiff]:
    diffs: list[FieldDiff] = []
    for key in keys:
        if before.get(key) != after.get(key):
            diffs.append(FieldDiff(name=key, before=before.get(key), after=after.get(key)))
    return diffs


def _normalize_structured_forms(structured: dict) -> dict:
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


def _normalize_structured_derivations_and_phrases(structured: dict) -> dict:
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


async def _enrich_phrase_and_related_meanings(
    structured: dict,
    scraper: WiktionaryScraper,
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


async def _enrich_phrase_and_related_meanings_parallel(
    structured: dict,
    scraper: WiktionaryScraper,
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


async def refresh_word_data(
    db: Session,
    word: Word,
    *,
    scraper: WiktionaryScraper | None = None,
    cache: dict[str, str | None] | None = None,
) -> list[FieldDiff]:
    before = _word_snapshot(word)

    wordnet_data = get_wordnet_snapshot(word.word)
    scraped_data = await scrape_all(word.word)
    structured = generate_structured_word_data(word.word, wordnet_data, scraped_data)
    structured = _normalize_structured_forms(structured)
    structured = _normalize_structured_derivations_and_phrases(structured)
    if scraper is not None and cache is not None:
        await _enrich_phrase_and_related_meanings(structured, scraper, cache)

    apply_structured_payload(db, word, structured)
    after = _word_snapshot(word)
    return _snapshot_diffs(
        before,
        after,
        [
            "phonetic",
            "definitions_count",
            "phrases",
            "core_image",
            "branches",
            "derivations_count",
            "related_words_count",
        ],
    )


def _phrase_state(word: Word) -> tuple[list[dict[str, str]], dict[str, str], list[str]]:
    phrases = [{"phrase": p.text, "meaning": p.meaning or ""} for p in sorted(word.phrases, key=lambda x: x.id)]
    related_notes = {rw.related_word: (rw.note or "") for rw in word.related_words}
    derivations = [drv.derived_word for drv in word.derivations]
    return phrases, related_notes, derivations


async def enrich_phrase_meanings(
    db: Session,  # noqa: ARG001 - 呼び出し側の統一シグネチャのため保持
    word: Word,
    *,
    scraper: WiktionaryScraper,
    cache: dict[str, str | None],
) -> list[FieldDiff]:
    before_phrases, before_notes, before_derivations = _phrase_state(word)

    normalized_phrases = [{"phrase": p.text, "meaning": p.meaning or ""} for p in sorted(word.phrases, key=lambda x: x.id)]
    phrase_map: dict[str, dict[str, str]] = {
        entry["phrase"].strip().lower(): entry for entry in normalized_phrases if entry.get("phrase", "").strip()
    }
    changed = False

    derivations_to_remove = []
    for drv in list(word.derivations):
        term = drv.derived_word.strip()
        if not term or not is_multi_token(term):
            continue
        key = term.lower()
        existing = phrase_map.get(key)
        if not existing:
            existing = {"phrase": term, "meaning": ""}
            normalized_phrases.append(existing)
            phrase_map[key] = existing
            changed = True
        seed = str(drv.meaning_ja or "").strip()
        if seed and seed not in _PLACEHOLDER_MEANINGS and needs_one_line_summary(seed):
            summarized = await resolve_meaning_ja(term, scraper, cache, seed_candidates=[seed])
            if summarized and summarized != existing.get("meaning", ""):
                existing["meaning"] = summarized
                changed = True
        elif seed and seed not in _PLACEHOLDER_MEANINGS and not existing.get("meaning", "").strip():
            existing["meaning"] = clean_line(seed, max_len=120)
            changed = True
        derivations_to_remove.append(drv)

    if derivations_to_remove:
        for drv in derivations_to_remove:
            word.derivations.remove(drv)
        changed = True

    for entry in normalized_phrases:
        phrase = entry["phrase"].strip()
        existing_meaning = entry.get("meaning", "").strip()
        if not phrase:
            continue
        if existing_meaning in _PLACEHOLDER_MEANINGS:
            existing_meaning = ""
        if existing_meaning and not needs_one_line_summary(existing_meaning):
            continue
        meaning = await resolve_meaning_ja(
            phrase,
            scraper,
            cache,
            seed_candidates=[existing_meaning] if existing_meaning else None,
        )
        if meaning and meaning != existing_meaning:
            entry["meaning"] = meaning
            changed = True

    for rel in word.related_words:
        term = rel.related_word.strip()
        if not term or not is_multi_token(term):
            continue
        note = str(rel.note or "").strip()
        if note in _PLACEHOLDER_MEANINGS:
            note = ""
        if note and not needs_one_line_summary(note):
            continue
        meaning = await resolve_meaning_ja(
            term,
            scraper,
            cache,
            seed_candidates=[note] if note else None,
        )
        if meaning and meaning != rel.note:
            rel.note = meaning
            changed = True

    if changed:
        word.phrase_links.clear()
        for entry in normalized_phrases:
            text = normalize_phrase_text(entry.get("phrase", ""))
            if not text:
                continue
            phrase = get_or_create_phrase(db, text, entry.get("meaning", ""))
            link_phrase_to_word(db, word, phrase)

    after_phrases, after_notes, after_derivations = _phrase_state(word)
    diffs: list[FieldDiff] = []
    if before_phrases != after_phrases:
        diffs.append(FieldDiff(name="phrases", before=before_phrases, after=after_phrases))
    if before_notes != after_notes:
        diffs.append(FieldDiff(name="related_word_notes", before=before_notes, after=after_notes))
    if before_derivations != after_derivations:
        diffs.append(FieldDiff(name="derivations", before=before_derivations, after=after_derivations))
    return diffs


def _core_image_is_generic(word_text: str, core_image: object) -> bool:
    value = str(core_image or "").strip()
    if not value:
        return True
    generic_patterns = {
        f"{word_text}: central concept",
        f"core image for {word_text}",
        f"etymology for {word_text}",
    }
    return value.lower() in {pattern.lower() for pattern in generic_patterns}


def _build_etymology_payload(word: Word) -> dict:
    from app.services.word_service import build_etymology_enrich_payload
    return build_etymology_enrich_payload(word.etymology)


def _build_definition_payload(word: Word) -> list[dict]:
    return [
        {
            "part_of_speech": definition.part_of_speech,
            "meaning_en": definition.meaning_en,
            "meaning_ja": definition.meaning_ja,
            "example_en": definition.example_en,
            "example_ja": definition.example_ja,
        }
        for definition in word.definitions
    ]


def enrich_etymology_map(db: Session, word: Word, *, only_missing: bool = False) -> list[FieldDiff]:  # noqa: ARG001
    from app.services.word_service import _apply_etymology_branches

    ety = word.etymology
    if only_missing:
        has_branches = bool(ety and len(ety.branches) > 0)
        if ety and not _core_image_is_generic(word.word, ety.core_image) and has_branches:
            return []

    enriched = enrich_core_image_and_branches(
        word_text=word.word,
        definitions=_build_definition_payload(word),
        etymology_data=_build_etymology_payload(word),
    )
    if not enriched:
        return []

    new_core_image = str(enriched.get("core_image", "")).strip()
    new_branches = enriched.get("branches")
    has_new_branches = isinstance(new_branches, list) and len(new_branches) > 0
    if not new_core_image and not has_new_branches:
        return []

    if not word.etymology:
        word.etymology = Etymology(word_id=word.id)

    diffs: list[FieldDiff] = []
    before_core = (word.etymology.core_image or "").strip()
    before_branches = [
        {"label": b.label, "meaning_en": b.meaning_en, "meaning_ja": b.meaning_ja}
        for b in word.etymology.branches
    ]
    if new_core_image and new_core_image != before_core:
        word.etymology.core_image = new_core_image
        diffs.append(FieldDiff(name="core_image", before=before_core, after=new_core_image))
    if has_new_branches and new_branches != before_branches:
        _apply_etymology_branches(word.etymology, list(new_branches))
        diffs.append(FieldDiff(name="branches", before=before_branches, after=list(new_branches)))
    return diffs

