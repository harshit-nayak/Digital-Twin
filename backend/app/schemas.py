from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(default="default")
    scientist: str = Field(default="einstein")
    message: str
    timeline: str | None = None
    ui: dict[str, Any] = Field(default_factory=dict)


class Source(BaseModel):
    id: str
    title: str
    scientist: str
    score: float
    timeline_start: int | None = None
    timeline_end: int | None = None
    excerpt: str


class ChatResponse(BaseModel):
    message: str
    scientist: str
    sources: list[Source] = Field(default_factory=list)
    timeline_context: str | None = None
    emotion: str = "thoughtful"
    memory_updates: list[str] = Field(default_factory=list)
    trace: dict[str, Any] | None = None

