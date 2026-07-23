"""Discovery: build the cycle's node list from state.json.

Runs BEFORE fan-out. Anything that requires sequencing or shared context
(which tickers, which positions, contract expiry math) happens here so the
nodes themselves stay independent.

Node count contract (asserted by run_cycle and the tests):
    len(universe) + 3 * len(gex_underlyings) + len(positions) + len(watchlist)
"""
from __future__ import annotations

import datetime as dt

from .nodes import (candidate_entry, gex_map, position_exit, pullback_gate,
                    ticker_signal, whale_flow)
from .orchestrator import Node


def gex_underlyings(state: dict) -> list[str]:
    """Index-class tickers each get 3 nodes: GEX map, whale flow, pullback gate.

    IWM is included for map/arming observation only — the reporter never
    routes a trade to IWM through the gate (supertrades-v3.md §5).
    """
    return [s for s, c in state.get("ticker_classes", {}).items() if c == "index"]


def _expiry_days(contract: str, today: dt.date | None) -> int | None:
    """Derive days-to-expiry from a 'SYM M/D $KC' contract string. Never pinned."""
    if today is None:
        return None
    try:
        m, d = contract.split()[1].split("/")
        expiry = dt.date(today.year, int(m), int(d))
        if expiry < today - dt.timedelta(days=180):  # year rollover
            expiry = expiry.replace(year=today.year + 1)
        return (expiry - today).days
    except (IndexError, ValueError):
        return None


def build_nodes(state: dict, today: dt.date | None = None) -> list[Node]:
    nodes: list[Node] = []
    for sym in state.get("universe", []):
        nodes.append(Node("ticker_signal", sym, ticker_signal, {"symbol": sym}))
    for sym in gex_underlyings(state):
        nodes.append(Node("gex_map", sym, gex_map, {"symbol": sym}))
        nodes.append(Node("whale_flow", sym, whale_flow, {"symbol": sym}))
        nodes.append(Node("pullback_gate", sym, pullback_gate, {"symbol": sym}))
    for pid, pos in state.get("positions", {}).items():
        nodes.append(Node("position_exit", pid, position_exit,
                          {"id": pid, "position": pos}))
    for row in state.get("watchlist", []):
        contract = row["contract"]
        nodes.append(Node("candidate_entry", row["id"], candidate_entry,
                          {"id": row["id"], "symbol": contract.split()[0],
                           "contract": contract,
                           "expiry_days": _expiry_days(contract, today)}))
    return nodes


def expected_node_count(state: dict) -> int:
    return (len(state.get("universe", []))
            + 3 * len(gex_underlyings(state))
            + len(state.get("positions", {}))
            + len(state.get("watchlist", [])))
