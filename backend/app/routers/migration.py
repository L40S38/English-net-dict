from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Word
from app.schemas import (
    MigrationInflectionApplyRequest,
    MigrationInflectionApplyResponse,
    MigrationInflectionApplyResult,
    MigrationInflectionTarget,
    MigrationInflectionTargetsResponse,
)
from app.services.word_merge_service import link_to_lemma, merge_into_lemma

router = APIRouter(prefix="/api/migration", tags=["migration"])


def _target_filter():
    return Word.lemma_word_id.is_(None), Word.inflection_type.is_(None)


@router.get("/inflection/targets", response_model=MigrationInflectionTargetsResponse)
def list_inflection_targets(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> MigrationInflectionTargetsResponse:
    filters = _target_filter()
    total = db.scalar(select(func.count(Word.id)).where(*filters)) or 0
    stmt = (
        select(Word.id, Word.word)
        .where(*filters)
        .order_by(Word.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = db.execute(stmt).all()
    return MigrationInflectionTargetsResponse(
        words=[MigrationInflectionTarget(id=word_id, word=word_text) for word_id, word_text in rows],
        total=int(total),
    )


@router.post("/inflection/apply", response_model=MigrationInflectionApplyResponse)
def apply_inflection_migration(
    payload: MigrationInflectionApplyRequest,
    db: Session = Depends(get_db),
) -> MigrationInflectionApplyResponse:
    results: list[MigrationInflectionApplyResult] = []
    applied = 0
    skipped = 0
    errors = 0

    for decision in payload.decisions:
        inflected = db.get(Word, decision.word_id)
        lemma = db.get(Word, decision.lemma_word_id)
        if inflected is None:
            errors += 1
            results.append(
                MigrationInflectionApplyResult(
                    word_id=decision.word_id,
                    action=decision.action,
                    status="error",
                    detail="word_id not found",
                )
            )
            continue
        if lemma is None:
            errors += 1
            results.append(
                MigrationInflectionApplyResult(
                    word_id=decision.word_id,
                    action=decision.action,
                    status="error",
                    detail="lemma_word_id not found",
                )
            )
            continue
        if inflected.id == lemma.id:
            skipped += 1
            results.append(
                MigrationInflectionApplyResult(
                    word_id=decision.word_id,
                    action=decision.action,
                    status="skipped",
                    detail="word_id and lemma_word_id are identical",
                )
            )
            continue

        try:
            with db.begin_nested():
                if decision.action == "merge":
                    merge_into_lemma(db, inflected, lemma)
                else:
                    link_to_lemma(db, inflected, lemma, decision.inflection_type or "inflection")
            applied += 1
            results.append(
                MigrationInflectionApplyResult(
                    word_id=decision.word_id,
                    action=decision.action,
                    status="applied",
                    detail="",
                )
            )
        except Exception as exc:  # noqa: BLE001
            errors += 1
            results.append(
                MigrationInflectionApplyResult(
                    word_id=decision.word_id,
                    action=decision.action,
                    status="error",
                    detail=str(exc),
                )
            )

    db.commit()
    return MigrationInflectionApplyResponse(
        applied=applied,
        skipped=skipped,
        errors=errors,
        results=results,
    )
