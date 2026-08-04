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
# This is a FIXTURE, not a feed — it cannot tell you it has gone stale, so it
# belongs to the dry-run path only. Anything that can place an order should use
# earnings.McpEarningsCalendar instead. Verified against the broker earnings
# calendar on 2026-07-30; refresh it when the reporting window rolls. A symbol
# absent from the map is treated as having no scheduled report — the correct
# answer for names that already reported this cycle (GOOGL, TSLA and INTC, as
# of this refresh), and why the blackout must be derived rather than hardcoded.
EARNINGS_CALENDAR: dict[str, tuple[date, str]] = {
    "MSFT": (date(2026, 7, 29), "pm"),
    "META": (date(2026, 7, 29), "pm"),
    "AMZN": (date(2026, 7, 30), "pm"),
    "AAPL": (date(2026, 7, 30), "pm"),
    "XOM": (date(2026, 7, 31), "am"),
    "CVX": (date(2026, 7, 31), "am"),
    "AMD": (date(2026, 8, 4), "pm"),
    "NVDA": (date(2026, 8, 26), "pm"),
}


class SimulatedSignalSource:
    def __init__(self, session: date):
        self.session = session
        self._calendar = StaticEarningsCalendar(EARNINGS_CALENDAR)

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
