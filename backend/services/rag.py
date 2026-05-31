from __future__ import annotations

from typing import AsyncIterator, TypedDict, Union

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, StateGraph

from services.rag_config import RAGConfig
from vector_store import VectorStore


_SYSTEM = (
    "You are a helpful assistant. Answer questions based solely on the provided "
    "context from PDF documents. If the context is insufficient, say so clearly.\n\n"
    "Context:\n{context}"
)


class _State(TypedDict):
    query: str
    doc_ids: list[str]
    top_k: int
    context: list[dict]


def _make_graph(vs: VectorStore):
    def retrieve(state: _State) -> dict:
        return {"context": vs.query(state["doc_ids"], state["query"], state["top_k"])}

    g: StateGraph = StateGraph(_State)
    g.add_node("retrieve", retrieve)
    g.set_entry_point("retrieve")
    g.add_edge("retrieve", END)
    return g.compile()


def _messages(query: str, context: list[dict], history: list[BaseMessage]) -> list[BaseMessage]:
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
    graph = _make_graph(vs)
    state = await graph.ainvoke({
        "query": query,
        "doc_ids": doc_ids,
        "top_k": rag_config.top_k,
        "context": [],
    })
    context: list[dict] = state["context"]

    async for chunk in llm.astream(_messages(query, context, history)):
        if chunk.content:
            yield str(chunk.content)

    sources = [
        {
            "doc_name": c["metadata"].get("file", ""),
            "chunk_preview": c["text"][:200],
            "score": round(c.get("score", 0.0), 3),
        }
        for c in context[:3]
    ]
    yield {"__done__": True, "sources": sources}
