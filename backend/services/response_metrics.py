"""Per-response quality scoring for *live* chat turns (label-free).

Unlike the eval harness, a live turn has no gold labels — so we only compute
metrics that need no ground truth: the LLM-judged faithfulness, answer relevance,
and context precision (one combined judge call), plus a retrieval-confidence
signal derived from the relevance scores the pipeline already produced. These are
blended into a single transparent ``confidence`` score.

Metrics shape (all values in [0, 1] or None):
    {confidence, retrieval_confidence, context_precision, faithfulness, answer_relevance}
"""
from __future__ import annotations

import logging
import math

from langchain_core.language_models.chat_models import BaseChatModel

from services import judge as judge_mod

logger = logging.getLogger("chatpdf.response_metrics")

METRIC_KEYS = ("confidence", "retrieval_confidence", "context_precision", "faithfulness", "answer_relevance")


def _sigmoid(x: float) -> float:
    # Numerically stable both directions.
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def retrieval_confidence(context: list[dict]) -> float | None:
    """A [0, 1] retrieval-confidence signal from the best retrieved chunk.

    Prefers the cross-encoder ``relevance`` logit (when the relevance gate ran),
    squashed through a sigmoid; otherwise falls back to the retriever ``score``.
    """
    if not context:
        return None
    rels = [c["relevance"] for c in context if c.get("relevance") is not None]
    if rels:
        return round(_sigmoid(max(rels)), 4)
    scores = [c["score"] for c in context if c.get("score") is not None]
    if not scores:
        return None
    return round(max(0.0, min(1.0, max(scores))), 4)


def score_response(
    question: str,
    context: list[dict],
    answer: str,
    judge_llm: BaseChatModel,
    config: dict | None = None,
) -> dict:
    """Score one live response. The judge call is best-effort: on failure its
    axes are None and ``confidence`` falls back to retrieval confidence alone.

    ``confidence`` is the mean of the available (non-None) component scores."""
    verdict = judge_mod.judge_response(question, [c["text"] for c in context], answer, judge_llm, config) or {}
    metrics = {
        "retrieval_confidence": retrieval_confidence(context),
        "context_precision": verdict.get("context_precision"),
        "faithfulness": verdict.get("faithfulness"),
        "answer_relevance": verdict.get("answer_relevance"),
    }
    components = [v for v in metrics.values() if v is not None]
    metrics["confidence"] = round(sum(components) / len(components), 4) if components else None
    return metrics
