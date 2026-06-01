from __future__ import annotations

from typing import AsyncIterator, Union

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from services.rag_config import RAGConfig, build_reranker, build_retriever
from vector_store import VectorStore

_SYSTEM = (
    "You are a helpful assistant. Answer questions based solely on the provided "
    "context from PDF documents. If the context is insufficient, say so clearly.\n\n"
    "Context:\n{context}"
)


def _build_messages(query: str, context: list[dict], history: list[BaseMessage]) -> list[BaseMessage]:
    ctx = "\n\n".join(c["text"] for c in context) or "No relevant context found."
    return [SystemMessage(content=_SYSTEM.format(context=ctx)), *history, HumanMessage(content=query)]


async def run_rag_stream(
    query: str,
    doc_ids: list[str],
    history: list[BaseMessage],
    rag_config: RAGConfig,
    vs: VectorStore,
    llm: BaseChatModel,
) -> AsyncIterator[Union[str, dict]]:
    # 1. Retrieve via retriever plugin
    context = build_retriever(rag_config, vs).search(query, rag_config.top_k, doc_ids)

    # 2. Rerank if configured
    if rag_config.reranker != "none" and context:
        context = build_reranker(rag_config).rerank(query, context)[: rag_config.rerank_top_n]

    # 3. Stream tokens from LLM
    async for chunk in llm.astream(_build_messages(query, context, history)):
        if chunk.content:
            yield str(chunk.content)

    # 4. Emit done sentinel with source citations
    sources = [
        {
            "doc_name": c["metadata"].get("file", ""),
            "chunk_preview": c["text"][:200],
            "score": round(c.get("score", 0.0), 3),
        }
        for c in context[:3]
    ]
    yield {"__done__": True, "sources": sources}
