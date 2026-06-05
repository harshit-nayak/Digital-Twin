"""
backend/app/rag/retriever.py

Hybrid retrieval: dense (ChromaDB) + sparse (BM25) merged with
Reciprocal Rank Fusion. Applies timeline metadata filter so
a scientist only retrieves from their past, not their future.
"""

import os
import pickle
from pathlib import Path
from dotenv import load_dotenv
import chromadb

from app.rag.embedder import embed_single

load_dotenv()

BASE_DIR   = Path(__file__).resolve().parents[2]
CHROMA_DIR = BASE_DIR / "db" / "chroma"
BM25_DIR   = BASE_DIR / "db" / "bm25"

# ── ChromaDB client (singleton) ───────────────────────────────────────────────

_chroma_client = None

def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _chroma_client


def get_collection(scientist_id: str):
    return get_chroma_client().get_collection(name=scientist_id)

# ── BM25 index loader (singleton per scientist) ───────────────────────────────

_bm25_cache = {}

def get_bm25_index(scientist_id: str) -> dict:
    if scientist_id not in _bm25_cache:
        path = BM25_DIR / f"{scientist_id}_bm25.pkl"
        if not path.exists():
            raise FileNotFoundError(
                f"BM25 index not found: {path}\n"
                f"Run ingestion first: python -m app.rag.ingest --scientist {scientist_id}"
            )
        with open(path, "rb") as f:
            _bm25_cache[scientist_id] = pickle.load(f)
    return _bm25_cache[scientist_id]

# ── Dense retrieval ───────────────────────────────────────────────────────────

def dense_retrieve(
    query_embedding : list[float],
    scientist_id    : str,
    timeline_year   : int,
    top_k           : int = 10,
) -> list[dict]:
    """
    Query ChromaDB with a query embedding.
    Filters to chunks with year <= timeline_year.
    Returns list of chunk dicts with score.
    """
    try:
        collection = get_collection(scientist_id)
    except Exception as e:
        print(f"[RETRIEVER] ChromaDB collection '{scientist_id}' not found: {e}")
        return []

    results = collection.query(
        query_embeddings = [query_embedding],
        n_results        = top_k,
        where            = {"year": {"$lte": timeline_year}},
        include          = ["documents", "metadatas", "distances"],
    )

    chunks = []
    for i in range(len(results["ids"][0])):
        chunks.append({
            "chunk_id":     results["ids"][0][i],
            "text":         results["documents"][0][i],
            "metadata":     results["metadatas"][0][i],
            "dense_score":  1 - results["distances"][0][i],  # convert distance to similarity
            "source":       "dense",
        })

    return chunks

# ── Sparse BM25 retrieval ─────────────────────────────────────────────────────

def sparse_retrieve(
    query           : str,
    scientist_id    : str,
    timeline_year   : int,
    top_k           : int = 10,
) -> list[dict]:
    """
    BM25 keyword retrieval over stored corpus.
    Applies timeline filter after retrieval.
    """
    index_data = get_bm25_index(scientist_id)
    bm25       = index_data["bm25"]
    corpus     = index_data["chunks"]

    tokenized_query = query.lower().split()
    scores          = bm25.get_scores(tokenized_query)

    # Pair each chunk with its BM25 score
    scored = sorted(
        enumerate(scores),
        key     = lambda x: x[1],
        reverse = True
    )

    chunks = []
    for idx, score in scored:
        if len(chunks) >= top_k * 2:   # over-fetch then filter
            break
        chunk = corpus[idx]
        # Apply timeline filter
        if chunk.get("year", 9999) <= timeline_year:
            chunks.append({
                "chunk_id":    chunk["chunk_id"],
                "text":        chunk["text"],
                "metadata": {
                    "source_title":    chunk.get("source_title", ""),
                    "source_type":     chunk.get("source_type", ""),
                    "year":            chunk.get("year", 0),
                    "timeline_period": chunk.get("timeline_period", ""),
                },
                "sparse_score": float(score),
                "source":       "sparse",
            })
        if len(chunks) >= top_k:
            break

    return chunks

# ── Reciprocal Rank Fusion ────────────────────────────────────────────────────

def reciprocal_rank_fusion(
    dense_chunks  : list[dict],
    sparse_chunks : list[dict],
    k             : int = 60,
) -> list[dict]:
    """
    Merge dense and sparse results using Reciprocal Rank Fusion.
    RRF score = sum of 1/(k + rank) across all ranked lists.

    Returns deduplicated list sorted by RRF score (highest first).
    """
    rrf_scores = {}   # chunk_id → rrf score
    all_chunks = {}   # chunk_id → chunk dict

    # Score dense results
    for rank, chunk in enumerate(dense_chunks):
        cid = chunk["chunk_id"]
        rrf_scores[cid] = rrf_scores.get(cid, 0) + 1 / (k + rank + 1)
        all_chunks[cid] = chunk

    # Score sparse results
    for rank, chunk in enumerate(sparse_chunks):
        cid = chunk["chunk_id"]
        rrf_scores[cid] = rrf_scores.get(cid, 0) + 1 / (k + rank + 1)
        if cid not in all_chunks:
            all_chunks[cid] = chunk

    # Sort by RRF score
    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    merged = []
    for cid, score in ranked:
        chunk = all_chunks[cid].copy()
        chunk["rrf_score"] = score
        merged.append(chunk)

    return merged

# ── Main hybrid retrieval function ───────────────────────────────────────────

def hybrid_retrieve(
    query         : str,
    scientist_id  : str,
    timeline_year : int,
    top_k         : int = 10,
) -> list[dict]:
    """
    Full hybrid retrieval pipeline:
    1. Embed the query
    2. Dense retrieval from ChromaDB
    3. Sparse BM25 retrieval
    4. Merge with RRF
    5. Return top_k results

    Args:
        query:         The search query (already rewritten by query intelligence layer)
        scientist_id:  e.g. "einstein"
        timeline_year: Only retrieve chunks with year <= this value
        top_k:         Number of results to return before reranking

    Returns:
        List of chunk dicts sorted by RRF score
    """
    # Step 1: Embed query
    query_embedding = embed_single(query)

    if not query_embedding:
        print("[RETRIEVER] Embedding failed, falling back to sparse only")
        sparse = sparse_retrieve(query, scientist_id, timeline_year, top_k)
        return sparse

    # Step 2: Dense retrieval
    dense  = dense_retrieve(query_embedding, scientist_id, timeline_year, top_k)

    # Step 3: Sparse retrieval
    sparse = sparse_retrieve(query, scientist_id, timeline_year, top_k)

    # Step 4: Merge with RRF
    merged = reciprocal_rank_fusion(dense, sparse)

    print(f"[RETRIEVER] Dense: {len(dense)} | Sparse: {len(sparse)} | Merged: {len(merged)}")

    return merged[:top_k]


def multi_query_retrieve(
    queries       : list[str],
    scientist_id  : str,
    timeline_year : int,
    top_k         : int = 10,
) -> list[dict]:
    """
    Run hybrid retrieval for multiple queries (from query decomposer),
    deduplicate results, and return top_k by RRF score.
    """
    seen_ids   = set()
    all_chunks = []

    for query in queries:
        results = hybrid_retrieve(query, scientist_id, timeline_year, top_k)
        for chunk in results:
            if chunk["chunk_id"] not in seen_ids:
                seen_ids.add(chunk["chunk_id"])
                all_chunks.append(chunk)

    # Re-sort by rrf_score after deduplication
    all_chunks.sort(key=lambda x: x.get("rrf_score", 0), reverse=True)

    return all_chunks[:top_k]
