"""Exit approval is ADVISORY — a decline can never veto a protective exit.

The defect these tests pin down: with ``require_exit_approval=True`` and the
default deny-all approver (or any decliner), every protective exit — including
the 15:45 ET force-flatten, which flows through ``_manage_exits`` and NOT
through the kill-switch ``_flatten_all`` path — used to be skipped, holding
0DTE into the bell.

Required behavior:
  * The operator still sees the ticket (approver is called with the Preview)
    and their answer is journaled (``exit_approval_advisory``).
  * The exit ALWAYS places: on decline, on approver exception, always.
  * ENTRIES are unchanged — a declined entry is still a hard veto.

PaperBroker/fakes only; nothing here can touch a real broker.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from agent.approval import ApprovalGate, Preview
from agent.broker.paper import PaperBroker
from agent.config import MARKET_TZ, RuntimeConfig
from agent.decision_log import DecisionLog
from agent.engine import SuperTradesAgent
from agent.models import Position
from agent.simulated import SimulatedSignalSource, demo_account, demo_chains

SESSION = date(2026, 7, 20)


def et(h, m):
    return datetime(2026, 7, 20, h, m, tzinfo=MARKET_TZ)


class NoSignals:
    def fired_signals(self, now):
        return []

    def earnings_symbols(self, now):
        return frozenset()


def healthy_position():
    # Flat-ish mark: no stop/target/thesis exit fires on its own.
    return Position("NVDA", "oid-1", "call", 202.5, SESSION, 4, 1.20, 1.25,
                    201.75, 202.90)


def stopped_position():
    # -50% premium stop fires: entry 1.20, mark 0.60.
    return Position("NVDA", "oid-1", "call", 202.5, SESSION, 4, 1.20, 0.60,
                    201.75, 202.90)


def build_agent(position, approver, log_path):
    cfg = RuntimeConfig(account_number="A1", dry_run=True, armed=False,
                        require_exit_approval=True)
    broker = PaperBroker(demo_account(), positions=[position])
    agent = SuperTradesAgent(cfg, broker, NoSignals(),
                             approval=ApprovalGate(approver, required=True),
                             log=DecisionLog(log_path))
    return agent, broker


class DeclinedExitStillPlaces(unittest.TestCase):
    def test_declined_1545_flatten_still_places(self):
        seen: list[Preview] = []

        def decline(preview):
            seen.append(preview)
            return False

        log_path = Path(tempfile.mkdtemp()) / "decisions.jsonl"
        agent, broker = build_agent(healthy_position(), decline, log_path)
        res = agent.run_cycle(et(15, 50))  # past the 15:45 ET force-flatten

        self.assertEqual(len(res.exits), 1)
        self.assertEqual(res.exits[0].kind, "flatten")
        # The operator saw the ticket...
        self.assertEqual(len(seen), 1)
        self.assertIn("ORDER PREVIEW", seen[0].render())
        # ...their decline did NOT veto it: the flatten placed anyway.
        self.assertEqual(len(broker.placed), 1)
        self.assertEqual(broker.placed[0].position_effect, "close")
        self.assertEqual(broker.placed[0].quantity, 4)

    def test_declined_stop_loss_still_places(self):
        log_path = Path(tempfile.mkdtemp()) / "decisions.jsonl"
        agent, broker = build_agent(stopped_position(), lambda p: False, log_path)
        res = agent.run_cycle(et(14, 0))

        self.assertEqual(len(res.exits), 1)
        self.assertEqual(res.exits[0].kind, "stop")
        self.assertEqual(len(broker.placed), 1)
        self.assertEqual(broker.placed[0].position_effect, "close")

    def test_default_deny_all_approver_cannot_block_exit(self):
        # No approver wired at all: ApprovalGate() defaults to deny_all.
        log_path = Path(tempfile.mkdtemp()) / "decisions.jsonl"
        cfg = RuntimeConfig(account_number="A1", dry_run=True, armed=False,
                            require_exit_approval=True)
        broker = PaperBroker(demo_account(), positions=[healthy_position()])
        agent = SuperTradesAgent(cfg, broker, NoSignals(),
                                 approval=ApprovalGate(required=True),
                                 log=DecisionLog(log_path))
        res = agent.run_cycle(et(15, 50))
        self.assertEqual(len(res.exits), 1)
        self.assertEqual(len(broker.placed), 1)

    def test_raising_approver_still_places(self):
        def explode(preview):
            raise RuntimeError("operator UI crashed")

        log_path = Path(tempfile.mkdtemp()) / "decisions.jsonl"
        agent, broker = build_agent(stopped_position(), explode, log_path)
        res = agent.run_cycle(et(14, 0))

        self.assertEqual(len(res.exits), 1)
        self.assertEqual(len(broker.placed), 1)
        # Journaled as not-approved; exit proceeded anyway.
        records = [json.loads(line) for line in log_path.read_text().splitlines()]
        advisory = [r for r in records if r["kind"] == "exit_approval_advisory"]
        self.assertEqual(len(advisory), 1)
        self.assertFalse(advisory[0]["approved"])

    def test_decline_is_journaled_and_exit_recorded(self):
        log_path = Path(tempfile.mkdtemp()) / "decisions.jsonl"
        agent, _ = build_agent(stopped_position(), lambda p: False, log_path)
        agent.run_cycle(et(14, 0))

        records = [json.loads(line) for line in log_path.read_text().splitlines()]
        advisory = [r for r in records if r["kind"] == "exit_approval_advisory"]
        self.assertEqual(len(advisory), 1)
        self.assertEqual(advisory[0]["symbol"], "NVDA")
        self.assertFalse(advisory[0]["approved"])
        self.assertIn("advisory only", advisory[0]["note"])
        # The exit itself is on the trail too — decline visibly did not stop it.
        exits = [r for r in records if r["kind"] == "exit"]
        self.assertEqual(len(exits), 1)
        self.assertEqual(exits[0]["exit_kind"], "stop")

    def test_approved_exit_journaled_as_approved(self):
        log_path = Path(tempfile.mkdtemp()) / "decisions.jsonl"
        agent, broker = build_agent(stopped_position(), lambda p: True, log_path)
        agent.run_cycle(et(14, 0))
        self.assertEqual(len(broker.placed), 1)
        records = [json.loads(line) for line in log_path.read_text().splitlines()]
        advisory = [r for r in records if r["kind"] == "exit_approval_advisory"]
        self.assertEqual(len(advisory), 1)
        self.assertTrue(advisory[0]["approved"])


class DeclinedEntryStillBlocked(unittest.TestCase):
    """Regression: entry approval remains a HARD veto."""

    def test_declined_entry_places_nothing(self):
        cfg = RuntimeConfig(account_number="A1", dry_run=True, armed=False)
        broker = PaperBroker(demo_account(), demo_chains(SESSION))
        seen: list[Preview] = []

        def decline(preview):
            seen.append(preview)
            return False

        log_path = Path(tempfile.mkdtemp()) / "decisions.jsonl"
        agent = SuperTradesAgent(cfg, broker, SimulatedSignalSource(SESSION),
                                 approval=ApprovalGate(decline, required=True),
                                 log=DecisionLog(log_path))
        res = agent.run_cycle(et(14, 32))

        # The NVDA signal fires and is previewed — but the decline blocks it.
        self.assertGreaterEqual(len(seen), 1)
        self.assertIn("NVDA", res.previewed_declined)
        self.assertEqual(res.placed_entries, [])
        self.assertEqual(broker.placed, [])
        log = log_path.read_text()
        self.assertIn('"declined"', log)
        self.assertNotIn('"entry"', log)


if __name__ == "__main__":
    unittest.main()
