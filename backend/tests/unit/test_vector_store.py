"""
Unit tests — VectorStore (ChromaDB wrapper).

Contracts under test:
  upsert_chunks      — writes chunk text + metadata into a per-doc collection.
  query              — returns [{text, metadata, score}] across docs, sorted by
                       score desc, truncated to top_k; missing/empty docs are
                       skipped (never raise).
  get_chunks         — returns every chunk's {text, metadata} for the docs in
                       scope; missing docs are skipped.
  delete_document    — drops a collection; deleting a missing doc is a no-op.

Runs offline against an EphemeralClient + _FakeEF (zero-vector embeddings →
deterministic distance 0 → score 1.0), so no model download or network.
"""
from __future__ import annotations

import chromadb
import pytest

from tests.conftest import _FakeEF
from vector_store import VectorStore


@pytest.fixture(name="vs")
def vs_fixture() -> VectorStore:
    # EphemeralClient reuses a process-global store, so wipe any collections
    # left by previous tests to keep each test isolated.
    client = chromadb.EphemeralClient()
    for col in client.list_collections():
        client.delete_collection(col.name)
    return VectorStore(client, embedding_fn=_FakeEF())


def _meta(doc_id: str, n: int) -> list[dict]:
    return [{"doc_id": doc_id, "chunk_index": i, "file": f"{doc_id}.pdf"} for i in range(n)]


# ── upsert + get_chunks ───────────────────────────────────────────────────────

def test_upsert_then_get_chunks_returns_all(vs: VectorStore):
    vs.upsert_chunks("d1", ["alpha", "beta"], _meta("d1", 2))
    chunks = vs.get_chunks(["d1"])
    assert {c["text"] for c in chunks} == {"alpha", "beta"}
    assert all(c["metadata"]["doc_id"] == "d1" for c in chunks)


def test_get_chunks_spans_multiple_docs(vs: VectorStore):
    vs.upsert_chunks("d1", ["a"], _meta("d1", 1))
    vs.upsert_chunks("d2", ["b", "c"], _meta("d2", 2))
    assert len(vs.get_chunks(["d1", "d2"])) == 3


def test_get_chunks_skips_missing_doc(vs: VectorStore):
    vs.upsert_chunks("d1", ["a"], _meta("d1", 1))
    # "ghost" was never ingested → silently skipped, not an error.
    assert len(vs.get_chunks(["d1", "ghost"])) == 1


def test_get_chunks_all_missing_returns_empty(vs: VectorStore):
    assert vs.get_chunks(["ghost"]) == []


def test_upsert_is_idempotent_on_same_ids(vs: VectorStore):
    vs.upsert_chunks("d1", ["a", "b"], _meta("d1", 2))
    vs.upsert_chunks("d1", ["a", "b"], _meta("d1", 2))  # same ids → overwrite, not append
    assert len(vs.get_chunks(["d1"])) == 2


# ── query ─────────────────────────────────────────────────────────────────────

def test_query_returns_scored_results(vs: VectorStore):
    vs.upsert_chunks("d1", ["hello world", "foo bar"], _meta("d1", 2))
    results = vs.query(["d1"], "hello", top_k=5)
    assert len(results) == 2
    assert all(set(r) == {"text", "metadata", "score"} for r in results)


def test_query_truncates_to_top_k(vs: VectorStore):
    vs.upsert_chunks("d1", ["a", "b", "c", "d"], _meta("d1", 4))
    assert len(vs.query(["d1"], "x", top_k=2)) == 2


def test_query_sorted_by_score_desc(vs: VectorStore):
    vs.upsert_chunks("d1", ["a", "b", "c"], _meta("d1", 3))
    scores = [r["score"] for r in vs.query(["d1"], "x", top_k=3)]
    assert scores == sorted(scores, reverse=True)


def test_query_missing_doc_returns_empty(vs: VectorStore):
    # get_collection raises for an unknown name → caught, no results.
    assert vs.query(["ghost"], "hello") == []


def test_query_skips_empty_collection(vs: VectorStore):
    # Collection exists (created lazily) but holds no chunks → skipped, not raised.
    vs._collection("empty")
    assert vs.query(["empty"], "hello") == []


def test_query_mixes_present_and_missing_docs(vs: VectorStore):
    vs.upsert_chunks("d1", ["a"], _meta("d1", 1))
    assert len(vs.query(["d1", "ghost"], "x", top_k=5)) == 1


# ── delete_document ───────────────────────────────────────────────────────────

def test_delete_document_removes_chunks(vs: VectorStore):
    vs.upsert_chunks("d1", ["a"], _meta("d1", 1))
    vs.delete_document("d1")
    assert vs.get_chunks(["d1"]) == []


def test_delete_missing_document_is_noop(vs: VectorStore):
    # Must not raise even though the collection never existed.
    vs.delete_document("ghost")
