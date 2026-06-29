"""
TDD — RAG pipeline unit tests (Phase 4 coverage hardening)

Contract under test:
  run_rag_stream:
    - reranker is applied when rag_config.reranker != "none"  (lines 63-64)
    - done sentinel always emitted as last item
    - sources limited by rerank_top_n when reranker active
"""
from unittest.mock import MagicMock, patch

# Captured at import time, before the autouse ``_stub_relevance_scorer`` fixture
# swaps out the module attribute — this is the real factory under test.
from services.rag import _relevance_scorer as _real_relevance_scorer
from services.rag import run_rag_stream
from services.rag_config import RAGConfig


async def _collect(gen) -> list:
    items = []
    async for item in gen:
        items.append(item)
    return items


# ── relevance-scorer lazy singleton (rag.py _relevance_scorer) ───────────────

def test_relevance_scorer_lazily_constructs_and_caches(monkeypatch):
    """First call builds the cross-encoder under the lock; subsequent calls
    return the memoised instance without reconstructing it."""
    import services.plugins.rerankers as rerankers
    import services.rag as rag_mod

    sentinel = object()
    monkeypatch.setattr(rerankers, "CrossEncoderReranker", lambda: sentinel)
    monkeypatch.setattr(rag_mod, "_relevance_scorer_singleton", None)

    assert _real_relevance_scorer() is sentinel
    # A second construction must not happen — swap in a different factory and
    # confirm the cached sentinel is still returned.
    monkeypatch.setattr(rerankers, "CrossEncoderReranker", lambda: object())
    assert _real_relevance_scorer() is sentinel


# ── reranker path (rag.py lines 63-64) ───────────────────────────────────────

async def test_reranker_applied_when_configured():
    """Lines 63-64: build_reranker is called and rerank() is invoked."""
    vs = MagicMock()
    vs.query.return_value = [
        {"text": "original chunk", "metadata": {"file": "doc.pdf"}, "score": 0.8}
    ]

    async def _fake_astream(messages, *a, **kw):
        from langchain_core.messages import AIMessageChunk
        yield AIMessageChunk(content="answer ")

    llm = MagicMock()
    llm.astream = _fake_astream

    fake_reranker = MagicMock()
    fake_reranker.rerank.return_value = [
        {"text": "reranked chunk", "metadata": {"file": "doc.pdf"}, "score": 0.95}
    ]

    # Disable the relevance gate to isolate the reranker wiring under test.
    cfg = RAGConfig(reranker="cross_encoder", rerank_top_n=1, relevance_gate=None)

    with patch("services.rag.build_reranker", return_value=fake_reranker):
        results = await _collect(
            run_rag_stream(
                query="test question",
                doc_ids=["doc1"],
                history=[],
                rag_config=cfg,
                vs=vs,
                llm=llm,
            )
        )

    fake_reranker.rerank.assert_called_once_with(
        "test question",
        [{"text": "original chunk", "metadata": {"file": "doc.pdf"}, "score": 0.8}],
    )
    done = results[-1]
    assert done["__done__"] is True


async def test_reranker_not_called_when_none():
    """No build_reranker call when reranker == 'none'."""
    vs = MagicMock()
    vs.query.return_value = [{"text": "chunk", "metadata": {"file": "f.pdf"}, "score": 0.5}]

    async def _fake_astream(messages, *a, **kw):
        from langchain_core.messages import AIMessageChunk
        yield AIMessageChunk(content="tok ")

    llm = MagicMock()
    llm.astream = _fake_astream

    cfg = RAGConfig(reranker="none")

    with patch("services.rag.build_reranker") as mock_br:
        await _collect(
            run_rag_stream(
                query="q",
                doc_ids=["d1"],
                history=[],
                rag_config=cfg,
                vs=vs,
                llm=llm,
            )
        )

    mock_br.assert_not_called()


async def test_done_sentinel_always_last():
    """Last item from run_rag_stream is always the done dict."""
    vs = MagicMock()
    vs.query.return_value = []  # no context

    async def _fake_astream(messages, *a, **kw):
        from langchain_core.messages import AIMessageChunk
        yield AIMessageChunk(content="hi")

    llm = MagicMock()
    llm.astream = _fake_astream

    results = await _collect(
        run_rag_stream(
            query="hello",
            doc_ids=[],
            history=[],
            rag_config=RAGConfig(),
            vs=vs,
            llm=llm,
        )
    )

    assert results[-1] == {"__done__": True, "sources": [], "context": []}
