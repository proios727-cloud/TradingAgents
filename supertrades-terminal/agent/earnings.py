"""Earnings blackout — the calendar half of GUARDRAILS.earnings_block_sessions.

Two calendars sit behind one protocol:

  * ``StaticEarningsCalendar`` — a hand-maintained fixture, used by the
    simulated / dry-run path.
  * ``McpEarningsCalendar`` — the live feed, reading Robinhood's
    ``get_earnings_calendar`` through the same injected ``mcp_call``
    dispatcher the broker uses.

Both derive the blackout through the same pure functions below, so a dry run
and a live run block identically given identical calendars.

FAIL-CLOSED — read before changing anything here:

    "We could not confirm this name is clear of earnings" and "this name has
    no earnings" must never collapse into the same answer.

An unwired dispatcher, an unreachable feed, a malformed payload, a row whose
date will not parse — each of these widens the blackout to the whole universe
rather than narrowing it to nothing. The failure mode of this module is that
the agent stops trading, never that it walks into a print. That matches the
existing house rule that an MCP error trips the kill switch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Iterable, Optional, Protocol, Sequence

from .config import GUARDRAILS, MARKET_TZ, WATCHLIST

McpCall = Callable[[str, dict], dict]


@dataclass(frozen=True)
class EarningsReport:
    symbol: str
    report_date: date
    timing: str  # "am" | "pm" | "" when the feed does not say


class EarningsCalendar(Protocol):
    def blackout(self, now: datetime, universe: Sequence[str]) -> frozenset[str]: ...


# --- session math --------------------------------------------------------
def next_session(d: date) -> date:
    nxt = d + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt


def sessions_between(a: date, b: date) -> int:
    """Signed count of trading sessions from ``a`` to ``b``.

    Weekdays only — market holidays are not modelled. A missed holiday makes
    this count HIGH by one, which would unblock a name a session early, so the
    live path pads its fetch window rather than relying on an exact count.
    """
    step = 1 if b >= a else -1
    count, cur = 0, a
    while cur != b:
        cur += timedelta(days=step)
        if cur.weekday() < 5:
            count += step
    return count


def gap_sessions(report_date: date, timing: str) -> tuple[date, ...]:
    """Session(s) whose OPEN can carry the earnings gap.

    An ``am`` report gaps its own open; a ``pm`` report gaps the next one
    (Friday ``pm`` -> Monday). When the feed does not say, the gap is one of
    the two and we cannot tell which, so both count — the wider window is the
    safe one.
    """
    t = (timing or "").strip().lower()
    if t == "am":
        return (report_date,)
    if t == "pm":
        return (next_session(report_date),)
    return (report_date, next_session(report_date))


def blackout_from_reports(
    reports: Iterable[EarningsReport], today: date, window: int
) -> frozenset[str]:
    """Symbols blocked on ``today`` given ``reports``.

    A symbol is blocked for ``window`` sessions on BOTH sides of the session
    carrying its gap: before, because a 0DTE long would be held into the
    event, and after, because the post-print IV crush is just as hostile to
    long premium. Symmetric is the conservative read of "earnings within N
    sessions" — it can only ever block more, never less.
    """
    return frozenset(
        r.symbol
        for r in reports
        if any(
            abs(sessions_between(today, g)) <= window
            for g in gap_sessions(r.report_date, r.timing)
        )
    )


# --- fixture calendar ----------------------------------------------------
# How long a generated fixture may be trusted before it stops answering.
# Reporting season turns over in weeks, so a fixture older than this is
# quoting a previous cycle: names that have since reported look clear, and
# names about to report are missing entirely.
STATIC_FIXTURE_MAX_AGE_DAYS = 21


class StaticEarningsCalendar:
    """Blackout from a generated ``{symbol: (date, timing)}`` mapping.

    Pass ``as_of`` (the date the mapping was generated) and the fixture gains
    the one thing a fixture normally cannot do: it can tell you it has gone
    stale. Past ``max_age_days`` it stops answering and fails closed, exactly
    like the live calendar does on an unreachable feed — a dry run that would
    otherwise quote last cycle's dates goes loudly wrong instead of quietly
    wrong. Without ``as_of`` it never expires, which is what ad-hoc test
    fixtures want.

    Use this for dry runs; use ``McpEarningsCalendar`` for anything that can
    place an order.
    """

    def __init__(
        self,
        reports: dict[str, tuple[date, str]],
        *,
        as_of: Optional[date] = None,
        max_age_days: int = STATIC_FIXTURE_MAX_AGE_DAYS,
    ):
        self._reports = [
            EarningsReport(sym, d, t) for sym, (d, t) in reports.items()
        ]
        self.as_of = as_of
        self.max_age_days = max_age_days
        self.last_error: str = ""

    def age_days(self, today: date) -> Optional[int]:
        return None if self.as_of is None else (today - self.as_of).days

    def blackout(
        self, now: datetime, universe: Sequence[str] = WATCHLIST
    ) -> frozenset[str]:
        today = now.astimezone(MARKET_TZ).date()

        age = self.age_days(today)
        if age is not None and age > self.max_age_days:
            self.last_error = (
                f"earnings fixture is {age} days old (generated "
                f"{self.as_of}, max {self.max_age_days}) — refresh it with "
                f"`python -m agent.cli refresh-earnings`"
            )
            return frozenset(universe)

        self.last_error = ""
        blocked = blackout_from_reports(
            self._reports, today, GUARDRAILS.earnings_block_sessions
        )
        return blocked & frozenset(universe)


# --- live calendar -------------------------------------------------------
# Sessions are weekdays, so N sessions is at most ceil(N/5)*7 + N calendar
# days. Padding generously is free (one call/day) and protects the window
# against holidays, which sessions_between does not model.
_FETCH_PAD_DAYS = 7


class McpEarningsCalendar:
    """Blackout from the broker's live earnings calendar.

    One fetch per session date, cached; failures are never cached, so a
    transient outage blocks only until the next successful call.
    """

    def __init__(
        self,
        mcp_call: Optional[McpCall] = None,
        *,
        pad_days: int = _FETCH_PAD_DAYS,
    ):
        self._mcp = mcp_call
        self._pad = pad_days
        self._cache: Optional[tuple[date, list[EarningsReport], frozenset[str]]] = None
        self.last_error: str = ""

    def blackout(
        self, now: datetime, universe: Sequence[str] = WATCHLIST
    ) -> frozenset[str]:
        everything = frozenset(universe)
        today = now.astimezone(MARKET_TZ).date()

        # Gate: no dispatcher wired -> we know nothing -> block everything.
        if self._mcp is None:
            self.last_error = "no mcp_call dispatcher wired"
            return everything

        fetched = self._fetch(today)
        if fetched is None:
            return everything
        reports, unparsable = fetched

        blocked = blackout_from_reports(
            reports, today, GUARDRAILS.earnings_block_sessions
        )
        # A row we could not read might have been a report for one of our
        # names, so any such symbol stays blocked on its own account.
        return (blocked | unparsable) & everything

    # -- internals --------------------------------------------------------
    def _fetch(
        self, today: date
    ) -> Optional[tuple[list[EarningsReport], frozenset[str]]]:
        if self._cache is not None and self._cache[0] == today:
            return self._cache[1], self._cache[2]

        window = GUARDRAILS.earnings_block_sessions
        start = today - timedelta(days=window + self._pad)
        span = 2 * (window + self._pad) + 1
        try:
            reports, unparsable = fetch_window(self._mcp, start, span)
        except Exception as e:  # noqa: BLE001 — any failure must fail closed
            self.last_error = f"earnings calendar fetch failed: {e}"
            self._cache = None
            return None

        self.last_error = ""
        self._cache = (today, reports, unparsable)
        return reports, unparsable


def fetch_window(
    mcp_call: McpCall, start: date, span_days: int
) -> tuple[list[EarningsReport], frozenset[str]]:
    """One raw, uncached ``get_earnings_calendar`` read over a date window.

    Deliberately sends no market-cap filter: filtering server-side could
    silently drop a watchlist name and unblock it, the one outcome this module
    exists to prevent. Raises on any failure — callers decide how to fail.
    """
    payload = mcp_call(
        "get_earnings_calendar",
        {"start_date": start.isoformat(), "days": span_days},
    )
    return parse_calendar(payload)


def parse_calendar(payload) -> tuple[list[EarningsReport], frozenset[str]]:
    """Parse a ``get_earnings_calendar`` payload.

    Returns the rows that parsed plus the symbols of the rows that did not.
    Unreadable rows are surfaced rather than skipped: a dropped row is an
    unblocked name, which is exactly the failure this module guards against.
    Rows are kept whether or not the feed marks them ``verified`` — an
    unconfirmed date still blocks, because blocking more is always the safe
    direction.
    """
    rows = _rows(payload)
    if not isinstance(rows, list):
        raise ValueError(f"unexpected earnings payload: {type(rows).__name__}")

    reports: list[EarningsReport] = []
    unparsable: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        report = row.get("report") or {}
        raw_date = (report.get("date") if isinstance(report, dict) else None) or ""
        timing = (report.get("timing") if isinstance(report, dict) else "") or ""
        try:
            reports.append(
                EarningsReport(symbol, date.fromisoformat(str(raw_date)), str(timing))
            )
        except (TypeError, ValueError):
            unparsable.add(symbol)
    return reports, frozenset(unparsable)


def _rows(payload):
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict) and "results" in data:
            return data.get("results") or []
        return payload.get("results") or data or []
    return payload or []
