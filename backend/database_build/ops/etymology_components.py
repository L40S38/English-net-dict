from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from core.models import Etymology, EtymologyComponent, Word
from core.services import word_service
from core.services.etymology_component_service import ensure_component_cache, get_component_cache


async def create_component_if_missing(db: Session, normalized: str) -> EtymologyComponent:
    existing = get_component_cache(db, normalized)
    if existing:
        return existing
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
    return component


async def rescrape_component(db: Session, normalized: str) -> EtymologyComponent:
    component, _ = await ensure_component_cache(db, normalized, force_refresh=True)
    db.commit()
    db.refresh(component)
    return component
