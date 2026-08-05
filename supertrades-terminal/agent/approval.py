"""Preview-every-order gate.

Before any ENTRY is placed, the agent renders a preview and asks a human
approver to confirm. The default approver DENIES — nothing is ever placed
without a human explicitly wiring an approve callback and saying yes. This is
the operator's per-order control, on top of the arm/dry-run gates.

For EXITS the same gate is consulted only as an ADVISORY (see engine): the
operator sees the ticket and their answer is journaled, but a protective exit
places regardless — a decline can veto an entry, never an exit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .broker.base import ReviewResult
from .models import OrderIntent


@dataclass
class Preview:
    intent: OrderIntent
    review: ReviewResult

    def render(self) -> str:
        i = self.intent
        lines = [
            f"ORDER PREVIEW ({i.kind}) — {i.symbol}",
            f"  {i.side} {i.quantity}x {i.option_id} @ limit ${i.limit_price:.2f} "
            f"({i.position_effect})",
            f"  reason: {i.reason}",
        ]
        if not self.review.ok:
            lines.append("  !!! BROKER REVIEW FAILED — this order was NOT "
                         "validated by the broker preview !!!")
            lines.append(f"  !!! error: {self.review.error or 'unknown review error'}")
        if self.review.alerts:
            lines.append("  alerts:")
            lines += [f"    - {a}" for a in self.review.alerts]
        lines.append(f"  MCP: {i.mcp_tool or 'place_option_order'} {i.mcp_params or ''}")
        return "\n".join(lines)


# An approver takes a Preview and returns True to place, False to skip.
Approver = Callable[[Preview], bool]


def deny_all(_preview: Preview) -> bool:
    """Default approver: never approve. Safe by construction."""
    return False


class ApprovalGate:
    def __init__(self, approver: Approver = deny_all, *, required: bool = True):
        self.approver = approver
        self.required = required

    def request(self, preview: Preview) -> bool:
        if not self.required:
            return True
        try:
            return bool(self.approver(preview))
        except Exception:  # noqa: BLE001 — a failing approver means "do not place"
            return False
