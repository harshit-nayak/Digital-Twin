"""
backend/app/rag/reranker.py

Two-stage reranking:
  Stage 1: Cross-encoder scoring (ms-marco-MiniLM-L-6-v2) — runs locally, free
  Stage 2: MMR diversity filter — removes redundant chunks
"""

from sentence_transformers import CrossEncoder
from app.rag.embedder import embed_single, cosine_similarity

# ── Cross-encoder (loaded once, reused) ──────────────────────────────────────

_cross_encoder = None

def get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        print("[RERANKER] Loading cross-encoder model (first time only)...")
        _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        print("[RERANKER] Cross-encoder ready.")
    return _cross_encoder

# ── Stage 1: Cross-encoder reranking ─────────────────────────────────────────

def cross_encoder_rerank(
    query  : str,
    chunks : list[dict],
    top_k  : int = 8,
) -> list[dict]:
    """
    Score each (query, chunk) pair with cross-encoder.
    Much more accurate than cosine similarity alone.
    Returns top_k chunks sorted by cross-encoder score.
    """
    if not chunks:
        return []

    encoder = get_cross_encoder()

    # Build (query, chunk_text) pairs
    pairs  = [(query, chunk["text"]) for chunk in chunks]
    scores = encoder.predict(pairs)

    # Attach scores and sort
    scored = sorted(
        zip(chunks, scores),
        key     = lambda x: x[1],
        reverse = True,
    )

    result = []
    for chunk, score in scored[:top_k]:
        c = chunk.copy()
        c["cross_encoder_score"] = float(score)
        result.append(c)

    return result

# ── Stage 2: MMR diversity filter ────────────────────────────────────────────

def mmr_filter(
    query         : str,
    chunks        : list[dict],
    top_k         : int   = 5,
    lambda_param  : float = 0.7,
) -> list[dict]:
    """
    Maximal Marginal Relevance:
    Selects chunks that are both relevant to the query AND
    different from already-selected chunks.

    lambda_param:
        1.0 = pure relevance (no diversity)
        0.0 = pure diversity (no relevance)
        0.7 = recommended balance

    Returns top_k diverse, relevant chunks.
    """
    if not chunks:
        return []

    if len(chunks) <= top_k:
        return chunks

    # Embed query and all chunks
    query_emb  = embed_single(query)
    chunk_embs = [embed_single(c["text"]) for c in chunks]

    selected_indices   = []
    remaining_indices  = list(range(len(chunks)))

    while len(selected_indices) < top_k and remaining_indices:

        if not selected_indices:
            # First pick: highest relevance to query
            best_idx = max(
                remaining_indices,
                key = lambda i: cosine_similarity(query_emb, chunk_embs[i])
            )
        else:
            # Subsequent picks: balance relevance vs diversity
            def mmr_score(i):
                relevance = cosine_similarity(query_emb, chunk_embs[i])
                # Max similarity to any already-selected chunk
                redundancy = max(
                    cosine_similarity(chunk_embs[i], chunk_embs[j])
                    for j in selected_indices
                )
                return lambda_param * relevance - (1 - lambda_param) * redundancy

            best_idx = max(remaining_indices, key=mmr_score)

        selected_indices.append(best_idx)
        remaining_indices.remove(best_idx)

    return [chunks[i] for i in selected_indices]

# ── Combined rerank pipeline ──────────────────────────────────────────────────

def rerank(
    query  : str,
    chunks : list[dict],
    top_k  : int = 5,
) -> list[dict]:
    """
    Full two-stage reranking pipeline:
      1. Cross-encoder: TopK=10 → Top 8
      2. MMR diversity: Top 8 → Top 3-5

    Args:
        query:  The original user query (not the rewritten version)
        chunks: Retrieved chunks from hybrid retrieval
        top_k:  Final number of chunks to return

    Returns:
        Final ranked, diverse chunks ready for context injection
    """
    if not chunks:
        return []

    print(f"[RERANKER] Input: {len(chunks)} chunks")

    # Stage 1: Cross-encoder
    stage1 = cross_encoder_rerank(query, chunks, top_k=min(8, len(chunks)))
    print(f"[RERANKER] After cross-encoder: {len(stage1)} chunks")

    # Stage 2: MMR diversity filter
    stage2 = mmr_filter(query, stage1, top_k=top_k)
    print(f"[RERANKER] After MMR: {len(stage2)} chunks")

    return stage2
