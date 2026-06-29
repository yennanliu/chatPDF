"""TDD — LLM-as-judge parsing for generation quality (RAGAs-style triad).

The judge call itself needs an API key, but the response *parser* is pure and
must be robust to the usual LLM output noise (code fences, stray prose).
"""
from __future__ import annotations

from services.judge import (
    judge_answer,
    judge_context,
    judge_correctness,
    judge_response,
    parse_judge_response,
)
from tests.conftest import _FakeChatModel


def test_parses_plain_json():
    r = parse_judge_response('{"faithfulness": 0.9, "answer_relevance": 0.8}')
    assert r == {"faithfulness": 0.9, "answer_relevance": 0.8}


def test_parses_fenced_json_with_prose():
    raw = 'Here is my assessment:\n```json\n{"faithfulness": 1.0, "answer_relevance": 0.5}\n```\nDone.'
    r = parse_judge_response(raw)
    assert r["faithfulness"] == 1.0
    assert r["answer_relevance"] == 0.5


def test_clamps_out_of_range_scores():
    r = parse_judge_response('{"faithfulness": 1.4, "answer_relevance": -0.2}')
    assert r["faithfulness"] == 1.0
    assert r["answer_relevance"] == 0.0


def test_returns_none_on_garbage():
    assert parse_judge_response("the model refused to answer") is None
    assert parse_judge_response("") is None


def test_returns_none_when_keys_missing():
    assert parse_judge_response('{"faithfulness": 0.9}') is None


# ── context precision / recall (label-free retrieval metrics) ──────────────────

def test_judge_context_scores_precision_and_recall_with_reference():
    llm = _FakeChatModel(response='{"context_precision": 0.75, "context_recall": 0.9}')
    out = judge_context("q?", ["chunk a", "chunk b"], "the reference answer", llm)
    assert out == {"context_precision": 0.75, "context_recall": 0.9}


def test_judge_context_recall_is_none_without_reference():
    # Precision is still scorable from the question alone; recall needs a reference.
    llm = _FakeChatModel(response='{"context_precision": 0.6}')
    out = judge_context("q?", ["chunk a"], None, llm)
    assert out["context_precision"] == 0.6
    assert out["context_recall"] is None


def test_judge_context_clamps_and_handles_garbage():
    assert judge_context("q?", ["c"], "ref", _FakeChatModel(response="no json here")) is None
    clamped = judge_context("q?", ["c"], "ref",
                            _FakeChatModel(response='{"context_precision": 1.3, "context_recall": -1}'))
    assert clamped == {"context_precision": 1.0, "context_recall": 0.0}


# ── live combined judge + answer correctness ───────────────────────────────────

def test_judge_response_scores_three_axes_in_one_call():
    llm = _FakeChatModel(
        response='{"faithfulness": 0.9, "answer_relevance": 0.8, "context_precision": 0.7}'
    )
    out = judge_response("q?", ["ctx"], "the answer", llm)
    assert out == {"faithfulness": 0.9, "answer_relevance": 0.8, "context_precision": 0.7}


def test_judge_response_none_on_garbage():
    assert judge_response("q?", ["ctx"], "ans", _FakeChatModel(response="no json")) is None


def test_judge_correctness_scores_against_reference():
    llm = _FakeChatModel(response='{"answer_correctness": 0.85}')
    assert judge_correctness("q?", "the answer", "the reference", llm) == 0.85


def test_judge_correctness_none_without_reference():
    # No reference → not scorable, no LLM call needed.
    assert judge_correctness("q?", "the answer", None, _FakeChatModel(response="x")) is None
    assert judge_correctness("q?", "the answer", "  ", _FakeChatModel(response="x")) is None


# ── brace escaping: document/answer text must not break str.format ──────────────

# PDF chunks routinely carry literal braces (code, JSON, LaTeX); these must not
# raise KeyError out of the prompt .format() and silently void every score.
_BRACEY = 'see {config: {"k": 1}} and \\frac{a}{b}'


def test_judge_answer_survives_braces_in_inputs():
    llm = _FakeChatModel(response='{"faithfulness": 0.9, "answer_relevance": 0.8}')
    out = judge_answer(_BRACEY, [_BRACEY], _BRACEY, llm)
    assert out == {"faithfulness": 0.9, "answer_relevance": 0.8}


def test_judge_context_survives_braces_in_inputs():
    llm = _FakeChatModel(response='{"context_precision": 0.7, "context_recall": 0.6}')
    out = judge_context(_BRACEY, [_BRACEY], _BRACEY, llm)
    assert out == {"context_precision": 0.7, "context_recall": 0.6}


def test_judge_response_survives_braces_in_inputs():
    llm = _FakeChatModel(response='{"faithfulness": 0.9, "answer_relevance": 0.8, "context_precision": 0.7}')
    out = judge_response(_BRACEY, [_BRACEY], _BRACEY, llm)
    assert out == {"faithfulness": 0.9, "answer_relevance": 0.8, "context_precision": 0.7}


def test_judge_correctness_survives_braces_in_inputs():
    llm = _FakeChatModel(response='{"answer_correctness": 0.85}')
    assert judge_correctness(_BRACEY, _BRACEY, _BRACEY, llm) == 0.85
