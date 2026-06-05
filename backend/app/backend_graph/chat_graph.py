from app.config import get_settings
from app.context import build_context
from app.llm import GenerationRequest, gateway
from app.memory import MemoryStore
from app.schemas import ChatRequest, ChatResponse, Source
from app.scientists import load_scientist


ALLOWED_TOPICS = {
    "physics",
    "science",
    "math",
    "mathematics",
    "energy",
    "light",
    "motion",
    "gravity",
    "radioactivity",
    "electricity",
    "quantum",
    "relativity",
    "learn",
    "explain",
}


def _domain_check(message: str) -> bool:
    words = set(message.lower().split())
    return bool(words & ALLOWED_TOPICS) or len(message.split()) < 8


def run_chat(request: ChatRequest) -> ChatResponse:
    settings = get_settings()
    scientist = load_scientist(request.scientist)

    if not _domain_check(request.message):
        return ChatResponse(
            message=f"{scientist.display_name} is ready for science, mathematics, and learning questions. Try asking about a concept, experiment, or timeline.",
            scientist=scientist.id,
            emotion="neutral",
        )

    context = build_context(
        query=request.message,
        scientist=scientist.id,
        timeline=request.timeline,
        session_id=request.session_id,
    )
    message = gateway.generate(
        GenerationRequest(
            system=context.system,
            prompt=context.prompt,
            temperature=0.35,
            max_tokens=800,
        )
    )

    memory_updates: list[str] = []
    if request.message.strip():
        store = MemoryStore()
        store.save(
            session_id=request.session_id,
            kind="topic",
            content=f"Student asked {scientist.display_name}: {request.message}",
            importance=0.6,
        )
        memory_updates.append("Saved conversation topic")

    trace = None
    if settings.backend_debug:
        trace = {
            "source_count": len(context.sources),
            "memory_count": len(context.memories),
            "provider": "gateway",
        }

    return ChatResponse(
        message=message,
        scientist=scientist.id,
        sources=[
            Source(
                id=source.id,
                title=source.title,
                scientist=source.scientist,
                score=source.score,
                timeline_start=source.timeline_start,
                timeline_end=source.timeline_end,
                excerpt=source.excerpt,
            )
            for source in context.sources
        ],
        timeline_context=context.timeline_context,
        emotion="thoughtful" if context.sources else "neutral",
        memory_updates=memory_updates,
        trace=trace,
    )

