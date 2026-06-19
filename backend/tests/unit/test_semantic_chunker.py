"""
TDD — SemanticChunker unit tests

Contract:
  SemanticChunker splits text into sentences, embeds each, and starts a new chunk
  wherever the cosine distance between consecutive sentences crosses a percentile
  threshold (a topic shift). `chunk_size` is a hard cap so chunks never grow
  unbounded. The embedder is injectable so tests stay offline.
"""
from __future__ import annotations

from services.plugins.base import BaseEmbedder
from services.plugins.chunkers import SemanticChunker
from services.rag_config import RAGConfig, available_chunkers, build_chunker


class _StubEmbedder(BaseEmbedder):
    """Maps each sentence to a fixed vector by keyword, so semantic breaks are deterministic."""

    def __init__(self, mapping: dict[str, list[float]], default: list[float] | None = None) -> None:
        self._mapping = mapping
        self._default = default or [0.0, 0.0]

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for t in texts:
            vec = self._default
            for key, v in self._mapping.items():
                if key in t:
                    vec = v
                    break
            out.append(vec)
        return out


# ── Basic contract ──────────────────────────────────────────────────────────

def test_semantic_chunker_empty_text_returns_empty():
    chunker = SemanticChunker(embedder=_StubEmbedder({}))
    assert chunker.split("") == []


def test_semantic_chunker_single_sentence_single_chunk():
    chunker = SemanticChunker(embedder=_StubEmbedder({}))
    assert chunker.split("Only one sentence here.") == ["Only one sentence here."]


def test_semantic_chunker_breaks_on_topic_shift():
    # Two "cat" sentences then two "stock" sentences — the break is between topics.
    embedder = _StubEmbedder({"cat": [1.0, 0.0], "stock": [0.0, 1.0]})
    text = "The cat slept. The cat purred. The stock rose. The stock fell."
    chunks = SemanticChunker(chunk_size=10_000, breakpoint_percentile=80, embedder=embedder).split(text)

    assert len(chunks) == 2
    assert "cat" in chunks[0] and "stock" not in chunks[0]
    assert "stock" in chunks[1] and "cat" not in chunks[1]


def test_semantic_chunker_size_cap_forces_split():
    # All sentences identical topic → no semantic break, but tiny chunk_size forces splits.
    embedder = _StubEmbedder({"same": [1.0, 0.0]})
    text = "Same topic one. Same topic two. Same topic three. Same topic four."
    chunks = SemanticChunker(chunk_size=20, breakpoint_percentile=95, embedder=embedder).split(text)

    assert len(chunks) > 1
    assert all(c.strip() for c in chunks)


def test_semantic_chunker_no_break_keeps_one_chunk():
    embedder = _StubEmbedder({"same": [1.0, 0.0]})
    text = "Same topic one. Same topic two. Same topic three."
    chunks = SemanticChunker(chunk_size=10_000, breakpoint_percentile=95, embedder=embedder).split(text)
    assert len(chunks) == 1


def test_semantic_chunker_lazy_loads_local_embedder():
    chunker = SemanticChunker()
    assert chunker._embedder is None  # not built until first split()


def test_semantic_chunker_builds_local_embedder_on_first_split(monkeypatch):
    built = _StubEmbedder({"cat": [1.0, 0.0], "stock": [0.0, 1.0]})
    import services.plugins.embedders as embedders

    monkeypatch.setattr(embedders, "LocalEmbedder", lambda: built)
    chunker = SemanticChunker(chunk_size=10_000, breakpoint_percentile=80)
    chunks = chunker.split("The cat slept. The cat purred. The stock rose.")

    assert chunker._embedder is built  # lazily built and cached
    assert len(chunks) == 2


# ── Registry wiring ───────────────────────────────────────────────────────────

def test_semantic_registered_in_chunker_registry():
    assert "semantic" in available_chunkers()


def test_build_chunker_returns_semantic_instance():
    cfg = RAGConfig(chunker="semantic", chunk_size=512, chunk_overlap=0)
    chunker = build_chunker(cfg)
    assert isinstance(chunker, SemanticChunker)
    assert chunker.chunk_size == 512
