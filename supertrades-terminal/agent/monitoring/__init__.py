"""Live-session monitoring and efficacy scoring for the Agentic account.

This package is the *observer* side of the agent: it never places, sizes, or
cancels an order. It ingests raw Robinhood MCP snapshots (orders, positions,
portfolio) captured by the monitoring loop, reconstructs the session's round
trips, grades them against the Guardrails in ``agent.config`` — the same limits
``risk_governor`` enforces prospectively — and emits an adherence/efficacy
report plus data-driven tuning recommendations.

Recommendations are advisory only. Guardrails are "risk limits, not tunables"
(config.py): nothing in this package mutates them.
"""

from .scorer import Snapshot, SessionScore, load_snapshot, score_snapshot

__all__ = ["Snapshot", "SessionScore", "load_snapshot", "score_snapshot"]
