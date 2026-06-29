"""TDD — cross-encoder relevance gate (services/rag.apply_relevance_gate).

Contract:
  * score each (query, chunk) with the injected cross-encoder scorer,
  * drop chunks below the logit threshold,
  * sort survivors by relevance (desc), attaching a `relevance` field,
  * never empty the context — keep the single best chunk if all fall below,
  * a scorer failure passes chunks through unchanged (must never break a turn),
  * the default RAGConfig has the gate enabled (on by default, for grounding).
"""
from __future__ import annotations

from services.rag import apply_relevance_gate
from services.rag_config import RAGConfig


class _Scorer:
    """Returns preset scores aligned to the chunk order."""
    def __init__(self, scores): self._scores = scores
    def score(self, query, chunks): return self._scores[:len(chunks)]


def _chunks(*texts):
    return [{"text": t, "metadata": {"chunk_index": i}} for i, t in enumerate(texts)]


def test_drops_chunks_below_threshold():
    chunks = _chunks("relevant", "irrelevant", "borderline")
    scorer = _Scorer([5.0, -4.0, 0.5])
    out = apply_relevance_gate("q", chunks, threshold=0.0, scorer=scorer)
    texts = [c["text"] for c in out]
    assert "irrelevant" not in texts           # below 0.0 → dropped
    assert set(texts) == {"relevant", "borderline"}


def test_sorts_survivors_by_relevance_desc():
    chunks = _chunks("low", "high", "mid")
    scorer = _Scorer([1.0, 9.0, 5.0])
    out = apply_relevance_gate("q", chunks, threshold=0.0, scorer=scorer)
    assert [c["text"] for c in out] == ["high", "mid", "low"]
    assert [c["relevance"] for c in out] == [9.0, 5.0, 1.0]


def test_never_empties_context_keeps_best():
    # All chunks score below threshold → keep the single best rather than nothing.
    chunks = _chunks("a", "b", "c")
    scorer = _Scorer([-2.0, -9.0, -5.0])
    out = apply_relevance_gate("q", chunks, threshold=0.0, scorer=scorer)
    assert len(out) == 1
    assert out[0]["text"] == "a"               # -2.0 is the highest of the three


def test_empty_context_passes_through():
    assert apply_relevance_gate("q", [], threshold=0.0, scorer=_Scorer([])) == []


def test_scorer_failure_passes_chunks_through():
    class _Boom:
        def score(self, query, chunks): raise RuntimeError("model exploded")
    chunks = _chunks("a", "b")
    out = apply_relevance_gate("q", chunks, threshold=0.0, scorer=_Boom())
    assert out == chunks                        # unchanged, no exception


def test_does_not_mutate_input_chunks():
    chunks = _chunks("a")
    apply_relevance_gate("q", chunks, threshold=0.0, scorer=_Scorer([3.0]))
    assert "relevance" not in chunks[0]         # gate works on copies


def test_gate_enabled_by_default():
    assert RAGConfig().relevance_gate == 0.0    # on by default
    assert RAGConfig(relevance_gate=None).relevance_gate is None  # opt-out
