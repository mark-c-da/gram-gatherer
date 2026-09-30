# Path triage — how to get Instagram saves into the library (and Twos)

Same extract pipeline (`scripts/gather.py` → `library/`). Different **shells** for where URLs come from and whether Twos is involved.

## Quick chooser

| Situation | Path | Twos auth |
|---|---|---|
| Paste one or a few IG links in chat | **A. Chat paste** | None |
| Twos MCP connected; interactive drain + write-back | **B. Twos MCP** (this PR) | Cursor MCP |
| Large backlog / cron / no Cursor in the loop | **C. Twos REST** (Workflow 1 PR) | `TWOS_API_KEY` |
| Agent or Shortcut already has a URL list file | **D. URL file** | None (optional MCP write-back later) |
| Phone capture only (no extract yet) | **E. Capture to Twos** | Twos app / Shortcut → Twos |

Redundancy is intentional: B and C both do “Twos in + library + Twos out.” Use B when MCP is handy; C when you need headless automation.

## Extract pipeline (shared by A–D)

```mermaid
flowchart TD
  url[Instagram URL] --> caption[Caption via yt-dlp + browser cookies]
  caption -->|sufficient| write[Write library markdown]
  caption -->|thin| media{Media?}
  media -->|carousel 2+ stills| ocr[OCR including HEIC]
  media -->|reel or video| whisper[Whisper]
  whisper -->|still thin| frames[Sample up to 12 frames by duration]
  frames --> frameOcr[ocr-frames]
  frames --> archive[archive/frames/shortcode]
  media -->|none| needs[needs_media]
  ocr --> write
  frameOcr --> write
  whisper -->|sufficient| write
```

Silent on-screen reels use frame OCR after Whisper. Sampled JPEGs are archived under `archive/frames/` for accuracy review (not cleared with `cache/`).

## A — Chat paste

1. User pastes Instagram URL(s).
2. Agent runs `python scripts/gather.py "URL"` (sequentially if several).
3. Library only, unless the agent also uses Twos MCP to write things by hand.

**Skill:** `gram-gatherer`

## B — Twos MCP (Cursor-orchestrated)

1. Agent uses Twos MCP `get_list` / `list_lists`.
2. Writes URLs to `cache/twos-mcp-urls.txt`.
3. `python scripts/gather.py --from-file cache/twos-mcp-urls.txt --emit-twos-payload`
4. Agent calls Twos MCP `create_list` + `create_thing(s)` from `twos_mcp_writeback`.

**Skill:** `gram-gatherer-twos-mcp`  
**Needs:** Twos MCP enabled in this Cursor session (desktop or cloud with MCP configured).

## C — Twos REST (CLI automation)

1. `export TWOS_API_KEY=twos_…`
2. `python scripts/gather.py --from-twos "List name" --to-twos`

Python owns both Twos read and write. No MCP required.

**Lives on:** Workflow 1 branch/PR (`cursor/twos-workflow-1-a782`). Merge both PRs to have B and C in one tree; then we can share URL-extraction helpers.

## D — URL file

```bash
python scripts/gather.py --from-file path/to/urls.txt
python scripts/gather.py --from-file path/to/urls.txt --emit-twos-payload
```

One Instagram URL per line; `#` comments allowed; optional `url | media_path`.

Used as the handoff format for path B. Fine on its own for any backlog sitting in a text file.

## E — Phone capture (Workflow 2, later)

iOS Shortcut / Twos app dumps links into a Twos list (or inbox file). Extract happens later via B or C when a machine with yt-dlp/cookies is available. Cursor on iPhone directs agents; it does not run `gather.py` on-device.

## Unification later

Candidate shared core (after both PRs land):

- `lib/instagram_urls.py` — URL extraction (this PR)
- `lib/twos_payload.py` — thing shape for MCP **and** REST create_thing bodies
- One batch runner with pluggable “source” and “sink” (file / MCP-agent / REST)

Until then: pick from the table; do not run B and C on the same list at the same time (duplicate library writes are skipped by shortcode; Twos write-back could double-create things).
