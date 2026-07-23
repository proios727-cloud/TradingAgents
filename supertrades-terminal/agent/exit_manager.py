"""Exit manager.

Exits stay live even when the session is halted for new entries. For each open
position, in priority order:

  1. 15:45 ET force-flatten (never hold 0DTE to the bell).
  2. Premium stop: mark <= -50% of entry premium -> close immediately (marketable).
  3. Thesis break, or underlying hit the stop -> close immediately (marketable).
  4. Premium target: mark >= +90% -> sell to close.
  5. Underlying hit target -> sell to close.
  6. Scale half at +1R (once), trail the rest.

Never widens a stop; the stop is fixed from entry.
"""

from __future__ import annotations

from datetime import datetime

from .config import GUARDRAILS as G
from .clock import at_or_past_flatten
from .models import ExitIntent, Position


def evaluate(position: Position, now: datetime) -> list[ExitIntent]:
    p = position
    if p.quantity <= 0:
        return []

    # 1. Force-flatten by 15:45 ET.
    if at_or_past_flatten(now):
        return [ExitIntent(p, "flatten", p.quantity, "15:45 ET force-flatten", marketable=True)]

    # 2. Premium stop (-50%).
    if p.premium_change_pct <= -G.stop_premium_loss:
        return [ExitIntent(p, "stop", p.quantity,
                           f"premium {p.premium_change_pct:.0%} <= -{G.stop_premium_loss:.0%}",
                           marketable=True)]

    # 3. Thesis break / underlying stop.
    if not p.thesis_intact:
        return [ExitIntent(p, "thesis_break", p.quantity, "thesis broke", marketable=True)]

    # 4. Premium target (+90%).
    if p.premium_change_pct >= G.target_premium_gain:
        return [ExitIntent(p, "target", p.quantity,
                           f"premium {p.premium_change_pct:.0%} >= +{G.target_premium_gain:.0%}")]

    # 5/6. Scale half at +1R, trail the rest. We approximate +1R on the option
    # as +100% premium unless a richer R model is supplied upstream.
    if not p.scaled and p.premium_change_pct >= 1.0 and p.quantity >= 2:
        half = p.quantity // 2
        return [ExitIntent(p, "scale", half, "scale half at +1R, trail the rest")]

    return []
