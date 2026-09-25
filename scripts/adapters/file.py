"""URL-file input adapter: one Instagram URL per line.

Used by the Cursor + Twos MCP path: the agent reads a Twos list via MCP,
writes Instagram links to a temp file, then the CLI drains that file.
Comments (#) and blank lines are ignored. Optional `url | media_path` columns.
"""

from __future__ import annotations

from pathlib import Path

from adapters.job import Job
from lib.instagram_urls import extract_instagram_urls
from lib.parse import parse_instagram_url


def get_jobs(path: Path) -> list[Job]:
    text = Path(path).expanduser().read_text(encoding="utf-8")
    jobs: list[Job] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        media_paths: list[Path] = []
        url_part = line
        if "|" in line:
            url_part, _, rest = line.partition("|")
            url_part = url_part.strip()
            for piece in rest.split("|"):
                piece = piece.strip()
                if piece:
                    media_paths.append(Path(piece).expanduser())
        urls = extract_instagram_urls(url_part)
        if not urls:
            try:
                urls = [parse_instagram_url(url_part).url]
            except ValueError:
                continue
        for url in urls:
            short = parse_instagram_url(url).shortcode
            if short in seen:
                continue
            seen.add(short)
            jobs.append(Job(url=url, media_paths=list(media_paths)))
    return jobs
