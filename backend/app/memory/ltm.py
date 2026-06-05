"""
backend/app/memory/ltm.py

Long-Term Memory (LTM) system.
Stores persistent facts about users across sessions.
Memory is RETRIEVED (relevance-searched), not blindly injected.

Memory types:
    identity   — who the user is (name, background)
    goal       — what they want to learn
    topic      — subjects they have explored
    episode    — notable exchanges or analogies that worked
    preference — how they like to learn
"""

import uuid
import json
import time
import sqlite3
from datetime import datetime
from pathlib import Path

from app.memory.database import get_connection

# ── Constants ─────────────────────────────────────────────────────────────────

MEMORY_TYPES       = {"identity", "goal", "topic", "episode", "preference"}
IMPORTANCE_DECAY   = 0.95    # per day decay factor
MIN_IMPORTANCE     = 0.1     # floor — never decay below this
CONFLICT_THRESHOLD = 0.85    # similarity score above which we update vs append
MAX_LTM_TOKENS     = 150     # max tokens to inject into prompt


# ── User management ───────────────────────────────────────────────────────────

def ensure_user(user_id: str):
    """Create user record if it doesn't exist."""
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
        (user_id,)
    )
    conn.execute(
        "INSERT OR IGNORE INTO user_profiles (user_id) VALUES (?)",
        (user_id,)
    )
    conn.commit()
    conn.close()


# ── Write memory ──────────────────────────────────────────────────────────────

