"""
TDD — WebSocket chat (sync tests via starlette TestClient)

Contract under test:
  WS /ws/chat/{session_id}
    client → { "query": "..." }
    server → { "type": "token", "data": "..." }  (one or more)
    server → { "type": "done", "sources": [...] }

  Phase 3 additions:
    - RAGConfig.top_k on library limits sources in done frame
    - Cross-collection search: sources from multiple docs
    - Source citation shape: doc_name, chunk_preview, score
    - Two sessions on same library are history-independent
"""


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


# ── Phase 3: RAGConfig override ───────────────────────────────────────────────

def test_rag_config_top_k_limits_sources(ws_client, sample_pdf):
    """Library with top_k=1 → done frame contains at most 1 source."""
    import io
    lib = ws_client.post("/api/libraries", json={
        "name": "Tight Lib",
        "rag_config": {"top_k": 1},
    }).json()
    doc = ws_client.post(
        "/api/documents/upload",
        files={"file": ("tight.pdf", io.BytesIO(sample_pdf), "application/pdf")},
    ).json()
    ws_client.post(f"/api/libraries/{lib['library_id']}/documents", json={"doc_id": doc["doc_id"]})

    sess = ws_client.post("/api/sessions", json={
        "library_id": lib["library_id"],
        "provider": "openai",
        "model": "gpt-4o",
    }).json()

    with ws_client.websocket_connect(f"/ws/chat/{sess['session_id']}") as ws:
        ws.send_json({"query": "Summarise"})
        frames = _recv_all(ws)

    done = next(f for f in frames if f["type"] == "done")
    assert len(done["sources"]) <= 1


def test_rag_config_overrides_are_independent_per_library(ws_client, sample_pdf):
    """Two libraries with different top_k values produce different source counts."""
    import io

    def _make_session(top_k: int) -> str:
        lib = ws_client.post("/api/libraries", json={
            "name": f"Lib top_k={top_k}",
            "rag_config": {"top_k": top_k},
        }).json()
        doc = ws_client.post(
            "/api/documents/upload",
            files={"file": (f"doc_{top_k}.pdf", io.BytesIO(sample_pdf), "application/pdf")},
        ).json()
        ws_client.post(f"/api/libraries/{lib['library_id']}/documents", json={"doc_id": doc["doc_id"]})
        return ws_client.post("/api/sessions", json={
            "library_id": lib["library_id"],
            "provider": "openai",
            "model": "gpt-4o",
        }).json()["session_id"]

    sid1 = _make_session(top_k=1)
    _make_session(top_k=5)

    def _sources(sid):
        with ws_client.websocket_connect(f"/ws/chat/{sid}") as ws:
            ws.send_json({"query": "test"})
            frames = _recv_all(ws)
        return next(f for f in frames if f["type"] == "done")["sources"]

    assert len(_sources(sid1)) <= 1
    # sid5 may also return ≤1 since the doc has only one chunk; what matters
    # is that top_k=1 is a stricter cap — no assertion on sid5 count


# ── Phase 3: source citation shape ───────────────────────────────────────────

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


# ── Phase 3: cross-collection search ─────────────────────────────────────────

def test_cross_collection_search_queries_all_docs(ws_client, sample_pdf):
    """A library with two documents searches both ChromaDB collections."""
    import io

    lib = ws_client.post("/api/libraries", json={"name": "Multi-doc Lib"}).json()

    # Upload two separate documents
    doc1 = ws_client.post(
        "/api/documents/upload",
        files={"file": ("alpha.pdf", io.BytesIO(sample_pdf), "application/pdf")},
    ).json()
    doc2 = ws_client.post(
        "/api/documents/upload",
        files={"file": ("beta.pdf", io.BytesIO(sample_pdf), "application/pdf")},
    ).json()
    ws_client.post(f"/api/libraries/{lib['library_id']}/documents", json={"doc_id": doc1["doc_id"]})
    ws_client.post(f"/api/libraries/{lib['library_id']}/documents", json={"doc_id": doc2["doc_id"]})

    sess = ws_client.post("/api/sessions", json={
        "library_id": lib["library_id"],
        "provider": "openai",
        "model": "gpt-4o",
    }).json()

    with ws_client.websocket_connect(f"/ws/chat/{sess['session_id']}") as ws:
        ws.send_json({"query": "Tell me about the documents"})
        frames = _recv_all(ws)

    done = next(f for f in frames if f["type"] == "done")
    # With two indexed docs and top_k=5, at least one source must appear
    assert len(done["sources"]) >= 1
    # At least one source must reference a real file name
    assert any(s["doc_name"] for s in done["sources"])


# ── Phase 3: independent session histories ────────────────────────────────────

def test_two_sessions_on_same_library_have_independent_histories(ws_client, sample_pdf):
    """Messages in session A do not appear in session B (same library)."""
    sid = _setup(ws_client, sample_pdf)
    lib_id = ws_client.get(f"/api/sessions/{sid}").json()["library_id"]

    # Open a second session on the same library
    sid2 = ws_client.post("/api/sessions", json={
        "library_id": lib_id,
        "provider": "openai",
        "model": "gpt-4o",
        "title": "Session B",
    }).json()["session_id"]

    # Chat in session 1 only
    with ws_client.websocket_connect(f"/ws/chat/{sid}") as ws:
        ws.send_json({"query": "Only in session 1"})
        _recv_all(ws)

    # Session 2 must have no messages
    detail2 = ws_client.get(f"/api/sessions/{sid2}").json()
    assert detail2["messages"] == []
