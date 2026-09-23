"""Parse Instagram post/reel URLs into a canonical URL and shortcode."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

SHORTCODE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
PATH_RE = re.compile(
    r"^/(?:p|reel|reels|tv)/(?P<shortcode>[A-Za-z0-9_-]+)/?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class InstagramRef:
    url: str
    shortcode: str


def parse_instagram_url(raw: str) -> InstagramRef:
    text = (raw or "").strip()
    if not text:
        raise ValueError("Instagram URL is empty")

    if SHORTCODE_RE.match(text) and "/" not in text:
        shortcode = text
        url = f"https://www.instagram.com/p/{shortcode}/"
        return InstagramRef(url=url, shortcode=shortcode)

    parsed = urlparse(text)
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host not in {"instagram.com", "instagr.am"}:
        raise ValueError(f"Not an Instagram URL: {raw}")

    match = PATH_RE.match(parsed.path or "")
    if not match:
        raise ValueError(f"Could not find a post/reel shortcode in: {raw}")

    shortcode = match.group("shortcode")
    kind = "reel" if "/reel" in (parsed.path or "").lower() else "p"
    url = f"https://www.instagram.com/{kind}/{shortcode}/"
    return InstagramRef(url=url, shortcode=shortcode)
