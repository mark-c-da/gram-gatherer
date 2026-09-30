"""Duration-based frame sampling and silent-reel OCR gating."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from lib.extract import (  # noqa: E402
    MAX_FRAME_SAMPLES,
    extract_text,
    frame_sample_plan,
)
from lib.fetch import FetchResult  # noqa: E402
from lib.parse import InstagramRef  # noqa: E402


def _ref() -> InstagramRef:
    return InstagramRef(url="https://www.instagram.com/reel/AbC/", shortcode="AbC")


class FrameSamplePlanTests(unittest.TestCase):
    def test_five_second_clip(self) -> None:
        plan = frame_sample_plan(5.0)
        self.assertEqual(plan.count, 5)
        self.assertEqual(len(plan.timestamps), 5)
        self.assertTrue(all(0 < t < 5.0 for t in plan.timestamps))
        self.assertAlmostEqual(plan.interval, 5.0 / 6.0, places=5)

    def test_fifteen_second_hits_cap(self) -> None:
        plan = frame_sample_plan(15.0)
        self.assertEqual(plan.count, MAX_FRAME_SAMPLES)
        self.assertEqual(len(plan.timestamps), 12)
        self.assertTrue(all(0 < t < 15.0 for t in plan.timestamps))

    def test_sixty_second_even_spacing(self) -> None:
        plan = frame_sample_plan(60.0)
        self.assertEqual(plan.count, 12)
        self.assertAlmostEqual(plan.interval, 60.0 / 13.0, places=5)
        self.assertAlmostEqual(plan.timestamps[0], plan.interval, places=5)
        self.assertAlmostEqual(plan.timestamps[-1], plan.interval * 12, places=5)

    def test_short_clip_uses_min_frames(self) -> None:
        plan = frame_sample_plan(1.0)
        self.assertEqual(plan.count, 3)
        self.assertTrue(all(0 < t < 1.0 for t in plan.timestamps))

    def test_zero_or_negative(self) -> None:
        self.assertEqual(frame_sample_plan(0).count, 0)
        self.assertEqual(frame_sample_plan(-3).count, 0)


class FrameOcrGateTests(unittest.TestCase):
    def test_skips_frame_ocr_when_whisper_rich(self) -> None:
        fetched = FetchResult(ref=_ref(), caption="")
        fetched.videos = [Path("reel.mp4")]
        rich = (
            "Here are five psychology books: Thinking Fast and Slow by Kahneman, "
            "Influence by Cialdini, Man's Search for Meaning by Frankl, "
            "Atomic Habits by Clear, and Quiet by Cain."
        )
        with mock.patch("lib.extract._whisper_videos") as whisper:
            whisper.return_value = type("P", (), {"text": rich, "skipped": []})()
            with mock.patch("lib.extract._frame_ocr_video") as frames:
                result = extract_text(fetched, skip_media=False, repo_root=Path("."))
                frames.assert_not_called()
        self.assertIn("whisper", result.sources_used)
        self.assertTrue(any("ocr-frames: skipped" in s for s in result.skipped))

    def test_runs_frame_ocr_when_whisper_empty(self) -> None:
        fetched = FetchResult(ref=_ref(), caption="5 psychology books")
        fetched.videos = [Path("reel.mp4")]
        with mock.patch("lib.extract._whisper_videos") as whisper:
            whisper.return_value = type("P", (), {"text": "", "skipped": ["whisper: silence"]})()
            with mock.patch("lib.extract._frame_ocr_video") as frames:
                frames.return_value = type(
                    "P", (), {"text": "Thinking Fast and Slow\nInfluence", "skipped": []}
                )()
                result = extract_text(fetched, skip_media=False, repo_root=Path("."))
                frames.assert_called_once()
        self.assertIn("ocr-frames", result.sources_used)
        self.assertIn("Thinking Fast and Slow", result.ocr_text)


class ArchiveFramesTests(unittest.TestCase):
    def test_archive_copies_and_writes_meta(self) -> None:
        from lib.extract import _archive_frames

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = root / "cache" / "AbC" / "frames"
            frames.mkdir(parents=True)
            (frames / "frame-01.jpg").write_bytes(b"fake")
            _archive_frames(
                frames,
                repo_root=root,
                shortcode="AbC",
                meta={"shortcode": "AbC", "frame_count": 1},
            )
            dest = root / "archive" / "frames" / "AbC"
            self.assertTrue((dest / "frame-01.jpg").exists())
            self.assertTrue((dest / "meta.json").exists())


if __name__ == "__main__":
    unittest.main()
