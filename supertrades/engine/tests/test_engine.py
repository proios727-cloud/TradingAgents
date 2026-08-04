"""Stage-gate tests for the SuperTrades v3 orchestrated cycle.

Run:  python -m unittest discover -s supertrades/engine/tests -v
"""
from __future__ import annotations

import asyncio
import copy
import datetime as dt
import json
import re
import unittest
from pathlib import Path

from supertrades.engine import journal
from supertrades.engine import nodes as nodes_mod
from supertrades.engine import ops
from supertrades.engine.discovery import build_nodes, expected_node_count, gex_underlyings
from supertrades.engine.orchestrator import Node, Orchestrator
from supertrades.engine.reporter import (AGENTIC_ACCT, GUARDRAILS, MARGIN_ACCT,
                                         high_iv_steer, make_final_reporter,
                                         short_dte_override_max_usd, summarizer)
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


class TestDisciplineGovernorV4(unittest.TestCase):
    """v4 Layer 1: the discipline governor. Each rule guarded so it can't regress."""

    def _blocked(self, report, cid="cand-nvda"):
        for a in report["guardrail_audit"]["per_candidate"]:
            if a["id"] == cid:
                return a["blocked_by"]
        raise AssertionError("candidate not audited")

    def test_delta_floor_raised_to_035(self):
        state = entry_ready_state(load_state())
        snap = perfect_candidate(state)
        snap["option_quotes"]["cand-nvda"].update({"delta": 0.30})  # was fine at 0.25
        self.assertIn("delta_floor", self._blocked(run(state, snap)))

    def test_premium_floor_blocks_cheap_contracts(self):
        state = entry_ready_state(load_state())
        snap = perfect_candidate(state)
        snap["option_quotes"]["cand-nvda"].update({"ask": 0.30})    # < $0.40 premium floor
        self.assertIn("min_premium", self._blocked(run(state, snap)))

    def test_per_trade_cap_tightened(self):
        state = entry_ready_state(load_state())
        snap = perfect_candidate(state)                              # bp 300
        snap["option_quotes"]["cand-nvda"].update({"ask": 1.00})    # $100 = 33% (> 22% cap)
        self.assertIn("per_trade_cap", self._blocked(run(state, snap)))

    def test_min_dte_blocks_short_dated_day_trade(self):
        state = entry_ready_state(load_state())
        state["watchlist"] = [{"id": "cand-nvda", "contract": "NVDA 7/29 $225C"}]
        snap = perfect_candidate(state)
        report = asyncio.run(run_one_cycle(state, snap, dt.date(2026, 7, 27)))  # 2 DTE
        self.assertIn("min_dte", self._blocked(report))

    def test_0dte_blocked_for_non_index(self):
        state = entry_ready_state(load_state())
        state["watchlist"] = [{"id": "cand-nvda", "contract": "NVDA 7/27 $225C"}]
        snap = perfect_candidate(state)
        report = asyncio.run(run_one_cycle(state, snap, dt.date(2026, 7, 27)))  # 0 DTE
        self.assertIn("0dte_blocked", self._blocked(report))

    def test_daily_entry_cap_freezes_all(self):
        state = entry_ready_state(load_state())
        capped = run(state, perfect_candidate(state, manual_entries_today=2))
        self.assertIsNone(capped["actions"]["entry"])
        for a in capped["guardrail_audit"]["per_candidate"]:
            self.assertIn("daily_entry_cap", a["blocked_by"])
        self.assertIn("daily_entry_cap", capped["guardrail_audit"]["entry_frozen"])

    def test_churn_brake_fires_at_three(self):
        state = entry_ready_state(load_state())
        state["day"]["churn_threshold_hit"] = False          # not yet alerted today
        snap = perfect_candidate(state)
        snap["account"]["manual_round_trips"] = 3            # v4 brake (was 4)
        # always visible in the scorecard, even under DND
        report = run(state, snap)
        self.assertTrue(any("churn" in f.lower()
                            for f in report["console"]["discipline"]["flags"]))
        # and mobile-pushes once notifications are on
        state["mode"]["dnd"] = False
        self.assertTrue([p for p in run(state, snap)["pushes"]
                         if p["kind"] == "churn_guard"])

    def test_overtrade_push_on_third_entry(self):
        state = entry_ready_state(load_state())
        snap = perfect_candidate(state, manual_entries_today=3)  # over the 2/day cap
        report = run(state, snap)
        self.assertTrue(any("cap" in f.lower()
                            for f in report["console"]["discipline"]["flags"]))
        state["mode"]["dnd"] = False
        self.assertTrue([p for p in run(state, snap)["pushes"]
                         if p["kind"] == "entry_cap"])

    def test_discipline_scorecard_present(self):
        state = load_state()
        report = run(state, synthetic_snapshot(state))
        d = report["console"]["discipline"]
        self.assertEqual(d["entries_cap"], 2)
        self.assertEqual(d["round_trip_brake"], 3)
        self.assertEqual(d["quality_floor"]["delta_min"], 0.35)
        self.assertEqual(d["quality_floor"]["min_dte"], 5)


