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


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def parse_judge_response(text: str) -> dict | None:
    """Extract {faithfulness, answer_relevance} from raw judge output.

    Tolerates code fences and surrounding prose; clamps scores to [0, 1];
    returns None when the JSON is absent, malformed, or missing an axis.
    """
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or any(k not in data for k in _REQUIRED):
        return None
    try:
        return {k: _clamp(data[k]) for k in _REQUIRED}
    except (TypeError, ValueError):
        return None


def judge_answer(
    question: str,
    context_texts: list[str],
    answer: str,
    llm: BaseChatModel,
) -> dict | None:
    """Ask ``llm`` to grade ``answer`` against the context. Returns the parsed
    scores, or None if the call fails or the output can't be parsed."""
    context = "\n\n".join(context_texts) or "No context retrieved."
    prompt = _JUDGE_PROMPT.format(question=question, context=context, answer=answer)
    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
    except Exception as exc:
        logger.warning("judge call failed: %s", exc)
        return None
    return parse_judge_response(str(resp.content))
