"""
backend/app/memory/database.py

SQLite database setup and schema.
Run init_db() once on startup to create all tables.
"""

import sqlite3
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH  = BASE_DIR / os.getenv("SQLITE_PATH", "db/memory.db")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row   # rows behave like dicts
    conn.execute("PRAGMA journal_mode=WAL")  # better concurrent access
    return conn


def init_db():
    """Create all tables if they don't exist. Safe to call on every startup."""
    conn = get_connection()
    cur  = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id    TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS memories (
            id             TEXT PRIMARY KEY,
            user_id        TEXT NOT NULL,
            scientist_id   TEXT NOT NULL,
            memory_type    TEXT NOT NULL,
            content        TEXT NOT NULL,
            importance     REAL DEFAULT 0.5,
            access_count   INTEGER DEFAULT 0,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            session_id    TEXT PRIMARY KEY,
            user_id       TEXT NOT NULL,
            scientist_id  TEXT NOT NULL,
            timeline_year INTEGER,
            summary       TEXT,
            started_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at      TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id            TEXT PRIMARY KEY,
            topics_explored    TEXT DEFAULT '[]',
            scientists_visited TEXT DEFAULT '[]',
            timeline_visits    TEXT DEFAULT '{}',
            depth_preferences  TEXT DEFAULT '{}',
            updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS retrieval_log (
            id               TEXT PRIMARY KEY,
            user_id          TEXT,
            scientist_id     TEXT,
            timeline_year    INTEGER,
            query            TEXT,
            rewritten_query  TEXT,
            chunks_retrieved TEXT,
            chunks_final     TEXT,
            faithfulness     REAL,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_memories_user
            ON memories(user_id, scientist_id);
        CREATE INDEX IF NOT EXISTS idx_memories_type
            ON memories(memory_type);
        CREATE INDEX IF NOT EXISTS idx_sessions_user
            ON sessions(user_id, scientist_id);
    """)

    conn.commit()
    conn.close()
    print(f"[DB] Initialized at {DB_PATH}")


if __name__ == "__main__":
    init_db()
