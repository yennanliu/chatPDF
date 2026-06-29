from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.plugins.base import BaseChunker, BaseReranker, BaseRetriever
    from vector_store import VectorStore


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
    min_score: float = 0.0           # drop retrieved chunks below this score (0 = off)
    multi_query: int = 0             # generate N query paraphrases for recall (0 = off)

    # reranking
    reranker: str = "none"           # none | cross_encoder
    rerank_top_n: int = 3

    # embedding
    embedder: str = "local"          # local | openai

    # generation
    temperature: float = 0.0
    system_prompt: str | None = None     # override the default RAG system prompt
    max_context_tokens: int = 8000       # budget for retrieved context + history

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> RAGConfig:
        data = json.loads(raw) if raw and raw.strip() not in ("", "{}") else {}
        valid = {k for k in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in valid})


# ── Plugin registries ─────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _chunker_registry() -> dict:
    from services.plugins.chunkers import RecursiveChunker, SemanticChunker, SentenceChunker
    return {
        "recursive": RecursiveChunker,
        "sentence": SentenceChunker,
        "semantic": SemanticChunker,
    }


def available_chunkers() -> list[str]:
    return list(_chunker_registry())


@lru_cache(maxsize=1)
def _retriever_registry() -> dict:
    from services.plugins.retrievers import DenseRetriever, HybridRetriever
    return {"dense": DenseRetriever, "hybrid": HybridRetriever}


@lru_cache(maxsize=1)
def _reranker_registry() -> dict:
    from services.plugins.rerankers import CrossEncoderReranker, NoopReranker
    return {"none": NoopReranker, "cross_encoder": CrossEncoderReranker}


def build_chunker(cfg: RAGConfig) -> BaseChunker:
    cls = _chunker_registry()[cfg.chunker]
    return cls(chunk_size=cfg.chunk_size, chunk_overlap=cfg.chunk_overlap)


def build_retriever(cfg: RAGConfig, vs: VectorStore) -> BaseRetriever:
    cls = _retriever_registry()[cfg.retriever]
    if cfg.retriever == "hybrid":
        return cls(vs, alpha=cfg.hybrid_alpha)
    return cls(vs)


def build_reranker(cfg: RAGConfig) -> BaseReranker:
    cls = _reranker_registry()[cfg.reranker]
    return cls()
