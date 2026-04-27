from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


class FollowupState:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def was_reported(self, thread_key: str, message_id: int) -> bool:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                "SELECT 1 FROM reported_items WHERE thread_key = ? AND message_id = ?",
                (thread_key, message_id),
            ).fetchone()
        return row is not None

    def mark_reported(self, thread_key: str, message_id: int) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO reported_items(thread_key, message_id, reported_at)
                VALUES (?, ?, ?)
                """,
                (thread_key, message_id, datetime.now().isoformat(timespec="seconds")),
            )

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reported_items (
                    thread_key TEXT NOT NULL,
                    message_id INTEGER NOT NULL,
                    reported_at TEXT NOT NULL,
                    PRIMARY KEY (thread_key, message_id)
                )
                """
            )
