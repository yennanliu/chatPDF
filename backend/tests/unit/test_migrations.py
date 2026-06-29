"""TDD — versioned migration runner (§1.6) and defensive source parsing (§1.7)."""
from sqlalchemy import text
from sqlmodel import create_engine

from migrations import run_migrations
from routers.sessions import _parse_sources


def test_migrations_apply_once_and_are_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    first = run_migrations(engine)
    assert "0001_remove_library" in first
    # Second run applies nothing.
    assert run_migrations(engine) == []


def test_migrations_record_versions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    run_migrations(engine)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT version FROM schema_migrations")).fetchall()
    assert ("0001_remove_library",) in rows


def test_migration_0001_drops_legacy_library_table(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE library (id TEXT PRIMARY KEY)"))
    run_migrations(engine)
    with engine.connect() as conn:
        names = {r[0] for r in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()}
    assert "library" not in names


# ── §1.7 defensive source parsing ──────────────────────────────────────────────

def test_parse_sources_valid():
    assert _parse_sources('[{"doc_name": "a.pdf"}]') == [{"doc_name": "a.pdf"}]


def test_parse_sources_none():
    assert _parse_sources(None) is None


def test_parse_sources_malformed_returns_none():
    assert _parse_sources("{not json") is None
    assert _parse_sources('{"not": "a list"}') is None
