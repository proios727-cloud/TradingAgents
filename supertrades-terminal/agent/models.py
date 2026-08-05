"""Typed data models passed between the agent's independent components.

Components never read each other's internals — they exchange these plain
dataclasses. This keeps every node narrow: the risk governor sees a Signal +
AccountState + DayState and returns a RiskVerdict; the contract selector sees a
Signal + ChainSnapshot and returns a ContractChoice; and so on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal, Optional

Direction = Literal["long", "short"]
OptionType = Literal["call", "put"]


@dataclass
class Signal:
    """A fired setup for one underlying at scan time.

    The four entry-confirmation booleans map to GO-LIVE's required conditions;
    the risk governor requires ALL of them plus RVOL >= 1.4x.
    """

    symbol: str
    direction: Direction
    strategy: str
    entry: float
    stop: float
    target: float
    time: str = ""
    # --- entry confirmation inputs ---
    setup_fired: bool = False
    rvol: float = 0.0
    index_aligned: bool = False
    structural_level_near_stop: bool = False
    confidence: int = 0
    # "momentum" (flip break, air-pocket run, hedge exhaustion, HOD break) or
    # "reversion" (king-node bounce, gap fill). Momentum-class signals get
    # convexity contract selection by default (operator standing directive
    # 2026-08-04: max gamma/delta for short explosive moves). "" = untagged ->
    # historical selection behavior.
    setup_class: str = ""
    # True when the scanner re-fired this setup as a validated CONTINUATION
    # after a profitable same-session exit (reclaim of the exit level or new
    # session high). The risk governor requires this flag — plus cooldown and
    # the per-name cap — before allowing a half-size re-entry.
    is_reentry: bool = False

    @property
    def option_type(self) -> OptionType:
        return "call" if self.direction == "long" else "put"


@dataclass
class OptionContract:
    """A single option instrument with a live quote and Greeks."""

    option_id: str
    symbol: str
    option_type: OptionType
    strike: float
    expiration: date
    bid: float
    ask: float
    delta: float
    gamma: float = 0.0                 # dΔ/dS — convexity; drives cheaper-OTM scoring

    @property
    def mid(self) -> float:
        return round((self.bid + self.ask) / 2.0, 2)

    @property
    def spread_pct_of_mid(self) -> float:
        m = self.mid
        return (self.ask - self.bid) / m if m > 0 else float("inf")

    def est_return_on_move(self, move: float) -> float:
        """Estimated return on premium for a favorable underlying ``move`` (in
        price units), from the 2nd-order Taylor expansion of option value:
        ΔP ≈ |Δ|·move + ½·Γ·move². Divided by the ask (per-share cost). This is
        higher for cheap, high-gamma (convex) contracts on a large expected move
        — the "best delta/gamma combo for profitability" score. Returns 0 when
        cost or gamma data is missing, so callers fall back to delta selection."""
        if self.ask <= 0:
            return 0.0
        est_pnl = abs(self.delta) * move + 0.5 * self.gamma * move * move
        return est_pnl / self.ask


@dataclass
class ChainSnapshot:
    """0DTE contracts available for an underlying at scan time."""

    symbol: str
    session_date: date
    contracts: list[OptionContract] = field(default_factory=list)

    def zero_dte(self) -> list[OptionContract]:
        return [c for c in self.contracts if c.expiration == self.session_date]


@dataclass
class ContractChoice:
    """The contract the selector picked, or a reason it declined."""

    contract: Optional[OptionContract]
    rejected_reason: str = ""

    @property
    def ok(self) -> bool:
        return self.contract is not None


@dataclass
class AccountState:
    """Snapshot of the Agentic cash account."""

    account_number: str
    agentic_allowed: bool
    option_level: str            # '', 'option_level_0', 'option_level_2', ...
    balance: float               # total account value
    settled_cash: float          # options proceeds settle T+1 — only settled is buyable
    unsettled_cash: float = 0.0
    open_premium: float = 0.0    # cost basis of currently-open premium

    @property
    def options_approved(self) -> bool:
        return self.option_level in ("option_level_2", "option_level_3")


@dataclass
class DayState:
    """Running per-session risk state (drives daily rules)."""

    day_r: float = 0.0                 # realized R so far today
    booked_profit_r: float = 0.0       # >0 R banked today (funds the press rule)
    yesterday_red: bool = False        # half-size the day after a red day
    consecutive_losses: int = 0        # feeds the kill switch
    entries_today: int = 0
    halted: bool = False               # set once daily halt/kill fires
    # --- continuation re-entry bookkeeping (engine._book_close writes these) ---
    profit_exit_at: dict = field(default_factory=dict)   # symbol -> ISO ts of last profitable FULL close
    loss_exit_syms: set = field(default_factory=set)     # names stopped out today -> closed for the session
    reentries: dict = field(default_factory=dict)        # symbol -> re-entries taken today


@dataclass
class Position:
    """An open 0DTE option position."""

    symbol: str
    option_id: str
    option_type: OptionType
    strike: float
    expiration: date
    quantity: int
    entry_premium: float               # per-contract premium paid
    current_premium: float             # per-contract mark
    underlying_stop: float
    underlying_target: float
    thesis_intact: bool = True
    scaled: bool = False               # half already taken off at +1R (legacy scale_trail)
    peak_premium: float = 0.0          # high-water mark of the mark; the position
                                       # tracker ratchets it up each cycle. Drives the
                                       # trailing stop. 0.0 => not yet tracked.
    # --- single-owner rule (operator-approved 2026-08-04) ---
    # Who manages this position's exit ladder: "engine" (opened by this agent),
    # "watcher" (session watcher owns it), or "external" (another session /
    # manual). Non-owners apply BACKSTOPS ONLY (15:45 flatten, -50% stop,
    # thesis break) and never run the ladder/tranches — two managers walking
    # orders on one position is how exits collide (2026-08-04 lesson).
    owner: str = "engine"
    # --- lot-aware tranche bookkeeping (5-stage ladder mode) ---
    tranche_s1_done: bool = False      # 3+ lots: one sold at the +45% arm touch
    tranche_target_done: bool = False  # 2+ lots: one sold at the +90% target touch

    @property
    def premium_change_pct(self) -> float:
        if self.entry_premium <= 0:
            return 0.0
        return (self.current_premium - self.entry_premium) / self.entry_premium

    @property
    def effective_peak(self) -> float:
        """Highest mark seen, floored at the current mark so a not-yet-tracked
        position (peak_premium == 0.0) never reports a peak below where it is —
        which keeps the trailing stop from firing spuriously."""
        return max(self.peak_premium, self.current_premium)


@dataclass
class OrderIntent:
    """A concrete order the agent wants to place — the exact MCP payload.

    ``mcp_tool`` + ``mcp_params`` are the literal call the broker adapter would
    dispatch, so a preview shows precisely what would hit the wire.
    """

    symbol: str
    option_id: str
    side: Literal["buy", "sell"]
    position_effect: Literal["open", "close"]
    quantity: int
    limit_price: float
    kind: Literal["entry", "exit"]
    reason: str = ""
    ref_id: str = ""                   # UUID idempotency key
    mcp_tool: str = ""
    mcp_params: dict = field(default_factory=dict)


@dataclass
class ExitIntent:
    """A protective exit for an open position."""

    position: Position
    kind: Literal["target", "stop", "flatten", "scale", "trail", "thesis_break",
                  "guard", "tranche"]
    quantity: int
    reason: str
    marketable: bool = False           # True => cross the spread (stop/flatten)


@dataclass
class RiskVerdict:
    """The single guardrail gate's decision for one candidate entry."""

    allow: bool
    premium_budget: float = 0.0        # $ premium allotted this trade
    max_contracts: int = 0
    reasons: list[str] = field(default_factory=list)   # why denied / notes

    @classmethod
    def deny(cls, *reasons: str) -> "RiskVerdict":
        return cls(allow=False, reasons=list(reasons))


@dataclass
class Decision:
    """One line in the append-only decision log."""

    ts: str
    kind: str                          # 'entry', 'exit', 'reject', 'kill', 'preview', ...
    symbol: str
    detail: dict = field(default_factory=dict)
