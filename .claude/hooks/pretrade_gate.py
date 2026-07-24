#!/usr/bin/env python3
"""PreToolUse gate for Robinhood options placement.

Wired in .claude/settings.json to fire before place_option_order /
cancel_option_order. It is a thin stdin/stdout wrapper around the deterministic
`decide()` in supertrades-terminal/agent/go_live.py:

  * hard **deny** on a kill switch, a non-armed stage, a market/stop entry, or an
    over-cap order — before the human is ever asked;
  * **ask** (with the full order shown) for a permitted live entry or any close,
    so the operator's final arm is always required;
  * **fail closed** — any error (bad payload, missing module) denies.

It never emits "allow": a live order is never auto-approved here.
"""

import json
import os
import sys
import importlib.util


def _emit(decision: str, reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))


def _load_decider():
    repo = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    path = os.path.join(repo, "supertrades-terminal", "agent", "go_live.py")
    spec = importlib.util.spec_from_file_location("_supertrades_go_live", path)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec: dataclasses with `from __future__ import annotations`
    # resolve their module via sys.modules during class creation.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (ValueError, OSError):
        _emit("deny", "pre-trade gate: unreadable hook payload — denying (fail-closed).")
        return 0

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {}) or {}

    try:
        go_live = _load_decider()
        decision, reason = go_live.decide(tool_name, tool_input)
        stage = go_live.load_stage()
    except Exception as exc:  # noqa: BLE001 — a gate must never crash open
        _emit("deny", f"pre-trade gate: internal error ({exc!r}) — denying (fail-closed).")
        return 0

    # Echo the exact order + stage to stderr so the operator sees precisely what
    # would hit the wire (never a summary), per OWASP MCP guidance.
    sys.stderr.write(
        f"[pre-trade gate] stage={stage.name} kill={go_live.kill_engaged()} "
        f"decision={decision.upper()}\n  tool={tool_name}\n"
        f"  order={json.dumps(tool_input, ensure_ascii=False)}\n  why={reason}\n"
    )
    _emit(decision, reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
