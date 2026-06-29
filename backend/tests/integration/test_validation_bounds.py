"""
TDD — input validation & resource bounds (§1.3, §1.4)

Contract under test:
  - Upload rejects non-PDF content-type / bad magic bytes (415)
  - Upload rejects files over the size limit (413)
  - Session create rejects too many doc_ids (422)
  - WebSocket rejects oversized queries (error frame, connection stays open)
"""
import io

import config


async def test_upload_rejects_non_pdf_content_type(client, sample_pdf):
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("evil.exe", sample_pdf, "application/octet-stream")},
    )
    assert resp.status_code == 415


async def test_upload_rejects_bad_magic_bytes(client):
    not_a_pdf = b"GIF89a this is not a pdf at all"
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("fake.pdf", not_a_pdf, "application/pdf")},
    )
    assert resp.status_code == 415


async def test_upload_rejects_oversized_file(client, sample_pdf, monkeypatch):
    monkeypatch.setattr(config.settings, "max_upload_mb", 0)  # everything is too big
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("big.pdf", sample_pdf, "application/pdf")},
    )
    assert resp.status_code == 413


async def test_upload_accepts_valid_pdf(client, sample_pdf):
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("ok.pdf", sample_pdf, "application/pdf")},
    )
    assert resp.status_code == 201


async def test_session_rejects_too_many_docs(client, sample_pdf, monkeypatch):
    monkeypatch.setattr(config.settings, "max_docs_per_session", 2)
    doc_ids = []
    for n in ("a.pdf", "b.pdf", "c.pdf"):
        r = await client.post(
            "/api/documents/upload",
            files={"file": (n, sample_pdf, "application/pdf")},
        )
        doc_ids.append(r.json()["doc_id"])

    resp = await client.post("/api/sessions", json={
        "doc_ids": doc_ids, "provider": "openai", "model": "gpt-4o",
    })
    assert resp.status_code == 422


def test_ws_rejects_oversized_query(ws_client, sample_pdf, monkeypatch):
    monkeypatch.setattr(config.settings, "max_query_chars", 10)
    doc_id = ws_client.post(
        "/api/documents/upload",
        files={"file": ("q.pdf", io.BytesIO(sample_pdf), "application/pdf")},
    ).json()["doc_id"]
    sid = ws_client.post("/api/sessions", json={
        "doc_ids": [doc_id], "provider": "openai", "model": "gpt-4o",
    }).json()["session_id"]

    with ws_client.websocket_connect(f"/ws/chat/{sid}") as ws:
        ws.send_json({"query": "x" * 50})
        msg = ws.receive_json()
    assert msg["type"] == "error"
