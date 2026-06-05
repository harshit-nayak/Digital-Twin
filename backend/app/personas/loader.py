"""
backend/app/personas/loader.py

Loads scientist YAML configuration files.
One config per scientist — used by context builder, teaching engine, etc.
"""

import yaml
from pathlib import Path
from functools import lru_cache

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "scientists"

_config_cache: dict = {}


def get_scientist_config(scientist_id: str) -> dict:
    """
    Load and cache a scientist's YAML config.
    Returns empty dict if config not found.
    """
    if scientist_id in _config_cache:
        return _config_cache[scientist_id]

    path = CONFIG_DIR / f"{scientist_id}.yaml"
    if not path.exists():
        print(f"[PERSONAS] Config not found: {path}")
        return {}

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    _config_cache[scientist_id] = config
    print(f"[PERSONAS] Loaded config for {scientist_id}")
    return config


def get_all_scientists() -> list[dict]:
    """
    List all configured scientists with their display metadata.
    Used by the Scientist Lobby endpoint.
    """
    scientists = []
    for yaml_path in CONFIG_DIR.glob("*.yaml"):
        sid    = yaml_path.stem
        config = get_scientist_config(sid)
        if config:
            scientists.append({
                "scientist_id" : sid,
                "name"         : config.get("name", sid.title()),
                "era"          : config.get("era", ""),
                "tagline"      : config.get("tagline", ""),
                "domain"       : config.get("domain", "Physics"),
                "avatar_url"   : config.get("avatar_url", ""),
                "timeline_milestones": [
                    {"year": m["year"], "label": m["label"]}
                    for m in config.get("timeline_milestones", [])
                ],
            })
    return scientists


def get_timeline_milestones(scientist_id: str) -> list[dict]:
    """Return the list of timeline milestones for a scientist."""
    config = get_scientist_config(scientist_id)
    return config.get("timeline_milestones", [])
