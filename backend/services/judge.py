"""LLM-as-judge for generation quality — the RAGAs answer-quality triad.

Scores a generated answer on two axes that don't need a reference answer:

  * **faithfulness / groundedness** — are the answer's claims supported by the
    retrieved context? (catches hallucination)
  * **answer relevance** — does the answer actually address the question?
    (catches evasive / off-topic replies)

Judges are noisy, so we follow ``doc/rag_evaluation.md`` §3: a fixed rubric,
temperature 0 (set by the caller when building the model), each axis scored
independently in one structured call, and a *different* model family from the
answerer where possible (the caller chooses). The parser is defensive — any
unparseable judge output yields ``None`` rather than a fabricated score.
"""
from __future__ import annotations

import json
import logging
import re

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

logger = logging.getLogger("chatpdf.judge")

_JUDGE_PROMPT = """You are a strict, impartial RAG answer grader. Score the ANSWER on two axes, each from 0.0 to 1.0:

- "faithfulness": how fully the answer's factual claims are supported by the CONTEXT. 1.0 = every claim is grounded in the context; 0.0 = the answer contradicts or invents facts not in the context.
- "answer_relevance": how directly the answer addresses the QUESTION. 1.0 = fully on-topic and complete; 0.0 = evasive or off-topic.

Judge ONLY against the provided context — do not use outside knowledge. Reply with a single JSON object and nothing else:
{{"faithfulness": <float>, "answer_relevance": <float>}}

QUESTION:
{question}

CONTEXT:
{context}

ANSWER:
{answer}
"""

_REQUIRED = ("faithfulness", "answer_relevance")

_CONTEXT_PROMPT = """You are a strict, impartial grader of RAG *retrieval* quality. Judge only the CONTEXT passages against the QUESTION{ref_clause}. Score each axis from 0.0 to 1.0:

- "context_precision": the fraction of the CONTEXT that is actually relevant to answering the QUESTION (signal vs. noise). 1.0 = every passage is on-topic and useful; 0.0 = all passages are irrelevant padding.
{recall_line}
Reply with a single JSON object and nothing else:
{schema}

QUESTION:
{question}

CONTEXT:
{context}
{ref_block}"""

_RECALL_LINE = '- "context_recall": how fully the CONTEXT covers the information needed to support the REFERENCE ANSWER. 1.0 = every fact in the reference answer is grounded in the context; 0.0 = none are.\n'


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _parse_scores(text: str, required: tuple[str, ...]) -> dict | None:
    """Extract a JSON object with the ``required`` numeric keys from raw LLM
    output. Tolerates code fences / surrounding prose; clamps to [0, 1]; returns
    None when the JSON is absent, malformed, or missing any required key."""
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or any(k not in data for k in required):
        return None
    try:
        return {k: _clamp(data[k]) for k in required}
    except (TypeError, ValueError):
        return None


def parse_judge_response(text: str) -> dict | None:
    """Extract {faithfulness, answer_relevance} from raw judge output."""
    return _parse_scores(text, _REQUIRED)


def judge_answer(
    question: str,
    context_texts: list[str],
    answer: str,
    llm: BaseChatModel,
    config: dict | None = None,
) -> dict | None:
    """Ask ``llm`` to grade ``answer`` against the context. Returns the parsed
    scores, or None if the call fails or the output can't be parsed. ``config``
    carries the LangChain run config (e.g. Langfuse callbacks) when tracing is on.
    """
    context = "\n\n".join(context_texts) or "No context retrieved."
    prompt = _JUDGE_PROMPT.format(question=question, context=context, answer=answer)
    try:
        resp = llm.invoke([HumanMessage(content=prompt)], config=config)
    except Exception as exc:
        logger.warning("judge call failed: %s", exc)
        return None
    return parse_judge_response(str(resp.content))


def judge_context(
    question: str,
    context_texts: list[str],
    reference_answer: str | None,
    llm: BaseChatModel,
    config: dict | None = None,
) -> dict | None:
    """Grade *retrieval* quality, label-free (RAGAs-style context metrics):

      * **context_precision** — how much of the retrieved context is relevant to
        the question (always scored; measures noise the relevance gate should cut).
      * **context_recall** — how fully the context covers the reference answer
        (only when ``reference_answer`` is provided; else returned as None).

    Returns ``{"context_precision": float, "context_recall": float | None}`` or
    None if the call fails or the output can't be parsed."""
    context = "\n\n".join(context_texts) or "No context retrieved."
    has_ref = bool(reference_answer and reference_answer.strip())
    if has_ref:
        required = ("context_precision", "context_recall")
        prompt = _CONTEXT_PROMPT.format(
            ref_clause=" and the REFERENCE ANSWER",
            recall_line=_RECALL_LINE,
            schema='{{"context_precision": <float>, "context_recall": <float>}}',
            question=question, context=context,
            ref_block=f"\nREFERENCE ANSWER:\n{reference_answer}\n",
        )
    else:
        required = ("context_precision",)
        prompt = _CONTEXT_PROMPT.format(
            ref_clause="",
            recall_line="",
            schema='{{"context_precision": <float>}}',
            question=question, context=context, ref_block="",
        )
    try:
        resp = llm.invoke([HumanMessage(content=prompt)], config=config)
    except Exception as exc:
        logger.warning("context judge call failed: %s", exc)
        return None
    parsed = _parse_scores(str(resp.content), required)
    if parsed is None:
        return None
    return {
        "context_precision": parsed["context_precision"],
        "context_recall": parsed.get("context_recall"),
    }
