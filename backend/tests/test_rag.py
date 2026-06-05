from pathlib import Path

from app.rag.engine import retrieve


def test_retrieve_with_local_corpus():
    path = Path(__file__).resolve().parents[2] / "data/corpus/raw/einstein/relativity.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("Relativity explains motion, light, clocks, and observers in physics.", encoding="utf-8")

    results = retrieve("How do light and clocks relate to motion?", "einstein", "1905")

    assert results
    assert results[0].scientist == "einstein"
    assert "Relativity" in results[0].title

