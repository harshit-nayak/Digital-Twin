"""
backend/app/graph/nodes.py

All LangGraph graph nodes.
Each node receives the full AgentState and returns a partial dict update.

Execution order (set by orchestrator.py):
    domain_check → query_intelligence → parallel_retrieval
    → rerank → context_builder → prompt_builder → llm → post_generation → memory_update
"""

import json
import asyncio
from datetime import datetime
from pathlib import Path

from app.graph.state     import AgentState
from app.rag.pipeline    import run_rag_pipeline
from app.memory.ltm      import (
    search_memories, get_memories_for_prompt,
    extract_memories_from_exchange, update_profile,
)
from app.memory.stm      import (
    add_to_stm as stm_add_exchange,
    format_stm_for_prompt,
    update_working_memory,
    WorkingMemory,
)
from app.memory.compressor   import compress_session
from app.context.builder     import build_prompt, parse_response, check_faithfulness
from app.llm.gateway         import llm_gateway
from app.personas.loader     import get_scientist_config

# ── Domain keyword sets (per scientist, loaded from config) ──────────────────

DOMAIN_KEYWORDS = {
    "einstein": [
        "relativity", "space", "time", "light", "gravity", "energy", "mass",
        "quantum", "photon", "photoelectric", "spacetime", "wave", "field",
        "simultaneity", "equivalence", "curved", "general", "special",
        "brownian", "atom", "molecule", "thermodynamics", "entropy",
        "unified", "tensor", "geodesic", "lorentz", "bohr", "physics"
    ],
    "newton": [
        "force", "motion", "gravity", "mass", "acceleration", "optics", "light",
        "calculus", "prism", "apple", "orbit", "planetary", "laws", "mechanics",
        "principia", "fluxions", "inertia", "momentum", "centripetal", "physics"
    ],
    "feynman": [
        "quantum", "electrodynamics", "QED", "photon", "electron", "path integral",
        "diagrams", "particle", "wave", "physics", "lecture", "nanotechnology",
        "computing", "challenger", "space shuttle", "bongo", "curiosity"
    ],
    "tesla": [
        "electricity", "current", "AC", "DC", "alternating", "coil", "motor",
        "generator", "electromagnetic", "wireless", "radio", "resonance", "voltage"
    ],
    "curie": [
        "radioactive", "radiation", "polonium", "radium", "element", "isotope",
        "chemistry", "physics", "x-ray", "nuclear", "atom", "decay", "Nobel"
    ],
}

OUT_OF_DOMAIN_SIGNALS = [
    "recipe", "cooking", "sport", "football", "bitcoin", "crypto",
    "stock market", "politics", "election", "celebrity", "movie",
    "fashion", "relationship advice", "medical advice", "legal advice",
    "code", "programming", "software", "javascript", "python"
]

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ── Node 1: Domain Check ──────────────────────────────────────────────────────

def domain_check_node(state: AgentState) -> dict:
    """
    Check if the query falls within the scientist's domain.
    Simple keyword check — fast, no LLM call, zero RAG tokens spent on refusal.
    """
    query       = state["query"].lower()
    scientist   = state["scientist_id"]

    # Check for hard out-of-domain signals
    if any(signal in query for signal in OUT_OF_DOMAIN_SIGNALS):
        print(f"[DOMAIN_CHECK] Out of domain detected: '{state['query'][:50]}'")
        return {"is_in_domain": False}

    # Check for at least one physics/science keyword
    keywords = DOMAIN_KEYWORDS.get(scientist, [])
    if any(kw in query for kw in keywords):
        return {"is_in_domain": True}

    # Borderline — assume in-domain for short or general questions
    # ("what is energy?" is fine — "who won the World Cup?" is not)
    word_count = len(query.split())
    if word_count <= 8:
        return {"is_in_domain": True}   # short question, give benefit of doubt

    # Medium-length query with no physics keywords — likely out of domain
    if word_count > 8 and not any(kw in query for kw in keywords):
        return {"is_in_domain": False}

    return {"is_in_domain": True}


# ── Node 2: Query Intelligence ────────────────────────────────────────────────

async def query_intelligence_node(state: AgentState) -> dict:
    """
    Rewrite query, generate HyDE, decompose into sub-queries.
    All LLM calls are cheap (max_tokens=40-150).
    """
    from app.rag.query_intelligence import process_query

    result = await process_query(
        query         = state["query"],
        scientist_id  = state["scientist_id"],
        timeline_year = state["timeline_year"],
        use_hyde      = True,
        use_decompose = True,
    )

    # Estimate complexity from sub-query count + query length
    n_subqueries = len(result["sub_queries"])
    word_count   = len(state["query"].split())
    complexity   = min(1.0, (n_subqueries - 1) * 0.3 + word_count / 50)

    return {
        "rewritten_query" : result["rewritten_query"],
        "hyde_text"       : result["hyde_text"],
        "sub_queries"     : result["sub_queries"],
        "query_complexity": round(complexity, 2),
    }


