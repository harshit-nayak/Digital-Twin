"""
backend/app/api/chat.py

Chat API endpoints:
    POST /chat          — full pipeline, returns JSON response
    WebSocket /chat/stream  — streaming response (typewriter effect)
    GET /scientists     — list all available scientists (lobby)
    GET /scientists/{id}/timeline — get milestone list
"""

import uuid
import json
import asyncio
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from app.graph.orchestrator import run_pipeline
from app.personas.loader    import get_all_scientists, get_timeline_milestones
from app.memory.ltm         import start_session

router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    user_id       : str
    scientist_id  : str
    timeline_year : int
    query         : str
    mode          : str = "chat"
    session_id    : Optional[str] = None
    working_memory: Optional[dict] = None


class ChatResponse(BaseModel):
    response_text    : str
    emotion_tag      : str
    sources          : list
    faithfulness_score: float
    session_id       : str
    rewritten_query  : str
    ltm_entries      : list


class StreamMessage(BaseModel):
    type   : str    # "chunk" | "done" | "meta" | "error"
    content: str


# ── POST /chat ────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Full pipeline execution. Returns complete response JSON.
    Use this for quiz mode, debate, and non-streaming use cases.
    """
    session_id = req.session_id or str(uuid.uuid4())

    try:
        result = await run_pipeline(
            user_id       = req.user_id,
            scientist_id  = req.scientist_id,
            timeline_year = req.timeline_year,
            query         = req.query,
            mode          = req.mode,
            session_id    = session_id,
            working_memory = req.working_memory or {},
        )

        return ChatResponse(
            response_text    = result["response_text"],
            emotion_tag      = result["emotion_tag"],
            sources          = result["sources"],
            faithfulness_score= result["faithfulness_score"],
            session_id       = session_id,
            rewritten_query  = result.get("rewritten_query", ""),
            ltm_entries      = result.get("ltm_entries", []),
        )

    except Exception as e:
        print(f"[API /chat] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── WebSocket /chat/stream ────────────────────────────────────────────────────

@router.websocket("/chat/stream")
async def chat_stream(websocket: WebSocket):
    """
    Streaming chat via WebSocket.

    Client sends JSON: { user_id, scientist_id, timeline_year, query, mode, session_id }
    Server streams back chunks:
        { "type": "chunk",   "content": "..." }   — text tokens as they arrive
        { "type": "meta",    "content": "{...}" }  — JSON: emotion, sources, faithfulness
        { "type": "done",    "content": "" }        — signals stream end
        { "type": "error",   "content": "..." }     — error message
    """
    await websocket.accept()

    try:
        # Receive the request payload
        raw = await websocket.receive_text()
        data = json.loads(raw)

        user_id       = data.get("user_id", "anonymous")
        scientist_id  = data.get("scientist_id", "einstein")
        timeline_year = int(data.get("timeline_year", 1927))
        query         = data.get("query", "")
        mode          = data.get("mode", "chat")
        session_id    = data.get("session_id") or str(uuid.uuid4())
        working_memory = data.get("working_memory", {})

        if not query.strip():
            await websocket.send_json({"type": "error", "content": "Empty query"})
            return

        # Run the pipeline (non-streaming) then stream the result manually
        # True streaming from Gemini can be added later via llm_gateway.complete_stream()
        result = await run_pipeline(
            user_id        = user_id,
            scientist_id   = scientist_id,
            timeline_year  = timeline_year,
            query          = query,
            mode           = mode,
            session_id     = session_id,
            working_memory = working_memory,
        )

        response_text = result["response_text"]

        # Stream the response word-by-word for typewriter effect
        words = response_text.split(" ")
        chunk_size = 3  # send 3 words at a time
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i : i + chunk_size])
            if i + chunk_size < len(words):
                chunk += " "
            await websocket.send_json({"type": "chunk", "content": chunk})
            await asyncio.sleep(0.03)  # ~30ms between chunks

        # Send metadata after text stream
        meta = {
            "emotion_tag"      : result["emotion_tag"],
            "sources"          : result["sources"],
            "faithfulness_score": result["faithfulness_score"],
            "session_id"       : session_id,
            "ltm_entries"      : result.get("ltm_entries", []),
        }
        await websocket.send_json({"type": "meta", "content": json.dumps(meta)})
        await websocket.send_json({"type": "done", "content": ""})

    except WebSocketDisconnect:
        print("[WS] Client disconnected")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[WS] Error: {e}")
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass


# ── GET /scientists ───────────────────────────────────────────────────────────

@router.get("/scientists")
async def list_scientists():
    """
    Return all configured scientists for the lobby page.
    """
    return {"scientists": get_all_scientists()}


# ── GET /scientists/{id}/timeline ─────────────────────────────────────────────

@router.get("/scientists/{scientist_id}/timeline")
async def get_timeline(scientist_id: str):
    """
    Return timeline milestones for a specific scientist.
    Used by the frontend timeline slider.
    """
    milestones = get_timeline_milestones(scientist_id)
    if not milestones:
        raise HTTPException(status_code=404, detail=f"No config for scientist: {scientist_id}")
    return {"scientist_id": scientist_id, "milestones": milestones}
