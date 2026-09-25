"""Push a saved gather result back into a Twos list as text (not a .txt file).

Creates one thing per saved item: title line + Instagram url + long-form note
holding the library markdown body. Re-runs can skip by Instagram url when the
caller uses skip_duplicates on markdown append, or we attach url on create_thing.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from lib.twos_client import TwosClient, TwosList


def default_output_title(source_title: str | None = None) -> str:
    day = date.today().isoformat()
    if source_title:
        return f"Gathered from {source_title} — {day}"
    return f"Gathered {day}"


def ensure_output_list(
    client: TwosClient,
    *,
    title: str | None = None,
    source_title: str | None = None,
    emoji: str = "📥",
) -> TwosList:
    name = (title or "").strip() or default_output_title(source_title)
    return client.create_list(name, emoji=emoji)


def markdown_for_twos(
    *,
    title: str,
    item_type: str,
    instagram_url: str,
    library_path: str | None,
    body_markdown: str,
) -> str:
    """Compact markdown block that Twos can parse into things via append_markdown."""
    lines = [
        f"## {title}",
        "",
        f"- type: {item_type}",
        f"- source: {instagram_url}",
    ]
    if library_path:
        lines.append(f"- library: `{library_path}`")
    lines.extend(["", body_markdown.strip(), ""])
    return "\n".join(lines)


def library_body_without_frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].lstrip("\n")
    return text


def push_saved_item(
    client: TwosClient,
    *,
    list_id: str,
    title: str,
    item_type: str,
    instagram_url: str,
    library_path: Path | None,
    root: Path | None = None,
) -> dict:
    """Create one Twos thing for a saved gather result."""
    body = ""
    if library_path and library_path.exists():
        body = library_body_without_frontmatter(library_path)
    note = body.strip() or None
    text = f"{item_type}: {title}".strip(": ")
    return client.create_thing(
        list_id=list_id,
        text=text,
        type="note",
        url=instagram_url,
        note=note,
        tags=[item_type] if item_type else None,
    )


def push_saved_markdown(
    client: TwosClient,
    *,
    list_id: str,
    title: str,
    item_type: str,
    instagram_url: str,
    library_rel: str | None,
    body_markdown: str,
) -> dict:
    """Append a markdown block (header + link + body) to the destination list."""
    md = markdown_for_twos(
        title=title,
        item_type=item_type,
        instagram_url=instagram_url,
        library_path=library_rel,
        body_markdown=body_markdown,
    )
    return client.append_markdown(md, list_id=list_id, skip_duplicates=True)
