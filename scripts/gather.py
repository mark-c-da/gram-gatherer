"""CLI: Instagram URL(s) in, library markdown out.

Modes:
- single URL (original)
- --from-file — drain a URL list (Twos MCP path: agent writes the file after MCP read)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from adapters.url import get_job  # noqa: E402
from lib.batch_file import run_from_file  # noqa: E402
from lib.pipeline import gather  # noqa: E402

EXIT_BY_STATUS = {
    "saved": 0,
    "duplicate": 2,
    "needs_media": 3,
    "error": 1,
}


def _emit(payload: dict) -> None:
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Extract a recipe, book, album, workout, or other item from Instagram. "
            "Pass one URL, or drain a URL file with --from-file (Twos MCP path)."
        )
    )
    parser.add_argument(
        "url",
        nargs="?",
        default="",
        help="Instagram post or reel URL (or a shortcode). Omit when using --from-file.",
    )
    parser.add_argument(
        "--from-file",
        default="",
        metavar="PATH",
        help="Text file of Instagram URLs, one per line (optional: url | media_path)",
    )
    parser.add_argument(
        "--emit-twos-payload",
        action="store_true",
        help="With --from-file: include twos_mcp_writeback JSON for Cursor Twos MCP create_list/create_thing",
    )
    parser.add_argument(
        "--twos-source-title",
        default="",
        metavar="TITLE",
        help="Optional source Twos list title (names the suggested output list)",
    )
    parser.add_argument(
        "--twos-output-title",
        default="",
        metavar="TITLE",
        help="Optional title for the Twos output list in the emitted payload",
    )
    parser.add_argument(
        "--caption",
        default="",
        help="Caption pasted by the user when fetch fails or is thin (single-URL mode)",
    )
    parser.add_argument(
        "--media",
        action="append",
        default=[],
        metavar="PATH",
        help="Local video or image (repeatable). Use after a needs_media miss.",
    )
    parser.add_argument(
        "--cookies-from-browser",
        default="",
        metavar="BROWSER",
        help="yt-dlp cookies source, e.g. chrome, edge, firefox",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing library file for this shortcode",
    )
    args = parser.parse_args(argv)

    from_file = (args.from_file or "").strip()
    cookies = args.cookies_from_browser or None

    if from_file:
        if args.url:
            parser.error("Pass either a URL or --from-file, not both")
        if args.caption or args.media:
            parser.error("--caption / --media only apply to single-URL mode")
        try:
            batch = run_from_file(
                Path(from_file),
                root=ROOT,
                cookies_from_browser=cookies,
                overwrite=args.overwrite,
                emit_twos_payload=bool(args.emit_twos_payload),
                source_list_title=(args.twos_source_title or "").strip() or None,
                output_list_title=(args.twos_output_title or "").strip() or None,
            )
        except (OSError, ValueError) as exc:
            _emit({"status": "error", "message": str(exc)})
            return 1
        _emit(batch.to_dict())
        return EXIT_BY_STATUS.get(batch.worst_exit_status, 1)

    if args.emit_twos_payload or args.twos_source_title or args.twos_output_title:
        parser.error("--emit-twos-payload / --twos-*-title require --from-file")

    if not (args.url or "").strip():
        parser.error("Instagram URL is required unless --from-file is set")

    job = get_job(args.url, caption=args.caption or None, media_paths=args.media)
    result = gather(
        job,
        root=ROOT,
        cookies_from_browser=cookies,
        overwrite=args.overwrite,
    )
    _emit(result.to_dict())
    return EXIT_BY_STATUS.get(result.status, 1)


if __name__ == "__main__":
    sys.exit(main())
