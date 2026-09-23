"""v1 input: one Instagram URL, optional pasted caption and local media.

Swap this adapter later without changing extract, classify, or write.
See inbox.py, twos.py, and file.py for the intended next inputs.
"""

from __future__ import annotations

from pathlib import Path

from adapters.job import Job


def get_job(
    url: str,
    caption: str | None = None,
    media_paths: list[str] | list[Path] | None = None,
) -> Job:
    paths = [Path(p).expanduser() for p in (media_paths or [])]
    text = (caption or "").strip() or None
    return Job(url=(url or "").strip(), caption=text, media_paths=paths)
