"""
backend/app/memory/stm.py

Short-Term Memory (STM) and Working Memory.

STM:     Last 6-8 exchanges from the current session.
         Stored in LangGraph state — no database needed.
         Windowed — oldest messages drop as conversation grows.

Working Memory (Scratchpad):
         Per-session reasoning state the system builds up.
         Tracks: conversation trajectory, established facts,
         active analogy, depth level.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional

# ── Constants ─────────────────────────────────────────────────────────────────

STM_MAX_EXCHANGES = 8     # max number of exchanges to keep in window
STM_MAX_CHARS     = 3000  # hard char limit on STM to control token usage


# ── STM Management ────────────────────────────────────────────────────────────

def add_to_stm(
    stm_window    : list[dict],
    user_message  : str,
    ai_response   : str,
) -> list[dict]:
    """
    Add a new exchange to the STM window.
    Drops oldest exchange if window exceeds STM_MAX_EXCHANGES.
    Returns updated window.
    """
    exchange = {
        "user":      user_message,
        "assistant": ai_response,
    }
    stm_window = stm_window + [exchange]

    # Keep only the last N exchanges
    if len(stm_window) > STM_MAX_EXCHANGES:
        stm_window = stm_window[-STM_MAX_EXCHANGES:]

    return stm_window


def format_stm_for_prompt(stm_window: list[dict]) -> str:
    """
    Format STM window into a conversation history string for prompt injection.
    Truncates if total chars exceed limit.
    """
    if not stm_window:
        return ""

    lines  = []
    total  = 0

    # Process in reverse so we keep the most recent exchanges
    for exchange in reversed(stm_window):
        user_line = f"Student: {exchange['user']}"
        ai_line   = f"Einstein: {exchange['assistant'][:300]}"  # truncate long responses
        block     = f"{user_line}\n{ai_line}"

        if total + len(block) > STM_MAX_CHARS:
            break

        lines.insert(0, block)
        total += len(block)

    return "\n\n".join(lines)


def clear_stm() -> list:
    """Return empty STM window. Call at session start."""
    return []


# ── Working Memory (Scratchpad) ───────────────────────────────────────────────

@dataclass
class WorkingMemory:
    """
    Per-session reasoning state.
    Updated after each exchange to help the model track
    where the conversation is going.
    """
    trajectory       : str        = ""
    # e.g. "User building toward GR — asked SR twice already"

    established_facts: list[str]  = field(default_factory=list)
    # Facts the user has confirmed understanding of

    active_analogy   : str        = ""
    # Which analogy is currently in use, e.g. "the train"

    depth_level      : int        = 1
    # 1=intro, 2=intermediate, 3=advanced
    # Increases as user demonstrates understanding

    topics_this_session: list[str] = field(default_factory=list)
    # Topics covered in this session

    exchange_count   : int        = 0
    # How many exchanges have happened

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "WorkingMemory":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def format_for_prompt(self) -> str:
        """Format working memory as a compact prompt block."""
        if not any([self.trajectory, self.established_facts,
                    self.active_analogy, self.topics_this_session]):
            return ""

        parts = []

        if self.trajectory:
            parts.append(f"Conversation trajectory: {self.trajectory}")

        if self.topics_this_session:
            parts.append(f"Topics covered this session: {', '.join(self.topics_this_session)}")

        if self.active_analogy:
            parts.append(f"Active analogy in use: {self.active_analogy}")

        if self.established_facts:
            facts = "; ".join(self.established_facts[-3:])  # last 3 only
            parts.append(f"Student has grasped: {facts}")

        parts.append(f"Student depth level: {self.depth_level}/3")

        return "\n".join(parts)


def update_working_memory(
    wm            : WorkingMemory,
    user_message  : str,
    ai_response   : str,
    emotion_tag   : str = "",
) -> WorkingMemory:
    """
    Update working memory after each exchange.
    Simple heuristic updates — no LLM call needed.
    """
    wm.exchange_count += 1

    # Track depth — increase if user asks follow-up questions
    follow_up_signals = ["why", "how exactly", "can you explain more",
                         "go deeper", "what about", "but then"]
    if any(s in user_message.lower() for s in follow_up_signals):
        wm.depth_level = min(wm.depth_level + 1, 3)

    # Track active analogy
    analogies = {
        "train":     ["train", "lightning", "embankment", "platform"],
        "elevator":  ["elevator", "lift", "accelerating box"],
        "twin":      ["twin", "rocket", "traveling brother"],
        "light beam":["ride a beam", "light beam", "alongside light"],
    }
    for analogy_name, keywords in analogies.items():
        if any(k in ai_response.lower() for k in keywords):
            wm.active_analogy = analogy_name
            break

    # Track topics
    physics_topics = [
        "special relativity", "general relativity", "photoelectric",
        "quantum mechanics", "time dilation", "equivalence principle",
        "e=mc", "mass energy", "spacetime", "gravity", "light speed"
    ]
    combined = (user_message + " " + ai_response).lower()
    for topic in physics_topics:
        if topic in combined and topic not in wm.topics_this_session:
            wm.topics_this_session.append(topic)

    # Update trajectory heuristically
    if wm.exchange_count == 1:
        wm.trajectory = f"Session started with: {user_message[:60]}"
    elif wm.exchange_count >= 3 and wm.topics_this_session:
        wm.trajectory = f"Exploring {', '.join(wm.topics_this_session[-2:])}; depth level {wm.depth_level}"

    return wm


def new_working_memory() -> WorkingMemory:
    """Create fresh working memory for a new session."""
    return WorkingMemory()
