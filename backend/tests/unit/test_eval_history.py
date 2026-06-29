"""TDD — eval run-history persistence (services/eval_history.py).

Contract:
  save_run(db, result)  — persist per-variant aggregate metrics from a run.
  load_history(db, lim) — return runs in chronological order (oldest→newest),
                          capped at ``lim``, each with its summary metrics.
The large per-question drill-down is dropped; only headline metrics are kept.
"""
from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

from services import eval_history


def _engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng)
    return eng


def _result(hit, *, label="dense", k=5, n=2, judge=False):
    return {
        "k": k, "n_questions": n, "judge_enabled": judge,
        "results": [{
            "label": label,
            "config": {"retriever": "dense"},
            "metrics": {"hit@k": hit, "ndcg@k": hit, "faithfulness": None},
            "per_question": [{"question": "q", "hit": True}],  # dropped on persist
        }],
    }


def test_save_then_load_roundtrips_summary():
    with Session(_engine()) as db:
        eval_history.save_run(db, _result(1.0))
        runs = eval_history.load_history(db)
    assert len(runs) == 1
    run = runs[0]
    assert run["k"] == 5
    assert run["n_questions"] == 2
    assert run["summary"][0]["label"] == "dense"
    assert run["summary"][0]["metrics"]["hit@k"] == 1.0
    # Heavy per-question payload must not be stored in the summary.
    assert "per_question" not in run["summary"][0]


def test_load_history_is_chronological_and_capped():
    eng = _engine()
    with Session(eng) as db:
        for i in range(5):
            eval_history.save_run(db, _result(i / 10.0))
        runs = eval_history.load_history(db, limit=3)
    # Capped to the 3 most-recent, returned oldest→newest for left-to-right charts.
    assert len(runs) == 3
    hits = [r["summary"][0]["metrics"]["hit@k"] for r in runs]
    assert hits == [0.2, 0.3, 0.4]


def test_empty_history():
    with Session(_engine()) as db:
        assert eval_history.load_history(db) == []
