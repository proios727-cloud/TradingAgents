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

    # --- Sizing (flat, GO-LIVE.md) ---
    sizing_pct: float = 0.025          # 2.5% of CURRENT balance as premium/trade
    per_trade_cap_usd: float = 1000.0  # hard cap per trade

    # --- Exits ---
    target_premium_gain: float = 0.90  # sell at +90% premium
    stop_premium_loss: float = 0.50    # sell at -50% premium (or thesis break)
    scale_half_at_r: float = 1.0       # scale half off at +1R, trail the rest
    force_flatten_et: time = time(15, 45)  # close ALL by 15:45 ET

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
    broker: str = "robinhood"      # 'robinhood' | 'paper'

    def can_place_live(self) -> bool:
        """Live dispatch is allowed only when explicitly armed AND not dry-run."""
        return self.armed and not self.dry_run
