"""Exit manager.

Exits stay live even when the session is halted for new entries. Three exit
engines, chosen by ``RuntimeConfig.exit_mode``:

  * "ladder" (DEFAULT, operator-approved 2026-08-04) — the five-stage peak
    ladder. Stages ARM when the position's peak mark touches +25% / +45% /
    +70% / +90% of entry; once armed, the exit line for the remainder is a
    max(leash x peak, floor x entry) ratchet that can only rise:

        peak touch      exit line                       locks
        +25%            entry                           breakeven
        +45%            max(0.65 x peak, 1.05 x entry)  >= +5%
        +70%            max(0.75 x peak, 1.35 x entry)  >= +35%
        +90% (target)   max(0.70 x peak, 1.60 x entry)  >= +60%

    Lot-aware tranches bank profit on the way up: 3+ lots sell one at the
    +45% arm touch, 2+ lots sell one at the target touch, and the last lot
    always trails — so a winner is never fully closed into strength, and a
    fade never round-trips a real gain (operator: "maximize profits even if
    target not hit", "do not paperhand").

  * "target" — historical behavior: the +90% premium target closes the WHOLE
    position.

  * "scale_trail" — legacy switch behavior: scale half at +1R, then a 30%
    peak-give-back trail on the runner. ``RuntimeConfig.scale_and_trail=True``
    with exit_mode left at its default is honored as this mode.

In every mode the fixed -50% premium stop, thesis break, and 15:45 flatten are
the non-negotiable floor, and lines only ever ratchet up — never widened.

Single-owner rule (operator-approved 2026-08-04): the ladder and tranches run
only for positions this engine OWNS (``Position.owner == "engine"``). For
watcher-/external-owned positions the engine applies backstops only (flatten,
stop, thesis break) so two managers never walk orders on one position.
"""

from __future__ import annotations

from datetime import datetime

from .config import GUARDRAILS as G
from .config import RuntimeConfig
from .clock import at_or_past_flatten
from .models import ExitIntent, Position


def _resolve_mode(cfg: RuntimeConfig | None) -> str:
    if cfg is None:
        return "ladder"
    mode = cfg.exit_mode or "ladder"
    # Back-compat: the old switch, set explicitly while exit_mode was left at
    # its default, means the caller wants the legacy scale+trail behavior.
    if mode == "ladder" and cfg.scale_and_trail:
        return "scale_trail"
    return mode


def ladder_line(position: Position) -> tuple[float, str]:
    """The armed exit line for ``position`` under the five-stage ladder, and
    the stage name that set it. (0.0, "") when no stage has armed. The line is
    monotone in the peak: within a stage both terms only rise with the peak,
    and each stage's floor clears the previous stage's line at the arm point."""
    entry = position.entry_premium
    if entry <= 0:
        return 0.0, ""
    peak = position.effective_peak
    peak_gain = (peak - entry) / entry
    if peak_gain >= G.ladder_s2_arm:
        return (max((1.0 - G.ladder_s2_give) * peak,
                    (1.0 + G.ladder_s2_floor) * entry), "runner")
    if peak_gain >= G.ladder_s15_arm:
        return (max((1.0 - G.ladder_s15_give) * peak,
                    (1.0 + G.ladder_s15_floor) * entry), "target-approach")
    if peak_gain >= G.ladder_s1_arm:
        return (max((1.0 - G.ladder_s1_give) * peak,
                    (1.0 + G.ladder_s1_floor) * entry), "profit-protect")
    if peak_gain >= G.ladder_guard_arm:
        return entry, "breakeven-guard"
    return 0.0, ""


def _ladder_exits(p: Position) -> list[ExitIntent]:
    entry = p.entry_premium
    peak_gain = ((p.effective_peak - entry) / entry) if entry > 0 else 0.0

    # Armed line first: if the CURRENT mark is at/under it, protect everything
    # that remains. (Peaks/arms may ratchet on wick highs upstream; the exit
    # decision itself always uses the polled mark passed in current_premium.)
    line, stage = ladder_line(p)
    if line > 0.0 and p.current_premium <= line:
        kind = "guard" if stage == "breakeven-guard" else "trail"
        return [ExitIntent(p, kind, p.quantity,
                           f"{stage}: mark ${p.current_premium:.2f} <= line ${line:.2f} "
                           f"(peak ${p.effective_peak:.2f})",
                           marketable=True)]

    # Tranches bank profit into strength on arm TOUCHES, one lot at a time,
    # and never touch the last lot — it always trails.
    if p.quantity >= 3 and not p.tranche_s1_done and peak_gain >= G.ladder_s1_arm:
        return [ExitIntent(p, "tranche", 1,
                           f"+{G.ladder_s1_arm:.0%} arm touched — bank one lot, "
                           f"trail the rest")]
    if p.quantity >= 2 and not p.tranche_target_done and peak_gain >= G.ladder_s2_arm:
        return [ExitIntent(p, "tranche", 1,
                           f"target +{G.ladder_s2_arm:.0%} touched — bank one lot, "
                           f"runner trails")]
    return []


def evaluate(
    position: Position,
    now: datetime,
    cfg: RuntimeConfig | None = None,
) -> list[ExitIntent]:
    p = position
    if p.quantity <= 0:
        return []
    mode = _resolve_mode(cfg)

    # 1. Force-flatten by 15:45 ET. Backstop — applies to every position.
    if at_or_past_flatten(now):
        return [ExitIntent(p, "flatten", p.quantity, "15:45 ET force-flatten", marketable=True)]

    # 2. Premium stop (-50%). Always the hard floor, in every mode, every owner.
    if p.premium_change_pct <= -G.stop_premium_loss:
        return [ExitIntent(p, "stop", p.quantity,
                           f"premium {p.premium_change_pct:.0%} <= -{G.stop_premium_loss:.0%}",
                           marketable=True)]

    # 3. Thesis break / underlying stop. Backstop.
    if not p.thesis_intact:
        return [ExitIntent(p, "thesis_break", p.quantity, "thesis broke", marketable=True)]

    # Single-owner rule: beyond the backstops above, only the owner runs the
    # ladder/target/trail logic for this position.
    if p.owner not in ("engine", ""):
        return []

    if mode == "ladder":
        return _ladder_exits(p)

    # 4. Premium target (+90%). In trail mode we do NOT hard-close the whole
    #    position here — we let it scale + trail so the runner can go further.
    if mode != "scale_trail" and p.premium_change_pct >= G.target_premium_gain:
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
    if mode == "scale_trail" and p.premium_change_pct >= G.trail_activate_gain:
        peak = p.effective_peak
        trail_level = peak * (1.0 - G.trail_give_back_pct)
        if p.current_premium <= trail_level:
            give_back = (peak - p.current_premium) / peak if peak > 0 else 0.0
            return [ExitIntent(p, "trail", p.quantity,
                               f"trailing stop: gave back {give_back:.0%} from peak "
                               f"${peak:.2f} (mark ${p.current_premium:.2f})",
                               marketable=True)]

    return []
