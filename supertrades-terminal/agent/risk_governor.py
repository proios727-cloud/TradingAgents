"""The single guardrail gate.

Every entry guardrail from GO-LIVE.md is evaluated here and NOWHERE else. No
other component (scanner, contract selector, exit manager, broker) re-checks or
weakens these — they trust the verdict. This is the one place to read to know
exactly when the agent is allowed to open a position, and how big.

Order of checks matters only for which reason surfaces first; all are hard
denials except sizing, which returns the allotted budget.
"""

from __future__ import annotations

import math
from datetime import datetime

from .config import GUARDRAILS as G
from .config import RuntimeConfig
from .clock import at_or_past_flatten, in_no_entry_window, in_session
from .models import AccountState, DayState, RiskVerdict, Signal


def evaluate(
    signal: Signal,
    account: AccountState,
    day: DayState,
    now: datetime,
    ask_premium: float,
    cfg: RuntimeConfig,
    *,
    held_symbols: frozenset[str] = frozenset(),
    earnings_symbols: frozenset[str] = frozenset(),
) -> RiskVerdict:
    """Decide whether ``signal`` may become a live entry, and for how much.

    ``ask_premium`` is the per-contract ask of the chosen contract (used for
    sizing and the settled-cash check). ``held_symbols`` and
    ``earnings_symbols`` are precomputed by the discovery step before fan-out —
    the governor never reaches back into broker state itself.
    """
    reasons: list[str] = []

    # --- Session windows -------------------------------------------------
    if not in_session(now):
        return RiskVerdict.deny("outside RTH (09:30–16:00 ET)")
    if at_or_past_flatten(now):
        return RiskVerdict.deny("at/after 15:45 ET flatten — no new entries")
    if in_no_entry_window(now):
        return RiskVerdict.deny("in first-15/last-10-min no-entry window")

    # --- Daily halt (entries stop; exits stay live elsewhere) ------------
    if day.halted:
        return RiskVerdict.deny("session halted")
    if day.day_r <= G.daily_halt_r:
        return RiskVerdict.deny(f"daily halt: day R {day.day_r:.2f} <= {G.daily_halt_r}")

    # --- Cash-account settlement floor -----------------------------------
    if account.settled_cash <= G.balance_floor_alert_usd:
        return RiskVerdict.deny(
            f"settled cash ${account.settled_cash:,.0f} at/below "
            f"${G.balance_floor_alert_usd:,.0f} floor — halt + alert"
        )

    # --- Entry confirmation: ALL FOUR must hold --------------------------
    if not signal.setup_fired:
        return RiskVerdict.deny("no setup fired")
    if signal.rvol < G.rvol_min:
        return RiskVerdict.deny(f"RVOL {signal.rvol:.2f} < {G.rvol_min}")
    if not signal.index_aligned:
        return RiskVerdict.deny("index not aligned with trade")
    if not signal.structural_level_near_stop:
        return RiskVerdict.deny("no structural level near stop")

    # --- Earnings block (within 3 sessions) ------------------------------
    if signal.symbol in earnings_symbols:
        return RiskVerdict.deny(f"{signal.symbol} has earnings within "
                                f"{G.earnings_block_sessions} sessions")

    # --- Never average down / double a held name -------------------------
    if signal.symbol in held_symbols:
        return RiskVerdict.deny(f"already holding {signal.symbol} — no adding/averaging")

    # --- Sizing: phase ladder (config.premium_budget), red-day / week1 mults ---
    # Build a size multiplier and a hard cap, then apply once.
    mult = 1.0
    cap = G.per_trade_cap_usd
    if day.yesterday_red:
        mult *= 0.5
        reasons.append("half-size (day after red)")
    if cfg.week1_half_size:
        mult *= 0.5
        cap = min(cap, G.per_trade_cap_usd * 0.5)  # week-1: $500 cap / half risk
        reasons.append("week-1 half-size ($500 cap)")
    budget = min(G.premium_budget(account.balance) * mult, cap)
    # Press rule: only once >= +2R is booked, later trades may size up 2x,
    # funded strictly by the day's booked profit (never base bankroll).
    if day.booked_profit_r >= G.press_min_booked_r and day.entries_today > 0:
        extra = min(budget * (G.press_multiplier - 1.0), day.booked_profit_r * budget)
        budget += extra
        reasons.append("press rule: sized up from booked profit")

    if ask_premium <= 0:
        return RiskVerdict.deny("no valid ask premium")
    cost_per_contract = ask_premium * 100.0
    max_contracts = int(math.floor(budget / cost_per_contract))

    # Never let open premium exceed settled cash; never buy with unsettled.
    affordable = int(math.floor(account.settled_cash / cost_per_contract))
    max_contracts = min(max_contracts, affordable)

    if max_contracts < 1:
        return RiskVerdict.deny(
            f"cannot afford 1 contract: budget ${budget:,.0f}, "
            f"settled ${account.settled_cash:,.0f}, contract ${cost_per_contract:,.0f}"
        )

    reasons.insert(0, f"allow: {max_contracts}x @ ~${ask_premium:.2f} "
                      f"(budget ${budget:,.0f})")
    return RiskVerdict(allow=True, premium_budget=budget,
                       max_contracts=max_contracts, reasons=reasons)
