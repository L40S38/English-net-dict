from __future__ import annotations

from sqlalchemy.orm import Session

from core.models import (
    ChatSession,
    Definition,
    DefinitionExample,
    Derivation,
    RelatedWord,
    Word,
    WordImage,
    WordPhrase,
)
from core.services.word_service import link_derivations, link_related_words


def _definition_key(item: Definition) -> tuple[str, str, str]:
    return (
        (item.part_of_speech or "").strip().lower(),
        (item.meaning_en or "").strip().lower(),
        (item.meaning_ja or "").strip().lower(),
    )


def _derivation_key(item: Derivation) -> tuple[str, str, str]:
    return (
        (item.derived_word or "").strip().lower(),
        (item.part_of_speech or "").strip().lower(),
        (item.meaning_ja or "").strip().lower(),
    )


def _related_key(item: RelatedWord) -> tuple[str, str, str]:
    return (
        (item.related_word or "").strip().lower(),
        (item.relation_type or "").strip().lower(),
        (item.note or "").strip().lower(),
    )


def merge_into_lemma(db: Session, inflected: Word, lemma: Word) -> None:
    if inflected.id == lemma.id:
        return

    existing_def_keys = {_definition_key(item) for item in lemma.definitions}
    for item in list(inflected.definitions):
        if _definition_key(item) in existing_def_keys:
            continue
        lemma.definitions.append(
            Definition(
                part_of_speech=item.part_of_speech,
                meaning_en=item.meaning_en,
                meaning_ja=item.meaning_ja,
                sort_order=item.sort_order,
                examples=[
                    DefinitionExample(
                        example_en=ex.example_en,
                        example_ja=ex.example_ja,
                        sort_order=ex.sort_order,
                    )
                    for ex in item.examples
                ],
            )
        )
        existing_def_keys.add(_definition_key(item))

    existing_drv_keys = {_derivation_key(item) for item in lemma.derivations}
    for item in list(inflected.derivations):
        if _derivation_key(item) in existing_drv_keys:
            continue
        lemma.derivations.append(
            Derivation(
                derived_word=item.derived_word,
                part_of_speech=item.part_of_speech,
                meaning_ja=item.meaning_ja,
                sort_order=item.sort_order,
            )
        )
        existing_drv_keys.add(_derivation_key(item))

    existing_rel_keys = {_related_key(item) for item in lemma.related_words}
    for item in list(inflected.related_words):
        if _related_key(item) in existing_rel_keys:
            continue
        lemma.related_words.append(
            RelatedWord(
                related_word=item.related_word,
                relation_type=item.relation_type,
                note=item.note,
            )
        )
        existing_rel_keys.add(_related_key(item))

    phrase_ids = {link.phrase_id for link in lemma.phrase_links}
    for link in list(inflected.phrase_links):
        if link.phrase_id in phrase_ids:
            continue
        db.add(WordPhrase(word_id=lemma.id, phrase_id=link.phrase_id))
        phrase_ids.add(link.phrase_id)

    # Only one image per word should be active at a time (see image_service's
    # "deactivate existing, then add new" pattern); copying inflected's images
    # verbatim could give lemma a second active image if both already have one.
    lemma_has_active_image = any(image.is_active for image in lemma.images)
    for image in list(inflected.images):
        is_active = image.is_active and not lemma_has_active_image
        if is_active:
            lemma_has_active_image = True
        lemma.images.append(
            WordImage(
                file_path=image.file_path,
                prompt=image.prompt,
                is_active=is_active,
                created_at=image.created_at,
            )
        )

    sessions = list(db.query(ChatSession).filter(ChatSession.word_id == inflected.id))
    for session in sessions:
        session.word_id = lemma.id

    link_derivations(db, lemma)
    link_related_words(db, lemma)
    db.flush()
    db.delete(inflected)


def link_to_lemma(db: Session, inflected: Word, lemma: Word, inflection_type: str) -> None:
    if inflected.id == lemma.id:
        return
    inflected.lemma_word_id = lemma.id
    inflected.inflection_type = inflection_type.strip() if inflection_type else "inflection"
    db.flush()
