"""Regenerate the dry-run earnings fixture from the live feed.

The fixture in ``simulated.py`` is the only earnings source the dry-run path
has, and reporting season turns over in weeks. Rather than leave it to be
hand-edited (and forgotten), this rewrites the generated block in place from
one read of the real ``get_earnings_calendar``:

    python -m agent.cli refresh-earnings

Read-only against the broker — the only mutation is to a source file in this
repo, which you then review and commit like any other change.

Scope: only symbols in ``WATCHLIST`` are written. ``StaticEarningsCalendar``
intersects its answer with the universe anyway, so entries for anything else
are dead weight that reads like coverage.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Sequence

from .config import WATCHLIST
from .earnings import EarningsReport, McpCall, fetch_window

BEGIN = "# --- BEGIN GENERATED EARNINGS FIXTURE ---"
END = "# --- END GENERATED EARNINGS FIXTURE ---"

FIXTURE_PATH = Path(__file__).with_name("simulated.py")

# Look back far enough to keep names whose post-print blackout is still open,
# and forward far enough to catch the next cycle before it arrives. The API
# caps a single window at 31 days, so this is two reads.
LOOKBACK_DAYS = 21
LOOKAHEAD_DAYS = 55
_MAX_WINDOW = 31


class FixtureRefreshError(RuntimeError):
    """Refresh could not complete. The fixture on disk is left untouched."""


def collect_reports(
    mcp_call: McpCall,
    today: date,
    *,
    universe: Sequence[str] = WATCHLIST,
) -> list[EarningsReport]:
    """Every scheduled report for ``universe`` around ``today``, deduped.

    A symbol reporting twice in range (a restated or moved date) keeps the
    entry NEAREST to today, since that is the one whose blackout is live.
    """
    wanted = {s.upper() for s in universe}
    start = today - timedelta(days=LOOKBACK_DAYS)
    end = today + timedelta(days=LOOKAHEAD_DAYS)

    best: dict[str, EarningsReport] = {}
    cursor = start
    while cursor <= end:
        span = min(_MAX_WINDOW, (end - cursor).days + 1)
        reports, _unparsable = fetch_window(mcp_call, cursor, span)
        for r in reports:
            if r.symbol not in wanted:
                continue
            prior = best.get(r.symbol)
            if prior is None or abs((r.report_date - today).days) < abs(
                (prior.report_date - today).days
            ):
                best[r.symbol] = r
        cursor += timedelta(days=span)

    # Chronological, so a reviewer reads the block as a calendar.
    return sorted(best.values(), key=lambda r: (r.report_date, r.symbol))


def render_block(reports: Sequence[EarningsReport], as_of: date) -> str:
    lines = [
        BEGIN,
        f"EARNINGS_CALENDAR_AS_OF = date({as_of.year}, {as_of.month}, {as_of.day})",
        "",
        "EARNINGS_CALENDAR: dict[str, tuple[date, str]] = {",
    ]
    for r in reports:
        d = r.report_date
        timing = r.timing if r.timing in ("am", "pm") else ""
        lines.append(
            f'    "{r.symbol}": (date({d.year}, {d.month}, {d.day}), "{timing}"),'
        )
    lines.append("}")
    lines.append(END)
    return "\n".join(lines)


def write_block(block: str, path: Path = FIXTURE_PATH) -> None:
    source = path.read_text()
    pattern = re.compile(
        re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL
    )
    if not pattern.search(source):
        raise FixtureRefreshError(
            f"markers not found in {path} — expected {BEGIN!r} ... {END!r}. "
            f"Nothing was written."
        )
    path.write_text(pattern.sub(lambda _m: block, source, count=1))


def refresh(
    mcp_call: McpCall,
    today: date,
    *,
    universe: Sequence[str] = WATCHLIST,
    path: Path = FIXTURE_PATH,
) -> list[EarningsReport]:
    """Fetch, render, and rewrite the fixture. Returns what was written.

    An empty result is refused rather than written: every watchlist name being
    genuinely report-free for the whole window is possible but indistinguish-
    able from a feed that answered with nothing, and the second one would
    quietly erase the blackout.
    """
    reports = collect_reports(mcp_call, today, universe=universe)
    if not reports:
        raise FixtureRefreshError(
            "the feed returned no reports for any watchlist name over "
            f"{LOOKBACK_DAYS + LOOKAHEAD_DAYS} days — refusing to write an "
            "empty fixture, which would read as 'nothing has earnings'. "
            "The existing fixture is unchanged."
        )
    write_block(render_block(reports, today), path)
    return reports
