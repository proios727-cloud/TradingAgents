"""SuperTrades v3 node functions.

Each node is pure and independent: it reads its own payload plus the shared
read-only cycle snapshot (produced by the MCP fetch step — the project's ONE
authenticated Robinhood path) and returns observations/proposals only.

NO GUARDRAIL LIVES HERE. Nodes may *propose* (e.g. "entry candidate viable",
"stop breached"); every accept/suppress decision is made exactly once in
reporter.final_reporter. Keeping proposals unfiltered is what makes the
single-gate test meaningful.

Snapshot schema (written by the loop's fetch step, see README):
{
  "asof_utc": str, "et_time": "HH:MM", "weekday": bool,
  "account": {"bp": float, "day_realized": float, "auto_entries_used": int,
               "manual_round_trips": int, "halted": bool},
  "quotes": {SYM: {"last": float, "prev_close": float, "day_pct": float}},
  "option_quotes": {ID: {"mark","bid","ask","delta","gamma","oi","volume","spread_pct",
                         "iv","iv_rank"}},   # iv = implied_volatility (abs); iv_rank optional 0-1
  "positions": {ID: {...state.json position fields...}},
  "candidates": [{"id","contract","symbol","expiry_days"}],
  "gex": {SYM: {"strikes": {K: {"call_oi","call_gamma","put_oi","put_gamma",
                                  "call_volume","put_volume","call_mark","put_mark"}},
                 "spot": float}},
  "vwap": {SYM: float},           # optional
  "prior": {"marks": {...}, "cum_volume": {...}, "day_pct": {...}, "crossed_2pct": [...]}
}
"""
from __future__ import annotations

WHALE_VOI_MIN = 20.0
WHALE_PREMIUM_MIN = 1_000_000.0


async def ticker_signal(payload: dict, snapshot: dict) -> dict:
    """Signal scan for one ticker: day%, cross/reversal events, vwap side."""
    sym = payload["symbol"]
    q = snapshot["quotes"].get(sym)
    if q is None:
        return {"symbol": sym, "missing": True}
    prior_pct = snapshot.get("prior", {}).get("day_pct", {}).get(sym)
    crossed = sym in snapshot.get("prior", {}).get("crossed_2pct", [])
    events = []
    if abs(q["day_pct"]) >= 2.0 and not crossed:
        events.append("first_2pct_cross")
    if prior_pct is not None and abs(q["day_pct"] - prior_pct) > 1.0:
        events.append("reversal_gt_1pct")
    vwap = snapshot.get("vwap", {}).get(sym)
    return {"symbol": sym, "day_pct": q["day_pct"],
            "above_vwap": (None if vwap is None else q["last"] > vwap),
            "events": events}


async def gex_map(payload: dict, snapshot: dict) -> dict:
    """Net GEX per strike for one underlying; king node + walls."""
    sym = payload["symbol"]
    g = snapshot.get("gex", {}).get(sym)
    if not g:
        return {"symbol": sym, "missing": True}
    net = {float(k): v["call_oi"] * v["call_gamma"] - v["put_oi"] * v["put_gamma"]
           for k, v in g["strikes"].items()}
    king = max(net, key=lambda k: net[k]) if net else None
    put_shelf = min(net, key=lambda k: net[k]) if net else None
    return {"symbol": sym, "spot": g["spot"], "net_gex": net,
            "king_node": king, "put_shelf": put_shelf}


async def whale_flow(payload: dict, snapshot: dict) -> dict:
    """Unusual-activity rows for one underlying (V:OI + premium screens)."""
    sym = payload["symbol"]
    g = snapshot.get("gex", {}).get(sym)
    if not g:
        return {"symbol": sym, "rows": []}
    rows = []
    for k, v in g["strikes"].items():
        for side in ("call", "put"):
            oi, vol, mark = v[f"{side}_oi"], v[f"{side}_volume"], v.get(f"{side}_mark", 0.0)
            if oi and vol / oi >= WHALE_VOI_MIN and vol * mark * 100 >= WHALE_PREMIUM_MIN:
                rows.append({"strike": float(k), "side": side, "voi": round(vol / oi, 1),
                             "premium": round(vol * mark * 100)})
    return {"symbol": sym, "rows": sorted(rows, key=lambda r: -r["premium"])}


async def pullback_gate(payload: dict, snapshot: dict) -> dict:
    """Gate-arming observation for one index underlying (observation only)."""
    sym = payload["symbol"]
    q = snapshot["quotes"].get(sym)
    if q is None:
        return {"symbol": sym, "missing": True}
    prior_pct = snapshot.get("prior", {}).get("day_pct", {}).get(sym)
    red_after_green = prior_pct is not None and prior_pct > 0 and q["day_pct"] < 0
    return {"symbol": sym, "day_pct": q["day_pct"],
            "arming": q["day_pct"] <= -0.75 or red_after_green,
            "red_after_green": red_after_green}


