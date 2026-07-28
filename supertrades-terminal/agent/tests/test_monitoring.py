"""Tests for the monitoring scorer — round-trip matching, guardrail grading,
metrics, and recommendation triggers, all on synthetic snapshots. Pure stdlib;
run with:

    cd supertrades-terminal && python -m unittest agent.tests.test_monitoring -v
"""

from __future__ import annotations

import unittest
from datetime import datetime

from agent.monitoring.scorer import (
    Snapshot, extract_fills, match_round_trips, score_snapshot,
)

SESSION = "2026-07-28"


def order(oid, symbol, side, effect, price, qty=1.0, ts="2026-07-28T15:00:00Z",
          expiration=SESSION, strike="700.0", state="filled", agent="user"):
    """A minimal filled single-leg option order as the MCP returns it."""
    return {
        "id": oid, "chain_symbol": symbol, "state": state, "placed_agent": agent,
        "legs": [{
            "option_id": f"opt-{symbol}-{strike}-{expiration}",
            "side": side, "position_effect": effect, "option_type": "call",
            "strike_price": strike, "expiration_date": expiration,
            "executions": [] if state != "filled" else [
                {"price": str(price), "quantity": str(qty), "timestamp": ts},
            ],
        }],
    }


def snap(orders, total_value=5000.0, cash=4000.0, buying_power=4000.0,
         captured="2026-07-28T17:00:00Z", marks=None, equity_orders=None):
    return Snapshot(
        captured_at=datetime.fromisoformat(captured.replace("Z", "+00:00")).astimezone(),
        account_masked="••••0000", total_value=total_value, cash=cash,
        buying_power=buying_power, options_value=0.0, option_orders=orders,
        equity_orders=equity_orders or [], marks=marks or {},
    )


class TestMatching(unittest.TestCase):
    def test_round_trip_fifo_and_pnl(self):
        orders = [
            order("o1", "QQQ", "buy", "open", 1.00, ts="2026-07-28T14:30:00Z"),
            order("o2", "QQQ", "sell", "close", 1.50, ts="2026-07-28T15:30:00Z"),
        ]
        closed, open_lots = match_round_trips(extract_fills(orders), {})
        self.assertEqual(len(closed), 1)
        self.assertEqual(open_lots, [])
        t = closed[0]
        self.assertAlmostEqual(t.pnl, 50.0)
        self.assertAlmostEqual(t.pct, 0.50)
        # R uses the -50% premium stop as the risk unit: +$50 on $50 risk = +1R.
        self.assertAlmostEqual(t.r_multiple, 1.0)
        self.assertAlmostEqual(t.hold_minutes, 60.0)
        self.assertEqual(t.dte_at_entry, 0)

    def test_unmatched_open_stays_open_and_marks_apply(self):
        orders = [order("o1", "SPY", "buy", "open", 0.80, ts="2026-07-28T15:14:00Z")]
        closed, open_lots = match_round_trips(
            extract_fills(orders), {"opt-SPY-700.0-2026-07-28": 1.28})
        self.assertEqual(closed, [])
        self.assertEqual(len(open_lots), 1)
        self.assertAlmostEqual(open_lots[0].pct, 0.60)

    def test_orphan_close_is_dropped(self):
        orders = [order("o1", "SPY", "sell", "close", 1.00)]
        closed, open_lots = match_round_trips(extract_fills(orders), {})
        self.assertEqual((closed, open_lots), ([], []))

    def test_non_filled_orders_ignored(self):
        orders = [order("o1", "SPY", "sell", "close", 1.79, state="cancelled")]
        self.assertEqual(extract_fills(orders), [])


