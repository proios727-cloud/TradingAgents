"""Orchestration: one scan cycle, guardrails applied once, exits always live.

Flow per cycle (09:30–16:00 ET, every 5 min):
  0. Kill-switch check first — if tripped: cancel all, flatten, halt.
  1. Manage exits for every open position (exits stay live even when halted).
  2. If not halted: discover held/earnings sets once, then for each fired
     signal run the SINGLE risk gate -> select contract -> preview -> approval
     -> place (all placement gated by dry-run/arm in the broker).

Approval is asymmetric: ENTRY approval is a hard veto (a declined entry is
never placed), while EXIT approval — when require_exit_approval is on — is
advisory only: the ticket is previewed and the operator's answer journaled,
but protective exits (stop, thesis break, 15:45 force-flatten, ...) always
place regardless of the answer.

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
from .config import MARKET_TZ, WATCHLIST, RuntimeConfig
from .decision_log import DecisionLog
from .earnings import EarningsCalendar
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
    failed_exits: list[tuple[str, str, str]] = field(default_factory=list)  # (symbol, exit_kind, error)


class SuperTradesAgent:
    def __init__(
        self,
        cfg: RuntimeConfig,
        broker: BrokerAdapter,
        signals: SignalSource,
        *,
        approval: ApprovalGate | None = None,
        log: DecisionLog | None = None,
        earnings: EarningsCalendar | None = None,
        kill: KillState | None = None,
    ):
        self.cfg = cfg
        self.broker = broker
        self.signals = signals
        # When wired, the calendar OVERRIDES the signal source's own blackout.
        # The signal source's version is a fixture; this one is the live feed
        # and fails closed, so it must win wherever both exist.
        self.earnings = earnings
        self.approval = approval or ApprovalGate(required=cfg.require_entry_approval)
        self.log = log or DecisionLog()
        self.day = DayState()
        # Share ONE KillState with the broker/dispatcher (pass the same object
        # here) so an MCP dispatch failure halts the very next cycle.
        self.kill = kill or KillState()
        # High-water mark of each open position's mark, keyed by option_id.
        # Positions are rebuilt from broker state each cycle, so the peak that
        # drives the trailing stop must persist here, across cycles.
        self._peaks: dict[str, float] = {}
        # Ladder-tranche bookkeeping and ownership, also keyed by option_id and
        # persisted across cycles for the same reason. _owners confirms the
        # positions THIS engine opened ("engine"); ids it never placed keep the
        # owner the broker adapter stamped (single-owner rule: the engine only
        # ever confirms its own, never claims someone else's).
        self._tranche_s1: set[str] = set()
        self._tranche_target: set[str] = set()
        self._owners: dict[str, str] = {}
        # Original lot count per option_id — the denominator R is booked
        # against (a tranche shrinks quantity, not the R scale). Guardian
        # finding 2026-08-04.
        self._orig_qty: dict[str, int] = {}
        # Lots already committed to dispatched sell orders that have not yet
        # shown up as a reduced position, and the last quantity observed (to
        # detect fills). Prevents overselling when a banking tranche rests.
        self._pending_sells: dict[str, int] = {}
        self._last_qty: dict[str, int] = {}

    # -- one cycle --------------------------------------------------------
    def run_cycle(self, now: datetime) -> CycleResult:
        res = CycleResult(ts=now.astimezone(MARKET_TZ).isoformat())

        # 0. Kill switch first.
        kd = kill_check(self.kill, now)
        if kd:
            self.day.halted = True
            # Cancelling working orders is best-effort — closing positions is
            # not. A raise here must never block the flatten below.
            try:
                self.broker.cancel_all()
            except Exception as e:  # noqa: BLE001 — flatten must still run
                self.log.record("cancel_all_failed", "*", now, error=repr(e))
            res.killed = kd.reason
            res.exits, res.failed_exits = self._flatten_all(now, reason=f"kill: {kd.reason}")
            self.log.record("kill", "*", now, reason=kd.reason)
            return res

        # 1. Exits always run (even if halted for entries).
        res.exits, res.failed_exits = self._manage_exits(now)

        # 2. Entries — only if not halted.
        if self.day.halted or self.day.day_r <= G.daily_halt_r:
            self.day.halted = True
            return res

        held = frozenset(p.symbol for p in self.broker.get_positions())
        earnings = (
            self.earnings.blackout(now, WATCHLIST)
            if self.earnings is not None
            else self.signals.earnings_symbols(now)
        )
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
            if not review.ok:
                # Fail CLOSED on entries: a failed broker preview must never
                # reach the human approval prompt dressed as a reviewable
                # order. Block the entry, log it, surface it as a rejection.
                reason = f"broker review failed: {review.error or 'unknown error'}"
                res.rejected.append((sig.symbol, reason))
                self.log.record("reject", sig.symbol, now, stage="review",
                                reason=reason, intent=intent.mcp_params)
                continue
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
                self._owners[choice.contract.option_id] = "engine"
                if sig.is_reentry:
                    self.day.reentries[sig.symbol] = self.day.reentries.get(sig.symbol, 0) + 1
                held = held | {sig.symbol}

        return res

    # -- helpers ----------------------------------------------------------
    def _manage_exits(self, now: datetime) -> tuple[list[ExitIntent], list[tuple[str, str, str]]]:
        out: list[ExitIntent] = []
        failed: list[tuple[str, str, str]] = []
        live_ids: set[str] = set()
        for pos in self.broker.get_positions():
            # Ratchet the per-position high-water mark before evaluating exits so
            # the trailing stop measures give-back from the true peak, not just
            # this cycle's mark. Only ever rises; never lowers an existing peak.
            live_ids.add(pos.option_id)
            self._orig_qty.setdefault(pos.option_id, pos.quantity)
            # Fills show up as a shrunk position: retire that much pending-sell.
            prev_qty = self._last_qty.get(pos.option_id, pos.quantity)
            if pos.quantity < prev_qty:
                filled = prev_qty - pos.quantity
                self._pending_sells[pos.option_id] = max(
                    0, self._pending_sells.get(pos.option_id, 0) - filled)
            self._last_qty[pos.option_id] = pos.quantity
            peak = max(self._peaks.get(pos.option_id, pos.current_premium),
                       pos.current_premium)
            self._peaks[pos.option_id] = peak
            pos.peak_premium = peak
            pos.owner = self._owners.get(pos.option_id, pos.owner)
            pos.tranche_s1_done = pos.option_id in self._tranche_s1
            pos.tranche_target_done = pos.option_id in self._tranche_target
            try:
                exits = exit_manager.evaluate(pos, now, self.cfg)
            except Exception as e:  # one position's failure never starves the rest
                self.log.record("error", pos.symbol, now, stage="exit_eval",
                                error=repr(e))
                continue
            for ex in exits:
                pending = self._pending_sells.get(pos.option_id, 0)
                if ex.kind in ("stop", "flatten", "thesis_break", "trail", "guard"):
                    # Protective exit: nothing may block or shrink it. If lots
                    # are committed to working orders, clear the book first,
                    # then send the full remainder marketable.
                    if pending:
                        self.broker.cancel_all()
                        self._pending_sells.clear()
                else:
                    # Banking exit (tranche/scale/target): never oversell —
                    # net out lots already committed to working sells.
                    ex.quantity = min(ex.quantity, max(0, pos.quantity - pending))
                    if ex.quantity <= 0:
                        continue
                out.append(ex)
                intent = self._exit_intent(ex)
                # APPROVAL IS ASYMMETRIC BY DESIGN:
                #   * ENTRIES are vetoable — the operator's decline blocks them.
                #   * EXITS are NOT — they are protective. With
                #     require_exit_approval=True the ticket is still previewed
                #     to the approver and their answer journaled, but the
                #     answer is ADVISORY ONLY: the exit places regardless of a
                #     decline, an approver exception, or no approver being
                #     wired at all (the default approver denies everything —
                #     it must never be able to veto a stop or the 15:45
                #     force-flatten and hold 0DTE into the bell).
                if self.cfg.require_exit_approval:
                    review = self.broker.review_order(intent)
                    # Fail OPEN on exits: a broker preview failure must never
                    # trap the agent in a position. The exit still goes to the
                    # approver, and the Preview renders the failed review
                    # unmistakably.
                    if not review.ok:
                        self.log.record("exit_review_failed", ex.position.symbol,
                                        now, exit_kind=ex.kind, error=review.error)
                    try:
                        approved = bool(self.approval.request(Preview(intent, review)))
                    except Exception as e:  # noqa: BLE001 — advisory; never blocks
                        approved = False
                        self.log.record("exit_approver_error", ex.position.symbol,
                                        now, exit_kind=ex.kind, error=repr(e))
                    self.log.record("exit_approval_advisory", ex.position.symbol,
                                    now, exit_kind=ex.kind, approved=approved,
                                    note="advisory only — protective exit placed "
                                         "regardless of operator response")
                # Snapshot the lot count at decision time: an instant-fill
                # broker (paper) mutates pos.quantity inside place_order, and
                # the flag/booking logic below must see the pre-fill count.
                qty_at_decision = pos.quantity
                # ISOLATION: one position's broker failure must never abort
                # the loop and leave every later position with no exit this
                # cycle. Catch here, journal loudly, and keep going — the
                # kill switch (tripped by the broker itself on a real error)
                # still halts entries next cycle; this just finishes the pass.
                try:
                    result = self.broker.place_order(intent)
                except Exception as e:  # noqa: BLE001 — isolate per-position
                    failed.append((ex.position.symbol, ex.kind, repr(e)))
                    self.log.record("exit_failed", ex.position.symbol, now,
                                    exit_kind=ex.kind, qty=ex.quantity,
                                    reason=ex.reason, error=repr(e))
                    continue
                # NB: detail key must not be "kind" — that's record()'s first
                # positional arg (was a latent TypeError on every real exit).
                self.log.record("exit", ex.position.symbol, now, exit_kind=ex.kind,
                                qty=ex.quantity, reason=ex.reason,
                                placed=result.placed, dry_run=result.dry_run)
                if result.placed or result.dry_run:
                    self._pending_sells[pos.option_id] = (
                        self._pending_sells.get(pos.option_id, 0) + ex.quantity)
                    if ex.kind == "tranche":
                        # Which tranche this was: the S1 tranche fires first
                        # and only once, so an un-flagged position taking a
                        # tranche at 3+ lots is S1; otherwise it's the target
                        # tranche. Flags persist engine-side across cycles.
                        if pos.option_id not in self._tranche_s1 and qty_at_decision >= 3:
                            self._tranche_s1.add(pos.option_id)
                        else:
                            self._tranche_target.add(pos.option_id)
                    self._book_close(ex, now)
        # Drop peaks/flags for positions no longer open so the maps can't leak
        # or resurrect stale state on a re-entered symbol.
        self._peaks = {oid: pk for oid, pk in self._peaks.items() if oid in live_ids}
        self._tranche_s1 &= live_ids
        self._tranche_target &= live_ids
        self._owners = {oid: ow for oid, ow in self._owners.items() if oid in live_ids}
        self._orig_qty = {oid: q for oid, q in self._orig_qty.items() if oid in live_ids}
        self._pending_sells = {oid: q for oid, q in self._pending_sells.items()
                               if oid in live_ids}
        self._last_qty = {oid: q for oid, q in self._last_qty.items() if oid in live_ids}
        return out, failed

    def _book_close(self, ex: ExitIntent, now: datetime) -> None:
        """Wire the loss limiters (guardian finding, 2026-08-04): realized R
        and the loss streak update the moment a protective exit is
        dispatched, so the -2R daily halt and the 3-loss kill fire
        in-session rather than depending on the retrospective scorer. R is
        computed from the mark at exit evaluation; fills may differ by
        slippage, which the scorer trues up after the fact. Scale-outs book
        their closed fraction of R but only FULL closes drive the streak."""
        p = ex.position
        if p.entry_premium <= 0:
            return
        # R is measured against the ORIGINAL lot count, not what remains after
        # tranches — else a post-tranche close over-books R (guardian finding).
        # p.quantity may already be 0 here (instant-fill brokers reduce it in
        # place_order), which is exactly why the denominator is _orig_qty.
        orig = self._orig_qty.get(p.option_id, p.quantity)
        if orig <= 0:
            return
        frac = min(ex.quantity / orig, 1.0)
        r = (p.current_premium - p.entry_premium) / (G.stop_premium_loss * p.entry_premium)
        r_booked = r * frac
        self.day.day_r += r_booked
        if r_booked > 0:
            self.day.booked_profit_r += r_booked
        if ex.kind not in ("scale", "tranche"):
            # Full closes drive the loss streak AND the continuation re-entry
            # bookkeeping: a profitable close opens the (gated) re-entry window
            # for the name; a loss closes the name for the session. A dead
            # scratch (r == 0) is neither: streak unchanged, no window opened.
            if r < 0:
                self.kill.consecutive_losses += 1
                self.day.loss_exit_syms.add(p.symbol)
            elif r > 0:
                self.kill.consecutive_losses = 0
                self.day.profit_exit_at[p.symbol] = now.isoformat()
        if self.day.day_r <= G.daily_halt_r and not self.day.halted:
            self.day.halted = True
            self.log.record("halt", p.symbol, now, day_r=round(self.day.day_r, 2))

    def _flatten_all(self, now: datetime, reason: str) -> tuple[list[ExitIntent], list[tuple[str, str, str]]]:
        out: list[ExitIntent] = []
        failed: list[tuple[str, str, str]] = []
        for pos in self.broker.get_positions():
            ex = ExitIntent(pos, "flatten", pos.quantity, reason, marketable=True)
            out.append(ex)
            # Emergency flatten: ISOLATE each position's attempt so a
            # persistently-failing one can never block flattening the rest —
            # including the 15:45 ET force-flatten on the kill path.
            try:
                self.broker.place_order(self._exit_intent(ex))
            except Exception as e:  # noqa: BLE001 — isolate per-position
                failed.append((ex.position.symbol, ex.kind, repr(e)))
                self.log.record("flatten_failed", ex.position.symbol, now,
                                exit_kind=ex.kind, qty=ex.quantity,
                                reason=ex.reason, error=repr(e))
        return out, failed

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
