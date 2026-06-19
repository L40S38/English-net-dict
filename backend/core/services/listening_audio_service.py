from __future__ import annotations

from sqlalchemy.orm import Session

from core.models import ListeningLine, ListeningLineAudio
from core.services.tts_service import synthesize_speech


def generate_line_audio(
    db: Session,
    line: ListeningLine,
    voice: str | None = None,
    set_primary: bool = True,
) -> ListeningLineAudio:
    resolved_voice = voice or line.speaker_ref.voice
    audio_path = synthesize_speech(line.text, f"listening-line-{line.id}", voice=resolved_voice)

    is_first = len(line.audio_variants) == 0
    make_primary = set_primary or is_first
    if make_primary:
        for variant in line.audio_variants:
            variant.is_primary = False

    audio = ListeningLineAudio(
        line_id=line.id,
        voice=resolved_voice,
        audio_path=audio_path,
        is_primary=make_primary,
    )
    db.add(audio)
    db.flush()
    return audio
