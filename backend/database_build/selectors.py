from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.models import Word


def load_words(
    db: Session,
    *,
    word_filter: str | None = None,
    limit: int | None = None,
    joinedloads: tuple = (),
) -> list[Word]:
    stmt = select(Word)
    for jl in joinedloads:
        stmt = stmt.options(jl)
    stmt = stmt.order_by(Word.id)
    if word_filter:
        stmt = stmt.where(func.lower(Word.word) == word_filter.strip().lower())
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt).unique())
