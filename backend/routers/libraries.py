from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from db import get_db
from models.tables import Document, Library, LibraryDocument

router = APIRouter(prefix="/api/libraries", tags=["libraries"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class LibraryCreate(BaseModel):
    name: str
    description: str | None = None
    rag_config: dict | None = None


class LibraryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    rag_config: dict | None = None


class DocumentSnippet(BaseModel):
    doc_id: str
    name: str
    status: str


class AddDocumentBody(BaseModel):
    doc_id: str


class LibraryOut(BaseModel):
    library_id: str
    name: str
    description: str | None
    rag_config: dict
    documents: list[DocumentSnippet]
    created_at: str


def _lib_out(lib: Library, docs: list[Document]) -> LibraryOut:
    return LibraryOut(
        library_id=lib.id,
        name=lib.name,
        description=lib.description,
        rag_config=json.loads(lib.rag_config or "{}"),
        documents=[DocumentSnippet(doc_id=d.id, name=d.name, status=d.status) for d in docs],
        created_at=lib.created_at.isoformat(),
    )


def _get_lib_docs(lib_id: str, db: Session) -> list[Document]:
    rows = db.exec(
        select(Document)
        .join(LibraryDocument, LibraryDocument.document_id == Document.id)
        .where(LibraryDocument.library_id == lib_id)
        .order_by(LibraryDocument.added_at)
    ).all()
    return list(rows)


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("", status_code=201, response_model=LibraryOut)
def create_library(body: LibraryCreate, db: Session = Depends(get_db)):
    lib = Library(
        name=body.name,
        description=body.description,
        rag_config=json.dumps(body.rag_config or {}),
    )
    db.add(lib)
    db.commit()
    db.refresh(lib)
    return _lib_out(lib, [])


@router.get("", response_model=list[LibraryOut])
def list_libraries(db: Session = Depends(get_db)):
    libs = db.exec(select(Library).order_by(Library.created_at.desc())).all()
    return [_lib_out(lib, _get_lib_docs(lib.id, db)) for lib in libs]


@router.get("/{library_id}", response_model=LibraryOut)
def get_library(library_id: str, db: Session = Depends(get_db)):
    lib = db.get(Library, library_id)
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    return _lib_out(lib, _get_lib_docs(library_id, db))


@router.patch("/{library_id}", response_model=LibraryOut)
def update_library(library_id: str, body: LibraryUpdate, db: Session = Depends(get_db)):
    lib = db.get(Library, library_id)
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    if body.name is not None:
        lib.name = body.name
    if body.description is not None:
        lib.description = body.description
    if body.rag_config is not None:
        lib.rag_config = json.dumps(body.rag_config)
    db.add(lib)
    db.commit()
    db.refresh(lib)
    return _lib_out(lib, _get_lib_docs(library_id, db))


@router.delete("/{library_id}", status_code=204)
def delete_library(library_id: str, db: Session = Depends(get_db)):
    lib = db.get(Library, library_id)
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")
    db.delete(lib)
    db.commit()


@router.post("/{library_id}/documents", response_model=LibraryOut)
def add_document_to_library(
    library_id: str,
    body: AddDocumentBody,
    db: Session = Depends(get_db),
):
    lib = db.get(Library, library_id)
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")

    doc = db.get(Document, body.doc_id)
    doc_id = body.doc_id
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    existing = db.get(LibraryDocument, (library_id, doc_id))
    if not existing:
        db.add(LibraryDocument(library_id=library_id, document_id=doc_id))
        db.commit()

    return _lib_out(lib, _get_lib_docs(library_id, db))


@router.delete("/{library_id}/documents/{doc_id}", response_model=LibraryOut)
def remove_document_from_library(
    library_id: str,
    doc_id: str,
    db: Session = Depends(get_db),
):
    lib = db.get(Library, library_id)
    if not lib:
        raise HTTPException(status_code=404, detail="Library not found")

    link = db.get(LibraryDocument, (library_id, doc_id))
    if link:
        db.delete(link)
        db.commit()

    return _lib_out(lib, _get_lib_docs(library_id, db))
