from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import Phrase, Word
from core.schemas import SearchSuggestItem

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/suggest", response_model=list[SearchSuggestItem])
def suggest_combined(
    q: str = Query(default="", min_length=0),
    limit: int = Query(default=10, ge=1, le=20),
    db: Session = Depends(get_db),
) -> list[SearchSuggestItem]:
    """ヘッダー検索用に単語・熟語を横断したサジェストを返す。"""
    keyword = q.strip()
    if not keyword:
        return []
    lowered = keyword.lower()

    word_prefix = Word.word.ilike(f"{keyword}%")
    word_rows = db.execute(
        select(Word.id, Word.word)
        .where(Word.word.ilike(f"%{keyword}%"))
        .order_by(word_prefix.desc(), Word.last_viewed_at.desc(), Word.updated_at.desc())
        .limit(limit)
    ).all()

    phrase_prefix = Phrase.text.ilike(f"{keyword}%")
    phrase_rows = db.execute(
        select(Phrase.id, Phrase.text)
        .where(Phrase.text.ilike(f"%{keyword}%"))
        .order_by(phrase_prefix.desc(), Phrase.updated_at.desc())
        .limit(limit)
    ).all()

    # (前方一致か, 候補) のペアで集約し、結果件数が小さいので Python 側でまとめてソートする。
    ranked = [
        (row.word.lower().startswith(lowered), SearchSuggestItem(type="word", id=row.id, text=row.word))
        for row in word_rows
    ] + [
        (row.text.lower().startswith(lowered), SearchSuggestItem(type="phrase", id=row.id, text=row.text))
        for row in phrase_rows
    ]
    ranked.sort(key=lambda pair: not pair[0])
    return [item for _, item in ranked][:limit]
