"""Error log records fetch problems and skips a repeated line."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from lib.error_log import append_error_log  # noqa: E402
from lib.pipeline import GatherResult  # noqa: E402


class ErrorLogTests(unittest.TestCase):
    def test_appends_saved_with_fetch_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = GatherResult(
                status="saved",
                shortcode="AbC",
                url="https://www.instagram.com/p/AbC/",
                errors=["ERROR: [Instagram] AbCchild: No video formats found"],
            )
            append_error_log(root, result)
            append_error_log(root, result)
            text = (root / "docs" / "ERROR-LOG.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("No video formats"), 1)
        self.assertIn("**AbC** (saved)", text)

    def test_skips_clean_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            append_error_log(
                root,
                GatherResult(status="saved", shortcode="AbC", message="Saved book"),
            )
            self.assertFalse((root / "docs" / "ERROR-LOG.md").exists())


if __name__ == "__main__":
    unittest.main()
