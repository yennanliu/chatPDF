from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vector_store import VectorStore
    from services.plugins.base import BaseChunker, BaseReranker, BaseRetriever


@dataclass
class RAGConfig:
    # chunking
    chunk_size: int = 800
    chunk_overlap: int = 100
    chunker: str = "recursive"       # recursive | sentence | semantic

    # retrieval
    top_k: int = 5
    retriever: str = "dense"         # dense | hybrid
    hybrid_alpha: float = 0.5

    # reranking
    reranker: str = "none"           # none | cross_encoder
    rerank_top_n: int = 3

    # embedding
    embedder: str = "local"          # local | openai

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> RAGConfig:
        data = json.loads(raw) if raw and raw.strip() not in ("", "{}") else {}
        valid = {k for k in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in valid})


# ── Plugin registries ─────────────────────────────────────────────────────────

def _chunker_registry() -> dict:
    from services.plugins.chunkers import RecursiveChunker, SentenceChunker
    return {"recursive": RecursiveChunker, "sentence": SentenceChunker}


def _retriever_registry() -> dict:
    from services.plugins.retrievers import DenseRetriever, HybridRetriever
    return {"dense": DenseRetriever, "hybrid": HybridRetriever}


def _reranker_registry() -> dict:
    from services.plugins.rerankers import CrossEncoderReranker, NoopReranker
    return {"none": NoopReranker, "cross_encoder": CrossEncoderReranker}


def build_chunker(cfg: RAGConfig) -> BaseChunker:
    cls = _chunker_registry()[cfg.chunker]
    if cfg.chunker == "sentence":
        return cls(chunk_size=cfg.chunk_size)
    return cls(chunk_size=cfg.chunk_size, chunk_overlap=cfg.chunk_overlap)


def build_retriever(cfg: RAGConfig, vs: VectorStore) -> BaseRetriever:
    cls = _retriever_registry()[cfg.retriever]
    return cls(vs)


def build_reranker(cfg: RAGConfig) -> BaseReranker:
    cls = _reranker_registry()[cfg.reranker]
    return cls()
