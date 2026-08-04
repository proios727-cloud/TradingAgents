"""Run one orchestrated SuperTrades cycle.

The live loop's fetch step (the session's Robinhood MCP tools — the project's
ONE authenticated broker path) writes a snapshot JSON, then runs:

    python -m supertrades.engine.run_cycle \
        --state supertrades/state.json --snapshot /path/to/snapshot.json

which prints the cycle report (console payload + actions + guardrail audit)
as JSON on stdout. The loop then executes actions via MCP and updates the
pages/state per supertrades-v3.md. No broker call ever happens in-process.

    python -m supertrades.engine.run_cycle --selftest

builds a synthetic snapshot from state.json and runs a full offline cycle —
this is what a freshly resurrected session runs to prove the engine is green.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import sys
from pathlib import Path

from .discovery import build_nodes, expected_node_count
from .orchestrator import Orchestrator
from .reporter import make_final_reporter, summarizer


def synthetic_snapshot(state: dict, *, et_time: str = "10:15",
                       day_realized: float = 0.0, bp: float = 303.20,
                       auto_entries_used: int = 0,
                       option_overrides: dict | None = None,
                       quote_overrides: dict | None = None) -> dict:
    """Deterministic offline snapshot covering every node's inputs."""
    quotes, vwap = {}, {}
    for i, sym in enumerate(state.get("universe", [])):
        last = 100.0 + 5 * i
        pct = round((-2.5 + i * 0.55) % 5 - 2.0, 2)
        quotes[sym] = {"last": last, "prev_close": round(last / (1 + pct / 100), 2),
                       "day_pct": pct, "rvol": 1.5}
        vwap[sym] = last - 0.5
    for sym, q in (quote_overrides or {}).items():
        quotes.setdefault(sym, {}).update(q)

    option_quotes = {}
    for pid, pos in state.get("positions", {}).items():
        entry = pos.get("entry", 1.0)
        option_quotes[pid] = {"mark": round(entry * 1.1, 2), "bid": round(entry, 2),
                              "ask": round(entry * 1.2, 2), "delta": 0.35,
                              "gamma": 0.02, "oi": 1500, "volume": 300,
                              "spread_pct": 8.0, "iv": 0.45, "iv_rank": 0.5}
    for row in state.get("watchlist", []):
        option_quotes[row["id"]] = {"mark": 0.55, "bid": 0.50, "ask": 0.60,
                                    "delta": 0.34, "gamma": 0.03, "oi": 2000,
                                    "volume": 800, "spread_pct": 9.0,
                                    "iv": 0.45, "iv_rank": 0.5}
    for oid, q in (option_overrides or {}).items():
        option_quotes.setdefault(oid, {}).update(q)

    gex = {}
    for sym, cls in state.get("ticker_classes", {}).items():
        if cls != "index":
            continue
        spot = quotes[sym]["last"]
        strikes = {}
        for j in range(-3, 4):
            k = round(spot + 5 * j)
            strikes[str(k)] = {"call_oi": 4000 + 900 * (3 - abs(j)),
                               "call_gamma": 0.03, "put_oi": 3000 + 400 * abs(j),
                               "put_gamma": 0.025, "call_volume": 2500,
                               "put_volume": 1800, "call_mark": 1.2, "put_mark": 1.0}
        gex[sym] = {"spot": spot, "strikes": strikes}

    return {"asof_utc": "SYNTHETIC", "et_time": et_time, "weekday": True,
            "account": {"bp": bp, "day_realized": day_realized,
                        "auto_entries_used": auto_entries_used,
                        "manual_round_trips": 0, "halted": False},
            "quotes": quotes, "option_quotes": option_quotes,
            "positions": state.get("positions", {}),
            "candidates": state.get("watchlist", []),
            "gex": gex, "vwap": vwap,
            "prior": {"marks": {}, "cum_volume": {}, "day_pct": {},
                      "crossed_2pct": []}}


async def run_one_cycle(state: dict, snapshot: dict,
                        today: dt.date | None = None) -> dict:
    nodes = build_nodes(state, today)
    expected = expected_node_count(state)
    if len(nodes) != expected:
        raise RuntimeError(f"node count {len(nodes)} != contract {expected}")
    orch = Orchestrator(batch_size=30)
    report = await orch.run(nodes, snapshot, summarizer, make_final_reporter(state))
    report["meta"]["expected_node_count"] = expected
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", default="supertrades/state.json")
    ap.add_argument("--snapshot", help="snapshot JSON written by the MCP fetch step")
    ap.add_argument("--today", help="YYYY-MM-DD for expiry math (defaults: snapshot asof date if parseable)")
    ap.add_argument("--selftest", action="store_true",
                    help="run offline against a synthetic snapshot")
    args = ap.parse_args(argv)

    state = json.loads(Path(args.state).read_text())
    if args.selftest:
        snapshot = synthetic_snapshot(state)
    elif args.snapshot:
        snapshot = json.loads(Path(args.snapshot).read_text())
    else:
        ap.error("--snapshot required unless --selftest")

    today = dt.date.fromisoformat(args.today) if args.today else None
    if today is None and snapshot.get("asof_utc", "").count("-") >= 2:
        try:
            today = dt.date.fromisoformat(snapshot["asof_utc"][:10])
        except ValueError:
            pass

    report = asyncio.run(run_one_cycle(state, snapshot, today))
    json.dump(report, sys.stdout, indent=2)
    print()
    if args.selftest:
        m = report["meta"]
        print(f"SELFTEST OK: {m['node_count']} nodes "
              f"(contract {m['expected_node_count']}), "
              f"{len(m['errors'])} errors", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
