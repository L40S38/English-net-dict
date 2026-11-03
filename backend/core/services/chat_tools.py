"""Tool definitions and executor for the chat agent loop.

Three read-only tools are always available to the LLM:
  1. lookup_word_data  – fetch specific fields for a word from the local DB
  2. search_db         – pattern-search words in the local DB
  3. search_web        – search the web via DuckDuckGo

One write tool is available only in word-scoped chat sessions (see WRITE_TOOL_DEFINITIONS):
  4. register_related_word – add a related word/synonym/antonym/etc. entry to the current word

One image tool is available in word/phrase/group-scoped sessions, but not etymology-component
sessions (see IMAGE_TOOL_DEFINITIONS):
  5. generate_chat_image – generate an illustrative image and return a URL for the LLM to embed
     via Markdown in its reply. The image is chat-only and is not saved as the word/phrase/group's
     official image (see core.services.image_service for that separate feature).
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from core.config import settings
from core.models import Definition, Etymology, EtymologyComponentItem, RelatedWord, Word
from core.services.image_service import generate_image_bytes
from core.services.web_word_search import search_web_dictionary, search_web_general
from core.services.word_service import link_related_words

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


# Write tools are appended to TOOL_DEFINITIONS only for word-scoped chat sessions
# (see chat_service.answer_in_session), so the LLM cannot even attempt to call
# them from a phrase/component/group chat.
_VALID_RELATION_TYPES = {"synonym", "confusable", "cognate", "antonym"}

WRITE_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "register_related_word",
        "description": (
            "Register a new related word/phrase entry for the word currently being discussed. "
            "Only call this when the user explicitly asks to add/register a related word, synonym, "
            "antonym, confusable word, or cognate (e.g. '関連語としてXを登録して', '類義語としてXを追加して'). "
            "Do not call this proactively just because a related word came up in conversation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "related_word": {
                    "type": "string",
                    "description": "The related English word or phrase to register (e.g. 'in light of').",
                },
                "relation_type": {
                    "type": "string",
                    "enum": sorted(_VALID_RELATION_TYPES),
                    "description": (
                        "Relationship type. Map Japanese terms: 類義語/同義語 -> synonym, "
                        "対義語/反意語 -> antonym, 同語源語 -> cognate, "
                        "紛らわしい語/間違えやすい語 -> confusable. Default to 'synonym' if the user "
                        "did not specify and it cannot be inferred."
                    ),
                },
                "note": {
                    "type": "string",
                    "description": "Optional short note explaining the nuance or reason for the relation. Leave empty if the user gave none.",
                },
            },
            "required": ["related_word", "relation_type"],
            "additionalProperties": False,
        },
    },
]

WRITE_TOOL_NAMES: set[str] = {tool["name"] for tool in WRITE_TOOL_DEFINITIONS}


# Image tool is appended to the tool list for word/phrase/group-scoped chat sessions only
# (see chat_service.answer_in_session) - not offered in etymology-component chats.
IMAGE_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "generate_chat_image",
        "description": (
            "Generate an illustrative image (イメージ図/イラスト) and return a URL to embed directly "
            "in the chat reply. Call this when the user clearly asks for a visual, e.g. "
            "「〜のイメージ図を出して」「〜を絵で見せて」「〜のイラストを生成して」「図解して」. "
            "Do not call this for requests that are purely about explaining meaning in words."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": (
                        "A detailed image-generation prompt in English describing what to draw, "
                        "based on the word/phrase's meaning, etymology, or nuance being discussed."
                    ),
                },
                "alt_text": {
                    "type": "string",
                    "description": "Short Japanese description of the image, used as Markdown alt text.",
                },
            },
            "required": ["prompt", "alt_text"],
            "additionalProperties": False,
        },
    },
]


# ---------------------------------------------------------------------------
# Tool executors
# ---------------------------------------------------------------------------

def execute_tool(db: Session, tool_name: str, arguments: dict[str, Any], word_id: int | None = None) -> str:
    try:
        if tool_name == "lookup_word_data":
            return _exec_lookup(db, arguments)
        if tool_name == "search_db":
            return _exec_search_db(db, arguments)
        if tool_name == "search_web":
            return _exec_search_web(arguments)
        if tool_name == "generate_chat_image":
            return _exec_generate_chat_image(arguments)
        if tool_name == "register_related_word":
            # Run in a SAVEPOINT so a failed write only undoes its own change on
            # error, rather than db.rollback() reverting the whole outer transaction
            # - including the user's chat message, which was already flushed (but
            # not committed) before the tool-calling loop started. Only this tool
            # actually writes to the DB, so only it needs the SAVEPOINT: wrapping the
            # other (read-only or network-bound) tools too just holds SQLite's write
            # lock for the duration of their web/API calls for no benefit.
            with db.begin_nested():
                return _exec_register_related_word(db, word_id, arguments)
        return json.dumps({"error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)
    except Exception:
        logger.exception("Tool execution failed: %s", tool_name)
        return json.dumps({"error": f"Tool '{tool_name}' failed"}, ensure_ascii=False)


def _exec_generate_chat_image(args: dict) -> str:
    prompt = str(args.get("prompt", "")).strip()
    alt_text = str(args.get("alt_text", "")).strip() or "generated image"
    if not prompt:
        return json.dumps({"error": "prompt is required"}, ensure_ascii=False)
    if not settings.openai_api_key:
        return json.dumps(
            {"error": "Image generation is not available (no API key configured)."}, ensure_ascii=False
        )

    try:
        image_dir = Path(settings.image_dir)
        image_dir.mkdir(parents=True, exist_ok=True)
        image_bytes = generate_image_bytes(prompt)
        if not image_bytes:
            return json.dumps({"error": "Image generation returned no data."}, ensure_ascii=False)

        filename = f"chat-{uuid.uuid4().hex[:8]}.png"
        (image_dir / filename).write_bytes(image_bytes)
        return json.dumps({"url": f"/static/images/{filename}", "alt_text": alt_text}, ensure_ascii=False)
    except Exception:
        logger.exception("Chat image generation failed")
        return json.dumps({"error": "Image generation failed."}, ensure_ascii=False)


def _exec_register_related_word(db: Session, word_id: int | None, args: dict) -> str:
    if word_id is None:
        return json.dumps(
            {"error": "register_related_word is not available in this chat context."},
            ensure_ascii=False,
        )

    related_word = str(args.get("related_word", "")).strip()
    if not related_word:
        return json.dumps({"error": "related_word is required"}, ensure_ascii=False)

    relation_type = str(args.get("relation_type", "")).strip().lower()
    relation_type_clamped = relation_type not in _VALID_RELATION_TYPES
    if relation_type_clamped:
        relation_type = "synonym"

    note = str(args.get("note") or "").strip()

    word = db.get(Word, word_id)
    if not word:
        return json.dumps({"error": "Word not found"}, ensure_ascii=False)

    for existing in word.related_words:
        if existing.related_word.strip().lower() == related_word.lower() and existing.relation_type == relation_type:
            return json.dumps(
                {
                    "result": "already_exists",
                    "related_word": {
                        "id": existing.id,
                        "related_word": existing.related_word,
                        "relation_type": existing.relation_type,
                        "note": existing.note,
                    },
                },
                ensure_ascii=False,
            )

    item = RelatedWord(related_word=related_word, relation_type=relation_type, note=note)
    word.related_words.append(item)
    db.flush()
    link_related_words(db, word)

    result: dict[str, Any] = {
        "result": "created",
        "related_word": {
            "id": item.id,
            "related_word": item.related_word,
            "relation_type": item.relation_type,
            "note": item.note,
        },
    }
    if relation_type_clamped:
        result["relation_type_clamped"] = True
    return json.dumps(result, ensure_ascii=False)


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
