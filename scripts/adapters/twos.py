"""Twos input adapter: pull Instagram URLs from a Twos list into Job rows.

Twos is a capture inbox. Each thing's `url` field and/or Instagram links inside
`text` / `note` become gather jobs. The searchable library stays under library/.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from adapters.job import Job
from lib.parse import parse_instagram_url
from lib.twos_client import TwosClient, TwosError, TwosList

IG_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:instagram\.com|instagr\.am)/(?:p|reel|reels|tv)/[A-Za-z0-9_-]+/?",
    re.IGNORECASE,
)


@dataclass
class TwosJob(Job):
    """Job plus the Twos thing id it came from (for later tagging if needed)."""

    thing_id: str | None = None
    source_list_id: str | None = None
    source_list_title: str | None = None


def extract_instagram_urls(*parts: str | None) -> list[str]:
    """Return unique canonical Instagram URLs found in the given text blobs."""
    found: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        text = str(part)
        candidates = list(IG_URL_RE.findall(text))
        # Also accept a bare shortcode-only url field that parse_instagram_url handles
        # when the whole string is itself a URL/shortcode.
        stripped = text.strip()
        if stripped and stripped not in candidates and (
            "instagram.com" in stripped.lower() or "instagr.am" in stripped.lower()
        ):
            candidates.insert(0, stripped)
        for raw in candidates:
            try:
                ref = parse_instagram_url(raw)
            except ValueError:
                continue
            if ref.shortcode in seen:
                continue
            seen.add(ref.shortcode)
            found.append(ref.url)
    return found


def urls_from_thing(thing: dict) -> list[str]:
    return extract_instagram_urls(
        thing.get("url"),
        thing.get("text"),
        thing.get("note"),
    )


def get_jobs(
    list_name_or_id: str,
    *,
    client: TwosClient | None = None,
) -> tuple[TwosList, list[TwosJob]]:
    """Resolve a Twos list and return Instagram jobs in list display order."""
    api = client or TwosClient()
    meta = api.find_list(list_name_or_id)
    detail = api.get_list(meta.id)
    things = detail.things if detail.things is not None else meta.things or []
    jobs: list[TwosJob] = []
    seen_shortcodes: set[str] = set()
    for thing in things:
        if not isinstance(thing, dict):
            continue
        for url in urls_from_thing(thing):
            try:
                shortcode = parse_instagram_url(url).shortcode
            except ValueError:
                continue
            if shortcode in seen_shortcodes:
                continue
            seen_shortcodes.add(shortcode)
            jobs.append(
                TwosJob(
                    url=url,
                    thing_id=str(thing.get("id") or "") or None,
                    source_list_id=detail.id or meta.id,
                    source_list_title=detail.title or meta.title,
                )
            )
    return detail, jobs


def require_jobs(list_name_or_id: str, *, client: TwosClient | None = None) -> tuple[TwosList, list[TwosJob]]:
    source, jobs = get_jobs(list_name_or_id, client=client)
    if not jobs:
        raise TwosError(
            f"Twos list {source.title!r} ({source.id}) has no Instagram post/reel links."
        )
    return source, jobs