def write_memory(
    user_id       : str,
    scientist_id  : str,
    memory_type   : str,
    content       : str,
    importance    : float = 0.7,
) -> str:
    """
    Write a new memory entry.
    Checks for conflicts first — updates existing if similar memory found.

    Returns the memory ID.
    """
    assert memory_type in MEMORY_TYPES, f"Invalid memory type: {memory_type}"

    ensure_user(user_id)

    # Check for conflicts
    existing = get_memories_by_type(user_id, scientist_id, memory_type)
    conflict  = find_conflict(content, existing)

    conn = get_connection()

    if conflict:
        # Update existing memory rather than create duplicate
        conn.execute("""
            UPDATE memories
            SET content      = ?,
                importance   = MAX(importance, ?),
                access_count = access_count + 1,
                last_accessed = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (content, importance, conflict["id"]))
        conn.commit()
        conn.close()
        print(f"[LTM] Updated existing {memory_type} memory: {content[:60]}")
        return conflict["id"]

    # New memory
    memory_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO memories
            (id, user_id, scientist_id, memory_type, content, importance)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (memory_id, user_id, scientist_id, memory_type, content, importance))

    conn.commit()
    conn.close()
    print(f"[LTM] Stored {memory_type} memory: {content[:60]}")
    return memory_id


# ── Read memories ─────────────────────────────────────────────────────────────

def get_memories_by_type(
    user_id      : str,
    scientist_id : str,
    memory_type  : str,
) -> list[dict]:
    """Get all memories of a specific type for a user + scientist."""
    conn    = get_connection()
    rows    = conn.execute("""
        SELECT * FROM memories
        WHERE user_id = ? AND scientist_id = ? AND memory_type = ?
        ORDER BY importance DESC, last_accessed DESC
    """, (user_id, scientist_id, memory_type)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_memories(
    user_id      : str,
    scientist_id : str,
) -> list[dict]:
    """Get all memories for a user + scientist, sorted by importance."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM memories
        WHERE user_id = ? AND scientist_id = ?
        ORDER BY importance DESC, last_accessed DESC
    """, (user_id, scientist_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_memories(
    user_id      : str,
    scientist_id : str,
    query        : str,
    top_k        : int = 5,
    min_importance: float = 0.3,
) -> list[dict]:
    """
    Search memories by keyword relevance.
    Simple keyword matching — good enough for LTM retrieval.
    Returns top_k most relevant memories above min_importance threshold.
    """
    all_mems = get_all_memories(user_id, scientist_id)

    if not all_mems:
        return []

    # Apply importance decay
    all_mems = [apply_decay(m) for m in all_mems]

    # Filter by minimum importance
    all_mems = [m for m in all_mems if m["importance"] >= min_importance]

    if not all_mems:
        return []

    # Score by keyword overlap with query
    query_words = set(query.lower().split())

    def relevance_score(memory: dict) -> float:
        content_words = set(memory["content"].lower().split())
        overlap       = len(query_words & content_words)
        base_score    = overlap / max(len(query_words), 1)
        # Weight by importance
        return base_score * 0.6 + memory["importance"] * 0.4

    scored = sorted(all_mems, key=relevance_score, reverse=True)

    # Update last_accessed for returned memories
    returned = scored[:top_k]
    update_access(user_id, [m["id"] for m in returned])

    return returned


def get_memories_for_prompt(
    user_id      : str,
    scientist_id : str,
    query        : str,
) -> str:
    """
    Retrieve relevant memories and format them for prompt injection.
    Hard limit: MAX_LTM_TOKENS tokens (~600 chars).
    """
    memories = search_memories(user_id, scientist_id, query, top_k=6)

    if not memories:
        return ""

    lines = []
    total_chars = 0
    char_limit  = MAX_LTM_TOKENS * 4  # ~4 chars per token

    for mem in memories:
        line = f"[{mem['memory_type'].upper()}] {mem['content']}"
        if total_chars + len(line) > char_limit:
            break
        lines.append(line)
        total_chars += len(line)

    return "\n".join(lines)


# ── Memory extraction from conversation ──────────────────────────────────────

def extract_memories_from_exchange(
    user_message      : str,
    assistant_message : str,
    user_id           : str,
    scientist_id      : str,
):
    """
    Simple rule-based memory extraction from a conversation exchange.
    Looks for explicit statements about the user.

    For production, this would be an LLM call.
    Here we use pattern matching to keep it fast and free.
    """
    text = user_message.lower()

    # Identity patterns
    identity_patterns = [
        ("my name is ", "identity"),
        ("i am ", "identity"),
        ("i'm ", "identity"),
        ("call me ", "identity"),
    ]
    for pattern, mtype in identity_patterns:
        if pattern in text:
            idx     = text.index(pattern) + len(pattern)
            content = user_message[idx:idx+60].split(".")[0].strip()
            if len(content) > 2:
                write_memory(user_id, scientist_id, mtype,
                             f"User's name/identity: {content}", importance=1.0)

    # Goal patterns
    goal_patterns = [
        "i want to learn",
        "i'm trying to understand",
        "i need to know",
        "my goal is",
        "i want to understand",
    ]
    for pattern in goal_patterns:
        if pattern in text:
            idx     = text.index(pattern)
            content = user_message[idx:idx+100].split(".")[0].strip()
            write_memory(user_id, scientist_id, "goal",
                         f"User goal: {content}", importance=0.9)

    # Topic tracking — what topics were discussed
    physics_topics = [
        "relativity", "quantum", "gravity", "photoelectric", "spacetime",
        "light", "energy", "mass", "time dilation", "equivalence",
        "wave", "particle", "uncertainty", "electromagnetism"
    ]
    for topic in physics_topics:
        if topic in text or topic in assistant_message.lower():
            write_memory(user_id, scientist_id, "topic",
                         f"Discussed topic: {topic}", importance=0.6)


# ── Session management ────────────────────────────────────────────────────────

def start_session(
    user_id       : str,
    scientist_id  : str,
    timeline_year : int,
) -> str:
    """Create a new session record. Returns session_id."""
    ensure_user(user_id)
    session_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute("""
        INSERT INTO sessions (session_id, user_id, scientist_id, timeline_year)
        VALUES (?, ?, ?, ?)
    """, (session_id, user_id, scientist_id, timeline_year))
    conn.commit()
    conn.close()
    return session_id


def end_session(session_id: str, summary: str):
    """Mark session as ended and store compressed summary."""
    conn = get_connection()
    conn.execute("""
        UPDATE sessions
        SET ended_at = CURRENT_TIMESTAMP, summary = ?
        WHERE session_id = ?
    """, (summary, session_id))
    conn.commit()
    conn.close()


def get_recent_sessions(
    user_id      : str,
    scientist_id : str,
    limit        : int = 3,
) -> list[dict]:
    """Get most recent session summaries for a user."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM sessions
        WHERE user_id = ? AND scientist_id = ? AND summary IS NOT NULL
        ORDER BY ended_at DESC
        LIMIT ?
    """, (user_id, scientist_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Profile management ────────────────────────────────────────────────────────

def update_profile(user_id: str, scientist_id: str, topic: str = None, year: int = None):
    """Update user profile with new topic or timeline visit."""
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
    ).fetchone()

    if not row:
        ensure_user(user_id)
        row = conn.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()

    topics   = json.loads(row["topics_explored"]    or "[]")
    visits   = json.loads(row["timeline_visits"]    or "{}")
    visited  = json.loads(row["scientists_visited"] or "[]")

    if topic and topic not in topics:
        topics.append(topic)

    if year:
        if scientist_id not in visits:
            visits[scientist_id] = []
        if year not in visits[scientist_id]:
            visits[scientist_id].append(year)

    if scientist_id not in visited:
        visited.append(scientist_id)

    conn.execute("""
        UPDATE user_profiles
        SET topics_explored    = ?,
            timeline_visits    = ?,
            scientists_visited = ?,
            updated_at         = CURRENT_TIMESTAMP
        WHERE user_id = ?
    """, (json.dumps(topics), json.dumps(visits), json.dumps(visited), user_id))

    conn.commit()
    conn.close()


def get_profile(user_id: str) -> dict:
    """Get user profile."""
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        return {}
    return dict(row)


# ── Memory deletion ───────────────────────────────────────────────────────────

def delete_memory(memory_id: str, user_id: str):
    """Delete a specific memory (user-initiated from sidebar)."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM memories WHERE id = ? AND user_id = ?",
        (memory_id, user_id)
    )
    conn.commit()
    conn.close()


