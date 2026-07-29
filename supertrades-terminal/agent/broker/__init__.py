"""Broker adapters. ``BrokerAdapter`` is the interface the engine speaks;
concrete drivers (Robinhood Agentic MCP, in-memory paper) implement it."""

from .base import BrokerAdapter, PlaceResult, ReviewResult
from .mcp_dispatch import (
    McpDispatchError,
    McpDispatcher,
    RobinhoodMcpHttpTransport,
    live_dispatcher,
)
from .paper import PaperBroker
from .robinhood_mcp import RobinhoodMcpBroker

__all__ = [
    "BrokerAdapter",
    "PlaceResult",
    "ReviewResult",
    "PaperBroker",
    "RobinhoodMcpBroker",
    "McpDispatcher",
    "McpDispatchError",
    "RobinhoodMcpHttpTransport",
    "live_dispatcher",
]
