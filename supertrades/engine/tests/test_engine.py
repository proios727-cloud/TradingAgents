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
                                         materialize_exit_rules, short_dte_override_max_usd,
                                         size_order, summarizer)
from supertrades.engine.run_cycle import run_one_cycle, synthetic_snapshot
from supertrades.engine import live
from supertrades.engine import evolution

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
        halted = run(state, perfect_candidate(state, day_realized=-130.0))
        self.assertTrue(halted["guardrail_audit"]["halted"])
        self.assertIsNone(halted["actions"]["entry"])
        for audit in halted["guardrail_audit"]["per_candidate"]:
            self.assertIn("daily_halt", audit["blocked_by"])
        self.assertIn("No entries recommended", halted["console"]["entries_note"])

    def test_exits_stay_live_during_halt(self):
        state = entry_ready_state(load_state())
        snap = perfect_candidate(state, day_realized=-130.0)
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

    def test_strict_moonshot_trail_locks_most_of_a_10x(self):
        # entry 0.20, peak +1000% (2.20), STRICT 0.20 give-back -> exit locking ~+800%
        rules = [{"type": "giveback", "arm_gain_pct": 100, "peak_frac": 0.20}]
        r = self._run_pos(rules, entry=0.20, hwm=2.20, mark=1.80, bid=1.79)
        # gave back (2.20-1.80)=0.40 >= 0.20*(2.20-0.20)=0.40 -> exit
        self.assertTrue(self._exits(r))

    def test_barbell_strategy_documented(self):
        b = load_state()["barbell_runner_strategy"]
        self.assertIn("ALWAYS BE REALIZING", b["principle"])
        self.assertIn("scale", b["leg_A_day_lock"].lower())

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


class TestPeakAwareCadenceV411(unittest.TestCase):
    """v4.11: poll cadence tightens as a position extends, so the trail catches fast reversals."""

    def test_cadence_tightens_with_peak(self):
        self.assertEqual(ops.poll_interval_seconds(0), 900)      # baseline 15 min
        self.assertEqual(ops.poll_interval_seconds(10), 900)
        self.assertEqual(ops.poll_interval_seconds(30), 480)     # past ratchet -> 8 min
        self.assertEqual(ops.poll_interval_seconds(120), 180)    # mega-winner -> 3 min
        self.assertEqual(ops.poll_interval_seconds(250), 90)     # +200% tight trail -> ~90s

    def test_extended_flag_pulls_onto_faster_cadence(self):
        self.assertEqual(ops.poll_interval_seconds(10, extended=True), 480)

    def test_monotone_non_increasing(self):
        prev = 10_000
        for pk in (0, 25, 50, 100, 150, 200, 300):
            cur = ops.poll_interval_seconds(pk)
            self.assertLessEqual(cur, prev)
            prev = cur

    def test_green_lock_fully_pruned(self):
        # the legacy rule type is gone from the node branch, reporter routing, and class defaults
        import supertrades.engine.nodes as n
        import supertrades.engine.reporter as rp
        self.assertNotIn('"green_lock"', Path(n.__file__).read_text())
        self.assertNotIn('"green_lock"', Path(rp.__file__).read_text())
        cd = load_state()["class_defaults"]
        self.assertNotIn("green_lock", cd["day_trade"])


class TestAmIndexVwapTrailV44(unittest.TestCase):
    """v4.4: morning-index trend-trailing stop (exit a scalp on a VWAP break)."""

    def _run(self, contract, *, last, vwap, entry=0.60, mark=0.90):
        state = copy.deepcopy(load_state())
        sym = contract.split()[0]
        state["positions"] = {
            "pos-agentic": {"contract": contract, "account": AGENTIC_ACCT,
                            "qty": 1, "entry": entry, "hwm": mark,
                            "ratchet_engaged": False, "class": "0dte_scalp",
                            "expiry": "2026-08-04",
                            "exit_rules": [{"type": "underlying_vwap_stop", "buffer_pct": 0.1}]}}
        state["watchlist"] = []
        snap = synthetic_snapshot(state, et_time="10:15", bp=500.0)
        snap["option_quotes"]["pos-agentic"].update({"mark": mark, "bid": mark - 0.02})
        snap["quotes"].setdefault(sym, {})["last"] = last
        snap["vwap"][sym] = vwap
        return [e for e in run(state, snap)["actions"]["exits"] if e["id"] == "pos-agentic"]

    def test_call_exits_on_vwap_break(self):
        ex = self._run("QQQ 8/4 $724C", last=722.0, vwap=724.0)   # below VWAP -> stop
        self.assertTrue(ex and ex[0]["order"] == "sell_limit_at_bid")
        self.assertIn("underlying_vwap_stop", ex[0]["why"])

    def test_call_holds_above_vwap(self):
        self.assertFalse(self._run("QQQ 8/4 $724C", last=726.0, vwap=724.0))  # trend intact

    def test_put_exits_when_price_reclaims_vwap(self):
        ex = self._run("SPY 8/4 $770P", last=772.0, vwap=770.0)   # above VWAP -> put stop
        self.assertTrue(ex)

    def test_am_index_trail_profile_present(self):
        cd = load_state()["class_defaults"]["0dte_scalp"]
        self.assertEqual(cd["am_index_trail"]["materialize_rule"]["type"],
                         "underlying_vwap_stop")


