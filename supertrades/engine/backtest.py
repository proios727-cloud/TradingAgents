"""Backtest harness — measure the exit rules on real trade paths (v4.12).

Turns "90/90 tests pass" (correctness) into "here's the expectancy + drawdown" (does it pay).
It replays an option PRICE PATH for each historical trade through the ACTUAL engine exit
evaluator (`nodes.position_exit`) with rules built by the ACTUAL `materialize_exit_rules`,
so what it measures is what ships — then scores the objective and compares the current rules
against the old flat +50/-30 baseline on the SAME paths.

Data honesty: the built-in paths are RECONSTRUCTED from each trade's known key points
(entry, peak, exit) — directional, not tick data. Swap in real intraday marks
(get_option_historicals) for precision; the harness doesn't change.

Run:  python -m supertrades.engine.backtest
"""
from __future__ import annotations

import asyncio

from .nodes import position_exit, expected_move_exits
from .reporter import (AGENTIC_ACCT, materialize_exit_rules, conviction_score)
from .evolution import recompute_performance, max_drawdown_usd, score_objective


def _path(entry: float, waypoints: list[float], steps_between: int = 10) -> list[float]:
    """Linearly interpolate a mark path through waypoints (entry first)."""
    pts = [entry] + waypoints
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        for i in range(1, steps_between + 1):
            out.append(round(a + (b - a) * i / steps_between, 4))
    return out


# The visible week, reconstructed from the ledger's key points (entry -> peak -> reversal).
# greeks are best-known / estimated; used only to derive the NEW rules' EM exit levels.
TRADES = [
    {"name": "SPY 8/4 771C", "entry": 0.75, "qty": 1,
     "greeks": dict(iv=0.12, delta=0.45, gamma=0.08, spot=771, dte=0),
     "path": _path(0.75, [1.275, 1.15])},                       # +70% peak, sold +64%
    {"name": "QQQ 8/4 724C", "entry": 0.64, "qty": 1,
     "greeks": dict(iv=0.37, delta=0.44, gamma=0.09, spot=724, dte=0),
     "path": _path(0.64, [1.43, 0.64])},                         # +123% peak, cratered
    {"name": "INTC 8/5 102C", "entry": 1.99, "qty": 1,
     "greeks": dict(iv=1.25, delta=0.45, gamma=0.058, spot=100, dte=1),
     "path": _path(1.99, [2.35, 1.99])},                         # +18% peak, faded
    {"name": "NVDA 7/31 220C", "entry": 1.03, "qty": 1,
     "greeks": dict(iv=0.55, delta=0.42, gamma=0.03, spot=118, dte=7),
     "path": _path(1.03, [1.10, 0.46])},                         # small pop then -55%
    {"name": "DIS 8/21 110C", "entry": 0.65, "qty": 1,
     "greeks": dict(iv=0.40, delta=0.40, gamma=0.03, spot=108, dte=28),
     "path": _path(0.65, [0.70, 0.375])},                        # -42%
    {"name": "RIVN 7/24 19c", "entry": 0.58, "qty": 1,
     "greeks": dict(iv=0.70, delta=0.38, gamma=0.05, spot=18.6, dte=3),
     "path": _path(0.58, [0.62, 0.07])},                         # -88% (outage stop)
]

FLAT_BASELINE = [{"type": "target", "pct": 50, "mech": "sell_limit_at_mark"},
                 {"type": "stop", "pct": -30, "mech": "sell_limit_at_bid"}]


