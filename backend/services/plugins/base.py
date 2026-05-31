from __future__ import annotations

from abc import ABC, abstractmethod


class BaseChunker(ABC):
    @abstractmethod
    def split(self, text: str) -> list[str]: ...


class BaseEmbedder(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class BaseRetriever(ABC):
    @abstractmethod
    def search(self, query: str, top_k: int, doc_ids: list[str]) -> list[dict]: ...


class BaseReranker(ABC):
    @abstractmethod
    def rerank(self, query: str, chunks: list[dict]) -> list[dict]: ...
