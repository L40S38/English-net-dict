from __future__ import annotations

import json
import random
import re

from openai import OpenAI
from sqlalchemy.orm import Session

from core.config import settings
from core.models import ListeningLine, ListeningScript, ListeningSpeaker
from core.schemas import ListeningLineRead, ListeningScriptRead
from core.services.listening_session_service import get_voice_accuracy_weights, get_weak_word_stats
from core.utils.prompt_loader import load_prompt
from core.utils.text_repair import repair_nested_strings

_MALE_VOICES = ["echo", "onyx", "fable", "alloy"]
_FEMALE_VOICES = ["nova", "shimmer"]
_NEUTRAL_VOICES = ["alloy", "nova", "echo", "shimmer", "fable", "onyx"]

# A single ListeningLine should read as a comfortable dictation/shadowing chunk:
# long enough to be a real utterance, short enough to fit on one line of UI.
_MIN_LINE_LENGTH = 25
_MAX_LINE_LENGTH = 160
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


def _pick_voice(
    gender: str,
    used_voices: set[str],
    voice_weights: dict[str, float] | None = None,
) -> str:
    pool = {"male": _MALE_VOICES, "female": _FEMALE_VOICES}.get(gender, _NEUTRAL_VOICES)
    # Prefer a voice not already used by another speaker in this script, so two
    # same-gender speakers don't end up sounding identical; fall back to the
    # full pool once it's exhausted.
    candidates = [v for v in pool if v not in used_voices] or list(pool)
    if not voice_weights:
        return random.choice(candidates)
    weights = [voice_weights.get(v, 1.0) for v in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]


