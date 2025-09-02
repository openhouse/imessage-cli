from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from ..identity.contacts import build_resolver
from ..views.conversation import get_conversation, list_chats, render_markdown


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="imx unify")
    parser.add_argument("--person", required=True)
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
    args = parser.parse_args(argv)
    person = args.person
    if person.startswith("did:"):
        person_did = person
    else:
        from ..identity import did as did_module  # heavy import only when needed
        if "@" in person or person.startswith("+"):
            person_did = did_module.resolve_handles_to_person([person])
        else:
            reg = did_module._load_registry()  # type: ignore[attr-defined]
            person_did = next(
                (d for d, info in reg.items() if info.get("label") == person), person
            )
    since = datetime.fromisoformat(args.since) if args.since else None
    until = datetime.fromisoformat(args.until) if args.until else None
    output = "jsonl" if args.jsonl else "objects"
    resolver = build_resolver(
        Path(args.contacts_vcf) if args.contacts_vcf else None,
        Path(args.contacts_csv) if args.contacts_csv else None,
    )

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
