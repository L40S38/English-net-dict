from __future__ import annotations

import json

from sqlalchemy.orm import Session

from core.models import Word
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
