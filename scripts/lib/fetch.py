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

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif"}
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
    # video: download the file. carousel: thumbnails only. unknown: try video, then thumbs.
    media_kind: str = "unknown"

    @property
    def media_files(self) -> list[Path]:
        return [*self.images, *self.videos]


def fetch_metadata(
    ref: InstagramRef,
    cache_dir: Path,
    cookies_from_browser: str | None = None,
    *,
    cookie_file: Path | None = None,
) -> FetchResult:
    """One yt-dlp metadata call. Does not download video or slide images."""
    result = FetchResult(ref=ref)
    cache_dir.mkdir(parents=True, exist_ok=True)
    browser = cookies_from_browser or os.environ.get("GRAM_COOKIES_FROM_BROWSER") or None

    _merge(result, _ytdlp_dump_json(ref, browser, cookie_file=cookie_file))
    if not result.caption:
        _merge(result, _fetch_oembed(ref, cache_dir))

    result.fetch_ok = bool(result.caption or result.media_files)
    return result


def fetch_media(
    result: FetchResult,
    cache_dir: Path,
    cookies_from_browser: str | None = None,
    *,
    cookie_file: Path | None = None,
) -> FetchResult:
    """Download only what the metadata call already said we need.

    Image carousels skip the video download. Reels skip a second metadata call.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    browser = cookies_from_browser or os.environ.get("GRAM_COOKIES_FROM_BROWSER") or None

    if result.media_kind == "carousel":
        _merge(result, _fetch_carousel_thumbs(result.ref, cache_dir, browser, cookie_file=cookie_file))
    else:
        _merge(result, _fetch_ytdlp_download(result.ref, cache_dir, browser, cookie_file=cookie_file))
        if result.media_kind != "video" and not result.videos and len(result.images) < 2:
            _merge(result, _fetch_carousel_thumbs(result.ref, cache_dir, browser, cookie_file=cookie_file))

    result.fetch_ok = bool(result.caption or result.media_files)
    return result


def media_kind_from_info(data: dict) -> str:
    """Classify a yt-dlp info dict before any download."""
    if not isinstance(data, dict):
        return "unknown"
    if data.get("_type") == "playlist":
        entries = [entry for entry in data.get("entries") or [] if isinstance(entry, dict)]
        if not entries:
            return "unknown"
        if any(_entry_has_video(entry) for entry in entries):
            return "video"
        return "carousel"
    if _entry_has_video(data):
        return "video"
    return "unknown"


def _entry_has_video(data: dict) -> bool:
    video_exts = {ext.lstrip(".") for ext in VIDEO_EXTS}
    for fmt in data.get("formats") or []:
        if not isinstance(fmt, dict):
            continue
        vcodec = fmt.get("vcodec")
        if vcodec and vcodec != "none":
            return True
        if str(fmt.get("ext") or "").lower() in video_exts:
            return True
    if str(data.get("ext") or "").lower() in video_exts:
        return True
    return False


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


def _cookie_args(browser: str | None, cookie_file: Path | None) -> list[str]:
    """Use a Netscape cookie file after the first browser copy in this run.

    The first yt-dlp call passes both --cookies-from-browser and --cookies so
    yt-dlp writes the jar. Later calls only read the file.
    """
    ready = (
        cookie_file is not None
        and cookie_file.is_file()
        and cookie_file.stat().st_size > 0
    )
    if ready:
        return ["--cookies", str(cookie_file)]
    if browser:
        args = ["--cookies-from-browser", browser]
        if cookie_file is not None:
            cookie_file.parent.mkdir(parents=True, exist_ok=True)
            args.extend(["--cookies", str(cookie_file)])
        return args
    return []


def _ytdlp_cmd(
    browser: str | None,
    *,
    playlist: bool = False,
    cookie_file: Path | None = None,
) -> list[str] | None:
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
    cmd.extend(_cookie_args(browser, cookie_file))
    return cmd


def _ytdlp_dump_json(
    ref: InstagramRef,
    browser: str | None,
    *,
    cookie_file: Path | None = None,
) -> FetchResult:
    result = FetchResult(ref=ref)
    cmd = _ytdlp_cmd(browser, playlist=True, cookie_file=cookie_file)
    if not cmd:
        result.errors.append("yt-dlp not installed (pip install yt-dlp)")
        return result
    cmd = [*cmd, "--dump-single-json", "--skip-download", ref.url]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        result.errors.append(f"yt-dlp metadata failed: {exc}")
        return result
    raw = (proc.stdout or "").strip()
    data = None
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
    if not isinstance(data, dict):
        err = (proc.stderr or proc.stdout or "yt-dlp metadata failed").strip().splitlines()
        result.errors.append(err[-1] if err else "yt-dlp metadata was not JSON")
        return result
    result.media_kind = media_kind_from_info(data)
    _apply_info_dict(data, result)
    if proc.returncode != 0 and not result.caption:
        err = (proc.stderr or "").strip().splitlines()
        if err:
            result.errors.append(err[-1])
    return result


def _fetch_ytdlp_download(
    ref: InstagramRef,
    cache_dir: Path,
    browser: str | None,
    *,
    cookie_file: Path | None = None,
) -> FetchResult:
    result = FetchResult(ref=ref)
    cmd = _ytdlp_cmd(browser, cookie_file=cookie_file)
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
    return result


def _fetch_carousel_thumbs(
    ref: InstagramRef,
    cache_dir: Path,
    browser: str | None,
    *,
    cookie_file: Path | None = None,
) -> FetchResult:
    """Image carousels have no video formats; grab slide thumbnails instead."""
    result = FetchResult(ref=ref)
    cmd = _ytdlp_cmd(browser, playlist=True, cookie_file=cookie_file)
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