class TestSizingAndMaterializeV45(unittest.TestCase):
    """v4.5: multi-lot sizing (enable scale-out) + barbell auto-materializer."""

    def test_cheap_contract_sizes_to_max_lots(self):
        # $0.40 contract, $1000 BP: cap 0.22*1000=$220 -> 5 lots capped to max_lots 3
        self.assertEqual(size_order(40.0, 1000.0), 3)

    def test_expensive_contract_sizes_to_one(self):
        # $199 contract on ~$900 BP: cap $198 -> fits 0 within cap? floor gives 0 -> min 1
        self.assertEqual(size_order(199.0, 900.0), 1)
        # a mid contract where 2 fit within the cap
        self.assertEqual(size_order(100.0, 1000.0), 2)   # cap $220 -> 2 lots ($200)

    def test_size_min_one_and_never_breaches_floor(self):
        # small BP: cap 0.22*200=$44 < one $60 lot -> floors to 1, still leaves > bp_floor
        self.assertEqual(size_order(60.0, 200.0), 1)
        self.assertGreaterEqual(200.0 - 60.0, GUARDRAILS["bp_floor_usd"])

    def test_materialize_single_lot_is_runner(self):
        cd = load_state()["class_defaults"]
        rules = materialize_exit_rules("day_trade", 1, cd)
        types = {r["type"] for r in rules}
        self.assertEqual(types, {"progressive_stop", "target", "giveback"})  # stop + runner + trail
        target = next(r for r in rules if r["type"] == "target")
        self.assertTrue(target.get("runner"))
        self.assertNotIn("scale_out_frac", target)

    def test_materialize_multilot_is_barbell(self):
        cd = load_state()["class_defaults"]
        rules = materialize_exit_rules("day_trade", 3, cd)
        target = next(r for r in rules if r["type"] == "target")
        self.assertEqual(target["scale_out_frac"], 0.5)          # leg A: bank half
        gb = next(r for r in rules if r["type"] == "giveback")
        self.assertEqual(gb["peak_frac"], 0.40)                  # loose while developing
        tiers = {t["peak_gte"]: t["frac"] for t in gb["tiers"]}
        self.assertEqual(tiers[200], 0.05)                       # +200% -> near-full lock

    def test_materialize_index_scalp_adds_vwap_trail(self):
        cd = load_state()["class_defaults"]
        rules = materialize_exit_rules("0dte_scalp", 2, cd, is_index=True)
        self.assertTrue(any(r["type"] == "underlying_vwap_stop" for r in rules))

    def test_entry_carries_sizing_and_rules(self):
        state = entry_ready_state(load_state())
        # cheap contract + ample BP -> multi-lot entry with materialized barbell rules
        snap = synthetic_snapshot(
            state, et_time="10:15", bp=1000.0,
            option_overrides={"cand-nvda": {"ask": 0.40, "delta": 0.42,
                                            "spread_pct": 6.0, "oi": 5000, "iv": 0.5}},
            quote_overrides={"NVDA": {"day_pct": 1.8}})
        snap["quotes"]["NVDA"]["last"] = snap["vwap"]["NVDA"] + 1.0
        entry = run(state, snap)["actions"]["entry"]
        self.assertIsNotNone(entry)
        self.assertGreaterEqual(entry["qty"], 2)
        self.assertTrue(any(r.get("scale_out_frac") for r in entry["exit_rules"]))


