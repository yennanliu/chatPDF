"""
TDD — documents API

Contract under test:
  POST /api/documents/upload  → 201, returns doc_id / name / status
  GET  /api/documents          → 200, list of documents
  DELETE /api/documents/{id}  → 204, document removed
                                    cascades: ChromaDB collection removed
                                              session membership removed
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
    assert data["status"] == "pending"  # ingestion runs in background
    assert data["page_count"] == 1      # page count from sync pre-scan


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


# ── Phase 4: BackgroundTasks upload + status polling ─────────────────────────

async def test_status_endpoint_returns_indexed_after_upload(client, sample_pdf):
    """After upload, background ingestion runs → status endpoint shows 'indexed'."""
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("status_test.pdf", sample_pdf, "application/pdf")},
    )
    doc_id = resp.json()["doc_id"]

    # ASGITransport runs background tasks before returning — already indexed
    status_resp = await client.get(f"/api/documents/{doc_id}/status")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["doc_id"] == doc_id
    assert body["status"] == "indexed"
    assert body["page_count"] == 1


async def test_status_endpoint_404_for_unknown(client):
    resp = await client.get("/api/documents/no-such-doc/status")
    assert resp.status_code == 404


async def test_upload_initial_response_is_pending(client, sample_pdf):
    """The POST response body always says 'pending' — client must poll for completion."""
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("pending_test.pdf", sample_pdf, "application/pdf")},
    )
    assert resp.json()["status"] == "pending"


# ── delete cascade tests (Phase 3) ───────────────────────────────────────────

async def test_delete_all_documents(client, sample_pdf):
    """DELETE /api/documents removes every document."""
    for n in ("a.pdf", "b.pdf"):
        await client.post(
            "/api/documents/upload",
            files={"file": (n, sample_pdf, "application/pdf")},
        )
    assert len((await client.get("/api/documents")).json()) == 2

    r = await client.delete("/api/documents")
    assert r.status_code == 204
    assert (await client.get("/api/documents")).json() == []


async def test_delete_all_documents_empty_ok(client):
    r = await client.delete("/api/documents")
    assert r.status_code == 204


async def test_delete_doc_removes_chroma_collection(client, test_vs, sample_pdf):
    """Deleting a document removes its ChromaDB collection."""
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("chroma_test.pdf", sample_pdf, "application/pdf")},
    )
    doc_id = resp.json()["doc_id"]

    # collection must exist after upload
    test_vs._client.get_collection(f"doc_{doc_id}")  # raises if missing

    await client.delete(f"/api/documents/{doc_id}")

    # collection must be gone after delete
    with pytest.raises(Exception):
        test_vs._client.get_collection(f"doc_{doc_id}")


async def test_delete_doc_cascades_session_membership(client, sample_pdf):
    """Deleting a document removes it from every session it belonged to."""
    doc = (await client.post(
        "/api/documents/upload",
        files={"file": ("member.pdf", sample_pdf, "application/pdf")},
    )).json()
    doc_id = doc["doc_id"]

    # add to two sessions
    sess_a = (await client.post("/api/sessions", json={
        "doc_ids": [doc_id], "provider": "openai", "model": "gpt-4o",
    })).json()
    sess_b = (await client.post("/api/sessions", json={
        "doc_ids": [doc_id], "provider": "openai", "model": "gpt-4o",
    })).json()

    # delete the document
    r = await client.delete(f"/api/documents/{doc_id}")
    assert r.status_code == 204

    # neither session should still list the document
    for sid in (sess_a["session_id"], sess_b["session_id"]):
        detail = (await client.get(f"/api/sessions/{sid}")).json()
        assert doc_id not in [d["doc_id"] for d in detail["documents"]]


def test_delete_session_cascades_messages(sample_pdf, ws_client):
    """Deleting a session removes its messages (FK CASCADE)."""
    import io
    doc = ws_client.post(
        "/api/documents/upload",
        files={"file": ("msg_test.pdf", io.BytesIO(sample_pdf), "application/pdf")},
    ).json()

    sess = ws_client.post("/api/sessions", json={
        "doc_ids": [doc["doc_id"]],
        "provider": "openai",
        "model": "gpt-4o",
    }).json()
    sid = sess["session_id"]

    # generate a message
    with ws_client.websocket_connect(f"/ws/chat/{sid}") as ws:
        ws.send_json({"query": "Hello"})
        for _ in range(20):
            msg = ws.receive_json()
            if msg.get("type") == "done":
                break

    # confirm messages exist
    detail = ws_client.get(f"/api/sessions/{sid}").json()
    assert len(detail["messages"]) > 0

    # delete session
    assert ws_client.delete(f"/api/sessions/{sid}").status_code == 204
    assert ws_client.get(f"/api/sessions/{sid}").status_code == 404

    # session and its messages are gone
    assert ws_client.get(f"/api/sessions/{sid}").status_code == 404
