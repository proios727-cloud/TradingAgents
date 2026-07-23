"""Append-only decision log (JSONL).

Every decision — signal, sizing calc, reject reason, preview, order, fill, exit,
kill — is appended as one JSON line. This is the audit trail that also feeds the
terminal's P&L view and trade journal. Never rewritten in place.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import MARKET_TZ
from .models import Decision


class DecisionLog:
    def __init__(self, path: str | Path = "decisions.jsonl"):
        self.path = Path(path)

    def record(self, kind: str, symbol: str, now: datetime, **detail) -> Decision:
        d = Decision(
            ts=now.astimezone(MARKET_TZ).isoformat(),
            kind=kind,
            symbol=symbol,
            detail=detail,
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": d.ts, "kind": d.kind,
                                "symbol": d.symbol, **d.detail}) + "\n")
        return d
