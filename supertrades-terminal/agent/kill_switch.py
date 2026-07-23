"""Kill switch — emergency halt, independent of the entry guardrails.

Any one of these fires a full stop: cancel all working orders, flatten all
positions, and halt for the day. Checked every cycle, before anything else.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .config import GUARDRAILS as G


@dataclass
class KillState:
    user_stop: bool = False              # operator said "STOP"
    mcp_error: bool = False              # any MCP/broker error this cycle
    last_data_ts: datetime | None = None  # timestamp of freshest data
    consecutive_losses: int = 0


@dataclass
class KillDecision:
    triggered: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.triggered


def check(state: KillState, now: datetime) -> KillDecision:
    if state.user_stop:
        return KillDecision(True, "operator STOP")
    if state.mcp_error:
        return KillDecision(True, "MCP/broker error")
    if state.last_data_ts is not None:
        age = (now - state.last_data_ts).total_seconds()
        if age > G.stale_data_seconds:
            return KillDecision(True, f"data stale {age:.0f}s > {G.stale_data_seconds:.0f}s")
    if state.consecutive_losses >= G.consecutive_loss_kill:
        return KillDecision(True, f"{state.consecutive_losses} consecutive losses")
    return KillDecision(False)
