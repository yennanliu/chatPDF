"""TDD — RAG evaluation API: gold-set CRUD + run (retrieval and LLM-judge).

Retrieval runs deterministically against the ephemeral vector store. The judge
path uses a fake gateway that emits valid judge JSON, with a fake API key
monkeypatched in so the router's key gate passes.
"""
from __future__ import annotations

import pytest

import config
from main import app
from services.llm_gateway import LLMGateway, get_llm_gateway
from tests.conftest import _FakeChatModel


@pytest.fixture(name="gold_path")
def gold_path_fixture(tmp_path, monkeypatch):
    path = tmp_path / "gold.json"
    monkeypatch.setattr(config.settings, "eval_gold_path", str(path))
    return path


def _seed(test_vs, doc_id, chunks):
    metas = [{"doc_id": doc_id, "chunk_index": i, "file": f"{doc_id}.pdf"} for i in range(len(chunks))]
    test_vs.upsert_chunks(doc_id, chunks, metas)


# ── gold CRUD ─────────────────────────────────────────────────────────────────

async def test_gold_empty_by_default(client, gold_path):
    r = await client.get("/api/eval/gold")
    assert r.status_code == 200
    assert r.json() == {"items": []}


async def test_gold_put_then_get_roundtrips(client, gold_path):
    items = [{
        "id": "q1",
        "question": "What retry policy is used?",
        "doc_ids": ["d1"],
        "relevant_substrings": ["exponential backoff"],
        "reference_answer": "Exponential backoff.",
    }]
    put = await client.put("/api/eval/gold", json={"items": items})
    assert put.status_code == 200
    got = await client.get("/api/eval/gold")
    assert got.json()["items"][0]["question"] == "What retry policy is used?"
    assert gold_path.exists()


async def test_presets_listed(client):
    r = await client.get("/api/eval/presets")
    presets = r.json()["presets"]
    labels = [p["label"] for p in presets]
    assert "dense + gate" in labels
    # The no-gate variant explicitly disables the relevance gate for comparison.
    no_gate = next(p for p in presets if p["label"] == "dense (no gate)")
    assert no_gate["overrides"]["relevance_gate"] is None


async def test_tracing_status_disabled_by_default(client, monkeypatch):
    monkeypatch.setattr(config.settings, "langfuse_public_key", "")
    monkeypatch.setattr(config.settings, "langfuse_secret_key", "")
    r = await client.get("/api/eval/tracing")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False
    assert body["host"] is None


# ── run history ───────────────────────────────────────────────────────────────

async def test_history_empty_by_default(client):
    r = await client.get("/api/eval/history")
    assert r.status_code == 200
    assert r.json() == {"runs": []}


async def test_run_is_persisted_to_history(client, test_vs, gold_path):
    _seed(test_vs, "dh", ["the ingest worker uses exponential backoff"])
    await client.put("/api/eval/gold", json={"items": [{
        "question": "retry policy?", "doc_ids": ["dh"],
        "relevant_substrings": ["exponential backoff"],
    }]})
    await client.post("/api/eval/run", json={
        "configs": [{"label": "dense", "overrides": {"retriever": "dense"}}],
        "k": 5,
    })
    r = await client.get("/api/eval/history")
    runs = r.json()["runs"]
    assert len(runs) == 1
    assert runs[0]["summary"][0]["label"] == "dense"
    assert runs[0]["summary"][0]["metrics"]["hit@k"] == 1.0


# ── run: retrieval only ───────────────────────────────────────────────────────

