from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.models import Phrase, Word
from core.schemas import MigrationInflectionApplyRequest
from core.services.lemma_service import LemmaCandidate, detect_lemma_candidates, suggest_inflection_action
from core.services.scraper.wiktionary import WiktionaryScraper
from core.services.spelling_suggestions import build_spellchecker, collect_spelling_suggestions
from core.services.word_ingest_service import ingest_word_or_phrase
from core.services.word_merge_service import link_to_lemma, merge_into_lemma
from database_build.runtime import JobSummary

VALID_ACTIONS = {"merge", "link", "register_as_is"}
FORM_KEYS = (
    "third_person_singular",
    "present_participle",
    "past_tense",
    "past_participle",
    "plural",
    "comparative",
    "superlative",
)


@dataclass
class MigrationApplyItemResult:
    word_id: int
    action: str
    status: str
    detail: str


def list_inflection_targets(db: Session, *, page: int, page_size: int) -> tuple[list[tuple[int, str]], int]:
    filters = (Word.lemma_word_id.is_(None), Word.inflection_type.is_(None))
    total = int(db.scalar(select(func.count(Word.id)).where(*filters)) or 0)
    stmt = (
        select(Word.id, Word.word)
        .where(*filters)
        .order_by(Word.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = db.execute(stmt).all()
    return [(word_id, word_text) for word_id, word_text in rows], total


def apply_inflection_migration(
    db: Session,
    payload: MigrationInflectionApplyRequest,
) -> tuple[JobSummary, list[MigrationApplyItemResult]]:
    summary = JobSummary()
    results: list[MigrationApplyItemResult] = []
    for decision in payload.decisions:
        inflected = db.get(Word, decision.word_id)
        lemma = db.get(Word, decision.lemma_word_id)
        if inflected is None:
            summary.errors += 1
            results.append(MigrationApplyItemResult(decision.word_id, decision.action, "error", "word_id not found"))
            continue
        if lemma is None:
            summary.errors += 1
            results.append(
                MigrationApplyItemResult(decision.word_id, decision.action, "error", "lemma_word_id not found")
            )
            continue
        if inflected.id == lemma.id:
            summary.skipped += 1
            results.append(
                MigrationApplyItemResult(
                    decision.word_id,
                    decision.action,
                    "skipped",
                    "word_id and lemma_word_id are identical",
                )
            )
            continue
        try:
            with db.begin_nested():
                if decision.action == "merge":
                    merge_into_lemma(db, inflected, lemma)
                else:
                    link_to_lemma(db, inflected, lemma, decision.inflection_type or "inflection")
            summary.applied += 1
            results.append(MigrationApplyItemResult(decision.word_id, decision.action, "applied", ""))
        except Exception as exc:  # noqa: BLE001
            summary.errors += 1
            results.append(MigrationApplyItemResult(decision.word_id, decision.action, "error", str(exc)))
    db.commit()
    return summary, results


def _find_word(db: Session, text: str) -> Word | None:
    normalized = text.strip().lower()
    if not normalized:
        return None
    return db.scalar(select(Word).where(func.lower(Word.word) == normalized))


def _read_csv_rows(file_path: Path) -> list[dict[str, str]]:
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")
    with file_path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


async def import_inflection_csv(
    db: Session,
    file_path: Path,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    word_filter: str | None = None,
) -> tuple[int, int, int]:
    rows = _read_csv_rows(file_path)
    if word_filter:
        target = word_filter.strip().lower()
        rows = [row for row in rows if str(row.get("word", "")).strip().lower() == target]
    if limit is not None:
        rows = rows[:limit]
    added = 0
    skipped = 0
    errors = 0
    scraper = WiktionaryScraper()
    phrase_cache: dict[str, str | None] = {}
    payload_cache: dict[str, dict] = {}
    for row in rows:
        word = str(row.get("word", "")).strip()
        action = str(row.get("action", "")).strip() or str(row.get("suggestion", "")).strip()
        lemma = str(row.get("lemma", "")).strip()
        selected_lemma = str(row.get("selected_lemma", "")).strip()
        inflection_type = str(row.get("inflection_type", "")).strip() or "inflection"
        if not word:
            skipped += 1
            continue
        if action not in VALID_ACTIONS:
            errors += 1
            continue
        try:
            if action == "register_as_is":
                result = await ingest_word_or_phrase(
                    db, word, scraper=scraper, payload_cache=payload_cache, meaning_cache=phrase_cache
                )
                added += result.created_count
            elif action == "merge":
                lemma_target = selected_lemma or lemma or word
                lemma_result = await ingest_word_or_phrase(
                    db, lemma_target, scraper=scraper, payload_cache=payload_cache, meaning_cache=phrase_cache
                )
                lemma_word = _find_word(db, lemma_target)
                inflected_word = _find_word(db, word)
                if lemma_word and inflected_word and lemma_word.id != inflected_word.id:
                    merge_into_lemma(db, inflected_word, lemma_word)
                added += lemma_result.created_count
            elif action == "link":
                lemma_target = selected_lemma or lemma
                if not lemma_target:
                    raise ValueError("lemma is required for link action")
                lemma_result = await ingest_word_or_phrase(
                    db, lemma_target, scraper=scraper, payload_cache=payload_cache, meaning_cache=phrase_cache
                )
                inflected_result = await ingest_word_or_phrase(
                    db, word, scraper=scraper, payload_cache=payload_cache, meaning_cache=phrase_cache
                )
                lemma_word = _find_word(db, lemma_target)
                inflected_word = _find_word(db, word)
                if not lemma_word or not inflected_word:
                    raise ValueError("failed to resolve lemma/inflected words for link")
                link_to_lemma(db, inflected_word, lemma_word, inflection_type)
                added += lemma_result.created_count + inflected_result.created_count
            if dry_run:
                db.rollback()
            else:
                db.commit()
        except Exception:  # noqa: BLE001
            errors += 1
            db.rollback()
    return added, skipped, errors


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


def _derive_lemma_candidates(word_text: str) -> list[tuple[str, str]]:
    lower = word_text.strip().lower()
    if not lower:
        return []
    out: list[tuple[str, str]] = []
    if lower.endswith("ied") and len(lower) > 4:
        out.append((lower[:-3] + "y", "past_participle"))
    if lower.endswith("ed") and len(lower) > 3:
        stem = lower[:-2]
        out.extend([(stem, "past_tense"), (stem + "e", "past_tense")])
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            out.append((stem[:-1], "past_tense"))
    if lower.endswith("ing") and len(lower) > 4:
        stem = lower[:-3]
        out.extend([(stem, "present_participle"), (stem + "e", "present_participle")])
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            out.append((stem[:-1], "present_participle"))
    if lower.endswith("ies") and len(lower) > 4:
        out.append((lower[:-3] + "y", "plural"))
    if lower.endswith("s") and len(lower) > 2 and not lower.endswith("ss"):
        out.append((lower[:-1], "plural"))
    seen: set[tuple[str, str]] = set()
    deduped: list[tuple[str, str]] = []
    for lemma, inflection_type in out:
        if (lemma, inflection_type) in seen:
            continue
        seen.add((lemma, inflection_type))
        deduped.append((lemma, inflection_type))
    return deduped


def _has_empty_etymology(word: Word) -> bool:
    ety = word.etymology
    if not ety:
        return True
    items = getattr(ety, "component_items", None)
    if not isinstance(items, list):
        return True
    return len(items) == 0


async def build_inflection_report_rows(
    words: list[Word],
    db: Session,
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
            inflected = by_lower_words.get(value.strip().lower())
            if not inflected or inflected.id == base.id:
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
                        [{"lemma": base.word, "lemma_word_id": base.id, "inflection_type": key, "score": 100}]
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
        if key in seen_words or not _has_empty_etymology(target):
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
                    lemma_resolution = "resolved_from_inflection"
                spelling_candidates_payload.append(
                    {
                        "spelling": spelling,
                        "source": suggestion["source"],
                        "lemma_candidates": _serialize_lemma_candidates(spelling_lemmas),
                        "selected_lemma": spelling_lemmas[0].lemma_word if spelling_lemmas else None,
                        "lemma_resolution": "direct" if spelling_lemmas else "manual",
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
        rows.append(
            {
                "word": target.word,
                "lemma": selected.lemma_word if selected else "",
                "lemma_word_id": str(selected.lemma_word_id) if selected and selected.lemma_word_id else "",
                "inflection_type": selected.inflection_type if selected else "",
                "has_own_content": str(selected.has_own_content) if selected else "",
                "lemma_candidates": _json(_serialize_lemma_candidates(candidates)),
                "spelling_candidates": _json(spelling_candidates_payload),
                "selected_spelling": selected_spelling,
                "lemma_resolution": lemma_resolution,
                "selected_lemma": selected.lemma_word if selected else "",
                "suggestion": suggestion or "",
                "action": "",
            }
        )
        seen_words.add(key)
    return rows


def write_inflection_report(output_file: Path, rows: list[dict[str, str]]) -> None:
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


def apply_known_inflection_fixes(db: Session) -> tuple[int, int]:
    updated = 0
    skipped = 0
    a_pos = db.scalar(select(Word).where(func.lower(Word.word) == "a's"))
    if a_pos:
        phrase = db.scalar(select(Phrase).where(Phrase.text == "take a's place"))
        if phrase:
            phrase.text = "take A's place"
            updated += 1
        db.delete(a_pos)
        updated += 1
    else:
        skipped += 1
    return updated, skipped
