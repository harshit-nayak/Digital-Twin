"""
backend/app/memory/working_memory.py

Working Memory (Scratchpad) — per-session reasoning state.

This is injected into the Context Builder and makes multi-turn
conversations dramatically more coherent. The LLM can reference
what trajectory the student is on, what analogies have worked,
and how deep the conversation has gone.

Working memory is ephemeral — lives only for the session.
It is rebuilt from each exchange, not persisted to SQLite.
"""

from dataclasses import dataclass, field


@dataclass
class WorkingMemory:
    """
    Per-session scratchpad.
    Updated after every exchange, injected into every prompt.
    """

    # Running description of where the student is heading
    # e.g. "Student is building toward General Relativity, asked SR twice"
    trajectory: str = ""

    # Physics concepts the student has confirmed they understand
    # e.g. ["time dilation", "reference frames", "photoelectric effect"]
    established_facts: list[str] = field(default_factory=list)

    # Which analogy is currently active in the conversation
    # e.g. "the train and the lightning bolt"
    active_analogy: str = ""

    # How deep the conversation has gone:
    # 1 = introductory, 2 = intermediate, 3 = advanced
    depth_level: int = 1

    # Raw exchange count (increments each turn)
    exchange_count: int = 0

    def format_for_prompt(self) -> str:
        """
        Format working memory for injection into the system prompt.
        Returns empty string if nothing meaningful to inject.
        """
        if self.exchange_count == 0:
            return ""

        lines = []

        if self.trajectory:
            lines.append(f"Learning trajectory: {self.trajectory}")

        if self.established_facts:
            facts = ", ".join(self.established_facts[-5:])  # last 5 only
            lines.append(f"Topics student understands: {facts}")

        if self.active_analogy:
            lines.append(f"Active analogy in use: \"{self.active_analogy}\"")

        depth_labels = {1: "introductory", 2: "intermediate", 3: "advanced"}
        lines.append(f"Conversation depth: {depth_labels.get(self.depth_level, 'intermediate')}")
        lines.append(f"Exchange #{self.exchange_count}")

        return "\n".join(lines)

    def update_from_exchange(
        self,
        user_message      : str,
        assistant_message : str,
    ):
        """
        Update working memory after each exchange.
        Simple heuristic — no LLM call to keep it free and fast.
        """
        self.exchange_count += 1
        user_lower = user_message.lower()

        # ── Track depth level ─────────────────────────────────────────────
        advanced_signals = [
            "derive", "proof", "tensor", "curvature", "manifold",
            "equations of motion", "field equations", "four-vector",
            "lorentz transformation", "geodesic", "invariant"
        ]
        intermediate_signals = [
            "formula", "equation", "calculate", "how exactly", "mathematically",
            "quantitatively", "derive", "formally", "rigorously"
        ]

        if any(s in user_lower for s in advanced_signals):
            self.depth_level = min(3, self.depth_level + 1)
        elif any(s in user_lower for s in intermediate_signals):
            self.depth_level = min(2, max(self.depth_level, 2))

        # ── Track established facts ───────────────────────────────────────
        understanding_signals = [
            "i understand", "that makes sense", "i see", "got it",
            "so basically", "ah i see", "oh so", "now i understand"
        ]
        physics_concepts = [
            "time dilation", "length contraction", "mass-energy", "photoelectric",
            "quantum", "relativity", "gravity", "spacetime", "light speed",
            "uncertainty", "wave-particle", "equivalence principle"
        ]
        if any(sig in user_lower for sig in understanding_signals):
            for concept in physics_concepts:
                if concept in user_lower or concept in assistant_message.lower():
                    if concept not in self.established_facts:
                        self.established_facts.append(concept)

        # ── Track active analogy ──────────────────────────────────────────
        analogy_markers = {
            "train":     "the train and the lightning bolt",
            "elevator":  "the elevator thought experiment",
            "clock":     "the light clock",
            "twins":     "the twin paradox",
            "rubber":    "the rubber sheet analogy for spacetime",
            "cannonball": "Newton's cannonball",
        }
        assist_lower = assistant_message.lower()
        for keyword, analogy_name in analogy_markers.items():
            if keyword in assist_lower:
                self.active_analogy = analogy_name
                break

        # ── Update trajectory heuristic ───────────────────────────────────
        trajectory_map = [
            (["general relativity", "gravity", "curved spacetime", "geodesic"], "building toward General Relativity"),
            (["quantum", "bohr", "uncertainty", "wave function"], "exploring Quantum Mechanics territory"),
            (["photoelectric", "light quanta", "photon"], "studying the photoelectric effect and light quanta"),
            (["special relativity", "simultaneity", "time dilation", "length"], "working through Special Relativity"),
            (["unified field", "grand theory", "everything"], "asking about the unified field theory"),
        ]
        for keywords, label in trajectory_map:
            if any(kw in user_lower or kw in assist_lower for kw in keywords):
                self.trajectory = label
                break

    def to_dict(self) -> dict:
        """Serialize to dict for LangGraph state."""
        return {
            "trajectory":        self.trajectory,
            "established_facts": self.established_facts,
            "active_analogy":    self.active_analogy,
            "depth_level":       self.depth_level,
            "exchange_count":    self.exchange_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkingMemory":
        """Restore from LangGraph state dict."""
        wm = cls()
        wm.trajectory        = data.get("trajectory", "")
        wm.established_facts = data.get("established_facts", [])
        wm.active_analogy    = data.get("active_analogy", "")
        wm.depth_level       = data.get("depth_level", 1)
        wm.exchange_count    = data.get("exchange_count", 0)
        return wm
