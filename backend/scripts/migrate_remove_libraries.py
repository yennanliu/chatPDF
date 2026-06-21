#!/usr/bin/env python3
"""One-shot, idempotent migration for the Library removal.

`SQLModel.metadata.create_all` is additive only — it can't drop the gone
`library`/`library_document` tables or reshape the `session` table (which lost
`library_id` and gained `rag_config`). This script does that once.

It PRESERVES your uploaded documents (and their ChromaDB vectors / files) and
drops only the library tables plus old chat sessions/messages, which referenced
libraries and can't be mapped onto the new session→documents model. The fresh
schema is then recreated by init_db().

Run from the backend dir:  uv run python scripts/migrate_remove_libraries.py
Safe to run more than once.
"""
import sqlite3
import sys
from pathlib import Path

# Allow running as `python scripts/...` from the backend dir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from db import init_db  # noqa: E402

DB_PATH = settings.sqlite_url.replace("sqlite:///", "")

# Old tables/columns that no longer exist in the model.
DROP_TABLES = ["library_document", "library", "message", "session"]


def main() -> None:
    db_file = Path(DB_PATH)
    if not db_file.exists():
        print(f"No DB at {db_file} — nothing to migrate. init_db() will create a fresh schema.")
        init_db()
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    existing = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    dropped = []
    for table in DROP_TABLES:
        if table in existing:
            cur.execute(f"DROP TABLE IF EXISTS {table}")
            dropped.append(table)
    con.commit()
    con.close()

    print(f"Dropped tables: {dropped or '(none — already migrated)'}")
    print("Documents preserved. Recreating fresh schema (session, message, session_document)…")
    init_db()
    print("Done.")


if __name__ == "__main__":
    main()