class TestGrading(unittest.TestCase):
    def _rules(self, score):
        return {v.rule for v in score.violations}

    def test_clean_session(self):
        orders = [
            order("o1", "QQQ", "buy", "open", 1.00, ts="2026-07-28T14:30:00Z"),
            order("o2", "QQQ", "sell", "close", 1.60, ts="2026-07-28T15:30:00Z"),
        ]
        score = score_snapshot(snap(orders))
        self.assertNotIn("0dte_only", self._rules(score))
        self.assertNotIn("sizing", self._rules(score))
        self.assertEqual(score.adherence, 100.0)

    def test_one_dte_entry_flagged(self):
        orders = [order("o1", "SPY", "buy", "open", 0.80, expiration="2026-07-29")]
        score = score_snapshot(snap(orders))
        self.assertIn("0dte_only", self._rules(score))
        self.assertLess(score.adherence, 100.0)

    def test_oversize_flagged_against_balance(self):
        # 2.5% of $1,000 = $25 allowed; $100 premium is ~4x over.
        orders = [
            order("o1", "QQQ", "buy", "open", 1.00, ts="2026-07-28T14:30:00Z"),
            order("o2", "QQQ", "sell", "close", 1.10, ts="2026-07-28T15:00:00Z"),
        ]
        score = score_snapshot(snap(orders, total_value=1000.0))
        self.assertIn("sizing", self._rules(score))

    def test_entry_window_flagged(self):
        # 13:35Z = 09:35 ET, inside the first-15-minutes block.
        orders = [order("o1", "QQQ", "buy", "open", 0.50, ts="2026-07-28T13:35:00Z")]
        score = score_snapshot(snap(orders))
        self.assertIn("entry_window", self._rules(score))

    def test_stop_discipline_breach(self):
        orders = [
            order("o1", "QQQ", "buy", "open", 1.00, ts="2026-07-28T14:30:00Z"),
            order("o2", "QQQ", "sell", "close", 0.25, ts="2026-07-28T15:30:00Z"),
        ]
        score = score_snapshot(snap(orders))
        self.assertIn("stop_discipline", self._rules(score))

    def test_force_flatten_after_1545(self):
        # Snapshot at 19:50Z = 15:50 ET with a same-day lot still open.
        orders = [order("o1", "QQQ", "buy", "open", 0.50, ts="2026-07-28T15:00:00Z")]
        score = score_snapshot(snap(orders, captured="2026-07-28T19:50:00Z"))
        self.assertIn("force_flatten", self._rules(score))

    def test_equity_fills_flagged(self):
        score = score_snapshot(snap([], equity_orders=[{"state": "filled"}]))
        self.assertIn("options_only", self._rules(score))

    def test_balance_floor_is_info_only(self):
        score = score_snapshot(snap([], total_value=434.0))
        floor = [v for v in score.violations if v.rule == "balance_floor"]
        self.assertEqual(len(floor), 1)
        self.assertEqual(floor[0].points, 0.0)


class TestMetricsAndRecs(unittest.TestCase):
    def test_metrics_roundup(self):
        orders = [
            order("o1", "QQQ", "buy", "open", 1.00, ts="2026-07-28T14:30:00Z"),
            order("o2", "QQQ", "sell", "close", 1.50, ts="2026-07-28T15:00:00Z"),
            order("o3", "SPY", "buy", "open", 1.00, ts="2026-07-28T15:10:00Z", strike="740.0"),
            order("o4", "SPY", "sell", "close", 0.80, ts="2026-07-28T15:40:00Z", strike="740.0"),
        ]
        m = score_snapshot(snap(orders)).metrics
        self.assertEqual(m["n_closed"], 2)
        self.assertAlmostEqual(m["realized_pnl"], 30.0)
        self.assertAlmostEqual(m["win_rate"], 0.5)
        self.assertAlmostEqual(m["profit_factor"], 2.5)

    def test_low_balance_makes_sizing_unworkable_rec(self):
        score = score_snapshot(snap([], total_value=434.0))
        self.assertTrue(any("unworkable" in r for r in score.recommendations))

    def test_sample_size_caveat_always_present_when_thin(self):
        score = score_snapshot(snap([]))
        self.assertTrue(any("provisional" in r for r in score.recommendations))


if __name__ == "__main__":
    unittest.main()
