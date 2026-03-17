from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChatSession, Word
from app.schemas import (
    ChatMessageCreate,
    ChatMessageRead,
    ChatReply,
    ChatSessionCreate,
    ChatSessionRead,
    ChatSessionUpdate,
)
from app.services.chat_service import (
    answer_in_session,
    auto_title_from_content,
    create_component_session,
    create_session,
    delete_session,
    list_component_sessions,
    list_messages,
    list_sessions,
    update_session_title,
)
from app.services.etymology_component_service import normalize_component_text

router = APIRouter(prefix="/api", tags=["chat"])


@router.get("/words/{word_id}/chat/sessions", response_model=list[ChatSessionRead])
def get_sessions(word_id: int, db: Session = Depends(get_db)) -> list[ChatSessionRead]:
    if not db.get(Word, word_id):
        raise HTTPException(status_code=404, detail="Word not found")
    sessions = list_sessions(db, word_id)
    return [ChatSessionRead.model_validate(s) for s in sessions]


@router.post("/words/{word_id}/chat/sessions", response_model=ChatSessionRead)
def post_session(word_id: int, payload: ChatSessionCreate, db: Session = Depends(get_db)) -> ChatSessionRead:
    if not db.get(Word, word_id):
        raise HTTPException(status_code=404, detail="Word not found")
    session = create_session(db, word_id, payload.title)
    db.commit()
    db.refresh(session)
    return ChatSessionRead.model_validate(session)


@router.get("/etymology-components/{component_text}/chat/sessions", response_model=list[ChatSessionRead])
def get_component_sessions(component_text: str, db: Session = Depends(get_db)) -> list[ChatSessionRead]:
    normalized = normalize_component_text(component_text)
    if not normalized:
        raise HTTPException(status_code=400, detail="component_text is required")
    sessions = list_component_sessions(db, normalized)
    return [ChatSessionRead.model_validate(s) for s in sessions]


@router.post("/etymology-components/{component_text}/chat/sessions", response_model=ChatSessionRead)
def post_component_session(
    component_text: str,
    payload: ChatSessionCreate,
    db: Session = Depends(get_db),
) -> ChatSessionRead:
    normalized = normalize_component_text(component_text)
    if not normalized:
        raise HTTPException(status_code=400, detail="component_text is required")
    session = create_component_session(db, normalized, payload.title)
    db.commit()
    db.refresh(session)
    return ChatSessionRead.model_validate(session)


@router.patch("/chat/sessions/{session_id}", response_model=ChatSessionRead)
def patch_session(
    session_id: int,
    payload: ChatSessionUpdate,
    db: Session = Depends(get_db),
) -> ChatSessionRead:
    try:
        session = update_session_title(db, session_id, payload.title)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")
    db.commit()
    db.refresh(session)
    return ChatSessionRead.model_validate(session)


@router.delete("/chat/sessions/{session_id}", status_code=204)
def remove_session(session_id: int, db: Session = Depends(get_db)) -> None:
    try:
        delete_session(db, session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")
    db.commit()


@router.get("/chat/sessions/{session_id}/messages", response_model=list[ChatMessageRead])
def get_messages(session_id: int, db: Session = Depends(get_db)) -> list[ChatMessageRead]:
    if not db.get(ChatSession, session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    messages = list_messages(db, session_id)
    return [ChatMessageRead.model_validate(m) for m in messages]


@router.post("/chat/sessions/{session_id}/messages", response_model=ChatReply)
def post_message(
    session_id: int,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
) -> ChatReply:
    session = db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    is_first_message = not list_messages(db, session_id)
    user, assistant = answer_in_session(db, session, payload.content)
    if is_first_message and session.title in ("Word Chat", f"Component Chat: {session.component_text}"):
        session.title = auto_title_from_content(payload.content)
    db.commit()
    db.refresh(user)
    db.refresh(assistant)
    return ChatReply(
        user_message=ChatMessageRead.model_validate(user),
        assistant_message=ChatMessageRead.model_validate(assistant),
    )
