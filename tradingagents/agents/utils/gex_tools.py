from langchain_core.tools import tool
from typing import Annotated

from tradingagents.dataflows.gex_positioning import get_dealer_positioning_report


@tool
def get_dealer_positioning(
    symbol: Annotated[str, "ticker symbol of the underlying, e.g. SPY, QQQ"],
) -> str:
    """
    Retrieve the option-dealer positioning map (GEX/VEX) for an underlying:
    gamma regime (damping vs amplifying), the zero-gamma flip level, king node,
    call/put walls, air pockets, and the largest per-strike gamma/vanna nodes.
    Built from recorded real option-chain snapshots (open interest, implied
    vol), not from price history — it describes structural support/resistance
    from market-maker hedging that OHLCV-based indicators cannot see.
    Coverage depends on the local snapshot archive (currently index ETFs such
    as SPY); the tool says plainly when no snapshot exists for a symbol.
    Args:
        symbol (str): Underlying ticker, e.g. SPY
    Returns:
        str: A formatted dealer-positioning report, or an explanation of why
        one is unavailable (never raises).
    """
    return get_dealer_positioning_report(symbol)
