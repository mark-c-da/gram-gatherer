"""Find Instagram post/reel URLs in free text (shared by file / future Twos adapters)."""

from __future__ import annotations

import re

from lib.parse import parse_instagram_url

IG_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:instagram\.com|instagr\.am)/(?:p|reel|reels|tv)/[A-Za-z0-9_-]+/?",
    re.IGNORECASE,
)


def extract_instagram_urls(*parts: str | None) -> list[str]:
    """Return unique canonical Instagram URLs found in the given text blobs."""
    found: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        text = str(part)
        candidates = list(IG_URL_RE.findall(text))
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
