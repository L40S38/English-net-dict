from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from core.database import get_db
from core.models import ListeningLine, ListeningScript, ListeningSession
from core.schemas import (
    ListeningAttemptCreate,
    ListeningAttemptRead,
    ListeningCustomScriptRequest,
    ListeningGenerateLineAudioRequest,
    ListeningLineAudioRead,
    ListeningLineRead,
    ListeningRandomScriptRequest,
    ListeningScriptRead,
    ListeningSessionCreate,
    ListeningSessionRead,
    ListeningSessionUpdate,
    ListeningWeakReviewRequest,
    WeakWordStat,
)
from core.services.listening_audio_service import generate_line_audio
from core.services.listening_script_service import (
    create_custom_script,
    generate_random_script,
    generate_weak_review_script,
    to_line_read,
    to_script_read,
)
from core.services.listening_session_service import (
    create_session,
    get_weak_word_stats,
    list_sessions,
    record_attempt,
    update_session,
)

router = APIRouter(prefix="/api/listening", tags=["listening"])


def _script_query():
    return select(ListeningScript).options(
        selectinload(ListeningScript.speakers),
        selectinload(ListeningScript.lines).joinedload(ListeningLine.speaker_ref),
        selectinload(ListeningScript.lines).selectinload(ListeningLine.audio_variants),
    )


def _line_query():
    return select(ListeningLine).options(
        joinedload(ListeningLine.speaker_ref),
        selectinload(ListeningLine.audio_variants),
    )


def _session_to_read(session: ListeningSession) -> ListeningSessionRead:
    data = {
        "id": session.id,
        "script_id": session.script_id,
        "script_title": session.script_ref.title if session.script_ref else "",
        "current_step": session.current_step,
        "playback_speed": session.playback_speed,
        "dictation_level": session.dictation_level,
        "status": session.status,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "completed_at": session.completed_at,
    }
    return ListeningSessionRead.model_validate(data)


@router.post("/scripts/random", response_model=ListeningScriptRead)
def post_random_script(
    payload: ListeningRandomScriptRequest, db: Session = Depends(get_db)
) -> ListeningScriptRead:
    try:
        script = generate_random_script(
            db,
            topic=payload.topic,
            level=payload.level,
            speaker_count=payload.speaker_count,
            is_conversation=payload.is_conversation,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.commit()
    refreshed = db.scalar(_script_query().where(ListeningScript.id == script.id))
    return to_script_read(refreshed)


@router.post("/scripts/custom", response_model=ListeningScriptRead)
def post_custom_script(
    payload: ListeningCustomScriptRequest, db: Session = Depends(get_db)
) -> ListeningScriptRead:
    try:
        script = create_custom_script(db, payload.raw_text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.commit()
    refreshed = db.scalar(_script_query().where(ListeningScript.id == script.id))
    return to_script_read(refreshed)


@router.post("/scripts/weak-review", response_model=ListeningScriptRead)
def post_weak_review_script(
    payload: ListeningWeakReviewRequest, db: Session = Depends(get_db)
) -> ListeningScriptRead:
    try:
        script = generate_weak_review_script(
            db,
            level=payload.level,
            speaker_count=payload.speaker_count,
            is_conversation=payload.is_conversation,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.commit()
    refreshed = db.scalar(_script_query().where(ListeningScript.id == script.id))
    return to_script_read(refreshed)


@router.get("/scripts/{script_id}", response_model=ListeningScriptRead)
def get_script(script_id: int, db: Session = Depends(get_db)) -> ListeningScriptRead:
    script = db.scalar(_script_query().where(ListeningScript.id == script_id))
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    return to_script_read(script)


@router.post("/lines/{line_id}/generate-audio", response_model=ListeningLineRead)
def post_line_audio(
    line_id: int,
    payload: ListeningGenerateLineAudioRequest,
    db: Session = Depends(get_db),
) -> ListeningLineRead:
    line = db.scalar(_line_query().where(ListeningLine.id == line_id))
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    try:
        generate_line_audio(db, line, voice=payload.voice)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.commit()
    refreshed = db.scalar(_line_query().where(ListeningLine.id == line_id))
    return to_line_read(refreshed)


@router.get("/lines/{line_id}/audio-variants", response_model=list[ListeningLineAudioRead])
def get_line_audio_variants(line_id: int, db: Session = Depends(get_db)) -> list[ListeningLineAudioRead]:
    line = db.scalar(_line_query().where(ListeningLine.id == line_id))
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    return to_line_read(line).audio_variants


@router.post("/sessions", response_model=ListeningSessionRead)
def post_session(payload: ListeningSessionCreate, db: Session = Depends(get_db)) -> ListeningSessionRead:
    script = db.get(ListeningScript, payload.script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    session = create_session(db, script)
    db.commit()
    refreshed = db.scalar(
        select(ListeningSession)
        .options(joinedload(ListeningSession.script_ref))
        .where(ListeningSession.id == session.id)
    )
    return _session_to_read(refreshed)


@router.get("/sessions", response_model=list[ListeningSessionRead])
def get_sessions(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ListeningSessionRead]:
    sessions = list_sessions(db, status=status)
    return [_session_to_read(s) for s in sessions]


@router.get("/sessions/{session_id}", response_model=ListeningSessionRead)
def get_session(session_id: int, db: Session = Depends(get_db)) -> ListeningSessionRead:
    session = db.scalar(
        select(ListeningSession)
        .options(joinedload(ListeningSession.script_ref))
        .where(ListeningSession.id == session_id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_to_read(session)


@router.patch("/sessions/{session_id}", response_model=ListeningSessionRead)
def patch_session(
    session_id: int, payload: ListeningSessionUpdate, db: Session = Depends(get_db)
) -> ListeningSessionRead:
    session = db.scalar(
        select(ListeningSession)
        .options(joinedload(ListeningSession.script_ref))
        .where(ListeningSession.id == session_id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    update_session(
        db,
        session,
        current_step=payload.current_step,
        playback_speed=payload.playback_speed,
        dictation_level=payload.dictation_level,
        status=payload.status,
    )
    db.commit()
    db.refresh(session)
    return _session_to_read(session)


@router.post("/sessions/{session_id}/attempts", response_model=ListeningAttemptRead)
def post_attempt(
    session_id: int, payload: ListeningAttemptCreate, db: Session = Depends(get_db)
) -> ListeningAttemptRead:
    session = db.get(ListeningSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    line = db.get(ListeningLine, payload.line_id)
    if not line or line.script_id != session.script_id:
        raise HTTPException(status_code=404, detail="Line not found")
    attempt = record_attempt(db, session, line, payload.dictation_level, payload.user_text)
    db.commit()
    db.refresh(attempt)
    return ListeningAttemptRead.model_validate(attempt)


@router.get("/analytics/weak-words", response_model=list[WeakWordStat])
def get_weak_words(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[WeakWordStat]:
    stats = get_weak_word_stats(db, limit=limit)
    return [WeakWordStat.model_validate(item) for item in stats]
