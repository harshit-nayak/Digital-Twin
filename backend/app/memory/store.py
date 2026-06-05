from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3

from app.config import get_settings


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9']+", text.lower()))


@dataclass
class Memory:
    id: int
    session_id: str
    kind: str
    content: str
    importance: float


class MemoryStore:
    _fallback_rows: list[Memory] = []
    _fallback_next_id = 1

    def __init__(self, db_path: str | None = None):
        settings = get_settings()
        self.path = settings.resolve(db_path or settings.memory_db_path)
        self.use_fallback = False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._init()
        except (OSError, sqlite3.Error):
            self.use_fallback = True

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance REAL NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def save(self, session_id: str, kind: str, content: str, importance: float = 0.5) -> int:
        compressed = content.strip()[:1200]
        if self.use_fallback:
            memory_id = MemoryStore._fallback_next_id
            MemoryStore._fallback_next_id += 1
            MemoryStore._fallback_rows.append(Memory(memory_id, session_id, kind, compressed, importance))
            return memory_id

        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO memories(session_id, kind, content, importance) VALUES (?, ?, ?, ?)",
                (session_id, kind, compressed, importance),
            )
            return int(cursor.lastrowid)

    def retrieve(self, query: str, session_id: str, limit: int = 5) -> list[Memory]:
        query_tokens = _tokens(query)
        if self.use_fallback:
            memories = [memory for memory in MemoryStore._fallback_rows if memory.session_id == session_id]
        else:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT id, session_id, kind, content, importance FROM memories WHERE session_id = ?",
                    (session_id,),
                ).fetchall()
            memories = [Memory(*row) for row in rows]
        return sorted(
            memories,
            key=lambda memory: (len(query_tokens & _tokens(memory.content)), memory.importance),
            reverse=True,
        )[:limit]

    def forget_session(self, session_id: str) -> int:
        if self.use_fallback:
            before = len(MemoryStore._fallback_rows)
            MemoryStore._fallback_rows = [
                memory for memory in MemoryStore._fallback_rows if memory.session_id != session_id
            ]
            return before - len(MemoryStore._fallback_rows)

        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM memories WHERE session_id = ?", (session_id,))
            return int(cursor.rowcount)


def retrieve_memory(query: str, session_id: str) -> list[Memory]:
    return MemoryStore().retrieve(query=query, session_id=session_id)
