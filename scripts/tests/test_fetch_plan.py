"""Metadata decides the one media call. Do not download video for an image carousel."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from adapters.job import Job  # noqa: E402
from lib.fetch import (  # noqa: E402
    FetchResult,
    _cookie_args,
    fetch_media,
    media_kind_from_info,
)
from lib.parse import InstagramRef  # noqa: E402
from lib.pipeline import gather  # noqa: E402


def _ref() -> InstagramRef:
    return InstagramRef(url="https://www.instagram.com/p/AbC/", shortcode="AbC")


class MediaKindTests(unittest.TestCase):
    def test_image_carousel(self) -> None:
        info = {
            "_type": "playlist",
            "description": "swipe for the list",
            "entries": [
                {"id": "slide1", "formats": [], "thumbnails": [{"url": "https://cdn/1.jpg"}]},
                {"id": "slide2", "formats": [], "thumbnails": [{"url": "https://cdn/2.jpg"}]},
            ],
        }
        self.assertEqual(media_kind_from_info(info), "carousel")

    def test_reel(self) -> None:
        info = {
            "id": "AbC",
            "formats": [{"ext": "mp4", "vcodec": "avc1", "url": "https://cdn/v.mp4"}],
        }
        self.assertEqual(media_kind_from_info(info), "video")

    def test_carousel_with_a_video_slide(self) -> None:
        info = {
            "_type": "playlist",
            "entries": [
                {"formats": [{"vcodec": "avc1", "ext": "mp4"}]},
                {"formats": []},
            ],
        }
        self.assertEqual(media_kind_from_info(info), "video")

    def test_empty_playlist_is_unknown(self) -> None:
        self.assertEqual(media_kind_from_info({"_type": "playlist", "entries": []}), "unknown")


class CookieArgsTests(unittest.TestCase):
    def test_first_call_copies_browser_into_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "cookies.txt"
            args = _cookie_args("opera", dest)
        self.assertEqual(
            args,
            ["--cookies-from-browser", "opera", "--cookies", str(dest)],
        )

    def test_later_call_reads_file_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "cookies.txt"
            dest.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
            args = _cookie_args("opera", dest)
        self.assertEqual(args, ["--cookies", str(dest)])


class FetchMediaTests(unittest.TestCase):
    def test_carousel_skips_video_download(self) -> None:
        fetched = FetchResult(ref=_ref(), caption="swipe", media_kind="carousel")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("lib.fetch._fetch_carousel_thumbs") as thumbs:
                thumbs.return_value = FetchResult(ref=_ref())
                with mock.patch("lib.fetch._fetch_ytdlp_download") as video:
                    fetch_media(fetched, Path(tmp), "opera")
                    video.assert_not_called()
            thumbs.assert_called_once()

    def test_video_skips_thumbnail_playlist(self) -> None:
        fetched = FetchResult(ref=_ref(), caption="thin", media_kind="video")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("lib.fetch._fetch_ytdlp_download") as video:
                video.return_value = FetchResult(ref=_ref())
                with mock.patch("lib.fetch._fetch_carousel_thumbs") as thumbs:
                    fetch_media(fetched, Path(tmp), "opera")
                    thumbs.assert_not_called()
            video.assert_called_once()


class PipelineCallTests(unittest.TestCase):
    def test_sufficient_caption_does_not_download(self) -> None:
        meta = FetchResult(
            ref=_ref(),
            caption=(
                "Books that will make you a better scientist. "
                "The Craft of Scientific Presentations by Michael Alley. "
                "A reading list of engineering books."
            ),
            media_kind="video",
            fetch_ok=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "library").mkdir()
            with mock.patch("lib.pipeline.fetch_metadata", return_value=meta) as metadata:
                with mock.patch("lib.pipeline.fetch_media") as media:
                    result = gather(
                        Job(url="https://www.instagram.com/p/AbC/"),
                        root=root,
                    )
            self.assertEqual(metadata.call_count, 1)
            media.assert_not_called()
            self.assertEqual(result.status, "saved")

    def test_thin_carousel_metadata_once_then_media_once(self) -> None:
        meta = FetchResult(
            ref=_ref(),
            caption="swipe for the list",
            media_kind="carousel",
            fetch_ok=True,
        )

        def _add_slides(result: FetchResult, *_args, **_kwargs) -> FetchResult:
            result.images = [Path("1.jpg"), Path("2.jpg")]
            return result

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "library").mkdir()
            with mock.patch("lib.pipeline.fetch_metadata", return_value=meta) as metadata:
                with mock.patch("lib.pipeline.fetch_media", side_effect=_add_slides) as media:
                    with mock.patch("lib.pipeline.extract_text") as extract:
                        extract.return_value = mock.Mock(
                            combined_text="swipe for the list\n\nTitle One\nTitle Two",
                            caption="swipe for the list",
                            sources_used=["caption", "ocr"],
                            skipped=[],
                        )
                        result = gather(
                            Job(url="https://www.instagram.com/p/AbC/"),
                            root=root,
                        )
            self.assertEqual(metadata.call_count, 1)
            self.assertEqual(media.call_count, 1)
            self.assertEqual(result.status, "saved")


if __name__ == "__main__":
    unittest.main()
