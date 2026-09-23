"""Future: a text file of Instagram URLs, one per line.

Bulk drain of a backlog without changing extract/write. Comments (#) and
blank lines would be ignored.

Not implemented in v1 — pass a single URL to gather.py instead.
"""

from __future__ import annotations

from pathlib import Path

from adapters.job import Job


def get_jobs(_path: Path) -> list[Job]:
    raise NotImplementedError("file-of-urls adapter is a v2 seam; use adapters.url.get_job")
