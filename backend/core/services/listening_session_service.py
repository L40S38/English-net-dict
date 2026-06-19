from __future__ import annotations

import re
from datetime import datetime
from itertools import zip_longest

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from core.models import (
    ListeningAttempt,
    ListeningLine,
    ListeningScript,
    ListeningSession,
    ListeningWordResult,
    Word,
)

_WORD_RE = re.compile(r"[A-Za-z']+")


def _tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in _WORD_RE.finditer(text or "")]


def create_session(db: Session, script: ListeningScript) -> ListeningSession:
    session = ListeningSession(script_id=script.id)
    db.add(session)
    db.flush()
    return session


def list_sessions(db: Session, status: str | None = None) -> list[ListeningSession]:
    stmt = select(ListeningSession).order_by(ListeningSession.updated_at.desc())
    if status:
        stmt = stmt.where(ListeningSession.status == status)
    return list(db.scalars(stmt))


def update_session(
    db: Session,
    session: ListeningSession,
    *,
    current_step: str | None = None,
    playback_speed: float | None = None,
    dictation_level: int | None = None,
    status: str | None = None,
) -> ListeningSession:
    if current_step is not None:
        session.current_step = current_step
    if playback_speed is not None:
        session.playback_speed = playback_speed
    if dictation_level is not None:
        session.dictation_level = dictation_level
    if status is not None:
        session.status = status
        if status == "completed" and session.completed_at is None:
            session.completed_at = datetime.utcnow()
    db.flush()
    return session


def _resolve_word_id(db: Session, token: str, cache: dict[str, int | None]) -> int | None:
    if token in cache:
        return cache[token]
    word_id = db.scalar(select(Word.id).where(func.lower(Word.word) == token))
    cache[token] = word_id
    return word_id


def record_attempt(
    db: Session,
    session: ListeningSession,
    line: ListeningLine,
    dictation_level: int,
    user_text: str,
) -> ListeningAttempt:
    correct_tokens = _tokenize(line.text)
    user_tokens = _tokenize(user_text)
    is_line_correct = all(c == u for c, u in zip_longest(correct_tokens, user_tokens))

    attempt = ListeningAttempt(
        session_id=session.id,
        line_id=line.id,
        dictation_level=dictation_level,
        user_text=user_text,
        is_correct=is_line_correct,
    )
    db.add(attempt)
    db.flush()

    word_id_cache: dict[str, int | None] = {}
    for idx, correct_token in enumerate(correct_tokens):
        user_token = user_tokens[idx] if idx < len(user_tokens) else None
        db.add(
            ListeningWordResult(
                attempt_id=attempt.id,
                word_text=correct_token,
                matched_word_id=_resolve_word_id(db, correct_token, word_id_cache),
                is_correct=user_token == correct_token,
            )
        )
    db.flush()
    return attempt


def get_weak_word_stats(db: Session, limit: int = 50) -> list[dict]:
    wrong_count = func.sum(case((ListeningWordResult.is_correct.is_(False), 1), else_=0))
    total_count = func.count()
    matched_word_id = func.max(ListeningWordResult.matched_word_id)
    stmt = (
        select(
            ListeningWordResult.word_text,
            total_count.label("total"),
            wrong_count.label("wrong"),
            matched_word_id.label("matched_word_id"),
        )
        .group_by(ListeningWordResult.word_text)
        .having(wrong_count > 0)
        .order_by(wrong_count.desc(), total_count.desc())
        .limit(limit)
    )
    results: list[dict] = []
    for row in db.execute(stmt).all():
        total = int(row.total)
        wrong = int(row.wrong)
        results.append(
            {
                "word_text": row.word_text,
                "total": total,
                "wrong": wrong,
                "accuracy": round((total - wrong) / total, 3) if total else 0.0,
                "matched_word_id": row.matched_word_id,
            }
        )
    return results