async def position_exit(payload: dict, snapshot: dict) -> dict:
    """Evaluate one open position's typed exit_rules; PROPOSE trips only."""
    pos = payload["position"]
    pid = payload["id"]
    oq = snapshot["option_quotes"].get(pid)
    if oq is None:
        return {"id": pid, "missing": True}
    mark, entry = oq["mark"], pos["entry"]
    pct = (mark - entry) / entry * 100 if entry else 0.0
    hwm = max(pos.get("hwm", entry), mark)
    trips = []
    for rule in pos.get("exit_rules", []):
        t = rule["type"]
        if t in ("target", "alert_target") and pct >= rule["pct"]:
            trips.append({"rule": t, "detail": f"+{pct:.0f}% >= {rule['pct']}%"})
        elif t == "stop" and pct <= rule["pct"] and not pos.get("ratchet_engaged"):
            trips.append({"rule": t, "detail": f"{pct:.0f}% <= {rule['pct']}%"})
        elif t == "stop" and pos.get("ratchet_engaged") and mark <= entry:
            trips.append({"rule": "ratchet_stop", "detail": f"mark {mark} <= entry {entry}"})
        elif t == "ratchet" and not pos.get("ratchet_engaged") \
                and (hwm - entry) / entry * 100 >= rule["arm_pct"]:
            trips.append({"rule": "ratchet_arm", "detail": f"HWM +{(hwm-entry)/entry*100:.0f}%"})
        elif t == "green_lock":
            # win-rate lever: once the peak first clears arm_pct, a small-green floor at
            # floor_pct goes live - converts "reached +arm%" into a guaranteed win, so a
            # winner can't round-trip into a loss (the DIS/NVDA/QQQ-giveback lesson).
            peak_pct = (hwm - entry) / entry * 100 if entry else 0.0
            floor_pct = rule.get("floor_pct", 0.0)
            if peak_pct >= rule["arm_pct"] and pct <= floor_pct:
                trips.append({"rule": "green_lock",
                              "detail": f"peak +{peak_pct:.0f}% -> back to +{pct:.0f}% "
                                        f"<= locked +{floor_pct:.0f}%"})
        elif t == "giveback":
            # trailing profit-lock: once the peak gain clears arm_gain_pct, exit if the
            # position gives back more than peak_frac of that peak gain (QQQ 8/4 lesson —
            # +123% peak round-tripped toward the exit before the poll caught it).
            peak_gain = hwm - entry
            armed = entry and peak_gain > 0 \
                and peak_gain / entry * 100 >= rule["arm_gain_pct"]
            if armed and (hwm - mark) >= rule["peak_frac"] * peak_gain:
                locked = (mark - entry) / entry * 100
                trips.append({"rule": "giveback",
                              "detail": f"gave back {rule['peak_frac']*100:.0f}% of peak "
                                        f"+{peak_gain/entry*100:.0f}% -> lock +{locked:.0f}%"})
        elif t == "alert_bid_floor" and oq["bid"] <= rule["bid"]:
            trips.append({"rule": t, "detail": f"bid {oq['bid']} <= {rule['bid']}"})
        elif t == "alert_swing":
            prior = snapshot.get("prior", {}).get("marks", {}).get(pid[:8]) \
                or snapshot.get("prior", {}).get("marks", {}).get(pid)
            if prior and abs(mark - prior) / prior * 100 >= rule["pct"]:
                trips.append({"rule": t, "detail": f"swing {(mark-prior)/prior*100:+.0f}%"})
    return {"id": pid, "contract": pos["contract"], "account": pos["account"],
            "class": pos["class"], "mark": mark, "pct": round(pct, 1),
            "hwm": hwm, "trips": trips}


async def candidate_entry(payload: dict, snapshot: dict) -> dict:
    """Evaluate one watchlist candidate against ENTRY FLOORS (facts only)."""
    cid, sym = payload["id"], payload["symbol"]
    oq = snapshot["option_quotes"].get(cid)
    if oq is None:
        return {"id": cid, "symbol": sym, "missing": True}
    q = snapshot["quotes"].get(sym, {})
    return {"id": cid, "symbol": sym, "contract": payload.get("contract", cid),
            "ask": oq["ask"], "delta": oq.get("delta"), "oi": oq.get("oi"),
            "spread_pct": oq.get("spread_pct"),
            "iv": oq.get("iv"), "iv_rank": oq.get("iv_rank"),
            "underlying_day_pct": q.get("day_pct"),
            "above_vwap": (None if snapshot.get("vwap", {}).get(sym) is None
                            else q.get("last", 0) > snapshot["vwap"][sym]),
            "expiry_days": payload.get("expiry_days")}
