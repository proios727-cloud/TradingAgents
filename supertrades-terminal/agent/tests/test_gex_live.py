"""Tests for the GEX live renderer / snapshot."""

from __future__ import annotations

import unittest

from agent.gex import StrikeGex
from agent.gex_live import render


def rows():
    return [
        StrikeGex(738, 0.15, 5000, 0.15, 8000, 40000, 480000),
        StrikeGex(739, 0.16, 6000, 0.16, 5000, 250000, 490000),
        StrikeGex(740, 0.15, 12000, 0.15, 22000, 420000, 550000),
        StrikeGex(742, 0.06, 13000, 0.05, 5000, 530000, 370000),
    ]


class Render(unittest.TestCase):
    def test_snapshot_has_expected_fields(self):
        out, snap = render("SPY", 739.6, rows())
        for k in ("symbol", "spot", "net_gex_b", "regime", "flip",
                  "call_wall", "put_wall", "king_node", "skew",
                  "long_gate", "short_gate"):
            self.assertIn(k, snap)
        self.assertEqual(snap["symbol"], "SPY")
        self.assertIn(snap["regime"], ("positive", "negative"))
        self.assertIsInstance(snap["long_gate"], bool)

    def test_render_text_mentions_flip_and_gates(self):
        out, _ = render("SPY", 739.6, rows())
        self.assertIn("gamma flip", out)
        self.assertIn("gate long", out)
        self.assertIn("gate short", out)


if __name__ == "__main__":
    unittest.main()
