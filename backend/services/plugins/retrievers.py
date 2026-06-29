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
    """Fuses dense (vector) retrieval with BM25 sparse retrieval.

    Dense embeddings capture meaning but miss exact terms (names, codes, IDs);
    BM25 captures exact lexical overlap. Both score sets are min-max normalized
    to [0, 1] and blended:

        fused = alpha * dense_norm + (1 - alpha) * sparse_norm

    so alpha=1.0 is pure dense, alpha=0.0 is pure sparse. Candidates are the full
    chunk corpus for the documents in scope; results are sorted by fused score
    and truncated to top_k.
    """

    def __init__(self, vs: VectorStore, alpha: float = 0.5) -> None:
        self._vs = vs
        self._alpha = alpha

    # Build cost is O(corpus); cache the index so repeated queries over the same
    # documents (e.g. a chat session) don't rebuild BM25 every turn.
    _bm25_cache: dict[tuple, tuple[int, object]] = {}

    def _bm25(self, doc_ids: list[str], corpus: list[dict]):
        from .sparse import BM25, tokenize

        cache_key = tuple(sorted(doc_ids))
        cached = self._bm25_cache.get(cache_key)
        if cached and cached[0] == len(corpus):
            return cached[1]
        index = BM25([tokenize(c["text"]) for c in corpus])
        self._bm25_cache[cache_key] = (len(corpus), index)
        return index

    def search(self, query: str, top_k: int, doc_ids: list[str]) -> list[dict]:
        corpus = self._vs.get_chunks(doc_ids)
        if not corpus:
            return []

        # Dense score for every chunk (pass the full corpus size as top_k).
        dense = self._vs.query(doc_ids, query, len(corpus))
        dense_by_key = {_key(d["metadata"]): d["score"] for d in dense}

        # Sparse (BM25) score for every chunk.
        sparse = self._bm25(doc_ids, corpus).scores(query)
        sparse_by_key = {_key(c["metadata"]): s for c, s in zip(corpus, sparse)}

        dnorm = _minmax(dense_by_key)
        snorm = _minmax(sparse_by_key)

        fused = [
            {
                "text": c["text"],
                "metadata": c["metadata"],
                "score": self._alpha * dnorm.get(_key(c["metadata"]), 0.0)
                + (1 - self._alpha) * snorm.get(_key(c["metadata"]), 0.0),
            }
            for c in corpus
        ]
        fused.sort(key=lambda x: x["score"], reverse=True)
        return fused[:top_k]


def _key(meta: dict) -> tuple:
    return (meta.get("doc_id"), meta.get("chunk_index"))


def _minmax(by_key: dict) -> dict:
    if not by_key:
        return {}
    lo, hi = min(by_key.values()), max(by_key.values())
    rng = hi - lo
    if rng == 0:
        return {k: 0.0 for k in by_key}
    return {k: (v - lo) / rng for k, v in by_key.items()}
