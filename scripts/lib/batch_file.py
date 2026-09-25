"""Sequential gather from a URL file (Twos MCP path handoff)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from adapters.file import get_jobs
from lib.pipeline import gather
from lib.twos_payload import batch_writeback_payload


@dataclass
class FileBatchResult:
    source_file: str
    results: list[dict] = field(default_factory=list)
    twos_mcp_writeback: dict | None = None

    def to_dict(self) -> dict:
        out = {
            "source_file": self.source_file,
            "count": len(self.results),
            "results": self.results,
        }
        if self.twos_mcp_writeback is not None:
            out["twos_mcp_writeback"] = self.twos_mcp_writeback
        return out

    @property
    def worst_exit_status(self) -> str:
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


def run_from_file(
    path: Path,
    *,
    root: Path,
    cookies_from_browser: str | None = None,
    overwrite: bool = False,
    emit_twos_payload: bool = False,
    source_list_title: str | None = None,
    output_list_title: str | None = None,
) -> FileBatchResult:
    jobs = get_jobs(path)
    batch = FileBatchResult(source_file=str(path))
    if not jobs:
        raise ValueError(f"No Instagram URLs found in {path}")

    for job in jobs:
        result = gather(
            job,
            root=root,
            cookies_from_browser=cookies_from_browser,
            overwrite=overwrite,
        )
        batch.results.append(result.to_dict())

    if emit_twos_payload:
        batch.twos_mcp_writeback = batch_writeback_payload(
            results=batch.results,
            root=root,
            source_list_title=source_list_title,
            output_list_title=output_list_title,
        )
    return batch
