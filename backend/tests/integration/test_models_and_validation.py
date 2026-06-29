"""TDD — model catalog endpoint (§4.3) and provider validation."""


async def test_models_endpoint_returns_catalog(client):
    resp = await client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"openai", "google", "anthropic"}
    assert all(isinstance(v, list) and v for v in data.values())


async def test_session_rejects_unknown_provider(client, sample_pdf):
    doc_id = (await client.post(
        "/api/documents/upload",
        files={"file": ("p.pdf", sample_pdf, "application/pdf")},
    )).json()["doc_id"]

    resp = await client.post("/api/sessions", json={
        "doc_ids": [doc_id], "provider": "cohere", "model": "command-r",
    })
    assert resp.status_code == 422


async def test_session_accepts_known_provider(client, sample_pdf):
    doc_id = (await client.post(
        "/api/documents/upload",
        files={"file": ("p.pdf", sample_pdf, "application/pdf")},
    )).json()["doc_id"]

    resp = await client.post("/api/sessions", json={
        "doc_ids": [doc_id], "provider": "anthropic", "model": "claude-opus-4-8",
    })
    assert resp.status_code == 201
