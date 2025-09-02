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
