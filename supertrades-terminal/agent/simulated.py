"""Simulated signal source + paper environment for dry runs.

Mirrors the terminal's ``data.js`` fixtures (the NVDA squeeze and TSLA
gamma-flip signals) so a dry-run cycle reproduces what the dashboard shows,
end-to-end through the real decision path — without any live data or account.
"""

from __future__ import annotations

from datetime import date, datetime

from .config import WATCHLIST
from .earnings import StaticEarningsCalendar
from .models import (
    AccountState,
    ChainSnapshot,
    OptionContract,
    Signal,
)

# Earnings calendar fixture: symbol -> (report date, "am" | "pm").
#
# A FIXTURE, not a feed — the dry-run path only. Anything that can place an
# order must use earnings.McpEarningsCalendar, which refetches once per
# session date and so stays current on its own.
#
# This block is GENERATED. Refresh it from the live feed with:
#
#     python -m agent.cli refresh-earnings
#
# and commit the result. Everything between the BEGIN/END markers is rewritten
# wholesale, so hand-edits there are lost — put anything durable outside them.
#
# EARNINGS_CALENDAR_AS_OF is what makes the fixture able to say it has gone
# stale: past STATIC_FIXTURE_MAX_AGE_DAYS, StaticEarningsCalendar stops
# answering and fails closed rather than quoting dates from a previous
# reporting cycle. A symbol absent from the map has no scheduled report.
# --- BEGIN GENERATED EARNINGS FIXTURE ---
EARNINGS_CALENDAR_AS_OF = date(2026, 8, 4)

EARNINGS_CALENDAR: dict[str, tuple[date, str]] = {
    "MSFT": (date(2026, 7, 29), "pm"),
    "META": (date(2026, 7, 29), "pm"),
    "AMZN": (date(2026, 7, 30), "pm"),
    "XOM": (date(2026, 7, 31), "am"),
    "AMD": (date(2026, 8, 4), "pm"),
    "NVDA": (date(2026, 8, 26), "pm"),
}
# --- END GENERATED EARNINGS FIXTURE ---


class SimulatedSignalSource:
    def __init__(self, session: date):
        self.session = session
        self._calendar = StaticEarningsCalendar(
            EARNINGS_CALENDAR, as_of=EARNINGS_CALENDAR_AS_OF
        )

    def fired_signals(self, now: datetime) -> list[Signal]:
        return [
            Signal(symbol="NVDA", direction="long", strategy="Squeeze confluence · 5m",
                   entry=202.10, stop=201.75, target=202.90, time="14:32:07",
                   setup_fired=True, rvol=2.1, index_aligned=True,
                   structural_level_near_stop=True, confidence=82),
            Signal(symbol="TSLA", direction="short", strategy="Gamma flip break · 1m",
                   entry=403.40, stop=404.90, target=399.60, time="14:27:44",
                   setup_fired=True, rvol=1.8, index_aligned=True,
                   structural_level_near_stop=True, confidence=71),
        ]

    def earnings_symbols(self, now: datetime) -> frozenset[str]:
        """Names inside the earnings blackout as of ``now``.

        Derived from EARNINGS_CALENDAR rather than hardcoded, so the blackout
        expires on its own instead of blocking a name forever. See
        earnings.blackout_from_reports for the window semantics.
        """
        return self._calendar.blackout(now, WATCHLIST)


def demo_account(account_number: str = "AGENTIC-DEMO") -> AccountState:
    return AccountState(
        account_number=account_number, agentic_allowed=True,
        option_level="option_level_2", balance=25000.0,
        settled_cash=25000.0, unsettled_cash=0.0,
    )


def demo_chains(session: date) -> dict[str, ChainSnapshot]:
    def c(sym, otype, strike, bid, ask, delta, gamma=0.0):
        return OptionContract(f"{sym}-{otype}-{strike}", sym, otype, strike,
                              session, bid, ask, delta, gamma)
    return {
        "NVDA": ChainSnapshot("NVDA", session, [
            c("NVDA", "call", 202.5, 1.18, 1.24, 0.49, 0.055),
            c("NVDA", "call", 205.0, 0.61, 0.66, 0.34, 0.070),
        ]),
        "TSLA": ChainSnapshot("TSLA", session, [
            c("TSLA", "put", 402.5, 2.40, 2.55, 0.47, 0.030),
            c("TSLA", "put", 400.0, 1.30, 1.42, 0.33, 0.042),
        ]),
    }
