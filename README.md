# gram-gatherer

Paste one Instagram post or reel URL into Cursor. The gram-gatherer skill runs a Python CLI that extracts a recipe, book, album, workout, or other item into a searchable markdown file.

Text files are the library. Instagram (and Twos) stay capture inboxes.

## Use it from chat

Paste a URL like `https://www.instagram.com/reel/SHORTCODE/`. The skill runs:

```bash
python scripts/gather.py "https://www.instagram.com/reel/SHORTCODE/"
```

If Instagram blocks the download, paste the caption and/or drop the video or screenshots, then re-run:

```bash
python scripts/gather.py "URL" --caption "pasted caption" --media "path/to/video.mp4"
```

One URL per run. Duplicates are skipped by Instagram shortcode (`library/index.json`).

## Layout

- `library/recipes/`, `library/books/`, `library/albums/`, `library/workouts/`, `library/other/` — one markdown file per item (this is the searchable library)
- `library/index.json` — shortcode → file path, used to skip duplicates
- `cache/` — temporary downloads only; deleted after a successful save (gitignored)
- `scripts/gather.py` — CLI
- `scripts/adapters/url.py` — v1 input (single URL). Stubs for inbox / Twos / URL-file sit next to it
- `.cursor/skills/gram-gatherer/SKILL.md` — agent workflow

## Setup

```bash
python -m pip install -r requirements.txt
```

On Windows, use `py -3` if `python` is not on PATH. Whisper and ffmpeg are installed for this Windows user (any project), not only gram-gatherer.

Instagram usually will not serve media anonymously. If yt-dlp fails, pass cookies from a browser where you are logged into Instagram:

```bash
python scripts/gather.py "URL" --cookies-from-browser chrome
```

`edge` and `firefox` work too. You can also set `GRAM_COOKIES_FROM_BROWSER`.

### Optional: OCR and Whisper

Caption is the first content check. If it already names the recipe, books, album, or workout, gather writes the file and does not download media, OCR, or transcribe. Carousel stills use OCR only after that. Reels use Whisper only after that. Missing tools skip that step.

- **OCR:** install [Tesseract](https://github.com/tesseract-ocr/tesseract), then `pip install pillow pytesseract`
- **Whisper (local):** machine-wide `faster-whisper` on your user Python. `ffmpeg` is on PATH. From any folder: `transcribe path\to\file.mp4`. Gram-gatherer also uses these. Reinstall with `py -3 -m pip install faster-whisper`.
- **Whisper (API):** `pip install openai` and set `OPENAI_API_KEY`

## CLI exit codes

| Code | JSON `status` | Meaning |
|---:|---|---|
| 0 | `saved` | Wrote `library/<type>/{shortcode}-{slug}.md` |
| 2 | `duplicate` | Shortcode already in `library/index.json` (use `--overwrite` to replace) |
| 3 | `needs_media` | Paste caption and/or drop media, then re-run |
| 1 | `error` | Bad URL or write failure |

## Later

Same pipeline, different shells: an app would queue URLs and search `library/`; an iPhone Shortcut should append URLs to an inbox file, not scrape Instagram. See `scripts/adapters/inbox.py`.
