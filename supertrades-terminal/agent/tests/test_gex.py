"""Tests for the dealer-GEX engine. Synthetic chains with known structure pin
the flip / walls / king-node math and the entry-confirmation gate."""

from __future__ import annotations

import unittest

from agent.gex import GexProfile, StrikeGex, compute_gex, gex_confirms


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

    def test_regime_from_net_gex_sign(self):
        # this chain nets POSITIVE GEX (call side dominates), so regime is
        # positive regardless of spot's position vs the flip
        self.assertGreater(self.p.net_gex, 0)
        self.assertEqual(self.p.regime, "positive")
        self.assertFalse(self.p.negative_gamma)

    def test_unusual_activity_flagged(self):
        flagged = {(s, side) for s, side, _ in self.p.unusual}
        self.assertIn((100, "call"), flagged)      # vol/oi = 4 >= 2.0

    def test_empty_chain_raises(self):
        with self.assertRaises(ValueError):
            compute_gex([], spot=100.0)


def prof(spot, flip, regime, unusual=()):
    net = -1e9 if regime == "negative" else 1e9
    return GexProfile(spot=spot, net_gex=net, flip=flip, call_wall=flip + 3,
                      put_wall=flip - 3, king_node=flip, regime=regime,
                      unusual=list(unusual))


class GexGate(unittest.TestCase):
    def test_at_flip_is_no_trade_both_ways(self):
        # the real SPY/QQQ case today: spot within the flip band -> neither side
        p = prof(739.6, 740, "negative")   # |diff| 0.4 < 0.15% of 740 (~1.11)
        self.assertFalse(gex_confirms(p, "long")[0])
        self.assertFalse(gex_confirms(p, "short")[0])
        self.assertIn("at the flip", gex_confirms(p, "long")[1])

    def test_long_below_flip_must_reclaim_first(self):
        ok, why = gex_confirms(prof(737, 740, "negative"), "long")  # clearly below
        self.assertFalse(ok)
        self.assertIn("reclaim", why)

    def test_short_below_flip_neg_gamma_confirmed(self):
        ok, _ = gex_confirms(prof(737, 740, "negative",
                                  [(733, "put", 12.0)]), "short")
        self.assertTrue(ok)

    def test_long_above_flip_neg_gamma_confirmed(self):
        # regime decoupled from side: -gamma continuation LONG is now reachable
        ok, why = gex_confirms(prof(743, 740, "negative"), "long")
        self.assertTrue(ok)
        self.assertIn("continuation", why)

    def test_long_vetoed_by_put_heavy_flow(self):
        ok, why = gex_confirms(prof(743, 740, "negative", [(735, "put", 8.0)]), "long")
        self.assertFalse(ok)
        self.assertIn("put-heavy", why)

    def test_pos_gamma_rejected_for_long_premium(self):
        # +gamma pinning is death for a premium buyer -> not confirmed
        ok, why = gex_confirms(prof(743, 740, "positive"), "long")
        self.assertFalse(ok)
        self.assertIn("pinning", why)

    def test_unknown_direction_rejected(self):
        self.assertFalse(gex_confirms(prof(737, 740, "negative"), "sideways")[0])


if __name__ == "__main__":
    unittest.main()
