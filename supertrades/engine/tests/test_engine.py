"""Stage-gate tests for the SuperTrades v3 orchestrated cycle.

Run:  python -m unittest discover -s supertrades/engine/tests -v
"""
from __future__ import annotations

import asyncio
import copy
import json
import re
import unittest
from pathlib import Path

from supertrades.engine import nodes as nodes_mod
from supertrades.engine.discovery import build_nodes, expected_node_count, gex_underlyings
from supertrades.engine.orchestrator import Node, Orchestrator
from supertrades.engine.reporter import (AGENTIC_ACCT, GUARDRAILS, MARGIN_ACCT,
                                         make_final_reporter, summarizer)
from supertrades.engine.run_cycle import run_one_cycle, synthetic_snapshot

ENGINE_DIR = Path(__file__).resolve().parents[1]
STATE_PATH = ENGINE_DIR.parents[0] / "state.json"


def load_state() -> dict:
    return json.loads(STATE_PATH.read_text())


def entry_ready_state(state: dict) -> dict:
    """State with an agentic day-trade position + clean watchlist candidate."""
    s = copy.deepcopy(state)
    s["positions"] = {
        "pos-agentic": {"contract": "XLE 7/24 $59C", "account": AGENTIC_ACCT,
                        "qty": 1, "entry": 0.40, "hwm": 0.40,
                        "ratchet_engaged": False, "class": "day_trade",
                        "expiry": "2026-07-24",
                        "exit_rules": [{"type": "target", "pct": 50},
                                       {"type": "stop", "pct": -30},
                                       {"type": "ratchet", "arm_pct": 25}]},
        "pos-margin": {"contract": "IREN 7/24 $33P", "account": MARGIN_ACCT,
                       "qty": 1, "entry": 0.39, "hwm": 0.39,
                       "ratchet_engaged": False, "class": "alert_only",
                       "expiry": "2026-07-24",
                       "exit_rules": [{"type": "alert_target", "pct": 50}]},
    }
    s["watchlist"] = [{"id": "cand-nvda", "contract": "NVDA 7/31 $225C"}]
    return s


def perfect_candidate(state: dict, **account) -> dict:
    """Snapshot where cand-nvda passes every entry floor at 10:15 ET."""
    snap = synthetic_snapshot(
        state, et_time="10:15", bp=300.0,
        option_overrides={"cand-nvda": {"ask": 0.60, "delta": 0.42,
                                        "spread_pct": 6.0, "oi": 5000}},
        quote_overrides={"NVDA": {"day_pct": 1.8}})
    snap["quotes"]["NVDA"]["last"] = snap["vwap"]["NVDA"] + 1.0
    snap["account"].update(account)
    return snap


def run(state, snap):
    return asyncio.run(run_one_cycle(state, snap))


class TestNodeCount(unittest.TestCase):
    def test_formula_on_live_state(self):
        state = load_state()
        nodes = build_nodes(state)
        want = (len(state["universe"]) + 3 * len(gex_underlyings(state))
                + len(state["positions"]) + len(state["watchlist"]))
        self.assertEqual(len(nodes), want)
        self.assertEqual(expected_node_count(state), want)

    def test_one_node_per_unit(self):
        state = load_state()
        keys = [(n.kind, n.key) for n in build_nodes(state)]
        self.assertEqual(len(keys), len(set(keys)), "duplicate node")
        for sym in gex_underlyings(state):
            for kind in ("gex_map", "whale_flow", "pullback_gate"):
                self.assertIn((kind, sym), keys)


class TestSingleGuardrailGate(unittest.TestCase):
    def test_halt_suppresses_every_entry_regardless_of_nodes(self):
        state = entry_ready_state(load_state())
        # control: same snapshot, healthy account -> entry recommended
        healthy = run(state, perfect_candidate(state, day_realized=0.0))
        self.assertIsNotNone(healthy["actions"]["entry"])
        self.assertEqual(healthy["actions"]["entry"]["id"], "cand-nvda")
        # halted: identical node inputs, day P&L below threshold
        halted = run(state, perfect_candidate(state, day_realized=-80.0))
        self.assertTrue(halted["guardrail_audit"]["halted"])
        self.assertIsNone(halted["actions"]["entry"])
        for audit in halted["guardrail_audit"]["per_candidate"]:
            self.assertIn("daily_halt", audit["blocked_by"])
        self.assertIn("No entries recommended", halted["console"]["entries_note"])

    def test_exits_stay_live_during_halt(self):
        state = entry_ready_state(load_state())
        snap = perfect_candidate(state, day_realized=-80.0)
        snap["option_quotes"]["pos-agentic"].update(
            {"mark": 0.26, "bid": 0.25})           # -35% -> stop
        report = run(state, snap)
        self.assertTrue(report["guardrail_audit"]["halted"])
        stops = [e for e in report["actions"]["exits"]
                 if e["id"] == "pos-agentic" and e["order"] == "sell_limit_at_bid"]
        self.assertTrue(stops, "stop exit must survive the halt")

    def test_nodes_propose_even_when_account_is_halted(self):
        """Nodes never read guardrails: identical output under a halted account."""
        state = entry_ready_state(load_state())
        snap = perfect_candidate(state, day_realized=-500.0, halted=True)
        out = asyncio.run(nodes_mod.candidate_entry(
            {"id": "cand-nvda", "symbol": "NVDA"}, snap))
        self.assertNotIn("blocked", out)
        self.assertEqual(out["ask"], 0.60)

    def test_guardrails_defined_only_in_reporter(self):
        """Static check: no guardrail constant/threshold outside reporter.py."""
        for name in ("orchestrator.py", "nodes.py", "discovery.py", "run_cycle.py"):
            src = (ENGINE_DIR / name).read_text()
            src = re.sub(r'("""|\'\'\')(?:.|\n)*?\1', "", src)  # docstrings
            src = re.sub(r"#[^\n]*", "", src)                    # comments
            self.assertNotIn("GUARDRAILS", src, name)
            patterns = [r"-\s*60", r"0\.25", r"0\.40", r"freez"]
            if name != "run_cycle.py":   # run_cycle's fixture carries the
                patterns.append(r"halt")  # account schema field "halted"
            for pattern in patterns:
                self.assertIsNone(re.search(pattern, src),
                                  f"guardrail-like value '{pattern}' in {name}")


