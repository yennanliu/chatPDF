#!/usr/bin/env python3
"""One-shot migration for the Library removal.

The app self-heals on startup (`init_db` → `_migrate_legacy_schema`), so this
script is only needed to migrate a DB without starting the server (e.g. a deploy
step). It drops the legacy library tables and the unmigratable session/message
rows — uploaded documents are preserved — then rebuilds the new schema.

Run from the backend dir:  uv run python scripts/migrate_remove_libraries.py
Safe to run more than once.
"""
import sys
from pathlib import Path

# Allow running as `python scripts/...` from the backend dir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect  # noqa: E402

import models.tables  # noqa: E402,F401 — registers tables on SQLModel.metadata
from db import engine, init_db  # noqa: E402


def main() -> None:
    init_db()  # runs _migrate_legacy_schema() then create_all()
    tables = sorted(inspect(engine).get_table_names())
    print(f"Migration complete. Tables: {tables}")


if __name__ == "__main__":
    main()
