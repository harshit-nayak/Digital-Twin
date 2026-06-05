from dataclasses import dataclass
from functools import lru_cache
from math import sqrt
from pathlib import Path
import re


from app.config import get_settings
from app.scientists import load_scientist
from app.simple_yaml import safe_load_file


@dataclass
class RetrievalResult:
    id: str
    title: str
    scientist: str
    score: float
    excerpt: str
    timeline_start: int | None = None
    timeline_end: int | None = None


@dataclass
class Chunk:
    id: str
    title: str
    scientist: str
    text: str
    timeline_start: int | None
    timeline_end: int | None


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z0-9']+", text.lower())


def _chunk_text(text: str, size: int = 900, overlap: int = 140) -> list[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(start + size, len(clean))
        chunks.append(clean[start:end].strip())
        if end == len(clean):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    shared = set(a) & set(b)
    numerator = sum(a[token] * b[token] for token in shared)
    left = sqrt(sum(value * value for value in a.values()))
    right = sqrt(sum(value * value for value in b.values()))
    return numerator / (left * right) if left and right else 0.0


def _vectorize(tokens: list[str]) -> dict[str, float]:
    vector: dict[str, float] = {}
    for token in tokens:
        vector[token] = vector.get(token, 0.0) + 1.0
    return vector


def _parse_timeline(timeline: str | None) -> tuple[int | None, int | None]:
    if not timeline:
        return None, None
    years = [int(match) for match in re.findall(r"\d{4}", timeline)]
    if len(years) >= 2:
        return min(years), max(years)
    if len(years) == 1:
        return years[0], years[0]
    return None, None


def _timeline_matches(chunk: Chunk, timeline: str | None) -> bool:
    start, end = _parse_timeline(timeline)
    if start is None or chunk.timeline_start is None or chunk.timeline_end is None:
        return True
    return chunk.timeline_start <= end and chunk.timeline_end >= start


@lru_cache
def _manifest() -> dict:
    settings = get_settings()
    path = settings.resolve(settings.corpus_manifest)
    if not path.exists():
        return {"sources": {}}
    return safe_load_file(path) or {"sources": {}}


@lru_cache
def _chunks_for(scientist_id: str) -> tuple[Chunk, ...]:
    settings = get_settings()
    scientist = load_scientist(scientist_id)
    manifest_sources = {
        source["id"]: source
        for source in _manifest().get("sources", {}).get(scientist.id, [])
    }
    chunks: list[Chunk] = []

    for corpus_path in scientist.corpus.paths:
        path = settings.resolve(corpus_path)
        if not path.exists():
            continue
        source = next(
            (
                item
                for item in manifest_sources.values()
                if settings.resolve(item.get("local_path", "")) == path
            ),
            {},
        )
        title = source.get("title", path.stem)
        raw = path.read_text(encoding="utf-8", errors="ignore")
        for index, text in enumerate(_chunk_text(raw)):
            chunks.append(
                Chunk(
                    id=f"{scientist.id}:{path.stem}:{index}",
                    title=title,
                    scientist=scientist.id,
                    text=text,
                    timeline_start=source.get("timeline_start"),
                    timeline_end=source.get("timeline_end"),
                )
            )
    return tuple(chunks)


def retrieve(query: str, scientist: str, timeline: str | None = None, top_k: int = 5) -> list[RetrievalResult]:
    query_tokens = _tokens(query)
    query_vector = _vectorize(query_tokens)
    candidates = [chunk for chunk in _chunks_for(scientist) if _timeline_matches(chunk, timeline)]

    scored: list[RetrievalResult] = []
    for chunk in candidates:
        chunk_tokens = _tokens(chunk.text)
        dense_score = _cosine(query_vector, _vectorize(chunk_tokens))
        bm25_like = sum(1 for token in set(query_tokens) if token in set(chunk_tokens)) / max(len(set(query_tokens)), 1)
        score = (0.65 * dense_score) + (0.35 * bm25_like)
        if score <= 0:
            continue
        scored.append(
            RetrievalResult(
                id=chunk.id,
                title=chunk.title,
                scientist=chunk.scientist,
                score=round(score, 4),
                excerpt=chunk.text[:520],
                timeline_start=chunk.timeline_start,
                timeline_end=chunk.timeline_end,
            )
        )

    return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]