class TestVolAwareAndConcentrationV42(unittest.TestCase):
    """v4.2 (8/4): IV-aware pricing steer + short-DTE concentration override ceiling."""

    def _audit(self, report, cid="cand-nvda"):
        for a in report["guardrail_audit"]["per_candidate"]:
            if a["id"] == cid:
                return a
        raise AssertionError("candidate not audited")

    def test_iv_hard_cap_blocks_uninvestable_premium(self):
        state = entry_ready_state(load_state())
        snap = perfect_candidate(state)
        snap["option_quotes"]["cand-nvda"].update({"iv": 3.0})   # 300% > 250% hard cap
        self.assertIn("iv_hard_cap", self._audit(run(state, snap))["blocked_by"])

    def test_high_iv_warns_but_does_not_block(self):
        state = entry_ready_state(load_state())
        snap = perfect_candidate(state)
        snap["option_quotes"]["cand-nvda"].update({"iv": 1.22})  # like the 8/4 INTC
        audit = self._audit(run(state, snap))
        self.assertIn("high_iv_prefer_debit_spread", audit["warnings"])
        self.assertNotIn("iv_hard_cap", audit["blocked_by"])
        self.assertTrue(audit["eligible"])                       # still tradable, just steered

    def test_iv_rank_top_band_also_steers(self):
        self.assertTrue(high_iv_steer(0.40, iv_rank=0.85))       # low abs IV, but top of year
        self.assertFalse(high_iv_steer(0.40, iv_rank=0.50))
        self.assertTrue(high_iv_steer(1.50, iv_rank=None))       # abs IV alone trips it

    def test_selection_prefers_lower_iv_expression(self):
        """A calmer-IV candidate outranks a higher-delta high-IV one."""
        state = entry_ready_state(load_state())
        state["watchlist"] = [{"id": "cand-nvda", "contract": "NVDA 7/31 $225C"},
                              {"id": "cand-amd", "contract": "AMD 7/31 $180C"}]
        snap = synthetic_snapshot(
            state, et_time="10:15", bp=600.0,
            option_overrides={
                "cand-nvda": {"ask": 0.60, "delta": 0.55, "spread_pct": 6.0,
                              "oi": 5000, "iv": 1.30},           # richer delta, hot IV
                "cand-amd": {"ask": 0.60, "delta": 0.42, "spread_pct": 6.0,
                             "oi": 5000, "iv": 0.45}},           # lower delta, calm IV
            quote_overrides={"NVDA": {"day_pct": 1.8}, "AMD": {"day_pct": 1.8}})
        for s in ("NVDA", "AMD"):
            snap["vwap"][s] = 100.0
            snap["quotes"][s]["last"] = 101.0      # above VWAP -> conviction ok
        report = run(state, snap)
        self.assertEqual(report["actions"]["entry"]["id"], "cand-amd")

    def test_short_dte_concentration_blocks_oversized_short_dated(self):
        state = entry_ready_state(load_state())
        state["watchlist"] = [{"id": "cand-nvda", "contract": "NVDA 7/29 $225C"}]
        # 3-DTE, cost $200 on $500 BP = 40% > 35% short-DTE ceiling
        snap = synthetic_snapshot(
            state, et_time="10:15", bp=500.0,
            option_overrides={"cand-nvda": {"ask": 2.00, "delta": 0.42,
                                            "spread_pct": 6.0, "oi": 5000, "iv": 0.5}},
            quote_overrides={"NVDA": {"day_pct": 1.8}})
        snap["quotes"]["NVDA"]["last"] = snap["vwap"]["NVDA"] + 1.0
        report = asyncio.run(run_one_cycle(state, snap, dt.date(2026, 7, 27)))  # 2 DTE
        self.assertIn("short_dte_concentration",
                      self._audit(report)["blocked_by"])

    def test_short_dte_override_ceiling_helper(self):
        self.assertAlmostEqual(short_dte_override_max_usd(402.0), 140.7)   # 35% of BP
        # today's INTC 1-DTE @ $199 on ~$402 BP would have exceeded this ceiling
        self.assertGreater(199.0, short_dte_override_max_usd(402.0))

    def test_scorecard_surfaces_new_rails(self):
        state = load_state()
        qf = run(state, synthetic_snapshot(state))["console"]["discipline"]["quality_floor"]
        self.assertEqual(qf["iv_soft_cap"], 0.90)
        self.assertEqual(qf["iv_hard_cap"], 2.50)
        self.assertEqual(qf["short_dte_bp_frac_cap"], 0.35)


