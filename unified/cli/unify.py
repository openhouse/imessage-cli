from __future__ import annotations

import argparse
from datetime import datetime

from ..identity import did as did_module
from ..views.conversation import get_conversation


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="imx unify")
    parser.add_argument("--person", required=True)
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--jsonl", action="store_true")
    args = parser.parse_args(argv)
    person = args.person
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
    conv = get_conversation(person_did, since, until, output=output)
    if output == "jsonl":
        for line in conv:  # type: ignore[assignment]
            print(line)
    else:
        for item in conv:  # type: ignore[assignment]
            text = item.get("text", "")
            print(f"{item['timestamp']} {item['who']}: {text}")


if __name__ == "__main__":  # pragma: no cover
    main()
