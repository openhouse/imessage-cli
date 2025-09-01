from __future__ import annotations

from enum import Enum


class TrustBadge(str, Enum):
    E2E_PRESERVED = "E2E_PRESERVED"
    LOCALLY_DECRYPTED = "LOCALLY_DECRYPTED"
    SERVER_BRIDGED = "SERVER_BRIDGED"
    PLAIN = "PLAIN"
    UNKNOWN = "UNKNOWN"


class BridgeMode(str, Enum):
    ON_DEVICE = "ON_DEVICE"
    RELAY = "RELAY"
    DIRECT = "DIRECT"
    NONE = "NONE"
