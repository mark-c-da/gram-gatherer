"""Future: parse a Twos list export for Instagram URLs.

Twos stays a capture inbox, not the searchable library. An export or copied
list should become Job(url=...) rows, then the existing gather pipeline.

Not implemented in v1 — paste one Instagram URL at a time instead.
"""

from __future__ import annotations

from pathlib import Path

from adapters.job import Job


def get_jobs(_export: Path) -> list[Job]:
    raise NotImplementedError("Twos adapter is a v2 seam; use adapters.url.get_job")
