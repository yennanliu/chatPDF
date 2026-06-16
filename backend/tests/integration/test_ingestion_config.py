"""
TDD — ingestion honors RAGConfig chunking params.

Before this change `ingest_document` hardcoded RecursiveChunker(800/100), so
chunk_size / chunk_overlap / chunker had no effect. These tests pin the new
behaviour: chunking is driven by the RAGConfig passed in, and the upload
endpoint threads chunk params from form fields into ingestion.
"""
from __future__ import annotations

import fitz

from models.tables import Document
from services.ingestion import ingest_document
from services.rag_config import RAGConfig


def _make_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    # Lay out sentences down the page so PyMuPDF keeps them as readable text.
    y = 72
    for line in text.split(". "):
        page.insert_text((50, y), line.strip() + ".")
        y += 18
    return doc.tobytes()


def _count(test_vs, doc_id: str) -> int:
    return test_vs._client.get_collection(name=f"doc_{doc_id}").count()


def _seed_doc(db_session, tmp_path, text: str) -> tuple[str, str]:
    pdf_bytes = _make_pdf(text)
    path = tmp_path / "sample.pdf"
    path.write_bytes(pdf_bytes)
    doc = Document(name="sample.pdf", file_path=str(path))
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc.id, str(path)


LONG_TEXT = (
    "Alpha sentence one. Beta sentence two. Gamma sentence three. "
    "Delta sentence four. Epsilon sentence five. Zeta sentence six."
)


def test_small_chunk_size_produces_more_chunks(db_session, test_vs, tmp_path):
    doc_id, path = _seed_doc(db_session, tmp_path, LONG_TEXT)
    ingest_document(doc_id, path, db_session, test_vs, RAGConfig(chunk_size=30, chunk_overlap=0))
    assert _count(test_vs, doc_id) > 1


def test_large_chunk_size_produces_single_chunk(db_session, test_vs, tmp_path):
    doc_id, path = _seed_doc(db_session, tmp_path, LONG_TEXT)
    ingest_document(doc_id, path, db_session, test_vs, RAGConfig(chunk_size=10_000, chunk_overlap=0))
    assert _count(test_vs, doc_id) == 1


def test_ingest_marks_document_indexed(db_session, test_vs, tmp_path):
    doc_id, path = _seed_doc(db_session, tmp_path, LONG_TEXT)
    ingest_document(doc_id, path, db_session, test_vs, RAGConfig())
    doc = db_session.get(Document, doc_id)
    assert doc.status == "indexed"
    assert doc.page_count == 1


def test_ingest_defaults_to_recursive_when_no_config(db_session, test_vs, tmp_path):
    doc_id, path = _seed_doc(db_session, tmp_path, LONG_TEXT)
    ingest_document(doc_id, path, db_session, test_vs)  # no rag_config
    assert _count(test_vs, doc_id) >= 1
    assert db_session.get(Document, doc_id).status == "indexed"


# ── Upload endpoint threads chunk params ──────────────────────────────────────

async def test_upload_accepts_chunk_params(client, test_vs):
    pdf_bytes = _make_pdf(LONG_TEXT)
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
        data={"chunker": "recursive", "chunk_size": "30", "chunk_overlap": "0"},
    )
    assert resp.status_code == 201
    doc_id = resp.json()["doc_id"]
    # Background ingestion has run by the time the response is delivered.
    assert _count(test_vs, doc_id) > 1


async def test_upload_rejects_unknown_chunker(client):
    pdf_bytes = _make_pdf("One sentence.")
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
        data={"chunker": "does-not-exist"},
    )
    assert resp.status_code == 422
