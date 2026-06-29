"""Retrieval evaluation metrics (§5.8).

Pure functions so they unit-test offline. A "result" is an ordered list of
retrieved chunk ids (best first); "relevant" is the set of ids that should have
been retrieved for the query. See ``scripts/eval_retrieval.py`` for the runner
and ``doc/rag_evaluation.md`` for the gold-set format.
"""
from __future__ import annotations


def hit_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """1.0 if any relevant id appears in the top-k, else 0.0."""
    return 1.0 if set(retrieved[:k]) & relevant else 0.0


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of relevant ids found in the top-k."""
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    """1/rank of the first relevant id (rank is 1-based); 0 if none found."""
    for i, rid in enumerate(retrieved, start=1):
        if rid in relevant:
            return 1.0 / i
    return 0.0


def aggregate(rows: list[dict], k: int = 5) -> dict[str, float]:
    """Average metrics over a list of {retrieved, relevant} rows."""
    if not rows:
        return {"hit@k": 0.0, "recall@k": 0.0, "mrr": 0.0, "n": 0}
    n = len(rows)
    return {
        "hit@k": sum(hit_at_k(r["retrieved"], set(r["relevant"]), k) for r in rows) / n,
        "recall@k": sum(recall_at_k(r["retrieved"], set(r["relevant"]), k) for r in rows) / n,
        "mrr": sum(reciprocal_rank(r["retrieved"], set(r["relevant"])) for r in rows) / n,
        "n": n,
    }
