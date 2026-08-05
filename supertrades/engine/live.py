"""Live execution layer — bridge Robinhood MCP outputs into the engine (v4.6).

The gap this closes: the engine (reporter.final_report) already DECIDES entries
(`actions.entry` with sizing + materialized exit_rules), but the live loop had been
hand-applying rules instead of running the engine on real data. These PURE helpers
shape the raw MCP tool outputs into the exact snapshot `run_one_cycle` expects, so
the ONLY variable step is the fetch — the entry/exit decision is then deterministic
and identical to the tested offline cycle.

Loop procedure (one agentic session — see supertrades-v3.md "Execution layer"):
  1. FETCH via MCP: get_portfolio (bp), get_equity_quotes (universe + candidate syms),
     get_option_quotes (open positions + watchlist candidate ids), get_equity_technical_
     indicators type=vwap (per sym).
  2. snap = assemble_snapshot(state, et_time=..., weekday=..., bp=..., equity_results=...,
     option_results=..., vwap=...).
  3. report = run_one_cycle(state, snap).
  4. EXECUTE report["actions"]: exits first (sell), then report["actions"]["entry"] if
     present -> review_option_order then place_option_order, then write the position to
     state.json with entry["exit_rules"] + entry["qty"]. Commit.

No MCP or I/O happens here — pure shaping, unit-tested in tests/test_engine.py.
"""
from __future__ import annotations


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def rvol_now(cum_volume: float | None, avg_daily_volume: float | None,
             frac_of_day: float) -> float | None:
    """OBJECTIVE intraday relative volume (v4.13): today's cumulative volume vs the
    average volume expected BY THIS TIME of day (avg_daily * fraction elapsed).

    Feeds conviction_score's rvol input and reporter.breakout_confirmed, replacing
    the qualitative 'no volume thrust' read with a number. frac_of_day = minutes
    since 9:30 / 390 (clamped to a small floor so the open doesn't divide by ~0).
    """
    if not cum_volume or not avg_daily_volume or avg_daily_volume <= 0:
        return None
    frac = min(max(frac_of_day, 0.05), 1.0)      # floor 5% ~ first 20 min
    return round(cum_volume / (avg_daily_volume * frac), 2)


def _day_pct(last: float, prev_close: float) -> float:
    if not prev_close:
        return 0.0
    return round((last - prev_close) / prev_close * 100, 2)


def equity_quotes(results: list) -> dict:
    """get_equity_quotes .data.results -> {SYM: {last, prev_close, day_pct}}."""
    out = {}
    for r in results:
        q = r.get("quote", r)
        sym = q.get("symbol")
        if not sym:
            continue
        last = _f(q.get("last_trade_price")) or _f(q.get("last_non_reg_trade_price")) or 0.0
        prev = _f(q.get("adjusted_previous_close")) or _f(q.get("previous_close")) or 0.0
        out[sym] = {"last": last, "prev_close": prev, "day_pct": _day_pct(last, prev)}
    return out


def option_quotes(results: list) -> dict:
    """get_option_quotes .data.results -> {ID: {mark,bid,ask,delta,gamma,oi,volume,spread_pct,iv}}."""
    out = {}
    for r in results:
        q = r.get("quote", r)
        oid = q.get("instrument_id")
        if not oid:
            continue
        bid = _f(q.get("bid_price")) or 0.0
        ask = _f(q.get("ask_price")) or 0.0
        mark = _f(q.get("adjusted_mark_price")) or _f(q.get("mark_price")) or 0.0
        spread_pct = round((ask - bid) / ask * 100, 1) if ask else None
        out[oid] = {"mark": mark, "bid": bid, "ask": ask,
                    "delta": _f(q.get("delta")), "gamma": _f(q.get("gamma")),
                    "oi": _i(q.get("open_interest")), "volume": _i(q.get("volume")),
                    "spread_pct": spread_pct, "iv": _f(q.get("implied_volatility"))}
    return out


def assemble_snapshot(state: dict, *, et_time: str, weekday: bool, bp: float,
                      equity_results: list, option_results: list,
                      vwap: dict | None = None, gex: dict | None = None,
                      prior: dict | None = None, rvol: dict | None = None) -> dict:
    """Shape live MCP data into the snapshot run_one_cycle consumes.

    Account discipline fields (day_realized, entries used, halted) come from state.day
    — the same ledger the loop maintains — so the engine's caps/halt see live counts.
    """
    day = state.get("day", {})
    quotes = equity_quotes(equity_results)
    for sym, rv in (rvol or {}).items():           # rvol = today vol / avg daily vol (conviction)
        if sym in quotes:
            quotes[sym]["rvol"] = rv
    return {
        "asof_utc": "LIVE", "et_time": et_time, "weekday": weekday,
        "account": {"bp": bp,
                    "day_realized": day.get("realized_pnl", 0.0),
                    "auto_entries_used": day.get("auto_entries_used", 0),
                    "manual_entries_today": day.get("manual_entries_today", 0),
                    "manual_round_trips": day.get("manual_round_trips", 0),
                    "halted": day.get("halted", False)},
        "quotes": quotes,
        "option_quotes": option_quotes(option_results),
        "positions": state.get("positions", {}),
        "candidates": state.get("watchlist", []),
        "gex": gex or {},
        "vwap": vwap or {},
        "prior": prior or {"marks": {}, "cum_volume": {}, "day_pct": {}, "crossed_2pct": []},
    }
