"""0DTE contract selection.

Given a fired Signal and the underlying's chain snapshot, pick the single
contract to trade: today's expiry, correct type, and a spread no wider than 10%
of mid. Anything failing -> decline (the name is skipped).

Two selection modes, chosen by ``RuntimeConfig.convexity_selection`` (default off):

  * DEFAULT — strike nearest the signal entry, delta ~0.45–0.55 from the broker's
    Greeks. The safe ATM pick; exactly the historical behavior.
  * CONVEXITY — only on high-conviction signals (confidence and RVOL past the
    conv_* bars), consider cheaper/more-convex contracts down to conv_delta_floor
    and pick the one with the best estimated return on the expected move to
    target (Δ·M + ½·Γ·M²). Falls back to the default pick when the signal isn't
    convincing enough, gamma data is missing, or no contract qualifies.

The spread guard and 0DTE-only rule apply in BOTH modes.
"""

from __future__ import annotations

from .config import GUARDRAILS as G
from .config import RuntimeConfig
from .models import ChainSnapshot, ContractChoice, OptionContract, Signal


def _spread_ok(c: OptionContract) -> bool:
    return c.spread_pct_of_mid <= G.max_spread_pct_of_mid


def _default_pick(signal: Signal, zero_dte: list[OptionContract]) -> ContractChoice:
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

    if not _spread_ok(candidate):
        return ContractChoice(
            None,
            f"spread {candidate.spread_pct_of_mid:.0%} > "
            f"{G.max_spread_pct_of_mid:.0%} of mid",
        )

    return ContractChoice(candidate)


def _convexity_pick(signal: Signal, zero_dte: list[OptionContract]) -> ContractChoice | None:
    """Best delta/gamma combo by estimated return on the move to target. Returns
    None to signal "fall back to the default pick" (weak signal, no gamma data,
    or nothing qualifies) — never a hard decline, so convexity mode can only
    upgrade a selection, never block a trade the default would have taken."""
    if signal.confidence < G.conv_min_confidence or signal.rvol < G.conv_min_rvol:
        return None  # not convincing enough — use the safe ATM pick

    move = abs(signal.target - signal.entry)
    if move <= 0:
        return None

    # Tradable pool: cheap enough to be convex but not a lottery ticket, spread
    # sane, and gamma actually present (else the score is delta-only = no signal).
    pool = [
        c for c in zero_dte
        if G.conv_delta_floor <= abs(c.delta) <= G.entry_delta_max
        and c.gamma > 0.0
        and _spread_ok(c)
    ]
    if not pool:
        return None

    # Highest estimated return on the expected move wins; break ties toward more
    # delta (more directional certainty) so we don't over-reach on convexity.
    best = max(pool, key=lambda c: (c.est_return_on_move(move), abs(c.delta)))
    return ContractChoice(best)


def select(
    signal: Signal,
    chain: ChainSnapshot,
    cfg: RuntimeConfig | None = None,
) -> ContractChoice:
    want_type = signal.option_type

    zero_dte = [c for c in chain.zero_dte() if c.option_type == want_type]
    if not zero_dte:
        # No 0DTE chain that day -> skip the name (never substitute later expiry).
        return ContractChoice(None, "no 0DTE chain for this name today")

    if cfg and cfg.convexity_selection:
        convex = _convexity_pick(signal, zero_dte)
        if convex is not None:
            return convex

    return _default_pick(signal, zero_dte)
