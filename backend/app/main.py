"""
backend/app/main.py

FastAPI application entry point.

Run with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Or from /backend directory:
    python -m uvicorn app.main:app --reload
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.api.chat   import router as chat_router
from app.api.memory import router as memory_router
from app.api.admin  import router as admin_router

load_dotenv()


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: initialize database, pre-load cross-encoder.
    Shutdown: cleanup if needed.
    """
    print("=" * 60)
    print("  Digital Twin Physics Academy — Backend Starting")
    print("=" * 60)

    # Initialize SQLite schema (idempotent — safe to call every time)
    from app.memory.database import init_db
    init_db()
    print("[STARTUP] Database initialized")

    # Pre-warm the cross-encoder model (slow to load, ~2s)
    try:
        from app.rag.reranker import get_cross_encoder
        get_cross_encoder()
        print("[STARTUP] Cross-encoder model loaded")
    except Exception as e:
        print(f"[STARTUP] Cross-encoder pre-load failed (will load on first query): {e}")

    # Pre-load Einstein config (most common scientist)
    try:
        from app.personas.loader import get_scientist_config
        get_scientist_config("einstein")
        print("[STARTUP] Einstein config loaded")
    except Exception as e:
        print(f"[STARTUP] Config pre-load failed: {e}")

    print("[STARTUP] Ready to serve requests")
    print("=" * 60)

    yield

    # Shutdown
    print("[SHUTDOWN] Digital Twin backend shutting down")


# ── App definition ────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "Digital Twin Physics Academy",
    description = "Talk to Einstein, Newton, Feynman, Tesla, and Curie.",
    version     = "1.0.0",
    lifespan    = lifespan,
)

# ── CORS (allow frontend dev server) ──────────────────────────────────────────

ALLOWED_ORIGINS = [
    "http://localhost:3000",    # React dev server
    "http://localhost:5173",    # Vite dev server
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ALLOWED_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Register routers ──────────────────────────────────────────────────────────

app.include_router(chat_router,   prefix="",         tags=["chat"])
app.include_router(memory_router, prefix="",          tags=["memory"])
app.include_router(admin_router,  prefix="",          tags=["admin"])


# ── Root health check ─────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "service" : "Digital Twin Physics Academy",
        "version" : "1.0.0",
        "status"  : "running",
        "endpoints": [
            "POST /chat",
            "WS   /chat/stream",
            "GET  /scientists",
            "GET  /scientists/{id}/timeline",
            "GET  /memory/{user_id}/{scientist_id}",
            "GET  /admin/keys",
            "GET  /admin/log",
            "GET  /admin/health",
        ]
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
