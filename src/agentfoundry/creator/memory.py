from __future__ import annotations

import sqlite3
from pathlib import Path


class CreatorMemory:
    """Small SQLite memory store keyed by creator and audience member."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_schema(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS creator_memory (
                    creator_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    memory_key TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (creator_id, audience_id, memory_key)
                )
                """
            )

    def remember(self, creator_id: str, audience_id: str, key: str, value: str) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO creator_memory
                    (creator_id, audience_id, memory_key, memory_value, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(creator_id, audience_id, memory_key)
                DO UPDATE SET memory_value=excluded.memory_value,
                              updated_at=CURRENT_TIMESTAMP
                """,
                (creator_id, audience_id, key, value),
            )

    def recall(self, creator_id: str, audience_id: str) -> dict[str, str]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT memory_key, memory_value
                FROM creator_memory
                WHERE creator_id=? AND audience_id=?
                ORDER BY memory_key
                """,
                (creator_id, audience_id),
            ).fetchall()
        return dict(rows)
