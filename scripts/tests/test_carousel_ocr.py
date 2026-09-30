"""OCR should only run on image carousels (2+ stills, no video)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from lib.extract import carousel_slide_images, extract_text  # noqa: E402
from lib.fetch import FetchResult  # noqa: E402
from lib.parse import InstagramRef  # noqa: E402


def _ref() -> InstagramRef:
    return InstagramRef(url="https://www.instagram.com/p/AbC/", shortcode="AbC")


class CarouselOcrGateTests(unittest.TestCase):
    def test_skips_single_thumb_and_oembed(self) -> None:
        fetched = FetchResult(ref=_ref())
        fetched.images = [Path("oembed-thumb.jpg"), Path("only-one.jpg")]
        self.assertEqual(carousel_slide_images(fetched), [])

    def test_skips_when_video_present(self) -> None:
        fetched = FetchResult(ref=_ref())
        fetched.images = [Path("1.jpg"), Path("2.jpg"), Path("3.jpg")]
        fetched.videos = [Path("reel.mp4")]
        self.assertEqual(carousel_slide_images(fetched), [])

    def test_accepts_multi_still_carousel(self) -> None:
        fetched = FetchResult(ref=_ref())
        slides = [Path("1.jpg"), Path("2.jpg"), Path("3.jpg")]
        fetched.images = slides
        self.assertEqual(carousel_slide_images(fetched), slides)

    def test_accepts_heic_carousel_slides(self) -> None:
        fetched = FetchResult(ref=_ref())
        slides = [Path("1.heic"), Path("2.heif"), Path("3.heic")]
        fetched.images = slides
        self.assertEqual(carousel_slide_images(fetched), slides)

    def test_extract_skips_ocr_note_when_not_carousel(self) -> None:
        fetched = FetchResult(ref=_ref(), caption="thin")
        fetched.videos = [Path("reel.mp4")]
        with mock.patch("lib.extract._whisper_videos") as whisper:
            whisper.return_value = type("P", (), {"text": "", "skipped": ["whisper: skip"]})()
            result = extract_text(fetched, skip_media=False)
        self.assertTrue(any("not a carousel" in s for s in result.skipped))
        self.assertEqual(result.ocr_text, "")


if __name__ == "__main__":
    unittest.main()
