from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Optional

import chromadb
from chromadb.api.types import EmbeddingFunction

from config import settings

logger = logging.getLogger("chatpdf.vector_store")


def _log_collection_error(op: str, doc_id: str, exc: Exception) -> None:
    """Log a Chroma access failure. A missing collection is expected (e.g. the
    doc is still ingesting), so log it at debug; anything else is a real warning."""
    msg = str(exc).lower()
    if "does not exist" in msg or "not found" in msg or "not exist" in msg:
        logger.debug("%s skipped, no collection for doc_id=%s", op, doc_id)
    else:
        logger.warning("%s failed for doc_id=%s: %s", op, doc_id, exc)


class VectorStore:
    def __init__(self, client: chromadb.ClientAPI, embedding_fn: Optional[EmbeddingFunction] = None):
        self._client = client
        self._embedding_fn = embedding_fn

    def _collection(self, doc_id: str) -> chromadb.Collection:
        kwargs: dict[str, Any] = {"name": f"doc_{doc_id}"}
        if self._embedding_fn is not None:
            kwargs["embedding_function"] = self._embedding_fn
        return self._client.get_or_create_collection(**kwargs)

    def _existing_collection(self, doc_id: str) -> chromadb.Collection:
        """Fetch an existing collection (raises if absent — callers catch)."""
        return self._client.get_collection(
            name=f"doc_{doc_id}",
            embedding_function=self._embedding_fn,
        )

    def upsert_chunks(self, doc_id: str, chunks: list[str], metadatas: list[dict]) -> None:
        col = self._collection(doc_id)
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        col.upsert(documents=chunks, metadatas=metadatas, ids=ids)

    def query(self, doc_ids: list[str], query_text: str, top_k: int = 5) -> list[dict]:
        results: list[dict] = []
        for doc_id in doc_ids:
            try:
                col = self._existing_collection(doc_id)
                r = col.query(query_texts=[query_text], n_results=top_k)
                docs = r["documents"][0]
                if not docs:
                    continue
                metas = r["metadatas"][0]
                dists = r["distances"][0]
                for text, meta, dist in zip(docs, metas, dists):
                    results.append({"text": text, "metadata": meta, "score": 1 - dist})
            except Exception as exc:
                _log_collection_error("query", doc_id, exc)
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get_chunks(self, doc_ids: list[str]) -> list[dict]:
        """Return every chunk for the given docs as [{text, metadata}] — used by BM25."""
        out: list[dict] = []
        for doc_id in doc_ids:
            try:
                col = self._existing_collection(doc_id)
                r = col.get(include=["documents", "metadatas"])
                for text, meta in zip(r["documents"], r["metadatas"]):
                    out.append({"text": text, "metadata": meta})
            except Exception as exc:
                _log_collection_error("get_chunks", doc_id, exc)
        return out

    def delete_document(self, doc_id: str) -> None:
        try:
            self._client.delete_collection(f"doc_{doc_id}")
        except Exception as exc:
            _log_collection_error("delete", doc_id, exc)


@lru_cache(maxsize=1)
def _chroma_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=settings.chroma_data_dir)


def _resolve_embedding_fn() -> Optional[EmbeddingFunction]:
    """Pick the embedding function from settings.embedding_backend.

    Returning None lets Chroma use its bundled local all-MiniLM-L6-v2 model.
    The same function is used for both ingestion and query so vectors always
    live in one space — switching backends requires re-ingesting documents.
    """
    if settings.embedding_backend == "openai":
        if not settings.openai_api_key:
            # Without a key the OpenAI embedder raises a cryptic credentials error
            # on every ingest/query. Fall back to the local model so the app stays
            # usable, and say so loudly.
            logger.warning(
                "EMBEDDING_BACKEND=openai but OPENAI_API_KEY is empty — "
                "falling back to local embeddings."
            )
            return None
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        logger.info("vector store using OpenAI embeddings")
        return OpenAIEmbeddingFunction(
            api_key=settings.openai_api_key,
            model_name="text-embedding-3-small",
        )
    return None


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    return VectorStore(_chroma_client(), embedding_fn=_resolve_embedding_fn())
