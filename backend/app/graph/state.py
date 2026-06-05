"""
backend/app/graph/state.py

LangGraph AgentState — the single state object passed between all nodes.
Every field is typed. Nodes read from state and return partial updates.
"""

from typing import TypedDict, Optional


class AgentState(TypedDict):
    # ── Input fields (set by caller before graph invocation) ─────────────────
    user_id       : str
    scientist_id  : str
    timeline_year : int
    query         : str
    mode          : str          # "chat" | "quiz" | "gedanken" | "modern_react" | "debate"
    session_id    : str

    # ── Query Intelligence (set by query_intelligence_node) ──────────────────
    rewritten_query  : str
    hyde_text        : str
    sub_queries      : list       # list[str]
    query_complexity : float      # 0.0–1.0

    # ── Retrieval (set by parallel_retrieval_node) ────────────────────────────
    retrieved_chunks : list       # list[dict]  — from RAG pipeline
    ltm_entries      : list       # list[dict]  — from LTM search
    stm_window       : list       # list[dict]  — recent exchanges
    ltm_context_str  : str        # formatted for prompt injection

    # ── Reranking (set by rerank_node) ────────────────────────────────────────
    final_chunks     : list       # list[dict]  — after cross-encoder + MMR

    # ── Context (set by context_builder_node) ─────────────────────────────────
    system_prompt    : str
    max_tokens       : int
    working_memory   : dict       # WorkingMemory.to_dict()

    # ── LLM output (set by llm_node) ──────────────────────────────────────────
    raw_response     : str

    # ── Post-generation (set by post_generation_node) ─────────────────────────
    emotion_tag      : str        # EXCITED | CONTEMPLATIVE | etc.
    response_text    : str        # cleaned response (no emotion tag)
    sources          : list       # list[dict] — source attributions
    faithfulness_score: float

    # ── Control flags ──────────────────────────────────────────────────────────
    is_in_domain     : bool
    error_message    : Optional[str]
