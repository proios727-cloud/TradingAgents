"""Simulated signal source + paper environment for dry runs.

Mirrors the terminal's ``data.js`` fixtures (the NVDA squeeze and TSLA
gamma-flip signals) so a dry-run cycle reproduces what the dashboard shows,
end-to-end through the real decision path — without any live data or account.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from .config import GUARDRAILS, MARKET_TZ
from .models import (
    AccountState,
    ChainSnapshot,
    OptionContract,
    Signal,
)

# Earnings calendar fixture: symbol -> (report date, "am" | "pm").
#
# This is a FIXTURE, not a feed. Verified against the broker earnings calendar
# on 2026-07-30; refresh it when the reporting window rolls, or replace the
# whole lookup with a live source. A symbol absent from the map is treated as
# having no scheduled report — which is the correct answer for names that
# already reported this cycle (GOOGL, TSLA and INTC, as of this refresh), and
# is why the blackout must be derived rather than hardcoded.
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


def _next_session(d: date) -> date:
    nxt = d + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt


def _sessions_between(a: date, b: date) -> int:
    """Signed count of trading sessions from ``a`` to ``b``.

    Weekdays only — market holidays are not modelled, because the fixture
    calendar above does not span one. A missed holiday can only make this
    count HIGH by one, which unblocks a name a session early; keep that in
    mind before pointing this at a live feed.
    """
    step = 1 if b >= a else -1
    count, cur = 0, a
    while cur != b:
        cur += timedelta(days=step)
        if cur.weekday() < 5:
            count += step
    return count


def _gap_session(report_date: date, timing: str) -> date:
    """The session whose OPEN carries the earnings gap.

    An ``am`` report gaps its own open; a ``pm`` report gaps the next one.
    """
    return report_date if timing == "am" else _next_session(report_date)


class SimulatedSignalSource:
    def __init__(self, session: date):
        self.session = session

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
        expires on its own instead of blocking a name forever. A symbol is
        blocked for GUARDRAILS.earnings_block_sessions sessions on BOTH sides
        of the session carrying its gap: before, because a 0DTE long would be
        held into the event, and after, because the post-print IV crush is
        just as hostile to long premium. Symmetric is the conservative read of
        "earnings within N sessions" — it can only ever block more, never less.
        """
        today = now.astimezone(MARKET_TZ).date()
        window = GUARDRAILS.earnings_block_sessions
        return frozenset(
            sym
            for sym, (report_date, timing) in EARNINGS_CALENDAR.items()
            if abs(_sessions_between(today, _gap_session(report_date, timing))) <= window
        )


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
