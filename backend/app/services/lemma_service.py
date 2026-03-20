from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Word
from app.services.scraper.wiktionary import WiktionaryScraper
from app.services.web_word_search import search_web_dictionary, search_web_general
from app.services.wordnet_service import ensure_wordnet

try:
    from nltk.stem import WordNetLemmatizer
except Exception:  # noqa: BLE001
    WordNetLemmatizer = None  # type: ignore[assignment]

FORM_TO_INFLECTION: dict[str, str] = {
    "third_person_singular": "third_person_singular",
    "present_participle": "present_participle",
    "past_tense": "past_tense",
    "past_participle": "past_participle",
    "plural": "plural",
    "comparative": "comparative",
    "superlative": "superlative",
}


@dataclass
class LemmaCandidate:
    lemma_word: str
    lemma_word_id: int | None
    inflection_type: str
    has_own_content: bool
    confidence: Literal["high", "medium", "low"] = "medium"
    source: Literal["db_forms", "possessive", "wiktionary", "nltk"] = "wiktionary"
    score: int = 0


def _normalize(word: str) -> str:
    return str(word or "").strip().lower()


def _safe_forms(word: Word) -> dict:
    forms = word.forms or {}
    return forms if isinstance(forms, dict) else {}


def _db_forms_matches(db: Session, target_word: str) -> list[LemmaCandidate]:
    target = _normalize(target_word)
    if not target:
        return []
    words = list(db.scalars(select(Word)))
    candidates: list[LemmaCandidate] = []
    seen: set[tuple[str, str]] = set()
    for base in words:
        base_word = _normalize(base.word)
        if base_word == target:
            continue
        forms = _safe_forms(base)
        for form_key, inflection_type in FORM_TO_INFLECTION.items():
            value = forms.get(form_key)
            if isinstance(value, str) and _normalize(value) == target:
                key = (base_word, inflection_type)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    LemmaCandidate(
                        lemma_word=base.word,
                        lemma_word_id=base.id,
                        inflection_type=inflection_type,
                        has_own_content=False,
                        confidence="high",
                        source="db_forms",
                        score=100,
                    )
                )
    return candidates


def _possessive_candidates(db: Session, target_word: str) -> list[LemmaCandidate]:
    target = _normalize(target_word)
    if not target:
        return []
    if target.endswith("'s"):
        lemma = target[:-2]
    elif target.endswith("’s"):
        lemma = target[:-2]
    elif target.endswith("s'"):
        lemma = target[:-1]
    else:
        return []
    lemma = lemma.strip()
    if not lemma:
        return []
    lemma_row = db.scalar(select(Word).where(Word.word.ilike(lemma)))
    return [
        LemmaCandidate(
            lemma_word=lemma,
            lemma_word_id=lemma_row.id if lemma_row else None,
            inflection_type="possessive",
            has_own_content=False,
            confidence="high" if lemma_row else "medium",
            source="possessive",
            score=95 if lemma_row else 85,
        )
    ]


def _extract_lemma_from_inflection_text(text: str) -> tuple[str, str] | None:
    value = str(text or "").strip()
    if not value:
        return None
    patterns = [
        (r"\bplural of\s+([A-Za-z][A-Za-z' -]{0,80})", "plural"),
        (r"\bthird[- ]person singular of\s+([A-Za-z][A-Za-z' -]{0,80})", "third_person_singular"),
        (r"\bpresent participle of\s+([A-Za-z][A-Za-z' -]{0,80})", "present_participle"),
        (r"\bpast tense of\s+([A-Za-z][A-Za-z' -]{0,80})", "past_tense"),
        (r"\bpast participle of\s+([A-Za-z][A-Za-z' -]{0,80})", "past_participle"),
        (r"\bcomparative of\s+([A-Za-z][A-Za-z' -]{0,80})", "comparative"),
        (r"\bsuperlative of\s+([A-Za-z][A-Za-z' -]{0,80})", "superlative"),
        (r"\binflection of\s+([A-Za-z][A-Za-z' -]{0,80})", "inflection"),
    ]
    for pattern, inflection_type in patterns:
        m = re.search(pattern, value, flags=re.IGNORECASE)
        if not m:
            continue
        lemma = re.sub(r"\s+", " ", m.group(1)).strip(" .,:;!?")
        if lemma:
            return lemma, inflection_type
    return None


def _has_own_content(scraped: dict) -> bool:
    definitions = scraped.get("definitions")
    if isinstance(definitions, list):
        # inflection-only pages tend to have a single short "X of Y" definition.
        rich = 0
        for item in definitions:
            if not isinstance(item, dict):
                continue
            meaning_en = str(item.get("meaning_en", "")).strip()
            if meaning_en and " of " not in meaning_en.lower():
                rich += 1
            if len(meaning_en) >= 40:
                rich += 1
        return rich >= 2
    return False


def _hits_to_text(hits: list[dict]) -> str:
    lines: list[str] = []
    for hit in hits[:8]:
        title = str(hit.get("title", "")).strip()
        body = str(hit.get("body", "")).strip()
        if title or body:
            lines.append(f"- {title}\n  {body}")
    return "\n".join(lines)


