"""Tool definitions and executor for the chat agent loop.

Three tools are available to the LLM:
  1. lookup_word_data  – fetch specific fields for a word from the local DB
  2. search_db         – pattern-search words in the local DB
  3. search_web        – search the web via DuckDuckGo
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Definition, Etymology, EtymologyComponentItem, Word
from app.services.web_word_search import search_web_dictionary, search_web_general

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool schemas (OpenAI Responses API format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "lookup_word_data",
        "description": (
            "Look up a specific English word in the local dictionary database. "
            "Returns the requested fields (definitions, etymology, derivations, related_words). "
            "Use this when you need detailed information about a particular word."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "word": {
                    "type": "string",
                    "description": "The English word to look up (case-insensitive).",
                },
                "fields": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["definitions", "etymology", "derivations", "related_words"],
                    },
                    "description": "Which data fields to retrieve. Omit to get all fields.",
                },
            },
            "required": ["word"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_db",
        "description": (
            "Search the local dictionary database for words matching substring patterns. "
            "Useful for finding words containing a morpheme, root, prefix, or suffix. "
            "The database has a limited set of words so results may be incomplete."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Substrings to search for (e.g. ['satile', 'vers']).",
                },
                "operator": {
                    "type": "string",
                    "enum": ["or", "and"],
                    "description": "How to combine patterns: 'or' = any pattern matches, 'and' = all patterns must match. Default: 'or'.",
                },
                "search_in": {
                    "type": "string",
                    "enum": ["word_spelling", "etymology_components", "definitions", "all"],
                    "description": "Where to search: word_spelling (word name), etymology_components, definitions (meaning text), or all. Default: 'word_spelling'.",
                },
            },
            "required": ["patterns"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_web",
        "description": (
            "Search the web using DuckDuckGo. Use this when the local database does not have "
            "enough information, or when you need broader knowledge. "
            "Two search types: 'dictionary' adds dictionary/etymology site keywords to queries; "
            "'general' performs a broad web search."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Search queries to execute (1-3 queries recommended).",
                },
                "search_type": {
                    "type": "string",
                    "enum": ["dictionary", "general"],
                    "description": "Type of search. 'dictionary' for word/etymology lookups, 'general' for broader searches. Default: 'dictionary'.",
                },
            },
            "required": ["queries"],
            "additionalProperties": False,
        },
    },
]


# ---------------------------------------------------------------------------
# Tool executors
# ---------------------------------------------------------------------------

def execute_tool(db: Session, tool_name: str, arguments: dict[str, Any]) -> str:
    try:
        if tool_name == "lookup_word_data":
            return _exec_lookup(db, arguments)
        if tool_name == "search_db":
            return _exec_search_db(db, arguments)
        if tool_name == "search_web":
            return _exec_search_web(arguments)
        return json.dumps({"error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)
    except Exception:
        logger.exception("Tool execution failed: %s", tool_name)
        return json.dumps({"error": f"Tool '{tool_name}' failed"}, ensure_ascii=False)


def _exec_lookup(db: Session, args: dict) -> str:
    word_text = str(args.get("word", "")).strip().lower()
    fields = args.get("fields") or ["definitions", "etymology", "derivations", "related_words"]

    stmt = select(Word).where(func.lower(Word.word) == word_text).options(
        joinedload(Word.definitions),
        joinedload(Word.etymology).joinedload(Etymology.component_items),
        joinedload(Word.derivations),
        joinedload(Word.related_words),
    )
    word = db.scalar(stmt)
    if not word:
        return json.dumps({"result": None, "message": f"Word '{word_text}' not found in database."}, ensure_ascii=False)

    result: dict[str, Any] = {"word": word.word, "phonetic": word.phonetic}

    if "definitions" in fields:
        result["definitions"] = [
            {"part_of_speech": d.part_of_speech, "meaning_en": d.meaning_en, "meaning_ja": d.meaning_ja}
            for d in sorted(word.definitions, key=lambda x: x.sort_order)
        ]
    if "etymology" in fields and word.etymology:
        result["etymology"] = {
            "components": [
                {"text": c.component_text, "meaning": c.meaning or "", "type": c.type or "root"}
                for c in sorted(word.etymology.component_items, key=lambda x: (x.sort_order, x.id))
            ],
            "origin_word": word.etymology.origin_word,
            "origin_language": word.etymology.origin_language,
            "raw_description": word.etymology.raw_description,
        }
    if "derivations" in fields:
        result["derivations"] = [
            {"word": d.derived_word, "part_of_speech": d.part_of_speech, "meaning_ja": d.meaning_ja}
            for d in word.derivations
        ]
    if "related_words" in fields:
        result["related_words"] = [
            {"word": r.related_word, "relation_type": r.relation_type, "note": r.note}
            for r in word.related_words
        ]

    return json.dumps({"result": result}, ensure_ascii=False)


def _exec_search_db(db: Session, args: dict) -> str:
    patterns: list[str] = [str(p).strip().lower() for p in args.get("patterns", []) if str(p).strip()]
    operator: str = args.get("operator", "or")
    search_in: str = args.get("search_in", "word_spelling")
    if not patterns:
        return json.dumps({"results": [], "message": "No patterns provided."}, ensure_ascii=False)

    matched: dict[str, dict] = {}

    for pattern in patterns[:5]:
        like_pattern = f"%{pattern}%"
        hits: list[Word] = []

        if search_in in ("word_spelling", "all"):
            stmt = (
                select(Word)
                .where(Word.word.ilike(like_pattern))
                .options(joinedload(Word.definitions))
                .limit(20)
            )
            hits.extend(db.scalars(stmt).unique())

        if search_in in ("etymology_components", "all"):
            stmt = (
                select(Word)
                .join(Etymology, Etymology.word_id == Word.id)
                .join(EtymologyComponentItem, EtymologyComponentItem.etymology_id == Etymology.id)
                .where(EtymologyComponentItem.component_text.ilike(like_pattern))
                .options(joinedload(Word.definitions))
                .limit(20)
            )
            hits.extend(db.scalars(stmt).unique())

        if search_in in ("definitions", "all"):
            stmt = (
                select(Word)
                .join(Definition, Definition.word_id == Word.id)
                .where(Definition.meaning_en.ilike(like_pattern) | Definition.meaning_ja.ilike(like_pattern))
                .options(joinedload(Word.definitions))
                .limit(20)
            )
            hits.extend(db.scalars(stmt).unique())

        for w in hits:
            key = w.word.lower()
            if key not in matched:
                matched[key] = {
                    "word": w.word,
                    "matched_patterns": [],
                    "definitions": [
                        {"part_of_speech": d.part_of_speech, "meaning_en": d.meaning_en, "meaning_ja": d.meaning_ja}
                        for d in sorted(w.definitions, key=lambda x: x.sort_order)[:3]
                    ],
                }
            if pattern not in matched[key]["matched_patterns"]:
                matched[key]["matched_patterns"].append(pattern)

    if operator == "and" and len(patterns) > 1:
        matched = {k: v for k, v in matched.items() if len(v["matched_patterns"]) >= len(patterns)}

    results = sorted(matched.values(), key=lambda x: (-len(x["matched_patterns"]), x["word"]))[:30]
    return json.dumps({"results": results, "total": len(results), "patterns": patterns, "operator": operator, "search_in": search_in}, ensure_ascii=False)


def _exec_search_web(args: dict) -> str:
    queries: list[str] = [str(q).strip() for q in args.get("queries", []) if str(q).strip()]
    search_type: str = args.get("search_type", "dictionary")
    if not queries:
        return json.dumps({"results": [], "message": "No queries provided."}, ensure_ascii=False)

    if search_type == "dictionary":
        results = search_web_dictionary(queries[:3])
    else:
        results = search_web_general(queries[:3])

    return json.dumps({"results": results, "search_type": search_type, "queries": queries}, ensure_ascii=False)
