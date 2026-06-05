from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path


@dataclass
class Settings:
    gemini_api_keys: str = os.getenv("GEMINI_API_KEYS", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    backend_debug: bool = os.getenv("BACKEND_DEBUG", "false").lower() == "true"
    memory_db_path: str = os.getenv("MEMORY_DB_PATH", "data/memory/digital_twin.db")
    chroma_path: str = os.getenv("CHROMA_PATH", "data/chroma")
    corpus_manifest: str = os.getenv("CORPUS_MANIFEST", "data/manifests/public_domain_sources.yaml")

    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def resolve(self, path: str) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else self.repo_root / candidate

    @property
    def gemini_keys(self) -> list[str]:
        return [key.strip() for key in self.gemini_api_keys.split(",") if key.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