def _llm_guess_pos(word: str, hits: list[dict]) -> str | None:
    if not hits:
        return None
    if not settings.openai_api_key:
        return None
    prompt = (
        "Given an English word and web snippets, return only one POS label from: "
        "noun, verb, adjective, adverb, unknown."
    )
    user = f"word: {word}\n{_hits_to_text(hits)}"
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        completion = client.responses.create(
            model=settings.openai_model_structured,
            temperature=0.0,
            input=[{"role": "system", "content": prompt}, {"role": "user", "content": user}],
        )
        value = str(completion.output_text or "").strip().lower()
        if value in {"noun", "verb", "adjective", "adverb", "unknown"}:
            return value
    except Exception:  # noqa: BLE001
        return None
    return None


def _guess_pos_from_web(word: str) -> str | None:
    dict_result = search_web_dictionary([word], max_results_per_query=6)
    dict_hits = dict_result.get("hits", []) if isinstance(dict_result, dict) else []
    pos = _llm_guess_pos(word, dict_hits if isinstance(dict_hits, list) else [])
    if pos and pos != "unknown":
        return pos
    general_result = search_web_general([f"{word} part of speech meaning"], max_results_per_query=6)
    general_hits = general_result.get("hits", []) if isinstance(general_result, dict) else []
    pos = _llm_guess_pos(word, general_hits if isinstance(general_hits, list) else [])
    if pos and pos != "unknown":
        return pos
    return None


def _lemmatize_with_pos_priority(word: str) -> str | None:
    normalized = _normalize(word)
    if not normalized or WordNetLemmatizer is None:
        return None
    try:
        ensure_wordnet()
    except Exception:  # noqa: BLE001
        return None
    lemmatizer = WordNetLemmatizer()
    pos_map = {"noun": "n", "verb": "v", "adjective": "a", "adverb": "r"}
    guessed = _guess_pos_from_web(normalized)
    ordered_pos: list[str] = []
    if guessed in pos_map:
        ordered_pos.append(pos_map[guessed])
    for pos in ("n", "v", "a", "r"):
        if pos not in ordered_pos:
            ordered_pos.append(pos)
    for pos in ordered_pos:
        lemma = lemmatizer.lemmatize(normalized, pos=pos).strip().lower()
        if lemma and lemma != normalized:
            return lemma
    return None


def _sort_and_dedupe_candidates(candidates: list[LemmaCandidate]) -> list[LemmaCandidate]:
    merged: dict[tuple[str, str], LemmaCandidate] = {}
    for candidate in candidates:
        key = (_normalize(candidate.lemma_word), candidate.inflection_type)
        prev = merged.get(key)
        if prev is None or candidate.score > prev.score:
            merged[key] = candidate
    return sorted(
        merged.values(),
        key=lambda x: (
            -x.score,
            x.lemma_word_id is None,
            _normalize(x.lemma_word),
        ),
    )


async def detect_lemma_candidates(word: str, db: Session, scraper: WiktionaryScraper | None = None) -> list[LemmaCandidate]:
    target = _normalize(word)
    if not target:
        return []

    candidates: list[LemmaCandidate] = []
    candidates.extend(_db_forms_matches(db, target))
    candidates.extend(_possessive_candidates(db, target))

    wiktionary_scraper = scraper or WiktionaryScraper()
    try:
        scraped = await wiktionary_scraper.scrape(target)
    except Exception:  # noqa: BLE001
        scraped = {}
    if isinstance(scraped, dict):
        possible_texts: list[str] = []
        summary = scraped.get("summary")
        if isinstance(summary, str):
            possible_texts.append(summary)
        definitions = scraped.get("definitions")
        if isinstance(definitions, list):
            for item in definitions:
                if not isinstance(item, dict):
                    continue
                meaning_en = item.get("meaning_en")
                if isinstance(meaning_en, str):
                    possible_texts.append(meaning_en)
        own_content = _has_own_content(scraped)
        for text in possible_texts:
            extracted = _extract_lemma_from_inflection_text(text)
            if not extracted:
                continue
            lemma, inflection_type = extracted
            lemma_row = db.scalar(select(Word).where(Word.word.ilike(lemma)))
            score = 70 + (10 if lemma_row else 0)
            candidates.append(
                LemmaCandidate(
                    lemma_word=lemma,
                    lemma_word_id=lemma_row.id if lemma_row else None,
                    inflection_type=inflection_type,
                    has_own_content=own_content,
                    confidence="medium",
                    source="wiktionary",
                    score=score,
                )
            )

    lemma_by_nltk = _lemmatize_with_pos_priority(target)
    if lemma_by_nltk:
        lemma_row = db.scalar(select(Word).where(Word.word.ilike(lemma_by_nltk)))
        candidates.append(
            LemmaCandidate(
                lemma_word=lemma_by_nltk,
                lemma_word_id=lemma_row.id if lemma_row else None,
                inflection_type="inflection",
                has_own_content=False,
                confidence="low",
                source="nltk",
                score=40 + (10 if lemma_row else 0),
            )
        )
    return _sort_and_dedupe_candidates(candidates)


async def detect_lemma(word: str, db: Session, scraper: WiktionaryScraper | None = None) -> LemmaCandidate | None:
    candidates = await detect_lemma_candidates(word, db, scraper=scraper)
    return candidates[0] if candidates else None


def suggest_inflection_action(
    candidate: LemmaCandidate | None,
) -> Literal["merge", "link", "register_as_is"] | None:
    if candidate is None:
        return "register_as_is"
    if candidate.has_own_content:
        return "link"
    return "merge"
