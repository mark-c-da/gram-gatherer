"""Shortcode -> library path index for duplicate detection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_index(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def lookup(index: dict[str, Any], shortcode: str) -> str | None:
    entry = index.get(shortcode)
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        path = entry.get("path")
        return path if isinstance(path, str) else None
    return None


def record(index: dict[str, Any], shortcode: str, rel_path: str, item_type: str) -> None:
    index[shortcode] = {"path": rel_path, "type": item_type}


def save_index(path: Path, index: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
