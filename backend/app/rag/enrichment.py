"""
backend/app/rag/enrichment.py

Retrieval Enrichment — runs after retrieval, before reranking.

Two techniques:
    1. Sentence Window Expansion  — fetch ±2 sentences around each chunk
    2. Auto-Merge (Parent-Child)  — if >50% of a parent's children are
                                    retrieved, replace them with the full parent

Note: In this implementation, sentence window expansion works on the
chunk text itself (we don't have the original document loaded in memory
after ingestion). For a future upgrade, store sentence indices in metadata.
"""

import re


def expand_sentence_window(chunk: dict, window: int = 2) -> dict:
    """
    Expand a chunk by ±`window` sentences from its own text.
    Keeps original text for reranking; uses expanded text for injection.

    Since we don't have the parent doc loaded post-ingestion, we
    use the chunk's own text and expand from its boundaries.
    In a future version, this would fetch from the original file.

    For now: this is a no-op pass-through (chunk text IS the window).
    We tag it so the system knows enrichment ran.
    """
    chunk = chunk.copy()
    # Mark that enrichment was applied
    chunk["enriched"]            = True
    chunk["text_for_injection"]  = chunk.get("text", "")
    chunk["text_for_reranking"]  = chunk.get("text", "")
    return chunk


def auto_merge(chunks: list[dict], merge_threshold: float = 0.5) -> list[dict]:
    """
    Parent-Child Auto-Merging.

    If more than `merge_threshold` fraction of a parent section's children
    are retrieved, replace all those children with their parent content.

    Implementation:
        - Groups chunks by their 'parent_id' metadata field
        - For groups that exceed the threshold, marks them as merged
        - In a simple corpus without explicit parent IDs, this is a no-op

    This prevents redundancy when many chunks from the same section
    all get retrieved — better to inject the whole section once.
    """
    if not chunks:
        return chunks

    # Group by parent_id
    parent_groups: dict[str, list[dict]] = {}
    no_parent: list[dict] = []

    for chunk in chunks:
        meta      = chunk.get("metadata", {})
        parent_id = meta.get("parent_id", None)
        if parent_id:
            parent_groups.setdefault(parent_id, []).append(chunk)
        else:
            no_parent.append(chunk)

    # If no parent IDs exist (current setup), return as-is
    if not parent_groups:
        return chunks

    merged = list(no_parent)

    for parent_id, children in parent_groups.items():
        # We don't track total_children count in current metadata
        # So for any group of 3+ chunks from same parent, merge them
        if len(children) >= 3:
            # Combine children into one pseudo-merged chunk
            combined_text = "\n\n".join(c["text"] for c in children)
            merged_chunk = children[0].copy()
            merged_chunk["text"]   = combined_text
            merged_chunk["merged"] = True
            merged.append(merged_chunk)
            print(f"[ENRICHMENT] Merged {len(children)} chunks from parent '{parent_id}'")
        else:
            merged.extend(children)

    return merged


def enrich_chunks(chunks: list[dict]) -> list[dict]:
    """
    Full enrichment pipeline:
    1. Sentence window expansion
    2. Auto-merge
    """
    if not chunks:
        return chunks

    # Step 1: Expand sentence windows
    expanded = [expand_sentence_window(c) for c in chunks]

    # Step 2: Auto-merge parent groups
    merged = auto_merge(expanded)

    print(f"[ENRICHMENT] {len(chunks)} chunks -> {len(merged)} after enrichment")
    return merged
