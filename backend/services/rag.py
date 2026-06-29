from __future__ import annotations

from typing import AsyncIterator, Union

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from services.rag_config import RAGConfig, build_reranker, build_retriever
from services.tokens import count_tokens
from vector_store import VectorStore

_SYSTEM = (
    "You are a helpful assistant. Answer questions based solely on the provided "
    "context from PDF documents. If the context is insufficient, say so clearly.\n\n"
    "Context:\n{context}"
)


def _fit_to_budget(
    query: str,
    context: list[dict],
    history: list[BaseMessage],
    system_template: str,
    budget: int,
) -> tuple[list[dict], list[BaseMessage]]:
    """Trim retrieved context and chat history so the prompt fits ``budget`` tokens.

    Context chunks arrive best-first, so we keep them in order and drop the tail.
    History is kept most-recent-first, dropping the oldest turns. The query and the
    system-prompt boilerplate are always reserved first.
    """
    used = count_tokens(system_template) + count_tokens(query)

    kept_ctx: list[dict] = []
    for c in context:
        cost = count_tokens(c["text"])
        if used + cost > budget:
            break
        used += cost
        kept_ctx.append(c)

    kept_hist_rev: list[BaseMessage] = []
    for msg in reversed(history):
        cost = count_tokens(str(msg.content))
        if used + cost > budget:
            break
        used += cost
        kept_hist_rev.append(msg)

    return kept_ctx, list(reversed(kept_hist_rev))


def _build_messages(
    query: str, context: list[dict], history: list[BaseMessage], system_template: str
) -> list[BaseMessage]:
    ctx = "\n\n".join(c["text"] for c in context) or "No relevant context found."
    return [SystemMessage(content=system_template.format(context=ctx)), *history, HumanMessage(content=query)]


def _expand_queries(query: str, n: int, llm: BaseChatModel) -> list[str]:
    """Ask the LLM for ``n`` alternative phrasings to widen recall. Falls back to
    just the original query if generation fails or returns nothing usable."""
    prompt = (
        f"Rewrite the following search query in {n} different ways that preserve "
        f"its meaning, one per line, no numbering:\n\n{query}"
    )
    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        variants = [line.strip("-• \t") for line in str(resp.content).splitlines() if line.strip()]
    except Exception:
        variants = []
    # De-dupe while preserving order; always include the original.
    seen, out = set(), []
    for q in [query, *variants]:
        if q and q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out[: n + 1]


def _retrieve(retriever, query: str, cfg: RAGConfig, doc_ids: list[str], llm: BaseChatModel) -> list[dict]:
    """Run retrieval for the query (and its paraphrases when multi_query is on),
    merging results by chunk key and keeping the best score for each."""
    if cfg.multi_query <= 0:
        return retriever.search(query, cfg.top_k, doc_ids)

    merged: dict[tuple, dict] = {}
    for q in _expand_queries(query, cfg.multi_query, llm):
        for hit in retriever.search(q, cfg.top_k, doc_ids):
            meta = hit["metadata"]
            key = (meta.get("doc_id"), meta.get("chunk_index"))
            if key not in merged or hit.get("score", 0.0) > merged[key].get("score", 0.0):
                merged[key] = hit
    ranked = sorted(merged.values(), key=lambda h: h.get("score", 0.0), reverse=True)
    return ranked[: cfg.top_k]


def retrieve_context(
    query: str,
    doc_ids: list[str],
    rag_config: RAGConfig,
    vs: VectorStore,
    llm: BaseChatModel | None = None,
) -> list[dict]:
    """Run the full retrieval path — retriever (optionally multi-query widened),
    grade filter, then reranker — and return the final context chunks.

    Shared by ``run_rag_stream`` and the evaluation runner so both measure the
    *same* pipeline. ``llm`` is only needed when ``multi_query`` is on; pass None
    to evaluate retrieval without an LLM available.
    """
    retriever = build_retriever(rag_config, vs)

    # 1. Retrieve (widen with paraphrases only when multi_query is on and we have an LLM)
    if rag_config.multi_query > 0 and llm is not None:
        context = _retrieve(retriever, query, rag_config, doc_ids, llm)
    else:
        context = retriever.search(query, rag_config.top_k, doc_ids)

    # 2. Grade filter — drop weakly-relevant chunks before they reach the prompt
    if rag_config.min_score > 0:
        context = [c for c in context if c.get("score", 0.0) >= rag_config.min_score]

    # 3. Rerank if configured
    if rag_config.reranker != "none" and context:
        context = build_reranker(rag_config).rerank(query, context)[: rag_config.rerank_top_n]

    return context


def build_rag_messages(
    query: str, context: list[dict], history: list[BaseMessage], rag_config: RAGConfig
) -> list[BaseMessage]:
    """Resolve the system template, trim context + history to the token budget,
    and assemble the final prompt messages. Shared by streaming and eval."""
    system_template = rag_config.system_prompt or _SYSTEM
    if "{context}" not in system_template:
        system_template = system_template + "\n\nContext:\n{context}"
    prompt_ctx, prompt_hist = _fit_to_budget(
        query, context, history, system_template, rag_config.max_context_tokens
    )
    return _build_messages(query, prompt_ctx, prompt_hist, system_template)


def sources_from_context(context: list[dict], limit: int = 3) -> list[dict]:
    """Shape retrieved chunks into the citation payload returned to clients."""
    return [
        {
            "doc_name": c["metadata"].get("file", ""),
            "page": c["metadata"].get("page"),
            "chunk_preview": c["text"][:200],
            "score": round(c.get("score", 0.0), 3),
        }
        for c in context[:limit]
    ]


async def run_rag_stream(
    query: str,
    doc_ids: list[str],
    history: list[BaseMessage],
    rag_config: RAGConfig,
    vs: VectorStore,
    llm: BaseChatModel,
) -> AsyncIterator[Union[str, dict]]:
    # 1. Retrieve + grade + rerank
    context = retrieve_context(query, doc_ids, rag_config, vs, llm)

    # 2. Build prompt (custom system prompt allowed; trimmed to the token budget)
    messages = build_rag_messages(query, context, history, rag_config)

    # 3. Stream tokens from LLM
    async for chunk in llm.astream(messages):
        if chunk.content:
            yield str(chunk.content)

    # 4. Emit done sentinel with source citations
    yield {"__done__": True, "sources": sources_from_context(context)}
