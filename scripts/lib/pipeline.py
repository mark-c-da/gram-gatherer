"""Orchestrate parse → fetch → extract → classify → write → index."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from adapters.job import Job
from lib.classify import caption_sufficient, structure_item
from lib.extract import ExtractResult, extract_text
from lib.fetch import FetchResult, attach_user_media, fetch_post
from lib import index as index_mod
from lib.parse import parse_instagram_url
from lib.write import write_item


@dataclass
class GatherResult:
    status: str
    shortcode: str = ""
    url: str = ""
    path: str | None = None
    item_type: str | None = None
    sources_used: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    message: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "shortcode": self.shortcode,
            "url": self.url,
            "path": self.path,
            "type": self.item_type,
            "sources_used": self.sources_used,
            "skipped": self.skipped,
            "message": self.message,
            "errors": self.errors,
        }


def gather(
    job: Job,
    *,
    root: Path,
    cookies_from_browser: str | None = None,
    overwrite: bool = False,
) -> GatherResult:
    library = root / "library"
    cache_root = root / "cache"
    index_path = library / "index.json"

    try:
        ref = parse_instagram_url(job.url)
    except ValueError as exc:
        return GatherResult(status="error", message=str(exc))

    idx = index_mod.load_index(index_path)
    existing = index_mod.lookup(idx, ref.shortcode)
    if existing and not overwrite:
        return GatherResult(
            status="duplicate",
            shortcode=ref.shortcode,
            url=ref.url,
            path=existing,
            message=f"Already saved at {existing}",
        )

    cache_dir = cache_root / ref.shortcode
    user_caption = (job.caption or "").strip()
    user_media = list(job.media_paths)

    fetched = _caption_only(ref, cache_dir, cookies_from_browser, user_caption)
    if user_media:
        attach_user_media(fetched, user_media)

    caption = fetched.caption.strip()
    if caption_sufficient(caption) and not user_media:
        extracted = extract_text(
            fetched,
            caption_override=user_caption or None,
            skip_media=True,
            repo_root=root,
        )
        return _commit(
            root, library, index_path, idx, ref, fetched, extracted, overwrite, cache_dir
        )

    if not caption_sufficient(caption) and not fetched.media_files:
        fetched = fetch_post(
            ref,
            cache_dir,
            cookies_from_browser,
            need_media=True,
        )
        if user_caption and (
            not fetched.caption or len(user_caption) >= len(fetched.caption)
        ):
            fetched.caption = user_caption
        if user_media:
            attach_user_media(fetched, user_media)
        caption = fetched.caption.strip()

    if not caption and not fetched.media_files:
        return GatherResult(
            status="needs_media",
            shortcode=ref.shortcode,
            url=ref.url,
            message=(
                "Could not fetch a caption or media. Paste the caption and/or "
                "drop the video or screenshots, then re-run with --caption / --media."
            ),
            errors=fetched.errors,
        )

    if not caption_sufficient(caption) and not fetched.media_files:
        return GatherResult(
            status="needs_media",
            shortcode=ref.shortcode,
            url=ref.url,
            message=(
                "Caption is too thin to extract a recipe, book, album, or workout, and no "
                "media was downloaded. Paste the caption and/or drop the video "
                "or screenshots, then re-run with --caption / --media."
            ),
            errors=fetched.errors,
            sources_used=["caption"] if caption else [],
        )

    extracted = extract_text(
        fetched,
        caption_override=user_caption or None,
        skip_media=False,
        repo_root=root,
    )
    if not extracted.caption and caption:
        extracted.caption = caption
        if "caption" not in extracted.sources_used and "user-paste" not in extracted.sources_used:
            extracted.sources_used.insert(0, "caption")

    return _commit(
        root, library, index_path, idx, ref, fetched, extracted, overwrite, cache_dir
    )


def _caption_only(
    ref,
    cache_dir: Path,
    cookies_from_browser: str | None,
    user_caption: str,
) -> FetchResult:
    if user_caption:
        fetched = FetchResult(ref=ref)
        fetched.caption = user_caption
        fetched.fetch_ok = True
        return fetched
    return fetch_post(ref, cache_dir, cookies_from_browser, need_media=False)


def _commit(
    root: Path,
    library: Path,
    index_path: Path,
    idx: dict,
    ref,
    fetched: FetchResult,
    extracted: ExtractResult,
    overwrite: bool,
    cache_dir: Path,
) -> GatherResult:
    combined = extracted.combined_text
    if not combined.strip():
        return GatherResult(
            status="needs_media",
            shortcode=ref.shortcode,
            url=ref.url,
            message="Nothing extractable yet. Paste a caption or drop media.",
            errors=fetched.errors,
            skipped=extracted.skipped,
        )

    item = structure_item(combined, fallback_author=fetched.author)
    try:
        written = write_item(library, ref, item, extracted, overwrite=overwrite)
    except FileExistsError as exc:
        existing_path = Path(str(exc))
        try:
            rel_existing = existing_path.relative_to(root).as_posix()
        except ValueError:
            rel_existing = existing_path.as_posix()
        return GatherResult(
            status="duplicate",
            shortcode=ref.shortcode,
            url=ref.url,
            path=rel_existing,
            item_type=item.item_type,
            message=f"File already exists: {rel_existing}",
        )

    rel = written.relative_to(root).as_posix()
    index_mod.record(idx, ref.shortcode, rel, item.item_type)
    index_mod.save_index(index_path, idx)
    _clear_cache(cache_dir)

    return GatherResult(
        status="saved",
        shortcode=ref.shortcode,
        url=ref.url,
        path=rel,
        item_type=item.item_type,
        sources_used=extracted.sources_used,
        skipped=extracted.skipped,
        message=f"Saved {item.item_type} to {rel}",
        errors=fetched.errors,
    )


def _clear_cache(cache_dir: Path) -> None:
    if cache_dir.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)
