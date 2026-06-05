"""
backend/app/graph/orchestrator.py

Main LangGraph orchestration graph.
Wires all nodes together in the canonical execution order from the architecture.

Execution flow:
    domain_check
        ├─ out of domain → domain_refusal → END
        └─ in domain →
            query_intelligence
            → parallel_retrieval
            → rerank
            → context_builder
            → prompt_builder
            → llm
            → post_generation
            → memory_update → END
"""

from langgraph.graph import StateGraph, END

from app.graph.state import AgentState
from app.graph.nodes import (
    domain_check_node,
    query_intelligence_node,
    parallel_retrieval_node,
    rerank_node,
    context_builder_node,
    prompt_builder_node,
    llm_node,
    post_generation_node,
    memory_update_node,
    domain_refusal_node,
)


def _route_domain_check(state: AgentState) -> str:
    """Route after domain check: refusal or continue pipeline."""
    if state.get("is_in_domain", True):
        return "query_intelligence"
    return "domain_refusal"


def build_graph() -> StateGraph:
    """Build and compile the main LangGraph graph."""
    graph = StateGraph(AgentState)

    # ── Add all nodes ─────────────────────────────────────────────────────────
    graph.add_node("domain_check",       domain_check_node)
    graph.add_node("domain_refusal",     domain_refusal_node)
    graph.add_node("query_intelligence", query_intelligence_node)
    graph.add_node("parallel_retrieval", parallel_retrieval_node)
    graph.add_node("rerank",             rerank_node)
    graph.add_node("context_builder",    context_builder_node)
    graph.add_node("prompt_builder",     prompt_builder_node)
    graph.add_node("llm",                llm_node)
    graph.add_node("post_generation",    post_generation_node)
    graph.add_node("memory_update",      memory_update_node)

    # ── Entry point ───────────────────────────────────────────────────────────
    graph.set_entry_point("domain_check")

    # ── Edges ────────────────────────────────────────────────────────────────
    graph.add_conditional_edges(
        "domain_check",
        _route_domain_check,
        {
            "query_intelligence": "query_intelligence",
            "domain_refusal":     "domain_refusal",
        }
    )

    # Refusal exits immediately (no RAG, no memory write)
    graph.add_edge("domain_refusal",     END)

    # Main pipeline — linear execution
    graph.add_edge("query_intelligence", "parallel_retrieval")
    graph.add_edge("parallel_retrieval", "rerank")
    graph.add_edge("rerank",             "context_builder")
    graph.add_edge("context_builder",    "prompt_builder")
    graph.add_edge("prompt_builder",     "llm")
    graph.add_edge("llm",                "post_generation")
    graph.add_edge("post_generation",    "memory_update")
    graph.add_edge("memory_update",      END)

    return graph.compile()


# ── Singleton compiled graph ──────────────────────────────────────────────────

_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ── Public invoke function ────────────────────────────────────────────────────

async def run_pipeline(
    user_id       : str,
    scientist_id  : str,
    timeline_year : int,
    query         : str,
    mode          : str    = "chat",
    session_id    : str    = "",
    working_memory: dict   = None,
) -> dict:
    """
    Run the full pipeline for one query.

    Returns the final state dict with:
        response_text, emotion_tag, sources, faithfulness_score,
        final_chunks, working_memory, ltm_entries
    """
    import uuid

    if not session_id:
        session_id = str(uuid.uuid4())

    # Initialize DB / session if needed
    from app.memory.ltm import start_session, ensure_user
    ensure_user(user_id)

    initial_state: AgentState = {
        # Input
        "user_id"         : user_id,
        "scientist_id"    : scientist_id,
        "timeline_year"   : timeline_year,
        "query"           : query,
        "mode"            : mode,
        "session_id"      : session_id,

        # Query intelligence (populated by node)
        "rewritten_query" : "",
        "hyde_text"       : "",
        "sub_queries"     : [],
        "query_complexity": 0.5,

        # Retrieval (populated by node)
        "retrieved_chunks": [],
        "ltm_entries"     : [],
        "stm_window"      : [],
        "ltm_context_str" : "",

        # Reranking
        "final_chunks"    : [],

        # Context
        "system_prompt"   : "",
        "max_tokens"      : 450,
        "working_memory"  : working_memory or {},

        # LLM output
        "raw_response"    : "",

        # Post-generation
        "emotion_tag"     : "NEUTRAL",
        "response_text"   : "",
        "sources"         : [],
        "faithfulness_score": 1.0,

        # Control
        "is_in_domain"    : True,
        "error_message"   : None,
    }

    graph  = get_graph()
    result = await graph.ainvoke(initial_state)

    return {
        "response_text"    : result.get("response_text", ""),
        "emotion_tag"      : result.get("emotion_tag", "NEUTRAL"),
        "sources"          : result.get("sources", []),
        "faithfulness_score": result.get("faithfulness_score", 1.0),
        "final_chunks"     : result.get("final_chunks", []),
        "working_memory"   : result.get("working_memory", {}),
        "ltm_entries"      : result.get("ltm_entries", []),
        "rewritten_query"  : result.get("rewritten_query", ""),
        "session_id"       : session_id,
    }
