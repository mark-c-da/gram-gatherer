"""Tests for URL-file adapter and Twos MCP payload helper."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from adapters.file import get_jobs  # noqa: E402
from lib.batch_file import run_from_file  # noqa: E402
from lib.instagram_urls import extract_instagram_urls  # noqa: E402
from lib.pipeline import GatherResult  # noqa: E402
from lib.twos_payload import batch_writeback_payload, thing_payload  # noqa: E402


class FileAdapterTests(unittest.TestCase):
    def test_parses_lines_and_comments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "urls.txt"
            path.write_text(
                "\n".join(
                    [
                        "# backlog",
                        "https://www.instagram.com/reel/DPyoYlngK01/",
                        "",
                        "https://instagram.com/p/Dc8ozlamwzs/ | /tmp/slide.jpg",
                        "https://www.instagram.com/reel/DPyoYlngK01/",
                    ]
                ),
                encoding="utf-8",
            )
            jobs = get_jobs(path)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].url, "https://www.instagram.com/reel/DPyoYlngK01/")
        self.assertEqual(jobs[1].media_paths, [Path("/tmp/slide.jpg")])


class PayloadTests(unittest.TestCase):
    def test_thing_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lib = Path(tmp) / "x.md"
            lib.write_text("---\ntype: book\n---\n\n# Hello\n\nbody\n", encoding="utf-8")
            payload = thing_payload(
                title="Hello",
                item_type="book",
                instagram_url="https://www.instagram.com/reel/Abc/",
                library_path=lib,
            )
        self.assertEqual(payload["text"], "book: Hello")
        self.assertEqual(payload["url"], "https://www.instagram.com/reel/Abc/")
        self.assertIn("body", payload["note"] or "")

    def test_batch_writeback_skips_non_saved(self) -> None:
        results = [
            {"status": "duplicate", "path": "library/books/x.md", "url": "https://www.instagram.com/p/a/"},
            {
                "status": "saved",
                "path": "library/books/y.md",
                "url": "https://www.instagram.com/reel/Yyy/",
                "type": "book",
                "shortcode": "Yyy",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "library" / "books" / "y.md"
            path.parent.mkdir(parents=True)
            path.write_text("# Title Y\n\nraw\n", encoding="utf-8")
            doc = batch_writeback_payload(results=results, root=root, source_list_title="Saved")
        self.assertEqual(len(doc["things"]), 1)
        self.assertIn("Gathered from Saved", doc["create_list"]["title"])


class BatchFileTests(unittest.TestCase):
    def test_emit_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "library").mkdir()
            urls = root / "urls.txt"
            urls.write_text("https://www.instagram.com/reel/Abc123/\n", encoding="utf-8")

            def fake_gather(job, **kwargs):
                rel = "library/books/Abc123-t.md"
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# T\n\nbody\n", encoding="utf-8")
                return GatherResult(
                    status="saved",
                    shortcode="Abc123",
                    url=job.url,
                    path=rel,
                    item_type="book",
                    message="ok",
                )

            with mock.patch("lib.batch_file.gather", side_effect=fake_gather):
                batch = run_from_file(
                    urls,
                    root=root,
                    emit_twos_payload=True,
                    source_list_title="Inbox",
                )
        self.assertEqual(batch.results[0]["status"], "saved")
        self.assertIsNotNone(batch.twos_mcp_writeback)
        self.assertEqual(len(batch.twos_mcp_writeback["things"]), 1)


class ExtractTests(unittest.TestCase):
    def test_extract(self) -> None:
        self.assertEqual(
            extract_instagram_urls("see https://www.instagram.com/reel/DPyoYlngK01/ now"),
            ["https://www.instagram.com/reel/DPyoYlngK01/"],
        )


if __name__ == "__main__":
    unittest.main()
