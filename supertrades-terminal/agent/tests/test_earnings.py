"""Earnings blackout tests — session math, window semantics, and above all
that every live-feed failure path FAILS CLOSED. Pure stdlib; run with:

    cd supertrades-terminal && python -m unittest agent.tests.test_earnings -v
"""

from __future__ import annotations

import unittest
from datetime import date, datetime

from agent.config import MARKET_TZ
from agent.earnings import (
    EarningsReport,
    McpEarningsCalendar,
    StaticEarningsCalendar,
    blackout_from_reports,
    gap_sessions,
    next_session,
    parse_calendar,
    sessions_between,
)

UNIVERSE = ("SPY", "MSFT", "META", "AMZN", "NVDA", "XOM")


def et(d: date, h: int = 12) -> datetime:
    return datetime(d.year, d.month, d.day, h, 0, tzinfo=MARKET_TZ)


def row(symbol: str, d: str, timing: str = "pm") -> dict:
    return {"symbol": symbol, "report": {"date": d, "timing": timing, "verified": True}}


class SessionMath(unittest.TestCase):
    def test_same_day_is_zero(self):
        self.assertEqual(sessions_between(date(2026, 7, 30), date(2026, 7, 30)), 0)

    def test_weekends_are_not_sessions(self):
        # Friday -> Monday is one session, not three days.
        self.assertEqual(sessions_between(date(2026, 7, 31), date(2026, 8, 3)), 1)

    def test_signed_backwards(self):
        self.assertEqual(sessions_between(date(2026, 8, 3), date(2026, 7, 31)), -1)

    def test_next_session_skips_the_weekend(self):
        self.assertEqual(next_session(date(2026, 7, 31)), date(2026, 8, 3))


class GapSession(unittest.TestCase):
    def test_am_gaps_its_own_open(self):
        self.assertEqual(gap_sessions(date(2026, 7, 31), "am"), (date(2026, 7, 31),))

    def test_pm_gaps_the_next_open(self):
        self.assertEqual(gap_sessions(date(2026, 7, 29), "pm"), (date(2026, 7, 30),))

    def test_friday_pm_gaps_monday(self):
        self.assertEqual(gap_sessions(date(2026, 7, 31), "pm"), (date(2026, 8, 3),))

    def test_unknown_timing_covers_both(self):
        # Cannot tell which open gaps -> block both. Wider is safe.
        self.assertEqual(
            gap_sessions(date(2026, 7, 30), ""),
            (date(2026, 7, 30), date(2026, 7, 31)),
        )


class WindowSemantics(unittest.TestCase):
    reports = [EarningsReport("MSFT", date(2026, 7, 29), "pm")]  # gaps 07-30

    def blocked_on(self, d: date, window: int = 3) -> frozenset[str]:
        return blackout_from_reports(self.reports, d, window)

    def test_blocked_on_the_gap_session(self):
        self.assertIn("MSFT", self.blocked_on(date(2026, 7, 30)))

    def test_blocked_before_the_event(self):
        self.assertIn("MSFT", self.blocked_on(date(2026, 7, 27)))

    def test_blocked_after_the_event_too(self):
        # Symmetric: post-print IV crush is as hostile to long premium as the
        # gap itself. 07-30 + 3 sessions = 08-04.
        self.assertIn("MSFT", self.blocked_on(date(2026, 8, 4)))

    def test_expires_on_its_own(self):
        self.assertNotIn("MSFT", self.blocked_on(date(2026, 8, 5)))


class Fixture(unittest.TestCase):
    def setUp(self):
        self.cal = StaticEarningsCalendar({
            "MSFT": (date(2026, 7, 29), "pm"),
            "NVDA": (date(2026, 8, 26), "pm"),
        })

    def test_blocks_the_near_name_only(self):
        blocked = self.cal.blackout(et(date(2026, 7, 30)), UNIVERSE)
        self.assertEqual(blocked, frozenset({"MSFT"}))

    def test_absent_symbol_is_never_blocked(self):
        # A name that already reported is simply not in the map.
        self.assertNotIn("SPY", self.cal.blackout(et(date(2026, 7, 30)), UNIVERSE))


