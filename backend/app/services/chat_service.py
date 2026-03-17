from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models import (
    ChatMessage,
    ChatSession,
    Etymology,
    EtymologyComponent,
    EtymologyVariant,
    Word,
    WordGroup,
    WordGroupItem,
)
from app.services.chat_tools import TOOL_DEFINITIONS, execute_tool
from app.services.etymology_component_service import get_component_cache, normalize_component_text
from app.utils.prompt_loader import load_prompt
from app.utils.text_repair import has_suspected_mojibake, repair_text

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5
MAX_HISTORY_MESSAGES = 20


def build_word_context(word: Word) -> dict[str, Any]:
    def _word_components(target: Word) -> list[dict]:
        if not target.etymology:
            return []
        return [
            {
                "text": item.component_text,
                "meaning": item.meaning or "",
                "type": item.type or "root",
                "sort_order": item.sort_order or 0,
            }
            for item in sorted(target.etymology.component_items, key=lambda x: (x.sort_order, x.id))
        ]

    components = []
    if word.etymology:
        components = _word_components(word)
    return {
        "word": word.word,
        "phonetic": word.phonetic,
        "definitions": [
            {
                "part_of_speech": d.part_of_speech,
                "meaning_en": d.meaning_en,
                "meaning_ja": d.meaning_ja,
                "example_en": d.example_en,
                "example_ja": d.example_ja,
            }
            for d in sorted(word.definitions, key=lambda x: x.sort_order)
        ],
        "etymology": {
            "components": components,
            "origin_word": word.etymology.origin_word if word.etymology else None,
            "origin_language": word.etymology.origin_language if word.etymology else None,
            "core_image": word.etymology.core_image if word.etymology else None,
            "branches": [
                {"label": b.label, "meaning_en": b.meaning_en, "meaning_ja": b.meaning_ja}
                for b in (word.etymology.branches if word.etymology else [])
            ],
            "raw_description": word.etymology.raw_description if word.etymology else None,
        },
        "derivations": [
            {
                "word": d.derived_word,
                "part_of_speech": d.part_of_speech,
                "meaning_ja": d.meaning_ja,
            }
            for d in word.derivations
        ],
        "related_words": [
            {
                "word": r.related_word,
                "relation_type": r.relation_type,
                "note": r.note,
                "linked_word_id": r.linked_word_id,
            }
            for r in word.related_words
        ],
    }


def build_component_context(
    component_text: str,
    words: list[Word],
    component_cache: EtymologyComponent | None,
) -> dict[str, Any]:
    def _word_components(target: Word) -> list[dict]:
        if not target.etymology:
            return []
        return [
            {
                "text": item.component_text,
                "meaning": item.meaning or "",
                "type": item.type or "root",
                "sort_order": item.sort_order or 0,
            }
            for item in sorted(target.etymology.component_items, key=lambda x: (x.sort_order, x.id))
        ]

    return {
        "component_text": component_text,
        "component_cache": {
            "resolved_meaning": component_cache.resolved_meaning if component_cache else None,
            "meanings": component_cache.wiktionary_meanings if component_cache else [],
            "related_terms": component_cache.wiktionary_related_terms if component_cache else [],
            "derived_terms": component_cache.wiktionary_derived_terms if component_cache else [],
            "source_url": component_cache.wiktionary_source_url if component_cache else None,
        },
        "words": [
            {
                "word": word.word,
                "definitions": [
                    {"part_of_speech": d.part_of_speech, "meaning_en": d.meaning_en, "meaning_ja": d.meaning_ja}
                    for d in sorted(word.definitions, key=lambda x: x.sort_order)
                ],
                "derivations": [
                    {"word": d.derived_word, "part_of_speech": d.part_of_speech, "meaning_ja": d.meaning_ja}
                    for d in word.derivations
                ],
                "related_words": [
                    {"word": r.related_word, "relation_type": r.relation_type, "note": r.note}
                    for r in word.related_words
                ],
                "etymology": {
                    "components": _word_components(word),
                    "origin_word": word.etymology.origin_word if word.etymology else None,
                    "origin_language": word.etymology.origin_language if word.etymology else None,
                    "raw_description": word.etymology.raw_description if word.etymology else None,
                },
            }
            for word in words
        ],
    }


