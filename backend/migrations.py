"""Versioned, tracked schema migrations (§1.6).

A real migration story without a heavy dependency: each migration has a unique
ordered id and runs at most once, recorded in a ``schema_migrations`` table.
This replaces the previous "self-heal on every startup" guesswork — you can see
exactly which versions a database is on.

Add a migration by appending a ``Migration`` to ``MIGRATIONS``; never edit or
reorder an already-released one. ``create_all`` still creates brand-new tables;
migrations handle *changes* to existing data/schema.

(For teams that prefer it, Alembic is the heavier industry-standard alternative;
this runner is intentionally minimal and SQLite-friendly.)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

logger = logging.getLogger("chatpdf.migrations")

_LEGACY_TABLES = ("library_document", "library")


@dataclass(frozen=True)
class Migration:
    version: str
    description: str
    run: Callable[[Connection], None]


def _0001_remove_library(conn: Connection) -> None:
    """Drop legacy Library tables and unmigratable session/message rows.

    ``create_all`` is additive-only, so a pre-Library-removal DB keeps the gone
    tables and a ``session`` lacking ``rag_config``; rebuild after dropping.
    """
    for t in _LEGACY_TABLES:
        conn.execute(text(f"DROP TABLE IF EXISTS {t}"))
    # Detect a legacy session shape and reset session/message so create_all rebuilds.
    cols = conn.execute(text("PRAGMA table_info('session')")).fetchall()
    names = {row[1] for row in cols}
    if cols and ("library_id" in names or "rag_config" not in names):
        conn.execute(text("DROP TABLE IF EXISTS message"))
        conn.execute(text("DROP TABLE IF EXISTS session"))


def _0002_add_message_metrics(conn: Connection) -> None:
    """Add the ``metrics`` column to ``message`` (per-response quality scores).

    ``create_all`` is additive at the table level only — it won't add a column to
    an existing table — so an established DB needs this ALTER. Idempotent: skip
    when the column is already present (or the table doesn't exist yet)."""
    cols = conn.execute(text("PRAGMA table_info('message')")).fetchall()
    if cols and not any(row[1] == "metrics" for row in cols):
        conn.execute(text("ALTER TABLE message ADD COLUMN metrics TEXT"))


MIGRATIONS: list[Migration] = [
    Migration("0001_remove_library", "Drop legacy Library tables/columns", _0001_remove_library),
    Migration("0002_add_message_metrics", "Add message.metrics column", _0002_add_message_metrics),
]


def _applied(conn: Connection) -> set[str]:
    conn.execute(text(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version TEXT PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    ))
    rows = conn.execute(text("SELECT version FROM schema_migrations")).fetchall()
    return {r[0] for r in rows}


def run_migrations(engine: Engine) -> list[str]:
    """Apply all pending migrations in order. Returns the versions applied."""
    applied: list[str] = []
    with engine.begin() as conn:
        done = _applied(conn)
        for m in MIGRATIONS:
            if m.version in done:
                continue
            logger.info("applying migration %s — %s", m.version, m.description)
            m.run(conn)
            conn.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:v)"),
                {"v": m.version},
            )
            applied.append(m.version)
    return applied