class TestLiveExecutionBridgeV46(unittest.TestCase):
    """v4.6: shape live Robinhood MCP outputs into the engine snapshot."""

    def test_equity_quotes_computes_day_pct(self):
        results = [{"quote": {"symbol": "INTC", "last_trade_price": "100.57",
                              "adjusted_previous_close": "91.00", "previous_close": "91.00"}}]
        q = live.equity_quotes(results)
        self.assertEqual(q["INTC"]["last"], 100.57)
        self.assertAlmostEqual(q["INTC"]["day_pct"], 10.52, places=1)

    def test_option_quotes_computes_spread_and_parses_greeks(self):
        results = [{"quote": {"instrument_id": "abc", "bid_price": "2.20", "ask_price": "2.32",
                              "adjusted_mark_price": "2.26", "mark_price": "2.26",
                              "delta": "0.46", "gamma": "0.058", "open_interest": "3266",
                              "volume": "5000", "implied_volatility": "1.25"}}]
        oq = live.option_quotes(results)["abc"]
        self.assertEqual(oq["bid"], 2.20)
        self.assertAlmostEqual(oq["spread_pct"], round((2.32 - 2.20) / 2.32 * 100, 1))
        self.assertEqual(oq["delta"], 0.46)
        self.assertEqual(oq["iv"], 1.25)
        self.assertEqual(oq["oi"], 3266)

    def test_bad_fields_do_not_crash(self):
        results = [{"quote": {"instrument_id": "z", "bid_price": None, "ask_price": "",
                              "delta": "n/a"}}]
        oq = live.option_quotes(results)["z"]
        self.assertEqual(oq["bid"], 0.0)
        self.assertIsNone(oq["spread_pct"])   # ask 0 -> no spread
        self.assertIsNone(oq["delta"])

    def test_assemble_pulls_account_from_state_day(self):
        state = load_state()
        state["day"] = {"realized_pnl": 93.0, "auto_entries_used": 1,
                        "manual_entries_today": 2, "manual_round_trips": 3, "halted": False}
        snap = live.assemble_snapshot(state, et_time="10:15", weekday=True, bp=500.0,
                                      equity_results=[], option_results=[])
        self.assertEqual(snap["account"]["bp"], 500.0)
        self.assertEqual(snap["account"]["day_realized"], 93.0)
        self.assertEqual(snap["account"]["auto_entries_used"], 1)
        for k in ("quotes", "option_quotes", "positions", "candidates", "gex", "vwap", "prior"):
            self.assertIn(k, snap)

    def test_assembled_snapshot_drives_a_full_cycle(self):
        # end-to-end: live-shaped data -> assemble -> run_one_cycle produces a valid report
        state = load_state()
        eq = [{"quote": {"symbol": s, "last_trade_price": "100.0",
                         "adjusted_previous_close": "99.0"}}
              for s in state.get("universe", [])]
        vwap = {s: 99.5 for s in state.get("universe", [])}
        snap = live.assemble_snapshot(state, et_time="10:15", weekday=True, bp=500.0,
                                      equity_results=eq, option_results=[], vwap=vwap)
        report = asyncio.run(run_one_cycle(state, snap))
        self.assertEqual(report["meta"]["node_count"], expected_node_count(state))
        self.assertIn("kpis", report["console"])
        self.assertEqual(report["console"]["kpis"]["buying_power"], 500.0)


