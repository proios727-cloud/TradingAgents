"""Orchestration: one scan cycle, guardrails applied once, exits always live.

Flow per cycle (09:30–16:00 ET, every 5 min):
  0. Kill-switch check first — if tripped: cancel all, flatten, halt.
  1. Manage exits for every open position (exits stay live even when halted).
  2. If not halted: discover held/earnings sets once, then for each fired
     signal run the SINGLE risk gate -> select contract -> preview -> approval
     -> place (all placement gated by dry-run/arm in the broker).

The engine never re-checks guardrails itself; risk_governor is the one gate.
Signals come from an injected SignalSource so the same engine runs on the
paper/simulated source (dry run) or a live signal engine.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from . import contract_selector, exit_manager, risk_governor
from .approval import ApprovalGate, Preview
from .broker.base import BrokerAdapter
from .config import GUARDRAILS as G
from .config import MARKET_TZ, RuntimeConfig
from .decision_log import DecisionLog
from .kill_switch import KillState, check as kill_check
from .models import DayState, ExitIntent, OrderIntent, Signal


class SignalSource(Protocol):
    def fired_signals(self, now: datetime) -> list[Signal]: ...
    def earnings_symbols(self, now: datetime) -> frozenset[str]: ...


@dataclass
class CycleResult:
    ts: str
    killed: str = ""                       # kill reason if fired
    exits: list[ExitIntent] = field(default_factory=list)
    placed_entries: list[OrderIntent] = field(default_factory=list)
    rejected: list[tuple[str, str]] = field(default_factory=list)  # (symbol, reason)
    previewed_declined: list[str] = field(default_factory=list)    # symbols the human skipped


class SuperTradesAgent:
    def __init__(
        self,
        cfg: RuntimeConfig,
        broker: BrokerAdapter,
        signals: SignalSource,
        *,
        approval: ApprovalGate | None = None,
        log: DecisionLog | None = None,
    ):
        self.cfg = cfg
        self.broker = broker
        self.signals = signals
        self.approval = approval or ApprovalGate(required=cfg.require_entry_approval)
        self.log = log or DecisionLog()
        self.day = DayState()
        self.kill = KillState()
        # High-water mark of each open position's mark, keyed by option_id.
        # Positions are rebuilt from broker state each cycle, so the peak that
        # drives the trailing stop must persist here, across cycles.
        self._peaks: dict[str, float] = {}

    # -- one cycle --------------------------------------------------------
    def run_cycle(self, now: datetime) -> CycleResult:
        res = CycleResult(ts=now.astimezone(MARKET_TZ).isoformat())

        # 0. Kill switch first.
        kd = kill_check(self.kill, now)
        if kd:
            self.day.halted = True
            self.broker.cancel_all()
            res.killed = kd.reason
            res.exits = self._flatten_all(now, reason=f"kill: {kd.reason}")
            self.log.record("kill", "*", now, reason=kd.reason)
            return res

        # 1. Exits always run (even if halted for entries).
        res.exits = self._manage_exits(now)

        # 2. Entries — only if not halted.
        if self.day.halted or self.day.day_r <= G.daily_halt_r:
            self.day.halted = True
            return res

        held = frozenset(p.symbol for p in self.broker.get_positions())
        earnings = self.signals.earnings_symbols(now)
        account = self.broker.get_account()

        for sig in self.signals.fired_signals(now):
            choice = contract_selector.select(sig, self.broker.get_chain(sig.symbol), self.cfg)
            if not choice.ok:
                res.rejected.append((sig.symbol, choice.rejected_reason))
                self.log.record("reject", sig.symbol, now, stage="contract",
                                reason=choice.rejected_reason)
                continue

            verdict = risk_governor.evaluate(
                sig, account, self.day, now, choice.contract.ask, self.cfg,
                held_symbols=held, earnings_symbols=earnings,
            )
            if not verdict.allow:
                res.rejected.append((sig.symbol, "; ".join(verdict.reasons)))
                self.log.record("reject", sig.symbol, now, stage="risk",
                                reason="; ".join(verdict.reasons))
                continue

            intent = self._entry_intent(sig, choice.contract, verdict.max_contracts)
            review = self.broker.review_order(intent)
            preview = Preview(intent, review)
            self.log.record("preview", sig.symbol, now, intent=intent.mcp_params,
                            alerts=review.alerts)

            if not self.approval.request(preview):
                res.previewed_declined.append(sig.symbol)
                self.log.record("declined", sig.symbol, now)
                continue

            result = self.broker.place_order(intent)
            self.log.record("entry", sig.symbol, now, placed=result.placed,
                            dry_run=result.dry_run, order_id=result.order_id,
                            detail=result.detail, error=result.error)
            if result.placed or result.dry_run:
                res.placed_entries.append(intent)
                self.day.entries_today += 1
                held = held | {sig.symbol}

        return res

    # -- helpers ----------------------------------------------------------
    def _manage_exits(self, now: datetime) -> list[ExitIntent]:
        out: list[ExitIntent] = []
        live_ids: set[str] = set()
        for pos in self.broker.get_positions():
            # Ratchet the per-position high-water mark before evaluating exits so
            # the trailing stop measures give-back from the true peak, not just
            # this cycle's mark. Only ever rises; never lowers an existing peak.
            live_ids.add(pos.option_id)
            peak = max(self._peaks.get(pos.option_id, pos.current_premium),
                       pos.current_premium)
            self._peaks[pos.option_id] = peak
            pos.peak_premium = peak
            for ex in exit_manager.evaluate(pos, now, self.cfg):
                out.append(ex)
                intent = self._exit_intent(ex)
                # Protective exits submit automatically when armed (config);
                # entries are the ones that require per-order approval.
                if self.cfg.require_exit_approval:
                    review = self.broker.review_order(intent)
                    if not self.approval.request(Preview(intent, review)):
                        continue
                result = self.broker.place_order(intent)
                self.log.record("exit", ex.position.symbol, now, kind=ex.kind,
                                qty=ex.quantity, reason=ex.reason,
                                placed=result.placed, dry_run=result.dry_run)
                if result.placed or result.dry_run:
                    self._book_close(ex, now)
        # Drop peaks for positions no longer open so the map can't leak or
        # resurrect a stale high-water mark on a re-entered symbol.
        self._peaks = {oid: pk for oid, pk in self._peaks.items() if oid in live_ids}
        return out

    def _book_close(self, ex: ExitIntent, now: datetime) -> None:
        """Wire the loss limiters (guardian finding, 2026-08-04): realized R
        and the loss streak update the moment a protective exit is
        dispatched, so the -2R daily halt and the 3-loss kill fire
        in-session rather than depending on the retrospective scorer. R is
        computed from the mark at exit evaluation; fills may differ by
        slippage, which the scorer trues up after the fact. Scale-outs book
        their closed fraction of R but only FULL closes drive the streak."""
        p = ex.position
        if p.entry_premium <= 0 or p.quantity <= 0:
            return
        frac = min(ex.quantity / p.quantity, 1.0)
        r = (p.current_premium - p.entry_premium) / (G.stop_premium_loss * p.entry_premium)
        r_booked = r * frac
        self.day.day_r += r_booked
        if r_booked > 0:
            self.day.booked_profit_r += r_booked
        if ex.kind != "scale":
            if r < 0:
                self.kill.consecutive_losses += 1
            else:
                self.kill.consecutive_losses = 0
        if self.day.day_r <= G.daily_halt_r and not self.day.halted:
            self.day.halted = True
            self.log.record("halt", p.symbol, now, day_r=round(self.day.day_r, 2))

    def _flatten_all(self, now: datetime, reason: str) -> list[ExitIntent]:
        out = []
        for pos in self.broker.get_positions():
            ex = ExitIntent(pos, "flatten", pos.quantity, reason, marketable=True)
            out.append(ex)
            self.broker.place_order(self._exit_intent(ex))
        return out

    def _entry_intent(self, sig: Signal, contract, qty: int) -> OrderIntent:
        return OrderIntent(
            symbol=sig.symbol, option_id=contract.option_id, side="buy",
            position_effect="open", quantity=qty, limit_price=contract.mid,
            kind="entry", ref_id=str(uuid.uuid4()),
            reason=f"{sig.strategy} | {sig.direction} | Δ{contract.delta:.2f}",
        )

    def _exit_intent(self, ex: ExitIntent) -> OrderIntent:
        p = ex.position
        price = p.current_premium * (0.98 if ex.marketable else 1.0)
        return OrderIntent(
            symbol=p.symbol, option_id=p.option_id, side="sell",
            position_effect="close", quantity=ex.quantity,
            limit_price=round(price, 2), kind="exit",
            ref_id=str(uuid.uuid4()), reason=f"{ex.kind}: {ex.reason}",
        )
