"""Tests for Shortcut / iCloud inbox adapter and --from-inbox batch."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from adapters.inbox import get_jobs, rewrite_inbox, resolve_inbox_path  # noqa: E402
from lib.batch_inbox import run_from_inbox  # noqa: E402
from lib.pipeline import GatherResult  # noqa: E402


class InboxAdapterTests(unittest.TestCase):
    def test_resolve_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(resolve_inbox_path(None, root=root), root / "inbox.txt")
            self.assertEqual(resolve_inbox_path("", root=root), root / "inbox.txt")
            self.assertEqual(resolve_inbox_path("drop.txt", root=root), root / "drop.txt")

    def test_missing_file_empty_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(get_jobs(Path(tmp) / "inbox.txt"), [])

    def test_parses_like_file_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inbox.txt"
            path.write_text(
                "\n".join(
                    [
                        "# from phone",
                        "https://www.instagram.com/reel/DPyoYlngK01/",
                        "https://instagram.com/p/Dc8ozlamwzs/ | /tmp/a.jpg",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            jobs = get_jobs(path)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[1].media_paths, [Path("/tmp/a.jpg")])

    def test_rewrite_keeps_pending_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inbox.txt"
            path.write_text(
                "\n".join(
                    [
                        "# backlog",
                        "https://www.instagram.com/reel/DoneCode1/",
                        "https://www.instagram.com/reel/NeedMedia/",
                        "https://www.instagram.com/p/AlsoDone/",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            kept = rewrite_inbox(path, keep_shortcodes={"NeedMedia"})
            text = path.read_text(encoding="utf-8")
        self.assertIn("NeedMedia", text)
        self.assertNotIn("DoneCode1", text)
        self.assertNotIn("AlsoDone", text)
        self.assertIn("# backlog", text)
        self.assertEqual(sum(1 for line in kept if "NeedMedia" in line), 1)


class BatchInboxTests(unittest.TestCase):
    def test_clears_saved_and_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "library").mkdir()
            inbox = root / "inbox.txt"
            inbox.write_text(
                "\n".join(
                    [
                        "https://www.instagram.com/reel/Abc123/",
                        "https://www.instagram.com/reel/Dup456/",
                        "https://www.instagram.com/reel/Need789/",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            def fake_gather(job, **kwargs):
                short = job.url.rstrip("/").split("/")[-1]
                if short == "Abc123":
                    return GatherResult(
                        status="saved",
                        shortcode=short,
                        url=job.url,
                        path=f"library/books/{short}.md",
                        item_type="book",
                        message="ok",
                    )
                if short == "Dup456":
                    return GatherResult(
                        status="duplicate",
                        shortcode=short,
                        url=job.url,
                        path=f"library/books/{short}.md",
                        item_type="book",
                        message="exists",
                    )
                return GatherResult(
                    status="needs_media",
                    shortcode=short,
                    url=job.url,
                    message="thin",
                )

            with mock.patch("lib.batch_inbox.gather", side_effect=fake_gather):
                batch = run_from_inbox(inbox, root=root)

            text = inbox.read_text(encoding="utf-8")
        self.assertEqual(batch.remaining_lines, 1)
        self.assertIn("Need789", text)
        self.assertNotIn("Abc123", text)
        self.assertNotIn("Dup456", text)

    def test_keep_inbox_skips_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "library").mkdir()
            inbox = root / "inbox.txt"
            original = "https://www.instagram.com/reel/KeepMe/\n"
            inbox.write_text(original, encoding="utf-8")

            def fake_gather(job, **kwargs):
                return GatherResult(
                    status="saved",
                    shortcode="KeepMe",
                    url=job.url,
                    path="library/books/KeepMe.md",
                    item_type="book",
                    message="ok",
                )

            with mock.patch("lib.batch_inbox.gather", side_effect=fake_gather):
                batch = run_from_inbox(inbox, root=root, clear_done=False)

            self.assertIsNone(batch.remaining_lines)
            self.assertEqual(inbox.read_text(encoding="utf-8"), original)

    def test_missing_inbox_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError) as ctx:
                run_from_inbox(None, root=root)
            self.assertIn("Inbox not found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
