"""
TDD — libraries API

Contract under test:
  POST   /api/libraries                             → 201
  GET    /api/libraries                             → 200 list
  GET    /api/libraries/{id}                        → 200 detail
  PATCH  /api/libraries/{id}                        → 200 updated
  DELETE /api/libraries/{id}                        → 204
  POST   /api/libraries/{id}/documents              → 200, doc added
  DELETE /api/libraries/{id}/documents/{doc_id}     → 200, doc removed
"""


# ── helpers ──────────────────────────────────────────────────────────────────

async def _create_library(client, name="My Lib", description=None):
    resp = await client.post("/api/libraries", json={"name": name, "description": description})
    assert resp.status_code == 201
    return resp.json()


async def _upload_doc(client, sample_pdf, name="doc.pdf"):
    resp = await client.post(
        "/api/documents/upload",
        files={"file": (name, sample_pdf, "application/pdf")},
    )
    assert resp.status_code == 201
    return resp.json()


# ── create ────────────────────────────────────────────────────────────────────

async def test_create_library_returns_201(client):
    data = await _create_library(client, "Research Papers")
    assert "library_id" in data
    assert data["name"] == "Research Papers"
    assert data["documents"] == []
    assert data["rag_config"] == {}


async def test_create_library_with_rag_config(client):
    cfg = {"chunk_size": 600, "top_k": 3}
    resp = await client.post("/api/libraries", json={"name": "Custom", "rag_config": cfg})
    assert resp.status_code == 201
    assert resp.json()["rag_config"]["chunk_size"] == 600


# ── list ──────────────────────────────────────────────────────────────────────

async def test_list_libraries_empty(client):
    resp = await client.get("/api/libraries")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_libraries_returns_all(client):
    await _create_library(client, "Lib A")
    await _create_library(client, "Lib B")
    resp = await client.get("/api/libraries")
    names = [lib["name"] for lib in resp.json()]
    assert "Lib A" in names
    assert "Lib B" in names


# ── get detail ────────────────────────────────────────────────────────────────

async def test_get_library_detail(client):
    created = await _create_library(client, "Detail Lib")
    lib_id = created["library_id"]

    resp = await client.get(f"/api/libraries/{lib_id}")
    assert resp.status_code == 200
    assert resp.json()["library_id"] == lib_id


async def test_get_nonexistent_library_returns_404(client):
    resp = await client.get("/api/libraries/no-such-id")
    assert resp.status_code == 404


# ── update ────────────────────────────────────────────────────────────────────

async def test_rename_library(client):
    lib = await _create_library(client, "Old Name")
    lib_id = lib["library_id"]

    resp = await client.patch(f"/api/libraries/{lib_id}", json={"name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


async def test_update_rag_config(client):
    lib = await _create_library(client)
    lib_id = lib["library_id"]

    resp = await client.patch(f"/api/libraries/{lib_id}", json={"rag_config": {"top_k": 10}})
    assert resp.status_code == 200
    assert resp.json()["rag_config"]["top_k"] == 10


# ── delete ────────────────────────────────────────────────────────────────────

async def test_delete_library(client):
    lib = await _create_library(client)
    lib_id = lib["library_id"]

    resp = await client.delete(f"/api/libraries/{lib_id}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/libraries/{lib_id}")
    assert resp.status_code == 404


async def test_delete_library_does_not_delete_documents(client, sample_pdf):
    lib = await _create_library(client)
    doc = await _upload_doc(client, sample_pdf)

    await client.post(f"/api/libraries/{lib['library_id']}/documents", json={"doc_id": doc["doc_id"]})
    await client.delete(f"/api/libraries/{lib['library_id']}")

    # document still exists
    resp = await client.get("/api/documents")
    assert any(d["doc_id"] == doc["doc_id"] for d in resp.json())


# ── document membership ───────────────────────────────────────────────────────

async def test_add_document_to_library(client, sample_pdf):
    lib = await _create_library(client)
    doc = await _upload_doc(client, sample_pdf)

    resp = await client.post(
        f"/api/libraries/{lib['library_id']}/documents",
        json={"doc_id": doc["doc_id"]},
    )
    assert resp.status_code == 200
    doc_ids = [d["doc_id"] for d in resp.json()["documents"]]
    assert doc["doc_id"] in doc_ids


async def test_add_document_idempotent(client, sample_pdf):
    lib = await _create_library(client)
    doc = await _upload_doc(client, sample_pdf)
    lid, did = lib["library_id"], doc["doc_id"]

    await client.post(f"/api/libraries/{lid}/documents", json={"doc_id": did})
    resp = await client.post(f"/api/libraries/{lid}/documents", json={"doc_id": did})
    assert resp.status_code == 200
    assert len(resp.json()["documents"]) == 1  # not duplicated


async def test_remove_document_from_library(client, sample_pdf):
    lib = await _create_library(client)
    doc = await _upload_doc(client, sample_pdf)
    lid, did = lib["library_id"], doc["doc_id"]

    await client.post(f"/api/libraries/{lid}/documents", json={"doc_id": did})
    resp = await client.delete(f"/api/libraries/{lid}/documents/{did}")
    assert resp.status_code == 200
    assert resp.json()["documents"] == []


async def test_document_can_belong_to_multiple_libraries(client, sample_pdf):
    lib_a = await _create_library(client, "A")
    lib_b = await _create_library(client, "B")
    doc = await _upload_doc(client, sample_pdf)
    did = doc["doc_id"]

    await client.post(f"/api/libraries/{lib_a['library_id']}/documents", json={"doc_id": did})
    await client.post(f"/api/libraries/{lib_b['library_id']}/documents", json={"doc_id": did})

    resp_a = await client.get(f"/api/libraries/{lib_a['library_id']}")
    resp_b = await client.get(f"/api/libraries/{lib_b['library_id']}")

    assert any(d["doc_id"] == did for d in resp_a.json()["documents"])
    assert any(d["doc_id"] == did for d in resp_b.json()["documents"])
