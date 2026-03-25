from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Iterator

from fastapi import Request

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "quality.db"


# PUBLIC_INTERFACE
def get_db_path() -> Path:
    """Return the configured SQLite DB path.

    Environment variables:
      - QUALITY_DB_PATH: Optional override for where the SQLite file is stored.
    """
    configured = os.getenv("QUALITY_DB_PATH")
    return Path(configured).expanduser().resolve() if configured else DEFAULT_DB_PATH


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# PUBLIC_INTERFACE
def init_db() -> None:
    """Initialize the SQLite database schema if it doesn't exist."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS defects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                area TEXT,
                location TEXT,
                reported_by TEXT,
                assigned_to TEXT,
                root_cause TEXT,
                due_date TEXT, -- ISO date yyyy-mm-dd
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_defects_status ON defects(status);
            CREATE INDEX IF NOT EXISTS idx_defects_severity ON defects(severity);
            CREATE INDEX IF NOT EXISTS idx_defects_due_date ON defects(due_date);

            CREATE TABLE IF NOT EXISTS defect_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                defect_id INTEGER NOT NULL,
                file_name TEXT,
                content_type TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(defect_id) REFERENCES defects(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_defect_images_defect_id ON defect_images(defect_id);

            CREATE TABLE IF NOT EXISTS corrective_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                defect_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                owner TEXT,
                status TEXT NOT NULL,
                due_date TEXT, -- ISO date yyyy-mm-dd
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(defect_id) REFERENCES defects(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_actions_defect_id ON corrective_actions(defect_id);
            CREATE INDEX IF NOT EXISTS idx_actions_status ON corrective_actions(status);
            CREATE INDEX IF NOT EXISTS idx_actions_due_date ON corrective_actions(due_date);
            """
        )
        conn.commit()
    finally:
        conn.close()


# PUBLIC_INTERFACE
def get_db(request: Request) -> sqlite3.Connection:
    """Get a per-request SQLite connection stored on app.state."""
    return request.app.state.db  # type: ignore[attr-defined]


# PUBLIC_INTERFACE
def db_session(request: Request) -> Iterator[sqlite3.Connection]:
    """FastAPI dependency yielding a sqlite3 connection."""
    yield get_db(request)
