from __future__ import annotations

from .base import BaseReranker


class NoopReranker(BaseReranker):
    def rerank(self, query: str, chunks: list[dict]) -> list[dict]:
        return chunks


class CrossEncoderReranker(BaseReranker):
    """Cross-encoder reranker — registered for future use."""

    def __init__(self, model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        self._model_name = model
        self._model = None  # lazy load

    def warm(self) -> None:
        """Eagerly load the model so the first real query isn't stalled by the
        download/load. Safe to call at startup; failures are swallowed."""
        try:
            from sentence_transformers import CrossEncoder
            if self._model is None:
                self._model = CrossEncoder(self._model_name)
        except Exception:
            pass

    def score(self, query: str, chunks: list[dict]) -> list[float]:
        """Cross-encoder relevance logit for each (query, chunk) pair, in order.

        Higher = more relevant; ≈0.0 is the relevant/not-relevant boundary
        (sigmoid 0.5). Used by both reranking and the relevance gate.
        """
        if not chunks:
            return []
        from sentence_transformers import CrossEncoder
        if self._model is None:
            self._model = CrossEncoder(self._model_name)
        pairs = [(query, c["text"]) for c in chunks]
        return [float(s) for s in self._model.predict(pairs)]

    def rerank(self, query: str, chunks: list[dict]) -> list[dict]:
        if not chunks:
            return chunks
        ranked = sorted(zip(chunks, self.score(query, chunks)), key=lambda x: x[1], reverse=True)
        return [c for c, _ in ranked]