def build_group_context(group: WordGroup) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for item in sorted(group.items, key=lambda x: (x.sort_order, x.id)):
        if item.item_type == "word" and item.word_ref:
            items.append({"type": "word", "word": item.word_ref.word})
        elif item.item_type == "phrase" and item.phrase_text:
            items.append(
                {
                    "type": "phrase",
                    "phrase": item.phrase_text,
                    "meaning": item.phrase_meaning or "",
                }
            )
        elif item.item_type == "example" and item.definition_ref and item.word_ref:
            items.append(
                {
                    "type": "example",
                    "word": item.word_ref.word,
                    "example_en": item.definition_ref.example_en,
                    "example_ja": item.definition_ref.example_ja,
                    "meaning_ja": item.definition_ref.meaning_ja,
                }
            )
    return {
        "group": {
            "id": group.id,
            "name": group.name,
            "description": group.description,
        },
        "items": items[:120],
    }


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

def list_sessions(db: Session, word_id: int) -> list[ChatSession]:
    stmt = select(ChatSession).where(ChatSession.word_id == word_id).order_by(ChatSession.updated_at.desc())
    return list(db.scalars(stmt))


def create_session(db: Session, word_id: int, title: str | None) -> ChatSession:
    session = ChatSession(word_id=word_id, title=title or "Word Chat")
    db.add(session)
    db.flush()
    return session


def list_component_sessions(db: Session, component_text: str) -> list[ChatSession]:
    normalized = normalize_component_text(component_text)
    stmt = (
        select(ChatSession)
        .where(ChatSession.component_text == normalized)
        .order_by(ChatSession.updated_at.desc())
    )
    return list(db.scalars(stmt))


def list_group_sessions(db: Session, group_id: int) -> list[ChatSession]:
    stmt = select(ChatSession).where(ChatSession.group_id == group_id).order_by(ChatSession.updated_at.desc())
    return list(db.scalars(stmt))


def create_group_session(db: Session, group_id: int, title: str | None) -> ChatSession:
    session = ChatSession(
        word_id=None,
        component_text=None,
        component_id=None,
        group_id=group_id,
        title=title or f"Group Chat: {group_id}",
    )
    db.add(session)
    db.flush()
    return session


def create_component_session(db: Session, component_text: str, title: str | None) -> ChatSession:
    normalized = normalize_component_text(component_text)
    component_cache = get_component_cache(db, normalized)
    session = ChatSession(
        word_id=None,
        component_text=normalized,
        component_id=component_cache.id if component_cache else None,
        title=title or f"Component Chat: {normalized}",
    )
    db.add(session)
    db.flush()
    return session


def update_session_title(db: Session, session_id: int, title: str) -> ChatSession:
    session = db.get(ChatSession, session_id)
    if not session:
        raise ValueError("Session not found")
    session.title = title.strip()[:255]
    db.flush()
    return session


def delete_session(db: Session, session_id: int) -> None:
    session = db.get(ChatSession, session_id)
    if not session:
        raise ValueError("Session not found")
    db.delete(session)
    db.flush()


def auto_title_from_content(content: str, max_length: int = 30) -> str:
    text = content.strip().replace("\n", " ")
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


# ---------------------------------------------------------------------------
# Message listing
# ---------------------------------------------------------------------------

