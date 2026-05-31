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

    def rerank(self, query: str, chunks: list[dict]) -> list[dict]:
        from sentence_transformers import CrossEncoder
        if self._model is None:
            self._model = CrossEncoder(self._model_name)
        pairs = [(query, c["text"]) for c in chunks]
        scores = self._model.predict(pairs)
        ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
        return [c for c, _ in ranked]
