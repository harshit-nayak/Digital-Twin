from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify() -> None:
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    for script in ("dev", "build", "preview"):
        _assert(script in package.get("scripts", {}), f"Missing npm script: {script}")

    required_files = [
        "index.html",
        "src/App.tsx",
        "src/main.tsx",
        "src/components/Classroom.tsx",
        "src/components/Sidebar.tsx",
        "src/services/chat.ts",
        "src/store/classroom.ts",
        "src/styles/app.css",
    ]
    for relative in required_files:
        path = FRONTEND / relative
        _assert(path.exists(), f"Missing frontend file: {relative}")
        _assert(path.read_text(encoding="utf-8").strip(), f"Empty frontend file: {relative}")

    chat_service = (FRONTEND / "src" / "services" / "chat.ts").read_text(encoding="utf-8")
    _assert("fetch(" in chat_service and "POST" in chat_service, "Chat service is not wired to POST")

    css = (FRONTEND / "src" / "styles" / "app.css").read_text(encoding="utf-8")
    _assert("@media (max-width: 760px)" in css, "Responsive mobile styles are missing")

    print("Frontend static verification passed: package, source files, chat service, responsive CSS.")


if __name__ == "__main__":
    verify()
