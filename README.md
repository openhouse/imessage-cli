# imessage-cli

Export a **diarized** text/Markdown transcript of your 1‑to‑1 iMessage/SMS conversation with any phone number or email address on **macOS**.

- Merges multiple threads for the same person across numbers and email addresses.
- Drops tapbacks 👍❤️ but **keeps replies/threads**.
- Recovers text stored in `attributedBody` (macOS Sequoia and later).
- Lists attachments inline (filenames), with optional copying of files.
- Outputs Markdown (`.md`) by default (or plain `.txt`).
For pipelines, the `--jsonl` flag emits a stable JSON Lines stream which can be loaded into SQLite with `sqlite-utils` and explored using Datasette.

> Example of the output format (attachments listed inline):  
> `2025-05-25 19:21 — Jamie:  [attachments: flowers-apng.PNG]` :contentReference[oaicite:0]{index=0}

## Requirements

- macOS with Messages database at `~/Library/Messages/chat.db`
- Python 3.9+ (standard on recent macOS)
- Grant **Full Disk Access** to your terminal app (System Settings → Privacy & Security → Full Disk Access)

## Install (no pip needed)

```bash
git clone <this folder or copy by hand>
cd imessage-cli
chmod +x imx
```

## Usage

```bash
# Basic: export whole history with +1-443-204-2987
./imx +14432042987

# Merge across phone and email handles
./imx +14432042987 user@example.com

# Set labels
./imx +14432042987 --me "Jamie" --name "Sarah"

# Choose output path/format
./imx +14432042987 --out ~/Desktop/Sarah.md
./imx +14432042987 --txt      # plain text file

# Preserve real multi-line messages instead of ↵
./imx +14432042987 --multiline

# Copy attachments into a folder next to the transcript
./imx +14432042987 --copy-attachments

# Date filter (local dates)
./imx +14432042987 --since 2024-10-01 --until 2025-07-01

# Open transcript after export
./imx +14432042987 --open
```

**Tip:** Set your preferred “me” label once:

```bash
export IMX_ME="Jamie"
./imx +14432042987 --name "Sarah"
```

## Notes

- If you see `database is locked`, quit the Messages app and re‑run.
- If some history is only in iCloud and not downloaded locally, it won’t export until synced to this Mac.
- This tool reads `chat.db` in **read‑only** mode and does not modify your data.

## License

MIT — see `LICENSE`.
