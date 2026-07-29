"""Live ``mcp_call`` dispatcher for the Robinhood Agentic Trading MCP.

This is the go-live wiring step from the README ("Wire a real
``mcp_call(tool, params)`` dispatcher into ``RobinhoodMcpBroker``"). It maps the
broker's short tool names onto the ``mcp__Robinhood_Trading__*`` MCP tools and
dispatches them over the MCP server's streamable-HTTP JSON-RPC endpoint.

Safety design — read carefully:

  * **Fail closed, always.** Any MCP error, HTTP failure, timeout, or
    unparseable response raises :class:`McpDispatchError` AND trips the shared
    :class:`~agent.kill_switch.KillState` (``mcp_error=True``) so the next
    engine cycle cancels all, flattens, and halts. Nothing is ever defaulted,
    fabricated, or silently retried.
  * **Reads go direct.** Quotes, chains, positions, orders, account, and the
    non-mutating ``review_option_order`` preview dispatch straight through.
  * **Mutations stay behind the existing gates.** ``place_option_order`` and
    ``cancel_option_order`` are only reachable through
    ``RobinhoodMcpBroker.place_order`` / ``cancel_all``, which enforce the
    dry-run / armed / eligibility gates. As defense in depth — NOT a second
    policy — the dispatcher re-checks ``cfg.can_place_live()`` and refuses to
    put a mutating call on the wire while ``dry_run=True`` or ``armed=False``;
    such an attempt means something bypassed the broker gates, so it also
    trips the kill switch.
  * **Everything else is refused.** Equity orders, option exercise, watchlists
    — any tool this agent has no business calling — never dispatches.
  * **Inert without credentials.** The HTTP transport refuses to construct
    without an OAuth bearer token (``ROBINHOOD_MCP_TOKEN``). No token, no
    connection, no live anything.
"""

from __future__ import annotations

import itertools
import json
import os
import socket
import urllib.error
import urllib.request
from typing import Callable, NoReturn, Optional

from ..config import RuntimeConfig
from ..kill_switch import KillState

# The Robinhood Agentic Trading MCP server, as namespaced by the MCP client.
MCP_TOOL_PREFIX = "mcp__Robinhood_Trading__"
DEFAULT_MCP_URL = "https://agent.robinhood.com/mcp/trading"
URL_ENV = "ROBINHOOD_MCP_URL"
TOKEN_ENV = "ROBINHOOD_MCP_TOKEN"

# Read-only tools (plus the non-mutating order preview): dispatch direct.
READ_TOOLS = frozenset({
    "get_accounts",
    "get_portfolio",
    "get_option_chains",
    "get_option_instruments",
    "get_option_quotes",
    "get_option_positions",
    "get_option_orders",
    "review_option_order",   # preview/validate only — places nothing
})

# Mutating tools this agent uses. ONLY reachable via the broker's gated
# methods; the dispatcher re-verifies cfg.can_place_live() before the wire.
GATED_MUTATIONS = frozenset({
    "place_option_order",
    "cancel_option_order",
})

# Mutating tools this agent must NEVER call, under any configuration.
REFUSED_TOOLS = frozenset({
    "place_equity_order",
    "cancel_equity_order",
    "exercise_option",
    "cancel_option_exercise",
})

_MUTATING_PREFIXES = ("place_", "cancel_", "exercise_", "update_", "create_",
                      "add_", "remove_", "follow_", "unfollow_")


class McpDispatchError(RuntimeError):
    """A failed, refused, or unparseable MCP dispatch. By the time this is
    raised for a live-path failure, the kill switch has been tripped."""


class McpDispatcher:
    """The ``mcp_call(tool, params) -> dict`` callable the broker consumes.

    Wraps a transport (real HTTP, or a fake in tests), classifies every tool,
    fails closed on every error, and shares the engine's ``KillState``.
    """

    def __init__(
        self,
        transport: Callable[[str, dict], object],
        cfg: RuntimeConfig,
        kill_state: KillState,
    ):
        self._transport = transport
        self.cfg = cfg
        self.kill_state = kill_state

    # -- fail closed -------------------------------------------------------
    def _trip(self, reason: str) -> NoReturn:
        self.kill_state.mcp_error = True
        raise McpDispatchError(reason)

    # -- the dispatcher ----------------------------------------------------
    def __call__(self, tool: str, params: dict) -> dict | list:
        short = tool.rsplit("__", 1)[-1]
        full = MCP_TOOL_PREFIX + short

        # Classification first — an unknown or forbidden tool never dispatches.
        if short not in READ_TOOLS and short not in GATED_MUTATIONS:
            if short in REFUSED_TOOLS or short.startswith(_MUTATING_PREFIXES):
                self._trip(f"refused tool {full!r}: this agent never calls it "
                           f"— nothing dispatched")
            raise McpDispatchError(
                f"unsupported tool {full!r} — nothing dispatched")

        # Defense in depth: a mutating call must already have passed the
        # broker's dry-run/armed/eligibility gates. If it reaches here while
        # not armed-live, something bypassed them — refuse AND kill.
        if short in GATED_MUTATIONS and not self.cfg.can_place_live():
            self._trip(
                f"{full} blocked (dry_run={self.cfg.dry_run}, "
                f"armed={self.cfg.armed}): mutating call while not armed-live "
                f"— nothing dispatched")

        try:
            raw = self._transport(full, dict(params or {}))
        except McpDispatchError as e:
            self.kill_state.mcp_error = True
            raise
        except Exception as e:  # noqa: BLE001 — every failure fails closed
            self._trip(f"{full} transport failure: {e!r}")
        return self._validate(full, raw)

    def _validate(self, full: str, raw) -> dict | list:
        if isinstance(raw, list):
            return raw
        if not isinstance(raw, dict):
            self._trip(f"{full} returned unparseable response of type "
                       f"{type(raw).__name__!r}: {raw!r}")
        if raw.get("isError") or raw.get("is_error"):
            self._trip(f"{full} returned an MCP tool error: {raw!r}")
        if raw.get("error"):
            self._trip(f"{full} returned an error payload: {raw['error']!r}")
        return raw