class TestEvolutionV47(unittest.TestCase):
    """v4.7: the self-tuning loop — recompute performance + surface safe improvements."""

    LEDGER = [
        {"contract": "RIVN 7/24 $19C", "pnl_usd": -4, "pct": -6, "result": "loss"},
        {"contract": "QQQ 7/21 $713C", "pnl_usd": -4, "pct": -6, "result": "loss"},
        {"contract": "DIS 8/21 $110C", "pnl_usd": -27, "pct": -42, "result": "loss",
         "note": "stop slipped past -30%"},
        {"contract": "NVDA 7/31 $220C", "pnl_usd": -56, "pct": -55, "result": "loss",
         "note": "stop slipped past -30%"},
        {"contract": "SPY 8/4 $771C", "pnl_usd": 48, "pct": 64, "peak_pct": 70, "result": "win"},
        {"contract": "QQQ 8/4 $724C", "pnl_usd": 36, "pct": 56, "peak_pct": 123, "result": "win"},
        {"contract": "INTC 8/5 $102C", "pnl_usd": 9, "pct": 4.5, "peak_pct": 18, "result": "win",
         "note": "cut early by a competing session's hard-exit"},
    ]

    def test_recompute_performance_from_ledger(self):
        p = evolution.recompute_performance(self.LEDGER)
        self.assertEqual(p["trades_closed"], 7)
        self.assertEqual((p["wins"], p["losses"]), (3, 4))
        self.assertEqual(p["win_rate"], 0.43)
        self.assertEqual(p["gross_pnl_usd"], 2)
        self.assertEqual(p["avg_win_usd"], 31.0)
        self.assertEqual(p["avg_loss_usd"], -22.75)
        self.assertAlmostEqual(p["expectancy_per_trade_usd"], 0.29, places=2)

    def test_recompute_ignores_open_and_empty(self):
        self.assertEqual(evolution.recompute_performance([])["trades_closed"], 0)
        mixed = self.LEDGER + [{"contract": "OPEN", "pnl_usd": None}]
        self.assertEqual(evolution.recompute_performance(mixed)["trades_closed"], 7)

    def test_reflect_surfaces_the_real_lessons(self):
        sugg = evolution.reflect({"trades": self.LEDGER})
        areas = {s["area"] for s in sugg}
        self.assertIn("loss_control", areas)   # DIS -42, NVDA -55 past the stop
        self.assertIn("give_back", areas)      # QQQ +123% -> +56%
        self.assertIn("execution", areas)      # INTC competing-trigger exit
        # risk-tightening suggestions are auto-safe; win-rate/sizing is not
        loss = next(s for s in sugg if s["area"] == "loss_control")
        self.assertTrue(loss["auto_safe"])
        wr = next((s for s in sugg if s["area"] == "win_rate"), None)
        self.assertTrue(wr is None or wr["auto_safe"] is False)

    def test_max_drawdown_walks_the_equity_curve(self):
        # losses first (-4,-4,-27,-56) sink equity to -91 before the wins recover it
        self.assertEqual(evolution.max_drawdown_usd(self.LEDGER), -91.0)
        # a book that only climbs has zero drawdown
        self.assertEqual(evolution.max_drawdown_usd(
            [{"pnl_usd": 10}, {"pnl_usd": 20}]), 0.0)

    def test_objective_weights_win_rate_success_and_penalizes_dd(self):
        perf = evolution.recompute_performance(self.LEDGER)
        mdd = evolution.max_drawdown_usd(self.LEDGER)
        score = evolution.score_objective(perf, mdd)
        # 0.45*43 + 0.30*0.29 - 0.25*91 = 19.35 + 0.087 - 22.75 ~= -3.31
        self.assertAlmostEqual(score, -3.31, places=1)
        # same win rate + expectancy but a shallower drawdown MUST score higher
        better = evolution.score_objective(perf, -20.0)
        self.assertGreater(better, score)
        # and lifting win rate (nothing else changed) MUST score higher
        lifted = evolution.score_objective({**perf, "win_rate": 0.70}, mdd)
        self.assertGreater(lifted, score)

    def test_reflect_clean_book_is_quiet(self):
        clean = [{"contract": "A", "pnl_usd": 50, "pct": 55, "peak_pct": 60, "result": "win"},
                 {"contract": "B", "pnl_usd": 40, "pct": 50, "peak_pct": 52, "result": "win"}]
        self.assertEqual(evolution.reflect({"trades": clean}), [])

    def test_performance_block_matches_recompute(self):
        # state.performance is kept consistent with the ledger via recompute
        state = load_state()
        if state.get("trades"):
            p = evolution.recompute_performance(state["trades"])
            self.assertEqual(state["performance"]["win_rate"], p["win_rate"])
            self.assertEqual(state["performance"]["trades_closed"], p["trades_closed"])


