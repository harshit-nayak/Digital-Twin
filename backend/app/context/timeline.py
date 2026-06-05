"""
backend/app/context/timeline.py

Timeline Engine.
Loads the correct historical context block for the selected milestone year.
Also handles timeline-aware belief calibration.
"""

from pathlib import Path
import yaml

BASE_DIR   = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "config" / "scientists"


def load_config(scientist_id: str) -> dict:
    path = CONFIG_DIR / f"{scientist_id}.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_timeline_context(scientist_id: str, timeline_year: int) -> str:
    """
    Returns the context block for the milestone year closest to
    (but not exceeding) the selected timeline_year.

    e.g. timeline_year=1930 → returns the 1927 block (closest ≤ 1930)
    """
    config     = load_config(scientist_id)
    milestones = config.get("timeline_milestones", [])

    if not milestones:
        return ""

    # Find the best matching milestone (largest year ≤ timeline_year)
    valid = [m for m in milestones if m["year"] <= timeline_year]

    if not valid:
        # If timeline_year is before all milestones, use the earliest
        valid = [min(milestones, key=lambda m: m["year"])]

    best = max(valid, key=lambda m: m["year"])

    label   = best.get("label", str(best["year"]))
    context = best.get("context", "").strip()

    print(f"[TIMELINE] {scientist_id} @ {timeline_year} -> milestone '{label}' ({best['year']})")

    return context


def get_milestone_label(scientist_id: str, timeline_year: int) -> str:
    """Returns the label for the active milestone. Used in UI display."""
    config     = load_config(scientist_id)
    milestones = config.get("timeline_milestones", [])
    valid      = [m for m in milestones if m["year"] <= timeline_year]
    if not valid:
        return str(timeline_year)
    best = max(valid, key=lambda m: m["year"])
    return best.get("label", str(best["year"]))


def get_all_milestones(scientist_id: str) -> list[dict]:
    """Returns all milestone stops for the timeline slider UI."""
    config = load_config(scientist_id)
    return [
        {"year": m["year"], "label": m.get("label", str(m["year"]))}
        for m in config.get("timeline_milestones", [])
    ]
