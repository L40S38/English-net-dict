from __future__ import annotations

import base64
import uuid
from pathlib import Path

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Word, WordImage
from app.services.wordnet_service import get_wordnet_snapshot
from app.utils.prompt_loader import load_prompt


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _dedup_lines(lines: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for line in lines:
        text = line.strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(text)
    return unique


def _build_meaning_branches_summary(word: Word) -> str:
    ety = word.etymology
    branches: list[str] = []

    if ety:
        for branch in ety.branches:
            label = _clean_text(branch.label)
            meaning_ja = _clean_text(branch.meaning_ja)
            meaning_en = _clean_text(branch.meaning_en)
            if label and meaning_ja:
                branches.append(f"- {label}: {meaning_ja}")
            elif label and meaning_en:
                branches.append(f"- {label}: {meaning_en}")
            elif meaning_ja:
                branches.append(f"- {meaning_ja}")
            elif meaning_en:
                branches.append(f"- {meaning_en}")
    if branches:
        return "\n".join(_dedup_lines(branches))

    fallback_lines: list[str] = []

    # Structured definitions are usually generated from WordNet/Wiktionary and are the best fallback.
    for definition in word.definitions[:8]:
        pos = _clean_text(definition.part_of_speech)
        meaning_ja = _clean_text(definition.meaning_ja)
        meaning_en = _clean_text(definition.meaning_en)
        if pos and meaning_ja:
            fallback_lines.append(f"- [{pos}] {meaning_ja}")
        elif pos and meaning_en:
            fallback_lines.append(f"- [{pos}] {meaning_en}")
        elif meaning_ja:
            fallback_lines.append(f"- {meaning_ja}")
        elif meaning_en:
            fallback_lines.append(f"- {meaning_en}")

    # Use etymology-derived meanings (Wiktionary extraction) when available.
    if ety:
        for item in ety.component_meanings[:8]:
            text = _clean_text(item.component_text)
            meaning = _clean_text(item.meaning)
            if text and meaning:
                fallback_lines.append(f"- [component:{text}] {meaning}")
            elif meaning:
                fallback_lines.append(f"- {meaning}")

    if ety:
        for variant in ety.variants[:6]:
            for key in ("label", "excerpt"):
                val = getattr(variant, key, None)
                value = _clean_text(val)
                if value:
                    fallback_lines.append(f"- [variant] {value}")
                    break

    # Last resort: direct WordNet snapshot definitions.
    if not fallback_lines:
        try:
            snapshot = get_wordnet_snapshot(word.word)
        except Exception:  # noqa: BLE001
            snapshot = {}
        for entry in snapshot.get("entries", [])[:8]:
            if not isinstance(entry, dict):
                continue
            definition = _clean_text(entry.get("definition"))
            part_of_speech = _clean_text(entry.get("part_of_speech"))
            if part_of_speech and definition:
                fallback_lines.append(f"- [wordnet:{part_of_speech}] {definition}")
            elif definition:
                fallback_lines.append(f"- [wordnet] {definition}")

    deduped = _dedup_lines(fallback_lines)
    if deduped:
        return "\n".join(deduped)
    return "- (No branch data. Use core etymology and dictionary meanings for branch design.)"


def build_image_prompt(word: Word) -> str:
    template = load_prompt("image_generation.md")
    ety = word.etymology
    core_image = ety.core_image if ety and ety.core_image else f"Core image for {word.word}"
    ety_summary = ety.raw_description if ety and ety.raw_description else f"Etymology for {word.word}"
    branches_summary = _build_meaning_branches_summary(word)
    return template.format(
        word=word.word,
        core_image=core_image,
        etymology_summary=ety_summary,
        branches_summary=branches_summary,
    )


def _write_placeholder_png(path: Path) -> None:
    # 1x1 transparent PNG
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAusB9Y5R16QAAAAASUVORK5CYII="
    )
    path.write_bytes(png_data)


def generate_word_image(db: Session, word: Word, user_prompt: str | None) -> WordImage:
    image_dir = Path(settings.image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)
    prompt = user_prompt or build_image_prompt(word)
    filename = f"{word.word.lower()}-{uuid.uuid4().hex[:8]}.png"
    file_path = image_dir / filename

    if settings.openai_api_key:
        try:
            client = OpenAI(api_key=settings.openai_api_key)
            result = client.images.generate(
                model=settings.openai_image_model,
                prompt=prompt,
                size=settings.openai_image_size,
            )
            b64 = result.data[0].b64_json
            if b64:
                file_path.write_bytes(base64.b64decode(b64))
            else:
                _write_placeholder_png(file_path)
        except Exception:  # noqa: BLE001
            _write_placeholder_png(file_path)
    else:
        _write_placeholder_png(file_path)

    for img in word.images:
        img.is_active = False

    relative_path = f"images/{filename}"
    image = WordImage(word_id=word.id, file_path=relative_path, prompt=prompt, is_active=True)
    db.add(image)
    db.flush()
    return image