async def simulate_trade(entry: float, path: list[float], exit_rules: list[dict],
                         qty: int = 1) -> dict:
    """Step a mark path through the real position_exit evaluator; return realized P&L.

    Applies trips the way reporter.final_report does: ratchet_arm -> flag; target -> scale-out
    (if multi-lot) / hold (runner) / sell-all (plain); any stop/trail -> sell the remainder.
    Anything still open at the end of the path exits at the last mark (session close).
    """
    pos = {"contract": "SIM", "account": AGENTIC_ACCT, "qty": qty, "entry": entry,
           "hwm": entry, "ratchet_engaged": False, "scaled_out": False,
           "class": "day_trade", "exit_rules": exit_rules}
    target_rule = next((r for r in exit_rules if r["type"] == "target"), {})
    remaining, realized, peak = qty, 0.0, entry
    for mark in path:
        if remaining <= 0:
            break
        peak = max(peak, mark)
        pos["hwm"], pos["qty"] = peak, remaining
        snap = {"option_quotes": {"SIM": {"mark": mark, "bid": mark}},
                "quotes": {}, "vwap": {}, "prior": {"marks": {}}}
        res = await position_exit({"position": pos, "id": "SIM"}, snap)
        for trip in res.get("trips", []):
            rule = trip["rule"]
            if rule == "ratchet_arm":
                pos["ratchet_engaged"] = True
            elif rule == "target":
                frac = target_rule.get("scale_out_frac")
                if frac and remaining > 1 and not pos["scaled_out"]:
                    sell = max(1, int(qty * frac))
                    realized += (mark - entry) * 100 * sell
                    remaining -= sell
                    pos["scaled_out"] = True
                elif not target_rule.get("runner"):        # plain flat target -> sell all
                    realized += (mark - entry) * 100 * remaining
                    remaining = 0
                # runner target -> hold, let the trail work
            elif rule in ("progressive_stop", "giveback", "stop", "ratchet_stop",
                          "underlying_vwap_stop"):
                realized += (mark - entry) * 100 * remaining
                remaining = 0
            if remaining <= 0:
                break
    if remaining > 0:                                     # ran to the close -> flatten
        realized += (path[-1] - entry) * 100 * remaining
    return {"pnl_usd": round(realized, 2),
            "pct": round((path[-1] - entry) / entry * 100, 1),
            "peak_pct": round((peak - entry) / entry * 100, 1)}


def _rules_for(trade: dict, ruleset: str) -> list[dict]:
    if ruleset == "flat":
        return [dict(r) for r in FLAT_BASELINE]
    g = trade["greeks"]
    em = expected_move_exits(entry=trade["entry"], iv=g["iv"], delta=g["delta"],
                             gamma=g["gamma"], spot=g["spot"], dte=g["dte"])
    return materialize_exit_rules("day_trade", trade["qty"], {},
                                  target_pct=em["target_pct"], stop_pct=em["stop_pct"])


async def run_backtest(trades: list[dict] | None = None) -> dict:
    trades = trades or TRADES
    out = {}
    for ruleset in ("flat", "current"):
        ledger = []
        for t in trades:
            r = await simulate_trade(t["entry"], t["path"], _rules_for(t, ruleset), t["qty"])
            ledger.append({"contract": t["name"], **r})
        perf = recompute_performance(ledger)
        mdd = max_drawdown_usd(ledger)
        out[ruleset] = {"ledger": ledger, "perf": perf, "max_drawdown_usd": mdd,
                        "objective": score_objective(perf, mdd)}
    return out


def main() -> int:
    res = asyncio.run(run_backtest())
    for name, label in (("flat", "FLAT baseline (+50/-30)"), ("current", "CURRENT rules")):
        b = res[name]
        print(f"\n=== {label} ===")
        for row in b["ledger"]:
            print(f"  {row['contract']:16} peak {row['peak_pct']:>6}%  -> P&L {row['pnl_usd']:>7}")
        p = b["perf"]
        print(f"  win {p['win_rate']:.0%}  exp ${p['expectancy_per_trade_usd']}/trade  "
              f"gross ${p['gross_pnl_usd']}  maxDD ${b['max_drawdown_usd']}  "
              f"OBJECTIVE {b['objective']}")
    print(f"\nobjective delta (current - flat): "
          f"{round(res['current']['objective'] - res['flat']['objective'], 2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