class TestProfitMaxGivebackV43(unittest.TestCase):
    """v4.3 (8/4): trailing give-back guard + scale-out + runner (uncap winners).

    Prompted by QQQ 8/4: +123% peak round-tripped to +56% exit because the fixed
    +50% target both capped upside and lagged the poll. Fix = let winners run and
    trail a give-back stop off the high-water mark; scale out across multiple lots.
    """

    def _run_pos(self, exit_rules, *, qty=1, entry=0.64, hwm=None, mark=None,
                 bid=None, ratchet=False, scaled=False, cls="0dte_scalp"):
        state = copy.deepcopy(load_state())
        state["positions"] = {
            "pos-agentic": {"contract": "QQQ 8/4 $724C", "account": AGENTIC_ACCT,
                            "qty": qty, "entry": entry, "hwm": hwm if hwm else entry,
                            "ratchet_engaged": ratchet, "scaled_out": scaled,
                            "class": cls, "expiry": "2026-08-04",
                            "exit_rules": exit_rules}}
        state["watchlist"] = []
        snap = synthetic_snapshot(state, et_time="10:15", bp=500.0)
        snap["option_quotes"]["pos-agentic"].update(
            {"mark": mark, "bid": bid if bid is not None else mark})
        return run(state, snap)

    def _exits(self, report):
        return [e for e in report["actions"]["exits"] if e["id"] == "pos-agentic"]

    GB = {"type": "giveback", "arm_gain_pct": 40, "peak_frac": 0.30}

    def test_giveback_trails_after_peak(self):
        # peak 1.43 (+123%), pulled back to 1.15: gave back 0.28 >= 0.30*0.79=0.237 -> exit
        r = self._run_pos([self.GB], hwm=1.43, mark=1.15, bid=1.14)
        ex = self._exits(r)
        self.assertTrue(ex and ex[0]["order"] == "sell_limit_at_bid")
        self.assertIn("give-back", ex[0]["why"])

    def test_giveback_dormant_below_arm(self):
        # peak only +30% (< 40% arm): trail not armed, no exit despite a pullback
        r = self._run_pos([self.GB], hwm=0.83, mark=0.72, bid=0.71)
        self.assertFalse(self._exits(r))

    def test_giveback_holds_near_peak(self):
        # still near the high (gave back < 30% of peak): keep holding
        r = self._run_pos([self.GB], hwm=1.43, mark=1.35, bid=1.34)
        self.assertFalse(self._exits(r))

    def test_non_0dte_trails_wider(self):
        # identical retrace: 0.40 peak_frac (day_trade) holds where 0.30 (0dte) would exit
        rules_wide = [{"type": "giveback", "arm_gain_pct": 40, "peak_frac": 0.40}]
        wide = self._run_pos(rules_wide, hwm=1.43, mark=1.15, bid=1.14, cls="day_trade")
        self.assertFalse(self._exits(wide))                       # 0.28 < 0.40*0.79=0.316
        tight = self._run_pos([self.GB], hwm=1.43, mark=1.15, bid=1.14)
        self.assertTrue(self._exits(tight))                       # 0.28 >= 0.237

    def test_runner_does_not_cap_at_target(self):
        rules = [{"type": "target", "pct": 50, "runner": True},
                 {"type": "giveback", "arm_gain_pct": 40, "peak_frac": 0.30}]
        # +55% (past target) but still near peak -> HOLD, not sell
        r = self._run_pos(rules, hwm=1.00, mark=0.99, bid=0.98)
        self.assertFalse(self._exits(r))
        self.assertTrue([a for a in r["actions"]["alerts"]
                         if a.get("rule") == "target_hold_runner"])

    def test_scale_out_banks_slice_and_trails_rest(self):
        rules = [{"type": "target", "pct": 50, "scale_out_frac": 0.5},
                 {"type": "giveback", "arm_gain_pct": 40, "peak_frac": 0.30}]
        r = self._run_pos(rules, qty=3, hwm=1.00, mark=0.99, bid=0.98)
        ex = self._exits(r)
        self.assertTrue(ex and ex[0]["qty"] == 1)                 # int(3*0.5)=1 banked
        upd = [u for u in r["actions"]["state_updates"]
               if u["id"] == "pos-agentic" and u["set"].get("scaled_out")]
        self.assertTrue(upd and upd[0]["set"]["qty"] == 2)        # 2 ride the trail

    def test_hwm_persists_for_trail_reference(self):
        # new high above stored hwm -> state bumps hwm so the trail measures true peak
        r = self._run_pos([self.GB], hwm=0.64, mark=1.20, bid=1.19)
        upd = [u for u in r["actions"]["state_updates"]
               if u["id"] == "pos-agentic" and "hwm" in u["set"]]
        self.assertTrue(upd and upd[0]["set"]["hwm"] == 1.20)

    def test_class_defaults_carry_profit_max_profiles(self):
        cd = load_state()["class_defaults"]
        self.assertEqual(cd["0dte_scalp"]["profit_max"]["giveback"]["peak_frac"], 0.30)
        self.assertEqual(cd["day_trade"]["profit_max"]["giveback"]["peak_frac"], 0.40)
        self.assertEqual(cd["swing"]["profit_max"]["giveback"]["peak_frac"], 0.50)
        self.assertIn("ta_fundamental_gate", cd["swing"]["profit_max"])


