"""RAG evaluation API — powers the frontend "RAG Evaluation" page.

Endpoints
---------
GET  /api/eval/gold      → the saved gold set
PUT  /api/eval/gold      → replace the gold set
GET  /api/eval/presets   → suggested RAGConfig variants to compare
POST /api/eval/run       → run retrieval (and optional LLM-judge) over the gold set

Retrieval metrics are deterministic and need no API key. The LLM-judge half is
opt-in and gracefully degrades to retrieval-only (with a warning) when the
chosen provider has no key configured.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session as DBSession

from config import settings
from db import get_db
from services import eval_history, gold_store, tracing
from services.eval_runner import run_eval
from services.llm_gateway import LLMGateway, get_llm_gateway
from services.model_catalog import MODEL_CATALOG
from services.rag_config import RAGConfig
from vector_store import VectorStore, get_vector_store

router = APIRouter(prefix="/api/eval", tags=["eval"])
logger = logging.getLogger("chatpdf.eval")

# Curated config variants mirroring the comparison table in doc/rag_evaluation.md §5.
_PRESETS = [
    # First pair isolates the relevance gate's effect (everything else equal) —
    # compare context_precision between them to see the noise the gate removes.
    {"label": "dense (no gate)", "overrides": {"retriever": "dense", "top_k": 5, "relevance_gate": None}},
    {"label": "dense + gate", "overrides": {"retriever": "dense", "top_k": 5}},  # gate on (default)
    {"label": "hybrid α0.5", "overrides": {"retriever": "hybrid", "hybrid_alpha": 0.5, "top_k": 5}},
    {"label": "hybrid α0.3", "overrides": {"retriever": "hybrid", "hybrid_alpha": 0.3, "top_k": 5}},
    {
        "label": "hybrid + rerank",
        "overrides": {
            "retriever": "hybrid", "hybrid_alpha": 0.4, "top_k": 10,
            "reranker": "cross_encoder", "rerank_top_n": 5,
        },
    },
]

_VALID_FIELDS = set(RAGConfig.__dataclass_fields__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class GoldItem(BaseModel):
    id: str | None = None
    question: str
    doc_ids: list[str] = []
    relevant_substrings: list[str] = []
    reference_answer: str | None = None


class GoldSet(BaseModel):
    items: list[GoldItem]


class ConfigVariant(BaseModel):
    label: str
    overrides: dict = {}


class JudgeSpec(BaseModel):
    enabled: bool = False
    answer_provider: str | None = None
    answer_model: str | None = None
    judge_provider: str | None = None
    judge_model: str | None = None


class EvalRunRequest(BaseModel):
    configs: list[ConfigVariant]
    k: int = 5
    judge: JudgeSpec = JudgeSpec()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_config(overrides: dict, k: int) -> RAGConfig:
    clean = {key: v for key, v in overrides.items() if key in _VALID_FIELDS}
    clean.setdefault("top_k", k)
    return RAGConfig(**clean)


def _has_key(provider: str) -> bool:
    return bool({
        "openai": settings.openai_api_key,
        "google": settings.resolved_google_api_key,
        "anthropic": settings.anthropic_api_key,
    }.get(provider, ""))


def _pick(provider: str | None, model: str | None) -> tuple[str, str] | None:
    """Resolve an explicit provider/model, else the first provider in the catalog
    order (OpenAI → Google → Anthropic) that has a key configured.

    Note: judging with the same family that answered risks self-preference bias
    (``doc/rag_evaluation.md`` §3); set ``judge_provider`` explicitly to a
    different family when you have keys for more than one."""
    if provider:
        if not _has_key(provider):
            return None
        return provider, model or MODEL_CATALOG[provider][0]
    for p in MODEL_CATALOG:
        if _has_key(p):
            return p, MODEL_CATALOG[p][0]
    return None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/gold", response_model=GoldSet)
def get_gold() -> GoldSet:
    return GoldSet(items=[GoldItem(**g) for g in gold_store.load_gold()])


@router.put("/gold", response_model=GoldSet)
def put_gold(body: GoldSet) -> GoldSet:
    gold_store.save_gold([g.model_dump() for g in body.items])
    return body


@router.get("/presets")
def get_presets() -> dict:
    return {"presets": _PRESETS}


@router.get("/tracing")
def get_tracing() -> dict:
    """Whether Langfuse tracing is configured — drives the UI status banner."""
    return tracing.status()


@router.get("/history")
def get_history(db: DBSession = Depends(get_db)) -> dict:
    """Past runs (aggregate metrics only) for the trend charts."""
    return {"runs": eval_history.load_history(db)}


@router.post("/run")
def run(
    body: EvalRunRequest,
    vs: VectorStore = Depends(get_vector_store),
    gateway: LLMGateway = Depends(get_llm_gateway),
    db: DBSession = Depends(get_db),
) -> dict:
    gold = gold_store.load_gold()
    variants = [(c.label, _build_config(c.overrides, body.k)) for c in body.configs]

    warnings: list[str] = []
    answer_llm = judge_llm = None

    if body.judge.enabled:
        answerer = _pick(body.judge.answer_provider, body.judge.answer_model)
        if not answerer:
            warnings.append("Generation skipped: no API key configured for any provider.")
        else:
            judge = _pick(body.judge.judge_provider, body.judge.judge_model)
            if not judge:
                warnings.append("Judge skipped: no API key configured for the judge provider.")
            else:
                answer_llm = gateway.get_llm(*answerer, temperature=0.0)
                judge_llm = gateway.get_llm(*judge, temperature=0.0)

    result = run_eval(gold, variants, vs, body.k, answer_llm=answer_llm, judge_llm=judge_llm)

    # If the judge ran but produced no scores at all, the call likely failed
    # (bad key / model error) — say so rather than silently showing blanks.
    if result["judge_enabled"] and gold and all(
        r["metrics"]["faithfulness"] is None for r in result["results"]
    ):
        warnings.append("Judge produced no scores — check the judge provider's API key and model.")

    # Persist the run so the trend charts have history (best-effort — a storage
    # hiccup must not fail the response the user is waiting on).
    if gold:
        try:
            eval_history.save_run(db, result)
        except Exception:
            logger.exception("failed to persist eval run to history")

    result["warnings"] = warnings
    result["tracing_enabled"] = tracing.is_enabled()
    return result
