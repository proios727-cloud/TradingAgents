"""Tests for the real-data 0DTE replay backtest.

Synthetic cases pin the fill logic (stop/target, next-bar entry, no lookahead);
the fixture case pins the engine to the REAL Robinhood premium data captured on
2026-07-24, so the honest result can't silently drift. Pure stdlib.
"""

from __future__ import annotations

import json
import os
import unittest

from agent.replay_backtest import BtConfig, run

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "spy_0dte_2026-07-24.json")

# A minimal underlying that fires a LONG at bar 2 (VWAP reclaim on high volume).
U_LONG = [
    (100, 100, 100, 100, 100),
    (99, 99, 99, 99, 100),
    (101, 101, 101, 101, 300),   # close 101 > vwap, rvol 3x -> long signal
    (101, 101, 101, 101, 100),   # entry fills on the option's open here
    (101, 101, 101, 101, 100),
]
FLAT = [(1, 1, 1, 1)] * 5        # put side: never triggers


class FillLogic(unittest.TestCase):
    def test_long_hits_target(self):
        call = [(1, 1, 1, 1)] * 3 + [(1.00, 1.00, 1.00, 1.00), (1.0, 2.0, 1.0, 1.9)]
        res = run(U_LONG, call, FLAT)
        self.assertEqual(res["count"], 1)
        t = res["trades"][0]
        self.assertEqual(t["side"], "LONG")
        self.assertEqual(t["entry"], 1.00)          # NEXT-bar open, not signal bar
        self.assertEqual(t["exit"], 1.90)           # +90% target
        self.assertAlmostEqual(t["r"], 1.8, places=2)

    def test_long_hits_stop(self):
        call = [(1, 1, 1, 1)] * 3 + [(1.00, 1.00, 1.00, 1.00), (1.0, 1.0, 0.4, 0.5)]
        res = run(U_LONG, call, FLAT)
        self.assertEqual(res["trades"][0]["reason"], "stop -50%")
        self.assertAlmostEqual(res["trades"][0]["r"], -1.0, places=2)

    def test_stop_wins_when_both_hit(self):
        # a bar that spans both stop and target -> stop is taken (conservative)
        call = [(1, 1, 1, 1)] * 3 + [(1.00, 1.00, 1.00, 1.00), (1.0, 2.0, 0.4, 1.0)]
        res = run(U_LONG, call, FLAT)
        self.assertEqual(res["trades"][0]["reason"], "stop -50%")

    def test_no_signal_no_trade(self):
        flat_u = [(100, 100, 100, 100, 100)] * 5
        self.assertEqual(run(flat_u, FLAT, FLAT)["count"], 0)

    def test_custom_thresholds(self):
        # tighter target (+50%) fills earlier
        call = [(1, 1, 1, 1)] * 3 + [(1.00, 1.00, 1.00, 1.00), (1.0, 1.6, 1.0, 1.5)]
        res = run(U_LONG, call, FLAT, BtConfig(target_pct=1.5))
        self.assertEqual(res["trades"][0]["exit"], 1.5)


class RealFixture(unittest.TestCase):
    def test_matches_captured_real_data(self):
        with open(FIXTURE, encoding="utf-8") as f:
            d = json.load(f)
        res = run([tuple(b) for b in d["underlying"]],
                  [tuple(b) for b in d["call"]],
                  [tuple(b) for b in d["put"]])
        # The real session produced exactly one signal: a short that stopped out.
        self.assertEqual(res["count"], 1)
        t = res["trades"][0]
        self.assertEqual(t["side"], "SHORT")
        self.assertEqual(t["reason"], "stop -50%")
        self.assertAlmostEqual(t["r"], -1.0, places=2)


if __name__ == "__main__":
    unittest.main()
