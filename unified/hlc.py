from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Tuple


@dataclass
class HLC:
    wall_ms: int = 0
    counter: int = 0
    node_id: str = "local"

    def now(self) -> str:
        current_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        if current_ms > self.wall_ms:
            self.wall_ms = current_ms
            self.counter = 0
        else:
            self.counter += 1
        return f"{self.wall_ms}:{self.counter}:{self.node_id}"

    def merge(self, remote: str) -> str:
        r_wall, r_count, _ = self._parse(remote)
        wall = max(self.wall_ms, r_wall)
        if self.wall_ms == r_wall:
            count = max(self.counter, r_count) + 1
        elif wall == self.wall_ms:
            count = self.counter + 1
        else:
            count = r_count + 1
        self.wall_ms, self.counter = wall, count
        return f"{self.wall_ms}:{self.counter}:{self.node_id}"

    @staticmethod
    def _parse(hlc: str) -> Tuple[int, int, str]:
        wall, cnt, node = hlc.split(":")
        return int(wall), int(cnt), node

    @staticmethod
    def compare(a: str, b: str) -> int:
        aw, ac, an = HLC._parse(a)
        bw, bc, bn = HLC._parse(b)
        if (aw, ac, an) < (bw, bc, bn):
            return -1
        if (aw, ac, an) > (bw, bc, bn):
            return 1
        return 0