def list_messages(db: Session, session_id: int) -> list[ChatMessage]:
    stmt = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
    messages = list(db.scalars(stmt))

    session_stmt = (
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .options(
            joinedload(ChatSession.word_ref)
            .joinedload(Word.etymology)
            .options(
                joinedload(Etymology.component_items),
                joinedload(Etymology.branches),
            )
        )
    )
    session = db.scalar(session_stmt)
    if not session or not session.word_ref or not session.word_ref.etymology:
        return messages

    current_raw = session.word_ref.etymology.raw_description or ""
    if not current_raw.strip():
        return messages

    replacement = f"語源メモ: {repair_text(current_raw)}"
    for msg in messages:
        if msg.role != "assistant" or not msg.content:
            continue
        updated = re.sub(r"語源メモ:\s*Etymology summary for [A-Za-z0-9_-]+\.", replacement, msg.content)
        if updated != msg.content:
            msg.content = updated

    return messages


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fallback_answer(word: Word, user_input: str) -> tuple[str, list[dict]]:
    safe_input = repair_text(user_input)
    if has_suspected_mojibake(user_input) or has_suspected_mojibake(safe_input):
        summary = f"「{word.word}」の質問テキストに文字エンコード異常の可能性があります。質問を再入力してください。\n\n"
    else:
        summary = f"「{word.word}」についての質問を受け取りました。\n\n"
    if word.etymology and word.etymology.raw_description:
        summary += f"語源メモ: {repair_text(word.etymology.raw_description)}"
    else:
        summary += "まだ十分な語源データがありません。再取得を試してください。"
    return summary, [{"source": "etymology"}]


def _fallback_component_answer(component_text: str) -> tuple[str, list[dict]]:
    summary = (
        f"語源要素「{component_text}」についての質問を受け取りました。\n\n"
        "語源要素キャッシュをもとに説明します。必要ならデータ再取得を実行してください。"
    )
    return summary, [{"source": "component_cache"}]


def _format_markdown_for_readability(text: str) -> str:
    value = repair_text(text)
    value = re.sub(r"(?<!\n)(#{2,6}\s)", r"\n\1", value)
    value = re.sub(r"(?<!\n)(\d+\.\s)", r"\n\1", value)
    value = re.sub(r"(?<!\n)(-\s)", r"\n\1", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _load_history(db: Session, session_id: int, exclude_msg_id: int | None = None) -> list[dict]:
    """Load recent conversation history for the LLM context."""
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(MAX_HISTORY_MESSAGES)
    )
    msgs = list(reversed(db.scalars(stmt).all()))
    history: list[dict] = []
    for m in msgs:
        if m.id == exclude_msg_id:
            continue
        if m.role in ("user", "assistant"):
            history.append({"role": m.role, "content": m.content})
    return history


# ---------------------------------------------------------------------------
# Main entry: tool-calling agent loop
# ---------------------------------------------------------------------------

def _run_agent_loop(
    db: Session,
    system_prompt: str,
    context_json: str,
    history: list[dict],
    user_question: str,
) -> tuple[str, list[dict]]:
    """Call the LLM with tools in a loop until it produces a final text response."""
    client = OpenAI(api_key=settings.openai_api_key)

    messages: list[dict | Any] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"対象のデータ:\n{context_json}"},
        *history,
        {"role": "user", "content": user_question},
    ]

    citations: list[dict] = [{"source": "word_context"}]

    for round_idx in range(MAX_TOOL_ROUNDS):
        response = client.responses.create(
            model=settings.openai_model_chat,
            input=messages,
            tools=TOOL_DEFINITIONS,
        )

        tool_calls = [item for item in response.output if item.type == "function_call"]
        if not tool_calls:
            break

        messages.extend(response.output)

        for tc in tool_calls:
            try:
                args = json.loads(tc.arguments)
            except json.JSONDecodeError:
                args = {}
            logger.info("Tool call [round %d]: %s(%s)", round_idx + 1, tc.name, tc.arguments[:200])
            result = execute_tool(db, tc.name, args)
            messages.append({
                "type": "function_call_output",
                "call_id": tc.call_id,
                "output": result,
            })
            citations.append({
                "source": tc.name,
                "query": args.get("queries") or args.get("patterns") or args.get("word"),
            })

    assistant_content = _format_markdown_for_readability(response.output_text.strip())
    if has_suspected_mojibake(assistant_content):
        assistant_content = (
            "回答テキストに文字エンコード異常が検出されました。"
            "もう一度質問するか、データ再取得を実行してください。"
        )
    return assistant_content, citations