class TestEntryFloors(unittest.TestCase):
    def _blocked(self, report, cid="cand-nvda"):
        for a in report["guardrail_audit"]["per_candidate"]:
            if a["id"] == cid:
                return a["blocked_by"]
        raise AssertionError("candidate not audited")

    def test_each_floor_blocks(self):
        state = entry_ready_state(load_state())
        cases = {
            "delta_floor": {"delta": 0.20},
            "spread_cap": {"spread_pct": 14.0},
            "oi_floor": {"oi": 120},
            "per_trade_cap": {"ask": 1.50},   # $150 > 40% of $300
        }
        for reason, patch in cases.items():
            snap = perfect_candidate(state)
            snap["option_quotes"]["cand-nvda"].update(patch)
            self.assertIn(reason, self._blocked(run(state, snap)), reason)

    def test_max_one_auto_entry_and_settlement_suppression(self):
        state = entry_ready_state(load_state())
        used = run(state, perfect_candidate(state, auto_entries_used=1))
        self.assertIn("max_auto_entries_used", self._blocked(used))
        low_bp = run(state, perfect_candidate(state, bp=61.0))
        self.assertIn("settlement_suppressed", self._blocked(low_bp))

    def test_already_held_and_time_windows(self):
        state = entry_ready_state(load_state())
        state["watchlist"] = [{"id": "cand-nvda", "contract": "XLE 8/7 $60C"}]
        snap = synthetic_snapshot(
            state, et_time="10:15", bp=300.0,
            option_overrides={"cand-nvda": {"ask": 0.60, "delta": 0.42,
                                            "spread_pct": 6.0, "oi": 5000}},
            quote_overrides={"XLE": {"day_pct": 1.8}})
        snap["quotes"]["XLE"]["last"] = snap["vwap"]["XLE"] + 1.0
        self.assertIn("already_held", self._blocked(run(state, snap)))
        early = perfect_candidate(entry_ready_state(load_state()))
        early["et_time"] = "09:35"
        r = run(entry_ready_state(load_state()), early)
        self.assertIn("opening_no_entry_window", self._blocked(r))
        late = perfect_candidate(entry_ready_state(load_state()))
        late["et_time"] = "15:10"
        r = run(entry_ready_state(load_state()), late)
        self.assertIn("after_1500_gex_scalp_only", self._blocked(r))


class TestExitRouting(unittest.TestCase):
    def test_margin_position_is_alert_only(self):
        state = entry_ready_state(load_state())
        snap = perfect_candidate(state)
        snap["option_quotes"]["pos-margin"].update({"mark": 0.60})  # +54% alert_target
        report = run(state, snap)
        self.assertFalse([e for e in report["actions"]["exits"]
                          if e["id"] == "pos-margin"])
        self.assertTrue([a for a in report["actions"]["alerts"]
                         if a.get("id") == "pos-margin"])

    def test_target_and_ratchet_arm(self):
        state = entry_ready_state(load_state())
        snap = perfect_candidate(state)
        snap["option_quotes"]["pos-agentic"].update({"mark": 0.61})  # +52%
        report = run(state, snap)
        self.assertTrue([e for e in report["actions"]["exits"]
                         if e["id"] == "pos-agentic"
                         and e["order"] == "sell_limit_at_mark"])
        self.assertTrue([u for u in report["actions"]["state_updates"]
                         if u["id"] == "pos-agentic"
                         and u["set"].get("ratchet_engaged")])


class TestOrchestrator(unittest.TestCase):
    def test_failed_node_never_sinks_the_cycle(self):
        async def boom(payload, snapshot):
            raise RuntimeError("synthetic node failure")
        state = entry_ready_state(load_state())
        snap = perfect_candidate(state)

        async def go():
            nodes = build_nodes(state) + [Node("ticker_signal", "BOOM", boom, {})]
            orch = Orchestrator()
            return await orch.run(nodes, snap, summarizer,
                                  make_final_reporter(state))
        report = asyncio.run(go())
        self.assertEqual(len(report["meta"]["errors"]), 1)
        self.assertIn("synthetic node failure", report["meta"]["errors"][0]["error"])
        self.assertIsNotNone(report["actions"]["entry"])  # rest of cycle intact

    def test_layered_fan_in_past_batch_size(self):
        orch = Orchestrator(batch_size=30)
        results = [{"kind": "ticker_signal", "key": f"S{i}", "ok": True,
                    "data": {"symbol": f"S{i}", "day_pct": 0.1, "events": []}}
                   for i in range(100)]
        merged = orch.layered_fan_in(results, summarizer)
        self.assertEqual(merged["node_count"], 100)
        self.assertEqual(len(merged["groups"]["signals"]), 100)

    def test_full_cycle_on_live_state(self):
        state = load_state()
        report = run(state, synthetic_snapshot(state))
        self.assertEqual(report["meta"]["node_count"],
                         expected_node_count(state))
        for section in ("kpis", "positions_rails", "signal_board",
                        "pullback_gate", "gex_map", "loop_guardrails"):
            self.assertIn(section, report["console"])


if __name__ == "__main__":
    unittest.main()
