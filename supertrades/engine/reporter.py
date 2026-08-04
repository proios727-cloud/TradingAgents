"""Summarizer + final reporter for SuperTrades v3.

THE SINGLE GUARDRAIL GATE. Every accept/suppress decision in the system —
daily halt, entry freeze, settlement suppression, delta/ask/spread/OI floors,
per-trade cap, BP floor, max auto-entries, time-of-day windows, already-held,
index-0DTE-requires-GEX-gate, alert-only routing, class session time stops,
churn guard, DND push precedence — lives in this module and nowhere else.
Nodes only observe and propose; orchestrator only schedules.

Values mirror supertrades-v3.md §3/§5/§6/§7 (that file wins on conflict).
"""
from __future__ import annotations

import functools

from .nodes import expected_move_exits

AGENTIC_ACCT = "902341866"   # execute here ONLY
MARGIN_ACCT = "812234458"    # READ-ONLY: alerts, never trade

GUARDRAILS = {
    "daily_halt_usd": -60.0,            # day P&L (realized + open) at/below -> halt
    "max_auto_entries_per_day": 1,      # engine-initiated auto entries
    "max_entries_per_day_total": 2,     # v4 governor: auto + manual combined; alert on the 3rd
    "max_contracts_per_order": 1,      # legacy default (single-lot floor)
    "max_lots_per_order": 3,            # v4.5: size up to N lots WITHIN the per-trade cap
    "barbell_min_lots": 2,             #   >= this -> stamp the barbell (scale-out + moonshot)
    "bp_floor_usd": 30.0,               # never leave less than this after entry
    "per_trade_bp_frac": 0.22,          # v4.1: contract cost <= 22% of settled BP (was 25/40).
                                        #   On the live ~$541 acct: max ~$119 capital/trade;
                                        #   intended -30% stop ~= $36 risk (~6.6% of account).
    "settlement_suppressed_below_bp": 80.0,
    "entry_delta_floor": 0.35,          # v4: raised from 0.25 (quality of expression)
    "spread_cap_pct_of_ask": 12.0,      # v4: paired with the premium floor below
    "min_premium_usd": 0.40,            # v4: keeps the bid/ask spread from being 20%+ of the trade
    "min_dte_day_trade": 5,             # v4: no <5-DTE single-name day-trades (theta-cliff lottos)
    "min_oi": 500,
    # v4.2 (8/4): vol-aware pricing — stop overpaying for premium on high-IV names.
    "iv_soft_cap": 0.90,                # abs IV above this -> flag 'overpaying for vol',
                                        #   prefer a debit spread, and de-rank vs lower-IV picks
    "iv_hard_cap": 2.50,               # abs IV above this -> block (uninvestable premium)
    "iv_rank_soft_cap": 0.80,          # if fetch supplies iv_rank (0-1): top-20%-of-year -> same steer
    # v4.2 (8/4): concentration ceiling for short-dated trades. Binds EVEN when the
    #   daily-2 / midday / min_dte rails are overridden by hand — the floor under overrides.
    "short_dte_days": 5,                # DTE strictly below this counts as short-dated
    "short_dte_bp_frac_cap": 0.35,      # short-DTE contract cost must be <= 35% of settled BP
                                        #   (today's INTC 1-DTE @ ~49% BP would have been trimmed)
    "churn_round_trips": 3,             # v4: churn brake tightened from 4
    "no_entry_before_et": "09:40",
    "midday_skip_et": ("12:00", "14:00"),
    "midday_skip_override_day_pct": 3.0,
    "after_et_gex_only": "15:00",       # after 3pm only GEX-gated index scalps
}

_GROUPS = ("signals", "gex", "whale", "gates", "exits", "entries")
_KIND_GROUP = {"ticker_signal": "signals", "gex_map": "gex",
               "whale_flow": "whale", "pullback_gate": "gates",
               "position_exit": "exits", "candidate_entry": "entries"}


