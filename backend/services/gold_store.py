"""Persistence for the RAG-eval gold set — a small JSON file on disk.

The gold set is a list of question / document-scope / expected-evidence triples
(``doc/rag_evaluation.md`` §4). It's intentionally a flat file rather than a DB
table: it's small (30–50 entries), edited rarely, and handy to commit alongside
the repo so eval runs are reproducible.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from config import settings

logger = logging.getLogger("chatpdf.eval")


def _path() -> Path:
    return Path(settings.eval_gold_path)


def load_gold() -> list[dict]:
    """Return the saved gold items, or [] when the file is absent/unreadable."""
    path = _path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except (ValueError, OSError) as exc:
        logger.warning("could not read gold set at %s: %s", path, exc)
        return []
    return data if isinstance(data, list) else []


def save_gold(items: list[dict]) -> None:
    """Overwrite the gold set on disk (creating parent dirs as needed)."""
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2))
    logger.info("saved gold set: %d items → %s", len(items), path)
