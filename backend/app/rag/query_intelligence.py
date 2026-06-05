"""
backend/app/rag/query_intelligence.py

Query Intelligence Layer — runs before retrieval.
Three components:
  1. Query Rewriter     — rewrites vague user query for semantic retrieval
  2. HyDE Generator     — generates hypothetical answer for better embedding
  3. Multi-Query Decomposer — splits complex questions into sub-queries
"""

import os
import json
from dotenv import load_dotenv
import google.genai as genai

load_dotenv()

async def quick_complete(prompt: str, max_tokens: int = 100) -> str:
    """Lightweight LLM call for query intelligence tasks via LLM Gateway."""
    from app.llm.gateway import llm_gateway
    try:
        return await llm_gateway.complete_fast(prompt, max_tokens=max_tokens)
    except Exception as e:
        print(f"[QUERY_INTEL] LLM call failed: {e}")
        return ""

# ── 1. Query Rewriter ─────────────────────────────────────────────────────────

async def rewrite_query(
    query         : str,
    scientist_id  : str,
    timeline_year : int,
) -> str:
    """
    Rewrites a conversational user query into a precise search query
    optimised for semantic retrieval over scientific texts.

    Example:
        "how does time work?" →
        "time dilation special relativity clock speed velocity Einstein 1905"
    """
    prompt = f"""You are a retrieval assistant for {scientist_id}'s scientific corpus (year {timeline_year}).

Rewrite this conversational query into a precise search query optimised for semantic retrieval over scientific texts.
- Use technical terms the scientist would use
- Include relevant concept names
- Keep it under 20 words
- Return ONLY the rewritten query, nothing else

Original query: {query}
Rewritten query:"""

    rewritten = await quick_complete(prompt, max_tokens=50)

    if not rewritten:
        print(f"[QUERY_INTEL] Rewrite failed, using original query")
        return query

    print(f"[QUERY_INTEL] Rewrite: '{query}' -> '{rewritten}'")
    return rewritten


# ── 2. HyDE — Hypothetical Document Embeddings ───────────────────────────────

async def generate_hyde(
    query         : str,
    scientist_id  : str,
    timeline_year : int,
) -> str:
    """
    Generates a hypothetical passage that WOULD appear in the corpus
    and directly answer the query. This hypothetical passage is then
    embedded instead of the raw question.

    Why: The embedding space is trained on document-document similarity.
    A hypothetical answer looks like a document. A question does not.
    This dramatically improves semantic match quality.

    Example:
        Query: "why can't we go faster than light?"
        HyDE:  "The constancy of the speed of light in all inertial frames,
                as required by Maxwell's equations, implies that no material
                object can be accelerated to the speed of light, since the
                energy required would become infinite..."
    """
    prompt = f"""Write a short passage (3-4 sentences) in the style of {scientist_id}'s scientific writing that would directly answer this question.
Write as if you are {scientist_id} explaining this concept from your actual work.
This is for retrieval purposes only — focus on the physics, not on personality.
Timeline year: {timeline_year}

Question: {query}
Passage:"""

    hyde_text = await quick_complete(prompt, max_tokens=150)

    if not hyde_text:
        print(f"[QUERY_INTEL] HyDE generation failed, using rewritten query")
        return query

    print(f"[QUERY_INTEL] HyDE generated ({len(hyde_text.split())} words)")
    return hyde_text


# ── 3. Multi-Query Decomposer ─────────────────────────────────────────────────

async def decompose_query(query: str) -> list[str]:
    """
    Breaks a complex question into 1-3 focused sub-queries for retrieval.
    Simple questions return a list with just the original query.

    Example:
        "How did your photoelectric work influence quantum mechanics and
         why did that make you uncomfortable with Bohr's interpretation?"
        →
        ["photoelectric effect Einstein 1905 light quanta",
         "quantum mechanics development Einstein influence",
         "Einstein Bohr Copenhagen interpretation disagreement"]
    """
    prompt = f"""Break this question into 1-3 focused search queries for retrieval over scientific texts.
Return a JSON array of strings. Maximum 3 items.
If the question is simple and focused, return just 1 query.
Return ONLY the JSON array, no explanation.

Question: {query}
JSON array:"""

    result = await quick_complete(prompt, max_tokens=120)

    if not result:
        return [query]

    # Parse JSON
    try:
        # Strip any markdown code fences if present
        result = result.strip()
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        result = result.strip()

        sub_queries = json.loads(result)

        if not isinstance(sub_queries, list):
            return [query]

        # Clean and validate
        sub_queries = [q.strip() for q in sub_queries if isinstance(q, str) and q.strip()]
        sub_queries = sub_queries[:3]   # max 3

        if not sub_queries:
            return [query]

        print(f"[QUERY_INTEL] Decomposed into {len(sub_queries)} sub-queries")
        return sub_queries

    except (json.JSONDecodeError, ValueError):
        print(f"[QUERY_INTEL] Decompose parse failed, using original query")
        return [query]


# ── Combined query intelligence pipeline ─────────────────────────────────────

async def process_query(
    query         : str,
    scientist_id  : str,
    timeline_year : int,
    use_hyde      : bool = True,
    use_decompose : bool = True,
) -> dict:
    """
    Full query intelligence pipeline.
    Returns a dict with everything the retriever needs.

    Returns:
        {
            "original_query":  str,
            "rewritten_query": str,
            "hyde_text":       str,   ← embed this for dense retrieval
            "sub_queries":     list,  ← retrieve for each of these
        }
    """
    # Always rewrite
    rewritten = await rewrite_query(query, scientist_id, timeline_year)

    # HyDE — generate hypothetical answer for embedding
    if use_hyde:
        hyde_text = await generate_hyde(query, scientist_id, timeline_year)
    else:
        hyde_text = rewritten

    # Decompose into sub-queries
    if use_decompose:
        sub_queries = await decompose_query(rewritten)
    else:
        sub_queries = [rewritten]

    return {
        "original_query":  query,
        "rewritten_query": rewritten,
        "hyde_text":       hyde_text,
        "sub_queries":     sub_queries,
    }