# ── Node 3: Parallel Retrieval ────────────────────────────────────────────────

async def parallel_retrieval_node(state: AgentState) -> dict:
    """
    Run RAG pipeline, LTM memory search, and STM fetch.
    These are logically independent — future version can use asyncio.gather.
    """
    # 3a: RAG retrieval (query intelligence already ran — use rewritten_query)
    rag_result = await run_rag_pipeline(
        query         = state["rewritten_query"] or state["query"],
        scientist_id  = state["scientist_id"],
        timeline_year = state["timeline_year"],
    )

    # 3b: LTM memory retrieval
    ltm_context_str = get_memories_for_prompt(
        user_id      = state["user_id"],
        scientist_id = state["scientist_id"],
        query        = state["query"],
    )

    # Load raw LTM entries for sidebar display
    ltm_entries = search_memories(
        user_id      = state["user_id"],
        scientist_id = state["scientist_id"],
        query        = state["query"],
        top_k        = 10,
    )

    # 3c: STM window — already in state from previous turn
    stm_window = state.get("stm_window", [])

    return {
        "retrieved_chunks" : rag_result["final_chunks"],
        "ltm_entries"      : ltm_entries,
        "ltm_context_str"  : ltm_context_str,
        "stm_window"       : stm_window,
    }


# ── Node 4: Rerank ────────────────────────────────────────────────────────────

def rerank_node(state: AgentState) -> dict:
    """
    Re-rank retrieved chunks with cross-encoder + MMR.
    (RAG pipeline already reranked, but this is the hook for enrichment too.)
    """
    # Chunks are already reranked from run_rag_pipeline
    # This node is a pass-through unless enrichment is added
    final_chunks = state.get("retrieved_chunks", [])

    print(f"[RERANK_NODE] Passing {len(final_chunks)} chunks to context builder")
    return {"final_chunks": final_chunks}


# ── Node 5: Context Builder ───────────────────────────────────────────────────

def context_builder_node(state: AgentState) -> dict:
    """
    Assemble the full system prompt from all context sources.
    This is the central layer — all inputs converge here.
    """
    wm_data = state.get("working_memory", {})
    wm      = WorkingMemory.from_dict(wm_data) if wm_data else WorkingMemory()
    wm_data = wm_data or {}

    prompt_package = build_prompt(
        scientist_id   = state["scientist_id"],
        timeline_year  = state["timeline_year"],
        mode           = state["mode"],
        rag_chunks     = state.get("final_chunks", []),
        ltm_context    = state.get("ltm_context_str", ""),
        stm_window     = state.get("stm_window", []),
        working_memory = wm,
    )

    return {
        "system_prompt": prompt_package["system_prompt"],
        "max_tokens"  : prompt_package["max_tokens"],
    }


# ── Node 6: Prompt Builder ────────────────────────────────────────────────────

def prompt_builder_node(state: AgentState) -> dict:
    """
    Build the final messages list for the LLM call.
    The user query goes into messages (not system prompt).
    """
    # For now, a single user turn
    # STM history is already in system prompt via context builder
    messages = [{"role": "user", "content": state["query"]}]

    return {"_messages": messages}   # internal key, consumed by llm_node


# ── Node 7: LLM ──────────────────────────────────────────────────────────────

async def llm_node(state: AgentState) -> dict:
    """
    Send assembled prompt to LLM gateway. Get response.
    """
    messages = state.get("_messages", [{"role": "user", "content": state["query"]}])

    raw_response = await llm_gateway.complete(
        messages      = messages,
        system_prompt = state["system_prompt"],
        max_tokens    = state.get("max_tokens", 450),
        temperature   = 0.7,
    )

    print(f"[LLM_NODE] Response length: {len(raw_response.split())} words")
    return {"raw_response": raw_response}


# ── Node 8: Post-Generation ───────────────────────────────────────────────────

