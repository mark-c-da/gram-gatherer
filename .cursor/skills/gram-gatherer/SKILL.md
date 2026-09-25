---
name: gram-gatherer
description: Extracts recipes, books, albums, workouts, and other items from Instagram post and reel URLs into one markdown file per item. Use when the user pastes an Instagram link, asks to gather or extract a saved post or reel, or wants to add it to the library.
---

# Gram-gatherer

Turn one Instagram post/reel URL into a searchable markdown file under `library/`. Run the CLI; do not reimplement fetch, Whisper, OCR, or dedup in chat.

Repo root is the directory that contains `scripts/gather.py` and `library/`.

## When to use

- User pastes an `instagram.com` `/p/`, `/reel/`, or `/reels/` URL
- User asks to gather, extract, or save a saved Instagram post

Single-URL mode is still one URL per CLI invocation. If they paste several in chat, process sequentially. Prefer `--from-twos` when the links already live on a Twos list (Workflow 1).

## Workflow

```
Task Progress:
- [ ] Parse URL / shortcode
- [ ] Run gather.py — caption first; media only if caption is thin
- [ ] If needs_media: ask user, then re-run with --caption / --media
- [ ] If saved: optionally tidy title/fields from the Raw section
- [ ] Reply with type, path, sources_used
```

### Step 1 — Run the CLI

From repo root (`python` or `py -3` on Windows):

```bash
python scripts/gather.py "https://www.instagram.com/reel/SHORTCODE/"
```

Cookies (Instagram often requires a logged-in browser):

```bash
python scripts/gather.py "URL" --cookies-from-browser chrome
```

Use `edge` or `firefox` if that is where they are logged into Instagram. `GRAM_COOKIES_FROM_BROWSER` also works.

Optional user-supplied media (after a `needs_media` miss):

```bash
python scripts/gather.py "URL" --caption "pasted caption" --media "path/to/video.mp4" --media "path/to/slide.jpg"
```

`--overwrite` only if they explicitly ask to replace an existing entry.

### Step 2 — Read the JSON on stdout

| `status` | What to do |
|---|---|
| `saved` | Done. Tidy the markdown if title/fields are generic. Reply with `type`, `path`, `sources_used`. |
| `duplicate` | Tell them the existing `path`. Do not overwrite unless they ask. |
| `needs_media` | Stop. Ask for the caption and/or dropped video/screenshots. Re-run with `--caption` / `--media`. |
| `error` | Show `message`. Do not invent a library file by hand. |

If Whisper or OCR was skipped, say so. Still keep a caption-only file when `status` is `saved`.

### Step 3 — Fetch-then-ask (do not scrape)

Never log into Instagram in a browser automation loop. Never use Graph API.

The script already tries **yt-dlp**, then **oEmbed**. If that is thin, it returns `needs_media`. Then you ask:

- Paste the caption from the Instagram app
- Drop the saved video and/or carousel screenshots into chat
- Save attachments under `cache/<shortcode>/` and pass `--media`

Then re-run `gather.py` with those flags.

`cache/` is temporary. After a **saved** run, the CLI deletes `cache/<shortcode>/` so videos and slides do not pile up. Keep a `needs_media` cache until the item is actually saved.

## Extraction order

Caption is the first content check, not a fallback. Do not skip ahead to OCR or Whisper while a usable caption exists.

1. **Caption** (yt-dlp metadata or a pasted caption). If it already names the recipe, books, album, or workout, write the file and stop. No download, OCR, or Whisper.
2. **Carousel / stills** — OCR (Tesseract). If images are in chat, you may also read them with vision and merge useful text into the file after the CLI write.
3. **Reel / video** — audio then Whisper. Missing Whisper/ffmpeg is a skip, not a hard fail.

## Dedup

Key is the Instagram **shortcode**. `library/index.json` maps shortcode → relative path.

If `status` is `duplicate`, report the path and stop.

## Output files

One file per item: `library/<type>/{shortcode}-{slug}.md`

Types: `recipes` | `books` | `albums` | `workouts` | `other`

Frontmatter must keep `url`, `shortcode`, `type`, `author`, `extracted_at`, `sources_used`.

When tidying after `saved`, keep frontmatter and the `## Raw` section. Improve title and typed fields only.

### Recipe

```markdown
# Title

**Source:** @author

## Ingredients
- item

## Steps
1. step

## Notes

## Raw
```

### Book

```markdown
# Title

**Author:** name
**Why save:**

## Raw
```

### Album

```markdown
# Title

**Artist:** name
**Notes:**

## Raw
```

### Workout

```markdown
# Title

**Coach:** name
**Why save:**

## Session
- 3 rounds
- 20 jumping jacks

## Raw
```

### Other

```markdown
# Title

**Summary:**

## Raw
```

## Workflow 1 — Twos in + library + Twos out

When the user wants to drain a Twos list of Instagram links (and optionally write text back to Twos):

1. Confirm `TWOS_API_KEY` is set (or ask them to export it). Do not invent a key.
2. Run from repo root:

```bash
python scripts/gather.py --from-twos "LIST NAME OR ID" --to-twos
```

Use `--to-twos-list "Title"` to name the new output list. Omit `--to-twos` to only write `library/`.

3. Read the batch JSON: `results[]` entries use the same `status` values as single-URL mode. Each `saved` row may include `twos_push`.
4. For any `needs_media` row, ask for caption/media and re-run **that URL** in single-URL mode (batch does not accept `--caption` / `--media`).

## Input adapters

- `scripts/adapters/url.py` — single Instagram URL
- `scripts/adapters/twos.py` — Twos list → jobs (Workflow 1)
- `inbox.py` / `file.py` — still stubs unless the user asks

## Reply shape

After a successful save:

- **Type:** recipe | book | album | workout | other
- **File:** `library/...`
- **Sources:** caption / ocr / whisper / user-paste
- **Skipped:** whatever the JSON listed
