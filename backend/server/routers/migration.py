from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.schemas import (
    MigrationInflectionApplyRequest,
    MigrationInflectionApplyResponse,
    MigrationInflectionApplyResult,
    MigrationInflectionTarget,
    MigrationInflectionTargetsResponse,
)
from database_build.ops.inflection import apply_inflection_migration as apply_inflection_migration_job
from database_build.ops.inflection import list_inflection_targets as list_inflection_targets_job

router = APIRouter(prefix="/api/migration", tags=["migration"])


@router.get("/inflection/targets", response_model=MigrationInflectionTargetsResponse)
def list_inflection_targets(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> MigrationInflectionTargetsResponse:
    rows, total = list_inflection_targets_job(db, page=page, page_size=page_size)
    return MigrationInflectionTargetsResponse(
        words=[MigrationInflectionTarget(id=word_id, word=word_text) for word_id, word_text in rows],
        total=int(total),
    )


@router.post("/inflection/apply", response_model=MigrationInflectionApplyResponse)
def apply_inflection_migration(
    payload: MigrationInflectionApplyRequest,
    db: Session = Depends(get_db),
) -> MigrationInflectionApplyResponse:
    summary, results = apply_inflection_migration_job(db, payload)
    return MigrationInflectionApplyResponse(
        applied=summary.applied,
        skipped=summary.skipped,
        errors=summary.errors,
        results=[
            MigrationInflectionApplyResult(
                word_id=item.word_id,
                action=item.action,
                status=item.status,
                detail=item.detail,
            )
            for item in results
        ],
    )
