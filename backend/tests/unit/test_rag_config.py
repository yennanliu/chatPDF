"""
TDD — RAGConfig unit tests

Contract under test:
  - RAGConfig has correct defaults
  - JSON round-trip is lossless
  - from_json handles empty / partial JSON
  - Plugin builders return the right concrete types
"""
from unittest.mock import MagicMock

from services.rag_config import RAGConfig, build_chunker, build_reranker, build_retriever
from services.plugins.chunkers import RecursiveChunker, SentenceChunker
from services.plugins.rerankers import NoopReranker
from services.plugins.retrievers import DenseRetriever, HybridRetriever


# ── RAGConfig ─────────────────────────────────────────────────────────────────

def test_defaults():
    cfg = RAGConfig()
    assert cfg.chunk_size == 800
    assert cfg.chunk_overlap == 100
    assert cfg.chunker == "recursive"
    assert cfg.top_k == 5
    assert cfg.retriever == "dense"
    assert cfg.reranker == "none"
    assert cfg.embedder == "local"


def test_json_round_trip():
    cfg = RAGConfig(chunk_size=600, top_k=3, reranker="none")
    restored = RAGConfig.from_json(cfg.to_json())
    assert restored.chunk_size == 600
    assert restored.top_k == 3
    assert restored.reranker == "none"


def test_from_empty_json_uses_defaults():
    assert RAGConfig.from_json("{}") == RAGConfig()
    assert RAGConfig.from_json("") == RAGConfig()


def test_from_partial_json():
    cfg = RAGConfig.from_json('{"chunk_size": 400}')
    assert cfg.chunk_size == 400
    assert cfg.top_k == 5  # default


def test_unknown_keys_ignored():
    cfg = RAGConfig.from_json('{"chunk_size": 500, "future_key": "ignore"}')
    assert cfg.chunk_size == 500


# ── Plugin builders ───────────────────────────────────────────────────────────

def test_build_recursive_chunker():
    cfg = RAGConfig(chunker="recursive", chunk_size=400, chunk_overlap=50)
    chunker = build_chunker(cfg)
    assert isinstance(chunker, RecursiveChunker)
    assert chunker.chunk_size == 400


def test_build_sentence_chunker():
    cfg = RAGConfig(chunker="sentence")
    assert isinstance(build_chunker(cfg), SentenceChunker)


def test_build_noop_reranker():
    assert isinstance(build_reranker(RAGConfig()), NoopReranker)


# ── RecursiveChunker ──────────────────────────────────────────────────────────

def test_recursive_chunker_splits_long_text():
    chunker = RecursiveChunker(chunk_size=50, chunk_overlap=10)
    chunks = chunker.split("a" * 300)
    assert len(chunks) > 1
    assert all(len(c) <= 50 for c in chunks)


def test_recursive_chunker_overlap():
    chunker = RecursiveChunker(chunk_size=10, chunk_overlap=3)
    text = "abcdefghijklmnopqrstuvwxyz"
    chunks = chunker.split(text)
    # second chunk should start before first chunk ends (overlap)
    assert chunks[1][0] == text[7]  # step = 10 - 3 = 7


def test_recursive_chunker_short_text_single_chunk():
    chunker = RecursiveChunker(chunk_size=500)
    chunks = chunker.split("hello world")
    assert chunks == ["hello world"]


def test_recursive_chunker_ignores_blank_chunks():
    chunker = RecursiveChunker(chunk_size=10, chunk_overlap=0)
    chunks = chunker.split("   ")
    assert chunks == []


# ── build_retriever ───────────────────────────────────────────────────────────

def test_build_retriever_returns_dense():
    vs = MagicMock()
    r = build_retriever(RAGConfig(retriever="dense"), vs)
    assert isinstance(r, DenseRetriever)


def test_build_retriever_returns_hybrid():
    vs = MagicMock()
    r = build_retriever(RAGConfig(retriever="hybrid"), vs)
    assert isinstance(r, HybridRetriever)


# ── NoopReranker ─────────────────────────────────────────────────────────────

def test_noop_reranker_preserves_order():
    reranker = NoopReranker()
    chunks = [{"text": "a", "score": 0.9}, {"text": "b", "score": 0.7}]
    assert reranker.rerank("q", chunks) == chunks
