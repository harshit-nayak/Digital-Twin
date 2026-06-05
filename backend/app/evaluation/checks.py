def evaluate_response(message: str, source_count: int, scientist: str) -> dict[str, bool | str]:
    grounded = source_count > 0 and bool(message.strip())
    persona = scientist.lower() in message.lower() or bool(message.strip())
    return {
        "rag_triad_ready": grounded,
        "hallucination_check_ready": source_count > 0,
        "persona_fidelity_ready": persona,
        "memory_quality_ready": True,
        "notes": "Heuristic v1 checks; replace with rubric scoring in evaluation phase.",
    }

