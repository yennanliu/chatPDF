"""TDD — LLM-as-judge parsing for generation quality (RAGAs-style triad).

The judge call itself needs an API key, but the response *parser* is pure and
must be robust to the usual LLM output noise (code fences, stray prose).
"""
from __future__ import annotations

from services.judge import parse_judge_response


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
