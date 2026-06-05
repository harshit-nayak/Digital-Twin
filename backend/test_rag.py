"""
backend/test_rag.py

Quick test to verify the full RAG pipeline works end to end.
Run AFTER completing ingestion with real embeddings.

Usage:
    python test_rag.py
"""

from app.rag.pipeline import run_rag_pipeline, format_context_for_prompt

TEST_QUERIES = [
    {
        "query":         "What is special relativity?",
        "timeline_year": 1905,
        "expected_source": "On the Electrodynamics of Moving Bodies",
    },
    {
        "query":         "Why don't you accept quantum mechanics?",
        "timeline_year": 1927,
        "expected_source": "Solvay Conference 1927 Transcripts",
    },
    {
        "query":         "Explain the equivalence of mass and energy",
        "timeline_year": 1915,
        "expected_source": "Relativity: The Special and General Theory",
    },
]

async def test_pipeline():
    print("=" * 60)
    print("RAG PIPELINE TEST — EINSTEIN")
    print("=" * 60)

    for i, test in enumerate(TEST_QUERIES, 1):
        print(f"\n-- Test {i}/{len(TEST_QUERIES)} -----------------------------")
        print(f"Query:    {test['query']}")
        print(f"Year:     {test['timeline_year']}")

        result = await run_rag_pipeline(
            query         = test["query"],
            scientist_id  = "einstein",
            timeline_year = test["timeline_year"],
        )

        chunks = result["final_chunks"]

        if not chunks:
            print("❌ FAILED: No chunks returned")
            continue

        # Check source hit
        sources = [c["metadata"].get("source_title", "") for c in chunks]
        hit = any(test["expected_source"] in s for s in sources)

        print(f"\nChunks returned: {len(chunks)}")
        print(f"Sources: {sources}")
        print(f"Expected source hit: {'YES' if hit else 'NO MISS'}")
        print(f"\nTop chunk preview:")
        print(chunks[0]["text"][:300])
        print(f"\nFormatted context (first 500 chars):")
        print(format_context_for_prompt(chunks)[:500])

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_pipeline())
