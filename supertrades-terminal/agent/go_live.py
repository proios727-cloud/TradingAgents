"""Staged go-live ladder + the deterministic pre-trade gate.

This is the bridge between the decision brain (which *assumes* a human arms every
entry) and a real Robinhood Agentic MCP connection (which does **not** enforce
that — order-approval is optional at Robinhood's layer). It gives you:

  * a **stage ladder** — preview → paper → tiny_live → scaled — each with hard,
    machine-checkable caps, so "going live" is a deliberate one-notch move, not a
    flag someone flips to 100%; and
  * ``decide()`` — a pure, deterministic admissibility gate the PreToolUse hook
    calls before any ``place_option_order`` reaches the wire. It never returns
    "allow": a live *entry* is at most "ask" (the human still arms it), and any
    cap/kill/shape violation is a hard "deny".

Design rules (match the rest of the agent):
  * **Fail safe.** No stage file -> preview (nothing live). Any parse error ->
    the caller denies.
  * **Exits are never blocked.** Closing/selling and cancels always fall through
    to a human "ask" — even during a kill — because you must always be able to
    get flat.
  * **Deterministic, not probabilistic.** Caps are dollar/contract limits and a
    kill file, never a model confidence score.

Pure stdlib and no relative imports on purpose, so the hook can load this file
directly without importing the whole ``agent`` package.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path

GATED_PLACE = "place_option_order"
GATED_CANCEL = "cancel_option_order"


@dataclass(frozen=True)
class Stage:
    """One rung of the go-live ladder. Caps of 0 mean 'no extra cap here' —
    ``scaled`` defers entirely to the risk governor's own 2.5%/$1k sizing."""

    name: str
    dry_run: bool          # True => the engine never dispatches a live order
    armed: bool            # False => the gate denies every live entry outright
    max_premium_usd: float # 0 => no stage cap (scaled); else hard per-entry cap
    max_contracts: int     # 0 => no stage cap; else hard per-entry contract cap
    note: str = ""


# The ladder. Climb ONE rung at a time, and only after the rung below has proven
# itself. preview/paper never arm; tiny_live is real money with a deliberately
# tiny cap; scaled hands sizing back to the risk governor.
STAGES: dict[str, Stage] = {
    "preview":   Stage("preview",   dry_run=True,  armed=False, max_premium_usd=0.0,    max_contracts=0,
                        note="Analysis + review_option_order only. No orders, ever."),
    "paper":     Stage("paper",     dry_run=True,  armed=False, max_premium_usd=0.0,    max_contracts=0,
                        note="Full decision path on the PaperBroker. Still no live order."),
    "tiny_live": Stage("tiny_live", dry_run=False, armed=True,  max_premium_usd=75.0,   max_contracts=1,
                        note="Real money, one contract, <=$75 premium/entry. Prove fills are real."),
    "scaled":    Stage("scaled",    dry_run=False, armed=True,  max_premium_usd=1000.0, max_contracts=0,
                        note="Sizing governed by the risk gate (phase ladder, $1k cap). Only after tiny_live is boring."),
}
LADDER = ["preview", "paper", "tiny_live", "scaled"]
DEFAULT_STAGE = "preview"

_RUNTIME_DIR = Path(os.environ.get("SUPERTRADES_HOME",
                                   str(Path(__file__).resolve().parent.parent / ".supertrades")))
STAGE_FILE = _RUNTIME_DIR / "stage.json"
KILL_FILE = _RUNTIME_DIR / "KILL"


# -- stage state -----------------------------------------------------------

def load_stage() -> Stage:
    """Active stage, or preview (safest) if unset/unreadable."""
    try:
        name = json.loads(STAGE_FILE.read_text(encoding="utf-8")).get("name")
    except (OSError, ValueError):
        return STAGES[DEFAULT_STAGE]
    return STAGES.get(name, STAGES[DEFAULT_STAGE])


def set_stage(name: str) -> Stage:
    """Pin the active stage. Raises on an unknown stage name."""
    if name not in STAGES:
        raise ValueError(f"unknown stage {name!r}; choose one of {LADDER}")
    stage = STAGES[name]
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_FILE.write_text(json.dumps(asdict(stage), indent=2), encoding="utf-8")
    return stage


def kill_engaged() -> bool:
    return KILL_FILE.exists()


