"""GEX forward-validation — turn logged snapshots into an honest verdict.

This is the machinery the forward-log feeds. It scores each gated entry on REAL
option premium and, critically, against MATCHED baselines, so we measure edge
over drift rather than being fooled by a bull/bear tape. Owned by the
quant-strategist agent; analysis-only (never places an order).

Per the pre-registered protocol:
  * Entry fills ASK-side, exits BID-side (approximated from the mid + the
    snapshot's captured spread) — mid-to-mid is how these validations lie.
  * Exit ladder on real premium: -50% -> R=-1, +90% -> R=+1.8, else the horizon
    mark. Risk = 50% of premium paid, so R is in premium-R units.
  * Every gated entry is compared to coin-flip, anti-gate, always-long,
    always-short on the SAME contracts/horizon. Primary metric =
    mean(gate_R - coinflip_R): the gate must beat its own inverse and not merely
    ride drift.
  * Significance via SESSION-level block bootstrap (snapshots autocorrelate).
  * Decision thresholds are pre-registered in DECISION below.

An ``entry`` is a dict:
  {session, gate_dir ('long'|'short'|None), call:{mid,spread,bars}, put:{...}}
where bars is the real option OHLC over the horizon (post-session fetched via
get_option_historicals), mid/spread are captured live at snapshot time.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class EntryCfg:
    stop_pct: float = 0.50      # -50% premium == -1R
    target_pct: float = 1.90    # +90% premium == +1.8R


@dataclass(frozen=True)
class Decision:
    min_entries: int = 200
    min_sessions: int = 25
    min_edge_r: float = 0.20    # held-out paired edge vs coin-flip
    # trade only if edge >= min_edge_r AND ci_low > 0 AND beats anti-gate


def _replay(mid: float, spread: float, bars: list, cfg: EntryCfg) -> float:
    """R for buying this contract: enter ask-side, run the exit ladder on the
    real mark path, exit bid-side. bars = [(o,h,l,c), ...]."""
    entry = mid * (1 + spread / 2)          # pay the ask
    if entry <= 0:
        return 0.0
    risk = entry * (1 - cfg.stop_pct)        # premium at the stop = 50%
    stop, tgt = entry * cfg.stop_pct, entry * cfg.target_pct
    for _o, h, l, _c in bars:
        if l <= stop:
            return (stop * (1 - spread / 2) - entry) / risk
        if h >= tgt:
            return (tgt * (1 - spread / 2) - entry) / risk
    last = bars[-1][3] if bars else entry
    return (last * (1 - spread / 2) - entry) / risk


def _score_dir(direction: str, entry: dict, cfg: EntryCfg) -> float:
    leg = entry["call"] if direction == "long" else entry["put"]
    return _replay(leg["mid"], leg["spread"], leg["bars"], cfg)


def score_entry(entry: dict, cfg: EntryCfg = EntryCfg(),
                rng: random.Random | None = None) -> dict:
    """R for the gate's call and each matched baseline on the same contracts."""
    rng = rng or random.Random(hash(str(entry.get("session"))) & 0xffffffff)
    gate = entry.get("gate_dir")
    out = {
        "always_long": _score_dir("long", entry, cfg),
        "always_short": _score_dir("short", entry, cfg),
        "coinflip": _score_dir("long" if rng.random() < 0.5 else "short", entry, cfg),
    }
    if gate in ("long", "short"):
        out["gate"] = _score_dir(gate, entry, cfg)
        out["anti"] = _score_dir("short" if gate == "long" else "long", entry, cfg)
    return out


def _bootstrap_ci(by_session: dict, n: int = 10000,
                  seed: int = 7) -> tuple[float, float]:
    """95% CI for the paired edge via SESSION-level block bootstrap."""
    keys = list(by_session)
    if not keys:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means = []
    for _ in range(n):
        pool = []
        for _ in keys:
            pool.extend(by_session[rng.choice(keys)])
        means.append(sum(pool) / len(pool) if pool else 0.0)
    means.sort()
    return (means[int(0.025 * n)], means[int(0.975 * n)])


def analyze(entries: list[dict], cfg: EntryCfg = EntryCfg(),
            decision: Decision = Decision()) -> dict:
    """Aggregate scored gated entries into the honest verdict."""
    scored = []
    for e in entries:
        s = score_entry(e, cfg)
        if "gate" in s:                       # only entries the gate actually took
            scored.append((e.get("session"), s))

    n = len(scored)
    if n == 0:
        return {"n": 0, "verdict": "no gated entries yet"}

    gate = [s["gate"] for _, s in scored]
    edge_cf = [s["gate"] - s["coinflip"] for _, s in scored]
    edge_anti = [s["gate"] - s["anti"] for _, s in scored]
    by_sess: dict = {}
    for sess, s in scored:
        by_sess.setdefault(sess, []).append(s["gate"] - s["coinflip"])

    mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
    ci_lo, ci_hi = _bootstrap_ci(by_sess)
    sessions = len(by_sess)
    paired = mean(edge_cf)

    powered = n >= decision.min_entries and sessions >= decision.min_sessions
    passes = paired >= decision.min_edge_r and ci_lo > 0 and mean(edge_anti) > 0
    if not powered:
        verdict = (f"INCONCLUSIVE — {n}/{decision.min_entries} entries, "
                   f"{sessions}/{decision.min_sessions} sessions. Keep logging.")
    elif passes:
        verdict = "TRADE (half size, keep logging) — powered, edge > threshold, CI>0, beats anti-gate"
    else:
        verdict = "KILL — powered but edge below threshold / CI straddles 0 / no beat vs anti-gate"

    return {
        "n": n, "sessions": sessions,
        "gate_mean_r": round(mean(gate), 3),
        "gate_win_rate": round(sum(1 for g in gate if g > 0) / n, 3),
        "paired_edge_vs_coinflip": round(paired, 3),
        "paired_edge_vs_anti": round(mean(edge_anti), 3),
        "edge_ci95": (round(ci_lo, 3), round(ci_hi, 3)),
        "always_long_mean_r": round(mean([s["always_long"] for _, s in scored]), 3),
        "always_short_mean_r": round(mean([s["always_short"] for _, s in scored]), 3),
        "powered": powered,
        "verdict": verdict,
    }
