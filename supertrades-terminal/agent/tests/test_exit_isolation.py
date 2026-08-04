"""Per-position isolation on the exit/flatten paths.

The defect these tests pin down: since commit 5fa8797 the broker parses
strictly and RAISES on missing fields / unknown order state, so
``place_order`` and ``cancel_all`` really can throw. Before this fix, an
unguarded ``place_order``/``cancel_all`` call inside a ``for pos in
get_positions()`` loop let ONE failing position's exception propagate out and
abort the exits/flatten of every OTHER position that cycle.

Required behavior:
  * ``_manage_exits``: a raise on one position's ``place_order`` must not
    prevent later positions from getting their exits placed.
  * ``_flatten_all`` (the kill-switch / 15:45 emergency path): same
    isolation — every position must get an attempt regardless of how many
    fail.
  * ``cancel_all()`` raising on the kill path must not prevent the flatten
    from running at all.
  * Every failure is loudly journaled (``exit_failed`` / ``flatten_failed``)
    with the symbol, exit kind, and error text — never silently swallowed,
    never logged as a success.

PaperBroker subclasses only; nothing here can touch a real broker.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from agent.broker.paper import PaperBroker
from agent.config import MARKET_TZ, RuntimeConfig
from agent.decision_log import DecisionLog
from agent.engine import SuperTradesAgent
from agent.kill_switch import KillState
from agent.models import Position

SESSION = date(2026, 7, 20)


def et(h, m):
    return datetime(2026, 7, 20, h, m, tzinfo=MARKET_TZ)


class NoSignals:
    def fired_signals(self, now):
        return []

    def earnings_symbols(self, now):
        return frozenset()


def stopped_position(sym):
    # -50% premium stop fires: entry 1.20, mark 0.60.
    return Position(sym, f"oid-{sym}", "call", 202.5, SESSION, 4, 1.20, 0.60,
                    201.75, 202.90)


def healthy_position(sym):
    # Flat-ish mark — only the 15:45 force-flatten fires on this one.
    return Position(sym, f"oid-{sym}", "call", 202.5, SESSION, 4, 1.20, 1.25,
                     201.75, 202.90)


class FailFirstBroker(PaperBroker):
    """Raises on ``place_order`` for one designated symbol, every time."""

    def __init__(self, *a, fail_symbol: str, **kw):
        super().__init__(*a, **kw)
        self.fail_symbol = fail_symbol

    def place_order(self, intent):
        if intent.symbol == self.fail_symbol:
            raise ValueError(f"broker rejected order for {intent.symbol}: unknown order state")
        return super().place_order(intent)


class CancelAllRaisesBroker(PaperBroker):
    def cancel_all(self) -> None:
        raise RuntimeError("cancel_all: MCP transport error")


def build_agent(broker, log_path):
    cfg = RuntimeConfig(account_number="A1", dry_run=True, armed=False)
    agent = SuperTradesAgent(cfg, broker, NoSignals(),
                             log=DecisionLog(log_path))
    return agent


def read_log(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


class ManageExitsIsolation(unittest.TestCase):
    def test_first_position_failure_does_not_block_the_rest(self):
        from agent.simulated import demo_account
        positions = [stopped_position("NVDA"), stopped_position("TSLA"),
                     stopped_position("AMD")]
        broker = FailFirstBroker(demo_account(), positions=positions,
                                  fail_symbol="NVDA")
        log_path = Path(tempfile.mkdtemp()) / "decisions.jsonl"
        agent = build_agent(broker, log_path)

        res = agent.run_cycle(et(14, 0))

        # All three positions were evaluated (the exit was attempted for
        # each), and the two healthy ones actually placed.
        self.assertEqual(len(res.exits), 3)
        placed_symbols = {i.symbol for i in broker.placed}
        self.assertEqual(placed_symbols, {"TSLA", "AMD"})
        self.assertNotIn("NVDA", placed_symbols)

        # The failure is surfaced on the CycleResult...
        self.assertEqual(len(res.failed_exits), 1)
        self.assertEqual(res.failed_exits[0][0], "NVDA")
        self.assertEqual(res.failed_exits[0][1], "stop")
        self.assertIn("unknown order state", res.failed_exits[0][2])

        # ...and loudly in the decision log, distinct from a real exit.
        records = read_log(log_path)
        failed = [r for r in records if r["kind"] == "exit_failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["symbol"], "NVDA")
        self.assertEqual(failed[0]["exit_kind"], "stop")
        self.assertIn("unknown order state", failed[0]["error"])
        # It must never masquerade as a successful exit record.
        exits = [r for r in records if r["kind"] == "exit"]
        self.assertEqual({r["symbol"] for r in exits}, {"TSLA", "AMD"})

    def test_middle_position_failure_does_not_block_later_ones(self):
        from agent.simulated import demo_account
        positions = [stopped_position("NVDA"), stopped_position("TSLA"),
                     stopped_position("AMD")]
        broker = FailFirstBroker(demo_account(), positions=positions,
                                  fail_symbol="TSLA")
        log_path = Path(tempfile.mkdtemp()) / "decisions.jsonl"
        agent = build_agent(broker, log_path)

        res = agent.run_cycle(et(14, 0))

        placed_symbols = {i.symbol for i in broker.placed}
        self.assertEqual(placed_symbols, {"NVDA", "AMD"})
        self.assertEqual(len(res.failed_exits), 1)
        self.assertEqual(res.failed_exits[0][0], "TSLA")


class FlattenAllIsolation(unittest.TestCase):
    def test_one_failing_position_does_not_block_flatten_of_the_rest(self):
        from agent.simulated import demo_account
        positions = [healthy_position("NVDA"), healthy_position("TSLA"),
                     healthy_position("AMD")]
        broker = FailFirstBroker(demo_account(), positions=positions,
                                  fail_symbol="NVDA")
        log_path = Path(tempfile.mkdtemp()) / "decisions.jsonl"
        agent = build_agent(broker, log_path)

        # Trip the kill switch directly and drive the kill path (STOP).
        agent.kill.user_stop = True
        res = agent.run_cycle(et(14, 0))

        self.assertEqual(res.killed, "operator STOP")
        # All three positions were attempted for the emergency flatten.
        self.assertEqual(len(res.exits), 3)
        placed_symbols = {i.symbol for i in broker.placed}
        self.assertEqual(placed_symbols, {"TSLA", "AMD"})
        self.assertNotIn("NVDA", placed_symbols)

        self.assertEqual(len(res.failed_exits), 1)
        self.assertEqual(res.failed_exits[0][0], "NVDA")
        self.assertEqual(res.failed_exits[0][1], "flatten")

        records = read_log(log_path)
        failed = [r for r in records if r["kind"] == "flatten_failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["symbol"], "NVDA")
        self.assertIn("unknown order state", failed[0]["error"])

        # The kill switch stays tripped/halted after the failure.
        self.assertTrue(agent.day.halted)

    def test_cancel_all_raising_still_yields_a_full_flatten(self):
        from agent.simulated import demo_account
        positions = [healthy_position("NVDA"), healthy_position("TSLA")]
        broker = CancelAllRaisesBroker(demo_account(), positions=positions)
        log_path = Path(tempfile.mkdtemp()) / "decisions.jsonl"
        agent = build_agent(broker, log_path)

        agent.kill.user_stop = True
        res = agent.run_cycle(et(14, 0))

        self.assertEqual(res.killed, "operator STOP")
        self.assertEqual(len(res.exits), 2)
        self.assertEqual({i.symbol for i in broker.placed}, {"NVDA", "TSLA"})
        self.assertEqual(res.failed_exits, [])

        records = read_log(log_path)
        cancel_failed = [r for r in records if r["kind"] == "cancel_all_failed"]
        self.assertEqual(len(cancel_failed), 1)
        self.assertIn("MCP transport error", cancel_failed[0]["error"])
        # The flatten (kill) record and both real exits still made it through.
        self.assertTrue(any(r["kind"] == "kill" for r in records))
        self.assertEqual(len([r for r in records if r["kind"] == "exit"
                              and r.get("exit_kind") == "flatten"]), 0)


if __name__ == "__main__":
    unittest.main()
