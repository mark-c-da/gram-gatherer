"""Write one markdown library file per Instagram item."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from lib.classify import StructuredItem, slugify
from lib.extract import ExtractResult
from lib.parse import InstagramRef


def write_item(
    library_root: Path,
    ref: InstagramRef,
    item: StructuredItem,
    extracted: ExtractResult,
    *,
    overwrite: bool = False,
) -> Path:
    folder = library_root / item.folder
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{ref.shortcode}-{slugify(item.title)}.md"
    path = folder / filename
    if path.exists() and not overwrite:
        raise FileExistsError(str(path))
    path.write_text(
        render_markdown(ref, item, extracted),
        encoding="utf-8",
        newline="\n",
    )
    return path


def render_markdown(ref: InstagramRef, item: StructuredItem, extracted: ExtractResult) -> str:
    if extracted.sources_used:
        sources_yaml = "[" + ", ".join(extracted.sources_used) + "]"
    else:
        sources_yaml = "[]"
    author = item.author or ""
    lines = [
        "---",
        "source: instagram",
        f"url: {ref.url}",
        f"shortcode: {ref.shortcode}",
        f"type: {item.item_type}",
        f"author: {author}",
        f"extracted_at: {date.today().isoformat()}",
        f"sources_used: {sources_yaml}",
        "---",
        "",
        f"# {item.title}",
        "",
    ]
    if item.item_type == "recipe":
        lines.extend(_recipe_body(item, author))
    elif item.item_type == "book":
        lines.extend(
            [
                f"**Author:** {item.author}",
                f"**Why save:** {item.fields.get('why_save', '')}",
                "",
            ]
        )
        if item.books:
            lines.extend(f"- {entry}" for entry in item.books)
            lines.append("")
    elif item.item_type == "album":
        lines.extend(
            [
                f"**Artist:** {item.fields.get('artist', item.author)}",
                f"**Notes:** {item.fields.get('notes', '')}",
                "",
            ]
        )
    elif item.item_type == "workout":
        lines.extend(_workout_body(item, author))
    else:
        lines.extend(
            [
                f"**Summary:** {item.fields.get('summary', '')}",
                "",
            ]
        )
    lines.extend(["## Raw", "", extracted.combined_text.strip() or "_No extracted text._", ""])
    return "\n".join(lines)


def _recipe_body(item: StructuredItem, author: str) -> list[str]:
    lines = [f"**Source:** {author}", "", "## Ingredients"]
    if item.ingredients:
        lines.extend(f"- {entry}" for entry in item.ingredients)
    else:
        lines.append("- ")
    lines.extend(["", "## Steps"])
    if item.steps:
        lines.extend(f"{i}. {step}" for i, step in enumerate(item.steps, start=1))
    else:
        lines.append("1. ")
    lines.extend(["", "## Notes", "", ""])
    return lines


def _workout_body(item: StructuredItem, author: str) -> list[str]:
    lines = [
        f"**Coach:** {author}",
        f"**Why save:** {item.fields.get('why_save', '')}",
        "",
        "## Session",
    ]
    if item.moves:
        lines.extend(f"- {entry}" for entry in item.moves)
    else:
        lines.append("- ")
    lines.extend(["", ""])
    return lines
