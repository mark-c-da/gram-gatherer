"""Shortcut / iCloud inbox drop → Jobs.

Phone capture (Workflow 2) appends Instagram URLs to ``inbox.txt`` at the repo
root (or an iCloud-synced copy of that file). This adapter only reads that
file; it does not scrape Instagram.

Line format (same as ``--from-file``):
    https://www.instagram.com/reel/SHORTCODE/
    https://www.instagram.com/p/SHORTCODE/ | cache/SHORTCODE/video.mp4

Comments (``#``) and blank lines are ignored when building jobs.
"""

from __future__ import annotations

from pathlib import Path

from adapters.file import get_jobs as get_jobs_from_file
from adapters.job import Job
from lib.instagram_urls import extract_instagram_urls
from lib.parse import parse_instagram_url

DEFAULT_INBOX_NAME = "inbox.txt"


def default_inbox_path(root: Path) -> Path:
    return Path(root) / DEFAULT_INBOX_NAME


def resolve_inbox_path(path: str | Path | None, *, root: Path) -> Path:
    """Return the inbox file path. Empty/None → ``<root>/inbox.txt``."""
    if path is None or str(path).strip() == "":
        return default_inbox_path(root)
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = Path(root) / p
    return p


def get_jobs(path: Path) -> list[Job]:
    """Load pending Jobs from an inbox file. Missing file → empty list."""
    inbox = Path(path).expanduser()
    if not inbox.is_file():
        return []
    return get_jobs_from_file(inbox)


def rewrite_inbox(
    path: Path,
    *,
    keep_shortcodes: set[str],
) -> list[str]:
    """Rewrite the inbox, keeping comments/blanks and URL lines still pending.

    Lines whose Instagram shortcode is *not* in ``keep_shortcodes`` are dropped
    (typically after ``saved`` / ``duplicate``). Unparseable non-comment lines
    are kept so nothing is silently lost.
    """
    inbox = Path(path).expanduser()
    if not inbox.is_file():
        return []

    original = inbox.read_text(encoding="utf-8")
    kept: list[str] = []
    for raw_line in original.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            kept.append(raw_line.rstrip("\n"))
            continue
        url_part = stripped
        if "|" in stripped:
            url_part = stripped.partition("|")[0].strip()
        try:
            short = parse_instagram_url(url_part).shortcode
        except ValueError:
            found = extract_instagram_urls(url_part)
            if not found:
                kept.append(raw_line.rstrip("\n"))
                continue
            short = parse_instagram_url(found[0]).shortcode
        if short in keep_shortcodes:
            kept.append(raw_line.rstrip("\n"))

    # Drop trailing blank lines; keep a single trailing newline when non-empty
    while kept and not kept[-1].strip():
        kept.pop()
    text = "\n".join(kept)
    if text:
        text += "\n"
    inbox.write_text(text, encoding="utf-8")
    return kept
