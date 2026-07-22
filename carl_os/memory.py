from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import List

from .models import MemoryRecord


class SQLiteMemoryStore:
    def __init__(
        self,
        database_path: str | Path = "data/carl_memory.sqlite3",
    ) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    importance REAL NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_user_created
                ON memories(user_id, created_at DESC)
                """
            )

            connection.commit()

    def remember(
        self,
        user_id: str,
        record: MemoryRecord,
    ) -> MemoryRecord:
        if not user_id.strip():
            raise ValueError("user_id cannot be empty.")

        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memories (
                    memory_id,
                    user_id,
                    content,
                    kind,
                    importance,
                    source,
                    created_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.memory_id,
                    user_id,
                    record.content,
                    record.kind,
                    record.importance,
                    record.source,
                    record.created_at,
                    json.dumps(record.metadata, sort_keys=True),
                ),
            )

            connection.commit()

        return record

    def recent(
        self,
        user_id: str,
        limit: int = 20,
    ) -> List[MemoryRecord]:
        if limit < 1:
            return []

        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    memory_id,
                    content,
                    kind,
                    importance,
                    source,
                    created_at,
                    metadata_json
                FROM memories
                WHERE user_id = ?
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()

        return [
            MemoryRecord(
                memory_id=row["memory_id"],
                content=row["content"],
                kind=row["kind"],
                importance=float(row["importance"]),
                source=row["source"],
                created_at=row["created_at"],
                metadata=json.loads(row["metadata_json"]),
            )
            for row in rows
        ]

    def search(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
    ) -> List[MemoryRecord]:
        terms = [
            term.lower().strip(".,!?;:")
            for term in query.split()
            if len(term.strip(".,!?;:")) > 2
        ]

        candidates = self.recent(
            user_id,
            limit=max(limit * 5, 30),
        )

        if not terms:
            return candidates[:limit]

        ranked = []

        for memory in candidates:
            text = memory.content.lower()
            matches = sum(
                1 for term in terms
                if term in text
            )

            if matches:
                ranked.append(
                    (
                        matches,
                        memory.importance,
                        memory.created_at,
                        memory,
                    )
                )

        ranked.sort(
            key=lambda item: (
                item[0],
                item[1],
                item[2],
            ),
            reverse=True,
        )

        return [
            item[-1]
            for item in ranked[:limit]
        ]

    def delete(
        self,
        user_id: str,
        memory_id: str,
    ) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM memories
                WHERE user_id = ?
                AND memory_id = ?
                """,
                (
                    user_id,
                    memory_id,
                ),
            )

            connection.commit()

        return cursor.rowcount > 0
