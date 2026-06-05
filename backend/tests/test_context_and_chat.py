from pathlib import Path

from app.backend_graph import run_chat
from app.context import build_context
from app.schemas import ChatRequest


def test_context_contains_persona_and_sources():
    path = Path(__file__).resolve().parents[2] / "data/corpus/raw/einstein/relativity.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("Light has a constant velocity in special relativity.", encoding="utf-8")

    context = build_context("Explain light velocity", "einstein", "1905", "test-session")

    assert "Albert Einstein" in context.system
    assert context.sources


def test_post_chat_flow_returns_response():
    response = run_chat(
        ChatRequest(
            session_id="test-session",
            scientist="einstein",
            message="Explain physics of light and motion",
            timeline="1905",
        )
    )

    assert response.scientist == "einstein"
    assert response.message
    assert response.memory_updates

