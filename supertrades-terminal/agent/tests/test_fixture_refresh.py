"""Fixture-refresh tests — the generated block must round-trip, stay scoped to
the watchlist, and refuse to write anything that would erase the blackout.
Pure stdlib; NO real MCP call is ever made. Run with:

    cd supertrades-terminal && python -m unittest agent.tests.test_fixture_refresh -v
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from agent.config import MARKET_TZ
from agent.earnings import EarningsReport, StaticEarningsCalendar
from agent.fixture_refresh import (
    BEGIN,
    END,
    FixtureRefreshError,
    collect_reports,
    refresh,
    render_block,
    write_block,
)

TODAY = date(2026, 8, 4)
UNIVERSE = ("NVDA", "MSFT", "AMZN", "XOM")


def row(symbol: str, d: str, timing: str = "pm") -> dict:
    return {"symbol": symbol, "report": {"date": d, "timing": timing}}


def feed(*rows):
    """An mcp_call that answers every window with the same rows."""
    calls: list[dict] = []

    def mcp(tool, params):
        calls.append(params)
        return {"data": {"results": list(rows)}}

    mcp.calls = calls
    return mcp


SAMPLE = feed(
    row("MSFT", "2026-07-29", "pm"),
    row("AMZN", "2026-07-30", "pm"),
    row("XOM", "2026-07-31", "am"),
    row("NVDA", "2026-08-26", "pm"),
    row("TSM", "2026-08-10", "pm"),      # not in the universe
)


class Collect(unittest.TestCase):
    def test_keeps_only_universe_symbols(self):
        reports = collect_reports(SAMPLE, TODAY, universe=UNIVERSE)
        self.assertEqual({r.symbol for r in reports}, set(UNIVERSE))

    def test_sorted_chronologically(self):
        reports = collect_reports(SAMPLE, TODAY, universe=UNIVERSE)
        self.assertEqual([r.report_date for r in reports],
                         sorted(r.report_date for r in reports))

    def test_sends_no_market_cap_filter(self):
        mcp = feed(row("MSFT", "2026-07-29"))
        collect_reports(mcp, TODAY, universe=UNIVERSE)
        self.assertTrue(mcp.calls)
        for params in mcp.calls:
            self.assertNotIn("filter", params)

    def test_windows_respect_the_31_day_api_cap(self):
        mcp = feed(row("MSFT", "2026-07-29"))
        collect_reports(mcp, TODAY, universe=UNIVERSE)
        for params in mcp.calls:
            self.assertLessEqual(params["days"], 31)

    def test_duplicate_symbol_keeps_the_nearest_date(self):
        mcp = feed(
            row("NVDA", "2026-08-26", "pm"),
            row("NVDA", "2026-08-05", "am"),   # nearer to TODAY
        )
        reports = collect_reports(mcp, TODAY, universe=("NVDA",))
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].report_date, date(2026, 8, 5))


class Render(unittest.TestCase):
    def test_block_is_importable_python_and_round_trips(self):
        reports = [
            EarningsReport("MSFT", date(2026, 7, 29), "pm"),
            EarningsReport("NVDA", date(2026, 8, 26), "pm"),
        ]
        block = render_block(reports, TODAY)
        ns: dict = {"date": date}
        exec(compile(block, "<fixture>", "exec"), ns)  # noqa: S102 — our own text
        self.assertEqual(ns["EARNINGS_CALENDAR_AS_OF"], TODAY)
        self.assertEqual(ns["EARNINGS_CALENDAR"], {
            "MSFT": (date(2026, 7, 29), "pm"),
            "NVDA": (date(2026, 8, 26), "pm"),
        })

    def test_unknown_timing_renders_empty_not_guessed(self):
        block = render_block([EarningsReport("MSFT", date(2026, 7, 29), "")], TODAY)
        self.assertIn('(date(2026, 7, 29), "")', block)


class Write(unittest.TestCase):
    def _tmp(self, body: str) -> Path:
        p = Path(tempfile.mkdtemp()) / "simulated.py"
        p.write_text(body)
        return p

    def test_replaces_only_between_the_markers(self):
        p = self._tmp(f"before\n{BEGIN}\nold = 1\n{END}\nafter\n")
        write_block(f"{BEGIN}\nnew = 2\n{END}", p)
        out = p.read_text()
        self.assertIn("before", out)
        self.assertIn("after", out)
        self.assertIn("new = 2", out)
        self.assertNotIn("old = 1", out)

    def test_missing_markers_writes_nothing(self):
        p = self._tmp("no markers here\n")
        with self.assertRaises(FixtureRefreshError):
            write_block(f"{BEGIN}\nx = 1\n{END}", p)
        self.assertEqual(p.read_text(), "no markers here\n")


class RefusesToErase(unittest.TestCase):
    def test_empty_feed_leaves_the_fixture_untouched(self):
        # An empty write would read as "nothing has earnings" — the exact
        # silent-unblock this whole module exists to prevent.
        p = Path(tempfile.mkdtemp()) / "simulated.py"
        original = f"{BEGIN}\nEARNINGS_CALENDAR = {{'MSFT': 1}}\n{END}\n"
        p.write_text(original)
        with self.assertRaises(FixtureRefreshError):
            refresh(feed(), TODAY, universe=UNIVERSE, path=p)
        self.assertEqual(p.read_text(), original)

    def test_feed_failure_propagates_and_writes_nothing(self):
        def boom(tool, params):
            raise ConnectionError("feed down")

        p = Path(tempfile.mkdtemp()) / "simulated.py"
        p.write_text(f"{BEGIN}\nx = 1\n{END}\n")
        with self.assertRaises(ConnectionError):
            refresh(boom, TODAY, universe=UNIVERSE, path=p)
        self.assertIn("x = 1", p.read_text())


class FixtureStaleness(unittest.TestCase):
    reports = {"MSFT": (date(2026, 7, 29), "pm")}

    def cal(self, **kw):
        return StaticEarningsCalendar(self.reports, **kw)

    def et(self, d: date) -> datetime:
        return datetime(d.year, d.month, d.day, 12, 0, tzinfo=MARKET_TZ)

    def test_fresh_fixture_answers_normally(self):
        cal = self.cal(as_of=TODAY, max_age_days=21)
        self.assertEqual(cal.blackout(self.et(TODAY), UNIVERSE),
                         frozenset({"MSFT"}))
        self.assertEqual(cal.last_error, "")

    def test_stale_fixture_fails_closed(self):
        cal = self.cal(as_of=TODAY, max_age_days=21)
        blocked = cal.blackout(self.et(date(2026, 9, 30)), UNIVERSE)
        self.assertEqual(blocked, frozenset(UNIVERSE))
        self.assertIn("refresh-earnings", cal.last_error)

    def test_boundary_day_still_answers(self):
        cal = self.cal(as_of=TODAY, max_age_days=21)
        cal.blackout(self.et(TODAY + __import__("datetime").timedelta(days=21)),
                     UNIVERSE)
        self.assertEqual(cal.last_error, "")

    def test_without_as_of_it_never_expires(self):
        # Ad-hoc test fixtures opt out by simply not passing as_of.
        cal = self.cal()
        self.assertEqual(cal.blackout(self.et(date(2030, 1, 1)), UNIVERSE),
                         frozenset())
        self.assertEqual(cal.last_error, "")


class ShippedFixtureIsCurrent(unittest.TestCase):
    def test_committed_fixture_parses_and_is_scoped(self):
        from agent.config import WATCHLIST
        from agent.simulated import EARNINGS_CALENDAR, EARNINGS_CALENDAR_AS_OF

        self.assertIsInstance(EARNINGS_CALENDAR_AS_OF, date)
        self.assertTrue(EARNINGS_CALENDAR)
        for sym, (d, timing) in EARNINGS_CALENDAR.items():
            self.assertIn(sym, WATCHLIST, f"{sym} is not on the watchlist")
            self.assertIsInstance(d, date)
            self.assertIn(timing, ("am", "pm", ""))


if __name__ == "__main__":
    unittest.main()
