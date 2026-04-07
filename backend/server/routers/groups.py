from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from core.constants import GROUP_NAME_MAX_LENGTH
from core.database import get_db
from core.models import Definition, Phrase, Word, WordGroup, WordGroupItem
from core.schemas import (
    GenerateImageRequest,
    GroupBulkAddItemsRequest,
    GroupBulkAddItemsResponse,
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
from core.services.group_suggest_service import suggest_group_candidates
from core.services.image_service import build_group_image_prompt, generate_group_image
from core.services.phrase_service import get_or_create_phrase, merge_meanings

router = APIRouter(prefix="/api/groups", tags=["groups"])


def _item_to_read(item: WordGroupItem) -> WordGroupItemRead:
    definition = item.definition_ref
    phrase = item.phrase_ref
    phrase_text = phrase.text if phrase else item.phrase_text
    phrase_meaning = phrase.meaning if phrase else item.phrase_meaning
    resolved_word_id = item.word_id
    if item.item_type == "phrase" and resolved_word_id is None and phrase is not None:
        links = phrase.word_links
        if links:
            resolved_word_id = links[0].word_id
    return WordGroupItemRead(
        id=item.id,
        item_type=item.item_type,
        word_id=resolved_word_id,
        definition_id=item.definition_id,
        phrase_id=item.phrase_id,
        phrase_text=phrase_text,
        phrase_meaning=phrase_meaning,
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
            joinedload(WordGroup.items).joinedload(WordGroupItem.phrase_ref).joinedload(Phrase.word_links),
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
    if len(name) > GROUP_NAME_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"group name must be at most {GROUP_NAME_MAX_LENGTH} characters",
        )
    group = WordGroup(name=name, description=payload.description.strip())
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
    if len(name) > GROUP_NAME_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"group name must be at most {GROUP_NAME_MAX_LENGTH} characters",
        )
    group.name = name
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
        phrase: Phrase | None = None
        if payload.phrase_id is not None:
            phrase = db.get(Phrase, payload.phrase_id)
            if not phrase:
                raise HTTPException(status_code=404, detail="Phrase not found")
        elif payload.phrase_text:
            phrase = get_or_create_phrase(db, payload.phrase_text, payload.phrase_meaning or "")
        if not phrase:
            raise HTTPException(status_code=400, detail="phrase_id or phrase_text is required for phrase items")
        item.phrase_id = phrase.id
        item.phrase_text = phrase.text[:255]
        item.phrase_meaning = merge_meanings(phrase.meaning or "", payload.phrase_meaning or "")
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
        .options(
            joinedload(WordGroupItem.word_ref),
            joinedload(WordGroupItem.definition_ref),
            joinedload(WordGroupItem.phrase_ref).joinedload(Phrase.word_links),
        )
    )
    if not refreshed:
        raise HTTPException(status_code=404, detail="Item not found")
    return _item_to_read(refreshed)


@router.post("/{group_id}/bulk-add-items", response_model=GroupBulkAddItemsResponse)
def bulk_add_group_items(
    group_id: int,
    payload: GroupBulkAddItemsRequest,
    db: Session = Depends(get_db),
) -> GroupBulkAddItemsResponse:
    group = db.get(WordGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    targets = [word_id for word_id in payload.word_ids if isinstance(word_id, int) and word_id > 0]
    if not targets:
        return GroupBulkAddItemsResponse(added=0, skipped=0)

    existing_word_ids = set(
        db.scalars(
            select(WordGroupItem.word_id).where(
                WordGroupItem.group_id == group_id,
                WordGroupItem.item_type == "word",
                WordGroupItem.word_id.is_not(None),
            )
        )
    )
    existing_word_ids.discard(None)
    valid_word_ids = set(db.scalars(select(Word.id).where(Word.id.in_(targets))))

    added = 0
    skipped = 0
    for word_id in targets:
        if word_id not in valid_word_ids or word_id in existing_word_ids:
            skipped += 1
            continue
        db.add(WordGroupItem(group_id=group_id, item_type="word", word_id=word_id))
        existing_word_ids.add(word_id)
        added += 1

    db.commit()
    return GroupBulkAddItemsResponse(added=added, skipped=skipped)


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
