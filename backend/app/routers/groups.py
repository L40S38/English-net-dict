from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Definition, Word, WordGroup, WordGroupItem
from app.schemas import (
    GenerateImageRequest,
    GroupImageRead,
    GroupSuggestRequest,
    GroupSuggestResponse,
    WordGroupCreate,
    WordGroupItemCreate,
    WordGroupItemRead,
    WordGroupListResponse,
    WordGroupRead,
    WordGroupUpdate,
)
from app.services.group_suggest_service import suggest_group_candidates
from app.services.image_service import build_group_image_prompt, generate_group_image

router = APIRouter(prefix="/api/groups", tags=["groups"])


def _item_to_read(item: WordGroupItem) -> WordGroupItemRead:
    definition = item.definition_ref
    return WordGroupItemRead(
        id=item.id,
        item_type=item.item_type,
        word_id=item.word_id,
        definition_id=item.definition_id,
        phrase_text=item.phrase_text,
        phrase_meaning=item.phrase_meaning,
        sort_order=item.sort_order,
        created_at=item.created_at,
        word=item.word_ref.word if item.word_ref else None,
        definition_part_of_speech=definition.part_of_speech if definition else None,
        definition_meaning_ja=definition.meaning_ja if definition else None,
        example_en=definition.example_en if definition else None,
        example_ja=definition.example_ja if definition else None,
    )


def _group_to_read(group: WordGroup, *, include_items: bool) -> WordGroupRead:
    items = [_item_to_read(item) for item in group.items] if include_items else []
    return WordGroupRead(
        id=group.id,
        name=group.name,
        description=group.description,
        item_count=len(group.items),
        created_at=group.created_at,
        updated_at=group.updated_at,
        items=items,
        images=[GroupImageRead.model_validate(img) for img in group.images],
    )


def _query_group(db: Session, group_id: int) -> WordGroup | None:
    stmt = (
        select(WordGroup)
        .where(WordGroup.id == group_id)
        .options(
            joinedload(WordGroup.items).joinedload(WordGroupItem.word_ref),
            joinedload(WordGroup.items).joinedload(WordGroupItem.definition_ref),
            joinedload(WordGroup.images),
        )
    )
    return db.scalar(stmt)


@router.get("", response_model=WordGroupListResponse)
def list_groups(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> WordGroupListResponse:
    stmt = (
        select(WordGroup)
        .options(joinedload(WordGroup.items))
        .order_by(WordGroup.updated_at.desc(), WordGroup.id.desc())
    )
    if q:
        keyword = q.strip()
        if keyword:
            stmt = stmt.where(WordGroup.name.ilike(f"%{keyword}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    groups = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).unique())
    return WordGroupListResponse(items=[_group_to_read(group, include_items=False) for group in groups], total=total)


@router.post("", response_model=WordGroupRead)
def create_group(payload: WordGroupCreate, db: Session = Depends(get_db)) -> WordGroupRead:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    group = WordGroup(name=name[:128], description=payload.description.strip())
    db.add(group)
    db.commit()
    db.refresh(group)
    return _group_to_read(group, include_items=True)


@router.get("/{group_id}", response_model=WordGroupRead)
def get_group(group_id: int, db: Session = Depends(get_db)) -> WordGroupRead:
    group = _query_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return _group_to_read(group, include_items=True)


@router.put("/{group_id}", response_model=WordGroupRead)
def update_group(group_id: int, payload: WordGroupUpdate, db: Session = Depends(get_db)) -> WordGroupRead:
    group = db.get(WordGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    group.name = name[:128]
    group.description = payload.description.strip()
    db.commit()
    refreshed = _query_group(db, group_id)
    if not refreshed:
        raise HTTPException(status_code=404, detail="Group not found")
    return _group_to_read(refreshed, include_items=True)


@router.delete("/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db)) -> dict:
    group = db.get(WordGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    db.delete(group)
    db.commit()
    return {"ok": True}


@router.post("/{group_id}/items", response_model=WordGroupItemRead)
def add_group_item(group_id: int, payload: WordGroupItemCreate, db: Session = Depends(get_db)) -> WordGroupItemRead:
    group = db.get(WordGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    item_type = payload.item_type
    item = WordGroupItem(group_id=group_id, item_type=item_type, sort_order=payload.sort_order)
    if item_type == "word":
        if payload.word_id is None:
            raise HTTPException(status_code=400, detail="word_id is required for word items")
        word = db.get(Word, payload.word_id)
        if not word:
            raise HTTPException(status_code=404, detail="Word not found")
        item.word_id = word.id
    elif item_type == "phrase":
        phrase_text = (payload.phrase_text or "").strip()
        if not phrase_text:
            raise HTTPException(status_code=400, detail="phrase_text is required for phrase items")
        item.phrase_text = phrase_text[:255]
        item.phrase_meaning = (payload.phrase_meaning or "").strip()
    elif item_type == "example":
        if payload.word_id is None or payload.definition_id is None:
            raise HTTPException(status_code=400, detail="word_id and definition_id are required for example items")
        word = db.get(Word, payload.word_id)
        definition = db.get(Definition, payload.definition_id)
        if not word:
            raise HTTPException(status_code=404, detail="Word not found")
        if not definition or definition.word_id != word.id:
            raise HTTPException(status_code=404, detail="Definition not found")
        item.word_id = word.id
        item.definition_id = definition.id
    db.add(item)
    db.commit()
    refreshed = db.scalar(
        select(WordGroupItem)
        .where(WordGroupItem.id == item.id)
        .options(joinedload(WordGroupItem.word_ref), joinedload(WordGroupItem.definition_ref))
    )
    if not refreshed:
        raise HTTPException(status_code=404, detail="Item not found")
    return _item_to_read(refreshed)


@router.delete("/{group_id}/items/{item_id}")
def delete_group_item(group_id: int, item_id: int, db: Session = Depends(get_db)) -> dict:
    item = db.get(WordGroupItem, item_id)
    if not item or item.group_id != group_id:
        raise HTTPException(status_code=404, detail="Group item not found")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.post("/{group_id}/suggest", response_model=GroupSuggestResponse)
def suggest_group_items(
    group_id: int,
    payload: GroupSuggestRequest,
    db: Session = Depends(get_db),
) -> GroupSuggestResponse:
    group = db.get(WordGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return suggest_group_candidates(db, payload.keywords, payload.limit)


@router.post("/{group_id}/generate-image", response_model=GroupImageRead)
def generate_group_image_route(
    group_id: int,
    payload: GenerateImageRequest,
    db: Session = Depends(get_db),
) -> GroupImageRead:
    group = _query_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    image = generate_group_image(db, group, payload.prompt)
    db.commit()
    db.refresh(image)
    return GroupImageRead.model_validate(image)


@router.get("/{group_id}/default-image-prompt")
def get_group_default_image_prompt(group_id: int, db: Session = Depends(get_db)) -> dict:
    group = _query_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return {"prompt": build_group_image_prompt(group)}
