"""Persistence for RAG-evaluation runs.

Only the per-variant *aggregate* metrics are stored (not the per-question
drill-down) — just enough to chart quality trends over time on the Evaluation
page. Backed by the ``eval_run`` table.
"""
from __future__ import annotations

import json
import logging

from sqlmodel import Session, select

from models.tables import EvalRun

logger = logging.getLogger("chatpdf.eval")

_DEFAULT_LIMIT = 30


def save_run(db: Session, result: dict) -> EvalRun:
    """Persist the headline metrics of a completed run (``run_eval`` output)."""
    summary = [
        {"label": r["label"], "config": r.get("config", {}), "metrics": r["metrics"]}
        for r in result.get("results", [])
    ]
    row = EvalRun(
        k=result.get("k", 0),
        n_questions=result.get("n_questions", 0),
        judge_enabled=bool(result.get("judge_enabled")),
        summary=json.dumps(summary),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def load_history(db: Session, limit: int = _DEFAULT_LIMIT) -> list[dict]:
    """Return up to ``limit`` recent runs, oldest→newest (left-to-right charts)."""
    rows = db.exec(
        select(EvalRun).order_by(EvalRun.created_at.desc()).limit(limit)
    ).all()
    out = []
    for r in reversed(rows):  # flip desc → chronological
        try:
            summary = json.loads(r.summary)
        except (ValueError, TypeError):
            logger.warning("eval_run %s has unparseable summary; skipping", r.id)
            continue
        out.append({
            "id": r.id,
            "created_at": r.created_at.isoformat(),
            "k": r.k,
            "n_questions": r.n_questions,
            "judge_enabled": r.judge_enabled,
            "summary": summary,
        })
    return out
