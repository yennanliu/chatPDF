"""TDD — extended retrieval metrics: nDCG, precision, substring scoring.

These pair with the existing id-based metric tests in ``test_rag_quality.py``;
here we cover the additions used by the live eval endpoint (``routers/eval.py``).
"""
from __future__ import annotations

import math

from services.eval import (
    aggregate,
    ndcg_at_k,
    precision_at_k,
    score_query,
)

# ── nDCG ────────────────────────────────────────────────────────────────────

def test_ndcg_perfect_ranking_is_one():
    # relevant items already at the top → nDCG == 1.0
    assert ndcg_at_k(["a", "b", "c"], {"a", "b"}, k=3) == 1.0


def test_ndcg_rewards_higher_ranks():
    top = ndcg_at_k(["a", "x", "y"], {"a"}, k=3)      # relevant at rank 1
    low = ndcg_at_k(["x", "y", "a"], {"a"}, k=3)      # relevant at rank 3
    assert top == 1.0
    assert 0.0 < low < top


def test_ndcg_known_value_rank_two():
    # single relevant item at rank 2: DCG = 1/log2(3); IDCG = 1/log2(2)=1
    got = ndcg_at_k(["x", "a", "y"], {"a"}, k=3)
    assert math.isclose(got, 1.0 / math.log2(3), rel_tol=1e-9)


def test_ndcg_no_relevant_is_zero():
    assert ndcg_at_k(["x", "y"], set(), k=2) == 0.0
    assert ndcg_at_k(["x", "y"], {"z"}, k=2) == 0.0


# ── precision@k ───────────────────────────────────────────────────────────────

def test_precision_at_k():
    assert precision_at_k(["a", "b", "c"], {"a", "c"}, k=3) == 2 / 3
    assert precision_at_k(["a", "b"], {"a"}, k=2) == 0.5
    assert precision_at_k([], {"a"}, k=3) == 0.0


# ── substring scoring (label-free, the live path) ─────────────────────────────

def test_score_query_hit_and_rank():
    texts = [
        "irrelevant preamble text",
        "the retry policy uses exponential backoff capped at 5 retries",
    ]
    r = score_query(texts, ["exponential backoff", "5 retries"], k=5)
    assert r["hit"] is True
    assert r["first_relevant_rank"] == 2
    assert r["substring_recall"] == 1.0       # both substrings present
    assert r["relevant_flags"] == [False, True]


def test_score_query_partial_substring_recall():
    texts = ["mentions exponential backoff only"]
    r = score_query(texts, ["exponential backoff", "5 retries"], k=5)
    assert r["hit"] is True
    assert r["substring_recall"] == 0.5       # 1 of 2 substrings found


def test_score_query_miss():
    r = score_query(["nothing relevant here"], ["widget"], k=5)
    assert r["hit"] is False
    assert r["first_relevant_rank"] is None
    assert r["substring_recall"] == 0.0


def test_score_query_is_case_insensitive():
    r = score_query(["Exponential Backoff"], ["exponential backoff"], k=5)
    assert r["hit"] is True


# ── aggregate now carries ndcg@k and precision@k ──────────────────────────────

def test_aggregate_includes_new_metrics():
    rows = [
        {"retrieved": ["a", "b"], "relevant": ["a"]},
        {"retrieved": ["x", "a"], "relevant": ["a"]},
    ]
    m = aggregate(rows, k=2)
    assert "ndcg@k" in m and "precision@k" in m
    assert m["hit@k"] == 1.0
    assert m["precision@k"] == 0.5            # 1 relevant of 2 in each row
