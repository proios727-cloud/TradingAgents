"""Live GEX map + forward-log CLI.

    python -m agent.gex_live SPY 739.6 spy_gex_chain.json
    python -m agent.gex_live QQQ 684.7 qqq_gex_chain.json

Renders the dealer-gamma map (net GEX, flip, walls, king node, regime, flow
skew, per-strike bars, and the entry gate) for a symbol, and APPENDS a compact
snapshot to .supertrades/gex_log.jsonl. The log is how you *forward-validate*
GEX: accumulate snapshots over sessions, then check whether the gate's calls
led anywhere (there is no free historical intraday chain to backtest against —
GEX must be measured going forward, not retro-fit).

The chain file is either a bare array of
    {strike, call_gamma, call_oi, put_gamma, put_oi, call_vol, put_vol}
rows, or an object {symbol, spot, rows:[...]}. Rows come from the Robinhood MCP
(get_option_instruments + get_option_quotes); this module only computes and
renders — the fetch is the operator's MCP step (Claude or a wired dispatcher).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

from .gex import StrikeGex, compute_gex, gex_confirms, flow_skew

_HOME = os.environ.get(
    "SUPERTRADES_HOME",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), ".supertrades"),
)
LOG = os.path.join(_HOME, "gex_log.jsonl")


def _rows(data) -> list[StrikeGex]:
    raw = data["rows"] if isinstance(data, dict) else data
    return [StrikeGex(r["strike"], r.get("call_gamma", 0), r.get("call_oi", 0),
                      r.get("put_gamma", 0), r.get("put_oi", 0),
                      r.get("call_vol", 0), r.get("put_vol", 0)) for r in raw]


def render(symbol: str, spot: float, rows: list[StrikeGex]) -> tuple[str, dict]:
    p = compute_gex(rows, spot)
    sk = flow_skew(p)
    long_ok, long_why = gex_confirms(p, "long", sk)
    short_ok, short_why = gex_confirms(p, "short", sk)
    b = 1e9
    side = "ABOVE" if spot >= p.flip else "BELOW"
    lines = [
        f"{symbol} GEX  (spot {spot:g}, {datetime.now(timezone.utc):%H:%M} UTC)",
        f"  net GEX    : {p.net_gex/b:+.2f} B/1%   -> {p.regime.upper()} gamma",
        f"  gamma flip : {p.flip:g}   (spot {side} flip)",
        f"  call wall  : {p.call_wall:g}     put wall: {p.put_wall:g}     king node: {p.king_node:g}",
        f"  flow skew  : {sk:+.2f}  (- = put-heavy)",
    ]
    mx = max((abs(g) for _, g in p.per_strike), default=1.0) or 1.0
    lines.append("  per-strike net GEX (B):")
    for s, g in p.per_strike:
        if abs(s - spot) <= 7:
            star = "*" if abs(s - spot) < 0.6 else " "
            bar = "#" * int(round(abs(g) / mx * 22))
            lines.append(f"   {s:>6g}{star} {'+' if g >= 0 else '-'}{abs(g)/b:5.2f} {bar}")
    lines.append(f"  gate long  : {long_ok}  ({long_why})")
    lines.append(f"  gate short : {short_ok}  ({short_why})")

    snap = {
        "ts": datetime.now(timezone.utc).isoformat(), "symbol": symbol, "spot": spot,
        "net_gex_b": round(p.net_gex / b, 3), "regime": p.regime, "flip": p.flip,
        "call_wall": p.call_wall, "put_wall": p.put_wall, "king_node": p.king_node,
        "skew": round(sk, 3), "long_gate": long_ok, "short_gate": short_ok,
    }
    return "\n".join(lines), snap


def log_snapshot(snap: dict) -> None:
    os.makedirs(_HOME, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(snap) + "\n")


# -- enriched, SCORABLE snapshot (for forward-validation) ------------------

def config_hash() -> str:
    """Pre-registration stamp: hash of the GEX constants + outcome definition,
    so a logged sample is tied to one frozen config."""
    import hashlib
    from .gex import MULTIPLIER, ONE_PCT
    from .gex_validate import EntryCfg
    c = EntryCfg()
    s = f"gex:{MULTIPLIER}:{ONE_PCT}|exit:{c.stop_pct}:{c.target_pct}"
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def _contract(c: dict) -> dict:
    """Normalize a quoted ATM contract into the scorable fields."""
    bid, ask = float(c.get("bid", 0) or 0), float(c.get("ask", 0) or 0)
    mid = (bid + ask) / 2 if (bid + ask) else float(c.get("mid", 0) or 0)
    spread = (ask - bid) / mid if mid > 0 else 1.0
    return {"option_id": c.get("option_id", ""), "strike": c.get("strike", 0),
            "expiry": c.get("expiry", ""), "delta": c.get("delta", 0),
            "bid": bid, "ask": ask, "mid": round(mid, 4),
            "spread_pct": round(spread, 4)}


def build_snapshot(symbol: str, spot: float, rows: list[StrikeGex],
                   call: dict, put: dict, session: str | None = None) -> dict:
    """A SCORABLE snapshot: the GEX map + gate decision + BOTH ATM contracts
    (the call a long would buy, the put a short would buy). `call`/`put` are
    quoted contracts {option_id, strike, expiry, delta, bid, ask} from the RH
    MCP. gate_dir is the XOR of the two gates (None if neither or both)."""
    import uuid
    from zoneinfo import ZoneInfo
    p = compute_gex(rows, spot)
    sk = flow_skew(p)
    long_ok, _ = gex_confirms(p, "long", sk)
    short_ok, _ = gex_confirms(p, "short", sk)
    gate = "long" if long_ok and not short_ok else "short" if short_ok and not long_ok else None
    now = datetime.now(timezone.utc)
    et = now.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    return {
        "snapshot_id": uuid.uuid4().hex[:12],
        "ts": now.isoformat(), "session": session or et,
        "symbol": symbol, "spot": spot, "flip": p.flip,
        "dist_to_flip": round(spot - p.flip, 2), "regime": p.regime,
        "net_gex_b": round(p.net_gex / 1e9, 3), "skew": round(sk, 3),
        "long_gate": long_ok, "short_gate": short_ok, "gate_dir": gate,
        "config_hash": config_hash(),
        "call": _contract(call), "put": _contract(put),
    }


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    if len(argv) < 3:
        print("usage: python -m agent.gex_live SYMBOL SPOT CHAINFILE [--no-log]")
        return 2
    symbol, spot, path = argv[0].upper(), float(argv[1]), argv[2]
    with open(path, encoding="utf-8") as f:
        rows = _rows(json.load(f))
    out, snap = render(symbol, spot, rows)
    print(out)
    if "--no-log" not in argv:
        log_snapshot(snap)
        print(f"\n  logged -> {LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
