from __future__ import annotations

import json

import pytest
from sqlalchemy.orm import Session

import core.services.chat_tools as chat_tools_module
from core.models import ChatMessage, ChatSession, Word
from core.services.chat_tools import execute_tool


def test_register_related_word_creates_and_links(db_session: Session) -> None:
    target = Word(word="abandon")
    linked = Word(word="in light of")
    db_session.add_all([target, linked])
    db_session.commit()

    result = json.loads(
        execute_tool(
            db_session,
            "register_related_word",
            {"related_word": "in light of", "relation_type": "synonym"},
            word_id=target.id,
        )
    )

    assert result["result"] == "created"
    assert result["related_word"]["related_word"] == "in light of"
    assert result["related_word"]["relation_type"] == "synonym"

    db_session.commit()
    db_session.refresh(target)
    assert len(target.related_words) == 1
    assert target.related_words[0].linked_word_id == linked.id


def test_register_related_word_detects_duplicate_within_same_turn(db_session: Session) -> None:
    target = Word(word="abandon")
    db_session.add(target)
    db_session.commit()

    args = {"related_word": "forsake", "relation_type": "synonym"}
    first = json.loads(execute_tool(db_session, "register_related_word", args, word_id=target.id))
    assert first["result"] == "created"

    # Simulates the LLM calling the tool twice for the same request within one agent loop,
    # before anything has been committed.
    second = json.loads(execute_tool(db_session, "register_related_word", args, word_id=target.id))
    assert second["result"] == "already_exists"

    db_session.commit()
    db_session.refresh(target)
    assert len(target.related_words) == 1


def test_register_related_word_detects_duplicate_after_commit(db_session: Session) -> None:
    target = Word(word="abandon")
    db_session.add(target)
    db_session.commit()

    args = {"related_word": "forsake", "relation_type": "synonym"}
    execute_tool(db_session, "register_related_word", args, word_id=target.id)
    db_session.commit()

    result = json.loads(execute_tool(db_session, "register_related_word", args, word_id=target.id))
    assert result["result"] == "already_exists"


def test_register_related_word_clamps_invalid_relation_type(db_session: Session) -> None:
    target = Word(word="abandon")
    db_session.add(target)
    db_session.commit()

    result = json.loads(
        execute_tool(
            db_session,
            "register_related_word",
            {"related_word": "quit", "relation_type": "bogus-type"},
            word_id=target.id,
        )
    )

    assert result["result"] == "created"
    assert result["related_word"]["relation_type"] == "synonym"
    assert result["relation_type_clamped"] is True


def test_register_related_word_without_word_id_returns_error(db_session: Session) -> None:
    result = json.loads(
        execute_tool(
            db_session,
            "register_related_word",
            {"related_word": "quit", "relation_type": "synonym"},
        )
    )
    assert "error" in result


def test_register_related_word_missing_word_returns_error(db_session: Session) -> None:
    target = Word(word="abandon")
    db_session.add(target)
    db_session.commit()

    result = json.loads(
        execute_tool(
            db_session,
            "register_related_word",
            {"related_word": "", "relation_type": "synonym"},
            word_id=target.id,
        )
    )
    assert "error" in result


def test_execute_tool_failure_does_not_lose_prior_flushed_writes(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing tool call must only undo its own write, not the whole
    transaction. answer_in_session flushes the user's ChatMessage before
    running the tool loop on the same db session/transaction; a naive
    db.rollback() in execute_tool's except block would silently discard that
    already-flushed message along with the failed tool's write."""
    target = Word(word="abandon")
    db_session.add(target)
    db_session.commit()

    session = ChatSession(word_id=target.id)
    db_session.add(session)
    db_session.flush()
    user_msg = ChatMessage(session_id=session.id, role="user", content="hi", citations=[])
    db_session.add(user_msg)
    db_session.flush()
    assert user_msg.id is not None

    def _boom(db: Session, word: Word) -> None:
        raise RuntimeError("simulated failure in the write path")

    monkeypatch.setattr(chat_tools_module, "link_related_words", _boom)

    result = json.loads(
        execute_tool(
            db_session,
            "register_related_word",
            {"related_word": "in light of", "relation_type": "synonym"},
            word_id=target.id,
        )
    )
    assert result == {"error": "Tool 'register_related_word' failed"}

    # The session must still be usable for the rest of the turn: adding and
    # committing the assistant's reply must succeed, and the earlier
    # already-flushed user message must still be there afterward.
    assistant_msg = ChatMessage(session_id=session.id, role="assistant", content="reply", citations=[])
    db_session.add(assistant_msg)
    db_session.commit()

    messages = (
        db_session.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.id)
        .all()
    )
    assert [m.role for m in messages] == ["user", "assistant"]

    # The failed related-word write itself must not have been persisted.
    db_session.refresh(target)
    assert target.related_words == []
