"""CLI: Instagram URL(s) in, library markdown out; optional Twos list in/out."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from adapters.url import get_job  # noqa: E402
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
            "Pass one URL, or drain a Twos list with --from-twos."
        )
    )
    parser.add_argument(
        "url",
        nargs="?",
        default="",
        help="Instagram post or reel URL (or a shortcode). Omit when using --from-twos.",
    )
    parser.add_argument(
        "--from-twos",
        default="",
        metavar="LIST",
        help="Twos list name or id whose things contain Instagram links (Workflow 1 input)",
    )
    parser.add_argument(
        "--to-twos",
        action="store_true",
        help="After each successful save, also create things on a new Twos list (Workflow 1 output)",
    )
    parser.add_argument(
        "--to-twos-list",
        default="",
        metavar="TITLE",
        help="Title for the new Twos output list (implies --to-twos). Default: Gathered from <source> — <date>",
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

    from_twos = (args.from_twos or "").strip()
    to_twos_list = (args.to_twos_list or "").strip() or None
    to_twos = bool(args.to_twos or to_twos_list)
    cookies = args.cookies_from_browser or None

    if from_twos:
        if args.url:
            parser.error("Pass either a URL or --from-twos, not both")
        if args.caption or args.media:
            parser.error("--caption / --media only apply to single-URL mode")
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

    if to_twos or to_twos_list:
        parser.error("--to-twos / --to-twos-list require --from-twos in this version")

    if not (args.url or "").strip():
        parser.error("Instagram URL is required unless --from-twos is set")

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
