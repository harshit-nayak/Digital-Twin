"""
backend/app/rag/embedder.py

Embedding wrapper for Google text-embedding-004.
Handles single strings and batches.
Swappable — change EMBEDDING_MODEL to switch providers.
"""

import os
import time
from pathlib import Path
from dotenv import load_dotenv
import google.genai as genai

load_dotenv()

EMBEDDING_MODEL = "models/gemini-embedding-001"
BATCH_SIZE      = 5      # stay within free tier rate limits
RETRY_DELAY     = 5      # seconds to wait on rate limit error


def get_client():
    api_key = os.getenv("GEMINI_KEY_1")
    if not api_key:
        raise ValueError("GEMINI_KEY_1 not set in .env")
    return genai.Client(api_key=api_key)


_client = None

def client():
    global _client
    if _client is None:
        _client = get_client()
    return _client


def embed_single(text: str) -> list[float]:
    """
    Embed a single string.
    Returns a list of floats (the embedding vector).
    """
    try:
        response = client().models.embed_content(
            model    = EMBEDDING_MODEL,
            contents = [text],
        )
        return response.embeddings[0].values
    except Exception as e:
        print(f"[EMBEDDER] Error embedding single text: {e}")
        return []


def embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of strings in batches.
    Returns a list of embedding vectors in the same order as input.
    """
    all_embeddings = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        success = False
        attempts = 0

        while not success and attempts < 3:
            try:
                response = client().models.embed_content(
                    model    = EMBEDDING_MODEL,
                    contents = batch,
                )
                for emb in response.embeddings:
                    all_embeddings.append(emb.values)
                success = True

            except Exception as e:
                attempts += 1
                print(f"[EMBEDDER] Batch {i//BATCH_SIZE + 1} attempt {attempts} failed: {e}")
                if attempts < 3:
                    time.sleep(RETRY_DELAY)
                else:
                    # Return empty vectors for failed batch
                    for _ in batch:
                        all_embeddings.append([])

    return all_embeddings


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.
    Used in MMR diversity filtering.
    """
    if not vec_a or not vec_b:
        return 0.0

    dot   = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = sum(a * a for a in vec_a) ** 0.5
    mag_b = sum(b * b for b in vec_b) ** 0.5

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot / (mag_a * mag_b)