def _split_into_sentences(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    return [s.strip() for s in _SENTENCE_BOUNDARY_RE.split(stripped) if s.strip()]


def _split_line_text(text: str) -> list[str]:
    """Re-chunk a (possibly multi-sentence, possibly too-long) line at sentence
    boundaries so each resulting chunk stays within a comfortable length for one
    dictation/shadowing turn, never cutting a sentence in half."""
    sentences = _split_into_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = [sentences[0]]
    for sentence in sentences[1:]:
        candidate = f"{chunks[-1]} {sentence}"
        if len(candidate) <= _MAX_LINE_LENGTH:
            chunks[-1] = candidate
        else:
            chunks.append(sentence)

    # Fold any leftover too-short chunk into a neighbor instead of leaving an
    # orphaned fragment (e.g. a trailing "Thanks!" split off on its own).
    changed = True
    while changed and len(chunks) > 1:
        changed = False
        for i, chunk in enumerate(chunks):
            if len(chunk) >= _MIN_LINE_LENGTH:
                continue
            if i > 0:
                chunks[i - 1] = f"{chunks[i - 1]} {chunk}"
            else:
                chunks[1] = f"{chunk} {chunks[1]}"
            del chunks[i]
            changed = True
            break
    return chunks


def _strip_json_code_fence(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```json"):
        value = value[len("```json") :].strip()
    elif value.startswith("```"):
        value = value[len("```") :].strip()
    if value.endswith("```"):
        value = value[:-3].strip()
    return value


def _call_llm(prompt: str, payload: dict, *, temperature: float) -> dict:
    if not settings.openai_api_key:
        raise RuntimeError("OpenAI API key is not configured")
    client = OpenAI(api_key=settings.openai_api_key)
    completion = client.responses.create(
        model=settings.openai_model_structured,
        temperature=temperature,
        input=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    )
    text = _strip_json_code_fence(completion.output_text or "")
    data = repair_nested_strings(json.loads(text))
    if not isinstance(data, dict):
        raise ValueError("LLM response was not a JSON object")
    return data


def _build_script_from_llm_payload(
    db: Session,
    data: dict,
    *,
    topic: str | None,
    level: str | None,
    is_conversation: bool,
    generation_mode: str,
    preferred_voices: list[str | None] | None = None,
    voice_weights: dict[str, float] | None = None,
) -> ListeningScript:
    speakers = data.get("speakers")
    lines = data.get("lines")
    if not isinstance(speakers, list) or not speakers:
        raise ValueError("LLM response did not include any speakers")
    if not isinstance(lines, list) or not lines:
        raise ValueError("LLM response did not include any lines")

    declared_labels = {str(sp.get("label", "")).strip() for sp in speakers if isinstance(sp, dict)}
    declared_labels.discard("")
    for line in lines:
        label = str(line.get("speaker_label", "")).strip() if isinstance(line, dict) else ""
        if label not in declared_labels:
            raise ValueError(f"Line references undeclared speaker '{label}'")

    title = str(data.get("title", "")).strip() or (topic or "Listening Practice")
    script = ListeningScript(
        title=title,
        topic=topic,
        level=level,
        is_conversation=is_conversation,
        generation_mode=generation_mode,
        source_type="ai_generated",
    )
    db.add(script)
    db.flush()

    label_to_speaker: dict[str, ListeningSpeaker] = {}
    used_voices: set[str] = set()
    for idx, sp in enumerate(speakers):
        label = str(sp.get("label", "")).strip()
        gender = str(sp.get("gender", "neutral")).strip().lower()
        if gender not in ("male", "female", "neutral"):
            gender = "neutral"
        preferred = preferred_voices[idx] if preferred_voices and idx < len(preferred_voices) else None
        voice = preferred or _pick_voice(gender, used_voices, voice_weights)
        used_voices.add(voice)
        speaker = ListeningSpeaker(
            script_id=script.id,
            label=label,
            voice=voice,
            sort_order=idx,
        )
        db.add(speaker)
        label_to_speaker[label] = speaker
    db.flush()

    sort_order = 0
    for line in lines:
        label = str(line.get("speaker_label", "")).strip()
        speaker = label_to_speaker[label]
        translation = str(line.get("translation_ja", "")).strip() or None
        chunks = _split_line_text(str(line.get("text", "")))
        for chunk_idx, chunk_text in enumerate(chunks):
            db.add(
                ListeningLine(
                    script_id=script.id,
                    speaker_id=speaker.id,
                    sort_order=sort_order,
                    text=chunk_text,
                    # A multi-sentence line that got split has only one translation
                    # from the LLM; attach it to the first chunk rather than guess
                    # how to divide it.
                    translation_ja=translation if chunk_idx == 0 else None,
                )
            )
            sort_order += 1
    db.flush()
    return script


def generate_random_script(
    db: Session,
    *,
    topic: str | None = None,
    level: str | None = None,
    speaker_count: int = 1,
    is_conversation: bool = False,
    voices: list[str | None] | None = None,
) -> ListeningScript:
    prompt = load_prompt("listening_script_generation.md")
    payload = {
        "topic": topic,
        "level": level,
        "speaker_count": speaker_count,
        "is_conversation": is_conversation,
        "weak_words": [],
    }
    data = _call_llm(prompt, payload, temperature=0.8)
    voice_weights = get_voice_accuracy_weights(db)
    return _build_script_from_llm_payload(
        db,
        data,
        topic=topic,
        level=level,
        is_conversation=is_conversation,
        generation_mode="random",
        preferred_voices=voices,
        voice_weights=voice_weights,
    )


def generate_weak_review_script(
    db: Session,
    *,
    level: str | None = None,
    speaker_count: int = 1,
    is_conversation: bool = False,
    limit: int = 10,
    voices: list[str | None] | None = None,
) -> ListeningScript:
    weak_words = [stat["word_text"] for stat in get_weak_word_stats(db, limit=limit)]
    if not weak_words:
        raise ValueError("No weak-word history yet")

    prompt = load_prompt("listening_script_generation.md")
    payload = {
        "topic": None,
        "level": level,
        "speaker_count": speaker_count,
        "is_conversation": is_conversation,
        "weak_words": weak_words,
    }
    data = _call_llm(prompt, payload, temperature=0.8)
    return _build_script_from_llm_payload(
        db,
        data,
        topic="Weak-word review",
        level=level,
        is_conversation=is_conversation,
        generation_mode="weak_review",
        preferred_voices=voices,
    )


def analyze_custom_script(raw_text: str) -> dict:
    text = raw_text.strip()
    if not text:
        raise ValueError("Text is empty")

    prompt = load_prompt("listening_script_segmentation.md")
    return _call_llm(prompt, {"raw_text": text}, temperature=0.0)


def build_custom_script(
    db: Session,
    parsed: dict,
    voices: list[str | None] | None = None,
) -> ListeningScript:
    is_conversation = len(parsed.get("speakers") or []) > 1
    return _build_script_from_llm_payload(
        db,
        parsed,
        topic=None,
        level=None,
        is_conversation=is_conversation,
        generation_mode="custom",
        preferred_voices=voices,
    )


def to_script_read(script: ListeningScript) -> ListeningScriptRead:
    data = {
        "id": script.id,
        "title": script.title,
        "topic": script.topic,
        "level": script.level,
        "is_conversation": script.is_conversation,
        "generation_mode": script.generation_mode,
        "source_type": script.source_type,
        "source_url": script.source_url,
        "created_at": script.created_at,
        "updated_at": script.updated_at,
        "speakers": [
            {"id": sp.id, "label": sp.label, "voice": sp.voice, "sort_order": sp.sort_order}
            for sp in sorted(script.speakers, key=lambda s: (s.sort_order, s.id))
        ],
        "lines": [
            {
                "id": ln.id,
                "speaker_id": ln.speaker_id,
                "speaker_label": ln.speaker_ref.label if ln.speaker_ref else "",
                "sort_order": ln.sort_order,
                "text": ln.text,
                "translation_ja": ln.translation_ja,
                "audio_variants": [
                    {
                        "id": av.id,
                        "voice": av.voice,
                        "audio_path": av.audio_path,
                        "is_primary": av.is_primary,
                        "created_at": av.created_at,
                    }
                    for av in ln.audio_variants
                ],
            }
            for ln in sorted(script.lines, key=lambda item: (item.sort_order, item.id))
        ],
    }
    return ListeningScriptRead.model_validate(data)


def to_line_read(line: ListeningLine) -> ListeningLineRead:
    data = {
        "id": line.id,
        "speaker_id": line.speaker_id,
        "speaker_label": line.speaker_ref.label if line.speaker_ref else "",
        "sort_order": line.sort_order,
        "text": line.text,
        "translation_ja": line.translation_ja,
        "audio_variants": [
            {
                "id": av.id,
                "voice": av.voice,
                "audio_path": av.audio_path,
                "is_primary": av.is_primary,
                "created_at": av.created_at,
            }
            for av in line.audio_variants
        ],
    }
    return ListeningLineRead.model_validate(data)
