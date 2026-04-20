from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from openai import OpenAI
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from core.config import settings
from core.models import Definition, Etymology, Word
from core.schemas import GroupSuggestCandidate, GroupSuggestResponse
from core.utils.prompt_loader import load_prompt


def _normalize_keywords(keywords: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in keywords:
        value = str(raw).strip().lower()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


MatchMode = Literal["contains", "starts_with", "ends_with"]
SearchScope = Literal["word", "phrase", "example", "all"]


@dataclass(frozen=True)
class SearchRule:
    scope: SearchScope
    text: str
    match: MatchMode


def _strip_json_fence(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```json"):
        value = value[len("```json") :].strip()
    if value.startswith("```"):
        value = value[3:].strip()
    if value.endswith("```"):
        value = value[:-3].strip()
    return value


def _normalize_rule_text(value: str) -> str:
    return str(value or "").strip()


def _extract_rules_with_gpt(keywords: list[str]) -> list[SearchRule]:
    """Generate richer search rules including starts/ends matching.

    If no API key, fall back to broad 'contains' rules across all scopes.
    """
    if not keywords:
        return []
    if not settings.openai_api_key:
        return [SearchRule(scope="all", text=k, match="contains") for k in keywords]

    client = OpenAI(api_key=settings.openai_api_key)
    system_prompt = load_prompt("group_suggest_rules.md")
    try:
        completion = client.responses.create(
            model=settings.openai_model_structured,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps({"keywords": keywords}, ensure_ascii=False)},
            ],
        )
        raw = _strip_json_fence(completion.output_text or "")
        data = json.loads(raw) if raw else {}
        rules_raw = data.get("rules", [])
        if not isinstance(rules_raw, list):
            raise ValueError("rules must be a list")
        rules: list[SearchRule] = []
        for item in rules_raw[:30]:
            if not isinstance(item, dict):
                continue
            scope = item.get("scope", "all")
            match = item.get("match", "contains")
            text = _normalize_rule_text(item.get("text", ""))
            if scope not in ("word", "phrase", "example", "all"):
                continue
            if match not in ("contains", "starts_with", "ends_with"):
                continue
            if not text:
                continue
            rules.append(SearchRule(scope=scope, match=match, text=text))
        if rules:
            return rules
        return [SearchRule(scope="all", text=k, match="contains") for k in keywords]
    except Exception:
        return [SearchRule(scope="all", text=k, match="contains") for k in keywords]


def _match_score(patterns: list[str], *texts: str) -> float:
    haystack = " ".join(texts).lower()
    if not haystack:
        return 0.0
    score = 0.0
    for pattern in patterns:
        if pattern in haystack:
            score += 1.0
    return score


def _like_pattern(rule: SearchRule) -> str:
    text = rule.text
    if rule.match == "starts_with":
        return f"{text}%"
    if rule.match == "ends_with":
        return f"%{text}"
    return f"%{text}%"


def _candidate_key(candidate: GroupSuggestCandidate) -> str:
    return (
        f"{candidate.item_type}:{candidate.word_id or ''}:"
        f"{candidate.definition_id or ''}:{candidate.phrase_text or ''}"
    )


def _collect_candidates(db: Session, rules: list[SearchRule], max_candidates: int = 500) -> list[GroupSuggestCandidate]:
    """Collect a broad set of candidates using SQL where possible.

    - Words/examples via SQL LIKE
    - Phrases via scanning Word.phrases
    """
    if not rules:
        return []
    word_rules = [r for r in rules if r.scope in ("word", "all")]
    example_rules = [r for r in rules if r.scope in ("example", "all")]
    phrase_rules = [r for r in rules if r.scope in ("phrase", "all")]

    candidates: dict[str, GroupSuggestCandidate] = {}

    if word_rules:
        clauses = [Word.word.ilike(_like_pattern(rule)) for rule in word_rules]
        stmt = (
            select(Word)
            .where(or_(*clauses))
            .options(joinedload(Word.definitions), joinedload(Word.etymology).joinedload(Etymology.component_items))
            .limit(max_candidates)
        )
        for word in db.scalars(stmt).unique():
            key = _candidate_key(GroupSuggestCandidate(item_type="word", word_id=word.id))
            candidates[key] = GroupSuggestCandidate(
                item_type="word",
                word_id=word.id,
                word=word.word,
                score=0.0,
            )

    if example_rules:
        like_clauses = []
        for rule in example_rules:
            pat = _like_pattern(rule)
            like_clauses.append(Definition.example_en.ilike(pat))
            like_clauses.append(Definition.example_ja.ilike(pat))
            like_clauses.append(Definition.meaning_en.ilike(pat))
            like_clauses.append(Definition.meaning_ja.ilike(pat))
        stmt = (
            select(Word, Definition)
            .join(Definition, Definition.word_id == Word.id)
            .where(or_(*like_clauses))
            .limit(max_candidates)
        )
        rows = db.execute(stmt).unique().all()
        for word, definition in rows:
            # Even if there is no example sentence, a meaning match should still surface
            # the word itself as a candidate (important for Japanese keyword searches).
            word_key = _candidate_key(GroupSuggestCandidate(item_type="word", word_id=word.id))
            if word_key not in candidates:
                candidates[word_key] = GroupSuggestCandidate(
                    item_type="word",
                    word_id=word.id,
                    word=word.word,
                    definition_part_of_speech=definition.part_of_speech,
                    definition_meaning_ja=definition.meaning_ja,
                    score=0.0,
                )

            if not (definition.example_en or definition.example_ja):
                continue
            candidate = GroupSuggestCandidate(
                item_type="example",
                word_id=word.id,
                definition_id=definition.id,
                word=word.word,
                definition_part_of_speech=definition.part_of_speech,
                definition_meaning_ja=definition.meaning_ja,
                example_en=definition.example_en,
                example_ja=definition.example_ja,
                score=0.0,
            )
            candidates[_candidate_key(candidate)] = candidate

    if phrase_rules:
        # Phrases are stored in Phrase table; scan words with eager-loaded phrases.
        words = list(
            db.scalars(
                select(Word).options(
                    joinedload(Word.definitions),
                    joinedload(Word.etymology).joinedload(Etymology.component_items),
                    joinedload(Word.phrases),
                )
            ).unique()
        )
        for word in words:
            for phrase in word.phrases:
                phrase_text = phrase.text
                phrase_meaning = phrase.meaning or ""
                text_lower = phrase_text.lower()
                meaning_lower = (phrase_meaning or "").lower()
                matched = False
                for rule in phrase_rules:
                    rule_text = rule.text.lower()
                    if rule.match == "starts_with" and text_lower.startswith(rule_text):
                        matched = True
                    elif rule.match == "ends_with" and text_lower.endswith(rule_text):
                        matched = True
                    elif rule.match == "contains" and (rule_text in text_lower or rule_text in meaning_lower):
                        matched = True
                    if matched:
                        break
                if not matched:
                    continue
                candidate = GroupSuggestCandidate(
                    item_type="phrase",
                    word_id=word.id,
                    phrase_id=phrase.id,
                    phrase_text=phrase_text,
                    phrase_meaning=phrase_meaning,
                    word=word.word,
                    score=0.0,
                )
                key = _candidate_key(candidate)
                if key not in candidates:
                    candidates[key] = candidate
                if len(candidates) >= max_candidates:
                    break
            if len(candidates) >= max_candidates:
                break

    return list(candidates.values())


