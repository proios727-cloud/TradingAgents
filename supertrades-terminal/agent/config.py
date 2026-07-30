"""Binding configuration for the SuperTrades execution agent.

Every value here is the source of truth from the design handoff's **GO-LIVE.md**,
which explicitly supersedes older sections of the bundle where they conflict
(e.g. the per-strategy risk map in the terminal's ``data.js`` — GO-LIVE's flat
2.5% / $1k sizing wins). Change nothing here without explicit operator approval;
these are the risk limits, not tunables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from zoneinfo import ZoneInfo

MARKET_TZ = ZoneInfo("America/New_York")

# Watchlist — scanned every 5 min, 09:30–16:00 ET.
#
# This is a scan universe, not a directional view: the agent trades 0DTE long
# calls AND puts, so a name earns its slot by being liquid and by actually
# moving, whichever way. Reviewed 2026-07-30 against the leadership rotation
# out of mega-cap tech and into cyclicals/defensives (industrials, healthcare,
# financials, energy, small caps) with crude near $100 on geopolitical risk.
#
# Note the 0DTE guardrail below: only SPY/QQQ/IWM list daily expiries, so the
# single names and sector ETFs here are tradeable on Fridays (and their own
# weekly expiries) and are skipped on other sessions.
#
#   SPY/QQQ/IWM  index core — daily chains; IWM added for the small-cap leg
#                of the rotation, which SPY/QQQ do not express
#   NVDA/AMD/    high-ATR tech movers — still the highest-RVOL names on the
#   TSLA/META    tape in both directions during the de-rating
#   XOM/XLE      energy leadership, crude-driven
#   XLF/XLV      financials + healthcare — the two sectors absorbing the
#                rotation bid most consistently
#   GLD          geopolitical/rate hedge; bid on the same headlines that hit
#                the index, so it gives the scanner a non-correlated leg
#
# Dropped 2026-07-30: CVX (redundant with XOM + XLE, thinner chain),
# COIN (crypto beta is not part of the current leadership theme).
WATCHLIST: tuple[str, ...] = (
    "SPY", "QQQ", "IWM",
    "NVDA", "AMD", "TSLA", "META",
    "XOM", "XLE", "XLF", "XLV", "GLD",
)


@dataclass(frozen=True)
class Guardrails:
    """Immutable risk limits. Evaluated in exactly one place: risk_governor."""

    # --- Instrument ---
    # 0DTE long calls/puts ONLY. No 0DTE chain that day -> skip the name.
    # No spreads, no shares, never a later expiry.
    only_0dte_long: bool = True

    # --- Sizing (flat, GO-LIVE.md) ---
    sizing_pct: float = 0.025          # 2.5% of CURRENT balance as premium/trade
    per_trade_cap_usd: float = 1000.0  # hard cap per trade

    # --- Exits ---
    target_premium_gain: float = 0.90  # sell at +90% premium
    stop_premium_loss: float = 0.50    # sell at -50% premium (or thesis break)
    scale_half_at_r: float = 1.0       # scale half off at +1R, trail the rest
    force_flatten_et: time = time(15, 45)  # close ALL by 15:45 ET

    # --- Trailing stop on the runner (only active when RuntimeConfig.scale_and_trail) ---
    # After scaling half at +1R, protect the remainder with a peak-give-back trail
    # instead of a hard full-position target. The trail only ratchets up — it can
    # never widen the fixed -50% premium stop above, which always remains the floor.
    trail_activate_gain: float = 1.0   # arm the trail once the mark is >= +100% (i.e. +1R on the option)
    trail_give_back_pct: float = 0.30  # exit the runner if the mark gives back >= 30% from its peak

    # --- Daily rules ---
    daily_halt_r: float = -2.0         # down 2R on the day -> entries stop (exits stay live)
    press_min_booked_r: float = 2.0    # up >=+2R -> later trades may size up 2x...
    press_multiplier: float = 2.0      # ...funded only by the day's booked profit
    earnings_block_sessions: int = 3   # no entries in names with earnings within 3 sessions
    no_entry_open_minutes: int = 15    # no entries in the first 15 min (09:30–09:45)
    no_entry_close_minutes: int = 10   # no entries in the last 10 min (15:50–16:00)

    # --- Entry confirmation (ALL FOUR required) ---
    rvol_min: float = 1.4              # RVOL >= 1.4x on the move
    # (setup fired, index aligned, structural level near stop — booleans on the Signal)

    # --- Contract selection ---
    entry_delta_min: float = 0.45
    entry_delta_max: float = 0.55
    max_spread_pct_of_mid: float = 0.10  # reject if bid/ask spread > 10% of mid
    reprice_after_seconds: float = 5.0   # limit at mid, reprice once after 5s
    max_reprice_misses: int = 2          # abandon after 2 misses

    # --- Convexity selection (only active when RuntimeConfig.convexity_selection) ---
    # On high-conviction signals, allow cheaper/more-convex contracts (down to
    # conv_delta_floor) and pick the one with the best estimated return on the
    # expected move to target (Δ·M + ½·Γ·M²), instead of the plain ~0.50-delta
    # pick. Only engages when confidence AND RVOL clear the bars below — a hard
    # delta floor keeps it off lottery tickets. The spread and 0DTE guards still apply.
    conv_delta_floor: float = 0.30       # never below this |Δ|, even chasing convexity
    conv_min_confidence: int = 70        # signal confidence required to use convexity mode
    conv_min_rvol: float = 1.8           # RVOL required to use convexity mode

    # --- Cash-account settlement (T+1) ---
    # Never buy with unsettled proceeds; open premium must never exceed settled cash.
    balance_floor_alert_usd: float = 2000.0  # nearing $2,000 -> halt + alert

    # --- Kill switch ---
    stale_data_seconds: float = 10.0     # data stale >10s -> kill
    consecutive_loss_kill: int = 3       # 3 straight losses -> flatten + halt

    # --- Session / cadence ---
    session_open_et: time = time(9, 30)
    session_close_et: time = time(16, 0)
    scan_interval_seconds: int = 300     # 5 min


GUARDRAILS = Guardrails()


@dataclass
class RuntimeConfig:
    """Mutable per-run switches. Safe defaults = fully inert (dry run, disarmed)."""

    account_number: str | None = None
    # Master safety switches -----------------------------------------------
    dry_run: bool = True          # True => no live order is ever dispatched
    armed: bool = False           # operator must explicitly arm; even then dry_run gates
    require_entry_approval: bool = True   # preview-every-order for ENTRIES
    # Protective exits (stop/target/15:45 flatten) submit automatically when
    # armed — blocking a stop-loss on manual approval would defeat risk control.
    require_exit_approval: bool = False
    week1_half_size: bool = False  # week-1 caps at half size ($500 / half %)
    # When True, exits scale half at +1R and TRAIL the runner (peak give-back)
    # instead of a hard +90% full-position target. Mirrors the terminal's
    # "Auto-scale out at +1R" switch. Default off = historical target behavior.
    scale_and_trail: bool = False
    # When True, high-conviction signals select the best delta/gamma combo by
    # estimated return on the expected move (convexity), allowing cheaper OTM
    # contracts down to the delta floor. Default off = plain ~0.50-delta pick.
    convexity_selection: bool = False
    broker: str = "robinhood"      # 'robinhood' | 'paper'

    def can_place_live(self) -> bool:
        """Live dispatch is allowed only when explicitly armed AND not dry-run."""
        return self.armed and not self.dry_run