def clear_all_memories(user_id: str, scientist_id: str):
    """Clear all memories for a user + scientist."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM memories WHERE user_id = ? AND scientist_id = ?",
        (user_id, scientist_id)
    )
    conn.commit()
    conn.close()
    print(f"[LTM] Cleared all memories for {user_id}/{scientist_id}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def apply_decay(memory: dict) -> dict:
    """Apply time-based importance decay."""
    try:
        last = datetime.fromisoformat(memory["last_accessed"])
        days = (datetime.now() - last).days
        decayed = memory["importance"] * (IMPORTANCE_DECAY ** days)
        memory  = dict(memory)
        memory["importance"] = max(decayed, MIN_IMPORTANCE)
    except Exception:
        pass
    return memory


def find_conflict(new_content: str, existing: list[dict]) -> dict | None:
    """
    Check if a similar memory already exists.
    Simple word-overlap check — returns existing memory if conflict found.
    """
    new_words = set(new_content.lower().split())
    for mem in existing:
        existing_words = set(mem["content"].lower().split())
        if not new_words or not existing_words:
            continue
        overlap = len(new_words & existing_words) / max(len(new_words), len(existing_words))
        if overlap >= CONFLICT_THRESHOLD:
            return mem
    return None


def update_access(user_id: str, memory_ids: list[str]):
    """Update last_accessed and increment access_count for retrieved memories."""
    if not memory_ids:
        return
    conn = get_connection()
    placeholders = ",".join("?" * len(memory_ids))
    conn.execute(f"""
        UPDATE memories
        SET last_accessed = CURRENT_TIMESTAMP,
            access_count  = access_count + 1
        WHERE id IN ({placeholders}) AND user_id = ?
    """, (*memory_ids, user_id))
    conn.commit()
    conn.close()
