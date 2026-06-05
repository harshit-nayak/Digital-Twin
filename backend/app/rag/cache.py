"""
backend/app/rag/cache.py

Retrieval result cache — in-memory dict with TTL=1 hour.
Avoids re-running the full RAG pipeline for identical queries.

Also contains the retrieval logger (writes to logs/retrieval_log.jsonl).
"""

import time
import json
import hashlib
import uuid
from pathlib import Path

# ── Cache ─────────────────────────────────────────────────────────────────────

_cache: dict = {}   # key → {"chunks": list, "ts": float}
CACHE_TTL    = 3600  # 1 hour


def get_cache_key(scientist_id: str, timeline_year: int, query: str) -> str:
    """Build a deterministic cache key."""
    raw = f"{scientist_id}:{timeline_year}:{query.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_cached_retrieval(key: str) -> list | None:
    """Return cached chunks if they exist and are not expired."""
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < CACHE_TTL:
        print(f"[CACHE] Hit for key {key[:8]}...")
        return entry["chunks"]
    return None


def cache_retrieval(key: str, chunks: list):
    """Store chunks in cache with current timestamp."""
    _cache[key] = {"chunks": chunks, "ts": time.time()}
    print(f"[CACHE] Stored {len(chunks)} chunks for key {key[:8]}...")


def clear_expired():
    """Remove expired entries (call periodically if needed)."""
    now     = time.time()
    expired = [k for k, v in _cache.items() if now - v["ts"] >= CACHE_TTL]
    for k in expired:
        del _cache[k]
    if expired:
        print(f"[CACHE] Cleared {len(expired)} expired entries")


def cache_size() -> int:
    """Return number of entries currently in cache."""
    return len(_cache)


# ── Retrieval Logger ──────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_retrieval(
    user_id        : str,
    scientist_id   : str,
    timeline_year  : int,
    query          : str,
    rewritten_query: str,
    sub_queries    : list,
    chunks_initial : list,
    chunks_final   : list,
    faithfulness   : float,
    response_text  : str,
    mode           : str = "chat",
):
    """
    Append one retrieval event to the daily JSONL log.

    Review this file during development to see:
    - Which queries are failing retrieval
    - Whether faithfulness scores are trending low
    - Which sources are most frequently retrieved
    """
    try:
        log_path = LOG_DIR / "retrieval_log.jsonl"
        entry = {
            "id"             : str(uuid.uuid4())[:8],
            "timestamp"      : time.strftime("%Y-%m-%dT%H:%M:%S"),
            "user_id"        : user_id,
            "scientist_id"   : scientist_id,
            "timeline_year"  : timeline_year,
            "mode"           : mode,
            "query"          : query,
            "rewritten_query": rewritten_query,
            "sub_queries"    : sub_queries,
            "chunks_initial" : [c.get("chunk_id", "?") for c in chunks_initial],
            "chunks_final"   : [c.get("chunk_id", "?") for c in chunks_final],
            "sources_used"   : list({
                c.get("metadata", {}).get("source_title", "?")
                for c in chunks_final
            }),
            "faithfulness"   : faithfulness,
            "response_words" : len(response_text.split()),
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"[LOG] Failed to write retrieval log: {e}")
