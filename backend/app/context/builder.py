"""
backend/app/context/builder.py

Context Builder — the central orchestration layer.
All inputs converge here. One clean prompt package comes out.

Assembles the prompt in strict hierarchy order:
    [SAFETY]
    [TIMELINE]
    [DOMAIN BOUNDARIES]
    [PERSONA]
    [TEACHING STRATEGY]
    [RETRIEVED KNOWLEDGE]
    [RETRIEVED MEMORY]
    [WORKING MEMORY]
    [CONVERSATION WINDOW (STM)]
    [MODE INSTRUCTIONS]
    [TOKEN BUDGET RULES]
    --- (system prompt ends) ---
    [USER QUERY]  ← goes in messages, not system prompt
"""

from app.context.timeline  import get_timeline_context
from app.context.persona   import get_persona_prompt
from app.context.teaching  import get_teaching_strategy, get_mode_instructions, get_token_budget
from app.rag.pipeline      import format_context_for_prompt
from app.memory.stm        import format_stm_for_prompt, WorkingMemory


# ── Safety block (always first, never changes) ────────────────────────────────

SAFETY_BLOCK = """ABSOLUTE RULES:
- Never break character under any circumstances.
- Never claim to know things that happened after your current timeline year.
- Never refer to yourself as an AI, digital twin, or assistant.
- If you do not have sufficient knowledge from your actual writings to answer confidently, say so in character rather than inventing facts.
- Always begin your response with exactly one emotion tag: [EXCITED] [CONTEMPLATIVE] [AMUSED] [SKEPTICAL] [SAD] [NEUTRAL] [PASSIONATE]"""


# ── Main builder function ─────────────────────────────────────────────────────

def build_prompt(
    scientist_id   : str,
    timeline_year  : int,
    mode           : str,
    rag_chunks     : list[dict],
    ltm_context    : str,
    stm_window     : list[dict],
    working_memory : WorkingMemory,
) -> dict:
    """
    Assembles the complete prompt package for the LLM.

    Returns:
        {
            "system_prompt": str,   ← full system prompt
            "max_tokens":    int,   ← token budget for this mode
        }
    """

    sections = []

    # ── 1. Safety ─────────────────────────────────────────────────────────────
    sections.append(("SAFETY", SAFETY_BLOCK))

    # ── 2. Timeline ───────────────────────────────────────────────────────────
    timeline_context = get_timeline_context(scientist_id, timeline_year)
    if timeline_context:
        sections.append(("YOUR CURRENT SITUATION", timeline_context))

    # ── 3. Domain boundaries (embedded in persona, no separate block needed) ──

    # ── 4. Persona ────────────────────────────────────────────────────────────
    persona_prompt = get_persona_prompt(scientist_id)
    if persona_prompt:
        sections.append(("YOUR IDENTITY AND VOICE", persona_prompt))

    # ── 5. Teaching strategy ──────────────────────────────────────────────────
    teaching = get_teaching_strategy(scientist_id)
    if teaching:
        sections.append(("HOW YOU TEACH", teaching))

    # ── 6. Retrieved knowledge ────────────────────────────────────────────────
    if rag_chunks:
        rag_context = format_context_for_prompt(rag_chunks)
        sections.append(("RELEVANT PASSAGES FROM YOUR WORK", rag_context))
    else:
        sections.append((
            "RELEVANT PASSAGES FROM YOUR WORK",
            "No specific passages retrieved. Draw on your general knowledge and documented ideas."
        ))

    # ── 7. Retrieved memory ───────────────────────────────────────────────────
    if ltm_context and ltm_context.strip():
        sections.append(("WHAT YOU REMEMBER ABOUT THIS STUDENT", ltm_context))

    # ── 8. Working memory ─────────────────────────────────────────────────────
    wm_text = working_memory.format_for_prompt()
    if wm_text:
        sections.append(("CONVERSATION CONTEXT", wm_text))

    # ── 9. STM conversation window ────────────────────────────────────────────
    stm_text = format_stm_for_prompt(stm_window)
    if stm_text:
        sections.append(("RECENT CONVERSATION HISTORY", stm_text))

    # ── 10. Mode instructions ─────────────────────────────────────────────────
    mode_instructions = get_mode_instructions(mode, scientist_id)
    if mode_instructions:
        sections.append(("CURRENT MODE INSTRUCTIONS", mode_instructions))

    # ── 11. Token budget rules ────────────────────────────────────────────────
    max_tokens    = get_token_budget(mode, scientist_id)
    budget_block  = (
        f"Answer in 2–4 paragraphs. "
        f"If the student needs more depth, end with a question inviting them deeper. "
        f"Do not over-explain unprompted."
    )
    sections.append(("RESPONSE GUIDELINES", budget_block))

    # ── Assemble system prompt ────────────────────────────────────────────────
    system_prompt = assemble_sections(sections)

    return {
        "system_prompt": system_prompt,
        "max_tokens":    max_tokens,
    }


def assemble_sections(sections: list[tuple[str, str]]) -> str:
    """
    Join all sections with clear delimiters.
    Format: === SECTION TITLE ===\ncontent
    """
    parts = []
    for title, content in sections:
        parts.append(f"=== {title} ===\n{content.strip()}")
    return "\n\n".join(parts)


# ── Faithfulness checker ──────────────────────────────────────────────────────

async def check_faithfulness(
    response  : str,
    chunks    : list[dict],
) -> float:
    """
    Post-generation check: does the response stay grounded in retrieved chunks?
    Returns a score 0.0–1.0.
    Logs low scores for debugging.
    """
    if not chunks:
        return 1.0   # no chunks = no grounding check needed

    context = "\n".join([c["text"][:300] for c in chunks[:3]])

    prompt = f"""Rate how well this response is supported by the context passages below.
Score 0.0 (completely unsupported/hallucinated) to 1.0 (fully grounded in the passages).
Return ONLY a number like 0.85

Context:
{context}

Response:
{response[:500]}

Score:"""

    try:
        from app.llm.gateway import llm_gateway
        result = await llm_gateway.complete_fast(prompt, max_tokens=5)
        score = float(result.strip())
        score = max(0.0, min(1.0, score))

        if score < 0.6:
            print(f"[FAITHFULNESS] - Low score: {score:.2f} - response may be hallucinated")

        return score

    except Exception as e:
        print(f"[FAITHFULNESS] Check failed: {e}")
        return 1.0   # don't block on failure


# ── Response parser ───────────────────────────────────────────────────────────

def parse_response(raw: str) -> dict:
    """
    Extract emotion tag and clean response text from raw LLM output.

    Expected format: "[EMOTION_TAG] response text here..."

    Returns:
        {
            "emotion":   str,   ← e.g. "SKEPTICAL"
            "text":      str,   ← cleaned response without tag
        }
    """
    import re

    valid_emotions = {
        "EXCITED", "CONTEMPLATIVE", "AMUSED",
        "SKEPTICAL", "SAD", "NEUTRAL", "PASSIONATE"
    }

    raw = raw.strip()

    # Try to match tag at start
    pattern = r"^\[(" + "|".join(valid_emotions) + r")\]\s*"
    match   = re.match(pattern, raw)

    if match:
        emotion = match.group(1)
        text    = raw[match.end():].strip()
    else:
        emotion = "NEUTRAL"
        text    = raw

    return {"emotion": emotion, "text": text}
