"""Live evaluation runner — drives the *same* RAG pipeline the chat path uses
over a gold set, for one or more ``RAGConfig`` variants, and returns a metrics
comparison table plus per-question drill-down.

Retrieval metrics (Hit@k, Recall@k, MRR, nDCG@k, Precision@k, latency) are
deterministic and free — they need no API key. Generation metrics (faithfulness,
answer relevance) are opt-in: pass ``answer_llm`` + ``judge_llm`` and the runner
will generate an answer per question and grade it (``services/judge.py``).

Synchronous on purpose: ``retrieve_context`` and the provider ``invoke`` calls
are blocking, so the FastAPI endpoint runs this in a worker thread.
"""
from __future__ import annotations

import logging
from statistics import median
from time import perf_counter

from langchain_core.language_models.chat_models import BaseChatModel

from services import judge as judge_mod
from services import tracing
from services.eval import score_query
from services.rag import build_rag_messages, retrieve_context
from services.rag_config import RAGConfig
from vector_store import VectorStore

logger = logging.getLogger("chatpdf.eval")

_PREVIEW_CHARS = 200


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _generate_answer(
    question: str, context: list[dict], cfg: RAGConfig, llm: BaseChatModel, config: dict | None = None
) -> str:
    messages = build_rag_messages(question, context, [], cfg)
    resp = llm.invoke(messages, config=config)
    return str(resp.content)


def _eval_variant(
    label: str,
    cfg: RAGConfig,
    gold: list[dict],
    vs: VectorStore,
    k: int,
    answer_llm: BaseChatModel | None,
    judge_llm: BaseChatModel | None,
) -> dict:
    rows: list[dict] = []
    latencies: list[float] = []
    judge_on = answer_llm is not None and judge_llm is not None

    # One Langfuse trace per variant: every LLM call below nests under it, and the
    # aggregate metrics are pushed as scores at the end. No-op when tracing is off.
    with tracing.eval_variant_trace(label, k=k, n_questions=len(gold)) as scope:
        for item in gold:
            question = item["question"]
            doc_ids = item.get("doc_ids", [])
            substrings = item.get("relevant_substrings", [])

            t0 = perf_counter()
            try:
                context = retrieve_context(question, doc_ids, cfg, vs, answer_llm, scope.config)
            except Exception:
                logger.exception("retrieval failed for question=%r variant=%s", question, label)
                context = []
            latency_ms = (perf_counter() - t0) * 1000
            latencies.append(latency_ms)

            scored = score_query([c["text"] for c in context], substrings, k)
            flags = scored["relevant_flags"]

            retrieved = [
                {
                    "doc_name": c["metadata"].get("file", ""),
                    "page": c["metadata"].get("page"),
                    "preview": c["text"][:_PREVIEW_CHARS],
                    "score": round(c.get("score", 0.0), 3),
                    "relevant": flags[i] if i < len(flags) else False,
                }
                for i, c in enumerate(context[:k])
            ]

            row = {
                "id": item.get("id"),
                "question": question,
                "hit": scored["hit"],
                "first_relevant_rank": scored["first_relevant_rank"],
                "mrr": scored["mrr"],
                "ndcg@k": scored["ndcg@k"],
                "precision@k": scored["precision@k"],
                "substring_recall": scored["substring_recall"],
                "latency_ms": round(latency_ms, 1),
                "retrieved": retrieved,
                "answer": None,
                "faithfulness": None,
                "answer_relevance": None,
            }

            if judge_on:
                try:
                    answer = _generate_answer(question, context, cfg, answer_llm, scope.config)
                    row["answer"] = answer
                    verdict = judge_mod.judge_answer(
                        question, [c["text"] for c in context], answer, judge_llm, scope.config
                    )
                    if verdict:
                        row["faithfulness"] = verdict["faithfulness"]
                        row["answer_relevance"] = verdict["answer_relevance"]
                except Exception:
                    logger.exception("generation/judge failed for question=%r variant=%s", question, label)

            rows.append(row)

        faith = [r["faithfulness"] for r in rows if r["faithfulness"] is not None]
        rel = [r["answer_relevance"] for r in rows if r["answer_relevance"] is not None]

        metrics = {
            "hit@k": _mean([1.0 if r["hit"] else 0.0 for r in rows]),
            "recall@k": _mean([r["substring_recall"] for r in rows]),
            "mrr": _mean([r["mrr"] for r in rows]),
            "ndcg@k": _mean([r["ndcg@k"] for r in rows]),
            "precision@k": _mean([r["precision@k"] for r in rows]),
            "p50_latency_ms": round(median(latencies), 1) if latencies else 0.0,
            "faithfulness": _mean(faith) if faith else None,
            "answer_relevance": _mean(rel) if rel else None,
        }
        scope.score(metrics)

    from dataclasses import asdict
    return {"label": label, "config": asdict(cfg), "metrics": metrics, "per_question": rows}


def run_eval(
    gold: list[dict],
    variants: list[tuple[str, RAGConfig]],
    vs: VectorStore,
    k: int = 5,
    *,
    answer_llm: BaseChatModel | None = None,
    judge_llm: BaseChatModel | None = None,
) -> dict:
    """Evaluate each (label, RAGConfig) variant over the gold set."""
    results = [
        _eval_variant(label, cfg, gold, vs, k, answer_llm, judge_llm)
        for label, cfg in variants
    ]
    return {
        "k": k,
        "n_questions": len(gold),
        "judge_enabled": answer_llm is not None and judge_llm is not None,
        "results": results,
    }
