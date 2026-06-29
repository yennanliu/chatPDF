from __future__ import annotations

import logging
import time
from pathlib import Path

import fitz  # PyMuPDF
from sqlmodel import Session

from models.tables import Document
from services.rag_config import RAGConfig, build_chunker
from vector_store import VectorStore

logger = logging.getLogger("chatpdf.ingestion")


def ingest_document(
    doc_id: str,
    file_path: str,
    db: Session,
    vs: VectorStore,
    rag_config: RAGConfig | None = None,
) -> None:
    cfg = rag_config or RAGConfig()
    started = time.perf_counter()
    logger.info(
        "ingest start: doc_id=%s file=%s chunker=%s size=%s overlap=%s",
        doc_id, Path(file_path).name, cfg.chunker, cfg.chunk_size, cfg.chunk_overlap,
    )

    pdf = fitz.open(file_path)
    page_count = len(pdf)
    chunker = build_chunker(cfg)
    file_name = Path(file_path).name

    # Chunk page-by-page so every chunk carries its source page number — this is
    # what lets citations point at a specific page rather than the whole document.
    chunks: list[str] = []
    metadatas: list[dict] = []
    seen: set[str] = set()
    total_chars = 0
    for page_no, page in enumerate(pdf, start=1):
        page_text = page.get_text()
        total_chars += len(page_text)
        for piece in chunker.split(page_text):
            key = piece.strip()
            if not key or key in seen:  # drop blanks and exact duplicates
                continue
            seen.add(key)
            metadatas.append({
                "doc_id": doc_id,
                "chunk_index": len(chunks),
                "file": file_name,
                "page": page_no,
            })
            chunks.append(piece)
    pdf.close()
    logger.info(
        "ingest extracted+chunked: doc_id=%s pages=%d chars=%d chunks=%d",
        doc_id, page_count, total_chars, len(chunks),
    )

    if chunks:
        vs.upsert_chunks(doc_id, chunks, metadatas)
        logger.info("ingest embedded+upserted: doc_id=%s chunks=%d", doc_id, len(chunks))
    else:
        logger.warning("ingest no chunks (empty/unreadable PDF?): doc_id=%s", doc_id)

    doc = db.get(Document, doc_id)
    doc.status = "indexed"
    doc.page_count = page_count
    db.add(doc)
    db.commit()
    logger.info(
        "ingest done: doc_id=%s status=indexed elapsed=%.2fs",
        doc_id, time.perf_counter() - started,
    )
