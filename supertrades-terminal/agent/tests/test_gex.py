"""Tests for the dealer-GEX engine. Synthetic chains with known structure pin
the flip / walls / king-node math and the entry-confirmation gate."""

from __future__ import annotations

import unittest

from agent.gex import StrikeGex, compute_gex, gex_confirms


def chain():
    # puts stacked low (95), calls stacked high (105) -> put wall 95, call wall
    # 105; 105 made dominant so it is also the king node. 100 has unusual call
    # volume (vol/oi = 4).
    return [
        StrikeGex(95, call_gamma=0.01, call_oi=100, put_gamma=0.05, put_oi=1000),
        StrikeGex(100, call_gamma=0.05, call_oi=500, put_gamma=0.05, put_oi=500,
                  call_vol=2000, put_vol=100),
        StrikeGex(105, call_gamma=0.05, call_oi=1200, put_gamma=0.01, put_oi=100),
    ]


class GexMath(unittest.TestCase):
    def setUp(self):
        self.p = compute_gex(chain(), spot=100.0)

    def test_walls(self):
        self.assertEqual(self.p.call_wall, 105)   # strongest positive GEX
        self.assertEqual(self.p.put_wall, 95)      # strongest negative GEX

    def test_king_node_is_dominant_strike(self):
        self.assertEqual(self.p.king_node, 105)

    def test_flip_between_crossing_strikes(self):
        # cumulative GEX crosses zero between 100 and 105
        self.assertTrue(100 <= self.p.flip <= 105)

    def test_regime_from_spot_vs_flip(self):
        # spot 100 sits below the flip -> negative-gamma regime
        self.assertEqual(self.p.regime, "negative")
        self.assertTrue(self.p.negative_gamma)

    def test_unusual_activity_flagged(self):
        flagged = {(s, side) for s, side, _ in self.p.unusual}
        self.assertIn((100, "call"), flagged)      # vol/oi = 4 >= 2.0

    def test_empty_chain_raises(self):
        with self.assertRaises(ValueError):
            compute_gex([], spot=100.0)


class GexGate(unittest.TestCase):
    def test_long_confirmed_in_neg_gamma_below_call_wall(self):
        p = compute_gex(chain(), spot=100.0)   # negative regime, spot < call wall
        ok, _ = gex_confirms(p, "long")
        self.assertTrue(ok)

    def test_short_confirmed_in_neg_gamma_above_put_wall(self):
        p = compute_gex(chain(), spot=100.0)
        ok, _ = gex_confirms(p, "short")
        self.assertTrue(ok)

    def test_unknown_direction_rejected(self):
        p = compute_gex(chain(), spot=100.0)
        ok, _ = gex_confirms(p, "sideways")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
