# imessage-cli

Export **room‑centric** Markdown transcripts from iMessage on macOS with correct speaker attribution and a clear participants header.
Works from your local `~/Library/Messages/chat.db` in **read‑only** mode. (Email threads are ingested separately; the CLI here focuses on iMessage rooms.)

- Correct author attribution via `message.handle_id → handle.id`
- Group chats supported; participants derived from `chat_handle_join`
- Local‑first contacts resolution (people.json + VCF/CSV + optional macOS Contacts)
- Cleans URL artifacts (`ttps://`, trailing `WHttpURL/`)
- Hides Apple link‑preview `.pluginPayloadAttachment` **only when** the message already contains a URL (evidence stays intact)
- Optional `--via-collapse` dedupes duplicate deliveries (e.g., SMS vs iMessage) within 120s for the same sender/text

> Example line format:  
> `2025-05-25 19:21 — Jamie: see https://example.com`

## Requirements

- macOS with Messages database at `~/Library/Messages/chat.db`
- Python 3.9+
- **Full Disk Access** granted to your terminal app (System Settings → Privacy & Security → Full Disk Access)

## Install

```bash
git clone <this repo>
cd imessage-cli
# optional convenience shim:
printf '%s\n' '#!/usr/bin/env bash' 'exec python -m unified.cli.unify "$@"' > imx && chmod +x imx
```

## Quick start

List your chats (by GUID and display name if present):

```bash
python -m unified.cli.unify --person "+14105551234" --list-chats
# or with the shim:
./imx --person "+14105551234" --list-chats
```

Export a single chat (by GUID or name) to Markdown:

```bash
python -m unified.cli.unify --person "+14105551234" \
  --chat "iMessage;-;1234567890ABCDEF" \
  --out ~/Desktop/thread.md
```

Resolve names from your contacts and show raw handles in parentheses:

```bash
python -m unified.cli.unify --person "+14105551234" \
  --chat "Family Group" \
  --contacts-vcf ~/Desktop/Contacts.vcf \
  --show-handles \
  --out family.md
```

Date filters (ISO 8601 or `YYYY-MM-DD`):

```bash
python -m unified.cli.unify --person "+14105551234" \
  --chat "Family Group" \
  --since 2025-01-01 --until 2025-06-30 \
  --out family-2025H1.md
```

Optionally collapse duplicate deliveries (e.g., SMS + iMessage of the same text):

```bash
python -m unified.cli.unify --person "+14105551234" \
  --chat "Family Group" \
  --via-collapse \
  --out family-collapsed.md
```

## Options (selected)

* `--person "<did|email|phone>"` — person context for listing/rendering
* `--list-chats` — print chats with counts and participants
* `--chat "<guid|name>"` — render a single room to Markdown
* `--out <path>` — write to file (stdout if omitted)
* `--contacts-vcf <file>` / `--contacts-csv <file>` — local contact sources
* `--show-handles` — append `(<mailto:/tel:...>)` after names
* `--since <iso>` / `--until <iso>` — time filter
* `--via-collapse` — merge duplicate deliveries (120s bucket, same text/sender)
* `--hide-plugin` / `--show-plugin` — control link‑preview attachment visibility

## Notes & limitations

* Reads `chat.db` in **read‑only** mode; no network calls.
* If some messages are only in iCloud and not on this Mac, they won’t appear until synced locally.
* Reactions (tapbacks) are retained in the data model; the plain text renderer may not print them.
* We currently do **not** copy attachment files; filenames are listed inline.
* We do **not** (yet) recover `attributedBody` content.

## Security

* Data and caches live under `~/.imx/unified/` (directory is created with restrictive permissions).
* Contacts resolution is local‑first (people.json + VCF/CSV + optional macOS Contacts via AppleScript).

## License

MIT — see `LICENSE`.

## 🧭 "Old → New" migration cheatsheet (keep at bottom or in a `MIGRATING.md`)

- **Old:** `./imx +14432042987` (1‑to‑1 export)  
  **New:** `python -m unified.cli.unify --person "+14432042987" --list-chats` → pick a room → `--chat "<guid|name>" --out file.md`

- **Old:** "merge across phone + email" (always)  
  **New:** transports are separate by default; use `--via-collapse` to coalesce **duplicate deliveries only**.

- **Old:** "copies attachments"  
  **New:** lists filenames only (copying: future enhancement).

