"""Tests for the enriched snapshot builder and the post-session scorer."""

from __future__ import annotations

import unittest

from agent.gex import StrikeGex
from agent.gex_live import build_snapshot
from agent.gex_score import score_log, to_entry


def chain():
    return [
        StrikeGex(738, 0.15, 5000, 0.15, 9000, 40000, 90000),
        StrikeGex(740, 0.15, 10000, 0.15, 20000, 400000, 550000),
        StrikeGex(743, 0.06, 12000, 0.05, 4000, 530000, 370000),
    ]


CALL = {"option_id": "C1", "strike": 741, "expiry": "2026-07-24",
        "delta": 0.5, "bid": 1.00, "ask": 1.10}
PUT = {"option_id": "P1", "strike": 741, "expiry": "2026-07-24",
       "delta": -0.5, "bid": 1.20, "ask": 1.30}


class Enrichment(unittest.TestCase):
    def test_snapshot_is_scorable(self):
        s = build_snapshot("SPY", 741.0, chain(), CALL, PUT)
        # both contracts captured with the fields the scorer needs
        self.assertEqual(s["call"]["option_id"], "C1")
        self.assertEqual(s["put"]["option_id"], "P1")
        self.assertAlmostEqual(s["call"]["mid"], 1.05, places=2)
        self.assertAlmostEqual(s["call"]["spread_pct"], 0.0952, places=3)
        self.assertIn(s["gate_dir"], ("long", "short", None))
        self.assertTrue(s["config_hash"])
        self.assertIn("dist_to_flip", s)

    def test_gate_dir_is_xor(self):
        s = build_snapshot("SPY", 741.0, chain(), CALL, PUT)
        both = s["long_gate"] and s["short_gate"]
        neither = not s["long_gate"] and not s["short_gate"]
        if both or neither:
            self.assertIsNone(s["gate_dir"])


class Scoring(unittest.TestCase):
    def _snap(self, gate="long", oc="C1", op="P1"):
        return {"session": "D1", "gate_dir": gate,
                "call": {"option_id": oc, "mid": 1.0, "spread_pct": 0.05},
                "put": {"option_id": op, "mid": 1.0, "spread_pct": 0.05}}

    def test_to_entry_maps_fields(self):
        e = to_entry(self._snap(), [(1, 2, 1, 1.9)], [(1, 1, 0.4, 0.5)])
        self.assertEqual(e["gate_dir"], "long")
        self.assertEqual(e["call"]["bars"], [(1, 2, 1, 1.9)])

    def test_score_log_counts_gated(self):
        bars = {"C1": [[1, 2, 1, 1.9]], "P1": [[1, 1, 0.4, 0.5]]}
        res = score_log([self._snap()], bars)
        self.assertEqual(res["n"], 1)
        self.assertEqual(res["skipped_unscorable"], 0)
        self.assertIn("INCONCLUSIVE", res["verdict"])

    def test_missing_bars_skipped(self):
        res = score_log([self._snap(oc="NOPE")], {"P1": [[1, 1, 1, 1]]})
        self.assertEqual(res["skipped_unscorable"], 1)
        self.assertEqual(res["n"], 0)


if __name__ == "__main__":
    unittest.main()
