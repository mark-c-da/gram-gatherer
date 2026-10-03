---
name: gram-gatherer-twos-mcp
description: Drain Instagram links from a Twos list via Twos MCP, run gram-gatherer into library/, then write extracted text back to a new Twos list through MCP. Use when Twos MCP is connected in Cursor and the user wants interactive Twos in/out without TWOS_API_KEY.
---

# Gram-gatherer — Twos MCP path

This path uses **Cursor’s Twos MCP connection** for Twos I/O. The Python CLI only extracts into `library/` and emits a write-back payload. It does **not** call the Twos REST API.

Repo root contains `scripts/gather.py` and `library/`.

For headless backlog automation (`TWOS_API_KEY`, `--from-twos`), see the separate REST Workflow 1 branch / PR and [docs/PATHS.md](../../../docs/PATHS.md).

## When to use

- Twos MCP is connected in this Cursor session
- User wants: Twos list of IG links → gather → library **and** a new Twos list with text
- Interactive / desk session (not cron, not phone automation alone)

## Workflow

```
Task Progress:
- [ ] Confirm Twos MCP tools are available (list_lists / get_list / create_list / create_thing)
- [ ] Resolve source list (name from user or list_lists)
- [ ] Extract Instagram URLs from things (url field + text/note)
- [ ] Write URLs to cache/twos-mcp-urls.txt
- [ ] Run gather.py --from-file … --emit-twos-payload
- [ ] For needs_media rows: ask user; re-run those URLs singly
- [ ] create_list + create_thing(s) from twos_mcp_writeback via MCP
- [ ] Reply with library paths and new Twos list title
```

### Step 1 — Read the Twos list (MCP)

Use Twos MCP:

1. `list_lists` if you need to find the list
2. `get_list` for the chosen list (things in display order)

Collect Instagram post/reel URLs from each thing’s `url`, `text`, and `note`. Deduplicate by shortcode.

### Step 2 — Hand off to the CLI

Write one URL per line to `cache/twos-mcp-urls.txt` (gitignored under `cache/`).

```bash
python scripts/gather.py --from-file cache/twos-mcp-urls.txt --emit-twos-payload \
  --twos-source-title "SOURCE LIST TITLE"
```

Optional: `--twos-output-title "Custom gathered list name"`.

Cookies if Instagram blocks anonymous fetch:

```bash
python scripts/gather.py --from-file cache/twos-mcp-urls.txt --emit-twos-payload \
  --cookies-from-browser chrome
```

Opera is the browser that works on this machine. Cookies are copied once for the file; each URL then does one metadata call, and a second call only when the caption is thin (thumbnails for an image carousel, the video for a reel).

### Step 3 — Handle per-URL statuses

Same codes as single-URL gather (`saved` / `duplicate` / `needs_media` / `error`).

For `needs_media`, stop that URL only: ask for caption/media, then:

```bash
python scripts/gather.py "URL" --caption "…" --media "…"
```

Then rebuild write-back from saved library files, or re-run the file batch with `--overwrite` only if the user asked.

### Step 4 — Write back via Twos MCP

The CLI JSON includes `twos_mcp_writeback`:

- `create_list` → call MCP `create_list` (title + emoji)
- `things[]` → call MCP `create_thing` or `create_things` on the new list  
  Each thing: `text`, `type: note`, `url` (Instagram), `note` (library markdown body), `tags`

Do **not** invent Twos ids. Use the list id returned by `create_list`.

### Step 5 — Reply

- Source Twos list
- New Twos list title / id
- Each item: type, `library/…` path, MCP write ok/fail
- Any `needs_media` / errors left

## Do not

- Call Twos REST or require `TWOS_API_KEY` on this path
- Scrape Instagram in a browser automation loop
- Skip the CLI and hand-write library files
- Use this skill when Twos MCP tools are missing — fall back to paste URLs, `--from-file` only, or the REST Workflow 1 path
