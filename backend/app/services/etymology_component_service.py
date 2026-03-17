from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import EtymologyComponent
from app.services.scraper.wiktionary import WiktionaryScraper


def normalize_component_text(component_text: str) -> str:
    return component_text.strip().lower()


def get_component_cache(db: Session, component_text: str) -> EtymologyComponent | None:
    normalized = normalize_component_text(component_text)
    if not normalized:
        return None
    stmt = select(EtymologyComponent).where(func.lower(EtymologyComponent.component_text) == normalized)
    return db.scalar(stmt)


async def ensure_component_cache(
    db: Session,
    component_text: str,
    *,
    force_refresh: bool = False,
) -> tuple[EtymologyComponent, bool]:
    normalized = normalize_component_text(component_text)
    existing = get_component_cache(db, normalized)
    if existing and not force_refresh:
        return existing, False

    scraped = await WiktionaryScraper().scrape_component_page(normalized)
    target = existing or EtymologyComponent(component_text=normalized)
    target.wiktionary_meanings = scraped.get("meanings", [])
    target.wiktionary_related_terms = scraped.get("related_terms", [])
    target.wiktionary_derived_terms = scraped.get("derived_terms", [])
    target.wiktionary_source_url = scraped.get("source_url")
    if not existing:
        db.add(target)
    db.flush()
    return target, True
