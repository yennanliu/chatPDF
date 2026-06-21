from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session as DBSession
from sqlmodel import select

from db import get_db
from models.tables import Document, Message, SessionDocument
from models.tables import Session as SessionModel

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    doc_ids: list[str]
    provider: str
    model: str
    title: str | None = None
    rag_config: dict | None = None


class SessionUpdate(BaseModel):
    title: str


class DocumentSnippet(BaseModel):
    doc_id: str
    name: str
    status: str


class MessageOut(BaseModel):
    role: str
    content: str
    sources: list[dict] | None = None
    created_at: str


class SessionOut(BaseModel):
    session_id: str
    title: str
    documents: list[DocumentSnippet]
    rag_config: dict
    provider: str
    model: str
    created_at: str


class SessionDetailOut(SessionOut):
    messages: list[MessageOut]


def _msg_out(m: Message) -> MessageOut:
    return MessageOut(
        role=m.role,
        content=m.content,
        sources=json.loads(m.sources) if m.sources else None,
        created_at=m.created_at.isoformat(),
    )


def _session_docs(session_id: str, db: DBSession) -> list[Document]:
    rows = db.exec(
        select(Document)
        .join(SessionDocument, SessionDocument.document_id == Document.id)
        .where(SessionDocument.session_id == session_id)
        .order_by(SessionDocument.added_at)
    ).all()
    return list(rows)


def _session_out(s: SessionModel, docs: list[Document]) -> SessionOut:
    return SessionOut(
        session_id=s.id,
        title=s.title,
        documents=[DocumentSnippet(doc_id=d.id, name=d.name, status=d.status) for d in docs],
        rag_config=json.loads(s.rag_config or "{}"),
        provider=s.provider,
        model=s.model,
        created_at=s.created_at.isoformat(),
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", status_code=201, response_model=SessionOut)
def create_session(body: SessionCreate, db: DBSession = Depends(get_db)):
    for doc_id in body.doc_ids:
        if not db.get(Document, doc_id):
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
    session = SessionModel(
        title=body.title or "New Chat",
        rag_config=json.dumps(body.rag_config or {}),
        provider=body.provider,
        model=body.model,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    for doc_id in body.doc_ids:
        db.add(SessionDocument(session_id=session.id, document_id=doc_id))
    db.commit()
    return _session_out(session, _session_docs(session.id, db))


@router.get("", response_model=list[SessionOut])
def list_sessions(db: DBSession = Depends(get_db)):
    rows = db.exec(select(SessionModel).order_by(SessionModel.created_at.desc())).all()
    return [_session_out(s, _session_docs(s.id, db)) for s in rows]


@router.delete("", status_code=204)
def delete_all_sessions(db: DBSession = Depends(get_db)):
    """Delete every session (messages + document links cascade)."""
    for s in db.exec(select(SessionModel)).all():
        db.delete(s)
    db.commit()


@router.get("/{session_id}", response_model=SessionDetailOut)
def get_session(session_id: str, db: DBSession = Depends(get_db)):
    s = db.get(SessionModel, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    msgs = db.exec(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    ).all()
    base = _session_out(s, _session_docs(session_id, db))
    return SessionDetailOut(**base.model_dump(), messages=[_msg_out(m) for m in msgs])


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
    return _session_out(s, _session_docs(session_id, db))


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: str, db: DBSession = Depends(get_db)):
    s = db.get(SessionModel, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(s)
    db.commit()
