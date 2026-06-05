from __future__ import annotations

import ast
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def _add_backend_to_path() -> None:
    backend_path = str(BACKEND)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _ensure_seed_corpus() -> None:
    seeds = {
        "einstein/relativity.txt": "Light has a constant velocity in special relativity.",
        "newton/principia.txt": "Motion changes when force acts, and gravity draws bodies together.",
        "feynman/approved_source.txt": "A clear physics explanation starts from observation, experiment, and doubt.",
        "tesla/experiments.txt": "Alternating currents and high frequency electrical experiments reveal energy transfer.",
        "curie/radioactive_substances.txt": "Radioactive substances emit rays that can be measured and compared.",
    }
    for relative, text in seeds.items():
        path = ROOT / "data" / "corpus" / "raw" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(text, encoding="utf-8")


def _verify_syntax() -> None:
    for path in (BACKEND / "app").rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def verify() -> None:
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    _add_backend_to_path()
    _verify_syntax()
    _ensure_seed_corpus()

    from app.backend_graph import run_chat
    from app.context import build_context
    from app.memory.store import MemoryStore
    from app.rag.engine import retrieve
    from app.schemas import ChatRequest
    from app.scientists import list_scientists, load_scientist
    from app.simple_yaml import safe_load_file

    expected = {"curie", "einstein", "feynman", "newton", "tesla"}
    scientists = set(list_scientists())
    _assert(scientists == expected, f"Expected five scientists, got {sorted(scientists)}")
    _assert(load_scientist("einstein").display_name == "Albert Einstein", "Einstein config did not load")

    manifest = safe_load_file(ROOT / "data" / "manifests" / "public_domain_sources.yaml")
    _assert(set(manifest.get("sources", {})) == expected, "Manifest does not cover all scientists")

    for scientist in sorted(expected):
        results = retrieve("Explain motion, light, energy, radioactivity, and experiment", scientist)
        _assert(results, f"No retrieval results for {scientist}")

    store = MemoryStore(str(ROOT / "verify_tmp" / "memory.db"))
    memory_id = store.save("verify-session", "topic", "Student likes relativity and clocks", 0.8)
    _assert(memory_id > 0, "Memory save failed")
    _assert(store.retrieve("clocks relativity", "verify-session"), "Memory retrieve failed")

    context = build_context("Explain physics of light and motion", "einstein", "1905", "verify-session")
    _assert("Albert Einstein" in context.system, "Context is missing scientist persona")
    _assert(context.sources, "Context is missing retrieval sources")

    response = run_chat(
        ChatRequest(
            session_id="verify-session",
            scientist="einstein",
            message="Explain physics of light and motion",
            timeline="1905",
        )
    )
    _assert(response.scientist == "einstein", "Chat returned the wrong scientist")
    _assert(bool(response.message), "Chat returned an empty message")
    _assert(bool(response.memory_updates), "Chat did not report a memory update")

    print("Backend verification passed: syntax, configs, manifest, retrieval, memory, context, chat.")


if __name__ == "__main__":
    verify()
