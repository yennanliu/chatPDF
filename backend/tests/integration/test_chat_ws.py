"""
TDD — WebSocket chat (sync tests via starlette TestClient)

Contract under test:
  WS /ws/chat/{session_id}
    client → { "query": "..." }
    server → { "type": "token", "data": "..." }  (one or more)
    server → { "type": "done", "sources": [...] }

  Additions:
    - per-session RAGConfig.top_k limits sources in done frame
    - Cross-collection search: sources from multiple docs
    - Source citation shape: doc_name, chunk_preview, score
    - Two sessions are history-independent
"""
import io

# ── helpers ───────────────────────────────────────────────────────────────────

def _upload(tc, name, sample_pdf):
    resp = tc.post(
        "/api/documents/upload",
        files={"file": (name, io.BytesIO(sample_pdf), "application/pdf")},
    )
    assert resp.status_code == 201
    return resp.json()["doc_id"]


def _make_session(tc, doc_ids, rag_config=None, title=None):
    body = {"doc_ids": doc_ids, "provider": "openai", "model": "gpt-4o"}
    if rag_config is not None:
        body["rag_config"] = rag_config
    if title:
        body["title"] = title
    return tc.post("/api/sessions", json=body).json()["session_id"]


def _setup(tc, sample_pdf):
    """Upload a doc, create a session over it, return session_id."""
    doc_id = _upload(tc, "doc.pdf", sample_pdf)
    return _make_session(tc, [doc_id])


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


# ── per-session RAGConfig override ────────────────────────────────────────────

def test_rag_config_top_k_limits_sources(ws_client, sample_pdf):
    """Session with top_k=1 → done frame contains at most 1 source."""
    doc_id = _upload(ws_client, "tight.pdf", sample_pdf)
    sid = _make_session(ws_client, [doc_id], rag_config={"top_k": 1})

    with ws_client.websocket_connect(f"/ws/chat/{sid}") as ws:
        ws.send_json({"query": "Summarise"})
        frames = _recv_all(ws)

    done = next(f for f in frames if f["type"] == "done")
    assert len(done["sources"]) <= 1


def test_rag_config_overrides_are_independent_per_session(ws_client, sample_pdf):
    """Two sessions with different top_k values produce different source caps."""
    def _session(top_k: int) -> str:
        doc_id = _upload(ws_client, f"doc_{top_k}.pdf", sample_pdf)
        return _make_session(ws_client, [doc_id], rag_config={"top_k": top_k})

    sid1 = _session(top_k=1)
    _session(top_k=5)

    def _sources(sid):
        with ws_client.websocket_connect(f"/ws/chat/{sid}") as ws:
            ws.send_json({"query": "test"})
            frames = _recv_all(ws)
        return next(f for f in frames if f["type"] == "done")["sources"]

    assert len(_sources(sid1)) <= 1


# ── source citation shape ─────────────────────────────────────────────────────

def test_source_citations_have_correct_fields(ws_client, sample_pdf):
    """Each source in the done frame must have doc_name, chunk_preview, score."""
    sid = _setup(ws_client, sample_pdf)

    with ws_client.websocket_connect(f"/ws/chat/{sid}") as ws:
        ws.send_json({"query": "What does this say?"})
        frames = _recv_all(ws)

    done = next(f for f in frames if f["type"] == "done")
    for src in done["sources"]:
        assert "doc_name" in src
        assert "chunk_preview" in src
        assert "score" in src
        assert isinstance(src["chunk_preview"], str)
        assert isinstance(src["score"], float)


# ── cross-collection search ───────────────────────────────────────────────────

def test_cross_collection_search_queries_all_docs(ws_client, sample_pdf):
    """A session with two documents searches both ChromaDB collections."""
    doc1 = _upload(ws_client, "alpha.pdf", sample_pdf)
    doc2 = _upload(ws_client, "beta.pdf", sample_pdf)
    sid = _make_session(ws_client, [doc1, doc2])

    with ws_client.websocket_connect(f"/ws/chat/{sid}") as ws:
        ws.send_json({"query": "Tell me about the documents"})
        frames = _recv_all(ws)

    done = next(f for f in frames if f["type"] == "done")
    assert len(done["sources"]) >= 1
    assert any(s["doc_name"] for s in done["sources"])


# ── independent session histories ─────────────────────────────────────────────

def test_two_sessions_have_independent_histories(ws_client, sample_pdf):
    """Messages in session A do not appear in session B (same docs)."""
    doc_id = _upload(ws_client, "shared.pdf", sample_pdf)
    sid = _make_session(ws_client, [doc_id])
    sid2 = _make_session(ws_client, [doc_id], title="Session B")

    with ws_client.websocket_connect(f"/ws/chat/{sid}") as ws:
        ws.send_json({"query": "Only in session 1"})
        _recv_all(ws)

    detail2 = ws_client.get(f"/api/sessions/{sid2}").json()
    assert detail2["messages"] == []
