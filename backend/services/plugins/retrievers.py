from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BaseRetriever

if TYPE_CHECKING:
    from vector_store import VectorStore


class DenseRetriever(BaseRetriever):
    def __init__(self, vs: VectorStore) -> None:
        self._vs = vs

    def search(self, query: str, top_k: int, doc_ids: list[str]) -> list[dict]:
        return self._vs.query(doc_ids, query, top_k)


class HybridRetriever(BaseRetriever):
    """Combines dense + BM25 sparse retrieval — registered for future use."""

    def __init__(self, vs: VectorStore, alpha: float = 0.5) -> None:
        self._vs = vs
        self._alpha = alpha

    def search(self, query: str, top_k: int, doc_ids: list[str]) -> list[dict]:
        # Phase 3+: implement BM25 merge; fall back to dense for now
        return self._vs.query(doc_ids, query, top_k)
