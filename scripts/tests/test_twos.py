"""Unit tests for Twos URL extraction and markdown helpers (no live API)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from adapters.twos import extract_instagram_urls, urls_from_thing  # noqa: E402
from lib.twos_out import default_output_title, markdown_for_twos  # noqa: E402


class ExtractUrlsTests(unittest.TestCase):
    def test_reel_and_post(self) -> None:
        text = (
            "save this https://www.instagram.com/reel/DPyoYlngK01/ "
            "and https://instagram.com/p/Dc8ozlamwzs/"
        )
        urls = extract_instagram_urls(text)
        self.assertEqual(
            urls,
            [
                "https://www.instagram.com/reel/DPyoYlngK01/",
                "https://www.instagram.com/p/Dc8ozlamwzs/",
            ],
        )

    def test_dedup_shortcode(self) -> None:
        urls = extract_instagram_urls(
            "https://www.instagram.com/reel/Abc123/",
            "https://www.instagram.com/reel/Abc123/?igsh=xyz",
        )
        self.assertEqual(urls, ["https://www.instagram.com/reel/Abc123/"])

    def test_thing_url_field(self) -> None:
        thing = {
            "id": "1",
            "text": "book list",
            "url": "https://www.instagram.com/reel/DPyoYlngK01/",
        }
        self.assertEqual(
            urls_from_thing(thing),
            ["https://www.instagram.com/reel/DPyoYlngK01/"],
        )

    def test_ignores_non_instagram(self) -> None:
        self.assertEqual(extract_instagram_urls("https://example.com/x"), [])


class TwosOutTests(unittest.TestCase):
    def test_default_title(self) -> None:
        title = default_output_title("Saved IG")
        self.assertTrue(title.startswith("Gathered from Saved IG — "))

    def test_markdown_block(self) -> None:
        md = markdown_for_twos(
            title="Six albums",
            item_type="album",
            instagram_url="https://www.instagram.com/reel/DQ7-t-ajNPl/",
            library_path="library/albums/DQ7-t-ajNPl-six-new-albums.md",
            body_markdown="# Six albums\n\n**Artist:** Don",
        )
        self.assertIn("## Six albums", md)
        self.assertIn("type: album", md)
        self.assertIn("instagram.com/reel/DQ7-t-ajNPl", md)


if __name__ == "__main__":
    unittest.main()
