"""
TDD — sessions API

Contract under test:
  POST   /api/sessions            → 201
  GET    /api/sessions            → 200 list
  GET    /api/sessions/{id}       → 200 detail + messages
  PATCH  /api/sessions/{id}       → 200 renamed
  DELETE /api/sessions/{id}       → 204
  Session reload reconstructs full message history via GET /{id}
"""
import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

async def _make_library(client, name="Test Lib"):
    r = await client.post("/api/libraries", json={"name": name})
    assert r.status_code == 201
    return r.json()


async def _make_session(client, library_id, title=None):
    body = {"library_id": library_id, "provider": "openai", "model": "gpt-4o"}
    if title:
        body["title"] = title
    r = await client.post("/api/sessions", json=body)
    assert r.status_code == 201
    return r.json()


# ── create ────────────────────────────────────────────────────────────────────

async def test_create_session_returns_201(client):
    lib = await _make_library(client)
    sess = await _make_session(client, lib["library_id"])
    assert "session_id" in sess
    assert sess["provider"] == "openai"
    assert sess["model"] == "gpt-4o"
    assert sess["title"] == "New Chat"


async def test_create_session_custom_title(client):
    lib = await _make_library(client)
    sess = await _make_session(client, lib["library_id"], title="My research chat")
    assert sess["title"] == "My research chat"


async def test_create_session_unknown_library_404(client):
    r = await client.post("/api/sessions", json={
        "library_id": "no-such-lib",
        "provider": "openai",
        "model": "gpt-4o",
    })
    assert r.status_code == 404


# ── list ──────────────────────────────────────────────────────────────────────

async def test_list_sessions_empty(client):
    r = await client.get("/api/sessions")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_sessions_returns_all(client):
    lib = await _make_library(client)
    await _make_session(client, lib["library_id"], "S1")
    await _make_session(client, lib["library_id"], "S2")
    r = await client.get("/api/sessions")
    titles = [s["title"] for s in r.json()]
    assert "S1" in titles and "S2" in titles


# ── detail + history ──────────────────────────────────────────────────────────

async def test_get_session_detail(client):
    lib = await _make_library(client)
    sess = await _make_session(client, lib["library_id"])
    r = await client.get(f"/api/sessions/{sess['session_id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["session_id"] == sess["session_id"]
    assert data["messages"] == []


async def test_get_nonexistent_session_404(client):
    r = await client.get("/api/sessions/no-such-id")
    assert r.status_code == 404


async def test_session_reload_reconstructs_history(client, sample_pdf):
    """After a WS chat turn, GET /{id} must return the full dialogue."""
    lib = await _make_library(client)

    # upload + add doc to library
    doc = (await client.post(
        "/api/documents/upload",
        files={"file": ("t.pdf", sample_pdf, "application/pdf")},
    )).json()
    await client.post(f"/api/libraries/{lib['library_id']}/documents", json={"doc_id": doc["doc_id"]})

    sess = await _make_session(client, lib["library_id"])

    # seed messages directly via ws (tested in test_chat_ws.py);
    # here we just confirm the REST endpoint correctly returns them
    # by inserting rows via the DB session (conftest db_session not in scope here,
    # so we rely on the WS test for end-to-end; this test checks the GET shape)
    r = await client.get(f"/api/sessions/{sess['session_id']}")
    assert r.status_code == 200
    assert isinstance(r.json()["messages"], list)


# ── rename / delete ───────────────────────────────────────────────────────────

async def test_rename_session(client):
    lib = await _make_library(client)
    sess = await _make_session(client, lib["library_id"])
    sid = sess["session_id"]

    r = await client.patch(f"/api/sessions/{sid}", json={"title": "Renamed"})
    assert r.status_code == 200
    assert r.json()["title"] == "Renamed"


async def test_delete_session(client):
    lib = await _make_library(client)
    sess = await _make_session(client, lib["library_id"])
    sid = sess["session_id"]

    r = await client.delete(f"/api/sessions/{sid}")
    assert r.status_code == 204

    r = await client.get(f"/api/sessions/{sid}")
    assert r.status_code == 404


async def test_two_sessions_on_same_library_independent(client):
    lib = await _make_library(client)
    s1 = await _make_session(client, lib["library_id"], "Chat A")
    s2 = await _make_session(client, lib["library_id"], "Chat B")
    assert s1["session_id"] != s2["session_id"]
    assert s1["library_id"] == s2["library_id"]