def summarizer(batch) -> dict:
    """Associative reducer: merges raw node results and/or prior summaries."""
    out = {"__summary__": True, "node_count": 0, "errors": [],
           "groups": {g: [] for g in _GROUPS}}
    for item in batch:
        if item.get("__summary__"):
            out["node_count"] += item["node_count"]
            out["errors"] += item["errors"]
            for g in _GROUPS:
                out["groups"][g] += item["groups"][g]
        else:
            out["node_count"] += 1
            if not item.get("ok"):
                out["errors"].append({"kind": item.get("kind"),
                                      "key": item.get("key"),
                                      "error": item.get("error")})
            else:
                g = _KIND_GROUP.get(item.get("kind"))
                if g:
                    out["groups"][g].append(item["data"])
    return out


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def short_dte_override_max_usd(bp: float) -> float:
    """Hard $ ceiling on a *hand-placed* (manual/agentic) entry with <short_dte_days DTE.

    This is the floor under the overrides: when the agent or user overrides the
    engine's daily-2 / midday / min_dte rails to take a short-dated trade, the
    contract cost still may not exceed this. The engine's own auto path is capped
    tighter by per_trade_bp_frac (0.22); this exists so the override path can't
    concentrate a short-DTE lotto the way the 8/4 INTC 1-DTE did (~49% of BP).
    """
    return GUARDRAILS["short_dte_bp_frac_cap"] * bp


def high_iv_steer(iv: float | None, iv_rank: float | None = None) -> bool:
    """True if this contract's vol is rich enough to prefer a debit spread over a
    naked long (abs IV over soft cap, or iv_rank in the top band when supplied)."""
    g = GUARDRAILS
    if iv is not None and iv > g["iv_soft_cap"]:
        return True
    if iv_rank is not None and iv_rank > g["iv_rank_soft_cap"]:
        return True
    return False


def conviction_score(c: dict) -> float:
    """Rank eligible entries by conviction for a higher base win rate (v4.9).

    Blends delta (win-probability proxy), RVOL (volume conviction), positive momentum +
    above-VWAP (trend), and an IV-fit penalty (don't overpay for vol). 0..1, higher = stronger.
    Missing inputs contribute neutrally so a sparse candidate isn't unfairly buried.
    """
    delta = c.get("delta") or 0.0
    rvol = c.get("rvol")
    day = c.get("underlying_day_pct") or 0.0
    iv = c.get("iv")
    s_delta = min(delta / 0.60, 1.0)                       # prob proxy, saturates ~0.60Δ
    s_rvol = min((rvol if rvol else 1.0) / 3.0, 1.0)       # ~3x average volume = strong
    s_mom = (min(day / 5.0, 1.0) if day > 0 else 0.0)      # positive momentum only
    s_vwap = 1.0 if c.get("above_vwap") else 0.0
    s_iv = 1.0 - min(max((iv or 0.5) - 0.90, 0.0) / 1.6, 1.0)   # penalize rich IV
    return round(0.35 * s_delta + 0.30 * s_rvol + 0.20 * s_mom
                 + 0.10 * s_vwap + 0.05 * s_iv, 3)


