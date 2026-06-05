"""
backend/app/api/admin.py

Admin endpoints (development/debugging only):
    GET  /admin/keys      — show LLM key pool status
    POST /admin/provider  — switch active provider
    GET  /admin/cache     — show retrieval cache stats
    GET  /admin/log       — show last N retrieval log entries
    POST /admin/db/init   — re-initialize the database
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.llm.gateway import llm_gateway
from app.rag.cache   import cache_size, clear_expired

router = APIRouter(prefix="/admin", tags=["admin"])

LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "retrieval_log.jsonl"


@router.get("/keys")
async def get_key_status():
    """Show current API key pool status for all providers."""
    return {
        "providers": llm_gateway.key_status(),
    }


@router.post("/provider/{provider_name}")
async def set_provider(provider_name: str):
    """Set the preferred provider order (put `provider_name` first)."""
    available = list(llm_gateway.key_managers.keys())
    if provider_name not in available:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider: {provider_name}. Available: {available}"
        )
    # Move requested provider to front
    order = [provider_name] + [p for p in llm_gateway.provider_order if p != provider_name]
    llm_gateway.provider_order = order
    return {"provider_order": order, "status": "updated"}


@router.get("/cache")
async def get_cache_stats():
    """Show retrieval cache size."""
    clear_expired()
    return {"cache_entries": cache_size()}


@router.get("/log")
async def get_retrieval_log(n: int = 20):
    """Return the last N retrieval log entries."""
    if not LOG_PATH.exists():
        return {"entries": [], "message": "Log file not found yet"}

    lines = LOG_PATH.read_text(encoding="utf-8").strip().split("\n")
    lines = [l for l in lines if l.strip()]
    last_n = lines[-n:]

    entries = []
    for line in reversed(last_n):
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return {"entries": entries, "total_in_log": len(lines)}


@router.post("/db/init")
async def reinit_db():
    """Re-initialize the SQLite database (safe — creates tables only if missing)."""
    from app.memory.database import init_db
    init_db()
    return {"status": "db initialized"}


@router.get("/health")
async def health_check():
    """Basic health check for monitoring."""
    return {
        "status"       : "ok",
        "cache_entries": cache_size(),
        "providers"    : list(llm_gateway.key_managers.keys()),
    }
