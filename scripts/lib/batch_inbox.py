"""Sequential gather from the phone / Shortcut inbox file."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from adapters.inbox import get_jobs, resolve_inbox_path, rewrite_inbox
from lib.pipeline import gather
from lib.twos_payload import batch_writeback_payload

# Shortcodes with these statuses leave the inbox after a successful drain.
DONE_STATUSES = frozenset({"saved", "duplicate"})


@dataclass
class InboxBatchResult:
    source_file: str
    results: list[dict] = field(default_factory=list)
    remaining_lines: int | None = None
    twos_mcp_writeback: dict | None = None

    def to_dict(self) -> dict:
        out: dict = {
            "source_file": self.source_file,
            "count": len(self.results),
            "results": self.results,
        }
        if self.remaining_lines is not None:
            out["remaining_lines"] = self.remaining_lines
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


def run_from_inbox(
    path: str | Path | None = None,
    *,
    root: Path,
    cookies_from_browser: str | None = None,
    overwrite: bool = False,
    clear_done: bool = True,
    emit_twos_payload: bool = False,
    source_list_title: str | None = None,
    output_list_title: str | None = None,
) -> InboxBatchResult:
    inbox = resolve_inbox_path(path, root=root)
    jobs = get_jobs(inbox)
    batch = InboxBatchResult(source_file=str(inbox))
    if not jobs:
        if not inbox.is_file():
            raise ValueError(
                f"Inbox not found: {inbox}. Create it (see inbox.example.txt) "
                "or point --from-inbox at your Shortcut drop file."
            )
        raise ValueError(f"No Instagram URLs found in {inbox}")

    for job in jobs:
        result = gather(
            job,
            root=root,
            cookies_from_browser=cookies_from_browser,
            overwrite=overwrite,
        )
        batch.results.append(result.to_dict())

    if clear_done:
        keep: set[str] = set()
        for row in batch.results:
            short = str(row.get("shortcode") or "")
            status = str(row.get("status") or "")
            if short and status not in DONE_STATUSES:
                keep.add(short)
        remaining = rewrite_inbox(inbox, keep_shortcodes=keep)
        # Count non-empty, non-comment lines still pending
        batch.remaining_lines = sum(
            1 for line in remaining if line.strip() and not line.strip().startswith("#")
        )

    if emit_twos_payload:
        batch.twos_mcp_writeback = batch_writeback_payload(
            results=batch.results,
            root=root,
            source_list_title=source_list_title or "iOS inbox",
            output_list_title=output_list_title,
        )
    return batch
