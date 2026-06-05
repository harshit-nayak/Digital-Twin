"""
backend/app/context/persona.py

Persona Engine.
Loads the scientist's persona prompt, domain keywords,
and domain boundary handling from YAML config.
"""

from pathlib import Path
import yaml

BASE_DIR   = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "config" / "scientists"


def load_config(scientist_id: str) -> dict:
    path = CONFIG_DIR / f"{scientist_id}.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_persona_prompt(scientist_id: str) -> str:
    """Returns the core persona prompt from the scientist's YAML config."""
    config = load_config(scientist_id)
    return config.get("persona_prompt", "").strip()


def get_domain_keywords(scientist_id: str) -> list[str]:
    """Returns the list of in-domain keywords for boundary checking."""
    config = load_config(scientist_id)
    return config.get("domain_keywords", [])


def is_in_domain(query: str, scientist_id: str) -> bool:
    """
    Quick domain boundary check.
    Returns True if the query appears to be within the scientist's domain.

    Uses keyword matching + a small set of out-of-domain signals.
    The LangGraph domain_check_node uses this before spending any tokens.
    """
    query_lower = query.lower()

    # Explicit out-of-domain signals
    out_of_domain = [
        "recipe", "cooking", "food", "sport", "football", "cricket",
        "movie", "film", "music", "song", "politics", "election",
        "stock", "investment", "finance", "history of rome",
        "french revolution", "world war", "geography",
    ]
    for signal in out_of_domain:
        if signal in query_lower:
            return False

    # Check against domain keywords
    domain_keywords = get_domain_keywords(scientist_id)
    for kw in domain_keywords:
        if kw.lower() in query_lower:
            return True

    # General physics/science signals that are always in domain
    general_science = [
        "how", "why", "what", "explain", "tell me", "describe",
        "teach", "understand", "learn", "think", "believe",
        "equation", "theory", "experiment", "prove", "derive",
    ]
    for signal in general_science:
        if signal in query_lower:
            return True

    # Default: allow — better to be permissive and let persona handle edge cases
    return True


def get_domain_refusal(scientist_id: str, query: str) -> str:
    """
    Returns an in-character domain refusal response.
    Used when is_in_domain() returns False.
    """
    refusals = {
        "einstein": (
            "[AMUSED] I am afraid this falls rather outside my province. "
            "My mind lives in equations, physical pictures, and the structure of spacetime. "
            "For what you are asking, I would recommend someone whose thought experiments "
            "involve rather different subject matter than trains and light beams."
        ),
        "newton": (
            "[NEUTRAL] This matter lies beyond the scope of natural philosophy as I have "
            "pursued it. My inquiries concern the mathematical principles governing "
            "motion, light, and gravitation. I cannot speak with authority on this."
        ),
        "feynman": (
            "[AMUSED] Ha — you're asking the wrong guy. I know a lot about "
            "how the universe works at the quantum level, but this? "
            "Way outside my lane. Ask someone who actually knows."
        ),
    }
    return refusals.get(
        scientist_id,
        "[NEUTRAL] I am afraid this question falls outside my area of knowledge. "
        "I would rather acknowledge my limits than mislead you."
    )