def engage_kill(reason: str = "manual") -> None:
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    KILL_FILE.write_text(reason, encoding="utf-8")


def clear_kill() -> None:
    KILL_FILE.unlink(missing_ok=True)


# -- the gate --------------------------------------------------------------

def _leg(tool_input: dict) -> dict:
    legs = tool_input.get("legs") or []
    return legs[0] if legs and isinstance(legs[0], dict) else {}


def _is_closing(tool_input: dict) -> bool:
    leg = _leg(tool_input)
    return leg.get("position_effect") == "close" or leg.get("side") == "sell"


def decide(tool_name: str, tool_input: dict,
           stage: Stage | None = None, killed: bool | None = None) -> tuple[str, str]:
    """Return ("deny"|"ask", reason) for a gated order tool. Never "allow": a
    permitted live entry is still handed to the human as "ask". Fail closed —
    an unrecognized shape denies."""
    stage = stage if stage is not None else load_stage()
    killed = kill_engaged() if killed is None else killed
    tool_input = tool_input or {}

    short = tool_name.rsplit("__", 1)[-1]  # strip mcp__<server>__ prefix if present

    # Cancels reduce exposure -> always let the human confirm, never stage-block.
    if short == GATED_CANCEL:
        return "ask", "Cancel an open order — confirm. (Cancels are never stage-blocked.)"

    if short != GATED_PLACE:
        return "deny", f"Unrecognized gated tool {tool_name!r}; manual review required."

    # Closing an existing position is protective — always available, even in a
    # non-armed stage and even under a kill (you must be able to get flat).
    if _is_closing(tool_input):
        leg = _leg(tool_input)
        return "ask", (f"Closing order ({leg.get('side')}/{leg.get('position_effect')}) — "
                       f"exits stay available. Confirm.")

    # --- from here: opening a NEW long entry ---
    if killed:
        return "deny", "KILL switch engaged — no new entries."
    if not stage.armed:
        return "deny", (f"Stage '{stage.name}' is not armed for live entries "
                        f"(preview/paper). No live order will be placed.")

    otype = str(tool_input.get("type") or "limit").lower()
    if otype != "limit":
        return "deny", (f"Stage '{stage.name}' allows only LIMIT entries (got '{otype}') — "
                        f"market/stop entries can't be cost-capped.")
    try:
        qty = int(tool_input.get("quantity") or 0)
        price = float(tool_input.get("price") or 0)
    except (TypeError, ValueError):
        return "deny", "Unparseable quantity/price on a limit entry."
    if qty <= 0 or price <= 0:
        return "deny", f"Invalid entry (qty={qty}, price={price})."

    premium = qty * price * 100.0
    if stage.max_contracts and qty > stage.max_contracts:
        return "deny", f"{qty} contracts > stage '{stage.name}' cap of {stage.max_contracts}."
    if stage.max_premium_usd and premium > stage.max_premium_usd:
        return "deny", (f"Est. premium ${premium:,.0f} > stage '{stage.name}' cap "
                        f"${stage.max_premium_usd:,.0f}.")

    return "ask", (f"LIVE ENTRY [{stage.name}]: buy {qty}× @ ${price:.2f} "
                   f"≈ ${premium:,.0f} premium. Arm this order?")


# -- tiny CLI --------------------------------------------------------------

def _main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "status"
    if cmd == "status":
        s = load_stage()
        print(f"stage: {s.name}  (armed={s.armed}, dry_run={s.dry_run}, "
              f"cap=${s.max_premium_usd:.0f}/{s.max_contracts or '∞'} contracts)")
        print(f"kill:  {'ENGAGED' if kill_engaged() else 'clear'}")
        print(f"note:  {s.note}")
        print(f"file:  {STAGE_FILE}")
    elif cmd == "set" and len(argv) > 1:
        s = set_stage(argv[1])
        print(f"stage set -> {s.name} ({s.note})")
    elif cmd == "kill":
        engage_kill(argv[1] if len(argv) > 1 else "manual")
        print("KILL engaged — new entries denied until cleared.")
    elif cmd == "clear-kill":
        clear_kill()
        print("KILL cleared.")
    else:
        print("usage: python -m agent.go_live [status | set <stage> | kill [reason] | clear-kill]")
        print(f"stages: {LADDER}")
        return 2
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(_main(sys.argv[1:]))
