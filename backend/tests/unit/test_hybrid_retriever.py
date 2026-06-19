"""
TDD — BM25 sparse scorer + HybridRetriever (dense + sparse fusion)

Contracts:
  BM25            — ranks docs containing query terms above docs without; rarer
                    terms carry more weight (idf).
  HybridRetriever — fuses dense (vector) scores with BM25 scores via min-max
                    normalization weighted by alpha (1.0 = pure dense,
                    0.0 = pure sparse). Candidates come from the full chunk
                    corpus; results are sorted by fused score, truncated to top_k.
  build_retriever — threads RAGConfig.hybrid_alpha into HybridRetriever.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from services.plugins.retrievers import HybridRetriever
from services.plugins.sparse import BM25, tokenize
from services.rag_config import RAGConfig, build_retriever

# ── BM25 ────────────────────────────────────────────────────────────────────

def test_tokenize_lowercases_and_splits():
    assert tokenize("Hello, World! 123") == ["hello", "world", "123"]


def test_bm25_ranks_matching_doc_higher():
    corpus = [["the", "cat", "sat"], ["financial", "report", "quarter"]]
    bm = BM25(corpus)
    scores = bm.scores("cat")
    assert scores[0] > scores[1]
    assert scores[1] == 0.0  # no overlap


def test_bm25_rarer_term_scores_higher():
    # "zebra" appears in 1 doc, "common" appears in all → zebra is more informative.
    corpus = [["common", "zebra"], ["common", "word"], ["common", "thing"]]
    bm = BM25(corpus)
    zebra = bm.scores("zebra")[0]
    common = bm.scores("common")[0]
    assert zebra > common


def test_bm25_empty_corpus_returns_empty():
    assert BM25([]).scores("anything") == []


# ── HybridRetriever fusion ────────────────────────────────────────────────────

def _fake_vs(corpus_texts: list[str], dense_scores: list[float]) -> MagicMock:
    """Build a VectorStore stub whose chunks/query share one (doc_id, chunk_index) keyspace."""
    chunks = [
        {"text": t, "metadata": {"doc_id": "d", "chunk_index": i, "file": "d.pdf"}}
        for i, t in enumerate(corpus_texts)
    ]
    vs = MagicMock()
    vs.get_chunks.return_value = chunks
    vs.query.return_value = [
        {"text": c["text"], "metadata": c["metadata"], "score": dense_scores[i]}
        for i, c in enumerate(chunks)
    ]
    return vs


def test_hybrid_empty_corpus_returns_empty():
    vs = MagicMock()
    vs.get_chunks.return_value = []
    assert HybridRetriever(vs).search("q", 5, ["d"]) == []


def test_hybrid_alpha_one_is_pure_dense_order():
    # Dense favours chunk 0; sparse (keyword) favours chunk 1. alpha=1 → dense wins.
    vs = _fake_vs(["alpha topic text", "keyword keyword keyword"], dense_scores=[0.9, 0.1])
    out = HybridRetriever(vs, alpha=1.0).search("keyword", top_k=2, doc_ids=["d"])
    assert out[0]["text"] == "alpha topic text"


def test_hybrid_alpha_zero_is_pure_sparse_order():
    # Same setup, alpha=0 → BM25 keyword match wins.
    vs = _fake_vs(["alpha topic text", "keyword keyword keyword"], dense_scores=[0.9, 0.1])
    out = HybridRetriever(vs, alpha=0.0).search("keyword", top_k=2, doc_ids=["d"])
    assert out[0]["text"] == "keyword keyword keyword"


def test_hybrid_truncates_to_top_k():
    vs = _fake_vs(["one", "two", "three", "four"], dense_scores=[0.1, 0.2, 0.3, 0.4])
    out = HybridRetriever(vs, alpha=0.5).search("two", top_k=2, doc_ids=["d"])
    assert len(out) == 2
    assert all("score" in r and "text" in r and "metadata" in r for r in out)


def test_hybrid_surfaces_keyword_chunk_dense_misses():
    # Pure dense ranks the keyword chunk LAST; a sparse-leaning blend rescues it.
    vs = _fake_vs(
        ["filler a", "filler b", "the rare_term appears here"],
        dense_scores=[0.8, 0.7, 0.05],
    )
    assert HybridRetriever(vs, alpha=1.0).search("rare_term", 1, ["d"])[0]["text"] == "filler a"
    out = HybridRetriever(vs, alpha=0.4).search("rare_term", top_k=1, doc_ids=["d"])
    assert out[0]["text"] == "the rare_term appears here"


# ── Wiring ────────────────────────────────────────────────────────────────────

def test_build_retriever_threads_alpha():
    vs = MagicMock()
    retriever = build_retriever(RAGConfig(retriever="hybrid", hybrid_alpha=0.25), vs)
    assert isinstance(retriever, HybridRetriever)
    assert retriever._alpha == 0.25