class RobinhoodMcpHttpTransport:
    """JSON-RPC ``tools/call`` over the MCP streamable-HTTP endpoint.

    Refuses to construct without an OAuth bearer token. Every HTTP/socket
    failure, timeout, or undecodable body raises ``McpDispatchError`` — the
    dispatcher above turns that into a kill.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ):
        self.url = url or os.environ.get(URL_ENV) or DEFAULT_MCP_URL
        tok = token if token is not None else os.environ.get(TOKEN_ENV, "")
        if not tok:
            raise McpDispatchError(
                f"no OAuth bearer token — set {TOKEN_ENV} (complete the "
                f"Robinhood MCP OAuth flow first). Refusing to construct a "
                f"live transport without credentials.")
        self._token = tok
        self.timeout = float(timeout_seconds)
        self._ids = itertools.count(1)

    def __call__(self, full_tool: str, params: dict) -> dict | list:
        name = (full_tool[len(MCP_TOOL_PREFIX):]
                if full_tool.startswith(MCP_TOOL_PREFIX) else full_tool)
        req_id = next(self._ids)
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": params},
        }).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, method="POST", headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self._token}",
        })
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                ctype = resp.headers.get("Content-Type", "") or ""
                payload = resp.read().decode("utf-8")
        except (urllib.error.URLError, socket.timeout, TimeoutError,
                OSError, UnicodeDecodeError) as e:
            raise McpDispatchError(
                f"MCP HTTP failure calling {name!r}: {e!r}") from e
        msg = self._extract_message(payload, ctype, req_id, name)
        return self._extract_result(msg, name)

    # -- response decoding (no fallbacks: undecodable => raise) -------------
    @staticmethod
    def _extract_message(payload: str, ctype: str, req_id: int, name: str) -> dict:
        candidates: list[dict] = []
        try:
            if "text/event-stream" in ctype:
                for chunk in payload.replace("\r\n", "\n").split("\n\n"):
                    data = "\n".join(line[5:].lstrip() for line in chunk.split("\n")
                                     if line.startswith("data:"))
                    if data.strip():
                        candidates.append(json.loads(data))
            else:
                candidates.append(json.loads(payload))
        except (ValueError, TypeError) as e:
            raise McpDispatchError(
                f"unparseable MCP response body for {name!r}: {e}") from e
        for msg in candidates:
            if isinstance(msg, dict) and msg.get("id") == req_id and (
                    "result" in msg or "error" in msg):
                return msg
        raise McpDispatchError(
            f"no JSON-RPC response for {name!r} (id={req_id}) in MCP reply")

    @staticmethod
    def _extract_result(msg: dict, name: str) -> dict | list:
        if msg.get("error"):
            raise McpDispatchError(f"MCP JSON-RPC error for {name!r}: {msg['error']!r}")
        result = msg.get("result")
        if not isinstance(result, dict):
            raise McpDispatchError(
                f"MCP result for {name!r} is not an object: {result!r}")
        if result.get("isError"):
            texts = [c.get("text", "") for c in (result.get("content") or [])
                     if isinstance(c, dict)]
            raise McpDispatchError(
                f"MCP tool error for {name!r}: {' '.join(t for t in texts if t) or result!r}")
        structured = result.get("structuredContent")
        if isinstance(structured, (dict, list)):
            return structured
        texts = [c.get("text") for c in (result.get("content") or [])
                 if isinstance(c, dict) and c.get("type") == "text"]
        joined = "\n".join(t for t in texts if t)
        if not joined:
            raise McpDispatchError(f"empty MCP result content for {name!r}")
        try:
            parsed = json.loads(joined)
        except ValueError as e:
            raise McpDispatchError(
                f"unparseable MCP result content for {name!r}: {e}") from e
        if not isinstance(parsed, (dict, list)):
            raise McpDispatchError(
                f"MCP result content for {name!r} is not an object/array: {parsed!r}")
        return parsed


def live_dispatcher(
    cfg: RuntimeConfig,
    kill_state: KillState,
    *,
    transport: Optional[Callable[[str, dict], object]] = None,
    url: Optional[str] = None,
    token: Optional[str] = None,
    timeout_seconds: float = 10.0,
) -> McpDispatcher:
    """Build the real dispatcher. Without an explicit ``transport`` this
    constructs the HTTP transport, which raises unless an OAuth token is
    present — so calling this in an unconfigured environment stays inert."""
    return McpDispatcher(
        transport or RobinhoodMcpHttpTransport(
            url=url, token=token, timeout_seconds=timeout_seconds),
        cfg, kill_state,
    )