class TestWinRateGreenLockV44(unittest.TestCase):
    """v4.4 (8/4): green_lock converts a brief winner into a guaranteed small win.

    Review found win rate ~33% (2/6) with the edge erased by winners round-tripping
    to losses. green_lock arms a small-green floor once the peak clears arm_pct.
    """

    def _run_pos(self, exit_rules, *, entry=0.64, hwm=None, mark=None, bid=None):
        state = copy.deepcopy(load_state())
        state["positions"] = {
            "pos-agentic": {"contract": "QQQ 8/4 $724C", "account": AGENTIC_ACCT,
                            "qty": 1, "entry": entry, "hwm": hwm if hwm else entry,
                            "ratchet_engaged": False, "class": "day_trade",
                            "expiry": "2026-08-04", "exit_rules": exit_rules}}
        state["watchlist"] = []
        snap = synthetic_snapshot(state, et_time="10:15", bp=500.0)
        snap["option_quotes"]["pos-agentic"].update(
            {"mark": mark, "bid": bid if bid is not None else mark})
        return run(state, snap)

    def _exits(self, r):
        return [e for e in r["actions"]["exits"] if e["id"] == "pos-agentic"]

    GL = {"type": "green_lock", "arm_pct": 20, "floor_pct": 5}

    def test_green_lock_exits_when_winner_round_trips(self):
        # peaked +25% (0.80), fell back to +3% (0.66) <= +5% lock -> exit a WIN
        r = self._run_pos([self.GL], hwm=0.80, mark=0.66, bid=0.65)
        ex = self._exits(r)
        self.assertTrue(ex and ex[0]["order"] == "sell_limit_at_bid")
        self.assertIn("green_lock", ex[0]["why"])

    def test_green_lock_dormant_until_armed(self):
        # peak only +12% (< 20% arm): floor not live, no exit at +3%
        r = self._run_pos([self.GL], hwm=0.72, mark=0.66, bid=0.65)
        self.assertFalse(self._exits(r))

    def test_green_lock_holds_above_floor(self):
        # armed (peak +25%) but still +15% (> +5% floor): keep holding
        r = self._run_pos([self.GL], hwm=0.80, mark=0.735, bid=0.73)
        self.assertFalse(self._exits(r))

    def test_class_defaults_carry_green_lock(self):
        cd = load_state()["class_defaults"]
        self.assertEqual(cd["0dte_scalp"]["green_lock"]["floor_pct"], 8)
        self.assertEqual(cd["day_trade"]["green_lock"]["floor_pct"], 5)
        self.assertEqual(cd["swing"]["green_lock"]["arm_pct"], 30)


