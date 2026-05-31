from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session as DBSession
from sqlmodel import select

from db import get_db
from models.tables import Library, Message
from models.tables import Session as SessionModel

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    library_id: str
    provider: str
    model: str
    title: str | None = None


class SessionUpdate(BaseModel):
    title: str


class MessageOut(BaseModel):
    role: str
    content: str
    sources: list[dict] | None = None
    created_at: str


class SessionOut(BaseModel):
    session_id: str
    title: str
    library_id: str
    provider: str
    model: str
    created_at: str


class SessionDetailOut(SessionOut):
    messages: list[MessageOut]


def _msg_out(m: Message) -> MessageOut:
    import json
    return MessageOut(
        role=m.role,
        content=m.content,
        sources=json.loads(m.sources) if m.sources else None,
        created_at=m.created_at.isoformat(),
    )


def _session_out(s: SessionModel) -> SessionOut:
    return SessionOut(
        session_id=s.id,
        title=s.title,
        library_id=s.library_id,
        provider=s.provider,
        model=s.model,
        created_at=s.created_at.isoformat(),
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", status_code=201, response_model=SessionOut)
def create_session(body: SessionCreate, db: DBSession = Depends(get_db)):
    if not db.get(Library, body.library_id):
        raise HTTPException(status_code=404, detail="Library not found")
    session = SessionModel(
        title=body.title or "New Chat",
        library_id=body.library_id,
        provider=body.provider,
        model=body.model,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_out(session)


@router.get("", response_model=list[SessionOut])
def list_sessions(db: DBSession = Depends(get_db)):
    rows = db.exec(select(SessionModel).order_by(SessionModel.created_at.desc())).all()
    return [_session_out(s) for s in rows]


@router.get("/{session_id}", response_model=SessionDetailOut)
def get_session(session_id: str, db: DBSession = Depends(get_db)):
    s = db.get(SessionModel, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    msgs = db.exec(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    ).all()
    return SessionDetailOut(**_session_out(s).model_dump(), messages=[_msg_out(m) for m in msgs])


@router.patch("/{session_id}", response_model=SessionOut)
def rename_session(session_id: str, body: SessionUpdate, db: DBSession = Depends(get_db)):
    s = db.get(SessionModel, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    s.title = body.title
    s.updated_at = datetime.now(UTC)
    db.add(s)
    db.commit()
    db.refresh(s)
    return _session_out(s)


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: str, db: DBSession = Depends(get_db)):
    s = db.get(SessionModel, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(s)
    db.commit()
