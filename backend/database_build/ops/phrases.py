from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.models import Word
from core.schemas import WordCreateRequest
from core.services.gpt_service import enrich_core_image_and_branches, generate_structured_word_data
from core.services.phrase_meaning_service import (
    clean_line,
    needs_one_line_summary,
    resolve_meaning_ja,
    resolve_meaning_ja_ddgs,
)
from core.services.phrase_service import get_or_create_phrase, link_phrase_to_word, normalize_phrase_text
from core.services.scraper.wiktionary import WiktionaryScraper
from core.services.word_data_helpers import (
    normalize_structured_derivations_and_phrases as _normalize_structured_derivations_and_phrases,
)
from core.services.word_data_helpers import normalize_structured_forms as _normalize_structured_forms
from core.services.word_ingest_service import _apply_enriched_etymology, _needs_etymology_enrichment
from core.services.word_service import apply_structured_payload
from core.services.wordnet_service import get_wordnet_snapshot
from core.utils.text_helpers import is_multi_token, normalize_phrase_entries
from database_build.ops.common import scrape_all
from database_build.reporting import FieldDiff

_PLACEHOLDER_MEANINGS = {"", "Wiktionaryの派生語"}


def _phrase_state(word: Word) -> tuple[list[dict[str, str]], dict[str, str], list[str]]:
    phrases = [{"phrase": p.text, "meaning": p.meaning or ""} for p in sorted(word.phrases, key=lambda x: x.id)]
    related_notes = {rw.related_word: (rw.note or "") for rw in word.related_words}
    derivations = [drv.derived_word for drv in word.derivations]
    return phrases, related_notes, derivations


async def enrich_phrase_meanings(
    db: Session,  # noqa: ARG001
    word: Word,
    *,
    scraper: WiktionaryScraper,
    cache: dict[str, str | None],
) -> list[FieldDiff]:
    before_phrases, before_notes, before_derivations = _phrase_state(word)
    normalized_phrases = [
        {"phrase": p.text, "meaning": p.meaning or ""} for p in sorted(word.phrases, key=lambda x: x.id)
    ]
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
        meaning = await resolve_meaning_ja(term, scraper, cache, seed_candidates=[note] if note else None)
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


def _tokenize_phrase(phrase: str) -> list[str]:
    tokens = [t.strip().lower() for t in re.split(r"\s+", phrase.strip()) if t.strip()]
    unique: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        unique.append(token)
    return unique


async def _build_structured_payload(word_text: str) -> dict:
    wordnet_data = get_wordnet_snapshot(word_text)
    scraped_data = await scrape_all(word_text)
    structured = generate_structured_word_data(word_text, wordnet_data, scraped_data)
    structured = _normalize_structured_forms(structured)
    structured = _normalize_structured_derivations_and_phrases(structured)
    if _needs_etymology_enrichment(word_text, structured):
        enriched = enrich_core_image_and_branches(
            word_text=word_text,
            definitions=structured.get("definitions", []),
            etymology_data=structured.get("etymology", {}),
        )
        structured = _apply_enriched_etymology(structured, enriched)
    forms = structured.get("forms")
    if isinstance(forms, dict):
        forms["phrases"] = normalize_phrase_entries(forms.get("phrases"))
        structured["forms"] = forms
    return structured


def _find_word(db: Session, word_text: str) -> Word | None:
    normalized = word_text.strip().lower()
    if not normalized:
        return None
    return db.scalar(select(Word).where(func.lower(Word.word) == normalized))


async def split_phrase_words(
    db: Session,
    phrase_word: Word,
    *,
    ddgs_cache: dict[str, str | None],
    payload_cache: dict[str, dict],
) -> tuple[int, int, int]:
    phrase_text = phrase_word.word.strip()
    tokens = _tokenize_phrase(phrase_text)
    if not tokens:
        return 0, 0, 0
    phrase_meaning = await resolve_meaning_ja_ddgs(phrase_text, ddgs_cache)
    added_words = 0
    phrases_appended = 0
    phrases_skipped = 0
    created_or_existing: list[Word] = []
    for token in tokens:
        existing = _find_word(db, token)
        if existing:
            created_or_existing.append(existing)
            continue
        structured = payload_cache.get(token)
        if structured is None:
            structured = await _build_structured_payload(token)
            payload_cache[token] = structured
        new_word = Word(word=WordCreateRequest(word=token).word)
        db.add(new_word)
        db.flush()
        apply_structured_payload(db, new_word, structured)
        created_or_existing.append(new_word)
        added_words += 1
    for token_word in created_or_existing:
        forms = dict(token_word.forms or {})
        phrases = normalize_phrase_entries(forms.get("phrases"))
        key_set = {entry["phrase"].strip().lower() for entry in phrases if entry.get("phrase", "").strip()}
        phrase_key = phrase_text.lower()
        if phrase_key in key_set:
            phrases_skipped += 1
            continue
        phrases.append({"phrase": phrase_text, "meaning": phrase_meaning or ""})
        forms["phrases"] = phrases
        token_word.forms = forms
        phrases_appended += 1
    db.delete(phrase_word)
    return added_words, phrases_appended, phrases_skipped
