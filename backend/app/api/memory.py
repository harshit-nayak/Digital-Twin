"""
backend/app/api/memory.py

Memory management endpoints:
    GET  /memory/{user_id}/{scientist_id}            — list all memories + profile
    DELETE /memory/{user_id}/{scientist_id}/{mem_id} — delete one memory
    DELETE /memory/{user_id}/{scientist_id}          — clear all memories
    GET  /memory/{user_id}/{scientist_id}/sessions   — list past sessions
"""

from fastapi import APIRouter, HTTPException

from app.memory.ltm import (
    get_all_memories, delete_memory, clear_all_memories,
    get_recent_sessions, get_profile,
)

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/{user_id}/{scientist_id}")
async def get_memories(user_id: str, scientist_id: str):
    """
    Return all memories for a user with a specific scientist.
    Also returns the user profile.
    Used by the Memory sidebar in the frontend.
    """
    memories = get_all_memories(user_id, scientist_id)
    profile  = get_profile(user_id)

    # Group memories by type for sidebar tabs
    grouped = {}
    for mem in memories:
        mtype = mem.get("memory_type", "unknown")
        grouped.setdefault(mtype, []).append({
            "id"          : mem["id"],
            "content"     : mem["content"],
            "importance"  : round(mem.get("importance", 0.5), 2),
            "access_count": mem.get("access_count", 0),
            "created_at"  : mem.get("created_at", ""),
        })

    return {
        "user_id"     : user_id,
        "scientist_id": scientist_id,
        "memories"    : grouped,
        "total"       : len(memories),
        "profile"     : profile,
    }


@router.delete("/{user_id}/{scientist_id}/{memory_id}")
async def remove_memory(user_id: str, scientist_id: str, memory_id: str):
    """
    Delete a specific memory entry (user-initiated from the sidebar).
    """
    delete_memory(memory_id, user_id)
    return {"deleted": memory_id, "status": "ok"}


@router.delete("/{user_id}/{scientist_id}")
async def reset_memories(user_id: str, scientist_id: str):
    """
    Clear all memories for this user + scientist combination.
    """
    clear_all_memories(user_id, scientist_id)
    return {
        "status"      : "cleared",
        "user_id"     : user_id,
        "scientist_id": scientist_id,
    }


@router.get("/{user_id}/{scientist_id}/sessions")
async def list_sessions(user_id: str, scientist_id: str, limit: int = 5):
    """
    Return recent session summaries.
    """
    sessions = get_recent_sessions(user_id, scientist_id, limit=limit)
    return {"sessions": sessions}
