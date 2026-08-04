"""Wiring the engine to the live Robinhood Trading MCP.

The broker needs an ``mcp_call(tool, params) -> dict``. Two ways to provide it:

  * **Claude-Code-driven (recommended, and what the broker's read-schema was
    validated against live):** Claude holds the RH MCP connection and makes the
    tool calls, gated by the PreToolUse approval hook. The engine computes
    OrderIntents; Claude dispatches them. Pass that bridge as ``mcp_call``.
  * **Headless:** a standalone process speaks MCP over HTTP to the RH endpoint
    with a bearer token from the desktop OAuth flow. ``HttpMcpDispatcher`` is
    that path. It **fails closed** (raises) with no token and **refuses
    order-placing tools** unless explicitly allowed to write.

``build_broker(cfg)`` picks the safe default: an **inert** broker (no dispatcher)
unless a token is configured — so nothing can reach a live account by accident.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Callable, Optional

from .config import RuntimeConfig
from .broker.robinhood_mcp import RobinhoodMcpBroker

DEFAULT_MCP_URL = "https://agent.robinhood.com/mcp/trading"

# Tools that mutate the account — never dispatched read-only.
WRITE_TOOLS = frozenset({
    "place_option_order", "cancel_option_order", "replace_option_order",
    "place_equity_order", "cancel_equity_order",
})


class HttpMcpDispatcher:
    """Minimal MCP-over-HTTP JSON-RPC dispatcher with a read-only guard.

    The network transport is injectable so the guard/marshalling can be tested
    without a live endpoint. The full request round-trip requires a real bearer
    token from the desktop OAuth flow — this class supplies the shape; the token
    is the operator's go-live credential.
    """

    def __init__(self, url: str, token: str, *, allow_write: bool = False,
                 transport: Optional[Callable[[dict], dict]] = None, timeout: float = 15.0):
        if not token:
            raise RuntimeError("no Robinhood MCP token — dispatcher inert (fail-closed)")
        self.url = url
        self._token = token
        self.allow_write = allow_write
        self._transport = transport or self._http_post
        self.timeout = timeout
        self._id = 0

    def __call__(self, tool: str, params: dict) -> dict:
        if tool in WRITE_TOOLS and not self.allow_write:
            raise PermissionError(
                f"{tool} blocked — dispatcher is read-only (allow_write=False). "
                f"Arming a live dispatcher is a deliberate operator step."
            )
        self._id += 1
        req = {"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
               "params": {"name": tool, "arguments": params}}
        return _unwrap(self._transport(req))

    def _http_post(self, req: dict) -> dict:
        body = json.dumps(req).encode("utf-8")
        r = urllib.request.Request(
            self.url, data=body, method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {self._token}",
            },
        )
        with urllib.request.urlopen(r, timeout=self.timeout) as f:  # noqa: S310 — fixed https endpoint
            return json.loads(f.read().decode("utf-8"))


def _unwrap(resp: dict) -> dict:
    """Pull the tool payload out of a JSON-RPC / MCP tools-call envelope."""
    if not isinstance(resp, dict):
        return {}
    if resp.get("error"):
        raise RuntimeError(f"MCP error: {resp['error']}")
    result = resp.get("result", resp)
    if isinstance(result, dict):
        if "structuredContent" in result:
            return result["structuredContent"]
        content = result.get("content")
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    try:
                        return json.loads(c.get("text", "{}"))
                    except ValueError:
                        return {"data": c.get("text")}
        return result
    return {}


def build_broker(cfg: RuntimeConfig, mcp_call: Optional[Callable[[str, dict], dict]] = None,
                 *, allow_write: Optional[bool] = None) -> RobinhoodMcpBroker:
    """Build a broker with the safe default: inert unless a dispatcher/token is
    wired. ``allow_write`` defaults to ``cfg.can_place_live()`` — read-only until
    the operator arms."""
    if mcp_call is not None:
        return RobinhoodMcpBroker(cfg, mcp_call)
    token = os.environ.get("ROBINHOOD_AGENT_TOKEN")
    if not token:
        return RobinhoodMcpBroker(cfg, None)  # inert — cannot reach a live account
    url = os.environ.get("ROBINHOOD_MCP_URL", DEFAULT_MCP_URL)
    write = cfg.can_place_live() if allow_write is None else allow_write
    return RobinhoodMcpBroker(cfg, HttpMcpDispatcher(url, token, allow_write=write))


def preflight(broker, *, want_levels=("option_level_2", "option_level_3")):
    """Go/no-go check before ``tiny_live``: agentic-accessible, options-approved,
    and has buying power. Returns ``(ok, reasons, account)``."""
    try:
        acct = broker.get_account()
    except Exception as e:  # noqa: BLE001 — surface as a soft no-go
        return False, [f"cannot read account: {e}"], None
    reasons: list[str] = []
    if not acct.agentic_allowed:
        reasons.append("account is not agentic_allowed (not accessible to this agent)")
    if acct.option_level not in want_levels:
        reasons.append(f"option level {acct.option_level!r} is below Level 2")
    if acct.settled_cash <= 0:
        reasons.append("no settled buying power")
    return (not reasons), reasons, acct
