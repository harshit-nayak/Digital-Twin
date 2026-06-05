from dataclasses import dataclass
from time import monotonic
from typing import Protocol

from app.config import get_settings


@dataclass
class GenerationRequest:
    prompt: str
    system: str = ""
    temperature: float = 0.4
    max_tokens: int = 800


class Provider(Protocol):
    name: str

    def generate(self, request: GenerationRequest) -> str:
        ...


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate(self, request: GenerationRequest) -> str:
        from google import genai

        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.model,
            contents=f"{request.system}\n\n{request.prompt}".strip(),
        )
        return response.text or ""


class LocalFallbackProvider:
    name = "local_fallback"

    def generate(self, request: GenerationRequest) -> str:
        lines = [line.strip() for line in request.prompt.splitlines() if line.strip()]
        question = next((line for line in lines if line.startswith("Student:")), "Student: your question")
        evidence = [line for line in lines if line.startswith("Source ")]
        if evidence:
            return (
                "Let us reason from the material we have. "
                f"{question.removeprefix('Student:').strip()} connects to this evidence: "
                f"{evidence[0][:260]}. "
                "A full Gemini response will replace this local draft once GEMINI_API_KEYS is configured."
            )
        return (
            "I can answer in character once the corpus and Gemini key are configured. "
            "For now, the system is wired and ready for grounded retrieval."
        )


class LLMGateway:
    def __init__(self) -> None:
        settings = get_settings()
        self.providers: list[Provider] = [
            GeminiProvider(key, settings.gemini_model) for key in settings.gemini_keys
        ] or [LocalFallbackProvider()]
        self.cooldowns: dict[str, float] = {}
        self.index = 0

    def generate(self, request: GenerationRequest) -> str:
        errors: list[str] = []
        for _ in range(len(self.providers)):
            provider = self.providers[self.index % len(self.providers)]
            self.index += 1
            cooldown_until = self.cooldowns.get(provider.name, 0)
            if cooldown_until > monotonic():
                continue
            try:
                return provider.generate(request)
            except Exception as exc:
                self.cooldowns[provider.name] = monotonic() + 30
                errors.append(f"{provider.name}: {exc}")
        return LocalFallbackProvider().generate(request) + f" Provider errors: {'; '.join(errors)}"


gateway = LLMGateway()

