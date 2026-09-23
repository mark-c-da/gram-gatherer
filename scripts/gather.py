"""CLI: one Instagram URL in, one library markdown file out."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from adapters.url import get_job  # noqa: E402
from lib.pipeline import gather  # noqa: E402

EXIT_BY_STATUS = {
    "saved": 0,
    "duplicate": 2,
    "needs_media": 3,
    "error": 1,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract a recipe, book, album, workout, or other item from one Instagram URL."
    )
    parser.add_argument("url", help="Instagram post or reel URL (or a shortcode)")
    parser.add_argument(
        "--caption",
        default="",
        help="Caption pasted by the user when fetch fails or is thin",
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

    job = get_job(args.url, caption=args.caption or None, media_paths=args.media)
    result = gather(
        job,
        root=ROOT,
        cookies_from_browser=args.cookies_from_browser or None,
        overwrite=args.overwrite,
    )
    json.dump(result.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return EXIT_BY_STATUS.get(result.status, 1)


if __name__ == "__main__":
    sys.exit(main())
