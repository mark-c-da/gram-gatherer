"""Fetch Instagram caption and media via yt-dlp, then oEmbed."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from lib.parse import InstagramRef

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTS = {".mp4", ".m4v", ".mov", ".webm", ".mkv"}
SKIP_EXTS = {".json", ".description", ".txt", ".vtt", ".srt"}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


@dataclass
class FetchResult:
    ref: InstagramRef
    caption: str = ""
    author: str = ""
    images: list[Path] = field(default_factory=list)
    videos: list[Path] = field(default_factory=list)
    fetch_ok: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def media_files(self) -> list[Path]:
        return [*self.images, *self.videos]


def fetch_post(
    ref: InstagramRef,
    cache_dir: Path,
    cookies_from_browser: str | None = None,
    *,
    need_media: bool = True,
) -> FetchResult:
    result = FetchResult(ref=ref)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cookies = cookies_from_browser or os.environ.get("GRAM_COOKIES_FROM_BROWSER") or None

    _merge(result, _ytdlp_dump_json(ref, cookies))
    if not result.caption:
        _merge(result, _fetch_oembed(ref, cache_dir))

    if need_media:
        _merge(result, _fetch_ytdlp_download(ref, cache_dir, cookies))

    result.fetch_ok = bool(result.caption or result.media_files)
    return result


def attach_user_media(result: FetchResult, media_paths: list[Path]) -> None:
    for raw in media_paths:
        path = Path(raw)
        if not path.exists():
            result.errors.append(f"media not found: {path}")
            continue
        ext = path.suffix.lower()
        if ext in IMAGE_EXTS:
            result.images.append(path)
        elif ext in VIDEO_EXTS:
            result.videos.append(path)
        else:
            result.errors.append(f"unsupported media type: {path}")
    result.fetch_ok = bool(result.caption or result.media_files)


def _merge(target: FetchResult, incoming: FetchResult) -> None:
    if incoming.caption and not target.caption:
        target.caption = incoming.caption
    if incoming.author and not target.author:
        target.author = incoming.author
    target.images.extend(incoming.images)
    target.videos.extend(incoming.videos)
    target.errors.extend(incoming.errors)
    if incoming.fetch_ok:
        target.fetch_ok = True


def _ytdlp_cmd(cookies: str | None, *, playlist: bool = False) -> list[str] | None:
    binary = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
    if binary:
        cmd = [binary, "--no-warnings", "--no-progress"]
    else:
        try:
            import yt_dlp  # noqa: F401
        except ImportError:
            return None
        cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--no-progress"]
    if playlist:
        cmd.extend(["--yes-playlist", "--ignore-no-formats-error"])
    else:
        cmd.append("--no-playlist")
    if cookies:
        cmd.extend(["--cookies-from-browser", cookies])
    return cmd


def _ytdlp_dump_json(ref: InstagramRef, cookies: str | None) -> FetchResult:
    result = FetchResult(ref=ref)
    cmd = _ytdlp_cmd(cookies)
    if not cmd:
        result.errors.append("yt-dlp not installed (pip install yt-dlp)")
        return result
    cmd = [*cmd, "--dump-json", "--skip-download", ref.url]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        result.errors.append(f"yt-dlp metadata failed: {exc}")
        return result
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "yt-dlp metadata failed").strip().splitlines()
        result.errors.append(err[-1] if err else "yt-dlp metadata failed")
        return result
    line = (proc.stdout or "").strip().splitlines()
    if not line:
        result.errors.append("yt-dlp returned empty metadata")
        return result
    try:
        data = json.loads(line[0])
    except json.JSONDecodeError:
        result.errors.append("yt-dlp metadata was not JSON")
        return result
    fake = FetchResult(ref=ref)
    _apply_info_dict(data, fake)
    return fake


def _fetch_ytdlp_download(
    ref: InstagramRef,
    cache_dir: Path,
    cookies: str | None,
) -> FetchResult:
    result = FetchResult(ref=ref)
    cmd = _ytdlp_cmd(cookies)
    if not cmd:
        if "yt-dlp not installed (pip install yt-dlp)" not in result.errors:
            result.errors.append("yt-dlp not installed (pip install yt-dlp)")
        return result

    out_tmpl = str(cache_dir / "%(id)s-%(autonumber)s.%(ext)s")
    cmd = [
        *cmd,
        "--write-info-json",
        "--write-thumbnail",
        "-o",
        out_tmpl,
        ref.url,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        result.errors.append(f"yt-dlp download failed: {exc}")
        return result
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "yt-dlp download failed").strip().splitlines()
        result.errors.append(err[-1] if err else "yt-dlp download failed")
    _scan_cache(cache_dir, result)
    if not result.media_files:
        _merge(result, _fetch_carousel_thumbs(ref, cache_dir, cookies))
    return result


def _fetch_carousel_thumbs(
    ref: InstagramRef,
    cache_dir: Path,
    cookies: str | None,
) -> FetchResult:
    """Image carousels have no video formats; grab slide thumbnails instead."""
    result = FetchResult(ref=ref)
    cmd = _ytdlp_cmd(cookies, playlist=True)
    if not cmd:
        return result
    out_tmpl = str(cache_dir / "%(playlist_index)s-%(id)s.%(ext)s")
    cmd = [
        *cmd,
        "--write-thumbnail",
        "--skip-download",
        "-o",
        out_tmpl,
        ref.url,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        result.errors.append(f"yt-dlp carousel thumbnails failed: {exc}")
        return result
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        if err:
            result.errors.append(err[-1])
    _scan_cache(cache_dir, result)
    return result


def _scan_cache(cache_dir: Path, result: FetchResult) -> None:
    if not cache_dir.exists():
        return
    for path in sorted(cache_dir.iterdir()):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                _apply_info_dict(data, result)
            continue
        if ext in SKIP_EXTS or path.name.endswith(".description"):
            continue
        if ext in IMAGE_EXTS:
            result.images.append(path)
        elif ext in VIDEO_EXTS:
            result.videos.append(path)
    result.fetch_ok = bool(result.caption or result.media_files)


def _apply_info_dict(data: dict, result: FetchResult) -> None:
    if not result.caption:
        caption = data.get("description") or data.get("title") or ""
        if isinstance(caption, str):
            result.caption = caption.strip()
    if not result.author:
        author = data.get("uploader") or data.get("channel") or data.get("creator") or ""
        if isinstance(author, str):
            result.author = author.strip()
    if result.caption or result.author:
        result.fetch_ok = True


def _fetch_oembed(ref: InstagramRef, cache_dir: Path) -> FetchResult:
    result = FetchResult(ref=ref)
    encoded = urllib.parse.quote(ref.url, safe="")
    endpoints = [
        f"https://www.instagram.com/api/oembed/?url={encoded}",
        f"https://api.instagram.com/oembed?url={encoded}",
    ]
    for endpoint in endpoints:
        req = urllib.request.Request(endpoint, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        title = data.get("title") or ""
        author = data.get("author_name") or ""
        if isinstance(title, str):
            result.caption = title.strip()
        if isinstance(author, str):
            result.author = author.strip()
        thumb = data.get("thumbnail_url")
        if isinstance(thumb, str) and thumb:
            saved = _download_thumbnail(thumb, cache_dir)
            if saved:
                result.images.append(saved)
        result.fetch_ok = bool(result.caption or result.images)
        if result.fetch_ok:
            return result
    result.errors.append("oEmbed returned no caption")
    return result


def _download_thumbnail(url: str, cache_dir: Path) -> Path | None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / "oembed-thumb.jpg"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            dest.write_bytes(resp.read())
        return dest
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
