from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
from sqlmodel import Session

from models.tables import Document
from vector_store import VectorStore


def _chunk_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += size - overlap
    return chunks


def ingest_document(doc_id: str, file_path: str, db: Session, vs: VectorStore) -> None:
    pdf = fitz.open(file_path)
    full_text = "\n".join(page.get_text() for page in pdf)
    page_count = len(pdf)
    pdf.close()

    chunks = _chunk_text(full_text)

    if chunks:
        metadatas = [
            {"doc_id": doc_id, "chunk_index": i, "file": Path(file_path).name}
            for i in range(len(chunks))
        ]
        vs.upsert_chunks(doc_id, chunks, metadatas)

    doc = db.get(Document, doc_id)
    doc.status = "indexed"
    doc.page_count = page_count
    db.add(doc)
    db.commit()
