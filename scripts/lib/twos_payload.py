"""Build Twos-shaped payloads for Cursor MCP write-back (no REST calls).

After gather saves library files, the agent can pass these objects to Twos MCP
tools (`create_list`, `create_thing` / `create_things`) using the user's MCP
connection — the same data the REST Workflow 1 would POST.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path


def default_output_title(source_title: str | None = None) -> str:
    day = date.today().isoformat()
    if source_title:
        return f"Gathered from {source_title} — {day}"
    return f"Gathered {day}"


def library_body_without_frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].lstrip("\n")
    return text


def title_from_library(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def thing_payload(
    *,
    title: str,
    item_type: str,
    instagram_url: str,
    library_path: Path | None = None,
) -> dict:
    note = None
    if library_path and library_path.exists():
        body = library_body_without_frontmatter(library_path).strip()
        note = body or None
    return {
        "text": f"{item_type}: {title}".strip(": "),
        "type": "note",
        "url": instagram_url,
        "note": note,
        "tags": [item_type] if item_type else [],
    }


def batch_writeback_payload(
    *,
    results: list[dict],
    root: Path,
    source_list_title: str | None = None,
    output_list_title: str | None = None,
) -> dict:
    """MCP handoff document: create one list, then one thing per saved result."""
    title = (output_list_title or "").strip() or default_output_title(source_list_title)
    things: list[dict] = []
    for entry in results:
        if entry.get("status") != "saved":
            continue
        rel = entry.get("path")
        lib = (root / rel) if rel else None
        heading = title_from_library(lib) if lib and lib.exists() else (entry.get("shortcode") or "item")
        things.append(
            thing_payload(
                title=heading,
                item_type=entry.get("type") or entry.get("item_type") or "other",
                instagram_url=entry.get("url") or "",
                library_path=lib if lib and lib.exists() else None,
            )
        )
    return {
        "mode": "twos_mcp_writeback",
        "create_list": {
            "title": title,
            "emoji": "📥",
        },
        "things": things,
        "mcp_hints": {
            "create_list_tool": "create_list",
            "create_thing_tool": "create_thing",
            "create_things_tool": "create_things",
            "note": (
                "Call Twos MCP create_list with create_list fields, then create_thing "
                "(or create_things) for each entry in things, targeting the new list id/name."
            ),
        },
    }
