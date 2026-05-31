"""
TDD — WebSocket chat (sync tests via starlette TestClient)

Contract under test:
  WS /ws/chat/{session_id}
    client → { "query": "..." }
    server → { "type": "token", "data": "..." }  (one or more)
    server → { "type": "done", "sources": [...] }

  After chat:
    GET /api/sessions/{id} shows messages persisted
"""
import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _setup(tc, sample_pdf):
    """Upload doc, create library+session, return session_id."""
    import io
    resp = tc.post(
        "/api/documents/upload",
        files={"file": ("doc.pdf", io.BytesIO(sample_pdf), "application/pdf")},
    )
    assert resp.status_code == 201
    doc_id = resp.json()["doc_id"]

    lib = tc.post("/api/libraries", json={"name": "WS Test Lib"}).json()
    tc.post(
        f"/api/libraries/{lib['library_id']}/documents",
        json={"doc_id": doc_id},
    )

    sess = tc.post("/api/sessions", json={
        "library_id": lib["library_id"],
        "provider": "openai",
        "model": "gpt-4o",
    }).json()
    return sess["session_id"]


def _recv_all(ws, max_frames: int = 30) -> list[dict]:
    frames: list[dict] = []
    for _ in range(max_frames):
        msg = ws.receive_json()
        frames.append(msg)
        if msg.get("type") in ("done", "error"):
            break
    return frames


# ── tests ─────────────────────────────────────────────────────────────────────

def test_ws_sends_token_frames_then_done(ws_client, sample_pdf):
    sid = _setup(ws_client, sample_pdf)

    with ws_client.websocket_connect(f"/ws/chat/{sid}") as ws:
        ws.send_json({"query": "What is this document about?"})
        frames = _recv_all(ws)

    token_frames = [f for f in frames if f.get("type") == "token"]
    done_frames  = [f for f in frames if f.get("type") == "done"]

    assert len(token_frames) >= 1, "Expected at least one token frame"
    assert len(done_frames) == 1,  "Expected exactly one done frame"
    assert "sources" in done_frames[0]


def test_ws_done_frame_has_sources_list(ws_client, sample_pdf):
    sid = _setup(ws_client, sample_pdf)

    with ws_client.websocket_connect(f"/ws/chat/{sid}") as ws:
        ws.send_json({"query": "Summarise the content."})
        frames = _recv_all(ws)

    done = next(f for f in frames if f["type"] == "done")
    assert isinstance(done["sources"], list)


def test_ws_messages_persisted_after_turn(ws_client, sample_pdf):
    sid = _setup(ws_client, sample_pdf)

    with ws_client.websocket_connect(f"/ws/chat/{sid}") as ws:
        ws.send_json({"query": "Hello"})
        _recv_all(ws)

    detail = ws_client.get(f"/api/sessions/{sid}").json()
    roles = [m["role"] for m in detail["messages"]]
    assert "user" in roles
    assert "assistant" in roles


def test_ws_unknown_session_sends_error(ws_client):
    with ws_client.websocket_connect("/ws/chat/no-such-session") as ws:
        ws.send_json({"query": "hello"})
        msg = ws.receive_json()
    assert msg["type"] == "error"


def test_ws_multiple_turns_accumulate_history(ws_client, sample_pdf):
    sid = _setup(ws_client, sample_pdf)

    with ws_client.websocket_connect(f"/ws/chat/{sid}") as ws:
        ws.send_json({"query": "First question"})
        _recv_all(ws)

    with ws_client.websocket_connect(f"/ws/chat/{sid}") as ws:
        ws.send_json({"query": "Second question"})
        _recv_all(ws)

    detail = ws_client.get(f"/api/sessions/{sid}").json()
    user_msgs = [m for m in detail["messages"] if m["role"] == "user"]
    assert len(user_msgs) == 2
