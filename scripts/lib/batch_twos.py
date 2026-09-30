"""Sequential gather from a Twos list, with optional write-back to a new Twos list."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from adapters.twos import TwosJob, require_jobs
from lib.pipeline import GatherResult, gather
from lib.twos_client import TwosClient
from lib.twos_out import ensure_output_list, push_saved_item


@dataclass
class BatchResult:
    source_list_id: str
    source_list_title: str
    output_list_id: str | None = None
    output_list_title: str | None = None
    results: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_list_id": self.source_list_id,
            "source_list_title": self.source_list_title,
            "output_list_id": self.output_list_id,
            "output_list_title": self.output_list_title,
            "count": len(self.results),
            "results": self.results,
        }

    @property
    def worst_exit_status(self) -> str:
        """Pick a summary status for CLI exit codes."""
        statuses = [r.get("status") for r in self.results]
        if any(s == "error" for s in statuses):
            return "error"
        if any(s == "needs_media" for s in statuses):
            return "needs_media"
        if statuses and all(s == "duplicate" for s in statuses):
            return "duplicate"
        if any(s == "saved" for s in statuses):
            return "saved"
        return "error"


def _title_from_library(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def run_from_twos(
    list_name_or_id: str,
    *,
    root: Path,
    to_twos: bool = False,
    to_twos_list: str | None = None,
    cookies_from_browser: str | None = None,
    overwrite: bool = False,
    client: TwosClient | None = None,
) -> BatchResult:
    api = client or TwosClient()
    source, jobs = require_jobs(list_name_or_id, client=api)
    batch = BatchResult(source_list_id=source.id, source_list_title=source.title)

    dest = None
    if to_twos or to_twos_list:
        dest = ensure_output_list(
            api,
            title=to_twos_list,
            source_title=source.title,
        )
        batch.output_list_id = dest.id
        batch.output_list_title = dest.title

    for job in jobs:
        result = gather(
            job,
            root=root,
            cookies_from_browser=cookies_from_browser,
            overwrite=overwrite,
        )
        entry = result.to_dict()
        entry["twos_thing_id"] = getattr(job, "thing_id", None)
        entry["twos_push"] = None

        if dest and result.status == "saved" and result.path:
            lib_path = root / result.path
            title = _title_from_library(lib_path) if lib_path.exists() else result.shortcode
            try:
                pushed = push_saved_item(
                    api,
                    list_id=dest.id,
                    title=title,
                    item_type=result.item_type or "other",
                    instagram_url=result.url or job.url,
                    library_path=lib_path if lib_path.exists() else None,
                    root=root,
                )
                entry["twos_push"] = {
                    "ok": True,
                    "thing_id": (pushed.get("id") or (pushed.get("thing") or {}).get("id")),
                }
            except Exception as exc:  # noqa: BLE001 — surface per-item failure, keep batch going
                entry["twos_push"] = {"ok": False, "error": str(exc)}

        batch.results.append(entry)

    return batch
