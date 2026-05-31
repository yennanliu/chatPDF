"""
TDD — documents API

Contract under test:
  POST /api/documents/upload  → 201, returns doc_id / name / status
  GET  /api/documents          → 200, list of documents
  DELETE /api/documents/{id}  → 204, document removed
"""
import pytest


async def test_upload_returns_201_with_doc_id(client, sample_pdf):
    response = await client.post(
        "/api/documents/upload",
        files={"file": ("sample.pdf", sample_pdf, "application/pdf")},
    )
    assert response.status_code == 201
    data = response.json()
    assert "doc_id" in data
    assert data["name"] == "sample.pdf"
    assert data["status"] == "indexed"
    assert data["page_count"] == 1


async def test_upload_persists_to_list(client, sample_pdf):
    await client.post(
        "/api/documents/upload",
        files={"file": ("a.pdf", sample_pdf, "application/pdf")},
    )
    resp = await client.get("/api/documents")
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()]
    assert "a.pdf" in names


async def test_list_empty_initially(client):
    resp = await client.get("/api/documents")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_delete_removes_document(client, sample_pdf):
    upload = await client.post(
        "/api/documents/upload",
        files={"file": ("del.pdf", sample_pdf, "application/pdf")},
    )
    doc_id = upload.json()["doc_id"]

    resp = await client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 204

    resp = await client.get("/api/documents")
    ids = [d["doc_id"] for d in resp.json()]
    assert doc_id not in ids


async def test_delete_nonexistent_returns_404(client):
    resp = await client.delete("/api/documents/no-such-id")
    assert resp.status_code == 404


async def test_upload_multiple_documents(client, sample_pdf):
    for name in ("first.pdf", "second.pdf", "third.pdf"):
        r = await client.post(
            "/api/documents/upload",
            files={"file": (name, sample_pdf, "application/pdf")},
        )
        assert r.status_code == 201

    resp = await client.get("/api/documents")
    assert len(resp.json()) == 3
