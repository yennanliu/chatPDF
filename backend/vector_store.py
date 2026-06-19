from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

import chromadb
from chromadb.api.types import EmbeddingFunction

from config import settings


class VectorStore:
    def __init__(self, client: chromadb.ClientAPI, embedding_fn: Optional[EmbeddingFunction] = None):
        self._client = client
        self._embedding_fn = embedding_fn

    def _collection(self, doc_id: str) -> chromadb.Collection:
        kwargs: dict[str, Any] = {"name": f"doc_{doc_id}"}
        if self._embedding_fn is not None:
            kwargs["embedding_function"] = self._embedding_fn
        return self._client.get_or_create_collection(**kwargs)

    def upsert_chunks(self, doc_id: str, chunks: list[str], metadatas: list[dict]) -> None:
        col = self._collection(doc_id)
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        col.upsert(documents=chunks, metadatas=metadatas, ids=ids)

    def query(self, doc_ids: list[str], query_text: str, top_k: int = 5) -> list[dict]:
        results: list[dict] = []
        for doc_id in doc_ids:
            try:
                col = self._client.get_collection(
                    name=f"doc_{doc_id}",
                    embedding_function=self._embedding_fn,
                )
                r = col.query(query_texts=[query_text], n_results=top_k)
                docs = r["documents"][0]
                if not docs:
                    continue
                metas = r["metadatas"][0]
                dists = r["distances"][0]
                for text, meta, dist in zip(docs, metas, dists):
                    results.append({"text": text, "metadata": meta, "score": 1 - dist})
            except Exception:
                pass
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get_chunks(self, doc_ids: list[str]) -> list[dict]:
        """Return every chunk for the given docs as [{text, metadata}] — used by BM25."""
        out: list[dict] = []
        for doc_id in doc_ids:
            try:
                col = self._client.get_collection(
                    name=f"doc_{doc_id}",
                    embedding_function=self._embedding_fn,
                )
                r = col.get(include=["documents", "metadatas"])
                for text, meta in zip(r["documents"], r["metadatas"]):
                    out.append({"text": text, "metadata": meta})
            except Exception:
                pass
        return out

    def delete_document(self, doc_id: str) -> None:
        try:
            self._client.delete_collection(f"doc_{doc_id}")
        except Exception:
            pass


@lru_cache(maxsize=1)
def _chroma_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=settings.chroma_data_dir)


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    return VectorStore(_chroma_client())
