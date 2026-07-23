"""0DTE contract selection.

Given a fired Signal and the underlying's chain snapshot, pick the single
contract to trade: today's expiry, correct type, strike nearest the signal
entry, delta ~0.45–0.55 from the broker's Greeks, and a spread no wider than
10% of mid. Anything failing -> decline (the name is skipped).
"""

from __future__ import annotations

from .config import GUARDRAILS as G
from .models import ChainSnapshot, ContractChoice, OptionContract, Signal


def select(signal: Signal, chain: ChainSnapshot) -> ContractChoice:
    want_type = signal.option_type

    zero_dte = [c for c in chain.zero_dte() if c.option_type == want_type]
    if not zero_dte:
        # No 0DTE chain that day -> skip the name (never substitute later expiry).
        return ContractChoice(None, "no 0DTE chain for this name today")

    # Rank by delta band first, then by strike proximity to the entry.
    in_band = [c for c in zero_dte if G.entry_delta_min <= abs(c.delta) <= G.entry_delta_max]
    pool = in_band or zero_dte  # fall back to nearest-strike if none are in band

    def rank(c: OptionContract) -> tuple[float, float]:
        delta_miss = abs(abs(c.delta) - 0.50)
        strike_miss = abs(c.strike - signal.entry)
        return (delta_miss, strike_miss)

    candidate = min(pool, key=rank)

    if not (G.entry_delta_min <= abs(candidate.delta) <= G.entry_delta_max):
        return ContractChoice(
            None,
            f"no contract in delta {G.entry_delta_min}–{G.entry_delta_max} "
            f"(best |Δ|={abs(candidate.delta):.2f})",
        )

    if candidate.spread_pct_of_mid > G.max_spread_pct_of_mid:
        return ContractChoice(
            None,
            f"spread {candidate.spread_pct_of_mid:.0%} > "
            f"{G.max_spread_pct_of_mid:.0%} of mid",
        )

    return ContractChoice(candidate)
