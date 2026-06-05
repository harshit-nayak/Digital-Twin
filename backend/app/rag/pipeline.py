"""
backend/app/rag/pipeline.py

RAG pipeline orchestrator.
Wires together: query intelligence → hybrid retrieval → reranking.
This is the single function the LangGraph nodes call.
"""

import os
from dotenv import load_dotenv

from app.rag.query_intelligence import process_query
from app.rag.retriever          import hybrid_retrieve, multi_query_retrieve
from app.rag.embedder           import embed_single
from app.rag.reranker           import rerank

load_dotenv()

HYDE_ENABLED         = os.getenv("HYDE_ENABLED", "true").lower() == "true"
MULTI_QUERY_ENABLED  = os.getenv("MULTI_QUERY_ENABLED", "true").lower() == "true"
TOP_K_INITIAL        = int(os.getenv("RAG_TOP_K_INITIAL", "10"))
TOP_K_FINAL          = int(os.getenv("RAG_TOP_K_AFTER_RERANK", "5"))


async def run_rag_pipeline(
    query         : str,
    scientist_id  : str,
    timeline_year : int,
    top_k         : int = None,
) -> dict:
    """
    Full RAG pipeline for one query.

    Flow:
        query → query intelligence → hybrid retrieval → reranking → final chunks

    Args:
        query:         Raw user query
        scientist_id:  e.g. "einstein"
        timeline_year: Selected milestone year
        top_k:         Final chunks to return (overrides env setting)

    Returns:
        {
            "final_chunks":    list of top ranked chunks,
            "query_data":      query intelligence output,
            "chunk_count":     int,
        }
    """
    final_k = top_k or TOP_K_FINAL

    print(f"\n[RAG] -- Starting pipeline --------------------------")
    print(f"[RAG] Query:    {query}")
    print(f"[RAG] Scientist: {scientist_id} | Year: {timeline_year}")

    # ── Step 1: Query Intelligence ─────────────────────────────────────────
    print(f"[RAG] Step 1: Query Intelligence")
    query_data = await process_query(
        query         = query,
        scientist_id  = scientist_id,
        timeline_year = timeline_year,
        use_hyde      = HYDE_ENABLED,
        use_decompose = MULTI_QUERY_ENABLED,
    )

    # ── Step 2: Retrieval ──────────────────────────────────────────────────
    print(f"[RAG] Step 2: Hybrid Retrieval")

    # Use HyDE text for the primary dense retrieval embedding
    primary_query = query_data["hyde_text"] if HYDE_ENABLED else query_data["rewritten_query"]

    if MULTI_QUERY_ENABLED and len(query_data["sub_queries"]) > 1:
        # Multi-query: retrieve for each sub-query, deduplicate
        retrieved_chunks = multi_query_retrieve(
            queries       = query_data["sub_queries"],
            scientist_id  = scientist_id,
            timeline_year = timeline_year,
            top_k         = TOP_K_INITIAL,
        )
    else:
        # Single query retrieval
        retrieved_chunks = hybrid_retrieve(
            query         = primary_query,
            scientist_id  = scientist_id,
            timeline_year = timeline_year,
            top_k         = TOP_K_INITIAL,
        )

    print(f"[RAG] Retrieved {len(retrieved_chunks)} chunks before reranking")

    if not retrieved_chunks:
        print(f"[RAG] WARNING: No chunks retrieved. Check corpus and ChromaDB.")
        return {
            "final_chunks": [],
            "query_data":   query_data,
            "chunk_count":  0,
        }

    # ── Step 3: Reranking ──────────────────────────────────────────────────
    print(f"[RAG] Step 3: Reranking")
    final_chunks = rerank(
        query  = query,       # use original query for reranking
        chunks = retrieved_chunks,
        top_k  = final_k,
    )

    print(f"[RAG] Final chunks: {len(final_chunks)}")
    print(f"[RAG] Sources: {[c['metadata'].get('source_title','?')[:30] for c in final_chunks]}")
    print(f"[RAG] -- Pipeline complete --------------------------\n")

    return {
        "final_chunks": final_chunks,
        "query_data":   query_data,
        "chunk_count":  len(final_chunks),
    }


def format_context_for_prompt(chunks: list[dict]) -> str:
    """
    Format final chunks into a clean context string for prompt injection.
    Each chunk is labeled with its source.
    """
    if not chunks:
        return "No relevant passages found in the corpus."

    parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk["metadata"].get("source_title", "Unknown source")
        year   = chunk["metadata"].get("year", "?")
        text   = chunk["text"].strip()
        parts.append(f"[{i}] From '{source}' ({year}):\n{text}")

    return "\n\n---\n\n".join(parts)
