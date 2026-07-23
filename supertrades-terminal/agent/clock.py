"""Market-session time helpers (all in ET). Time is always passed in
explicitly so behavior is deterministic and testable."""

from __future__ import annotations

from datetime import datetime, timedelta

from .config import GUARDRAILS as G
from .config import MARKET_TZ


def to_et(now: datetime) -> datetime:
    """Normalize an aware/naive datetime to ET. Naive is assumed to be ET."""
    if now.tzinfo is None:
        return now.replace(tzinfo=MARKET_TZ)
    return now.astimezone(MARKET_TZ)


def in_session(now: datetime) -> bool:
    et = to_et(now)
    return G.session_open_et <= et.time() <= G.session_close_et


def in_no_entry_window(now: datetime) -> bool:
    """True during the first 15 min or last 10 min of the session — no entries."""
    et = to_et(now)
    open_cutoff = (
        datetime.combine(et.date(), G.session_open_et)
        + timedelta(minutes=G.no_entry_open_minutes)
    ).time()
    close_cutoff = (
        datetime.combine(et.date(), G.session_close_et)
        - timedelta(minutes=G.no_entry_close_minutes)
    ).time()
    t = et.time()
    return t < open_cutoff or t > close_cutoff


def at_or_past_flatten(now: datetime) -> bool:
    """True at/after 15:45 ET — force-flatten everything."""
    return to_et(now).time() >= G.force_flatten_et
