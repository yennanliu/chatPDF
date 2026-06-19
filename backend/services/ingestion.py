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
    full_text = "\n".join(page.get_text() for page in pdf)
    page_count = len(pdf)
    pdf.close()
    logger.info(
        "ingest extracted: doc_id=%s pages=%d chars=%d", doc_id, page_count, len(full_text)
    )

    chunks = build_chunker(cfg).split(full_text)
    logger.info("ingest chunked: doc_id=%s chunks=%d", doc_id, len(chunks))

    if chunks:
        metadatas = [
            {"doc_id": doc_id, "chunk_index": i, "file": Path(file_path).name}
            for i in range(len(chunks))
        ]
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
