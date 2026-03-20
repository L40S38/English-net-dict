from __future__ import annotations

import re
from functools import lru_cache

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import (
    Definition,
    Derivation,
    Etymology,
    EtymologyBranch,
    EtymologyComponent,
    EtymologyComponentItem,
    EtymologyComponentMeaning,
    EtymologyLanguageChainLink,
    EtymologyVariant,
    RelatedWord,
    Word,
)
from app.schemas import (
    DefinitionRead,
    DerivationRead,
    EtymologyComponentItemCreate,
    EtymologyUpdate,
    RelatedWordRead,
    StructuredWordPayload,
    WordImageRead,
    WordRead,
)
from app.services.wordnet_service import get_wordnet_snapshot
from app.services.phrase_service import (
    get_or_create_phrase,
    link_phrase_to_word,
    normalize_phrase_text,
)
from app.utils.etymology_components import normalize_component_text
from app.stores.word_store import WordStore
from app.utils.pos_labels import normalize_part_of_speech

def _is_word_like_component(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    if normalized.startswith("-") or normalized.endswith("-"):
        return False
    return bool(re.fullmatch(r"[a-z][a-z'-]*", normalized))


def _is_forced_morpheme_component(component: dict) -> bool:
    text = str(component.get("text", "")).strip()
    normalized = text.lower()
    if not normalized:
        return True
    # Keep hyphenated affix forms (over-, -ment) as morphemes by default.
    if normalized.startswith("-") or normalized.endswith("-"):
        return True
    comp_type = str(component.get("type", "")).strip().lower()
    if comp_type in {"prefix", "suffix", "root", "proto_root"}:
        return True
    meaning = str(component.get("meaning", "")).strip()
    if any(keyword in meaning for keyword in ("接頭", "接尾", "語根")):
        return True
    if meaning in {"語源要素", "接頭要素", "語根要素"}:
        return True
    return False


@lru_cache(maxsize=2048)
def _is_candidate_word(text: str) -> bool:
    if not _is_word_like_component(text):
        return False
    snapshot = get_wordnet_snapshot(text)
    return bool(snapshot.get("entries", []))


def resolve_component_link(db: Session, component: dict) -> tuple[int | None, bool]:
    if _is_forced_morpheme_component(component):
        return None, False
    text = str(component.get("text", ""))
    normalized = text.strip().lower()
    if not normalized:
        return None, False
    linked_word_id = WordStore.find_linked_word_id(db, normalized)
    if linked_word_id is not None:
        return linked_word_id, True
    return None, _is_candidate_word(normalized)


def _normalize_branches(branches: object) -> list[dict]:
    if not isinstance(branches, list):
        return []
    normalized: list[dict] = []
    for branch in branches:
        if isinstance(branch, dict):
            item = dict(branch)
            item.setdefault("label", str(item.get("label", "")).strip())
            item.setdefault("meaning_ja", str(item.get("meaning_ja", "")).strip())
            item.setdefault("meaning_en", str(item.get("meaning_en", "")).strip())
            normalized.append(item)
            continue
        if isinstance(branch, str):
            text = branch.strip()
            if not text:
                continue
            normalized.append({"label": text, "meaning_ja": text, "meaning_en": ""})
    return normalized


def _normalized_component_text(text: str) -> str:
    return text.strip().lower()


def _resolve_component_cache_id(db: Session, component: EtymologyComponentItemCreate) -> int | None:
    if component.component_id:
        exists = db.get(EtymologyComponent, component.component_id)
        if exists:
            return component.component_id
    normalized = _normalized_component_text(component.text)
    if not normalized:
        return None
    stmt = select(EtymologyComponent.id).where(func.lower(EtymologyComponent.component_text) == normalized)
    return db.scalar(stmt)


def _component_item_to_dict(db: Session, item: EtymologyComponentItem) -> dict:
    result = {
        "text": item.component_text,
        "meaning": item.meaning or "",
        "type": item.type or "root",
        "sort_order": item.sort_order or 0,
    }
    linked_word_id, candidate_word = resolve_component_link(db, result)
    auto_modes = ["word", "morpheme"] if candidate_word else ["morpheme"]
    result["linked_word_id"] = linked_word_id
    result["candidate_word"] = candidate_word
    result["auto_modes"] = auto_modes
    result["display_mode"] = "auto"
    return result


def _apply_etymology_components(db: Session, etymology: Etymology, components: list[EtymologyComponentItemCreate]) -> None:
    etymology.component_items.clear()
    for idx, comp in enumerate(components):
        raw = comp.text.strip()
        if not raw:
            continue
        text = normalize_component_text(raw)
        if text is None or not text.strip():
            continue
        text = text.strip()
        etymology.component_items.append(
            EtymologyComponentItem(
                sort_order=comp.sort_order if comp.sort_order is not None else idx,
                component_text=text,
                meaning=(comp.meaning or "").strip(),
                type=(comp.type or "root").strip() or "root",
                component_id=_resolve_component_cache_id(db, comp),
            )
        )


def _attr(obj: object, key: str, default: str = "") -> str:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _apply_etymology_branches(etymology: Etymology, branches: list) -> None:
    etymology.branches.clear()
    for idx, b in enumerate(branches):
        label = str(_attr(b, "label")).strip()
        if not label:
            continue
        meaning_en = str(_attr(b, "meaning_en") or "").strip() or None
        meaning_ja = str(_attr(b, "meaning_ja") or "").strip() or None
        etymology.branches.append(
            EtymologyBranch(sort_order=idx, label=label, meaning_en=meaning_en, meaning_ja=meaning_ja)
        )


def _apply_etymology_component_meanings(etymology: Etymology, items: list, variant_id: int | None = None) -> None:
    target = etymology.component_meanings if variant_id is None else None
    if variant_id is not None:
        variant = next((v for v in etymology.variants if v.id == variant_id), None)
        target = variant.component_meanings if variant else []
    if target is None:
        return
    target.clear()
    for idx, item in enumerate(items):
        text = str(_attr(item, "text")).strip()
        meaning = str(_attr(item, "meaning")).strip()
        if not text:
            continue
        target.append(
            EtymologyComponentMeaning(
                etymology_id=etymology.id,
                variant_id=variant_id,
                sort_order=idx,
                component_text=text,
                meaning=meaning,
            )
        )


def _apply_etymology_variants(db: Session, etymology: Etymology, variants: list) -> None:
    etymology.variants.clear()
    for idx, v in enumerate(variants):
        label = str(_attr(v, "label") or "").strip() or None
        excerpt = str(_attr(v, "excerpt") or "").strip() or None
        variant = EtymologyVariant(
            etymology_id=etymology.id,
            sort_order=idx,
            label=label,
            excerpt=excerpt,
        )
        etymology.variants.append(variant)
        db.flush()
        components = _attr(v, "components", []) or []
        component_meanings = _attr(v, "component_meanings", []) or []
        language_chain = _attr(v, "language_chain", []) or []
        for cidx, comp in enumerate(components):
            raw = str(_attr(comp, "text")).strip()
            if not raw:
                continue
            text = normalize_component_text(raw)
            if text is None or not text.strip():
                continue
            text = text.strip()
            comp_create = comp if hasattr(comp, "model_dump") else EtymologyComponentItemCreate.model_validate(comp)
            variant.component_items.append(
                EtymologyComponentItem(
                    etymology_id=etymology.id,
                    variant_id=variant.id,
                    sort_order=cidx,
                    component_text=text,
                    meaning=str(_attr(comp, "meaning") or "").strip(),
                    type=str(_attr(comp, "type", "root") or "root").strip() or "root",
                    component_id=_resolve_component_cache_id(db, comp_create),
                )
            )
        for cmidx, cm in enumerate(component_meanings):
            ctext = str(_attr(cm, "text")).strip()
            cmeaning = str(_attr(cm, "meaning")).strip()
            if not ctext:
                continue
            variant.component_meanings.append(
                EtymologyComponentMeaning(
                    etymology_id=etymology.id,
                    variant_id=variant.id,
                    sort_order=cmidx,
                    component_text=ctext,
                    meaning=cmeaning,
                )
            )
        for lcidx, link in enumerate(language_chain):
            lang = str(_attr(link, "lang")).strip()
            word = str(_attr(link, "word")).strip()
            if not lang or not word:
                continue
            lang_name = str(_attr(link, "lang_name") or "").strip() or None
            relation = str(_attr(link, "relation") or "").strip() or None
            variant.language_chain_links.append(
                EtymologyLanguageChainLink(
                    etymology_id=etymology.id,
                    variant_id=variant.id,
                    sort_order=lcidx,
                    lang=lang,
                    lang_name=lang_name,
                    word=word,
                    relation=relation,
                )
            )


def apply_etymology_update(db: Session, etymology: Etymology, payload: dict) -> None:
    parsed = EtymologyUpdate.model_validate(payload)
    etymology.origin_word = parsed.origin_word
    etymology.origin_language = parsed.origin_language
    etymology.core_image = parsed.core_image
    etymology.raw_description = parsed.raw_description
    _apply_etymology_components(db, etymology, parsed.components)
    _apply_etymology_branches(etymology, parsed.branches)
    etymology.language_chain_links.clear()
    for idx, link in enumerate(parsed.language_chain):
        if not link.lang.strip() or not link.word.strip():
            continue
        etymology.language_chain_links.append(
            EtymologyLanguageChainLink(
                etymology_id=etymology.id,
                variant_id=None,
                sort_order=idx,
                lang=link.lang.strip(),
                lang_name=link.lang_name.strip() if link.lang_name else None,
                word=link.word.strip(),
                relation=link.relation.strip() if link.relation else None,
            )
        )
    _apply_etymology_component_meanings(etymology, parsed.component_meanings, variant_id=None)
    _apply_etymology_variants(db, etymology, parsed.etymology_variants)


def build_etymology_enrich_payload(etymology: Etymology | None) -> dict:
    """Build etymology dict for enrich_core_image_and_branches API."""
    if not etymology:
        return {
            "core_image": "",
            "branches": [],
            "raw_description": "",
            "components": [],
            "language_chain": [],
            "component_meanings": [],
            "etymology_variants": [],
            "origin_word": None,
            "origin_language": None,
        }
    branches = [
        {"label": b.label, "meaning_en": b.meaning_en, "meaning_ja": b.meaning_ja}
        for b in sorted(etymology.branches, key=lambda x: (x.sort_order, x.id))
    ]
    language_chain = [
        {"lang": l.lang, "lang_name": l.lang_name, "word": l.word, "relation": l.relation}
        for l in sorted(etymology.language_chain_links, key=lambda x: (x.sort_order, x.id))
    ]
    component_meanings = [
        {"text": m.component_text, "meaning": m.meaning}
        for m in sorted(etymology.component_meanings, key=lambda x: (x.sort_order, x.id))
    ]
    etymology_variants = []
    for v in sorted(etymology.variants, key=lambda x: (x.sort_order, x.id)):
        var_components = [
            {"text": i.component_text, "meaning": i.meaning, "type": i.type}
            for i in sorted(v.component_items, key=lambda x: (x.sort_order, x.id))
        ]
        var_component_meanings = [
            {"text": m.component_text, "meaning": m.meaning}
            for m in sorted(v.component_meanings, key=lambda x: (x.sort_order, x.id))
        ]
        var_language_chain = [
            {"lang": l.lang, "lang_name": l.lang_name, "word": l.word, "relation": l.relation}
            for l in sorted(v.language_chain_links, key=lambda x: (x.sort_order, x.id))
        ]
        etymology_variants.append({
            "label": v.label,
            "excerpt": v.excerpt,
            "components": var_components,
            "component_meanings": var_component_meanings,
            "language_chain": var_language_chain,
        })
    return {
        "core_image": etymology.core_image or "",
        "branches": branches,
        "raw_description": etymology.raw_description or "",
        "components": [
            {"text": i.component_text, "meaning": i.meaning, "type": i.type}
            for i in sorted(etymology.component_items, key=lambda x: (x.sort_order, x.id))
        ],
        "language_chain": language_chain,
        "component_meanings": component_meanings,
        "etymology_variants": etymology_variants,
        "origin_word": etymology.origin_word,
        "origin_language": etymology.origin_language,
    }


def _build_etymology_read(db: Session, etymology: Etymology) -> dict:
    component_items = sorted(etymology.component_items, key=lambda x: (x.sort_order, x.id))
    out_components = []
    for item in component_items:
        norm_text = normalize_component_text(item.component_text)
        if norm_text is None:
            continue
        d = _component_item_to_dict(db, item)
        d["text"] = norm_text
        out_components.append(d)
    branches = [
        {"label": b.label, "meaning_en": b.meaning_en, "meaning_ja": b.meaning_ja}
        for b in sorted(etymology.branches, key=lambda x: (x.sort_order, x.id))
    ]
    language_chain = [
        {"lang": l.lang, "lang_name": l.lang_name, "word": l.word, "relation": l.relation}
        for l in sorted(etymology.language_chain_links, key=lambda x: (x.sort_order, x.id))
    ]
    component_meanings = [
        {"text": m.component_text, "meaning": m.meaning}
        for m in sorted(etymology.component_meanings, key=lambda x: (x.sort_order, x.id))
    ]
    etymology_variants = []
    for v in sorted(etymology.variants, key=lambda x: (x.sort_order, x.id)):
        var_components = []
        for item in sorted(v.component_items, key=lambda x: (x.sort_order, x.id)):
            norm_text = normalize_component_text(item.component_text)
            if norm_text is None:
                continue
            d = _component_item_to_dict(db, item)
            d["text"] = norm_text
            var_components.append(d)
        var_component_meanings = [
            {"text": m.component_text, "meaning": m.meaning}
            for m in sorted(v.component_meanings, key=lambda x: (x.sort_order, x.id))
        ]
        var_language_chain = [
            {"lang": l.lang, "lang_name": l.lang_name, "word": l.word, "relation": l.relation}
            for l in sorted(v.language_chain_links, key=lambda x: (x.sort_order, x.id))
        ]
        etymology_variants.append({
            "label": v.label,
            "excerpt": v.excerpt,
            "components": var_components,
            "component_meanings": var_component_meanings,
            "language_chain": var_language_chain,
        })
    return {
        "id": etymology.id,
        "components": out_components,
        "origin_word": etymology.origin_word,
        "origin_language": etymology.origin_language,
        "core_image": etymology.core_image,
        "branches": branches,
        "language_chain": language_chain,
        "component_meanings": component_meanings,
        "etymology_variants": etymology_variants,
        "raw_description": etymology.raw_description,
    }


def _extract_phrase_entries(payload: dict) -> list[dict[str, str]]:
    explicit = payload.get("phrases")
    entries: list[dict[str, str]] = []
    if isinstance(explicit, list):
        for item in explicit:
            if not isinstance(item, dict):
                continue
            text = normalize_phrase_text(str(item.get("text", item.get("phrase", ""))))
            if not text:
                continue
            meaning = str(item.get("meaning", "")).strip()
            entries.append({"text": text, "meaning": meaning})
        if entries:
            return entries

    forms = payload.get("forms")
    if not isinstance(forms, dict):
        return []
    raw_phrases = forms.get("phrases")
    if not isinstance(raw_phrases, list):
        return []
    for item in raw_phrases:
        if isinstance(item, str):
            text = normalize_phrase_text(item)
            if text:
                entries.append({"text": text, "meaning": ""})
            continue
        if not isinstance(item, dict):
            continue
        text = normalize_phrase_text(str(item.get("phrase", item.get("text", ""))))
        if not text:
            continue
        meaning = str(item.get("meaning", item.get("meaning_en", item.get("meaning_ja", "")))).strip()
        entries.append({"text": text, "meaning": meaning})
    return entries


def replace_word_phrases(db: Session, word: Word, phrase_entries: list[dict[str, str]]) -> None:
    word.phrase_links.clear()
    db.flush()
    for entry in phrase_entries:
        text = normalize_phrase_text(entry.get("text", ""))
        if not text:
            continue
        phrase = get_or_create_phrase(db, text, entry.get("meaning", ""))
        link_phrase_to_word(db, word, phrase)
    db.flush()


def to_word_read(db: Session, word: Word) -> WordRead:
    definitions = []
    for d in word.definitions:
        item = DefinitionRead.model_validate(d).model_dump()
        item["part_of_speech"] = normalize_part_of_speech(item.get("part_of_speech"))
        definitions.append(item)

    derivations = []
    for drv in word.derivations:
        item = DerivationRead.model_validate(drv).model_dump()
        item["part_of_speech"] = normalize_part_of_speech(item.get("part_of_speech"))
        derivations.append(item)

    forms_data = dict(word.forms or {})
    forms_data.pop("phrases", None)
    phrases_data = [
        {
            "id": phrase.id,
            "text": phrase.text,
            "meaning": phrase.meaning or "",
            "created_at": phrase.created_at,
            "updated_at": phrase.updated_at,
        }
        for phrase in sorted(word.phrases, key=lambda item: (item.text.lower(), item.id))
    ]
    lemma_word_text = None
    if word.lemma_ref is not None:
        lemma_word_text = word.lemma_ref.word
    elif word.lemma_word_id is not None:
        lemma_word = db.get(Word, word.lemma_word_id)
        lemma_word_text = lemma_word.word if lemma_word else None
    inflected_forms_rows = db.execute(
        select(Word.id, Word.word, Word.inflection_type).where(Word.lemma_word_id == word.id).order_by(Word.word.asc())
    ).all()
    inflected_forms = [
        {"word_id": int(row[0]), "word": str(row[1]), "inflection_type": row[2]}
        for row in inflected_forms_rows
    ]

    data: dict = {
        "id": word.id,
        "word": word.word,
        "phonetic": word.phonetic,
        "forms": forms_data,
        "created_at": word.created_at,
        "updated_at": word.updated_at,
        "last_viewed_at": word.last_viewed_at,
        "definitions": definitions,
        "etymology": _build_etymology_read(db, word.etymology) if word.etymology else None,
        "derivations": derivations,
        "related_words": [RelatedWordRead.model_validate(r).model_dump() for r in word.related_words],
        "phrases": phrases_data,
        "images": [WordImageRead.model_validate(i).model_dump() for i in word.images],
        "chat_session_count": len(word.chat_sessions),
        "lemma_word_id": word.lemma_word_id,
        "inflection_type": word.inflection_type,
        "lemma_word_text": lemma_word_text,
        "inflected_forms": inflected_forms,
    }
    return WordRead.model_validate(data)


def apply_structured_payload(db: Session, word: Word, payload: dict) -> None:
    if isinstance(payload, dict):
        etymology_payload = payload.get("etymology", {})
        if isinstance(etymology_payload, dict):
            raw_branches = etymology_payload.get("branches", [])
            normalized_branches = _normalize_branches(raw_branches)
            if normalized_branches != raw_branches:
                patched_etymology = dict(etymology_payload)
                patched_etymology["branches"] = normalized_branches
                payload = dict(payload)
                payload["etymology"] = patched_etymology
    phrase_entries = _extract_phrase_entries(payload)
    parsed = StructuredWordPayload.model_validate(payload)
    word.phonetic = parsed.phonetic
    forms = dict(parsed.forms or {})
    forms.pop("phrases", None)
    word.forms = forms

    word.definitions.clear()
    for d in parsed.definitions:
        word.definitions.append(
            Definition(
                part_of_speech=normalize_part_of_speech(d.part_of_speech),
                meaning_en=d.meaning_en,
                meaning_ja=d.meaning_ja,
                example_en=d.example_en,
                example_ja=d.example_ja,
                sort_order=d.sort_order,
            )
        )

    if not word.etymology:
        word.etymology = Etymology()
    ety = parsed.etymology.model_dump()
    apply_etymology_update(db, word.etymology, ety)

    word.derivations.clear()
    for d in parsed.derivations:
        word.derivations.append(
            Derivation(
                derived_word=d.derived_word,
                part_of_speech=normalize_part_of_speech(d.part_of_speech),
                meaning_ja=d.meaning_ja,
                sort_order=d.sort_order,
            )
        )
    db.flush()
    link_derivations(db, word)

    word.related_words.clear()
    for r in parsed.related_words:
        word.related_words.append(
            RelatedWord(
                related_word=r.related_word,
                relation_type=r.relation_type,
                note=r.note,
            )
        )
    db.flush()
    link_related_words(db, word)
    replace_word_phrases(db, word, phrase_entries)


def replace_definitions(word: Word, definitions: list[dict]) -> None:
    word.definitions.clear()
    for d in definitions:
        word.definitions.append(
            Definition(
                part_of_speech=normalize_part_of_speech(d.get("part_of_speech", "noun")),
                meaning_en=d.get("meaning_en", ""),
                meaning_ja=d.get("meaning_ja", ""),
                example_en=d.get("example_en", ""),
                example_ja=d.get("example_ja", ""),
                sort_order=d.get("sort_order", 0),
            )
        )


def split_comma_items(text: str) -> list[str]:
    parts = [part.strip() for part in str(text).split(",")]
    unique: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(part)
    return unique


def replace_derivations(db: Session, word: Word, derivations: list[dict]) -> None:
    word.derivations.clear()
    for d in derivations:
        split_words = split_comma_items(d.get("derived_word", ""))
        if not split_words:
            continue
        for derived_word in split_words:
            word.derivations.append(
                Derivation(
                    derived_word=derived_word,
                    part_of_speech=normalize_part_of_speech(d.get("part_of_speech", "noun")),
                    meaning_ja=d.get("meaning_ja", ""),
                    sort_order=d.get("sort_order", 0),
                )
            )
    db.flush()
    link_derivations(db, word)


def replace_related_words(db: Session, word: Word, related_words: list[dict]) -> None:
    word.related_words.clear()
    for r in related_words:
        split_words = split_comma_items(r.get("related_word", ""))
        if not split_words:
            continue
        for related_word in split_words:
            word.related_words.append(
                RelatedWord(
                    related_word=related_word,
                    relation_type=r.get("relation_type", "synonym"),
                    note=r.get("note", ""),
                )
            )
    db.flush()
    link_related_words(db, word)


def link_related_words(db: Session, word: Word) -> None:
    for rel in word.related_words:
        rel.linked_word_id = WordStore.find_linked_word_id(db, rel.related_word)


def link_derivations(db: Session, word: Word) -> None:
    for drv in word.derivations:
        drv.linked_word_id = WordStore.find_linked_word_id(db, drv.derived_word)


def has_etymology_component(word: Word, component_text: str) -> bool:
    etymology = word.etymology
    if not etymology:
        return False
    target = component_text.strip().lower()
    if not target:
        return False
    for item in etymology.component_items:
        if item.component_text.strip().lower() == target:
            return True
    for item in etymology.component_meanings:
        if item.component_text.strip().lower() == target:
            return True
    for variant in etymology.variants:
        for item in variant.component_items:
            if item.component_text.strip().lower() == target:
                return True
        for item in variant.component_meanings:
            if item.component_text.strip().lower() == target:
                return True
    return False


def resolve_component_meaning(words: list[Word], component_text: str) -> str | None:
    target = component_text.strip().lower()
    if not target:
        return None
    generic = {"語源要素", "語根要素", "接頭要素"}

    def _check_etymology(etymology: Etymology) -> str | None:
        for item in etymology.component_meanings:
            if item.component_text.strip().lower() == target:
                meaning = (item.meaning or "").strip()
                if meaning and meaning not in generic:
                    return meaning
        for item in etymology.component_items:
            if item.component_text.strip().lower() == target:
                meaning = (item.meaning or "").strip()
                if meaning and meaning not in generic:
                    return meaning
        for variant in etymology.variants:
            for item in variant.component_meanings:
                if item.component_text.strip().lower() == target:
                    meaning = (item.meaning or "").strip()
                    if meaning and meaning not in generic:
                        return meaning
            for item in variant.component_items:
                if item.component_text.strip().lower() == target:
                    meaning = (item.meaning or "").strip()
                    if meaning and meaning not in generic:
                        return meaning
        return None

    for w in words:
        if not w.etymology:
            continue
        result = _check_etymology(w.etymology)
        if result:
            return result
    return None


def aggregate_related_words(words: list[Word]) -> list[dict]:
    buckets: dict[tuple[str, str], dict] = {}
    for word in words:
        for rel in word.related_words:
            name = rel.related_word.strip()
            if not name:
                continue
            key = (name.lower(), rel.relation_type)
            if key not in buckets:
                buckets[key] = {
                    "related_word": name,
                    "relation_type": rel.relation_type,
                    "note": rel.note or "",
                    "linked_word_id": rel.linked_word_id,
                    "count": 0,
                }
            entry = buckets[key]
            entry["count"] += 1
            if not entry["linked_word_id"] and rel.linked_word_id:
                entry["linked_word_id"] = rel.linked_word_id
            if len(rel.note or "") > len(entry["note"]):
                entry["note"] = rel.note
    return sorted(
        buckets.values(),
        key=lambda item: (-int(item["count"]), str(item["related_word"]).lower(), str(item["relation_type"])),
    )


def aggregate_derivations(words: list[Word]) -> list[dict]:
    buckets: dict[str, dict] = {}
    for word in words:
        for drv in word.derivations:
            name = drv.derived_word.strip()
            if not name:
                continue
            key = name.lower()
            if key not in buckets:
                buckets[key] = {
                    "derived_word": name,
                    "part_of_speech": drv.part_of_speech,
                    "meaning_ja": drv.meaning_ja or "",
                    "linked_word_id": drv.linked_word_id,
                    "count": 0,
                }
            entry = buckets[key]
            entry["count"] += 1
            if not entry["linked_word_id"] and drv.linked_word_id:
                entry["linked_word_id"] = drv.linked_word_id
            if not entry["meaning_ja"] and drv.meaning_ja:
                entry["meaning_ja"] = drv.meaning_ja
    return sorted(buckets.values(), key=lambda item: (-int(item["count"]), str(item["derived_word"]).lower()))
