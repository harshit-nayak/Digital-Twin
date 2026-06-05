"""
backend/app/memory/compressor.py

Session compressor.
After a session ends, compress the full exchange history
into a ≤150 token summary stored in LTM.
Also handles LLM-based memory extraction for high-quality memory writing.
"""

import os
from dotenv import load_dotenv
import google.genai as genai

load_dotenv()


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


def compress_session(exchanges: list[dict]) -> str:
    """
    Compress a full session's exchanges into a ≤150 token summary.
    Called when a session ends.

    Args:
        exchanges: list of {"user": ..., "assistant": ...} dicts

    Returns:
        Compressed summary string
    """
    if not exchanges:
        return ""

    # Build conversation text (truncate each exchange to keep prompt small)
    convo_lines = []
    for ex in exchanges[-10:]:   # max last 10 exchanges
        convo_lines.append(f"Student: {ex['user'][:150]}")
        convo_lines.append(f"Scientist: {ex['assistant'][:200]}")

    convo_text = "\n".join(convo_lines)

    prompt = f"""Summarise this educational conversation in 2-3 sentences (under 100 words).
Focus on: topics covered, student's understanding level, analogies that worked, questions left open.
Be specific and factual. Return only the summary.

Conversation:
{convo_text}

Summary:"""

    try:
        response = client().models.generate_content(
            model    = "gemini-2.0-flash",
            contents = prompt,
            config   = genai.types.GenerateContentConfig(
                max_output_tokens = 150,
                temperature       = 0.2,
            ),
        )
        return response.text.strip()
    except Exception as e:
        print(f"[COMPRESSOR] Session compression failed: {e}")
        # Fallback: simple manual summary
        topics = set()
        for ex in exchanges:
            for word in ["relativity", "quantum", "gravity", "photoelectric",
                         "spacetime", "time dilation", "equivalence"]:
                if word in ex.get("user", "").lower() or word in ex.get("assistant", "").lower():
                    topics.add(word)
        return f"Session covered: {', '.join(topics) if topics else 'general physics'}. {len(exchanges)} exchanges."


def extract_memories_llm(
    user_message      : str,
    assistant_message : str,
    scientist_id      : str,
) -> list[dict]:
    """
    Use LLM to extract structured memories from a conversation exchange.
    More accurate than rule-based extraction in ltm.py.
    Called selectively (not every exchange) to save tokens.

    Returns list of {"type": ..., "content": ..., "importance": ...}
    """
    prompt = f"""Extract factual memories about the student from this exchange.
Return a JSON array. Each item: {{"type": "identity|goal|topic|episode|preference", "content": "...", "importance": 0.0-1.0}}
Only extract clear, explicit facts. Return [] if nothing worth storing.
Return ONLY the JSON array.

Student said: {user_message}
{scientist_id.title()} responded: {assistant_message[:300]}

JSON:"""

    try:
        response = client().models.generate_content(
            model    = "gemini-2.0-flash",
            contents = prompt,
            config   = genai.types.GenerateContentConfig(
                max_output_tokens = 200,
                temperature       = 0.1,
            ),
        )
        text = response.text.strip()

        # Strip markdown fences
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        import json
        memories = json.loads(text)

        if not isinstance(memories, list):
            return []

        # Validate structure
        valid = []
        for m in memories:
            if isinstance(m, dict) and "type" in m and "content" in m:
                valid.append({
                    "type":       m["type"],
                    "content":    str(m["content"])[:200],
                    "importance": float(m.get("importance", 0.6)),
                })
        return valid

    except Exception as e:
        print(f"[COMPRESSOR] Memory extraction failed: {e}")
        return []
