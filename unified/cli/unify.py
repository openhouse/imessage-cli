from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from ..identity import contacts
from ..identity.contacts import build_resolver, expand_handles
from ..views.conversation import get_conversation, list_chats, render_markdown
from ..views.voice import render_voice_manuscript
from .person_resolver import (
    db_persons,
    guess_person_from_voice,
    print_persons_summary,
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="imx")
    parser.add_argument("--person")
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--jsonl", action="store_true")
    parser.add_argument("--group-by", choices=["none", "chat"], default="chat")
    parser.add_argument("--via-collapse", action="store_true", default=False)
    parser.add_argument("--contacts-vcf")
    parser.add_argument("--contacts-csv")
    parser.add_argument("--hide-plugin", action="store_true", default=True)
    parser.add_argument("--show-plugin", dest="hide_plugin", action="store_false")
    parser.add_argument("--list-chats", action="store_true")
    parser.add_argument("--chat")
    parser.add_argument("--out")
    parser.add_argument("--show-handles", action="store_true")
    parser.add_argument("--voice-of")
    parser.add_argument("--context", type=int, default=2)
    parser.add_argument("--quotes-only", action="store_true", default=False)
    parser.add_argument(
        "--list-persons",
        action="store_true",
        help="List local persons discovered in the event log and exit",
    )
    parser.add_argument(
        "--auto-person",
        action="store_true",
        help="If --person is omitted, try to auto-select using --voice-of (unique match)",
    )
    args = parser.parse_args(argv)
    def resolve_person() -> str:
        if args.person:
            person = args.person
            if person.startswith("did:"):
                return person
            from ..identity import did as did_module  # heavy import only when needed

            if "@" in person or person.startswith("+"):
                return did_module.resolve_handles_to_person([person])
            reg = did_module._load_registry()  # type: ignore[attr-defined]
            return next((d for d, info in reg.items() if info.get("label") == person), person)
        persons = db_persons()
        if args.list_persons:
            print_persons_summary()
            raise SystemExit(0)
        if len(persons) == 1:
            return persons[0]
        if args.auto_person and args.voice_of:
            auto, evidence = guess_person_from_voice(args.voice_of)
            if auto:
                print(f"Auto-selected person_did: {auto} (via --voice-of evidence)")
                return auto
        print("--person required (multiple persons found).")
        print_persons_summary()
        if args.voice_of and not args.auto_person:
            print(
                "\nHint: re-run with --auto-person (will select the unique match by --voice-of if possible)."
            )
        raise SystemExit(2)

    person_did = resolve_person()
    since = datetime.fromisoformat(args.since) if args.since else None
    until = datetime.fromisoformat(args.until) if args.until else None
    output = "jsonl" if args.jsonl else "objects"
    contacts.DEFAULT_VCF = Path(args.contacts_vcf) if args.contacts_vcf else None
    contacts.DEFAULT_CSV = Path(args.contacts_csv) if args.contacts_csv else None
    resolver = build_resolver(contacts.DEFAULT_VCF, contacts.DEFAULT_CSV)

    if args.voice_of:
        display, handles, explain = expand_handles(
            args.voice_of, contacts.DEFAULT_VCF, contacts.DEFAULT_CSV
        )
        print(
            f'Resolved "{display}" → {{{", ".join(sorted(handles))}}} ({len(handles)} handles)'
        )
        md = render_voice_manuscript(
            person_did,
            args.voice_of,
            since=since,
            until=until,
            context=args.context,
            quotes_only=args.quotes_only,
            show_handles=args.show_handles,
            via_collapse=args.via_collapse,
            hide_plugin_payload=args.hide_plugin,
            resolve_display=resolver,
        )
        if args.out:
            Path(args.out).write_text(md)
        else:
            print(md)
        return

    if args.list_chats:
        chats = list_chats(person_did, resolver)
        for c in chats:
            parts = ", ".join(c["participants"])
            print(f"{c['conversation_id']} · {c['count']} msgs · {parts}")
        return

    if args.chat:
        md = render_markdown(
            person_did,
            args.chat,
            resolve_display=resolver,
            show_handles=args.show_handles,
            hide_plugin_payload=args.hide_plugin,
            via_collapse=args.via_collapse,
        )
        if args.out:
            Path(args.out).write_text(md)
        else:
            print(md)
        return

    conv = get_conversation(
        person_did,
        since,
        until,
        output=output,
        group_by_conversation=(args.group_by == "chat"),
        via_collapse=args.via_collapse,
        resolve_display=resolver,
        hide_plugin_payload=args.hide_plugin,
    )
    if output == "jsonl":
        for line in conv:  # type: ignore[assignment]
            print(line)
    else:
        for item in conv:  # type: ignore[assignment]
            if item.get("kind") == "header":
                parts = ", ".join(item.get("participants", []))
                cid = item.get("conversation_id") or ""
                print(f"## Conversation {cid}\nParticipants: {parts}")
                continue
            text = item.get("text", "")
            via = item.get("via", [])
            via_s = f"  (via: {', '.join(via)})" if via else ""
            print(f"{item['timestamp']} — {item['who']}: {text}{via_s}")


if __name__ == "__main__":  # pragma: no cover
    main()
