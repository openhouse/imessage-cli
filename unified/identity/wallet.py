from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

WALLET_DIR = Path.home() / ".imx/unified/wallet"
PRIV_PATH = WALLET_DIR / "ed25519.key"
PUB_PATH = WALLET_DIR / "ed25519.pub"


def get_or_create_keypair() -> Tuple[bytes, bytes]:
    WALLET_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(WALLET_DIR, 0o700)
    if PRIV_PATH.exists() and PUB_PATH.exists():
        priv_bytes = PRIV_PATH.read_bytes()
        pub_bytes = PUB_PATH.read_bytes()
        return pub_bytes, priv_bytes
    priv = Ed25519PrivateKey.generate()
    priv_bytes = priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    pub_bytes = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    PRIV_PATH.write_bytes(priv_bytes)
    PUB_PATH.write_bytes(pub_bytes)
    os.chmod(PRIV_PATH, 0o600)
    os.chmod(PUB_PATH, 0o600)
    return pub_bytes, priv_bytes


def store_vc(vc: dict) -> str:
    WALLET_DIR.mkdir(parents=True, exist_ok=True)
    vc_id = f"vc-{uuid.uuid4()}"
    path = WALLET_DIR / f"{vc_id}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(vc, f, indent=2)
    return vc_id


def load_vc(vc_id: str) -> dict:
    path = WALLET_DIR / f"{vc_id}.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