def _rerank_with_gpt(
    *,
    intent_keywords: list[str],
    rules: list[SearchRule],
    candidates: list[GroupSuggestCandidate],
    limit: int,
) -> list[GroupSuggestCandidate]:
    if not settings.openai_api_key:
        return candidates[:limit]
    if not candidates:
        return []
    client = OpenAI(api_key=settings.openai_api_key)
    system_prompt = load_prompt("group_suggest_rerank.md")
    payload = {
        "keywords": intent_keywords,
        "rules": [r.__dict__ for r in rules],
        "candidates": [
            {
                "key": _candidate_key(c),
                "item_type": c.item_type,
                "word": c.word,
                "phrase_text": c.phrase_text,
                "phrase_meaning": c.phrase_meaning,
                "example_en": c.example_en,
                "example_ja": c.example_ja,
                "definition_meaning_ja": c.definition_meaning_ja,
                "score": c.score,
            }
            for c in candidates
        ],
        "limit": limit,
    }
    try:
        completion = client.responses.create(
            model=settings.openai_model_structured,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        raw = _strip_json_fence(completion.output_text or "")
        data = json.loads(raw) if raw else {}
        selected = data.get("selected", [])
        if not isinstance(selected, list):
            return candidates[:limit]
        selected_keys = [str(x) for x in selected if str(x).strip()]
        by_key = {_candidate_key(c): c for c in candidates}
        reranked: list[GroupSuggestCandidate] = []
        for key in selected_keys:
            c = by_key.get(key)
            if not c:
                continue
            reranked.append(c)
            if len(reranked) >= limit:
                break
        return reranked or candidates[:limit]
    except Exception:
        return candidates[:limit]


def suggest_group_candidates(db: Session, keywords: list[str], limit: int = 20) -> GroupSuggestResponse:
    normalized_keywords = _normalize_keywords(keywords)
    if not normalized_keywords:
        return GroupSuggestResponse(keywords=[], candidates=[])
    rules = _extract_rules_with_gpt(normalized_keywords)
    # Use rule texts as baseline patterns for initial scoring.
    patterns = _normalize_keywords([r.text for r in rules]) or normalized_keywords
    collected = _collect_candidates(db, rules, max_candidates=800)

    # Compute a simple baseline score (used as fallback or pre-rerank ordering).
    scored: list[GroupSuggestCandidate] = []
    for candidate in collected:
        if candidate.item_type == "word":
            score = _match_score(patterns, candidate.word or "")
        elif candidate.item_type == "phrase":
            score = _match_score(patterns, candidate.phrase_text or "", candidate.phrase_meaning or "")
        else:
            score = _match_score(patterns, candidate.example_en or "", candidate.example_ja or "")
        scored.append(candidate.model_copy(update={"score": score}))

    ranked = sorted(scored, key=lambda c: (-c.score, c.word or "", c.phrase_text or ""))[:300]
    final_limit = max(1, min(limit, 100))
    reranked = _rerank_with_gpt(
        intent_keywords=normalized_keywords,
        rules=rules,
        candidates=ranked,
        limit=final_limit,
    )
    return GroupSuggestResponse(keywords=normalized_keywords, candidates=reranked)
