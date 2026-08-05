"""Reliable-ops helpers (v4 Layer 2).

Deterministic clock / phase / flatten / staleness logic so a cycle can never
*silently* miss a rollover, a class time-stop flatten, or a stale-state broker
reconcile — even when the self-scheduling wakeup stalls (the failure that carried
the 7/24 DIS day-trade into the weekend). Whatever fires the cycle — the concentrated
cron, the dedicated 3:44 flatten trigger, or a heartbeat — calls cycle_intent() and
gets the same answer about what this cycle MUST do.

Times are ET "HH:MM". Pure functions, no I/O — unit-tested in tests/test_engine.py.
"""
from __future__ import annotations

import datetime as dt

AGENTIC_ACCT = "902341866"
CLOCK_GATE = ("08:55", "16:05")     # outside this window -> no-op, zero MCP calls
MARKET_OPEN = "09:30"
MIDDAY = ("12:00", "14:00")
POWER_HOUR = "15:00"
STALE_MINUTES = 20                  # state older than this, in-hours -> must reconcile


def _m(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def clock_phase(et_time: str, weekday: bool = True) -> str:
    """closed | premarket | core | midday | power_hour."""
    if not weekday:
        return "closed"
    t = _m(et_time)
    lo, hi = CLOCK_GATE
    if t < _m(lo) or t >= _m(hi):
        return "closed"
    if t < _m(MARKET_OPEN):
        return "premarket"
    if t >= _m(POWER_HOUR):
        return "power_hour"
    mlo, mhi = MIDDAY
    if _m(mlo) <= t < _m(mhi):
        return "midday"
    return "core"


def rollover_due(trading_date: str, today_iso: str) -> bool:
    """Day block must reset before anything else when the date turned over."""
    return bool(trading_date) and bool(today_iso) and trading_date != today_iso


def flatten_due(state: dict, et_time: str) -> list[str]:
    """Agentic position ids whose class session time-stop has passed at et_time.

    This is the safety net for the missed-flatten failure: any fire after the
    stop time returns the ids, so the exit can't be skipped just because the
    tick that *should* have caught it never ran.
    """
    t = _m(et_time)
    cd = state.get("class_defaults", {})
    due = []
    for pid, pos in state.get("positions", {}).items():
        if pos.get("account") != AGENTIC_ACCT:
            continue
        c = cd.get(pos.get("class"), {})
        stop = c.get("hard_exit_et") or c.get("flatten_et")
        if stop and t >= _m(stop) and not pos.get("ratchet_engaged"):
            due.append(pid)
    return due


def stale(updated_at_iso: str | None, now_iso: str | None,
          max_min: int = STALE_MINUTES) -> bool:
    """True if state.updated_at is older than max_min (or unparseable/missing)."""
    if not updated_at_iso or not now_iso:
        return True
    try:
        u = dt.datetime.fromisoformat(updated_at_iso.replace("Z", "+00:00"))
        n = dt.datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
        return (n - u).total_seconds() > max_min * 60
    except ValueError:
        return True


def poll_interval_seconds(peak_pct: float, extended: bool = False,
                          at_level: bool = False) -> int:
    """Management poll cadence that TIGHTENS as a position extends, so the tightening trail
    actually catches a fast reversal near a peak (the QQQ 8/4 +123%->+56% lesson).

    peak_pct = peak gain % (hwm-based). The bigger the winner - and the tighter its trail tier
    (5% give-back past +200%) - the faster we must re-check, because a resting poll is the real
    binding constraint on any trail. `extended` (past the target / near a trail trigger) pulls a
    still-developing position onto the faster cadence too.

    at_level (v4.13): price is AT an armed trigger level (wall tag, flip reclaim, HOD test) —
    flat or in-position. The 8/5 lesson: SPY's 770 slice-and-reclaim resolved BETWEEN 12-min
    polls, so the confirm/fail was never seen live. At a level the cadence is the trigger.
    """
    if at_level or peak_pct >= 200:
        return 90          # decision imminent — near-continuous watch
    if peak_pct >= 100:
        return 180
    if peak_pct >= 25 or extended:
        return 480         # past ratchet / target — 8 min
    return 900             # 15 min baseline


def cycle_intent(et_time: str, weekday: bool, trading_date: str, today_iso: str,
                 state: dict, updated_at: str | None = None,
                 now: str | None = None) -> dict:
    """The one place that decides what a cycle MUST do, for any trigger source."""
    phase = clock_phase(et_time, weekday)
    actions: list[str] = []
    if phase == "closed":
        return {"phase": phase, "actions": ["no_op"], "flatten_ids": []}

    if rollover_due(trading_date, today_iso):
        actions.append("rollover")
    if phase == "premarket":
        actions.append("build_premarket_plan")

    fl = flatten_due(state, et_time)
    if fl:
        actions.append("flatten")
    if stale(updated_at, now):
        actions.append("reconcile_broker")   # never trust a bare selftest when stale
    if phase in ("premarket", "core", "power_hour"):
        actions.append("run_cycle")

    # de-dup, stable order
    seen, ordered = set(), []
    for a in actions:
        if a not in seen:
            seen.add(a)
            ordered.append(a)
    return {"phase": phase, "actions": ordered, "flatten_ids": fl}
