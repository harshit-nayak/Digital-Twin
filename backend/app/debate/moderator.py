from dataclasses import dataclass

from app.context import build_context
from app.llm import GenerationRequest, gateway


@dataclass
class DebateTurn:
    scientist: str
    message: str
    sources: list


def run_debate_turn(topic: str, scientist: str, opponent_claim: str, session_id: str = "debate") -> DebateTurn:
    context = build_context(topic, scientist, None, session_id)
    prompt = (
        f"Debate topic: {topic}\n"
        f"Opponent claim: {opponent_claim}\n"
        "Respond with one grounded rebuttal, one concession if appropriate, and one teaching takeaway."
    )
    message = gateway.generate(GenerationRequest(system=context.system, prompt=f"{context.prompt}\n{prompt}"))
    return DebateTurn(scientist=scientist, message=message, sources=context.sources)

