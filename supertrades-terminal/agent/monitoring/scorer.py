"""Reconstruct and grade a live session from raw Robinhood MCP snapshots.

Input is a snapshot JSON file written by the monitoring loop:

    {
      "captured_at": "2026-07-28T16:22:00Z",
      "account_masked": "••••1866",
      "portfolio": { ...raw get_portfolio data... },
      "option_orders": [ ...raw get_option_orders orders[]... ],
      "equity_orders": [ ...raw get_equity_orders orders[]... ],
      "marks": { "<option_id>": 1.28 }        # optional per-contract mark
    }

Only fields this module reads need to be present. Timestamps are UTC ISO-8601
(trailing ``Z`` accepted); all session logic is evaluated in ET (MARKET_TZ).

Grading is retrospective and uses the *snapshot* balance as the sizing base —
the balance at entry time is not in the order record, so sizing findings on a
day with large P&L swings are approximate and labeled as such.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Optional

from ..config import GUARDRAILS as G
from ..config import MARKET_TZ

CONTRACT_MULT = 100.0


def _parse_ts(raw: str) -> datetime:
    """UTC ISO timestamp -> aware datetime in ET."""
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(MARKET_TZ)


@dataclass
class Fill:
    """One executed single-leg option fill (an execution row, flattened)."""

    order_id: str
    option_id: str
    symbol: str
    option_type: str                   # 'call' | 'put'
    strike: float
    expiration: date
    side: str                          # 'buy' | 'sell'
    position_effect: str               # 'open' | 'close'
    quantity: float
    price: float                       # per-share premium actually executed
    ts: datetime                       # ET
    placed_agent: str = "user"

    @property
    def premium(self) -> float:
        """Total dollars of premium for this fill."""
        return self.price * self.quantity * CONTRACT_MULT


@dataclass
class RoundTrip:
    """An opened lot, matched FIFO to its close (or still open)."""

    option_id: str
    symbol: str
    option_type: str
    strike: float
    expiration: date
    quantity: float
    entry_ts: datetime
    entry_premium: float               # $ paid
    placed_agent: str = "user"
    exit_ts: Optional[datetime] = None
    exit_premium: Optional[float] = None  # $ received
    mark: Optional[float] = None       # per-share mark for open lots, if known

    @property
    def closed(self) -> bool:
        return self.exit_premium is not None

    @property
    def pnl(self) -> Optional[float]:
        if self.exit_premium is None:
            return None
        return self.exit_premium - self.entry_premium

    @property
    def pct(self) -> Optional[float]:
        """Premium return; for open lots, unrealized from ``mark`` when known."""
        if self.entry_premium <= 0:
            return None
        if self.closed:
            return (self.exit_premium - self.entry_premium) / self.entry_premium
        if self.mark is not None:
            return (self.mark * self.quantity * CONTRACT_MULT - self.entry_premium) / self.entry_premium
        return None

    @property
    def r_multiple(self) -> Optional[float]:
        """P&L in units of planned risk (stop = -50% of premium, per Guardrails)."""
        if self.pnl is None or self.entry_premium <= 0:
            return None
        return self.pnl / (G.stop_premium_loss * self.entry_premium)

    @property
    def hold_minutes(self) -> Optional[float]:
        if self.exit_ts is None:
            return None
        return (self.exit_ts - self.entry_ts).total_seconds() / 60.0

    @property
    def dte_at_entry(self) -> int:
        return (self.expiration - self.entry_ts.date()).days

    def label(self) -> str:
        exp = self.expiration.strftime("%-m/%-d")
        return f"{self.symbol} {self.strike:g}{self.option_type[0].upper()} {exp}"


@dataclass
class Violation:
    rule: str
    severity: str                      # 'high' | 'medium' | 'info'
    trade: str                         # trade label or '' for session-level
    detail: str
    points: float                      # adherence deduction


@dataclass
class Snapshot:
    captured_at: datetime              # ET
    account_masked: str
    total_value: float
    cash: float
    buying_power: float
    options_value: float
    option_orders: list[dict]
    equity_orders: list[dict] = field(default_factory=list)
    marks: dict[str, float] = field(default_factory=dict)

    @property
    def session_date(self) -> date:
        return self.captured_at.date()


@dataclass
class SessionScore:
    snapshot: Snapshot
    closed: list[RoundTrip]
    open_lots: list[RoundTrip]
    violations: list[Violation]
    metrics: dict
    adherence: float                   # 0-100
    recommendations: list[str]


def load_snapshot(path: str | Path) -> Snapshot:
    raw = json.loads(Path(path).read_text())
    pf = raw.get("portfolio", {})
    bp = pf.get("buying_power", {})
    return Snapshot(
        captured_at=_parse_ts(raw["captured_at"]),
        account_masked=raw.get("account_masked", ""),
        total_value=float(pf.get("total_value", 0) or 0),
        cash=float(pf.get("cash", 0) or 0),
        buying_power=float(bp.get("buying_power", 0) or 0),
        options_value=float(pf.get("options_value", 0) or 0),
        option_orders=raw.get("option_orders", []),
        equity_orders=raw.get("equity_orders", []),
        marks={k: float(v) for k, v in raw.get("marks", {}).items()},
    )


def extract_fills(option_orders: list[dict]) -> list[Fill]:
    """Flatten filled single-leg orders into Fill rows, oldest first."""
    fills: list[Fill] = []
    for order in option_orders:
        if order.get("state") != "filled":
            continue
        for leg in order.get("legs", []):
            for ex in leg.get("executions", []):
                fills.append(Fill(
                    order_id=order.get("id", ""),
                    option_id=leg.get("option_id", ""),
                    symbol=order.get("chain_symbol", ""),
                    option_type=leg.get("option_type", ""),
                    strike=float(leg.get("strike_price", 0) or 0),
                    expiration=date.fromisoformat(leg["expiration_date"]),
                    side=leg.get("side", ""),
                    position_effect=leg.get("position_effect", ""),
                    quantity=float(ex.get("quantity", 0) or 0),
                    price=float(ex.get("price", 0) or 0),
                    ts=_parse_ts(ex["timestamp"]),
                    placed_agent=order.get("placed_agent", "user"),
                ))
    fills.sort(key=lambda f: f.ts)
    return fills


def match_round_trips(fills: list[Fill], marks: dict[str, float]) -> tuple[list[RoundTrip], list[RoundTrip]]:
    """FIFO-match closes to opens per option_id. Returns (closed, open_lots).

    The agent trades 1-lot long options, so partial-fill lot splitting is not
    modeled: a close is matched whole against the oldest open lot of the same
    contract. Closes with no visible open (position opened before the snapshot
    window) are dropped rather than guessed at.
    """
    open_lots: dict[str, list[RoundTrip]] = {}
    closed: list[RoundTrip] = []
    for f in fills:
        if f.side == "buy" and f.position_effect == "open":
            open_lots.setdefault(f.option_id, []).append(RoundTrip(
                option_id=f.option_id, symbol=f.symbol, option_type=f.option_type,
                strike=f.strike, expiration=f.expiration, quantity=f.quantity,
                entry_ts=f.ts, entry_premium=f.premium, placed_agent=f.placed_agent,
            ))
        elif f.side == "sell" and f.position_effect == "close":
            lots = open_lots.get(f.option_id, [])
            if lots:
                lot = lots.pop(0)
                lot.exit_ts = f.ts
                lot.exit_premium = f.premium
                closed.append(lot)
    still_open = [lot for lots in open_lots.values() for lot in lots]
    for lot in still_open:
        if lot.option_id in marks:
            lot.mark = marks[lot.option_id]
    still_open.sort(key=lambda t: t.entry_ts)
    closed.sort(key=lambda t: t.exit_ts)
    return closed, still_open


def _entry_window_ok(ts: datetime) -> bool:
    t = ts.time()
    start = (datetime.combine(ts.date(), G.session_open_et)
             + timedelta(minutes=G.no_entry_open_minutes)).time()
    end = (datetime.combine(ts.date(), G.session_close_et)
           - timedelta(minutes=G.no_entry_close_minutes)).time()
    return start <= t < end


def grade(snap: Snapshot, closed: list[RoundTrip], open_lots: list[RoundTrip]) -> list[Violation]:
    v: list[Violation] = []
    allowed = G.premium_budget(snap.total_value)
    trades = closed + open_lots

    for t in trades:
        if t.dte_at_entry != 0:
            v.append(Violation(
                "0dte_only", "high", t.label(),
                f"entered {t.dte_at_entry} DTE — Guardrails.only_0dte_long requires same-day expiry",
                15.0))
        aplus_allowed = allowed * G.conviction_aplus_mult
        if t.entry_premium > aplus_allowed * 1.05:
            v.append(Violation(
                "sizing", "medium", t.label(),
                f"${t.entry_premium:.0f} premium vs ~${allowed:.0f} allowed "
                f"(${aplus_allowed:.0f} at A+ conviction; phase ladder at "
                f"${snap.total_value:.0f} balance, snapshot-approximate)",
                8.0))
        elif t.entry_premium > allowed * 1.05:
            v.append(Violation(
                "sizing_conviction", "info", t.label(),
                f"${t.entry_premium:.0f} premium is inside the A+ budget "
                f"(~${aplus_allowed:.0f}) but above base ~${allowed:.0f} — "
                f"conviction is unverifiable from fills; check the signal ledger",
                0.0))
        if not _entry_window_ok(t.entry_ts):
            v.append(Violation(
                "entry_window", "medium", t.label(),
                f"entry at {t.entry_ts.strftime('%H:%M')} ET is inside a no-entry window",
                5.0))

    for t in closed:
        if t.pct is not None and t.pct < -(G.stop_premium_loss + 0.10):
            v.append(Violation(
                "stop_discipline", "high", t.label(),
                f"closed at {t.pct:+.0%} — beyond the -{G.stop_premium_loss:.0%} stop plus slippage allowance",
                15.0))

    flatten_dt = datetime.combine(snap.session_date, G.force_flatten_et, tzinfo=MARKET_TZ)
    if snap.captured_at >= flatten_dt:
        for t in open_lots:
            if t.expiration <= snap.session_date:
                v.append(Violation(
                    "force_flatten", "high", t.label(),
                    f"still open past {G.force_flatten_et.strftime('%H:%M')} ET on expiry day",
                    15.0))

    # Daily halt: walk closed trades in exit order; entries after the day is
    # down daily_halt_r should not exist.
    day_r = 0.0
    halted_at: Optional[datetime] = None
    for t in closed:
        day_r += t.r_multiple or 0.0
        if halted_at is None and day_r <= G.daily_halt_r:
            halted_at = t.exit_ts
    if halted_at is not None:
        late = [t for t in closed + open_lots if t.entry_ts > halted_at]
        for t in late:
            v.append(Violation(
                "daily_halt", "high", t.label(),
                f"entered after the day hit {G.daily_halt_r:g}R (halt fired {halted_at.strftime('%H:%M')} ET)",
                15.0))

    losses = 0
    kill_at: Optional[datetime] = None
    for t in closed:
        losses = losses + 1 if (t.pnl or 0) < 0 else 0
        if kill_at is None and losses >= G.consecutive_loss_kill:
            kill_at = t.exit_ts
    if kill_at is not None:
        late = [t for t in closed + open_lots if t.entry_ts > kill_at]
        for t in late:
            v.append(Violation(
                "loss_kill", "high", t.label(),
                f"entered after {G.consecutive_loss_kill} straight losses (kill due {kill_at.strftime('%H:%M')} ET)",
                15.0))

    equity_fills = [o for o in snap.equity_orders if o.get("state") == "filled"]
    if equity_fills:
        v.append(Violation(
            "options_only", "high", "",
            f"{len(equity_fills)} filled share order(s) — Guardrails permit 0DTE long options only",
            15.0))

    if snap.total_value < G.balance_floor_alert_usd:
        v.append(Violation(
            "balance_floor", "info", "",
            f"balance ${snap.total_value:.0f} is below Guardrails.balance_floor_alert_usd "
            f"(${G.balance_floor_alert_usd:.0f}) — config calls for halt + alert at this level",
            0.0))

    return v


def compute_metrics(closed: list[RoundTrip], open_lots: list[RoundTrip]) -> dict:
    pnls = [t.pnl for t in closed if t.pnl is not None]
    rs = [t.r_multiple for t in closed if t.r_multiple is not None]
    wins = [t for t in closed if (t.pnl or 0) > 0]
    losses = [t for t in closed if (t.pnl or 0) <= 0]
    gross_win = sum(t.pnl for t in wins) if wins else 0.0
    gross_loss = -sum(t.pnl for t in losses) if losses else 0.0
    holds = [t.hold_minutes for t in closed if t.hold_minutes is not None]
    return {
        "n_closed": len(closed),
        "n_open": len(open_lots),
        "realized_pnl": sum(pnls),
        "total_r": sum(rs),
        "avg_r": sum(rs) / len(rs) if rs else 0.0,
        "win_rate": len(wins) / len(closed) if closed else 0.0,
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else float("inf") if gross_win > 0 else 0.0,
        "avg_win_pct": sum(t.pct for t in wins) / len(wins) if wins else 0.0,
        "avg_loss_pct": sum(t.pct for t in losses) / len(losses) if losses else 0.0,
        "median_hold_min": median(holds) if holds else 0.0,
    }


def recommend(snap: Snapshot, closed: list[RoundTrip], open_lots: list[RoundTrip],
              violations: list[Violation], metrics: dict) -> list[str]:
    """Data-driven tuning notes. Advisory only — Guardrails changes need the
    operator; each note carries its sample size so thin evidence reads as thin."""
    recs: list[str] = []
    n = metrics["n_closed"]
    allowed = G.premium_budget(snap.total_value)

    if snap.total_value < G.sizing_phases[-1][0]:
        next_bound = next(b for b, _ in G.sizing_phases if snap.total_value < b)
        recs.append(
            f"Sizing phase: fixed ${allowed:.0f}/trade at ${snap.total_value:.0f} balance "
            f"(next phase at ${next_bound:.0f}; {G.sizing_pct:.1%} takes over at "
            f"${G.sizing_phases[-1][0]:.0f}).")

    dte_break = [t for t in closed + open_lots if t.dte_at_entry != 0]
    if dte_break:
        recs.append(
            f"{len(dte_break)} of {len(closed) + len(open_lots)} entries were 1+ DTE. "
            f"Either hold the 0DTE-only line or amend only_0dte_long deliberately — "
            f"1DTE longs carry overnight theta/gap risk none of the exit rules model.")

    wins = [t for t in closed if (t.pnl or 0) > 0]
    if len(wins) >= 2 and metrics["avg_win_pct"] < 0.5 * G.target_premium_gain:
        recs.append(
            f"Winners are being cut at {metrics['avg_win_pct']:+.0%} on average vs the "
            f"+{G.target_premium_gain:.0%} target (n={len(wins)}). If that's deliberate "
            f"momentum-fade selling it's fine; if it's nerves, RuntimeConfig.scale_and_trail "
            f"(half off at +1R, trail the rest) captures the same early profit without "
            f"capping the runner.")

    if n and metrics["win_rate"] >= 0.5 and metrics["avg_r"] < 0.5:
        recs.append(
            f"Win rate {metrics['win_rate']:.0%} but avg {metrics['avg_r']:+.2f}R (n={n}): "
            f"wins are small relative to the -50% risk budget. Expectancy improves more "
            f"from letting winners reach the target than from more entries.")

    if snap.buying_power < 30 and snap.cash > 100:
        recs.append(
            f"Buying power ${snap.buying_power:.2f} vs cash ${snap.cash:.0f}: T+1 settlement "
            f"has today's proceeds locked. New entries before tomorrow would violate the "
            f"settled-cash rule — expect the agent to sit out rather than churn.")

    if n < 10:
        recs.append(
            f"Only {n} closed round-trip(s) in sample — treat every threshold above as "
            f"provisional until there are 20+ trades of data.")
    return recs


def score_snapshot(snap: Snapshot) -> SessionScore:
    fills = extract_fills(snap.option_orders)
    closed, open_lots = match_round_trips(fills, snap.marks)
    violations = grade(snap, closed, open_lots)
    metrics = compute_metrics(closed, open_lots)
    adherence = max(0.0, 100.0 - sum(v.points for v in violations))
    recs = recommend(snap, closed, open_lots, violations, metrics)
    return SessionScore(snap, closed, open_lots, violations, metrics, adherence, recs)
