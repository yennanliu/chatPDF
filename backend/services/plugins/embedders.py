from __future__ import annotations

from .base import BaseEmbedder


class LocalEmbedder(BaseEmbedder):
    """Delegates to ChromaDB's built-in all-MiniLM-L6-v2 ONNX embedder."""

    def __init__(self) -> None:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        self._ef = DefaultEmbeddingFunction()

    def embed(self, texts: list[str]) -> list[list[float]]:
        return list(self._ef(texts))


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI text-embedding-3-small — registered for future use."""

    def __init__(self, api_key: str = "", model: str = "text-embedding-3-small") -> None:
        self._api_key = api_key
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        from openai import OpenAI
        client = OpenAI(api_key=self._api_key)
        resp = client.embeddings.create(input=texts, model=self._model)
        return [item.embedding for item in resp.data]
