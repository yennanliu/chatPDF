"""
TDD — sessions API

Contract under test:
  POST   /api/sessions            → 201 (takes doc_ids + provider/model + optional rag_config)
  GET    /api/sessions            → 200 list
  GET    /api/sessions/{id}       → 200 detail + messages
  PATCH  /api/sessions/{id}       → 200 renamed
  DELETE /api/sessions/{id}       → 204
  Session carries its own documents and rag_config (no Library layer).
"""


# ── helpers ───────────────────────────────────────────────────────────────────

async def _upload_doc(client, name="t.pdf", sample_pdf=b"%PDF-1.4"):
    r = await client.post(
        "/api/documents/upload",
        files={"file": (name, sample_pdf, "application/pdf")},
    )
    assert r.status_code == 201
    return r.json()["doc_id"]


async def _make_session(client, doc_ids, title=None, rag_config=None):
    body = {"doc_ids": doc_ids, "provider": "openai", "model": "gpt-4o"}
    if title:
        body["title"] = title
    if rag_config is not None:
        body["rag_config"] = rag_config
    r = await client.post("/api/sessions", json=body)
    assert r.status_code == 201
    return r.json()


# ── create ────────────────────────────────────────────────────────────────────

async def test_create_session_returns_201(client, sample_pdf):
    doc_id = await _upload_doc(client, sample_pdf=sample_pdf)
    sess = await _make_session(client, [doc_id])
    assert "session_id" in sess
    assert sess["provider"] == "openai"
    assert sess["model"] == "gpt-4o"
    assert sess["title"] == "New Chat"
    assert [d["doc_id"] for d in sess["documents"]] == [doc_id]


async def test_create_session_custom_title(client, sample_pdf):
    doc_id = await _upload_doc(client, sample_pdf=sample_pdf)
    sess = await _make_session(client, [doc_id], title="My research chat")
    assert sess["title"] == "My research chat"


async def test_create_session_persists_rag_config(client, sample_pdf):
    doc_id = await _upload_doc(client, sample_pdf=sample_pdf)
    sess = await _make_session(client, [doc_id], rag_config={"top_k": 3, "retriever": "hybrid"})
    assert sess["rag_config"]["top_k"] == 3
    assert sess["rag_config"]["retriever"] == "hybrid"


async def test_create_session_no_docs_ok(client):
    sess = await _make_session(client, [])
    assert sess["documents"] == []


async def test_create_session_unknown_doc_404(client):
    r = await client.post("/api/sessions", json={
        "doc_ids": ["no-such-doc"],
        "provider": "openai",
        "model": "gpt-4o",
    })
    assert r.status_code == 404


# ── list ──────────────────────────────────────────────────────────────────────

async def test_list_sessions_empty(client):
    r = await client.get("/api/sessions")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_sessions_returns_all(client, sample_pdf):
    doc_id = await _upload_doc(client, sample_pdf=sample_pdf)
    await _make_session(client, [doc_id], "S1")
    await _make_session(client, [doc_id], "S2")
    r = await client.get("/api/sessions")
    titles = [s["title"] for s in r.json()]
    assert "S1" in titles and "S2" in titles


# ── detail + history ──────────────────────────────────────────────────────────

async def test_get_session_detail(client, sample_pdf):
    doc_id = await _upload_doc(client, sample_pdf=sample_pdf)
    sess = await _make_session(client, [doc_id])
    r = await client.get(f"/api/sessions/{sess['session_id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["session_id"] == sess["session_id"]
    assert data["messages"] == []
    assert [d["doc_id"] for d in data["documents"]] == [doc_id]


async def test_get_nonexistent_session_404(client):
    r = await client.get("/api/sessions/no-such-id")
    assert r.status_code == 404


# ── rename / delete ───────────────────────────────────────────────────────────

async def test_rename_session(client, sample_pdf):
    doc_id = await _upload_doc(client, sample_pdf=sample_pdf)
    sess = await _make_session(client, [doc_id])
    sid = sess["session_id"]

    r = await client.patch(f"/api/sessions/{sid}", json={"title": "Renamed"})
    assert r.status_code == 200
    assert r.json()["title"] == "Renamed"


async def test_delete_session(client, sample_pdf):
    doc_id = await _upload_doc(client, sample_pdf=sample_pdf)
    sess = await _make_session(client, [doc_id])
    sid = sess["session_id"]

    r = await client.delete(f"/api/sessions/{sid}")
    assert r.status_code == 204

    r = await client.get(f"/api/sessions/{sid}")
    assert r.status_code == 404


async def test_delete_all_sessions(client, sample_pdf):
    doc_id = await _upload_doc(client, sample_pdf=sample_pdf)
    await _make_session(client, [doc_id], "A")
    await _make_session(client, [doc_id], "B")

    r = await client.delete("/api/sessions")
    assert r.status_code == 204
    assert (await client.get("/api/sessions")).json() == []


async def test_delete_all_sessions_empty_ok(client):
    r = await client.delete("/api/sessions")
    assert r.status_code == 204


async def test_two_sessions_share_docs_independently(client, sample_pdf):
    doc_id = await _upload_doc(client, sample_pdf=sample_pdf)
    s1 = await _make_session(client, [doc_id], "Chat A")
    s2 = await _make_session(client, [doc_id], "Chat B")
    assert s1["session_id"] != s2["session_id"]
    assert [d["doc_id"] for d in s1["documents"]] == [d["doc_id"] for d in s2["documents"]]
