import sqlite3

from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from config import settings

engine = create_engine(
    settings.sqlite_url,
    connect_args={"check_same_thread": False},
    echo=False,
)

# Tables that no longer exist after the Library removal.
_LEGACY_TABLES = ("library_document", "library")


@event.listens_for(Engine, "connect")
def _sqlite_fk_pragma(dbapi_connection, _record) -> None:
    """Enable FK enforcement (and CASCADE) for every SQLite connection."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _migrate_legacy_schema() -> None:
    """Idempotent self-heal for DBs created before the Library removal.

    `create_all` is additive-only, so a pre-existing DB keeps the gone library
    tables and a `session` table that still has `library_id` / lacks `rag_config`.
    Drop the legacy tables and the unmigratable session/message rows (uploaded
    documents are preserved); `create_all` then rebuilds the new schema. Once
    migrated this is a no-op, so it is safe to run on every startup.
    """
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    legacy_session = False
    if "session" in tables:
        cols = {c["name"] for c in insp.get_columns("session")}
        legacy_session = "library_id" in cols or "rag_config" not in cols

    if not (tables & set(_LEGACY_TABLES)) and not legacy_session:
        return  # already on the current schema

    with engine.begin() as conn:
        for t in _LEGACY_TABLES:
            conn.execute(text(f"DROP TABLE IF EXISTS {t}"))
        if legacy_session:
            conn.execute(text("DROP TABLE IF EXISTS message"))
            conn.execute(text("DROP TABLE IF EXISTS session"))


def init_db() -> None:
    _migrate_legacy_schema()
    SQLModel.metadata.create_all(engine)


def get_db():
    with Session(engine) as session:
        yield session