async def test_run_retrieval_detects_hit(client, test_vs, gold_path):
    _seed(test_vs, "d1", [
        "an unrelated preamble paragraph",
        "the ingest worker uses exponential backoff capped at 5 retries",
    ])
    await client.put("/api/eval/gold", json={"items": [{
        "id": "q1",
        "question": "retry policy?",
        "doc_ids": ["d1"],
        "relevant_substrings": ["exponential backoff"],
    }]})

    r = await client.post("/api/eval/run", json={
        "configs": [{"label": "dense", "overrides": {"retriever": "dense"}}],
        "k": 5,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["judge_enabled"] is False
    assert body["n_questions"] == 1
    res = body["results"][0]
    assert res["metrics"]["hit@k"] == 1.0
    assert res["per_question"][0]["hit"] is True
    # the relevant chunk is flagged in the drill-down
    assert any(c["relevant"] for c in res["per_question"][0]["retrieved"])


async def test_run_reports_miss_when_substring_absent(client, test_vs, gold_path):
    _seed(test_vs, "d2", ["nothing about the topic here"])
    await client.put("/api/eval/gold", json={"items": [{
        "question": "q", "doc_ids": ["d2"], "relevant_substrings": ["unobtainium"],
    }]})
    r = await client.post("/api/eval/run", json={"configs": [{"label": "dense", "overrides": {}}]})
    assert r.json()["results"][0]["metrics"]["hit@k"] == 0.0


async def test_judge_disabled_without_key(client, test_vs, gold_path, monkeypatch):
    # No keys configured → judge requested but gracefully skipped with a warning.
    monkeypatch.setattr(config.settings, "openai_api_key", "")
    monkeypatch.setattr(config.settings, "google_api_key", "")
    monkeypatch.setattr(config.settings, "gemini_api_key", "")
    monkeypatch.setattr(config.settings, "anthropic_api_key", "")
    _seed(test_vs, "d3", ["exponential backoff is used"])
    await client.put("/api/eval/gold", json={"items": [{
        "question": "q", "doc_ids": ["d3"], "relevant_substrings": ["backoff"],
    }]})
    r = await client.post("/api/eval/run", json={
        "configs": [{"label": "dense", "overrides": {}}],
        "judge": {"enabled": True},
    })
    body = r.json()
    assert body["judge_enabled"] is False
    assert body["warnings"]
    assert body["results"][0]["metrics"]["faithfulness"] is None


# ── run: with LLM judge (fake gateway returns valid judge JSON) ────────────────

class _JsonGateway(LLMGateway):
    def get_llm(self, provider, model, temperature=0.0):
        # One canned blob serving both judges — each parser extracts only its own
        # keys (judge_answer: faithfulness/answer_relevance; judge_context: the
        # context_* pair), ignoring the extras.
        return _FakeChatModel(response=(
            '{"faithfulness": 0.9, "answer_relevance": 0.8, '
            '"context_precision": 0.7, "context_recall": 0.6, "answer_correctness": 0.95}'
        ))


class _GarbageJudgeGateway(LLMGateway):
    """Answers fine but the judge returns unparseable output → scores are None."""
    def get_llm(self, provider, model, temperature=0.0):
        return _FakeChatModel(response="the judge refused to produce JSON")


async def test_run_with_judge_scores_generation(client, test_vs, gold_path, monkeypatch):
    monkeypatch.setattr(config.settings, "anthropic_api_key", "test-key")
    # Override the gateway for this test (client fixture clears overrides at teardown).
    app.dependency_overrides[get_llm_gateway] = lambda: _JsonGateway()

    _seed(test_vs, "d4", ["the ingest worker uses exponential backoff"])
    await client.put("/api/eval/gold", json={"items": [{
        "question": "retry policy?", "doc_ids": ["d4"],
        "relevant_substrings": ["exponential backoff"],
        "reference_answer": "The ingest worker retries with exponential backoff.",
    }]})
    r = await client.post("/api/eval/run", json={
        "configs": [{"label": "dense", "overrides": {}}],
        "judge": {"enabled": True, "answer_provider": "anthropic", "judge_provider": "anthropic"},
    })
    body = r.json()
    assert body["judge_enabled"] is True
    res = body["results"][0]
    assert res["metrics"]["faithfulness"] == 0.9
    assert res["metrics"]["answer_relevance"] == 0.8
    # Label-free retrieval-quality metrics scored by the context judge.
    assert res["metrics"]["context_precision"] == 0.7
    assert res["metrics"]["context_recall"] == 0.6
    # Answer correctness vs. the gold reference answer.
    assert res["metrics"]["answer_correctness"] == 0.95
    assert res["per_question"][0]["answer"] is not None
    assert res["per_question"][0]["context_precision"] == 0.7


async def test_run_warns_when_judge_yields_no_scores(client, test_vs, gold_path, monkeypatch):
    monkeypatch.setattr(config.settings, "anthropic_api_key", "test-key")
    app.dependency_overrides[get_llm_gateway] = lambda: _GarbageJudgeGateway()

    _seed(test_vs, "d5", ["the ingest worker uses exponential backoff"])
    await client.put("/api/eval/gold", json={"items": [{
        "question": "retry policy?", "doc_ids": ["d5"],
        "relevant_substrings": ["exponential backoff"],
    }]})
    r = await client.post("/api/eval/run", json={
        "configs": [{"label": "dense", "overrides": {}}],
        "judge": {"enabled": True, "answer_provider": "anthropic", "judge_provider": "anthropic"},
    })
    body = r.json()
    # Retrieval still scored; judge produced nothing → a warning explains the blanks.
    assert body["results"][0]["metrics"]["hit@k"] == 1.0
    assert body["results"][0]["metrics"]["faithfulness"] is None
    assert any("Judge produced no scores" in w for w in body["warnings"])
