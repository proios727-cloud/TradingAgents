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
  "quotes": {SYM: {"last": float, "prev_close": float, "day_pct": float, "rvol": float}},
                 # rvol = today's volume / avg daily volume (conviction); optional
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


def progressive_stop_pct(peak_pct: float, base: float = 3.25, slope: float = 0.35,
                         initial: float = -30.0) -> float:
    """Unified ratcheting stop (% P&L) as a function of the peak gain %.

    room R(g) = base + slope*g is the give-back allowed at peak g; the stop rides at g - R(g),
    floored at the initial stop. Params (not guardrail thresholds) travel on the exit_rule:
      - base/slope tuned so breakeven lands near +5% (base=3.25, slope=0.35),
      - small greens lock tight (low drawdown), big runners get progressively looser room.
    Monotone up in practice because the caller feeds peak = hwm-based gain.
    """
    if peak_pct <= 0:
        return initial
    return round(max(initial, peak_pct - (base + slope * peak_pct)), 2)


def expected_move_exits(entry: float, *, iv: float, delta: float, spot: float,
                        dte: float, gamma: float = 0.0, hold_days: float = 0.3,
                        target_sigma: float = 0.35, stop_sigma: float = 0.4) -> dict:
    """Vol-appropriate target/stop (% P&L) from IV + greeks, instead of a flat +50/-30.

    EM = spot*IV*sqrt(horizon/252) is the ~1-sigma underlying move over the intraday HOLD
    horizon (a scalp holds hours, not to expiry — capped by DTE). The option moves
    ~ delta*EM + 0.5*gamma*EM^2 for that (gamma convexity favors the runner). Target is a
    reachable sigma-fraction of that move (low-IV name -> nearer target you can hit -> higher
    win rate; high-IV -> wider), the stop a smaller fraction. Clamped to sane bounds and
    falling back to flat +50/-30 when greeks are missing, so it never returns nonsense. The
    sigma / hold_days knobs are evolution hypotheses, tuned toward the objective score.
    """
    if not (entry and spot and iv and delta):
        return {"target_pct": 50.0, "stop_pct": -30.0, "basis": "flat_fallback"}
    horizon = min(hold_days, max(dte, 0.15))         # scalp hold, never past ~0DTE session
    em_und = spot * iv * (horizon / 252.0) ** 0.5
    opt_move = abs(delta) * em_und + 0.5 * gamma * em_und ** 2
    if opt_move <= 0:
        return {"target_pct": 50.0, "stop_pct": -30.0, "basis": "flat_fallback"}
    tp = min(max(target_sigma * opt_move / entry * 100, 15.0), 200.0)   # reachable, bounded
    sp = min(max(-stop_sigma * opt_move / entry * 100, -45.0), -8.0)    # vol-scaled, bounded
    return {
        "target_pct": round(tp, 1),
        "stop_pct": round(sp, 1),
        "expected_underlying_move": round(em_und, 2),
        "expected_option_move": round(opt_move, 2),
        "basis": f"IV {iv:.0%} · d{delta:.2f} · {target_sigma}s/{stop_sigma}s hold {horizon:.1f}d",
    }


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
        elif t == "progressive_stop":
            # ONE ratcheting-stop equation for the whole life (minimal-DD, user 8/4):
            # give-back room R = base + slope*peak GROWS with the move, so a small green locks
            # tight (stop reaches ~breakeven by ~+5%) while a big runner gets looser room.
            # Floored at the initial stop; monotone up because it's driven by hwm.
            peak_pct = (hwm - entry) / entry * 100 if entry else 0.0
            sp = progressive_stop_pct(peak_pct, rule.get("base", 3.25),
                                      rule.get("slope", 0.35), rule.get("initial_pct", -30.0))
            if pct <= sp:
                trips.append({"rule": "progressive_stop",
                              "detail": f"peak {peak_pct:+.0f}% -> stop {sp:+.1f}%; back to {pct:+.1f}%"})
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
        elif t == "underlying_vwap_stop":
            # trend-trailing stop for morning index scalps: stay in while the underlying
            # holds the right side of VWAP; exit on a break. VWAP rises through an uptrend,
            # so the stop trails the trend without capping upside (unlike a fixed target).
            sym = pos["contract"].split()[0]
            vwap = snapshot.get("vwap", {}).get(sym)
            last = snapshot.get("quotes", {}).get(sym, {}).get("last")
            buf = rule.get("buffer_pct", 0.0) / 100.0
            is_call = pos["contract"].rstrip().endswith("C")
            if vwap is not None and last is not None:
                broke = (last < vwap * (1 - buf)) if is_call else (last > vwap * (1 + buf))
                if broke:
                    side = "below" if is_call else "above"
                    trips.append({"rule": "underlying_vwap_stop",
                                  "detail": f"{sym} {last:.2f} broke {side} VWAP {vwap:.2f}"})
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
            "ask": oq["ask"], "delta": oq.get("delta"), "gamma": oq.get("gamma"),
            "oi": oq.get("oi"), "spread_pct": oq.get("spread_pct"),
            "iv": oq.get("iv"), "iv_rank": oq.get("iv_rank"),
            "underlying_last": q.get("last"), "rvol": q.get("rvol"),
            "underlying_day_pct": q.get("day_pct"),
            "above_vwap": (None if snapshot.get("vwap", {}).get(sym) is None
                            else q.get("last", 0) > snapshot["vwap"][sym]),
            "expiry_days": payload.get("expiry_days")}
