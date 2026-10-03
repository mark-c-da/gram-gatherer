"""Append gather failures to docs/ERROR-LOG.md.

A save can still carry yt-dlp errors (a carousel that tried a video download
and recovered). Those belong here, next to needs_media and hard errors.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

_HEADER = """# Error log

Gather appends a bullet when a run returns `error` or `needs_media`, or when a save still carries fetch errors. One line per problem. Newest day at the bottom.
"""


def append_error_log(root: Path, result) -> None:
    lines = _lines(result)
    if not lines:
        return
    path = root / "docs" / "ERROR-LOG.md"
    try:
        existing = path.read_text(encoding="utf-8") if path.exists() else _HEADER
        day = date.today().isoformat()
        if f"## {day}" not in existing:
            existing = existing.rstrip() + f"\n\n## {day}\n"
        fresh = [line for line in lines if line not in existing]
        if not fresh:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(existing.rstrip() + "\n" + "\n".join(fresh) + "\n", encoding="utf-8")
    except OSError:
        return


def _lines(result) -> list[str]:
    short = result.shortcode or "(no shortcode)"
    messages: list[str] = []
    if result.status in {"error", "needs_media"} and result.message:
        messages.append(result.message)
    messages.extend(result.errors or [])
    out: list[str] = []
    for message in messages:
        text = " ".join(message.split())
        if not text:
            continue
        out.append(f"- **{short}** ({result.status}): {text}")
    return out
