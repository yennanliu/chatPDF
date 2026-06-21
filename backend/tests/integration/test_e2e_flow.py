"""
Phase 7 — End-to-end integration tests

Full happy paths that chain every layer together in a single test:
  upload → poll status → session (with docs) → chat → reload history

These catch regressions that per-endpoint tests miss: mismatched IDs across
operations, cascade assumptions, history accumulation, and status transitions.
"""
import io

# ── helpers ───────────────────────────────────────────────────────────────────

def _upload(tc, sample_pdf, name: str = "e2e.pdf"):
    return tc.post(
        "/api/documents/upload",
        files={"file": (name, io.BytesIO(sample_pdf), "application/pdf")},
    ).json()


def _recv_until_done(ws, max_frames: int = 40) -> list[dict]:
    frames: list[dict] = []
    for _ in range(max_frames):
        msg = ws.receive_json()
        frames.append(msg)
        if msg.get("type") in ("done", "error"):
            break
    return frames


# ── E2E: full happy path ──────────────────────────────────────────────────────

def test_e2e_upload_session_chat_reload(ws_client, sample_pdf):
    """
    Complete user journey:
      upload PDF → verify indexed → create session over the doc →
      chat turn 1 → reload history → chat turn 2 →
      verify history accumulation → rename session
    """
    # 1. Upload
    doc = _upload(ws_client, sample_pdf, "journey.pdf")
    assert doc["status"] == "pending"
    doc_id = doc["doc_id"]

    # 2. Poll status (background task ran synchronously in TestClient)
    status = ws_client.get(f"/api/documents/{doc_id}/status").json()
    assert status["status"] == "indexed"
    assert status["page_count"] == 1

    # 3. Create session over the document
    sess = ws_client.post("/api/sessions", json={
        "doc_ids": [doc_id],
        "provider": "openai",
        "model": "gpt-4o",
        "title": "E2E Chat",
    }).json()
    assert sess["session_id"]
    assert sess["title"] == "E2E Chat"
    assert any(d["doc_id"] == doc_id for d in sess["documents"])
    session_id = sess["session_id"]

    # 6. Chat turn 1
    with ws_client.websocket_connect(f"/ws/chat/{session_id}") as ws:
        ws.send_json({"query": "What is in this document?"})
        frames = _recv_until_done(ws)

    assert any(f["type"] == "token" for f in frames), "Expected at least one token frame"
    done = next(f for f in frames if f["type"] == "done")
    assert isinstance(done["sources"], list)

    # 7. Reload session — messages must be persisted
    detail = ws_client.get(f"/api/sessions/{session_id}").json()
    assert len(detail["messages"]) == 2
    assert detail["messages"][0]["role"] == "user"
    assert detail["messages"][1]["role"] == "assistant"
    assert "What is in this document?" in detail["messages"][0]["content"]

    # 8. Chat turn 2 — history accumulates
    with ws_client.websocket_connect(f"/ws/chat/{session_id}") as ws:
        ws.send_json({"query": "Summarise in one sentence."})
        _recv_until_done(ws)

    detail2 = ws_client.get(f"/api/sessions/{session_id}").json()
    user_msgs = [m for m in detail2["messages"] if m["role"] == "user"]
    assert len(user_msgs) == 2, f"Expected 2 user turns, got {len(user_msgs)}"

    # 9. Rename session
    renamed = ws_client.patch(
        f"/api/sessions/{session_id}", json={"title": "Renamed E2E"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Renamed E2E"


# ── E2E: upload progress transitions ─────────────────────────────────────────

def test_e2e_upload_status_polling(ws_client, sample_pdf):
    """
    POST /upload returns pending immediately; GET /status returns indexed
    after background ingestion (synchronous in TestClient).
    """
    doc = _upload(ws_client, sample_pdf, "poll.pdf")
    assert doc["status"] == "pending"      # initial response = pending
    assert doc["page_count"] == 1          # page count pre-scanned sync

    status = ws_client.get(f"/api/documents/{doc['doc_id']}/status").json()
    assert status["status"] == "indexed"   # background task ran before response returned
    assert status["page_count"] == 1


# ── E2E: error state — unknown session → WS error frame ──────────────────────

def test_e2e_ws_error_on_bad_session(ws_client):
    """WS chat on a non-existent session sends an error frame, not a crash."""
    with ws_client.websocket_connect("/ws/chat/no-such-session-id") as ws:
        ws.send_json({"query": "hello"})
        msg = ws.receive_json()
    assert msg["type"] == "error"
    assert "detail" in msg


# ── E2E: error state — session with no docs still returns done frame ──────────

def test_e2e_empty_session_chat_returns_done(ws_client, sample_pdf):
    """
    Chatting on a session with no documents should still complete (no crash);
    sources list will be empty or minimal.
    """
    sess = ws_client.post("/api/sessions", json={
        "doc_ids": [],
        "provider": "openai",
        "model": "gpt-4o",
    }).json()

    with ws_client.websocket_connect(f"/ws/chat/{sess['session_id']}") as ws:
        ws.send_json({"query": "Anything?"})
        frames = _recv_until_done(ws)

    # Either a done frame or an error frame — never a hang
    terminal = frames[-1]
    assert terminal["type"] in ("done", "error")


# ── E2E: cascade integrity ────────────────────────────────────────────────────

def test_e2e_delete_session_removes_history(ws_client, sample_pdf):
    """
    Deleting a session cascades: its messages (and document links) are removed,
    and the document itself survives.
    """
    doc = _upload(ws_client, sample_pdf, "cascade.pdf")
    sess = ws_client.post("/api/sessions", json={
        "doc_ids": [doc["doc_id"]],
        "provider": "openai",
        "model": "gpt-4o",
    }).json()
    session_id = sess["session_id"]

    # Generate some history
    with ws_client.websocket_connect(f"/ws/chat/{session_id}") as ws:
        ws.send_json({"query": "Hello"})
        _recv_until_done(ws)

    detail = ws_client.get(f"/api/sessions/{session_id}").json()
    assert len(detail["messages"]) > 0

    # Delete the session
    assert ws_client.delete(f"/api/sessions/{session_id}").status_code == 204
    assert ws_client.get(f"/api/sessions/{session_id}").status_code == 404

    # The document still exists independently
    assert ws_client.get(f"/api/documents/{doc['doc_id']}/status").status_code == 200
