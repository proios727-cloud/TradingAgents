"""Broker review-failure handling — asymmetric by design.

ENTRIES fail closed: a failed ``review_order`` blocks the entry before the
human approval prompt (nothing to approve, nothing placed, rejection logged).
EXITS fail open: a failed review must never trap the agent in a position —
the exit still proceeds to the approver, with the failure rendered loudly in
the Preview. PaperBroker/fakes only; nothing here can touch a real broker.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from agent.approval import ApprovalGate, Preview
from agent.broker.base import ReviewResult
from agent.broker.paper import PaperBroker
from agent.config import MARKET_TZ, RuntimeConfig
from agent.decision_log import DecisionLog
from agent.engine import SuperTradesAgent
from agent.models import OrderIntent, Position
from agent.simulated import SimulatedSignalSource, demo_account, demo_chains

SESSION = date(2026, 7, 20)
REVIEW_ERROR = "MCP timeout: review_option_order took >10s"


def et(h, m):
    return datetime(2026, 7, 20, h, m, tzinfo=MARKET_TZ)


class FailingReviewBroker(PaperBroker):
    """Paper broker whose broker-side preview always fails (soft failure,
    exactly like RobinhoodMcpBroker.review_order on an MCP exception)."""

    def review_order(self, intent: OrderIntent) -> ReviewResult:
        return ReviewResult(ok=False, error=REVIEW_ERROR)


class NoSignals:
    def fired_signals(self, now):
        return []

    def earnings_symbols(self, now):
        return frozenset()


class EntryReviewFailureRails(unittest.TestCase):
    def _run(self):
        cfg = RuntimeConfig(account_number="A1", dry_run=True, armed=False)
        broker = FailingReviewBroker(demo_account(), demo_chains(SESSION))
        approvals: list[Preview] = []

        def approver(preview):
            approvals.append(preview)
            return True  # would approve — must never be asked

        log_path = Path(tempfile.mkdtemp()) / "decisions.jsonl"
        agent = SuperTradesAgent(
            cfg, broker, SimulatedSignalSource(SESSION),
            approval=ApprovalGate(approver, required=True),
            log=DecisionLog(log_path),
        )
        return agent.run_cycle(et(14, 32)), broker, approvals, log_path

    def test_entry_blocked_approval_never_requested_nothing_placed(self):
        res, broker, approvals, _ = self._run()
        self.assertEqual(approvals, [])          # human never prompted
        self.assertEqual(broker.placed, [])      # nothing placed, even on paper
        self.assertEqual(res.placed_entries, [])
        self.assertEqual(res.previewed_declined, [])

    def test_entry_surfaced_as_rejection_with_error(self):
        res, _, _, log_path = self._run()
        nvda = [r for (sym, r) in res.rejected if sym == "NVDA"]
        self.assertEqual(len(nvda), 1)
        self.assertIn("broker review failed", nvda[0])
        self.assertIn(REVIEW_ERROR, nvda[0])
        # ...and recorded in the decision log with the error text.
        log = log_path.read_text()
        self.assertIn('"reject"', log)
        self.assertIn('"review"', log)
        self.assertIn(REVIEW_ERROR, log)


class ExitReviewFailureRails(unittest.TestCase):
    def _stopped_position(self):
        # -50% premium stop fires: entry 1.20, mark 0.60.
        return Position("NVDA", "oid-1", "call", 202.5, SESSION, 4, 1.20, 0.60,
                        201.75, 202.90)

    def test_exit_proceeds_and_preview_shows_failure(self):
        cfg = RuntimeConfig(account_number="A1", dry_run=True, armed=False,
                            require_exit_approval=True)
        broker = FailingReviewBroker(demo_account(),
                                     positions=[self._stopped_position()])
        seen: list[Preview] = []

        def approver(preview):
            seen.append(preview)
            return True

        log_path = Path(tempfile.mkdtemp()) / "decisions.jsonl"
        agent = SuperTradesAgent(cfg, broker, NoSignals(),
                                 approval=ApprovalGate(approver, required=True),
                                 log=DecisionLog(log_path))
        res = agent.run_cycle(et(14, 0))

        # The exit was evaluated, previewed to the human, and placed — the
        # review failure did NOT block getting out.
        self.assertEqual(len(res.exits), 1)
        self.assertEqual(res.exits[0].kind, "stop")
        self.assertEqual(len(broker.placed), 1)
        self.assertEqual(broker.placed[0].position_effect, "close")
        # The approver saw the failed review, rendered unmistakably.
        self.assertEqual(len(seen), 1)
        rendered = seen[0].render()
        self.assertIn("BROKER REVIEW FAILED", rendered)
        self.assertIn(REVIEW_ERROR, rendered)
        # And the failure is on the audit trail.
        self.assertIn("exit_review_failed", log_path.read_text())

    def test_exit_without_exit_approval_still_places(self):
        # Default config path (require_exit_approval=False): review is never
        # consulted for exits, so a broken review can't block them either.
        cfg = RuntimeConfig(account_number="A1", dry_run=True, armed=False)
        broker = FailingReviewBroker(demo_account(),
                                     positions=[self._stopped_position()])
        log_path = Path(tempfile.mkdtemp()) / "decisions.jsonl"
        agent = SuperTradesAgent(cfg, broker, NoSignals(),
                                 log=DecisionLog(log_path))
        res = agent.run_cycle(et(14, 0))
        self.assertEqual(len(res.exits), 1)
        self.assertEqual(len(broker.placed), 1)


class PreviewRenderRails(unittest.TestCase):
    def test_failed_review_renders_unmistakably(self):
        intent = OrderIntent("NVDA", "oid-1", "sell", "close", 4, 0.59, "exit",
                             reason="stop: premium -50%")
        rendered = Preview(intent, ReviewResult(ok=False, error="boom")).render()
        self.assertIn("BROKER REVIEW FAILED", rendered)
        self.assertIn("boom", rendered)

    def test_ok_review_renders_no_failure_banner(self):
        intent = OrderIntent("NVDA", "oid-1", "buy", "open", 1, 1.21, "entry")
        rendered = Preview(intent, ReviewResult(ok=True)).render()
        self.assertNotIn("BROKER REVIEW FAILED", rendered)


if __name__ == "__main__":
    unittest.main()
