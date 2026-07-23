"""Broker interface + result types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..models import AccountState, ChainSnapshot, OrderIntent, Position


@dataclass
class ReviewResult:
    ok: bool
    quote: dict = field(default_factory=dict)
    alerts: list[str] = field(default_factory=list)   # order_checks, surfaced verbatim
    fees: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class PlaceResult:
    placed: bool                 # True only if a live order was actually dispatched
    dry_run: bool                # True if simulated (nothing sent)
    order_id: str = ""
    detail: dict = field(default_factory=dict)
    error: str = ""


class BrokerAdapter(ABC):
    """Reads are always allowed. ``place_order`` is the only mutating call and
    is gated by the concrete driver (dry-run / arm / account eligibility)."""

    @abstractmethod
    def get_account(self) -> AccountState: ...

    @abstractmethod
    def get_positions(self) -> list[Position]: ...

    @abstractmethod
    def get_chain(self, symbol: str) -> ChainSnapshot: ...

    @abstractmethod
    def review_order(self, intent: OrderIntent) -> ReviewResult: ...

    @abstractmethod
    def place_order(self, intent: OrderIntent) -> PlaceResult: ...

    @abstractmethod
    def cancel_all(self) -> None: ...
