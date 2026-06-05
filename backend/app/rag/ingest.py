"""
backend/app/rag/ingest.py

Corpus ingestion pipeline for the Digital Twin Physics Academy.
Run this script once per scientist to clean, chunk, embed, and store their corpus.

Usage:
    python -m app.rag.ingest --scientist einstein
"""

import os
import re
import json
import pickle
import argparse
import yaml
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
from rank_bm25 import BM25Okapi
import google.genai as genai

load_dotenv()

# ── Constants ─────────────────────────────────────────────────────────────────

CHUNK_SIZE      = 500        # target tokens per chunk (approx 4 chars per token)
CHUNK_OVERLAP   = 50         # overlap in tokens between chunks
CHARS_PER_TOKEN = 4          # rough approximation
CHUNK_CHARS     = CHUNK_SIZE * CHARS_PER_TOKEN
OVERLAP_CHARS   = CHUNK_OVERLAP * CHARS_PER_TOKEN

BASE_DIR        = Path(__file__).resolve().parents[2]   # backend/
CONFIG_DIR      = BASE_DIR / "config" / "scientists"
DATA_DIR        = BASE_DIR / "data"
CHROMA_DIR      = BASE_DIR / "db" / "chroma"
BM25_DIR        = BASE_DIR / "db" / "bm25"

# ── Gemini client ─────────────────────────────────────────────────────────────

def get_gemini_client():
    api_key = os.getenv("GEMINI_KEY_1")
    if not api_key:
        raise ValueError("GEMINI_KEY_1 not found in .env")
    client = genai.Client(api_key=api_key)
    return client

# ── Config loader ─────────────────────────────────────────────────────────────

def load_scientist_config(scientist_id: str) -> dict:
    config_path = CONFIG_DIR / f"{scientist_id}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# ── Step 1: Load raw documents ────────────────────────────────────────────────

def load_documents(scientist_id: str, config: dict) -> list[dict]:
    """
    Load all corpus files for a scientist.
    Returns list of { filename, raw_text, source_type, year, timeline_period }
    """
    corpus_base = DATA_DIR / scientist_id
    files       = config["corpus"]["files"]

    documents = []
    for filename in files:
        filepath = corpus_base / filename
        if not filepath.exists():
            print(f"  [WARN] File not found, skipping: {filepath}")
            continue

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            raw_text = f.read()

        # Infer metadata from filename
        meta = infer_metadata(filename, scientist_id)

        documents.append({
            "filename":        filename,
            "raw_text":        raw_text,
            "source_title":    meta["source_title"],
            "source_type":     meta["source_type"],
            "year":            meta["year"],
            "timeline_period": meta["timeline_period"],
        })

        print(f"  [LOAD] {filename} — {len(raw_text):,} chars")

    return documents


def infer_metadata(filename: str, scientist_id: str) -> dict:
    """
    Infer source metadata from filename.
    Extend this dict as you add more files.
    """
    metadata_map = {
        # Einstein
        "relativity_book.txt": {
            "source_title":    "Relativity: The Special and General Theory",
            "source_type":     "book",
            "year":            1916,
            "timeline_period": "1915",
        },
        "world_as_i_see_it.txt": {
            "source_title":    "The World As I See It",
            "source_type":     "essays",
            "year":            1934,
            "timeline_period": "1935",
        },
        "1905_photoelectric.txt": {
            "source_title":    "On a Heuristic Point of View Concerning the Production and Transformation of Light",
            "source_type":     "paper",
            "year":            1905,
            "timeline_period": "1905",
        },
        "1905_special_relativity.txt": {
            "source_title":    "On the Electrodynamics of Moving Bodies",
            "source_type":     "paper",
            "year":            1905,
            "timeline_period": "1905",
        },
        "solvay_1927.txt": {
            "source_title":    "Solvay Conference 1927 Transcripts",
            "source_type":     "transcript",
            "year":            1927,
            "timeline_period": "1927",
        },
    }

    if filename in metadata_map:
        return metadata_map[filename]

    # Fallback — unknown file
    print(f"  [WARN] No metadata mapping for {filename}, using defaults")
    return {
        "source_title":    filename.replace(".txt", "").replace("_", " ").title(),
        "source_type":     "unknown",
        "year":            1900,
        "timeline_period": "1905",
    }

