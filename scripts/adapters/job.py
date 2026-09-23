"""A single gather job. Every input adapter should return this, then stop.

The extract / classify / write pipeline depends only on Job, not on how
the URL arrived (chat paste, Twos export, inbox file, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Job:
    url: str
    caption: str | None = None
    media_paths: list[Path] = field(default_factory=list)
