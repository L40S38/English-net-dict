from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Etymology, EtymologyComponent, EtymologyComponentItem, Word
from app.schemas import EtymologyComponentListItem, EtymologyComponentListResponse, EtymologyComponentRead
from app.services import word_service
from app.services.etymology_component_service import (
    ensure_component_cache,
    get_component_cache,
    normalize_component_text,
)

router = APIRouter(prefix="/api/etymology-components", tags=["etymology-components"])


@router.get("", response_model=EtymologyComponentListResponse)
def list_etymology_components(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> EtymologyComponentListResponse:
    stmt = select(EtymologyComponent).order_by(EtymologyComponent.updated_at.desc())
    if q:
        keyword = q.strip()
        if keyword:
            stmt = stmt.where(EtymologyComponent.component_text.ilike(f"%{keyword}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    component_ids = [item.id for item in items]
    counts: dict[int, int] = {}
    if component_ids:
        rows = db.execute(
            select(EtymologyComponentItem.component_id, func.count(func.distinct(Etymology.word_id)))
            .join(Etymology, Etymology.id == EtymologyComponentItem.etymology_id)
            .where(EtymologyComponentItem.component_id.in_(component_ids))
            .group_by(EtymologyComponentItem.component_id)
        ).all()
        counts = {int(component_id): int(count) for component_id, count in rows if component_id is not None}
    result_items = []
    for item in items:
        base = EtymologyComponentRead.model_validate(item)
        result_items.append(EtymologyComponentListItem(**base.model_dump(), word_count=counts.get(item.id, 0)))
    return EtymologyComponentListResponse(items=result_items, total=total)


@router.get("/{component_text}", response_model=EtymologyComponentRead)
async def get_etymology_component(component_text: str, db: Session = Depends(get_db)) -> EtymologyComponentRead:
    normalized = normalize_component_text(component_text)
    if not normalized:
        raise HTTPException(status_code=400, detail="component_text is required")
    component = get_component_cache(db, normalized)
    if not component:
        raise HTTPException(status_code=404, detail="Etymology component not found")
    return EtymologyComponentRead.model_validate(component)


@router.post("/{component_text}", response_model=EtymologyComponentRead)
async def create_etymology_component(component_text: str, db: Session = Depends(get_db)) -> EtymologyComponentRead:
    normalized = normalize_component_text(component_text)
    if not normalized:
        raise HTTPException(status_code=400, detail="component_text is required")
    existing = get_component_cache(db, normalized)
    if existing:
        return EtymologyComponentRead.model_validate(existing)
    component, _ = await ensure_component_cache(db, normalized, force_refresh=False)
    words = list(
        db.scalars(
            select(Word).options(
                joinedload(Word.etymology).joinedload(Etymology.component_items),
            )
        ).unique()
    )
    filtered = [word for word in words if word_service.has_etymology_component(word, normalized)]
    component.resolved_meaning = word_service.resolve_component_meaning(filtered, normalized)
    db.commit()
    db.refresh(component)
    return EtymologyComponentRead.model_validate(component)


@router.post("/{component_text}/rescrape", response_model=EtymologyComponentRead)
async def rescrape_etymology_component(component_text: str, db: Session = Depends(get_db)) -> EtymologyComponentRead:
    normalized = normalize_component_text(component_text)
    if not normalized:
        raise HTTPException(status_code=400, detail="component_text is required")
    component, _ = await ensure_component_cache(db, normalized, force_refresh=True)
    db.commit()
    db.refresh(component)
    return EtymologyComponentRead.model_validate(component)
