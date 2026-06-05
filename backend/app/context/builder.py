from dataclasses import dataclass

from app.memory import retrieve_memory
from app.rag import retrieve
from app.scientists import load_scientist


@dataclass
class ContextPackage:
    system: str
    prompt: str
    timeline_context: str | None
    sources: list
    memories: list


def build_context(query: str, scientist: str, timeline: str | None, session_id: str) -> ContextPackage:
    config = load_scientist(scientist)
    sources = retrieve(query=query, scientist=scientist, timeline=timeline)
    memories = retrieve_memory(query=query, session_id=session_id)
    selected_timeline = next(
        (
            item
            for item in config.timelines
            if timeline and (timeline == item.id or timeline.lower() in item.label.lower())
        ),
        config.timelines[0] if config.timelines else None,
    )

    source_lines = [
        f"Source {index + 1} [{source.title}, score {source.score}]: {source.excerpt}"
        for index, source in enumerate(sources)
    ]
    memory_lines = [f"Memory {index + 1}: {memory.content}" for index, memory in enumerate(memories)]
    teaching = "; ".join(config.teaching_strategy.moves)
    principles = "; ".join(config.persona.principles)
    timeline_context = selected_timeline.focus if selected_timeline else None

    system = (
        f"You are {config.display_name}. Voice: {config.persona.voice} "
        f"Principles: {principles}. Teaching style: {config.teaching_strategy.style}. "
        "Stay grounded in supplied sources. If evidence is missing, say what is missing."
    )
    prompt = "\n".join(
        [
            f"Timeline: {selected_timeline.label if selected_timeline else 'general'}",
            f"Timeline focus: {timeline_context or 'general scientific teaching'}",
            f"Teaching moves: {teaching}",
            *memory_lines,
            *source_lines,
            f"Student: {query}",
            "Answer as a concise classroom explanation with citations when sources are available.",
        ]
    )
    return ContextPackage(system=system, prompt=prompt, timeline_context=timeline_context, sources=sources, memories=memories)

