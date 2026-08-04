"""Binding configuration for the SuperTrades execution agent.

Every value here is the source of truth from the design handoff's **GO-LIVE.md**,
which explicitly supersedes older sections of the bundle where they conflict
(e.g. the per-strategy risk map in the terminal's ``data.js`` — GO-LIVE's sizing wins;
since 2026-08-04 that sizing is the operator-approved phase ladder below). Change nothing here without explicit operator approval;
these are the risk limits, not tunables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from zoneinfo import ZoneInfo

MARKET_TZ = ZoneInfo("America/New_York")

# Watchlist — scanned every 5 min, 09:30–16:00 ET.
WATCHLIST: tuple[str, ...] = (
    "SPY", "QQQ", "NVDA", "TSLA", "AMD", "META", "COIN", "XOM", "CVX", "XLE",
)


@dataclass(frozen=True)
class Guardrails:
    """Immutable risk limits. Evaluated in exactly one place: risk_governor."""

    # --- Instrument ---
    # 0DTE long calls/puts ONLY. No 0DTE chain that day -> skip the name.
    # No spreads, no shares, never a later expiry.
    only_0dte_long: bool = True

    # --- Sizing (phase ladder; operator-amended 2026-08-04) ---
    # GO-LIVE's flat 2.5% is unsatisfiable at small balances (2.5% of $500 buys
    # no contract), so sizing runs a phase ladder until 2.5% takes over:
    #   Kickstart  balance < $1,500  -> $75 fixed  (tiny_live's proven cap)
    #   Build      balance < $4,000  -> $100 fixed
    #   Scale      balance >= $4,000 -> 2.5% of balance (2.5% x $4k = $100,
    #              so the handoff is seamless), always capped at $1,000.
    # Red-day / week-1 half-size multipliers apply to the phase budget too.
    sizing_pct: float = 0.025          # % of CURRENT balance once in Scale phase
    per_trade_cap_usd: float = 1000.0  # hard cap per trade, all phases
    sizing_phases: tuple = ((1500.0, 75.0), (4000.0, 100.0))
    # (upper_balance_bound, fixed_premium_budget); above the last bound -> sizing_pct
    # NOTE: the settled-cash floor (balance_floor_alert_usd) denies ALL
    # automated entries at/below it. Operator-lowered $2,000 -> $300 on
    # 2026-08-04 (its own explicit decision, after guardian review flagged
    # that $2,000 kept Kickstart dormant): below $300 the account has lost
    # ~45% from the kickstart stake and the right behavior is halt + alert,
    # not smaller bets. The 15% clamp above keeps budgets sane down to it.
    kickstart_max_pct_of_balance: float = 0.15  # base fixed budget <= 15% of balance
    # (A+ conviction multiplies AFTER the clamp: effective entry <= 22.5% at 1.5x)

    # --- Conviction-tiered sizing (operator-approved 2026-08-04) ---
    # A+ (confidence >= conv_min_confidence AND rvol >= conv_min_rvol — the
    # same bar as convexity mode) sizes 1.5x the phase budget; B (scored but
    # low confidence) sizes 0.5x; unscored (confidence == 0) stays neutral.
    # Evidence for raising the A+ multiplier must come from the signal ledger.
    conviction_aplus_mult: float = 1.5
    conviction_b_mult: float = 0.5
    conviction_b_max_confidence: int = 50

    def __post_init__(self):
        bounds = [b for b, _ in self.sizing_phases]
        if bounds != sorted(bounds):   # raise (not assert): must survive python -O
            raise ValueError("sizing_phases must be sorted ascending")

    def premium_budget(self, balance: float) -> float:
        """Per-trade premium budget for ``balance`` under the phase ladder.
        The single sizing entry point — risk_governor and the monitoring
        scorer both call this so live gating and retrospective grading can
        never disagree. Fixed phase budgets are clamped to
        ``kickstart_max_pct_of_balance`` so a fixed dollar amount can never
        become an unbounded fraction of a shrinking account."""
        for bound, fixed in self.sizing_phases:
            if balance < bound:
                return min(fixed, self.per_trade_cap_usd,
                           self.kickstart_max_pct_of_balance * balance)
        return min(self.sizing_pct * balance, self.per_trade_cap_usd)

    def conviction_multiplier(self, confidence: int, rvol: float) -> float:
        """Size multiplier from signal conviction. Neutral when unscored."""
        if confidence >= self.conv_min_confidence and rvol >= self.conv_min_rvol:
            return self.conviction_aplus_mult
        if 0 < confidence < self.conviction_b_max_confidence:
            return self.conviction_b_mult
        return 1.0

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
    balance_floor_alert_usd: float = 300.0  # at/below $300 settled -> halt + alert
    # (operator-lowered from $2,000 on 2026-08-04 to open the Kickstart phase)

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
