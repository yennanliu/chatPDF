from __future__ import annotations

import logging
import uuid
from pathlib import Path

import fitz
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from config import settings
from db import get_db
from models.tables import Document
from services.ingestion import ingest_document
from services.rag_config import RAGConfig, available_chunkers
from vector_store import VectorStore, get_vector_store

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger("chatpdf.documents")


class DocumentOut(BaseModel):
    doc_id: str
    name: str
    page_count: int | None
    status: str
    created_at: str


class DocumentStatusOut(BaseModel):
    doc_id: str
    status: str
    page_count: int | None


def _doc_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        doc_id=doc.id,
        name=doc.name,
        page_count=doc.page_count,
        status=doc.status,
        created_at=doc.created_at.isoformat(),
    )


def _bg_ingest(
    doc_id: str, file_path: str, db: Session, vs: VectorStore, rag_config: RAGConfig
) -> None:
    """Background task: chunk + embed PDF, update status when done."""
    try:
        ingest_document(doc_id, file_path, db, vs, rag_config)
    except Exception:
        logger.exception("ingest FAILED: doc_id=%s file=%s — marking status=error", doc_id, file_path)
        doc = db.get(Document, doc_id)
        if doc:
            doc.status = "error"
            db.add(doc)
            db.commit()


@router.post("/upload", status_code=201, response_model=DocumentOut)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    chunker: str = Form("recursive"),
    chunk_size: int = Form(800, gt=0),
    chunk_overlap: int = Form(100, ge=0),
    db: Session = Depends(get_db),
    vs: VectorStore = Depends(get_vector_store),
):
    if chunker not in available_chunkers():
        raise HTTPException(
            status_code=422,
            detail=f"Unknown chunker '{chunker}'. Choose one of: {', '.join(available_chunkers())}",
        )

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    doc_id = str(uuid.uuid4())
    safe_name = Path(file.filename).name if file.filename else "upload.pdf"
    dest = upload_dir / f"{doc_id}_{safe_name}"

    content = await file.read()
    dest.write_bytes(content)
    logger.info(
        "upload received: doc_id=%s name=%s bytes=%d chunker=%s",
        doc_id, safe_name, len(content), chunker,
    )

    # Count pages synchronously — cheap header read, no text extraction
    page_count: int | None = None
    try:
        with fitz.open(str(dest)) as pdf:
            page_count = len(pdf)
    except Exception:
        pass

    doc = Document(id=doc_id, name=safe_name, file_path=str(dest), page_count=page_count)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    rag_config = RAGConfig(chunker=chunker, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    # FastAPI guarantees yield-dep teardown waits for background tasks,
    # so passing db here is safe — the session stays open until _bg_ingest returns.
    background_tasks.add_task(_bg_ingest, doc_id, str(dest), db, vs, rag_config)
    logger.info("upload accepted, ingest scheduled: doc_id=%s pages=%s", doc_id, page_count)

    return _doc_out(doc)


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    docs = db.exec(select(Document).order_by(Document.created_at.desc())).all()
    return [_doc_out(d) for d in docs]


@router.delete("", status_code=204)
def delete_all_documents(
    db: Session = Depends(get_db),
    vs: VectorStore = Depends(get_vector_store),
):
    """Delete every document — vectors, files, and rows (session links cascade)."""
    docs = db.exec(select(Document)).all()
    logger.info("delete-all start: %d documents", len(docs))
    for doc in docs:
        vs.delete_document(doc.id)
        dest = Path(doc.file_path)
        if dest.exists():
            dest.unlink()
        db.delete(doc)
    db.commit()
    logger.info("delete-all done: %d documents removed", len(docs))


@router.get("/{doc_id}/status", response_model=DocumentStatusOut)
def get_document_status(doc_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentStatusOut(doc_id=doc.id, status=doc.status, page_count=doc.page_count)


@router.delete("/{doc_id}", status_code=204)
def delete_document(
    doc_id: str,
    db: Session = Depends(get_db),
    vs: VectorStore = Depends(get_vector_store),
):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    logger.info("delete start: doc_id=%s name=%s", doc_id, doc.name)
    vs.delete_document(doc_id)

    dest = Path(doc.file_path)
    if dest.exists():
        dest.unlink()

    try:
        db.delete(doc)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("delete FAILED (db): doc_id=%s — likely referenced by a session", doc_id)
        raise HTTPException(
            status_code=409,
            detail="Cannot delete: document is still referenced by one or more chat sessions.",
        )
    logger.info("delete done: doc_id=%s", doc_id)
