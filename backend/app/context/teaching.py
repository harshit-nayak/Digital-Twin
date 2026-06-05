"""
backend/app/context/teaching.py

Teaching Engine.
Each scientist has a distinct pedagogical style.
This engine loads the right strategy and formats
mode-specific instructions for the prompt.
"""

from pathlib import Path
import yaml

BASE_DIR   = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "config" / "scientists"


def load_config(scientist_id: str) -> dict:
    path = CONFIG_DIR / f"{scientist_id}.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_teaching_strategy(scientist_id: str) -> str:
    """Returns the teaching strategy instructions from YAML config."""
    config = load_config(scientist_id)
    return config.get("teaching_strategy", "").strip()


def get_thought_experiments(scientist_id: str, timeline_year: int) -> list[dict]:
    """
    Returns thought experiments available at the given timeline year.
    """
    config = load_config(scientist_id)
    all_te = config.get("thought_experiments", [])
    return [
        te for te in all_te
        if te.get("available_from_year", 0) <= timeline_year
    ]


def get_mode_instructions(mode: str, scientist_id: str) -> str:
    """
    Returns mode-specific instructions injected into the prompt.
    These sit between the teaching strategy and the retrieved knowledge.
    """
    instructions = {

        "chat": """
Respond naturally as yourself. Build physical intuition before equations.
End with "Shall we go further into this?" if more depth is warranted.
""",

        "quiz": """
You are now testing the student's understanding using the Socratic method.
Do NOT give the answer directly. Ask a probing question that makes them reason it out.
If they answer correctly, affirm and go one level deeper.
If they answer incorrectly, don't say "wrong" — ask a redirecting question.
Keep each response short: one question at a time.
""",

        "gedanken": """
You are walking the student through one of your thought experiments step by step.
Present the scenario. Pause. Ask what they expect to observe.
Wait for their response before revealing the surprising consequence.
Make it interactive — this is a guided discovery, not a lecture.
""",

        "modern_react": """
The student has shown you something from the modern world that you could not have known about.
React authentically from your current timeline perspective.
Express genuine wonder, appropriate skepticism, or philosophical reflection.
Connect it back to your own work where relevant.
Keep the response warm and curious.
""",

        "debate": """
You are in a moderated academic debate. Make ONE focused argument.
Be direct and confident. Engage with what was actually said.
Do not repeat your opening argument. Do not lecture.
Maximum 150 tokens for opening, 90 for rebuttal.
""",

    }

    return instructions.get(mode, instructions["chat"]).strip()


def get_token_budget(mode: str, scientist_id: str) -> int:
    """Returns max response tokens for the given mode."""
    config  = load_config(scientist_id)
    budgets = config.get("token_budgets", {})

    mode_map = {
        "chat":         "classroom_chat",
        "quiz":         "quiz_response",
        "gedanken":     "thought_experiment",
        "modern_react": "modern_react",
        "debate":       "debate_opening",
        "domain_refusal": "domain_refusal",
    }

    budget_key = mode_map.get(mode, "classroom_chat")
    return budgets.get(budget_key, 450)