# ── Step 2: Clean text ────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """
    Clean raw text:
    - Remove Project Gutenberg headers/footers
    - Normalize whitespace
    - Remove page numbers and running headers
    - Fix encoding artifacts
    """
    # Remove Project Gutenberg boilerplate
    gutenberg_start = re.search(
        r"\*\*\* START OF (THE|THIS) PROJECT GUTENBERG", text, re.IGNORECASE
    )
    gutenberg_end = re.search(
        r"\*\*\* END OF (THE|THIS) PROJECT GUTENBERG", text, re.IGNORECASE
    )
    if gutenberg_start:
        text = text[gutenberg_start.end():]
    if gutenberg_end:
        text = text[:gutenberg_end.start()]

    # Remove lines that are just page numbers (e.g. "- 42 -" or just "42")
    text = re.sub(r"^\s*-?\s*\d+\s*-?\s*$", "", text, flags=re.MULTILINE)

    # Remove lines that look like running headers (all caps, short)
    text = re.sub(r"^[A-Z\s]{5,50}$", "", text, flags=re.MULTILINE)

    # Normalize multiple newlines to max 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove leading/trailing whitespace per line
    lines = [line.strip() for line in text.split("\n")]
    text  = "\n".join(lines)

    # Fix common encoding artifacts
    text = text.replace("\x00", "")
    text = text.replace("\ufffd", "'")
    text = text.replace("â€™", "'")
    text = text.replace("â€œ", '"')
    text = text.replace("â€", '"')

    # Normalize whitespace within lines
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()

# ── Step 3: Semantic-aware chunking ───────────────────────────────────────────

def chunk_document(doc: dict) -> list[dict]:
    """
    Split a document into overlapping chunks.
    Tries to split on paragraph boundaries first (semantic-aware).
    Falls back to character-based splitting.

    Each chunk gets full metadata from its parent document.
    """
    text     = doc["raw_text"]
    chunks   = []
    chunk_id = 0

    # Split into paragraphs first
    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]

    current_chunk  = ""
    current_chars  = 0

    for para in paragraphs:
        para_chars = len(para)

        # If a single paragraph is larger than chunk size, split it by sentence
        if para_chars > CHUNK_CHARS * 1.5:
            sentences   = split_into_sentences(para)
            for sentence in sentences:
                if current_chars + len(sentence) > CHUNK_CHARS and current_chunk:
                    # Save current chunk
                    chunks.append(make_chunk(
                        doc, current_chunk.strip(), chunk_id
                    ))
                    chunk_id += 1
                    # Start new chunk with overlap
                    overlap_text  = get_overlap_text(current_chunk)
                    current_chunk = overlap_text + " " + sentence
                    current_chars = len(current_chunk)
                else:
                    current_chunk += " " + sentence
                    current_chars += len(sentence)
            continue

        # Normal paragraph — add to current chunk or start new one
        if current_chars + para_chars > CHUNK_CHARS and current_chunk:
            chunks.append(make_chunk(doc, current_chunk.strip(), chunk_id))
            chunk_id += 1
            overlap_text  = get_overlap_text(current_chunk)
            current_chunk = overlap_text + "\n\n" + para
            current_chars = len(current_chunk)
        else:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
            current_chars = len(current_chunk)

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append(make_chunk(doc, current_chunk.strip(), chunk_id))

    return chunks


def make_chunk(doc: dict, text: str, chunk_id: int) -> dict:
    """Build a chunk dict with full metadata."""
    return {
        "chunk_id":        f"{doc['filename'].replace('.txt','')}_{chunk_id:04d}",
        "text":            text,
        "source_title":    doc["source_title"],
        "source_type":     doc["source_type"],
        "year":            doc["year"],
        "timeline_period": doc["timeline_period"],
        "char_count":      len(text),
        "word_count":      len(text.split()),
    }


def split_into_sentences(text: str) -> list[str]:
    """Simple sentence splitter."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def get_overlap_text(text: str) -> str:
    """Get the last OVERLAP_CHARS characters for chunk overlap."""
    if len(text) <= OVERLAP_CHARS:
        return text
    # Try to start overlap at a sentence boundary
    overlap_region = text[-OVERLAP_CHARS:]
    sentence_start = overlap_region.find(". ")
    if sentence_start != -1:
        return overlap_region[sentence_start + 2:]
    return overlap_region

