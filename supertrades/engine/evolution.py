"""Evolution loop — the system keeps updating and improving a little each cycle (v4.7).

Three cadences, all pure/deterministic here (the loop does the I/O):
  - per close   -> recompute_performance(trades) : win-rate / expectancy from the ledger
  - per EOD     -> reflect(state) : surface concrete, safe improvement candidates from
                    the day's outcomes vs the rails (the human/loop applies them)
  - continuous  -> state.json is the memory; each session reads it and carries the
                    ledger + open hypotheses forward, so small gains compound.

No thresholds are *enforced* here (that stays in reporter.py, the single gate) — this
module only measures and suggests. Applying a tweak is a logged, reversible edit.
"""
from __future__ import annotations


def recompute_performance(trades: list[dict]) -> dict:
    """Roll a structured trade ledger into the performance summary.

    trades: [{"pnl_usd": float, ...}, ...] — only entries with a numeric pnl_usd count
    (open positions carry pnl_usd=None). Pure; safe on an empty ledger.
    """
    closed = [t for t in trades if isinstance(t.get("pnl_usd"), (int, float))]
    n = len(closed)
    wins = [t for t in closed if t["pnl_usd"] > 0]
    losses = [t for t in closed if t["pnl_usd"] <= 0]
    gross = sum(t["pnl_usd"] for t in closed)
    avg_win = round(sum(t["pnl_usd"] for t in wins) / len(wins), 2) if wins else 0.0
    avg_loss = round(sum(t["pnl_usd"] for t in losses) / len(losses), 2) if losses else 0.0
    return {
        "trades_closed": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / n, 2) if n else 0.0,
        "gross_pnl_usd": round(gross, 2),
        "avg_win_usd": avg_win,
        "avg_loss_usd": avg_loss,
        "expectancy_per_trade_usd": round(gross / n, 2) if n else 0.0,
    }


def reflect(state: dict) -> list[dict]:
    """Surface concrete, safe improvement candidates from the ledger + recent outcomes.

    Returns a list of {area, observation, suggestion, auto_safe} — auto_safe=True means
    it only TIGHTENS risk or fixes a proven miss (the loop may apply it and log it);
    auto_safe=False means it loosens risk or is structural and needs explicit user OK.
    Deterministic: same state -> same suggestions, so it can run unattended each EOD.
    """
    trades = state.get("trades", [])
    perf = recompute_performance(trades)
    out: list[dict] = []

    closed = [t for t in trades if isinstance(t.get("pnl_usd"), (int, float))]
    losses = [t for t in closed if t["pnl_usd"] <= 0]

    # 1. Oversized losses => stops slipped; tightening the exit is always safe.
    big = [t for t in losses if isinstance(t.get("pct"), (int, float)) and t["pct"] <= -40]
    if big:
        names = ", ".join(t.get("contract", "?") for t in big)
        out.append({"area": "loss_control",
                    "observation": f"{len(big)} loss(es) past -40% ({names}) — stops slipped the -30% line",
                    "suggestion": "marketable stops + no single-name overnight gap; consider a -25% hard cap on low-conviction",
                    "auto_safe": True})

    # 2. Winners round-tripping => green_lock / trail is the fix (tighten = safe).
    gave_back = [t for t in closed
                 if isinstance(t.get("peak_pct"), (int, float))
                 and isinstance(t.get("pct"), (int, float))
                 and t["peak_pct"] - t["pct"] >= 40]
    if gave_back:
        names = ", ".join(t.get("contract", "?") for t in gave_back)
        out.append({"area": "give_back",
                    "observation": f"{len(gave_back)} winner(s) round-tripped >=40% of peak ({names})",
                    "suggestion": "green_lock earlier and/or a stricter give-back peak_frac on the runner",
                    "auto_safe": True})

    # 3. Low win rate with positive expectancy => scale-out earlier to bank more wins.
    if perf["trades_closed"] >= 5 and perf["win_rate"] < 0.5 and perf["expectancy_per_trade_usd"] > 0:
        out.append({"area": "win_rate",
                    "observation": f"win rate {perf['win_rate']:.0%} but expectancy +${perf['expectancy_per_trade_usd']}/trade",
                    "suggestion": "size to >=2 lots so leg-A scale-out locks more days green without capping runners",
                    "auto_safe": False})

    # 4. Execution-layer: competing-trigger exits are a coordination miss, not a rules one.
    if any("competing" in (t.get("note", "").lower()) for t in closed):
        out.append({"area": "execution",
                    "observation": "a competing session's trigger exited a position early",
                    "suggestion": "audit triggers at session start; one executor only",
                    "auto_safe": True})

    return out
