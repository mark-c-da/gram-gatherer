"""Batch Twos flow with a fake client (no network)."""

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

from lib.batch_twos import run_from_twos  # noqa: E402
from lib.pipeline import GatherResult  # noqa: E402
from lib.twos_client import TwosList  # noqa: E402


class FakeTwos:
    def __init__(self) -> None:
        self.created_things: list[dict] = []
        self.created_lists: list[dict] = []

    def find_list(self, name_or_id: str) -> TwosList:
        return TwosList(id="src1", title=name_or_id)

    def get_list(self, list_id: str) -> TwosList:
        return TwosList(
            id=list_id,
            title="Saved IG",
            things=[
                {
                    "id": "t1",
                    "text": "books",
                    "url": "https://www.instagram.com/reel/DPyoYlngK01/",
                },
                {
                    "id": "t2",
                    "text": "https://www.instagram.com/reel/DQ7-t-ajNPl/ albums",
                },
            ],
        )

    def create_list(self, title: str, *, emoji: str | None = None, things=None) -> TwosList:
        self.created_lists.append({"title": title, "emoji": emoji})
        return TwosList(id="out1", title=title, emoji=emoji)

    def create_thing(self, **kwargs):
        self.created_things.append(kwargs)
        return {"id": f"thing-{len(self.created_things)}"}


class BatchTwosTests(unittest.TestCase):
    def test_sequential_gather_and_push(self) -> None:
        fake = FakeTwos()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "library").mkdir()
            (root / "library" / "index.json").write_text("{}", encoding="utf-8")

            def fake_gather(job, **kwargs):
                short = job.url.rstrip("/").split("/")[-1]
                path = root / "library" / "books" / f"{short}-title.md"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    f"---\nshortcode: {short}\n---\n\n# Title {short}\n\nbody\n",
                    encoding="utf-8",
                )
                # Update index like real pipeline
                idx_path = root / "library" / "index.json"
                idx = json.loads(idx_path.read_text(encoding="utf-8") or "{}")
                rel = path.relative_to(root).as_posix()
                idx[short] = {"path": rel, "type": "book"}
                # Real index format may differ — gather writes via index_mod; we only need path on result
                idx_path.write_text(json.dumps(idx), encoding="utf-8")
                return GatherResult(
                    status="saved",
                    shortcode=short,
                    url=job.url,
                    path=rel,
                    item_type="book",
                    sources_used=["caption"],
                    message="ok",
                )

            with mock.patch("lib.batch_twos.gather", side_effect=fake_gather):
                batch = run_from_twos(
                    "Saved IG",
                    root=root,
                    to_twos=True,
                    client=fake,  # type: ignore[arg-type]
                )

        self.assertEqual(batch.output_list_id, "out1")
        self.assertEqual(len(batch.results), 2)
        self.assertEqual(len(fake.created_things), 2)
        self.assertTrue(all(r["status"] == "saved" for r in batch.results))
        self.assertTrue(all(r["twos_push"]["ok"] for r in batch.results))
        self.assertEqual(
            fake.created_things[0]["url"],
            "https://www.instagram.com/reel/DPyoYlngK01/",
        )


if __name__ == "__main__":
    unittest.main()