# ── Step 4: Embed chunks ──────────────────────────────────────────────────────

def embed_chunks(chunks: list[dict], client) -> list[dict]:
    """
    Embed each chunk using Google gemini-embedding-001.
    Adds 'embedding' key to each chunk dict.
    Handles 429 rate limits by parsing retry-after delay and sleeping.
    Free tier: 100 requests/min -> batch of 5 = safe throughput.
    """
    import time as _time
    import re as _re
    BATCH_SIZE       = 5    # 5 texts/request, ~20 req/min well under 100/min
    FALLBACK_SLEEP   = 65   # sleep this long on 429 if no delay in error msg
    total            = len(chunks)

    print(f"  [EMBED] Embedding {total} chunks (batch={BATCH_SIZE}, rate-limit-aware)...")

    for i in range(0, total, BATCH_SIZE):
        batch   = chunks[i : i + BATCH_SIZE]
        texts   = [c["text"] for c in batch]
        attempt = 0

        while attempt < 6:
            try:
                response = client.models.embed_content(
                    model    = "models/gemini-embedding-001",
                    contents = texts,
                )
                for j, chunk in enumerate(batch):
                    chunk["embedding"] = response.embeddings[j].values
                break  # success, move on

            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    m     = _re.search(r"retry[^\d]*(\d+)", err_str, _re.IGNORECASE)
                    delay = int(m.group(1)) + 3 if m else FALLBACK_SLEEP
                    print(f"  [RATE LIMIT] batch {i//BATCH_SIZE + 1} — sleeping {delay}s ...")
                    _time.sleep(delay)
                    attempt += 1
                else:
                    print(f"  [ERROR] Batch {i//BATCH_SIZE + 1} failed: {e}")
                    for chunk in batch:
                        chunk["embedding"] = []
                    break
        else:
            print(f"  [SKIP] Batch {i//BATCH_SIZE + 1} gave up after 6 attempts.")
            for chunk in batch:
                chunk["embedding"] = []

        if (i // BATCH_SIZE + 1) % 20 == 0:
            print(f"  [EMBED] Progress: {min(i + BATCH_SIZE, total)}/{total}")

    print(f"  [EMBED] Done.")
    return chunks

# ── Step 5: Store to ChromaDB ─────────────────────────────────────────────────

def store_to_chromadb(chunks: list[dict], scientist_id: str):
    """
    Store embedded chunks in ChromaDB.
    One collection per scientist.
    Skips chunks with empty embeddings.
    """
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    client     = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(
        name     = scientist_id,
        metadata = {"hnsw:space": "cosine"}
    )

    valid_chunks = [c for c in chunks if c.get("embedding")]

    if not valid_chunks:
        print("  [CHROMA] No valid embeddings to store.")
        return

    ids        = [c["chunk_id"]   for c in valid_chunks]
    embeddings = [c["embedding"]  for c in valid_chunks]
    documents  = [c["text"]       for c in valid_chunks]
    metadatas  = [
        {
            "source_title":    c["source_title"],
            "source_type":     c["source_type"],
            "year":            c["year"],
            "timeline_period": c["timeline_period"],
            "word_count":      c["word_count"],
        }
        for c in valid_chunks
    ]

    # Add in batches to avoid ChromaDB limits
    BATCH = 100
    for i in range(0, len(valid_chunks), BATCH):
        collection.add(
            ids        = ids[i:i+BATCH],
            embeddings = embeddings[i:i+BATCH],
            documents  = documents[i:i+BATCH],
            metadatas  = metadatas[i:i+BATCH],
        )

    print(f"  [CHROMA] Stored {len(valid_chunks)} chunks in collection '{scientist_id}'")

# ── Step 6: Build BM25 index ──────────────────────────────────────────────────

def build_bm25_index(chunks: list[dict], scientist_id: str):
    """
    Build a BM25 sparse retrieval index over all chunks.
    Saved as a pickle file for fast loading at query time.
    """
    BM25_DIR.mkdir(parents=True, exist_ok=True)

    tokenized_corpus = [c["text"].lower().split() for c in chunks]
    bm25             = BM25Okapi(tokenized_corpus)

    index_data = {
        "bm25":   bm25,
        "chunks": chunks,           # store chunk text + metadata alongside index
    }

    save_path = BM25_DIR / f"{scientist_id}_bm25.pkl"
    with open(save_path, "wb") as f:
        pickle.dump(index_data, f)

    print(f"  [BM25] Index saved: {save_path} ({len(chunks)} chunks)")

# ── Step 7: Save chunk manifest ───────────────────────────────────────────────

def save_manifest(chunks: list[dict], scientist_id: str):
    """
    Save a JSON manifest of all chunks (without embeddings) for inspection.
    Useful for debugging and verifying chunk quality.
    """
    manifest_dir  = BASE_DIR / "db"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"{scientist_id}_manifest.json"

    manifest = [
        {
            "chunk_id":     c["chunk_id"],
            "source_title": c["source_title"],
            "source_type":  c["source_type"],
            "year":         c["year"],
            "word_count":   c["word_count"],
            "preview":      c["text"][:200] + "..." if len(c["text"]) > 200 else c["text"],
        }
        for c in chunks
    ]

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"  [MANIFEST] Saved {len(manifest)} entries -> {manifest_path}")

