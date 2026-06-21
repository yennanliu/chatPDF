"""
Unit tests — ingest_document edge cases.

Contract under test:
  - A PDF that yields no extractable text produces zero chunks, upserts
    nothing, yet still marks the document "indexed" with its page_count
    (the "empty/unreadable PDF" branch).

Uses local fakes only (in-memory SQLite + EphemeralClient + _FakeEF) — fast,
offline, no model download.
"""
from __future__ import annotations

import fitz

from models.tables import Document
from services.ingestion import ingest_document
from services.rag_config import RAGConfig


def _blank_pdf(tmp_path) -> str:
    """A two-page PDF with no text content."""
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    path = tmp_path / "blank.pdf"
    doc.save(str(path))
    return str(path)


def test_empty_pdf_indexes_with_no_chunks(db_session, test_vs, tmp_path):
    path = _blank_pdf(tmp_path)
    doc = Document(name="blank.pdf", file_path=path)
    db_session.add(doc)
    db_session.commit()

    ingest_document(doc.id, path, db_session, test_vs)

    refreshed = db_session.get(Document, doc.id)
    assert refreshed.status == "indexed"
    assert refreshed.page_count == 2
    # Nothing was embedded — the empty-chunks branch was taken.
    assert test_vs.get_chunks([doc.id]) == []


def test_pdf_with_text_indexes_chunks(db_session, test_vs, tmp_path, sample_pdf):
    path = tmp_path / "sample.pdf"
    path.write_bytes(sample_pdf)
    doc = Document(name="sample.pdf", file_path=str(path))
    db_session.add(doc)
    db_session.commit()

    ingest_document(doc.id, str(path), db_session, test_vs, RAGConfig(chunk_size=40))

    refreshed = db_session.get(Document, doc.id)
    assert refreshed.status == "indexed"
    assert len(test_vs.get_chunks([doc.id])) > 0
