"""Simulated signal source + paper environment for dry runs.

Mirrors the terminal's ``data.js`` fixtures (the NVDA squeeze and TSLA
gamma-flip signals) so a dry-run cycle reproduces what the dashboard shows,
end-to-end through the real decision path — without any live data or account.
"""

from __future__ import annotations

from datetime import date, datetime

from .models import (
    AccountState,
    ChainSnapshot,
    OptionContract,
    Signal,
)


class SimulatedSignalSource:
    def __init__(self, session: date):
        self.session = session

    def fired_signals(self, now: datetime) -> list[Signal]:
        return [
            Signal(symbol="NVDA", direction="long", strategy="Squeeze confluence · 5m",
                   entry=202.10, stop=201.75, target=202.90, time="14:32:07",
                   setup_fired=True, rvol=2.1, index_aligned=True,
                   structural_level_near_stop=True, confidence=82),
            Signal(symbol="TSLA", direction="short", strategy="Gamma flip break · 1m",
                   entry=403.40, stop=404.90, target=399.60, time="14:27:44",
                   setup_fired=True, rvol=1.8, index_aligned=True,
                   structural_level_near_stop=True, confidence=71),
        ]

    def earnings_symbols(self, now: datetime) -> frozenset[str]:
        # Hyperscaler week per data.js EARNINGS — these names are blocked.
        return frozenset({"GOOGL", "META", "MSFT", "AMZN", "TSLA"})


def demo_account(account_number: str = "AGENTIC-DEMO") -> AccountState:
    return AccountState(
        account_number=account_number, agentic_allowed=True,
        option_level="option_level_2", balance=25000.0,
        settled_cash=25000.0, unsettled_cash=0.0,
    )


def demo_chains(session: date) -> dict[str, ChainSnapshot]:
    def c(sym, otype, strike, bid, ask, delta, gamma=0.0):
        return OptionContract(f"{sym}-{otype}-{strike}", sym, otype, strike,
                              session, bid, ask, delta, gamma)
    return {
        "NVDA": ChainSnapshot("NVDA", session, [
            c("NVDA", "call", 202.5, 1.18, 1.24, 0.49, 0.055),
            c("NVDA", "call", 205.0, 0.61, 0.66, 0.34, 0.070),
        ]),
        "TSLA": ChainSnapshot("TSLA", session, [
            c("TSLA", "put", 402.5, 2.40, 2.55, 0.47, 0.030),
            c("TSLA", "put", 400.0, 1.30, 1.42, 0.33, 0.042),
        ]),
    }