class TestReliableOpsV4(unittest.TestCase):
    """v4 Layer 2: deterministic clock/flatten/staleness so no cycle silently misses."""

    def test_clock_phase(self):
        self.assertEqual(ops.clock_phase("08:00"), "closed")
        self.assertEqual(ops.clock_phase("09:15"), "premarket")
        self.assertEqual(ops.clock_phase("10:00"), "core")
        self.assertEqual(ops.clock_phase("12:30"), "midday")
        self.assertEqual(ops.clock_phase("15:30"), "power_hour")
        self.assertEqual(ops.clock_phase("16:30"), "closed")
        self.assertEqual(ops.clock_phase("10:00", weekday=False), "closed")

    def test_rollover_due(self):
        self.assertTrue(ops.rollover_due("2026-07-24", "2026-07-27"))
        self.assertFalse(ops.rollover_due("2026-07-27", "2026-07-27"))

    def test_flatten_due_catches_daytrade_and_0dte(self):
        s = load_state()
        s["positions"] = {
            "dt": {"account": AGENTIC_ACCT, "class": "day_trade", "ratchet_engaged": False},
            "od": {"account": AGENTIC_ACCT, "class": "0dte_scalp", "ratchet_engaged": False},
            "rt": {"account": AGENTIC_ACCT, "class": "day_trade", "ratchet_engaged": True},
            "mg": {"account": MARGIN_ACCT, "class": "alert_only", "ratchet_engaged": False},
        }
        self.assertEqual(ops.flatten_due(s, "15:00"), [])              # before any stop
        self.assertEqual(set(ops.flatten_due(s, "15:20")), {"od"})     # 0dte hard-exit 15:15
        self.assertEqual(set(ops.flatten_due(s, "15:50")), {"od", "dt"})  # + day-trade 15:45
        self.assertNotIn("rt", ops.flatten_due(s, "15:50"))           # ratchet engaged -> hold
        self.assertNotIn("mg", ops.flatten_due(s, "15:50"))           # margin never flattened

    def test_stale(self):
        self.assertTrue(ops.stale("2026-07-27T14:00:00Z", "2026-07-27T14:25:00Z"))
        self.assertFalse(ops.stale("2026-07-27T14:00:00Z", "2026-07-27T14:05:00Z"))
        self.assertTrue(ops.stale(None, "2026-07-27T14:00:00Z"))

    def test_cycle_intent_closed_is_noop(self):
        s = load_state()
        it = ops.cycle_intent("07:00", True, s["trading_date"], "2026-07-27", s)
        self.assertEqual(it["actions"], ["no_op"])

    def test_cycle_intent_premarket_rollover(self):
        s = load_state()
        it = ops.cycle_intent("09:10", True, "2026-07-24", "2026-07-27", s)
        self.assertIn("rollover", it["actions"])
        self.assertIn("build_premarket_plan", it["actions"])
        self.assertIn("run_cycle", it["actions"])

    def test_cycle_intent_flags_flatten_and_stale(self):
        s = load_state()
        s["positions"] = {"dt": {"account": AGENTIC_ACCT, "class": "day_trade",
                                 "ratchet_engaged": False}}
        it = ops.cycle_intent("15:50", True, "2026-07-27", "2026-07-27", s,
                              updated_at="2026-07-27T15:00:00Z",
                              now="2026-07-27T19:50:00Z")
        self.assertIn("flatten", it["actions"])
        self.assertEqual(it["flatten_ids"], ["dt"])
        self.assertIn("reconcile_broker", it["actions"])


