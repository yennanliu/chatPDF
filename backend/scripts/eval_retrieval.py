#!/usr/bin/env python3
"""Retrieval evaluation runner (§5.8).

Reads a gold-set JSON, runs the configured retriever against the live vector
store for each query, and prints Hit@k / Recall@k / MRR. See
``doc/rag_evaluation.md`` for the gold-set format.

Gold-set shape:
    [
      {"query": "...", "doc_ids": ["..."], "relevant": ["<doc_id>_<chunk_index>", ...]},
      ...
    ]

Run from the backend dir:
    uv run python scripts/eval_retrieval.py gold.json --top-k 5 --retriever hybrid
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.eval import aggregate  # noqa: E402
from services.rag_config import RAGConfig, build_retriever  # noqa: E402
from vector_store import get_vector_store  # noqa: E402


def _chunk_id(meta: dict) -> str:
    return f"{meta.get('doc_id')}_{meta.get('chunk_index')}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate retrieval quality against a gold set.")
    ap.add_argument("gold", help="Path to gold-set JSON")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--retriever", default="dense", choices=["dense", "hybrid"])
    ap.add_argument("--alpha", type=float, default=0.5)
    args = ap.parse_args()

    gold = json.loads(Path(args.gold).read_text())
    cfg = RAGConfig(retriever=args.retriever, hybrid_alpha=args.alpha, top_k=args.top_k)
    vs = get_vector_store()
    retriever = build_retriever(cfg, vs)

    rows = []
    for item in gold:
        hits = retriever.search(item["query"], args.top_k, item["doc_ids"])
        rows.append({
            "retrieved": [_chunk_id(h["metadata"]) for h in hits],
            "relevant": item["relevant"],
        })

    metrics = aggregate(rows, k=args.top_k)
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