class TestProgressiveStopV48(unittest.TestCase):
    """v4.8: one ratcheting-stop equation — tight when small-green, loose for big runners."""

    def test_equation_curve(self):
        from supertrades.engine.nodes import progressive_stop_pct as ps
        self.assertEqual(ps(0), -30.0)            # not green -> initial stop
        self.assertEqual(ps(-5), -30.0)           # red -> initial stop
        self.assertAlmostEqual(ps(5), 0.0, places=1)     # breakeven by ~+5% (the "significant move")
        self.assertGreater(ps(20), 0)             # locks green past +20%
        self.assertGreater(ps(100), ps(20))       # monotone up with the peak
        # big runners get looser room (lock a smaller *fraction* than small greens)... but always higher $
        self.assertGreater(ps(200), 100)

    def _run(self, entry, hwm, mark, bid):
        state = copy.deepcopy(load_state())
        state["positions"] = {"p": {"contract": "INTC 8/5 $102C", "account": AGENTIC_ACCT,
                                    "qty": 1, "entry": entry, "hwm": hwm, "ratchet_engaged": False,
                                    "class": "day_trade", "expiry": "2026-08-05",
                                    "exit_rules": [{"type": "progressive_stop"}]}}
        state["watchlist"] = []
        snap = synthetic_snapshot(state, et_time="10:15", bp=500.0)
        snap["option_quotes"]["p"].update({"mark": mark, "bid": bid})
        return [e for e in run(state, snap)["actions"]["exits"] if e["id"] == "p"]

    def test_small_green_that_reverses_exits_near_breakeven_not_at_minus30(self):
        # peaked +5% (2.09), fell back to breakeven-ish -> progressive stop fires (was -30% before)
        ex = self._run(1.99, 2.09, 1.98, 1.97)
        self.assertTrue(ex and ex[0]["order"] == "sell_limit_at_bid")
        self.assertIn("progressive_stop", ex[0]["why"])

    def test_still_green_and_climbing_holds(self):
        # peaked +18%, only pulled to +12% -> above the ratcheted stop, keep holding
        self.assertFalse(self._run(1.99, 2.35, 2.23, 2.21))

    def test_materialized_ladder_is_lean(self):
        cd = load_state()["class_defaults"]
        self.assertEqual({r["type"] for r in materialize_exit_rules("day_trade", 1, cd)},
                         {"progressive_stop", "target", "giveback"})


class TestGreeksIvRvolV49(unittest.TestCase):
    """v4.9: greek/IV expected-move exits + RVOL-weighted conviction ranking."""

    def test_expected_move_scales_with_iv(self):
        from supertrades.engine.nodes import expected_move_exits as em
        lo = em(entry=0.60, iv=0.20, delta=0.45, gamma=0.03, spot=100, dte=1)
        hi = em(entry=0.60, iv=1.20, delta=0.45, gamma=0.03, spot=100, dte=1)
        # a higher-IV name has a wider expected move -> a wider (further) target
        self.assertGreater(hi["target_pct"], lo["target_pct"])
        # target is a reachable positive %, stop is negative and bounded
        self.assertGreaterEqual(lo["target_pct"], 15.0)
        self.assertLessEqual(hi["target_pct"], 250.0)
        self.assertTrue(-55.0 <= hi["stop_pct"] <= -8.0)

    def test_expected_move_falls_back_without_greeks(self):
        from supertrades.engine.nodes import expected_move_exits as em
        r = em(entry=0.60, iv=0.0, delta=0.0, spot=0, dte=1)
        self.assertEqual((r["target_pct"], r["stop_pct"]), (50.0, -30.0))

    def test_conviction_rewards_delta_rvol_momentum(self):
        from supertrades.engine.reporter import conviction_score
        strong = conviction_score({"delta": 0.55, "rvol": 3.0, "underlying_day_pct": 4.0,
                                    "above_vwap": True, "iv": 0.5})
        weak = conviction_score({"delta": 0.36, "rvol": 0.8, "underlying_day_pct": 0.2,
                                 "above_vwap": False, "iv": 1.4})
        self.assertGreater(strong, weak)
        # RVOL alone moves the needle: same everything, higher volume scores higher
        base = {"delta": 0.45, "underlying_day_pct": 2.0, "above_vwap": True, "iv": 0.5}
        self.assertGreater(conviction_score({**base, "rvol": 3.0}),
                           conviction_score({**base, "rvol": 1.0}))

    def test_entry_carries_conviction_and_em_exits(self):
        state = entry_ready_state(load_state())
        snap = synthetic_snapshot(
            state, et_time="10:15", bp=1000.0,
            option_overrides={"cand-nvda": {"ask": 0.60, "delta": 0.42, "gamma": 0.03,
                                            "spread_pct": 6.0, "oi": 5000, "iv": 0.55}},
            quote_overrides={"NVDA": {"day_pct": 1.8, "rvol": 2.5}})
        snap["quotes"]["NVDA"]["last"] = snap["vwap"]["NVDA"] + 1.0
        entry = run(state, snap)["actions"]["entry"]
        self.assertIsNotNone(entry)
        self.assertIn("conviction", entry)
        self.assertIn("expected_move", entry)
        # the materialized stop uses the EM-derived level, not a flat -30
        ps = next(r for r in entry["exit_rules"] if r["type"] == "progressive_stop")
        self.assertEqual(ps["initial_pct"], entry["expected_move"]["stop_pct"])


