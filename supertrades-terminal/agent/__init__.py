"""SuperTrades execution agent.

Decision/risk brain for the SuperTrades 0DTE options system, wired to the
Robinhood Agentic Trading MCP. This package makes the *decisions* (scan ->
risk gate -> contract -> order intent -> exits) and enforces every guardrail
from the design handoff's GO-LIVE.md in exactly one place (``risk_governor``).

Safety model (do not weaken):
  * DRY_RUN is the default. Nothing is ever sent to a live account unless the
    operator explicitly arms the agent AND wires a real ``mcp_call`` dispatcher.
  * Every *entry* order is previewed and requires explicit human approval
    before it can be placed (preview-every-order).
  * The agent may only ever open long calls/puts, disarm, or flatten. It never
    widens a stop, averages down, or routes around the account isolation.

This module deliberately does NOT contain a live ``mcp_call`` implementation.
Going live is a human step: fund the Agentic account, get options Level 2,
wire the dispatcher, and arm. See agent/README.md.
"""

from .config import GUARDRAILS, WATCHLIST, RuntimeConfig
from .models import (
    AccountState,
    ContractChoice,
    Decision,
    ExitIntent,
    OrderIntent,
    Position,
    RiskVerdict,
    Signal,
)

__all__ = [
    "GUARDRAILS",
    "WATCHLIST",
    "RuntimeConfig",
    "AccountState",
    "ContractChoice",
    "Decision",
    "ExitIntent",
    "OrderIntent",
    "Position",
    "RiskVerdict",
    "Signal",
]
