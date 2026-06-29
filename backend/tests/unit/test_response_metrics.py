"""TDD — live per-response scoring (services/response_metrics.py).

Contract:
  retrieval_confidence — sigmoid of the best cross-encoder relevance logit, else
                         the best retriever score, else None for empty context.
  score_response       — combines the judge verdict with retrieval confidence
                         into a `confidence` = mean of available components;
                         a failed judge degrades gracefully (None axes).
"""
from __future__ import annotations

from services.response_metrics import retrieval_confidence, score_response
from tests.conftest import _FakeChatModel


def test_retrieval_confidence_uses_sigmoid_of_best_relevance():
    ctx = [{"text": "a", "relevance": 0.0}, {"text": "b", "relevance": 2.0}]
    # sigmoid(2.0) ≈ 0.8808
    assert retrieval_confidence(ctx) == 0.8808


def test_retrieval_confidence_falls_back_to_score():
    ctx = [{"text": "a", "score": 0.4}, {"text": "b", "score": 0.7}]
    assert retrieval_confidence(ctx) == 0.7


def test_retrieval_confidence_none_for_empty():
    assert retrieval_confidence([]) is None


def test_score_response_blends_components_into_confidence():
    llm = _FakeChatModel(
        response='{"faithfulness": 1.0, "answer_relevance": 0.5, "context_precision": 0.6}'
    )
    ctx = [{"text": "a", "relevance": 2.0}]  # retrieval_confidence ≈ 0.8808
    m = score_response("q?", ctx, "the answer", llm)
    assert m["faithfulness"] == 1.0
    assert m["answer_relevance"] == 0.5
    assert m["context_precision"] == 0.6
    assert m["retrieval_confidence"] == 0.8808
    # confidence = mean(0.8808, 0.6, 1.0, 0.5)
    assert m["confidence"] == round((0.8808 + 0.6 + 1.0 + 0.5) / 4, 4)


def test_score_response_degrades_when_judge_unparseable():
    llm = _FakeChatModel(response="the judge said no")
    ctx = [{"text": "a", "score": 0.9}]
    m = score_response("q?", ctx, "answer", llm)
    assert m["faithfulness"] is None
    assert m["answer_relevance"] is None
    assert m["context_precision"] is None
    # Confidence falls back to the only available component (retrieval).
    assert m["confidence"] == 0.9


def test_score_response_all_none_yields_none_confidence():
    llm = _FakeChatModel(response="garbage")
    m = score_response("q?", [], "answer", llm)  # no context → no retrieval signal
    assert m["confidence"] is None