async def post_generation_node(state: AgentState) -> dict:
    """
    1. Parse emotion tag from response
    2. Extract source attribution from final_chunks
    3. Faithfulness check (optional, based on env setting)
    """
    parsed = parse_response(state["raw_response"])

    # Build source list for frontend display
    sources = []
    for chunk in state.get("final_chunks", []):
        meta = chunk.get("metadata", {})
        sources.append({
            "title": meta.get("source_title", "Unknown"),
            "year" : meta.get("year", "?"),
            "type" : meta.get("source_type", "?"),
        })
    # Deduplicate
    seen   = set()
    unique_sources = []
    for s in sources:
        key = (s["title"], s["year"])
        if key not in seen:
            seen.add(key)
            unique_sources.append(s)

    # Faithfulness check
    import os
    faithfulness = 1.0
    if os.getenv("FAITHFULNESS_CHECK", "true").lower() == "true":
        faithfulness = await check_faithfulness(
            response = parsed["text"],
            chunks   = state.get("final_chunks", []),
        )

    return {
        "emotion_tag"      : parsed["emotion"],
        "response_text"    : parsed["text"],
        "sources"          : unique_sources,
        "faithfulness_score": faithfulness,
    }


# ── Node 9: Memory Update ─────────────────────────────────────────────────────

def memory_update_node(state: AgentState) -> dict:
    """
    After response delivered:
    1. Add exchange to STM window
    2. Extract + store LTM memories
    3. Update working memory
    4. Log retrieval data
    5. Update user profile
    """
    user_id      = state["user_id"]
    scientist_id = state["scientist_id"]

    # 1. Add to STM window (in-state list)
    current_stm = state.get("stm_window", [])
    updated_stm = stm_add_exchange(
        stm_window  = current_stm,
        user_message= state["query"],
        ai_response = state["response_text"],
    )

    # 2. Extract + write LTM memories
    extract_memories_from_exchange(
        user_message      = state["query"],
        assistant_message = state["response_text"],
        user_id           = user_id,
        scientist_id      = scientist_id,
    )

    # 3. Update working memory
    wm      = WorkingMemory.from_dict(state.get("working_memory", {}))
    wm      = update_working_memory(wm, state["query"], state["response_text"])
    wm_dict = wm.to_dict()

    # 4. Log retrieval
    _log_retrieval(state)

    # 5. Update user profile
    update_profile(
        user_id      = user_id,
        scientist_id = scientist_id,
        year         = state["timeline_year"],
    )

    return {
        "working_memory": wm_dict,
        "stm_window"    : updated_stm,
    }


# ── Domain refusal node ───────────────────────────────────────────────────────

def domain_refusal_node(state: AgentState) -> dict:
    """
    Return an in-character refusal for out-of-domain queries.
    Costs 0 RAG tokens.
    """
    refusals = {
        "einstein": (
            "[AMUSED] I am afraid that particular subject falls quite outside "
            "my expertise. My mind dwells in the realm of physics — space, time, "
            "light, and the elegant equations that govern them. Perhaps you have "
            "a question about the nature of gravity or the speed of light?"
        ),
        "newton": (
            "[NEUTRAL] That matter lies beyond the bounds of Natural Philosophy. "
            "I concern myself with the mathematical principles governing motion, "
            "optics, and celestial mechanics. Have you a question on such matters?"
        ),
        "feynman": (
            "[AMUSED] Ha! That's not really my department. I'm a physics guy — "
            "particles, waves, quantum weirdness. Ask me something about that "
            "and I'll get properly excited."
        ),
    }

    scientist   = state["scientist_id"]
    refusal_msg = refusals.get(
        scientist,
        "[NEUTRAL] That question falls outside my domain of knowledge. "
        "Please ask me about physics and science."
    )

    parsed = parse_response(refusal_msg)

    return {
        "emotion_tag"      : parsed["emotion"],
        "response_text"    : parsed["text"],
        "sources"          : [],
        "faithfulness_score": 1.0,
        "raw_response"     : refusal_msg,
        "final_chunks"     : [],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _log_retrieval(state: AgentState):
    """Append retrieval data to JSONL log file."""
    try:
        log_path = LOG_DIR / "retrieval_log.jsonl"
        entry = {
            "timestamp"      : datetime.now().isoformat(),
            "user_id"        : state.get("user_id", ""),
            "scientist_id"   : state.get("scientist_id", ""),
            "timeline_year"  : state.get("timeline_year", 0),
            "query"          : state.get("query", ""),
            "rewritten_query": state.get("rewritten_query", ""),
            "sub_queries"    : state.get("sub_queries", []),
            "chunks_initial" : len(state.get("retrieved_chunks", [])),
            "chunks_final"   : len(state.get("final_chunks", [])),
            "sources_used"   : [s["title"] for s in state.get("sources", [])],
            "faithfulness"   : state.get("faithfulness_score", 1.0),
            "response_words" : len(state.get("response_text", "").split()),
            "mode"           : state.get("mode", "chat"),
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"[LOG] Retrieval logging failed: {e}")