def answer_in_session(db: Session, session: ChatSession, user_input: str) -> tuple[ChatMessage, ChatMessage]:
    safe_user_input = repair_text(user_input)
    if has_suspected_mojibake(user_input) or has_suspected_mojibake(safe_user_input):
        safe_user_input = "文字エンコード異常の可能性があるため、質問を再入力してください。"
    user_msg = ChatMessage(session_id=session.id, role="user", content=safe_user_input, citations=[])
    db.add(user_msg)
    db.flush()

    if session.group_id:
        group_stmt = (
            select(WordGroup)
            .where(WordGroup.id == session.group_id)
            .options(
                joinedload(WordGroup.items).joinedload(WordGroupItem.word_ref),
                joinedload(WordGroup.items).joinedload(WordGroupItem.definition_ref),
            )
        )
        group = db.scalar(group_stmt)
        if not group:
            raise ValueError("Group not found")
        context_json = json.dumps(build_group_context(group), ensure_ascii=False)
    elif session.component_text:
        component_text = normalize_component_text(session.component_text)
        word_stmt = select(Word).options(
            joinedload(Word.definitions),
            joinedload(Word.etymology).joinedload(Etymology.component_items),
            joinedload(Word.etymology).joinedload(Etymology.component_meanings),
            joinedload(Word.etymology).joinedload(Etymology.variants).joinedload(EtymologyVariant.component_items),
            joinedload(Word.etymology).joinedload(Etymology.variants).joinedload(EtymologyVariant.component_meanings),
            joinedload(Word.derivations),
            joinedload(Word.related_words),
        )
        words = list(db.scalars(word_stmt).unique())
        matched_words: list[Word] = []
        for word in words:
            etymology = word.etymology
            if not etymology:
                continue
            def _component_text(item) -> str:
                value = getattr(
                    item,
                    "component_text",
                    item.get("text", "") if isinstance(item, dict) else "",
                )
                return str(value).strip().lower()

            items: list = list(etymology.component_items or []) + list(etymology.component_meanings or [])
            for v in (etymology.variants or []):
                items.extend(v.component_items or [])
                items.extend(v.component_meanings or [])
            for item in items:
                if _component_text(item) == component_text:
                    matched_words.append(word)
                    break
        component_cache = get_component_cache(db, component_text)
        context_json = json.dumps(
            build_component_context(component_text, matched_words, component_cache),
            ensure_ascii=False,
        )
    else:
        word_stmt = (
            select(Word)
            .where(Word.id == session.word_id)
            .options(
                joinedload(Word.definitions),
                joinedload(Word.etymology).joinedload(Etymology.component_items),
                joinedload(Word.etymology).joinedload(Etymology.component_meanings),
                joinedload(Word.etymology).joinedload(Etymology.variants).joinedload(EtymologyVariant.component_items),
                joinedload(Word.etymology).joinedload(Etymology.variants).joinedload(EtymologyVariant.component_meanings),
                joinedload(Word.derivations),
                joinedload(Word.related_words),
            )
        )
        word = db.scalar(word_stmt)
        if not word:
            raise ValueError("Word not found")
        context_json = json.dumps(build_word_context(word), ensure_ascii=False)

    system_prompt = load_prompt("chat_agent.md")
    history = _load_history(db, session.id, exclude_msg_id=user_msg.id)

    if settings.openai_api_key:
        try:
            assistant_content, citations = _run_agent_loop(
                db, system_prompt, context_json, history, safe_user_input,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Agent loop failed")
            if session.component_text:
                assistant_content, citations = _fallback_component_answer(
                    normalize_component_text(session.component_text)
                )
            else:
                assistant_content, citations = _fallback_answer(word, safe_user_input)
    else:
        if session.component_text:
            assistant_content, citations = _fallback_component_answer(normalize_component_text(session.component_text))
        else:
            assistant_content, citations = _fallback_answer(word, safe_user_input)
        if has_suspected_mojibake(assistant_content):
            assistant_content = (
                "回答テキストに文字エンコード異常が検出されました。"
                "もう一度質問するか、データ再取得を実行してください。"
            )

    assistant_content = _format_markdown_for_readability(assistant_content)

    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=assistant_content,
        citations=citations,
    )
    db.add(assistant_msg)
    db.flush()
    return user_msg, assistant_msg
