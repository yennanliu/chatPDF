"""
TDD — Hybrid retrieval end-to-end against a real (ephemeral) ChromaDB.

Exercises VectorStore.get_chunks + query + BM25 fusion together, which the
mock-based unit tests cannot. The fake embedder returns identical vectors, so
dense scores are flat — meaning the lexical (BM25) signal is what discriminates,
which is exactly the case hybrid retrieval is meant to handle.
"""
from __future__ import annotations

from services.plugins.retrievers import HybridRetriever


def _seed(test_vs, doc_id: str, chunks: list[str]) -> None:
    metas = [{"doc_id": doc_id, "chunk_index": i, "file": f"{doc_id}.pdf"} for i in range(len(chunks))]
    test_vs.upsert_chunks(doc_id, chunks, metas)


def test_get_chunks_returns_all_stored_chunks(test_vs):
    _seed(test_vs, "d1", ["alpha beta", "gamma delta"])
    got = test_vs.get_chunks(["d1"])
    assert {c["text"] for c in got} == {"alpha beta", "gamma delta"}
    assert all(c["metadata"]["doc_id"] == "d1" for c in got)


def test_get_chunks_missing_doc_is_ignored(test_vs):
    assert test_vs.get_chunks(["nope"]) == []


def test_hybrid_ranks_keyword_match_first(test_vs):
    _seed(test_vs, "d1", ["the quarterly revenue grew", "an unrelated paragraph about cats"])
    out = HybridRetriever(test_vs, alpha=0.5).search("revenue", top_k=2, doc_ids=["d1"])
    assert out[0]["text"] == "the quarterly revenue grew"
    assert len(out) == 2
