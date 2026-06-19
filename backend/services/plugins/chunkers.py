from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .base import BaseChunker

if TYPE_CHECKING:
    from .base import BaseEmbedder

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


class RecursiveChunker(BaseChunker):
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, text: str) -> list[str]:
        chunks: list[str] = []
        start = 0
        step = max(1, self.chunk_size - self.chunk_overlap)
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += step
        return chunks


class SentenceChunker(BaseChunker):
    """Splits on sentence boundaries — registered for future use."""

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 0) -> None:
        self.chunk_size = chunk_size

    def split(self, text: str) -> list[str]:
        sentences = _SENTENCE_RE.split(text)
        chunks: list[str] = []
        current = ""
        for s in sentences:
            if len(current) + len(s) > self.chunk_size and current:
                chunks.append(current.strip())
                current = s
            else:
                current = (current + " " + s).strip()
        if current:
            chunks.append(current)
        return chunks


class SemanticChunker(BaseChunker):
    """Embedding-based semantic chunking.

    Splits text into sentences, embeds each, and starts a new chunk wherever the
    cosine distance between consecutive sentences exceeds a percentile threshold
    (i.e. a topic shift). `chunk_size` is a hard character cap so a long run of
    semantically-similar sentences never grows a chunk unbounded.

    The embedder is injectable; by default it lazily builds the local
    all-MiniLM-L6-v2 embedder, so importing this class costs nothing.
    """

    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 0,
        breakpoint_percentile: int = 90,
        embedder: BaseEmbedder | None = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap  # accepted for registry compatibility
        self.breakpoint_percentile = breakpoint_percentile
        self._embedder = embedder

    def _get_embedder(self) -> BaseEmbedder:
        if self._embedder is None:
            from .embedders import LocalEmbedder
            self._embedder = LocalEmbedder()
        return self._embedder

    def split(self, text: str) -> list[str]:
        sentences = [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]
        if len(sentences) <= 1:
            return sentences

        import numpy as np

        vectors = [np.asarray(v, dtype=float) for v in self._get_embedder().embed(sentences)]
        distances = [1.0 - _cosine(vectors[i], vectors[i + 1]) for i in range(len(vectors) - 1)]
        threshold = float(np.percentile(distances, self.breakpoint_percentile))

        chunks: list[str] = []
        current = [sentences[0]]
        for i in range(1, len(sentences)):
            topic_shift = distances[i - 1] > threshold
            too_big = len(" ".join(current)) + 1 + len(sentences[i]) > self.chunk_size
            if topic_shift or too_big:
                chunks.append(" ".join(current))
                current = [sentences[i]]
            else:
                current.append(sentences[i])
        chunks.append(" ".join(current))
        return chunks


def _cosine(a, b) -> float:
    import numpy as np

    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))
