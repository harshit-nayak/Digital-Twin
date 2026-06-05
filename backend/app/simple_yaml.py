import json
from pathlib import Path
from typing import Any


def _scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith("[") or value.startswith("{"):
        return json.loads(value)
    if value.isdigit():
        return int(value)
    return value.strip('"').strip("'")


def _parse_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index

    is_list = lines[index][1].startswith("- ")
    if is_list:
        items: list[Any] = []
        while index < len(lines) and lines[index][0] == indent and lines[index][1].startswith("- "):
            text = lines[index][1][2:].strip()
            if not text:
                value, index = _parse_block(lines, index + 1, indent + 2)
                items.append(value)
                continue
            if ":" in text:
                key, raw = text.split(":", 1)
                item: dict[str, Any] = {key.strip(): _scalar(raw)}
                index += 1
                while index < len(lines) and lines[index][0] > indent:
                    child_indent, child_text = lines[index]
                    if child_indent == indent + 2 and ":" in child_text:
                        child_key, child_raw = child_text.split(":", 1)
                        if child_raw.strip():
                            item[child_key.strip()] = _scalar(child_raw)
                            index += 1
                        else:
                            item[child_key.strip()], index = _parse_block(lines, index + 1, child_indent + 2)
                    else:
                        break
                items.append(item)
            else:
                items.append(_scalar(text))
                index += 1
        return items, index

    mapping: dict[str, Any] = {}
    while index < len(lines) and lines[index][0] == indent and not lines[index][1].startswith("- "):
        text = lines[index][1]
        key, raw = text.split(":", 1)
        if raw.strip():
            mapping[key.strip()] = _scalar(raw)
            index += 1
        else:
            mapping[key.strip()], index = _parse_block(lines, index + 1, indent + 2)
    return mapping, index


def safe_load(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        return {}
    if stripped.startswith("{") or stripped.startswith("["):
        return json.loads(stripped)

    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, raw.strip()))
    value, _ = _parse_block(lines, 0, lines[0][0] if lines else 0)
    return value


def safe_load_file(path: Path) -> Any:
    return safe_load(path.read_text(encoding="utf-8"))

