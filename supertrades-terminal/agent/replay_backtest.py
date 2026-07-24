"""Real 0DTE backtest — replays SuperTrades signals on REAL bars.

Unlike the terminal's ``genBacktest`` (a seeded *simulation* that assumes its
own win rate), this fills every trade on **real historical option premium**.
Signals fire on the real underlying 5-min bars; a long buys the real ATM call,
a short buys the real ATM put, and exits are checked bar-by-bar against the
option's actual OHLC. Nothing is modeled — the win rate and R fall out of real
price action.

Data comes from the Robinhood MCP (validated live): ``get_equity_historicals``
for the underlying and ``get_option_historicals`` for the ATM call/put of that
session's 0DTE expiry. Gather a day into the fixture shape below and replay it:

    python -m agent.replay_backtest agent/tests/fixtures/spy_0dte_2026-07-24.json

Honest scope: entries here are the TA-expressible subset (VWAP reclaim +
RVOL) — GEX/flow confluence is not in this data, so results are a conservative
floor on the live signal. One session is an illustration; run many for an edge.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict

Bar = tuple  # (open, high, low, close[, volume])


@dataclass(frozen=True)
class BtConfig:
    stop_pct: float = 0.50      # -50% premium == -1R
    target_pct: float = 1.90    # +90% premium
    rvol_min: float = 1.4
    rvol_lookback: int = 10
    open_et_min: int = 9 * 60 + 30   # 09:30 ET, bar 0
    bar_minutes: int = 5


@dataclass
class Trade:
    bar: int
    et: str
    side: str
    entry: float
    exit: float
    reason: str
    r: float
    pnl_1lot: float


def _session_vwap(underlying: list[Bar]) -> list[float]:
    out, cum_pv, cum_v = [], 0.0, 0.0
    for o, h, l, c, v in underlying:
        tp = (h + l + c) / 3.0
        cum_pv += tp * v
        cum_v += v
        out.append(cum_pv / cum_v if cum_v else c)
    return out


def _rvol(underlying: list[Bar], i: int, n: int) -> float:
    lo = max(0, i - n)
    prior = [underlying[j][4] for j in range(lo, i)]
    avg = sum(prior) / len(prior) if prior else underlying[i][4]
    return underlying[i][4] / avg if avg else 0.0


def _et(bar: int, cfg: BtConfig) -> str:
    m = cfg.open_et_min + bar * cfg.bar_minutes
    return f"{m // 60:02d}:{m % 60:02d}"


def run(underlying: list[Bar], call: list[Bar], put: list[Bar],
        cfg: BtConfig = BtConfig()) -> dict:
    """Replay the strategy over aligned underlying/call/put bar series."""
    n = len(underlying)
    vwap = _session_vwap(underlying)
    trades: list[Trade] = []

    i = 1
    while i < n - 1:
        c_now, c_prev = underlying[i][3], underlying[i - 1][3]
        rv = _rvol(underlying, i, cfg.rvol_lookback)
        long_sig = c_prev <= vwap[i - 1] and c_now > vwap[i] and rv >= cfg.rvol_min
        short_sig = c_prev >= vwap[i - 1] and c_now < vwap[i] and rv >= cfg.rvol_min
        if not (long_sig or short_sig):
            i += 1
            continue

        opt = call if long_sig else put
        entry = opt[i + 1][0]           # fill at NEXT bar open — no lookahead
        if entry <= 0:
            i += 1
            continue
        stop, tgt = entry * cfg.stop_pct, entry * cfg.target_pct

        exit_px, why, j = None, "", i + 1
        while j < n:
            _o, h, l, _c = opt[j]
            if l <= stop:               # stop takes priority if both hit
                exit_px, why = stop, f"stop -{(1-cfg.stop_pct)*100:.0f}%"
                break
            if h >= tgt:
                exit_px, why = tgt, f"target +{(cfg.target_pct-1)*100:.0f}%"
                break
            j += 1
        if exit_px is None:
            exit_px, why = opt[n - 1][3], "close (end of data)"

        r = (exit_px - entry) / (entry * (1 - cfg.stop_pct))
        trades.append(Trade(i, _et(i, cfg), "LONG" if long_sig else "SHORT",
                            round(entry, 2), round(exit_px, 2), why,
                            round(r, 2), round((exit_px - entry) * 100, 0)))
        i = j + 1                        # flat until this trade closes

    n_t = len(trades)
    wins = sum(1 for t in trades if t.r > 0)
    sum_r = sum(t.r for t in trades)
    return {
        "trades": [asdict(t) for t in trades],
        "count": n_t,
        "win_rate": (wins / n_t) if n_t else 0.0,
        "avg_r": (sum_r / n_t) if n_t else 0.0,
        "total_r": sum_r,
        "pnl_1lot": sum(t.pnl_1lot for t in trades),
    }


def _print(res: dict, meta: str = "") -> None:
    print(f"REAL 0DTE backtest {meta}\n")
    print(f"{'time':>6} {'side':>5} {'entry':>7} {'exit':>7} {'R':>7}  {'$1-lot':>8}  reason")
    print("-" * 58)
    for t in res["trades"]:
        print(f"{t['et']:>6} {t['side']:>5} {t['entry']:7.2f} {t['exit']:7.2f} "
              f"{t['r']:+7.2f}  {t['pnl_1lot']:+8.0f}  {t['reason']}")
    print("-" * 58)
    if res["count"]:
        print(f"\ntrades {res['count']} | win {res['win_rate']*100:.0f}% | "
              f"avg {res['avg_r']:+.2f}R | total {res['total_r']:+.2f}R | "
              f"P&L 1-lot each {res['pnl_1lot']:+.0f}$")
    else:
        print("\nno signals fired in this session")


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("usage: python -m agent.replay_backtest <fixture.json>")
        return 2
    with open(argv[0], encoding="utf-8") as f:
        d = json.load(f)
    cfg = BtConfig(**d.get("config", {}))
    res = run([tuple(b) for b in d["underlying"]],
              [tuple(b) for b in d["call"]],
              [tuple(b) for b in d["put"]], cfg)
    _print(res, d.get("meta", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
