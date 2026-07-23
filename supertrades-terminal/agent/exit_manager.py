"""Exit manager.

Exits stay live even when the session is halted for new entries. For each open
position, in priority order:

  1. 15:45 ET force-flatten (never hold 0DTE to the bell).
  2. Premium stop: mark <= -50% of entry premium -> close immediately (marketable).
  3. Thesis break, or underlying hit the stop -> close immediately (marketable).
  4. Premium target: mark >= +90% -> sell to close.
  5. Underlying hit target -> sell to close.
  6. Scale half at +1R (once), then trail the runner.

Two exit modes, chosen by ``RuntimeConfig.scale_and_trail`` (default off):

  * OFF (default) — the +90% premium target closes the WHOLE position. Simple,
    banks the base hit, and is exactly the historical behavior.
  * ON — after +1R the position scales half off and the runner is protected by a
    trailing stop that gives back at most ``trail_give_back_pct`` from its peak
    mark, letting a winner run past +90% while locking in profit. Mirrors the
    terminal's "Auto-scale out at +1R" switch.

Never widens a stop: the fixed -50% premium stop, thesis break, and 15:45
flatten are always the floor, and the trail only ratchets up.
"""

from __future__ import annotations

from datetime import datetime

from .config import GUARDRAILS as G
from .config import RuntimeConfig
from .clock import at_or_past_flatten
from .models import ExitIntent, Position


def evaluate(
    position: Position,
    now: datetime,
    cfg: RuntimeConfig | None = None,
) -> list[ExitIntent]:
    p = position
    if p.quantity <= 0:
        return []
    scale_and_trail = bool(cfg and cfg.scale_and_trail)

    # 1. Force-flatten by 15:45 ET.
    if at_or_past_flatten(now):
        return [ExitIntent(p, "flatten", p.quantity, "15:45 ET force-flatten", marketable=True)]

    # 2. Premium stop (-50%). Always the hard floor, in both modes.
    if p.premium_change_pct <= -G.stop_premium_loss:
        return [ExitIntent(p, "stop", p.quantity,
                           f"premium {p.premium_change_pct:.0%} <= -{G.stop_premium_loss:.0%}",
                           marketable=True)]

    # 3. Thesis break / underlying stop.
    if not p.thesis_intact:
        return [ExitIntent(p, "thesis_break", p.quantity, "thesis broke", marketable=True)]

    # 4. Premium target (+90%). In trail mode we do NOT hard-close the whole
    #    position here — we let it scale + trail so the runner can go further.
    if not scale_and_trail and p.premium_change_pct >= G.target_premium_gain:
        return [ExitIntent(p, "target", p.quantity,
                           f"premium {p.premium_change_pct:.0%} >= +{G.target_premium_gain:.0%}")]

    # 5. Scale half at +1R (once). We approximate +1R on the option as +100%
    #    premium unless a richer R model is supplied upstream.
    if not p.scaled and p.premium_change_pct >= 1.0 and p.quantity >= 2:
        half = p.quantity // 2
        return [ExitIntent(p, "scale", half, "scale half at +1R, trail the rest")]

    # 6. Trailing stop on the runner (trail mode only). Armed once the mark has
    #    reached the activation gain; exits the remainder when it gives back
    #    trail_give_back_pct from the peak mark seen. Only ever tightens.
    if scale_and_trail and p.premium_change_pct >= G.trail_activate_gain:
        peak = p.effective_peak
        trail_level = peak * (1.0 - G.trail_give_back_pct)
        if p.current_premium <= trail_level:
            give_back = (peak - p.current_premium) / peak if peak > 0 else 0.0
            return [ExitIntent(p, "trail", p.quantity,
                               f"trailing stop: gave back {give_back:.0%} from peak "
                               f"${peak:.2f} (mark ${p.current_premium:.2f})",
                               marketable=True)]

    return []
