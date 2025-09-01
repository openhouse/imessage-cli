from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import List

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature

from . import wallet


def _sign_bytes(data: bytes) -> bytes:
    pub, priv = wallet.get_or_create_keypair()
    key = Ed25519PrivateKey.from_private_bytes(priv)
    return key.sign(data)


def _pub_key() -> Ed25519PublicKey:
    pub, _ = wallet.get_or_create_keypair()
    return Ed25519PublicKey.from_public_bytes(pub)


def create_vc(subject_did: str, handles: List[str], evidence: List[str]) -> dict:
    vc = {
        "@context": ["https://www.w3.org/2018/credentials/v2"],
        "type": ["VerifiableCredential", "RelationshipCredential"],
        "issuer": "did:me:local",
        "subject": subject_did,
        "claims": {"handles": [{"kind": "handle", "value": h} for h in handles]},
        "evidence": evidence,
        "issuanceDate": datetime.now(tz=timezone.utc).isoformat(),
        "expirationDate": None,
    }
    sign(vc)
    return vc


def sign(vc: dict) -> None:
    payload = json.dumps(vc, sort_keys=True).encode("utf-8")
    sig = _sign_bytes(payload)
    vc["proof"] = {
        "type": "Ed25519",
        "jws": base64.urlsafe_b64encode(sig).decode("ascii"),
    }


def verify(vc: dict) -> bool:
    proof = vc.get("proof")
    if not proof:
        return False
    sig = base64.urlsafe_b64decode(proof["jws"])
    vc_copy = vc.copy()
    vc_copy.pop("proof", None)
    payload = json.dumps(vc_copy, sort_keys=True).encode("utf-8")
    try:
        _pub_key().verify(sig, payload)
        return True
    except InvalidSignature:
        return False
