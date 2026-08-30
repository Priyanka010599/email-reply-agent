"""SQLite connection helper. Creates the database file's parent directory on demand."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def get_connection(database_path: str) -> sqlite3.Connection:
    path = Path(database_path)
    if path.parent != Path("") and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