class TestJournalWriterV4(unittest.TestCase):
    def test_slug_is_filename_safe_and_stable(self):
        self.assertEqual(journal.slug("DIS 8/21 $105C"), "DIS-8-21-105C")
        self.assertEqual(journal.slug("SPY 8/7 $765C"), "SPY-8-7-765C")

    def test_append_under_replaces_placeholder_then_appends(self):
        md = "# D\n\n## Cycle log\n- (none yet)\n"
        out = journal.append_under(md, "## Cycle log",
                                   journal.cycle_line("09:56", "reconcile", "flat"))
        self.assertNotIn("(none yet)", out)
        self.assertIn("- 09:56 ET — **reconcile**: flat", out)
        # a second append keeps both bullets, in order
        out2 = journal.append_under(out, "## Cycle log",
                                    journal.cycle_line("10:30", "cycle", "no entry"))
        self.assertLess(out2.index("reconcile"), out2.index("no entry"))

    def test_append_under_missing_heading_appends_section(self):
        out = journal.append_under("# D\n", "## Cycle log",
                                   journal.cycle_line("09:56", "x", "y"))
        self.assertIn("## Cycle log", out)
        self.assertIn("**x**: y", out)

    def test_append_under_stops_at_next_heading(self):
        md = "## Cycle log\n- a\n\n## EOD review\n- keep me\n"
        out = journal.append_under(md, "## Cycle log",
                                   journal.cycle_line("10:00", "b", "c"))
        # new bullet lands before EOD review, which is untouched
        self.assertLess(out.index("**b**: c"), out.index("EOD review"))
        self.assertIn("- keep me", out)

    def test_trade_frontmatter_defaults_pinescript_source(self):
        fm = journal.trade_frontmatter({"symbol": "NVDA",
                                        "contract": "NVDA 8/21 $210C"})
        self.assertIn("signal_source: pinescript", fm)
        self.assertIn("account: 902341866", fm)
        self.assertIn("# NVDA 8/21 $210C", fm)
        self.assertTrue(fm.startswith("---\n"))


if __name__ == "__main__":
    unittest.main()
