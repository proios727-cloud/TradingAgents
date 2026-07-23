#!/usr/bin/env python3
"""PostToolUse audit logger for the Robinhood MCP.

Wired in .claude/settings.json to fire after every mcp__Robinhood_Trading__*
call. Appends one JSON line per call to <SUPERTRADES_HOME>/audit.jsonl — a
grounded, timestamped record of exactly what tools ran with what parameters,
which the research flagged as the only trustworthy account of an agent's
actions (the model's own narrative is not). Never blocks the tool: any failure
here is swallowed so auditing can't break execution.
"""

import json
import os
import sys
from datetime import datetime, timezone


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0  # nothing to log; never block

    repo = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    home = os.environ.get(
        "SUPERTRADES_HOME",
        os.path.join(repo, "supertrades-terminal", ".supertrades"),
    )
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event.get("hook_event_name", "PostToolUse"),
        "tool": event.get("tool_name", ""),
        "input": event.get("tool_input", {}),
        "response": event.get("tool_response", {}),
    }
    try:
        os.makedirs(home, exist_ok=True)
        with open(os.path.join(home, "audit.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass  # audit is best-effort; never fail the tool
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