class LiveFeedHappyPath(unittest.TestCase):
    def test_parses_and_blocks(self):
        calls: list[tuple[str, dict]] = []

        def mcp(tool, params):
            calls.append((tool, params))
            return {"data": {"results": [
                row("MSFT", "2026-07-29", "pm"),
                row("XOM", "2026-07-31", "am"),
                row("NVDA", "2026-08-26", "pm"),
            ]}}

        cal = McpEarningsCalendar(mcp)
        blocked = cal.blackout(et(date(2026, 7, 30)), UNIVERSE)
        self.assertEqual(blocked, frozenset({"MSFT", "XOM"}))
        self.assertEqual(calls[0][0], "get_earnings_calendar")
        # No market-cap filter — server-side filtering could drop a watchlist
        # name and silently unblock it.
        self.assertNotIn("filter", calls[0][1])

    def test_one_fetch_per_session_date(self):
        n = []

        def mcp(tool, params):
            n.append(1)
            return {"data": {"results": [row("MSFT", "2026-07-29", "pm")]}}

        cal = McpEarningsCalendar(mcp)
        cal.blackout(et(date(2026, 7, 30), 10), UNIVERSE)
        cal.blackout(et(date(2026, 7, 30), 14), UNIVERSE)
        self.assertEqual(len(n), 1)
        cal.blackout(et(date(2026, 7, 31)), UNIVERSE)
        self.assertEqual(len(n), 2)

    def test_result_is_scoped_to_the_universe(self):
        def mcp(tool, params):
            return {"data": {"results": [row("TSM", "2026-07-29", "pm")]}}

        self.assertEqual(
            McpEarningsCalendar(mcp).blackout(et(date(2026, 7, 30)), UNIVERSE),
            frozenset(),
        )


class LiveFeedFailsClosed(unittest.TestCase):
    """Every one of these must block the WHOLE universe, never nothing."""

    def assert_blocks_everything(self, cal):
        self.assertEqual(
            cal.blackout(et(date(2026, 7, 30)), UNIVERSE), frozenset(UNIVERSE)
        )

    def test_no_dispatcher_wired(self):
        self.assert_blocks_everything(McpEarningsCalendar())

    def test_dispatcher_raises(self):
        def mcp(tool, params):
            raise RuntimeError("connection reset")

        cal = McpEarningsCalendar(mcp)
        self.assert_blocks_everything(cal)
        self.assertIn("connection reset", cal.last_error)

    def test_malformed_payload(self):
        self.assert_blocks_everything(McpEarningsCalendar(lambda t, p: "nonsense"))

    def test_failure_is_not_cached(self):
        state = {"fail": True}

        def mcp(tool, params):
            if state["fail"]:
                raise RuntimeError("transient")
            return {"data": {"results": [row("MSFT", "2026-07-29", "pm")]}}

        cal = McpEarningsCalendar(mcp)
        self.assert_blocks_everything(cal)
        state["fail"] = False
        # Same session date, but the failure must not have been cached.
        self.assertEqual(
            cal.blackout(et(date(2026, 7, 30)), UNIVERSE), frozenset({"MSFT"})
        )

    def test_unreadable_row_blocks_its_own_symbol(self):
        def mcp(tool, params):
            return {"data": {"results": [
                {"symbol": "META", "report": {"date": "not-a-date", "timing": "pm"}},
                row("NVDA", "2026-08-26", "pm"),
            ]}}

        blocked = McpEarningsCalendar(mcp).blackout(et(date(2026, 7, 30)), UNIVERSE)
        self.assertIn("META", blocked)   # unparsable -> blocked, not dropped
        self.assertNotIn("NVDA", blocked)

    def test_empty_calendar_blocks_nothing(self):
        # A successful fetch that genuinely returns no reports is NOT a
        # failure — it must not block, or the agent could never trade.
        cal = McpEarningsCalendar(lambda t, p: {"data": {"results": []}})
        self.assertEqual(
            cal.blackout(et(date(2026, 7, 30)), UNIVERSE), frozenset()
        )


class Parsing(unittest.TestCase):
    def test_accepts_nested_and_flat_shapes(self):
        nested, _ = parse_calendar({"data": {"results": [row("MSFT", "2026-07-29")]}})
        flat, _ = parse_calendar({"results": [row("MSFT", "2026-07-29")]})
        bare, _ = parse_calendar([row("MSFT", "2026-07-29")])
        self.assertEqual(len(nested), len(flat), len(bare))
        self.assertEqual(nested[0].symbol, "MSFT")

    def test_unverified_rows_still_block(self):
        payload = {"data": {"results": [
            {"symbol": "MSFT",
             "report": {"date": "2026-07-29", "timing": "pm", "verified": False}},
        ]}}
        reports, _ = parse_calendar(payload)
        self.assertEqual(len(reports), 1)

    def test_rejects_a_non_list_payload(self):
        with self.assertRaises(ValueError):
            parse_calendar({"data": {"results": {"nope": 1}}})


if __name__ == "__main__":
    unittest.main()