def size_order(cost_per_contract_usd: float, bp: float) -> int:
    """Lots to buy: fill the per-trade cost cap with up to max_lots_per_order, >= 1.

    v4.5 — same risk envelope as before (total cost still bounded by per_trade_bp_frac
    of BP and the bp floor), but a cheap-enough contract is bought in 2-3 lots so the
    barbell can scale out. An expensive contract still resolves to a single lot.
    """
    g = GUARDRAILS
    if cost_per_contract_usd <= 0:
        return 1
    cap_usd = g["per_trade_bp_frac"] * bp
    n = int(cap_usd // cost_per_contract_usd)
    while n >= 1 and bp - n * cost_per_contract_usd < g["bp_floor_usd"]:
        n -= 1
    return max(1, min(g["max_lots_per_order"], n))


def materialize_exit_rules(class_name: str, qty: int, class_defaults: dict,
                           is_index: bool = False, target_pct: float | None = None,
                           stop_pct: float | None = None) -> list[dict]:
    """Stamp exit_rules onto a new position from its class profile (v4.5 auto-materializer).

    Single lot -> never-red + loose give-back runner. >= barbell_min_lots -> the barbell:
    leg A scale-out (bank half at target, locks the day) + leg B strict moonshot trail
    (give back only 20% of peak) so a runner is realized continuously and protected.
    Index scalps additionally get the VWAP trend-trail.
    """
    cd = class_defaults.get(class_name, {})
    # target/stop default to the class flats, but are OVERRIDDEN by IV+greek expected-move
    # levels when the caller passes them (v4.9) - reachable targets lift win rate, and the
    # initial stop is vol-appropriate instead of a flat -30%.
    tgt = target_pct if target_pct is not None else cd.get("target_pct", 50)
    stp = stop_pct if stop_pct is not None else cd.get("stop_pct", -30)
    # ONE ratcheting-stop equation covers the whole life (initial stop -> ~breakeven by +5%
    # -> locks growing green -> looser room for big runners). Minimal drawdown, fewer parts.
    rules: list[dict] = [
        {"type": "progressive_stop", "base": 3.25, "slope": 0.35,
         "initial_pct": stp, "mech": "sell_marketable_through_bid"},
    ]
    barbell = qty >= GUARDRAILS["barbell_min_lots"]
    if barbell:
        # leg A: bank half at the (reachable) target. leg B: strict moonshot trail tightens
        # the remainder beyond the progressive stop once it's a big winner.
        rules.append({"type": "target", "pct": tgt,
                      "scale_out_frac": 0.5, "mech": "scale_out_lock_day"})
        rules.append({"type": "giveback", "arm_gain_pct": 100, "peak_frac": 0.20,
                      "mech": "strict_moonshot_trail"})
    else:
        # single lot: runner that doesn't cap at target; the progressive stop is the trail.
        rules.append({"type": "target", "pct": tgt,
                      "runner": True, "mech": "hold_runner_trail_no_cap"})
    if is_index and class_name == "0dte_scalp":
        trail = cd.get("am_index_trail", {}).get("materialize_rule",
                                                 {"type": "underlying_vwap_stop", "buffer_pct": 0.1})
        rules.append(dict(trail))
    return rules


def make_final_reporter(state: dict):
    """Bind state so the callable keeps the (summary, snapshot) signature."""
    return functools.partial(final_report, state=state)


def final_report(summary: dict, snapshot: dict, state: dict) -> dict:
    g = GUARDRAILS
    acct = snapshot.get("account", {})
    groups = summary["groups"]
    positions = state.get("positions", {})
    class_defaults = state.get("class_defaults", {})
    et_min = _minutes(snapshot.get("et_time", "10:00"))
    dnd = bool(state.get("mode", {}).get("dnd"))

    actions = {"exits": [], "entry": None, "state_updates": [], "alerts": []}
    pushes: list[dict] = []

    # ---- day P&L (agentic realized + agentic open) and the daily halt -------
    open_pnl = 0.0
    for ex in groups["exits"]:
        pos = positions.get(ex.get("id"), {})
        if pos.get("account") == AGENTIC_ACCT and not ex.get("missing"):
            open_pnl += (ex["mark"] - pos["entry"]) * 100 * pos.get("qty", 1)
    day_pnl = acct.get("day_realized", 0.0) + open_pnl
    halted = bool(acct.get("halted")) or day_pnl <= g["daily_halt_usd"]
    if halted and not acct.get("halted"):
        pushes.append({"kind": "daily_halt", "dnd_exempt": True,
                       "msg": f"DAILY HALT: day P&L {day_pnl:+.2f} <= {g['daily_halt_usd']:.0f}. "
                              "Entries stopped; exits stay live."})

    # ---- exits: convert proposals to orders/alerts (exits stay live in halt) -
    for ex in groups["exits"]:
        pos = positions.get(ex.get("id"), {})
        if ex.get("missing"):
            actions["alerts"].append({"id": ex.get("id"), "rule": "no_quote",
                                      "detail": "position quote missing this cycle"})
            continue
        alert_only = (pos.get("account") != AGENTIC_ACCT
                      or pos.get("class") == "alert_only")
        qty = pos.get("qty", 1)
        rules = {r["type"]: r for r in pos.get("exit_rules", [])}
        for trip in ex.get("trips", []):
            rule = trip["rule"]
            if rule == "ratchet_arm":
                actions["state_updates"].append(
                    {"id": ex["id"], "set": {"ratchet_engaged": True, "hwm": ex["hwm"]},
                     "why": f"breakeven ratchet armed: {trip['detail']}"})
            elif alert_only:
                actions["alerts"].append({"id": ex["id"], "contract": ex["contract"],
                                          "rule": rule, "detail": trip["detail"]})
            elif rule == "target":
                trule = rules.get("target", {})
                frac = trule.get("scale_out_frac")
                # multi-contract: bank a slice at target, let the rest run under the trail
                if frac and qty > 1 and not pos.get("scaled_out"):
                    sell_qty = max(1, int(qty * frac))
                    actions["exits"].append(
                        {"id": ex["id"], "contract": ex["contract"], "qty": sell_qty,
                         "order": "sell_limit_at_mark",
                         "why": f"scale-out {sell_qty}/{qty} at target: {trip['detail']}"})
                    actions["state_updates"].append(
                        {"id": ex["id"], "set": {"scaled_out": True, "qty": qty - sell_qty},
                         "why": "banked scale-out slice; remainder trails give-back guard"})
                # runner (used for override/high-conviction plays): DON'T cap at +50% —
                # hold and let the trailing give-back guard capture the peak instead
                elif trule.get("runner"):
                    actions["alerts"].append(
                        {"id": ex["id"], "contract": ex["contract"], "rule": "target_hold_runner",
                         "detail": f"{trip['detail']} — holding under give-back trail (runner)"})
                else:
                    actions["exits"].append(
                        {"id": ex["id"], "contract": ex["contract"], "qty": qty,
                         "order": "sell_limit_at_mark", "why": f"target: {trip['detail']}"})
            elif rule == "giveback":
                actions["exits"].append(
                    {"id": ex["id"], "contract": ex["contract"], "qty": qty,
                     "order": "sell_limit_at_bid", "why": f"give-back trail: {trip['detail']}"})
            elif rule in ("stop", "ratchet_stop", "green_lock", "underlying_vwap_stop",
                          "progressive_stop"):
                actions["exits"].append(
                    {"id": ex["id"], "contract": ex["contract"], "qty": qty,
                     "order": "sell_limit_at_bid", "why": f"{rule}: {trip['detail']}"})
            else:
                actions["alerts"].append({"id": ex["id"], "contract": ex["contract"],
                                          "rule": rule, "detail": trip["detail"]})
        # persist the peak so the give-back trail measures from a true high-water mark
        stored_hwm = pos.get("hwm", pos.get("entry", 0.0))
        if (not alert_only and ex.get("hwm") and ex["hwm"] > stored_hwm
                and not any(u["id"] == ex["id"] and "hwm" in u.get("set", {})
                            for u in actions["state_updates"])):
            actions["state_updates"].append(
                {"id": ex["id"], "set": {"hwm": ex["hwm"]},
                 "why": "peak high-water mark advanced (give-back trail reference)"})
        # class session time stops (clock rules live here, not in nodes)
        cd = class_defaults.get(pos.get("class"), {})
        stop_at = cd.get("hard_exit_et") or cd.get("flatten_et")
        if stop_at and et_min >= _minutes(stop_at) and not alert_only:
            if pos.get("ratchet_engaged") and cd.get("flatten_et"):
                actions["alerts"].append(
                    {"id": ex["id"], "contract": ex["contract"], "rule": "keep_or_flatten",
                     "detail": f"ratchet engaged at {stop_at} flatten — default flatten 15:55"})
            else:
                actions["exits"].append({"id": ex["id"], "contract": ex["contract"],
                                         "order": "sell_limit_at_mark",
                                         "why": f"class '{pos.get('class')}' time stop {stop_at} ET"})

    # ---- entry gate (every entry guardrail, once, here) ---------------------
    bp = acct.get("bp", 0.0)
    held_syms = {p["contract"].split()[0] for p in positions.values()
                 if p.get("account") == AGENTIC_ACCT}

    entries_today = acct.get("auto_entries_used", 0) + acct.get("manual_entries_today", 0)

    frozen = []                       # global freezes: apply to every candidate
    if halted:
        frozen.append("daily_halt")
    if acct.get("auto_entries_used", 0) >= g["max_auto_entries_per_day"]:
        frozen.append("max_auto_entries_used")
    if entries_today >= g["max_entries_per_day_total"]:   # v4 governor
        frozen.append("daily_entry_cap")
    if bp < g["settlement_suppressed_below_bp"]:
        frozen.append("settlement_suppressed")
    if not snapshot.get("weekday", True):
        frozen.append("not_a_weekday")
    if et_min < _minutes(g["no_entry_before_et"]):
        frozen.append("opening_no_entry_window")
    if et_min >= _minutes(g["after_et_gex_only"]):
        frozen.append("after_1500_gex_scalp_only")

    audits = []
    for c in groups["entries"]:
        blocked = list(frozen)
        warnings: list[str] = []
        if c.get("missing"):
            blocked.append("no_quote")
        else:
            cost = c["ask"] * 100
            if cost > g["per_trade_bp_frac"] * bp:
                blocked.append("per_trade_cap")
            if bp - cost < g["bp_floor_usd"]:
                blocked.append("bp_floor")
            if c.get("delta") is None or c["delta"] < g["entry_delta_floor"]:
                blocked.append("delta_floor")
            if c.get("spread_pct") is None or c["spread_pct"] > g["spread_cap_pct_of_ask"]:
                blocked.append("spread_cap")
            if c.get("oi") is not None and c["oi"] < g["min_oi"]:
                blocked.append("oi_floor")
            if c.get("ask") is not None and c["ask"] < g["min_premium_usd"]:
                blocked.append("min_premium")            # v4: spread-as-% sanity
            if c["symbol"] in held_syms:
                blocked.append("already_held")
            day_pct = c.get("underlying_day_pct")
            if not (day_pct is not None and day_pct > 0 and c.get("above_vwap")):
                blocked.append("conviction")
            lo, hi = g["midday_skip_et"]
            if (_minutes(lo) <= et_min < _minutes(hi)
                    and (day_pct is None or abs(day_pct) <= g["midday_skip_override_day_pct"])):
                blocked.append("midday_window")
            edays = c.get("expiry_days")
            is_index = state.get("ticker_classes", {}).get(c["symbol"]) == "index"
            if edays is not None:
                if is_index and edays <= 1:
                    blocked.append("index_0dte_requires_gex_gate")
                elif edays <= 0:
                    blocked.append("0dte_blocked")        # v4: no non-index 0DTE autos
                elif edays < g["min_dte_day_trade"]:
                    blocked.append("min_dte")             # v4: no <5-DTE day-trades
            # v4.2 vol-aware pricing: block absurd IV, steer rich IV to a spread
            iv = c.get("iv")
            if iv is not None and iv > g["iv_hard_cap"]:
                blocked.append("iv_hard_cap")
            if high_iv_steer(iv, c.get("iv_rank")):
                warnings.append("high_iv_prefer_debit_spread")
            # v4.2 concentration ceiling for short-dated trades (binds under overrides)
            if edays is not None and edays < g["short_dte_days"] \
                    and cost > g["short_dte_bp_frac_cap"] * bp:
                blocked.append("short_dte_concentration")
        audits.append({"id": c.get("id"), "symbol": c.get("symbol"),
                       "contract": c.get("contract"), "warnings": warnings,
                       "blocked_by": blocked, "eligible": not blocked})

    eligible = [a for a in audits if a["eligible"]]
    if eligible:
        by_id = {c["id"]: c for c in groups["entries"]}
        # prefer lower-IV expressions: a non-high-IV candidate outranks any high-IV
        # one; within a tier, highest delta wins. High-IV is chosen only when it's
        # the sole eligible option (then it carries the prefer-spread warning through).
        def _rank(a):
            not_high_iv = "high_iv_prefer_debit_spread" not in a.get("warnings", [])
            return (not_high_iv, conviction_score(by_id[a["id"]]))
        pick = max(eligible, key=_rank)                      # v4.9: conviction-ranked (see _rank)
        cand = by_id[pick["id"]]
        cost_per = (cand.get("ask") or 0.0) * 100
        qty = size_order(cost_per, bp)                       # v4.5 multi-lot sizing
        sym = pick.get("symbol") or cand.get("symbol")
        is_index = state.get("ticker_classes", {}).get(sym) == "index"
        entry_class = "day_trade"                            # auto momentum entries are day-trades
        # v4.9: IV + greek expected-move exits (reachable target, vol-appropriate stop)
        em = expected_move_exits(entry=cand.get("ask") or 0.0, iv=cand.get("iv") or 0.0,
                                 delta=cand.get("delta") or 0.0, gamma=cand.get("gamma") or 0.0,
                                 spot=cand.get("underlying_last") or 0.0,
                                 dte=cand.get("expiry_days") or 1)
        exit_rules = materialize_exit_rules(entry_class, qty, class_defaults, is_index,
                                            target_pct=em["target_pct"], stop_pct=em["stop_pct"])
        actions["entry"] = {"id": pick["id"], "contract": pick["contract"],
                            "qty": qty,
                            "order": "review_then_place_buy_limit",
                            "account": AGENTIC_ACCT,
                            "warnings": pick.get("warnings", []),
                            "class": entry_class, "exit_rules": exit_rules,
                            "conviction": conviction_score(cand), "expected_move": em,
                            "sizing": f"{qty} lot(s) @ ~${cost_per:.0f}; "
                                      f"barbell={qty >= g['barbell_min_lots']}"}

    # ---- churn guard --------------------------------------------------------
    if (acct.get("manual_round_trips", 0) >= g["churn_round_trips"]
            and not state.get("day", {}).get("churn_threshold_hit")):
        pushes.append({"kind": "churn_guard", "dnd_exempt": False,
                       "msg": f"{acct.get('manual_round_trips')} manual round-trips today "
                              f"(brake at {g['churn_round_trips']}) — spread cost is compounding."})

    # ---- v4 discipline governor: over-trading breach ------------------------
    if (entries_today > g["max_entries_per_day_total"]
            and not state.get("day", {}).get("entry_cap_alerted")):
        pushes.append({"kind": "entry_cap", "dnd_exempt": False,
                       "msg": f"{entries_today} entries today — over the "
                              f"{g['max_entries_per_day_total']}/day governor cap. Overtrading."})

    # ---- system failure: majority of nodes erroring is never silent ---------
    if summary["errors"] and summary["node_count"] \
            and len(summary["errors"]) * 2 >= summary["node_count"]:
        pushes.append({"kind": "system_failure", "dnd_exempt": True,
                       "msg": f"{len(summary['errors'])}/{summary['node_count']} nodes failed — "
                              "check MCP connection / rebuild loop."})

    # ---- gate + console payload (sections mirror the console page) ----------
    armed = [x["symbol"] for x in groups["gates"]
             if x.get("arming") and not x.get("missing")]
    signals = sorted((s for s in groups["signals"] if not s.get("missing")),
                     key=lambda s: -abs(s.get("day_pct", 0)))
    whale_rows = sorted((dict(r, symbol=w["symbol"]) for w in groups["whale"]
                         for r in w.get("rows", [])),
                        key=lambda r: -r["premium"])[:10]

    console = {
        "kpis": {"buying_power": bp, "day_pnl": round(day_pnl, 2),
                 "open_pnl": round(open_pnl, 2),
                 "open_positions": len(positions),
                 "auto_entries": f"{acct.get('auto_entries_used', 0)}"
                                 f"/{g['max_auto_entries_per_day']}",
                 "entries_state": ("HALTED" if halted else
                                   "FROZEN" if frozen else "ARMED")},
        "positions_rails": [ex for ex in groups["exits"] if not ex.get("missing")],
        "signal_board": signals,
        "pullback_gate": {"status": "ARMED" if armed else "STANDBY",
                          "armed_symbols": armed,
                          "note": "IWM arms only — plays map to SPY/QQQ"},
        "gex_map": {x["symbol"]: {"spot": x.get("spot"),
                                  "king_node": x.get("king_node"),
                                  "put_shelf": x.get("put_shelf")}
                    for x in groups["gex"] if not x.get("missing")},
        "whale_rows": whale_rows,
        "loop_guardrails": {"engine": "fan-out / layered fan-in",
                            "node_count": summary["node_count"],
                            "node_errors": summary["errors"],
                            "guardrail_gate": "single gate: engine/reporter.py"},
        "discipline": {                     # v4 governor scorecard
            "entries_today": entries_today,
            "entries_cap": g["max_entries_per_day_total"],
            "round_trips": acct.get("manual_round_trips", 0),
            "round_trip_brake": g["churn_round_trips"],
            "quality_floor": {"delta_min": g["entry_delta_floor"],
                              "spread_max_pct": g["spread_cap_pct_of_ask"],
                              "premium_min": g["min_premium_usd"],
                              "min_dte": g["min_dte_day_trade"],
                              "per_trade_bp_frac": g["per_trade_bp_frac"],
                              "iv_soft_cap": g["iv_soft_cap"],
                              "iv_hard_cap": g["iv_hard_cap"],
                              "short_dte_bp_frac_cap": g["short_dte_bp_frac_cap"]},
            "flags": ([f"entry cap reached ({entries_today}/{g['max_entries_per_day_total']})"]
                      if entries_today >= g["max_entries_per_day_total"] else [])
                     + (["churn brake — round-trips at/over limit"]
                        if acct.get("manual_round_trips", 0) >= g["churn_round_trips"] else []),
        },
    }
    if actions["entry"] is None:
        why = ", ".join(sorted(set(frozen))) if frozen else "no eligible candidates"
        console["entries_note"] = f"No entries recommended — {why}"

    if dnd:
        pushes = [p for p in pushes if p["dnd_exempt"]]

    return {"console": console, "actions": actions, "pushes": pushes,
            "guardrail_audit": {"halted": halted, "day_pnl": round(day_pnl, 2),
                                "entry_frozen": frozen, "per_candidate": audits},
            "meta": {"node_count": summary["node_count"],
                     "errors": summary["errors"], "dnd": dnd}}
