"""In-memory paper broker — deterministic, no network, no money.

Used for dry-run cycles and the rail-test suite. Fills limit orders instantly
at the limit price and tracks positions. Never touches a real account.
"""

from __future__ import annotations

from ..models import AccountState, ChainSnapshot, OrderIntent, Position
from .base import BrokerAdapter, PlaceResult, ReviewResult


class PaperBroker(BrokerAdapter):
    def __init__(
        self,
        account: AccountState,
        chains: dict[str, ChainSnapshot] | None = None,
        positions: list[Position] | None = None,
    ):
        self._account = account
        self._chains = chains or {}
        self._positions = list(positions or [])
        self.placed: list[OrderIntent] = []   # audit of everything "filled"

    def get_account(self) -> AccountState:
        return self._account

    def get_positions(self) -> list[Position]:
        return [p for p in self._positions if p.quantity > 0]

    def get_chain(self, symbol: str) -> ChainSnapshot:
        return self._chains[symbol]

    def review_order(self, intent: OrderIntent) -> ReviewResult:
        return ReviewResult(ok=True, quote={"mark_price": intent.limit_price})

    def place_order(self, intent: OrderIntent) -> PlaceResult:
        # Paper fills are always simulated (dry_run True) — never a live order.
        self.placed.append(intent)
        cost = intent.limit_price * 100 * intent.quantity
        if intent.position_effect == "open":
            self._account.settled_cash -= cost
            self._account.open_premium += cost
        else:
            self._account.settled_cash += cost  # settles T+1 in reality; instant here
            self._account.open_premium = max(0.0, self._account.open_premium - cost)
            # Instant fill also reduces the position — without this, engine
            # cycles would re-see full quantity after every close and the
            # exit path could never be exercised end-to-end in tests.
            for p in self._positions:
                if p.option_id == intent.option_id and p.quantity > 0:
                    p.quantity = max(0, p.quantity - intent.quantity)
                    break
        return PlaceResult(placed=False, dry_run=True,
                           order_id=f"paper-{len(self.placed)}",
                           detail={"filled_at": intent.limit_price})

    def cancel_all(self) -> None:
        return
