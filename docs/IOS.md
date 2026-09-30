# iOS capture — Shortcut → inbox → gather

Phone capture only dumps Instagram links. Extract still runs on a machine with
yt-dlp/cookies (desktop, Cursor Cloud with cookies, or a cron host). Cursor on
iPhone can *direct* an agent; it does not run `gather.py` on-device.

## Two capture targets

| Target | Phone does | Later drain |
|---|---|---|
| **A. Inbox file** | Shortcut appends URL to `inbox.txt` (iCloud-synced repo copy) | `python scripts/gather.py --from-inbox` |
| **B. Twos list** | Share / Twos app saves the link on a list | Path B (MCP) or C (REST) in [PATHS.md](PATHS.md) |

Prefer **A** when the repo lives in iCloud Drive (or another sync folder) and you
want a zero-API capture path. Prefer **B** when Twos is already the inbox.

## Inbox file format

Same as `--from-file`. One URL per line:

```text
# from Shortcut
https://www.instagram.com/reel/SHORTCODE/
https://www.instagram.com/p/SHORTCODE/
```

Optional local media (usually desktop-only): `url | path/to/file`.

Copy [inbox.example.txt](../inbox.example.txt) to `inbox.txt` at the repo root
(`inbox.txt` is gitignored). Or point `--from-inbox` at any synced path.

## Build the iOS Shortcut (inbox file)

1. **Shortcuts** app → **+** → name it e.g. `Save to gram-gatherer`.
2. **Add Action** → **Receive** → set to **URLs** (Share Sheet) and optionally **Safari web pages**.
3. **Get URLs from Input** (if the share is a Safari page / rich content).
4. **Append to File**:
   - File: `inbox.txt` inside your synced `gram-gatherer` folder (iCloud Drive → the repo, or a Shortcuts Folder that mirrors it).
   - Text to append: the Instagram URL, then a newline.
   - Enable **Make New File** so the first share creates `inbox.txt`.
5. Optional: **Show Notification** “Queued for gather”.
6. **Add to Share Sheet** / set **Share Sheet** details so Instagram’s Share menu lists it.

Share an Instagram post/reel → Shortcut → URL lands in `inbox.txt`. Sync must
finish before you drain on another device.

### If the repo is not in iCloud

- Shortcut appends to **iCloud Drive / Shortcuts / gram-inbox.txt**.
- On the gather machine: download/sync that file, or use
  `python scripts/gather.py --from-inbox ~/path/to/gram-inbox.txt`.
- Or use **Twos** as the capture target instead (table above).

## Drain on the gather machine

```bash
# Default path: <repo>/inbox.txt — clears saved/duplicate lines after run
python scripts/gather.py --from-inbox --cookies-from-browser opera

# Custom drop file
python scripts/gather.py --from-inbox ~/iCloud/Shortcuts/gram-inbox.txt

# Leave the file unchanged
python scripts/gather.py --from-inbox --keep-inbox
```

`needs_media` and `error` lines stay in the inbox so you can paste caption/media
and re-run. Optional `--emit-twos-payload` works the same as `--from-file` for
MCP write-back after drain.

## Twos-only phone path (no inbox file)

1. In Twos (or a Shortcut that creates a Twos thing), save the Instagram URL on
   a list such as `Saved Instagram`.
2. Later, from a machine with cookies:

```bash
# MCP (Cursor orchestrates) — see skill gram-gatherer-twos-mcp
# or REST:
export TWOS_API_KEY=twos_...
python scripts/gather.py --from-twos "Saved Instagram" --to-twos
```

## What not to do on iPhone

- Do not scrape Instagram in the Shortcut.
- Do not expect Whisper/OCR/cookies to run in Shortcuts or Cursor mobile alone.
- Do not put secrets (`TWOS_API_KEY`, browser cookie DBs) into the Shortcut.
