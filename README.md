# gram-gatherer

Paste one Instagram post or reel URL into Cursor. The gram-gatherer skill runs a Python CLI that extracts a recipe, book, album, workout, or other item into a searchable markdown file.

Markdown under `library/` is the searchable store. Twos can be a **capture inbox** (list of Instagram links) and, in Workflow 1, also receive the extracted text back on a **new list** (API things — not `.txt` files).

## Use it from chat

Paste a URL like `https://www.instagram.com/reel/SHORTCODE/`. The skill runs:

```bash
python scripts/gather.py "https://www.instagram.com/reel/SHORTCODE/"
```

If Instagram blocks the download, paste the caption and/or drop the video or screenshots, then re-run:

```bash
python scripts/gather.py "URL" --caption "pasted caption" --media "path/to/video.mp4"
```

One URL per run (single-URL mode). Duplicates are skipped by Instagram shortcode (`library/index.json`).

### Workflow 1 — Twos list in, library + Twos list out

1. Put Instagram post/reel links on a Twos list (thing `url` field and/or links in the text).
2. Set `TWOS_API_KEY` (Twos → Settings → Advanced → API Keys; needs `read:lists`, `write:lists`, `write:things`).
3. Drain the list sequentially:

```bash
export TWOS_API_KEY=twos_...
python scripts/gather.py --from-twos "Saved Instagram" --to-twos
```

Optional: `--to-twos-list "My gathered books"` sets the new output list title (implies `--to-twos`). Default title is `Gathered from <source> — YYYY-MM-DD`.

Each successful save still writes `library/...`. It also creates a Twos thing on the new list: title line, Instagram `url`, and the markdown body as the thing’s long-form `note`.

`--from-twos` alone drains into the library without write-back.

## Layout

- `library/recipes/`, `library/books/`, `library/albums/`, `library/workouts/`, `library/other/` — one markdown file per item (this is the searchable library)
- `library/index.json` — shortcode → file path, used to skip duplicates
- `cache/` — temporary downloads only; deleted after a successful save (gitignored)
- `scripts/gather.py` — CLI (single URL or `--from-twos`)
- `scripts/adapters/url.py` — single-URL input
- `scripts/adapters/twos.py` — Twos list → Instagram jobs
- `scripts/lib/twos_client.py` / `twos_out.py` — Twos REST + write-back
- `.cursor/skills/gram-gatherer/SKILL.md` — agent workflow

## Setup

```bash
python -m pip install -r requirements.txt
```

On Windows, use `py -3` if `python` is not on PATH. Whisper and ffmpeg are installed for this Windows user (any project), not only gram-gatherer.

For Workflow 1, also export `TWOS_API_KEY`.

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

Phone (Workflow 2): iOS Shortcut / Cursor mobile for Twos **output** without draining a Twos inbox. Inbox file drain remains a stub — see `scripts/adapters/inbox.py`.
