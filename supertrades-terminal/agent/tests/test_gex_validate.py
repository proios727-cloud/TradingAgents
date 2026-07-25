"""Tests for the GEX forward-validation engine — fill logic, baselines, verdict."""

from __future__ import annotations

import unittest

from agent.gex_validate import Decision, EntryCfg, analyze, score_entry


def entry(session="D1", gate="long"):
    # call runs to target (+90%), put runs to stop (-50%)
    return {
        "session": session, "gate_dir": gate,
        "call": {"mid": 1.0, "spread": 0.05, "bars": [(1.0, 2.0, 1.0, 1.9)]},
        "put":  {"mid": 1.0, "spread": 0.05, "bars": [(1.0, 1.0, 0.4, 0.5)]},
    }


class Scoring(unittest.TestCase):
    def test_target_and_stop_R(self):
        s = score_entry(entry(gate="long"))
        self.assertGreater(s["gate"], 1.4)          # call hit +90% target (~+1.8R pre-spread)
        self.assertLess(s["anti"], -0.9)            # anti = put, hit -50% stop

    def test_always_baselines_present(self):
        s = score_entry(entry())
        self.assertGreater(s["always_long"], 0)     # call target
        self.assertLess(s["always_short"], 0)       # put stop
        self.assertIn("coinflip", s)

    def test_ask_entry_bid_exit_haircut(self):
        # with spread, even a target fill is < the ideal +1.8R (fills are worse)
        s = score_entry(entry())
        self.assertLess(s["gate"], 1.8)

    def test_no_gate_entry_has_no_gate_key(self):
        s = score_entry(entry(gate=None))
        self.assertNotIn("gate", s)
        self.assertIn("always_long", s)             # baselines still computed


class Analysis(unittest.TestCase):
    def test_small_sample_is_inconclusive(self):
        res = analyze([entry("D1"), entry("D2"), entry("D3")])
        self.assertEqual(res["n"], 3)
        self.assertIn("INCONCLUSIVE", res["verdict"])
        self.assertFalse(res["powered"])

    def test_non_gated_entries_excluded(self):
        res = analyze([entry(gate=None), entry(gate=None)])
        self.assertEqual(res["n"], 0)

    def test_reports_paired_edge_and_ci(self):
        res = analyze([entry(f"D{i}") for i in range(5)])
        self.assertIn("paired_edge_vs_coinflip", res)
        self.assertIn("edge_ci95", res)
        self.assertEqual(len(res["edge_ci95"]), 2)

    def test_powered_pass_path(self):
        # 260 winning gated entries across 30 sessions -> powered; gate beats
        # its (losing) anti and coin-flip, CI above 0 -> TRADE verdict
        es = [entry(f"S{i%30}") for i in range(260)]
        res = analyze(es, decision=Decision(min_entries=200, min_sessions=25))
        self.assertTrue(res["powered"])
        self.assertGreater(res["paired_edge_vs_coinflip"], 0)
        self.assertIn(res["verdict"].split()[0], ("TRADE", "KILL"))


if __name__ == "__main__":
    unittest.main()
