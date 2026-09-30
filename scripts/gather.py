"""CLI: Instagram URL(s) in, library markdown out.

Modes:
- single URL
- --from-file — URL list (Twos MCP handoff: agent writes the file after MCP read)
- --from-inbox — drain Shortcut / iCloud ``inbox.txt`` (clears saved/duplicate lines)
- --from-twos — drain a Twos list via REST (TWOS_API_KEY); optional --to-twos write-back
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
from lib.batch_inbox import run_from_inbox  # noqa: E402
from lib.batch_twos import run_from_twos  # noqa: E402
from lib.pipeline import gather  # noqa: E402
from lib.twos_client import TwosError  # noqa: E402

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
            "Pass one URL, --from-file, --from-inbox, or --from-twos (REST)."
        )
    )
    parser.add_argument(
        "url",
        nargs="?",
        default="",
        help="Instagram post or reel URL (or a shortcode). Omit when using --from-file / --from-inbox / --from-twos.",
    )
    parser.add_argument(
        "--from-file",
        default="",
        metavar="PATH",
        help="Text file of Instagram URLs, one per line (optional: url | media_path)",
    )
    parser.add_argument(
        "--from-inbox",
        nargs="?",
        const="inbox.txt",
        default="",
        metavar="PATH",
        help=(
            "Drain the Shortcut/iCloud inbox file (default: inbox.txt at repo root). "
            "Removes saved/duplicate lines unless --keep-inbox."
        ),
    )
    parser.add_argument(
        "--keep-inbox",
        action="store_true",
        help="With --from-inbox: do not rewrite the inbox after drain",
    )
    parser.add_argument(
        "--emit-twos-payload",
        action="store_true",
        help="With --from-file / --from-inbox: include twos_mcp_writeback JSON for Cursor Twos MCP create_list/create_thing",
    )
    parser.add_argument(
        "--twos-source-title",
        default="",
        metavar="TITLE",
        help="Optional source Twos list title (names the suggested MCP output list)",
    )
    parser.add_argument(
        "--twos-output-title",
        default="",
        metavar="TITLE",
        help="Optional title for the Twos output list in the emitted MCP payload",
    )
    parser.add_argument(
        "--from-twos",
        default="",
        metavar="LIST",
        help="Twos list name or id whose things contain Instagram links (REST; needs TWOS_API_KEY)",
    )
    parser.add_argument(
        "--to-twos",
        action="store_true",
        help="With --from-twos: after each successful save, create things on a new Twos list",
    )
    parser.add_argument(
        "--to-twos-list",
        default="",
        metavar="TITLE",
        help="Title for the new Twos REST output list (implies --to-twos). Default: Gathered from <source> — <date>",
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
        help="yt-dlp cookies source, e.g. chrome, edge, firefox, opera",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing library file for this shortcode",
    )
    args = parser.parse_args(argv)

    from_file = (args.from_file or "").strip()
    from_inbox = args.from_inbox  # already "" or path; const default when flag alone
    from_twos = (args.from_twos or "").strip()
    to_twos_list = (args.to_twos_list or "").strip() or None
    to_twos = bool(args.to_twos or to_twos_list)
    cookies = args.cookies_from_browser or None
    modes = [bool(from_file), bool(from_inbox), bool(from_twos)]
    if sum(modes) > 1:
        parser.error("Pass only one of --from-file, --from-inbox, or --from-twos")

    if args.keep_inbox and not from_inbox:
        parser.error("--keep-inbox requires --from-inbox")

    if from_file:
        if args.url:
            parser.error("Pass either a URL or --from-file, not both")
        if args.caption or args.media:
            parser.error("--caption / --media only apply to single-URL mode")
        if to_twos or to_twos_list:
            parser.error("--to-twos / --to-twos-list require --from-twos (REST), not --from-file")
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

    if from_inbox:
        if args.url:
            parser.error("Pass either a URL or --from-inbox, not both")
        if args.caption or args.media:
            parser.error("--caption / --media only apply to single-URL mode")
        if to_twos or to_twos_list:
            parser.error("--to-twos / --to-twos-list require --from-twos (REST), not --from-inbox")
        try:
            batch = run_from_inbox(
                from_inbox,
                root=ROOT,
                cookies_from_browser=cookies,
                overwrite=args.overwrite,
                clear_done=not args.keep_inbox,
                emit_twos_payload=bool(args.emit_twos_payload),
                source_list_title=(args.twos_source_title or "").strip() or None,
                output_list_title=(args.twos_output_title or "").strip() or None,
            )
        except (OSError, ValueError) as exc:
            _emit({"status": "error", "message": str(exc)})
            return 1
        _emit(batch.to_dict())
        return EXIT_BY_STATUS.get(batch.worst_exit_status, 1)

    if from_twos:
        if args.url:
            parser.error("Pass either a URL or --from-twos, not both")
        if args.caption or args.media:
            parser.error("--caption / --media only apply to single-URL mode")
        if args.emit_twos_payload or args.twos_source_title or args.twos_output_title:
            parser.error("--emit-twos-payload / --twos-*-title are for --from-file / --from-inbox, not --from-twos")
        try:
            batch = run_from_twos(
                from_twos,
                root=ROOT,
                to_twos=to_twos,
                to_twos_list=to_twos_list,
                cookies_from_browser=cookies,
                overwrite=args.overwrite,
            )
        except TwosError as exc:
            _emit({"status": "error", "message": str(exc)})
            return 1
        _emit(batch.to_dict())
        return EXIT_BY_STATUS.get(batch.worst_exit_status, 1)

    if args.emit_twos_payload or args.twos_source_title or args.twos_output_title:
        parser.error("--emit-twos-payload / --twos-*-title require --from-file or --from-inbox")
    if to_twos or to_twos_list:
        parser.error("--to-twos / --to-twos-list require --from-twos")

    if not (args.url or "").strip():
        parser.error("Instagram URL is required unless --from-file, --from-inbox, or --from-twos is set")

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
