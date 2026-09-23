"""Future: drain a Shortcut / iCloud inbox without touching extract/write.

Intended drop path: gram-gatherer/inbox.txt (or an iCloud copy of it).

Suggested line format (not implemented in v1):
    https://www.instagram.com/reel/SHORTCODE/
    https://www.instagram.com/p/SHORTCODE/ | cache/SHORTCODE/video.mp4

The iPhone Shortcut should only append URLs (and optional local media paths).
It should not scrape Instagram.

When implemented, yield Job(url=..., media_paths=...) for each pending line,
then the same `lib.pipeline.gather` used by the URL adapter.
"""

from __future__ import annotations

from adapters.job import Job


def get_jobs() -> list[Job]:
    raise NotImplementedError("inbox adapter is a v2 seam; use adapters.url.get_job")