# ── Main pipeline ─────────────────────────────────────────────────────────────

def ingest(scientist_id: str, skip_embed: bool = False):
    """
    Full ingestion pipeline for one scientist.

    Args:
        scientist_id: e.g. "einstein"
        skip_embed:   if True, skip embedding (useful for testing chunking only)
    """
    print(f"\n{'='*60}")
    print(f"  INGESTING: {scientist_id.upper()}")
    print(f"{'='*60}\n")

    # Load config
    print("[1/6] Loading config...")
    config = load_scientist_config(scientist_id)

    # Load documents
    print("\n[2/6] Loading documents...")
    documents = load_documents(scientist_id, config)
    print(f"  Loaded {len(documents)} documents")

    if not documents:
        print("  [ERROR] No documents loaded. Check data/ folder.")
        return

    # Clean + chunk
    print("\n[3/6] Cleaning and chunking...")
    all_chunks = []
    for doc in documents:
        doc["raw_text"] = clean_text(doc["raw_text"])
        chunks          = chunk_document(doc)
        all_chunks.extend(chunks)
        print(f"  {doc['filename']}: {len(chunks)} chunks")

    print(f"  Total chunks: {len(all_chunks)}")

    # Embed
    if not skip_embed:
        print("\n[4/6] Embedding chunks...")
        client     = get_gemini_client()
        all_chunks = embed_chunks(all_chunks, client)
    else:
        print("\n[4/6] Skipping embedding (--skip-embed flag set)")
        for chunk in all_chunks:
            chunk["embedding"] = []

    # Store to ChromaDB
    print("\n[5/6] Storing to ChromaDB...")
    store_to_chromadb(all_chunks, scientist_id)

    # Build BM25 index
    print("\n[6/6] Building BM25 index...")
    build_bm25_index(all_chunks, scientist_id)

    # Save manifest for inspection
    save_manifest(all_chunks, scientist_id)

    print(f"\n{'='*60}")
    print(f"  INGESTION COMPLETE: {scientist_id.upper()}")
    print(f"  Total chunks ingested: {len(all_chunks)}")
    print(f"  ChromaDB collection:   {scientist_id}")
    print(f"  BM25 index:            db/bm25/{scientist_id}_bm25.pkl")
    print(f"  Chunk manifest:        db/{scientist_id}_manifest.json")
    print(f"{'='*60}\n")


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest scientist corpus")
    parser.add_argument(
        "--scientist",
        type    = str,
        default = "einstein",
        help    = "Scientist ID to ingest (e.g. einstein)"
    )
    parser.add_argument(
        "--skip-embed",
        action  = "store_true",
        help    = "Skip embedding step (for testing chunking only)"
    )
    args = parser.parse_args()

    ingest(args.scientist, skip_embed=args.skip_embed)