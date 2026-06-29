"""Retrieval evaluation metrics (§5.8).

Pure functions so they unit-test offline. A "result" is an ordered list of
retrieved chunk ids (best first); "relevant" is the set of ids that should have
been retrieved for the query. See ``scripts/eval_retrieval.py`` for the offline
runner, ``services/eval_runner.py`` for the live (API) runner, and
``doc/rag_evaluation.md`` for the gold-set format.

These are the same ranking metrics that IR-eval libraries (ranx, pytrec_eval)
and the RAGAs context metrics compute — kept in-house here as a handful of pure
functions to avoid pulling a heavy numerical stack (numba/pandas) into the image.
"""
from __future__ import annotations

import math


def hit_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """1.0 if any relevant id appears in the top-k, else 0.0."""
    return 1.0 if set(retrieved[:k]) & relevant else 0.0


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of relevant ids found in the top-k."""
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of the top-k retrieved ids that are relevant."""
    if k <= 0 or not retrieved:
        return 0.0
    topk = retrieved[:k]
    return sum(1 for rid in topk if rid in relevant) / len(topk)


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    """1/rank of the first relevant id (rank is 1-based); 0 if none found."""
    for i, rid in enumerate(retrieved, start=1):
        if rid in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Normalized discounted cumulative gain over binary relevance.

    Rewards placing relevant chunks above irrelevant ones, with a logarithmic
    rank discount. Normalized by the ideal ordering so it lands in [0, 1].
    """
    if not relevant:
        return 0.0
    dcg = sum(
        1.0 / math.log2(i + 1)
        for i, rid in enumerate(retrieved[:k], start=1)
        if rid in relevant
    )
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def score_query(retrieved_texts: list[str], substrings: list[str], k: int) -> dict:
    """Score one query's retrieval against substring-based gold (label-free).

    Each required substring stands for a piece of evidence the answer needs. A
    retrieved chunk is "relevant" if it contains *any* required substring. This
    avoids brittle chunk-id coupling that breaks whenever you re-chunk
    (``doc/rag_evaluation.md`` §4).

    Returns per-query: hit, first_relevant_rank, mrr, ndcg@k, precision@k,
    substring_recall (fraction of required substrings surfaced in the top-k),
    and the per-chunk relevant flags for UI drill-down.
    """
    subs = [s.lower() for s in substrings if s.strip()]
    topk = retrieved_texts[:k]
    lowered = [t.lower() for t in topk]
    flags = [any(s in t for s in subs) for t in lowered]

    first_rank = next((i for i, f in enumerate(flags, start=1) if f), None)
    found_subs = sum(1 for s in subs if any(s in t for t in lowered))

    return {
        "hit": first_rank is not None,
        "first_relevant_rank": first_rank,
        "mrr": (1.0 / first_rank) if first_rank else 0.0,
        "ndcg@k": ndcg_at_k(
            [str(i) for i in range(len(topk))],
            {str(i) for i, f in enumerate(flags) if f},
            k,
        ),
        "precision@k": (sum(flags) / len(topk)) if topk else 0.0,
        "substring_recall": (found_subs / len(subs)) if subs else 0.0,
        "relevant_flags": flags,
    }


def aggregate(rows: list[dict], k: int = 5) -> dict[str, float]:
    """Average id-based metrics over a list of {retrieved, relevant} rows."""
    if not rows:
        return {"hit@k": 0.0, "recall@k": 0.0, "mrr": 0.0, "ndcg@k": 0.0, "precision@k": 0.0, "n": 0}
    n = len(rows)

    def avg(fn) -> float:
        return sum(fn(r["retrieved"], set(r["relevant"])) for r in rows) / n

    return {
        "hit@k": avg(lambda ret, rel: hit_at_k(ret, rel, k)),
        "recall@k": avg(lambda ret, rel: recall_at_k(ret, rel, k)),
        "mrr": avg(reciprocal_rank),
        "ndcg@k": avg(lambda ret, rel: ndcg_at_k(ret, rel, k)),
        "precision@k": avg(lambda ret, rel: precision_at_k(ret, rel, k)),
        "n": n,
    }
