from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import EtymologyComponentRead
from app.services.etymology_component_service import ensure_component_cache, normalize_component_text

router = APIRouter(prefix="/api/etymology-components", tags=["etymology-components"])


@router.get("/{component_text}", response_model=EtymologyComponentRead)
async def get_etymology_component(component_text: str, db: Session = Depends(get_db)) -> EtymologyComponentRead:
    normalized = normalize_component_text(component_text)
    if not normalized:
        raise HTTPException(status_code=400, detail="component_text is required")
    component, changed = await ensure_component_cache(db, normalized, force_refresh=False)
    if changed:
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
