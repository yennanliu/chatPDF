from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from config import settings
from db import get_db
from models.tables import Document
from services.ingestion import ingest_document
from vector_store import VectorStore, get_vector_store

router = APIRouter(prefix="/api/documents", tags=["documents"])


class DocumentOut(BaseModel):
    doc_id: str
    name: str
    page_count: int | None
    status: str
    created_at: str


def _doc_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        doc_id=doc.id,
        name=doc.name,
        page_count=doc.page_count,
        status=doc.status,
        created_at=doc.created_at.isoformat(),
    )


@router.post("/upload", status_code=201, response_model=DocumentOut)
async def upload_document(
    file: UploadFile,
    db: Session = Depends(get_db),
    vs: VectorStore = Depends(get_vector_store),
):
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    doc_id = str(uuid.uuid4())
    safe_name = Path(file.filename).name if file.filename else "upload.pdf"
    dest = upload_dir / f"{doc_id}_{safe_name}"

    content = await file.read()
    dest.write_bytes(content)

    doc = Document(id=doc_id, name=safe_name, file_path=str(dest))
    db.add(doc)
    db.commit()

    try:
        ingest_document(doc_id, str(dest), db, vs)
    except Exception as exc:
        doc.status = "error"
        db.add(doc)
        db.commit()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    db.refresh(doc)
    return _doc_out(doc)


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    docs = db.exec(select(Document).order_by(Document.created_at.desc())).all()
    return [_doc_out(d) for d in docs]


@router.delete("/{doc_id}", status_code=204)
def delete_document(
    doc_id: str,
    db: Session = Depends(get_db),
    vs: VectorStore = Depends(get_vector_store),
):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    vs.delete_document(doc_id)

    dest = Path(doc.file_path)
    if dest.exists():
        dest.unlink()

    db.delete(doc)
    db.commit()