class TestTieredTrailV410(unittest.TestCase):
    """v4.10: the runner trail TIGHTENS at extreme gains (loose early, near-full lock >200%)."""

    TRAIL = {"type": "giveback", "arm_gain_pct": 50, "peak_frac": 0.40,
             "tiers": [{"peak_gte": 100, "frac": 0.20}, {"peak_gte": 200, "frac": 0.05}]}

    def _exits(self, entry, hwm, mark, bid):
        state = copy.deepcopy(load_state())
        state["positions"] = {"p": {"contract": "QQQ 8/4 $724C", "account": AGENTIC_ACCT,
                                    "qty": 1, "entry": entry, "hwm": hwm, "ratchet_engaged": False,
                                    "class": "0dte_scalp", "expiry": "2026-08-04",
                                    "exit_rules": [self.TRAIL]}}
        state["watchlist"] = []
        snap = synthetic_snapshot(state, et_time="10:15", bp=500.0)
        snap["option_quotes"]["p"].update({"mark": mark, "bid": bid})
        return [e for e in run(state, snap)["actions"]["exits"] if e["id"] == "p"]

    def test_developing_runner_gets_room(self):
        # entry 1.00, peak +80% (1.80), pulled to +50% (1.50): gave back 0.30 of a 0.80 peak
        # = 37.5% < 40% base frac -> HOLD, let it run
        self.assertFalse(self._exits(1.00, 1.80, 1.50, 1.49))

    def test_mega_winner_locks_tight(self):
        # entry 1.00, peak +300% (4.00), slips to +270% (3.70): gave back 0.30 of a 3.00 peak
        # = 10% > the 5% frac at the +200% tier -> EXIT, locking ~all of the huge gain
        ex = self._exits(1.00, 4.00, 3.70, 3.68)
        self.assertTrue(ex and ex[0]["order"] == "sell_limit_at_bid")

    def test_mid_tier_tightens_vs_base(self):
        # peak +120% (2.20), pulled to +90% (1.90): gave back 0.30 of 1.20 = 25% > 20% (+100 tier)
        # -> exits, where the loose 40% base would still be holding
        self.assertTrue(self._exits(1.00, 2.20, 1.90, 1.89))


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


class TestExecutionAccuracyV413(unittest.TestCase):
    """v4.13: resting bracket exits, objective breakout RVOL gate, at-level cadence."""

    def test_barbell_scale_out_is_a_resting_bracket(self):
        # the scale-out leg rests as a GTC limit AT the target from the moment of fill,
        # so the lock-the-day exit can't be missed between polls (QQQ 8/4 lesson)
        from supertrades.engine.reporter import materialize_exit_rules
        rules = materialize_exit_rules("day_trade", 2, {}, target_pct=40, stop_pct=-25)
        tgt = next(r for r in rules if r["type"] == "target")
        self.assertTrue(tgt.get("resting_bracket"))
        self.assertEqual(tgt["scale_out_frac"], 0.5)
        # single-lot runner does NOT rest a cap — the runner rides the trail
        solo = materialize_exit_rules("day_trade", 1, {}, target_pct=40, stop_pct=-25)
        stgt = next(r for r in solo if r["type"] == "target")
        self.assertFalse(stgt.get("resting_bracket", False))
        self.assertTrue(stgt.get("runner"))

    def test_breakout_needs_objective_rvol(self):
        # a level-break only confirms with real participation; a quiet creep or
        # UNKNOWN volume does not (the 8/5 NVDA 221.7 slow-creep fakeout)
        from supertrades.engine.reporter import breakout_confirmed, GUARDRAILS
        self.assertTrue(breakout_confirmed(GUARDRAILS["breakout_rvol_min"]))
        self.assertTrue(breakout_confirmed(3.0))
        self.assertFalse(breakout_confirmed(1.1))
        self.assertFalse(breakout_confirmed(None))

    def test_rvol_now_is_time_of_day_relative(self):
        from supertrades.engine.live import rvol_now
        # half the day elapsed, half the average volume traded -> exactly 1.0x
        self.assertEqual(rvol_now(500_000, 1_000_000, 0.5), 1.0)
        # same cumulative volume EARLY in the day = much hotter tape
        self.assertGreater(rvol_now(500_000, 1_000_000, 0.1), 1.0)
        # missing inputs -> None (unknown must not confirm a breakout)
        self.assertIsNone(rvol_now(None, 1_000_000, 0.5))
        self.assertIsNone(rvol_now(500_000, 0, 0.5))

    def test_at_level_cadence_is_tight_even_when_flat(self):
        from supertrades.engine import ops
        # flat at an armed level -> 90s; the SPY 770 reclaim resolved between 12-min polls
        self.assertEqual(ops.poll_interval_seconds(0, at_level=True), 90)
        self.assertEqual(ops.poll_interval_seconds(30, at_level=True), 90)
        # away from any level, the ladder is unchanged
        self.assertEqual(ops.poll_interval_seconds(0), 900)
        self.assertEqual(ops.poll_interval_seconds(30), 480)


