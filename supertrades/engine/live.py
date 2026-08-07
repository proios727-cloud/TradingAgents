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

v4.14 adds the UNIVERSE FUNNEL (screen wide, execute narrow): funnel_candidates
shapes raw run_scan rows, funnel_filter applies the cheap equity-level pre-checks
(thresholds live ONLY in reporter.GUARDRAILS, passed in), funnel_rank picks the
top-N by reporter.conviction_score. Option-level gates (spread/OI/delta/IV/
affordability) still bind later at candidate_entry/final_report — the funnel just
decides which names are worth an option-chain fetch. Permanent SPY/QQQ coverage
is the caller's job; the funnel never hardcodes symbols.

No MCP or I/O happens here — pure shaping, unit-tested in tests/test_engine.py.
"""
from __future__ import annotations

from .reporter import conviction_score


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


_SYM_KEYS = ("symbol", "sym", "ticker")
_LAST_KEYS = ("last_trade_price", "price", "last", "last_price", "last_trade")
_PCT_KEYS = ("day_pct", "percent_change", "pct_change", "change_pct", "change_percent")
_VOL_KEYS = ("volume", "cum_volume", "day_volume")
_AVGVOL_KEYS = ("avg_volume", "average_volume", "avg_daily_volume", "average_daily_volume")
_MCAP_KEYS = ("market_cap", "Market cap", "marketcap", "mkt_cap")


def _first(row: dict, keys: tuple):
    for k in keys:
        if row.get(k) is not None:
            return row[k]
    return None


def rh_scan_rows(scan_results: list, frac_of_day: float = 1.0) -> list:
    """Canonical mapping from run_scan result rows -> funnel_candidates input (v4.14.2).

    THE unit trap this exists to fix (8/5 proven miss): the RH scanner's '% Change'
    column is a FRACTION (0.19935 = +19.9%), not a percent. Ad-hoc mappings fed it
    to the funnel as-is, so SHOP's +19.9% earnings-day rip scored as +0.2% and the
    sweep reported 'no movers'. Normalize to PERCENT here — every scan consumer
    goes through this one mapper, never hand-rolls the columns again.

    v4.15 (8/7 proven miss): the scanner's 'Relative volume' column is a FULL-DAY
    ratio (today's cum volume / avg DAILY volume), so intraday it understates real
    participation — at 12:00 ET a name pacing 1.5x prints ~0.6 and the funnel kept
    0 of 200 rows. Pass frac_of_day (minutes since 9:30 / 390) and the mapper
    converts to time-of-day-relative rvol here, same basis as rvol_now. Default 1.0
    (EOD / after-hours scans) is the unchanged full-day comparison.
    """
    frac = min(max(frac_of_day, 0.05), 1.0)
    out = []
    for r in scan_results or []:
        if r.get("instrument_type") not in (None, "EQUITY"):
            continue
        c = r.get("columns", {})
        pct = _f(c.get("% Change"))
        rvol = _f(c.get("Relative volume"))
        out.append({"symbol": r.get("ticker"), "last": c.get("Last"),
                    "day_pct": None if pct is None else pct * 100.0,
                    "rvol": None if rvol is None else round(rvol / frac, 2),
                    "volume": c.get("Volume"),
                    "market_cap": c.get("Market cap")})
    return out


def index_leader(quotes: dict, syms: tuple = ("SPY", "QQQ")) -> str | None:
    """Pick the LEADER among correlated index vehicles (v4.15, 8/7 replay lesson).

    Same thesis, same breakout window: QQQ (+1.07% day, leading all morning) paid
    ~8x what SPY (+0.56%) did on the identical 10:45-11:30 leg (720C +143% peak vs
    772C +16%). When more than one index arms on the same signal, trade the one
    with the stronger tape — rank by day_pct, rvol as tiebreak. Returns None when
    fewer than two of the syms have quotes (nothing to rank); selection only,
    every gate still binds on whichever vehicle is chosen.
    """
    ranked = []
    for s in syms:
        q = quotes.get(s)
        if not q or q.get("day_pct") is None:
            continue
        ranked.append((q["day_pct"], q.get("rvol") or 0.0, s))
    if len(ranked) < 2:
        return None
    ranked.sort(reverse=True)
    return ranked[0][2]


def funnel_candidates(scan_rows: list, quotes_meta: dict | None = None) -> list:
    """UNIVERSE FUNNEL stage 1 (v4.14): normalize raw run_scan rows.

    Scanner rows arrive with flexible keys ('symbol'/'sym', 'last_trade_price'/
    'price'/'last', 'day_pct'/'percent_change', 'rvol' OR volume+avg_volume) —
    be defensive and shape them into {sym, last, day_pct, rvol}. When rvol isn't
    supplied directly it is derived time-of-day-relative via rvol_now, using
    quotes_meta={'frac_of_day': ...} (defaults to 1.0 = full-day comparison).
    Rows without a symbol or a positive last price are dropped; unknown day_pct/
    rvol stay None (downstream decides how unknowns are treated).
    """
    frac = (quotes_meta or {}).get("frac_of_day", 1.0)
    out = []
    for row in scan_rows or []:
        if not isinstance(row, dict):
            continue
        r = row.get("quote", row)
        sym = _first(r, _SYM_KEYS)
        last = _f(_first(r, _LAST_KEYS))
        if not sym or not last or last <= 0:
            continue
        rvol = _f(r.get("rvol"))
        if rvol is None:
            rvol = rvol_now(_f(_first(r, _VOL_KEYS)), _f(_first(r, _AVGVOL_KEYS)), frac)
        out.append({"sym": str(sym).upper(), "last": last,
                    "day_pct": _f(_first(r, _PCT_KEYS)), "rvol": rvol,
                    "market_cap": _f(_first(r, _MCAP_KEYS))})
    return out


def funnel_filter(cands: list, bp: float, per_setup_usd: float, guardrails: dict) -> list:
    """UNIVERSE FUNNEL stage 2 (v4.14): cheap tradability PRE-CHECKS judged from
    equity-level data alone — decides which names are worth an option-chain fetch.

    Drops: underlying priced outside [funnel_min_underlying_usd,
    funnel_max_underlying_usd] (junk options below, budget-busting contracts
    above), rvol below funnel_rvol_min or unknown (participation must PROVE
    itself — same posture as breakout_confirmed), |day_pct| beyond
    funnel_day_pct_max_abs (gap-trap; chasing an extreme gap is how you buy the
    top). Unknown day_pct passes (it's a gap-EXCESS check, not a momentum gate).
    A per-setup budget that exceeds available BP kills the whole funnel — no
    setup is fundable. ALL thresholds come from the passed guardrails dict
    (reporter.GUARDRAILS): none live here. Option-level gates (spread/OI/delta/
    IV/affordability) still bind later at candidate_entry/final_report.
    """
    if bp is not None and per_setup_usd is not None and per_setup_usd > bp:
        return []
    lo = guardrails["funnel_min_underlying_usd"]
    hi = guardrails["funnel_max_underlying_usd"]
    out = []
    mcap_floor = guardrails["funnel_min_market_cap_usd"]
    for c in cands:
        if not (lo <= c["last"] <= hi):
            continue
        if c.get("rvol") is None or c["rvol"] < guardrails["funnel_rvol_min"]:
            continue
        day = c.get("day_pct")
        if day is not None and abs(day) > guardrails["funnel_day_pct_max_abs"]:
            continue
        # v4.14.1 recognition floor (8/5 live-run finding): unknown or sub-floor
        # market cap = meme-thin options + no recognition — never worth a chain fetch.
        mc = c.get("market_cap")
        if mc is None or mc < mcap_floor:
            continue
        out.append(c)
    return out


def funnel_rank(cands: list, top_n: int = 5) -> list:
    """UNIVERSE FUNNEL stage 3 (v4.14): rank survivors by reporter.conviction_score
    and keep the top N — the narrow list that earns an option-chain fetch.

    Only equity-level inputs exist at this stage (rvol + day momentum); delta/IV/
    VWAP contribute neutrally per conviction_score's design. Each returned cand
    carries its score as 'conviction'. Permanent SPY/QQQ coverage is the caller's
    concern — nothing is hardcoded here.
    """
    scored = [dict(c, conviction=conviction_score(
        {"rvol": c.get("rvol"), "underlying_day_pct": c.get("day_pct")}))
        for c in cands]
    scored.sort(key=lambda c: c["conviction"], reverse=True)
    return scored[:max(0, top_n)]


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
