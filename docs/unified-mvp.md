# Unified Conversation MVP

This MVP stores events from local connectors (iMessage and email) in an append-only SQLite log under `~/.imx/unified/`. Keys and relationship credentials live in `~/.imx/unified/wallet/` and `people.json`.

## Threat Model
- Keys are stored locally on disk; protect `~/.imx/unified/` (0700 perms).
- Wallet key files are created with `0600` permissions.
- Deleting `~/.imx/unified/` (and any backups) removes all stored events and credentials ("vanish").
- Connectors access local databases in read-only mode; view building does not perform network calls.

## Usage
```
# List chats for a person
python -m unified.cli.unify --person "<did or handle>" --list-chats

# Render a chat to markdown
python -m unified.cli.unify --person "<did or handle>" --chat "<conversation_id>" --show-handles --out thread.md
```

### Voice view

Extract a person's authored lines across rooms with surrounding context:

```
python -m unified.cli.unify --voice-of lindseyagriffith@gmail.com --context 2 --out voice-lindsey.md
python -m unified.cli.unify --voice-of +13169921361 --quotes-only
```

`--context` controls how many neighboring messages to include on either side of
each authored line. `--quotes-only` lists only the target's messages while
keeping room headers for orientation.

### Choosing a person

The repository's `imx` helper script runs the `unify` CLI directly, so no subcommand is needed.

If your event log contains multiple local identities (multiple `person_did`s):

```bash
# List all persons with counts, date range, and services
imx --list-persons

# Let the CLI pick the person automatically when --voice-of uniquely identifies one
imx --auto-person --voice-of someone@example.com --context 2
```

If ambiguous, the CLI prints a summary and asks you to pass `--person`.