class TestUniverseFunnelV414(unittest.TestCase):
    """v4.14: universe funnel (screen wide, execute narrow) + unusual-flow confirmation."""

    def test_funnel_shapes_flexible_scanner_rows(self):
        # three key dialects: canonical, terse, volume-pair (rvol derived via rvol_now)
        rows = [
            {"symbol": "intc", "last_trade_price": "100.57", "percent_change": "2.4",
             "volume": "40000000", "avg_volume": "80000000"},          # 0.5 frac -> rvol 1.0
            {"sym": "AMD", "price": 180.0, "day_pct": 1.2, "rvol": 2.1},
            {"quote": {"ticker": "NVDA", "last": "220.5", "change_pct": "3.1"}},
            {"price": 50.0},                                            # no symbol -> dropped
            {"symbol": "ZERO", "last": 0},                              # no price -> dropped
        ]
        cands = live.funnel_candidates(rows, quotes_meta={"frac_of_day": 0.5})
        self.assertEqual([c["sym"] for c in cands], ["INTC", "AMD", "NVDA"])
        intc = cands[0]
        self.assertEqual(intc["last"], 100.57)
        self.assertEqual(intc["day_pct"], 2.4)
        self.assertEqual(intc["rvol"], 1.0)          # 40M vs 80M*0.5 elapsed
        self.assertEqual(cands[1]["rvol"], 2.1)      # direct rvol passes through
        self.assertIsNone(cands[2]["rvol"])          # no volume data -> unknown, not invented

    def test_funnel_filter_drops_untradable_keeps_clean_mover(self):
        g = GUARDRAILS
        mk = lambda sym, last, rvol, day, mcap=20e9: {"sym": sym, "last": last,
                                                     "rvol": rvol, "day_pct": day,
                                                     "market_cap": mcap}
        cands = [
            mk("PENNY", 3.50, 2.0, 2.0),     # under $5 -> junk options
            mk("RICH", 1500.0, 2.0, 2.0),    # over $1000 -> can't fit per-setup budget
            mk("DEAD", 120.0, 0.8, 2.0),     # rvol below funnel floor
            mk("NOVOL", 120.0, None, 2.0),   # unknown rvol never passes the sieve
            mk("GAPPED", 120.0, 2.0, 9.5),   # |day %| > gap-trap rail
            mk("MEME", 12.0, 4.5, 0.3, mcap=1e9),   # v4.14.1: sub-$5B anomaly (the 8/5 BLMN case)
            mk("NOCAP", 40.0, 3.0, 1.0, mcap=None), # v4.14.1: unknown cap = unrecognized, drop
            mk("CLEAN", 120.0, 2.0, 2.5),    # the mover the funnel exists to find
        ]
        kept = live.funnel_filter(cands, bp=500.0, per_setup_usd=110.0, guardrails=g)
        self.assertEqual([c["sym"] for c in kept], ["CLEAN"])
        # per-setup budget beyond BP -> nothing is fundable, funnel yields nothing
        self.assertEqual(live.funnel_filter(cands, 90.0, 110.0, g), [])
        # thresholds live ONLY in GUARDRAILS
        self.assertEqual(g["funnel_min_underlying_usd"], 5.0)
        self.assertEqual(g["funnel_max_underlying_usd"], 1000.0)
        self.assertEqual(g["funnel_rvol_min"], 1.2)
        self.assertEqual(g["funnel_day_pct_max_abs"], 8.0)
        self.assertEqual(g["funnel_min_market_cap_usd"], 5e9)

    def test_rh_scan_rows_normalizes_fraction_pct(self):
        # the 8/5 proven miss: scanner '% Change' is a FRACTION — SHOP's +19.9%
        # earnings rip read as +0.2% and the sweep said 'no movers'
        rows = [{"ticker": "SHOP", "instrument_type": "EQUITY",
                 "columns": {"Last": "147.88", "% Change": "0.19935",
                             "Relative volume": "1.51", "Market cap": 1.6e11}},
                {"ticker": "XIDX", "instrument_type": "INDEX", "columns": {}}]
        shaped = live.rh_scan_rows(rows)
        self.assertEqual(len(shaped), 1)                  # non-equity dropped
        self.assertAlmostEqual(shaped[0]["day_pct"], 19.935, places=3)
        cands = live.funnel_candidates(shaped)
        self.assertAlmostEqual(cands[0]["day_pct"], 19.935, places=3)
        # +19.9% now correctly trips the gap-trap rail instead of hiding at 0.2%
        kept = live.funnel_filter(cands, bp=500.0, per_setup_usd=110.0,
                                  guardrails=GUARDRAILS)
        self.assertEqual(kept, [])

    def test_funnel_candidates_carry_market_cap(self):
        rows = [{"symbol": "NVDA", "last": 220.0, "market_cap": "5.45e12"},
                {"symbol": "SHOP", "last": 147.9, "Market cap": 1.6e11},
                {"symbol": "TINY", "last": 12.0}]
        cands = live.funnel_candidates(rows)
        self.assertEqual(cands[0]["market_cap"], 5.45e12)
        self.assertEqual(cands[1]["market_cap"], 1.6e11)   # scanner-column dialect
        self.assertIsNone(cands[2]["market_cap"])          # unknown stays None (filter drops it)

    def test_funnel_rank_returns_top_n_by_conviction(self):
        cands = [{"sym": "MEH", "last": 50.0, "rvol": 1.3, "day_pct": 0.5},
                 {"sym": "HOT", "last": 120.0, "rvol": 3.0, "day_pct": 4.0},
                 {"sym": "WARM", "last": 80.0, "rvol": 2.0, "day_pct": 2.0}]
        top2 = live.funnel_rank(cands, top_n=2)
        self.assertEqual([c["sym"] for c in top2], ["HOT", "WARM"])
        for c in top2:                                   # score rides along for the console
            self.assertIn("conviction", c)
        self.assertGreater(top2[0]["conviction"], top2[1]["conviction"])
        # top_n wider than the field just returns everyone, still sorted
        self.assertEqual(len(live.funnel_rank(cands, top_n=10)), 3)

    def test_unusual_flow_needs_3x_oi_and_known_inputs(self):
        from supertrades.engine.reporter import unusual_flow
        self.assertTrue(unusual_flow(3000, 1000))        # exactly 3x confirms
        self.assertTrue(unusual_flow(9000, 1000))
        self.assertFalse(unusual_flow(2000, 1000))       # 2x = active, not unusual
        self.assertFalse(unusual_flow(None, 1000))       # unknown never confirms
        self.assertFalse(unusual_flow(3000, None))
        self.assertFalse(unusual_flow(0, 0))
        self.assertEqual(GUARDRAILS["flow_vol_oi_min"], 3.0)

    def test_conviction_flow_bonus_is_small_and_additive(self):
        from supertrades.engine.reporter import conviction_score
        base = {"delta": 0.42, "rvol": 2.0, "underlying_day_pct": 2.0,
                "above_vwap": True, "iv": 0.5}
        plain = conviction_score(base)
        flagged = conviction_score({**base, "flow_unusual": True})
        self.assertAlmostEqual(flagged - plain, 0.05, places=3)   # exactly the small bonus
        # confirmation, never a solo trigger: flow alone barely moves a weak candidate
        weak = {"delta": 0.2, "rvol": 0.8, "underlying_day_pct": -1.0,
                "above_vwap": False, "iv": 1.5}
        self.assertLess(conviction_score({**weak, "flow_unusual": True}),
                        conviction_score(base))
        # explicit False / absent are identical (no penalty either way)
        self.assertEqual(conviction_score({**base, "flow_unusual": False}), plain)


if __name__ == "__main__":
    unittest.main()
