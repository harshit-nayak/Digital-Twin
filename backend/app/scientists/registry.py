from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from app.simple_yaml import safe_load_file


class Persona(BaseModel):
    era: str
    voice: str
    principles: list[str] = Field(default_factory=list)


class TimelineMilestone(BaseModel):
    id: str
    label: str
    start: int
    end: int
    focus: str


class CorpusConfig(BaseModel):
    paths: list[str]
    manifest_ids: list[str] = Field(default_factory=list)


class TeachingStrategy(BaseModel):
    style: str
    moves: list[str] = Field(default_factory=list)


class VoiceConfig(BaseModel):
    accent: str
    pace: str


class ScientistConfig(BaseModel):
    id: str
    display_name: str
    persona: Persona
    timelines: list[TimelineMilestone]
    corpus: CorpusConfig
    teaching_strategy: TeachingStrategy
    voice: VoiceConfig
    sprites: dict[str, str] = Field(default_factory=dict)


def _scientist_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "scientists"


def list_scientists() -> list[str]:
    return sorted(path.stem for path in _scientist_dir().glob("*.yaml"))


@lru_cache
def load_scientist(scientist_id: str) -> ScientistConfig:
    normalized = scientist_id.lower().strip()
    path = _scientist_dir() / f"{normalized}.yaml"
    if not path.exists():
        available = ", ".join(list_scientists())
        raise ValueError(f"Unknown scientist '{scientist_id}'. Available: {available}")

    data = safe_load_file(path)
    try:
        config = ScientistConfig.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"Invalid scientist config at {path}: {exc}") from exc

    if config.id != normalized:
        raise ValueError(f"Scientist id mismatch in {path}: expected {normalized}, got {config.id}")
    return config
