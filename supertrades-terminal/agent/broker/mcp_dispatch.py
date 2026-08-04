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
  * **Endpoint is pinned, not configurable to anywhere.** The transport
    refuses to construct unless the resolved URL is ``https://`` and its host
    is the Robinhood MCP host (or a subdomain of it) — an env var or config
    typo can never silently downgrade to plaintext or repoint at an attacker
    host. The only override is an explicit, non-default ``allow_insecure_url``
    constructor kwarg meant for tests, never for production wiring.
  * **A timed-out mutation is UNKNOWN, never "failed".** If
    ``place_option_order``/``cancel_option_order`` fails at the transport
    level (timeout, socket error, unreadable body) Robinhood may already have
    accepted it. Before raising, the transport makes exactly ONE read-only
    reconciliation call (``get_option_orders``), narrowed to a recent window
    via ``created_at_gte``/``placed_agent``, and looks for a PLAUSIBLE match
    on ``placed_agent == "agentic"`` + quantity + price + recency — NOT
    ``ref_id``: the real ``get_option_orders`` response never echoes back the
    ``ref_id`` an order was placed with, so matching on it always fails (see
    ``_reconcile_after_failure``). The resulting error always says the state
    is UNKNOWN/may have been placed (or unverifiable, if reconciliation
    itself fails) — it never claims the order failed. Reconciliation cannot
    place, cancel, or retry.
  * **Bounded in time and size.** Every request has an overall wall-clock
    deadline (beyond the per-socket-read timeout) and a maximum response body
    size; exceeding either fails the call the same way any other transport
    failure does.
"""

from __future__ import annotations

import itertools
import json
import os
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Callable, NoReturn, Optional
from urllib.parse import urlparse

from ..config import RuntimeConfig
from ..kill_switch import KillState

# The Robinhood Agentic Trading MCP server, as namespaced by the MCP client.
MCP_TOOL_PREFIX = "mcp__Robinhood_Trading__"
DEFAULT_MCP_URL = "https://agent.robinhood.com/mcp/trading"
URL_ENV = "ROBINHOOD_MCP_URL"
TOKEN_ENV = "ROBINHOOD_MCP_TOKEN"

# The only host (or subdomain of it) the live transport will ever talk to,
# derived from DEFAULT_MCP_URL rather than duplicated as a literal. Nothing —
# not ROBINHOOD_MCP_URL, not a constructor arg — can point this at another
# host without the explicit, test-only ``allow_insecure_url`` escape hatch.
_EXPECTED_MCP_HOST = (urlparse(DEFAULT_MCP_URL).hostname or "").lower()

# Defaults for the overall request deadline / response body cap (defect C).
# The deadline sits modestly above the default per-socket-read timeout so a
# slow-but-honest connection still completes; the cap comfortably covers a
# full option chain response while refusing to buffer an unbounded body.
_DEFAULT_DEADLINE_MARGIN_SECONDS = 5.0
_DEFAULT_MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MiB

# How far back reconciliation looks, and how close a candidate order's
# ``created_at`` must sit to the failed placement attempt to be considered
# the same order. There is no ``ref_id`` to match on (see module docstring
# and ``_reconcile_after_failure``), so this window is what keeps the
# composite match narrow. 120s comfortably covers this transport's own
# request budget (socket timeout + ``_DEFAULT_DEADLINE_MARGIN_SECONDS``,
# ~15s by default) plus broker-side ack/processing latency, while staying
# tight enough that an unrelated same-symbol order placed minutes later (by
# the user, or a later agent cycle) is not swept in as a false match.
RECONCILIATION_WINDOW_SECONDS = 120.0

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


def _resolve_and_validate_url(url: Optional[str], allow_insecure_url: bool) -> str:
    """Resolve the MCP endpoint and pin it to the real Robinhood host.

    ``allow_insecure_url`` is a narrow, explicit, test-only escape hatch — it
    must be passed by keyword by the caller (never an env var, never
    defaulted True) and localhost is NOT special-cased into the allowed set.
    """
    resolved = url or os.environ.get(URL_ENV) or DEFAULT_MCP_URL
    if allow_insecure_url:
        return resolved
    parsed = urlparse(resolved)
    if parsed.scheme != "https":
        raise McpDispatchError(
            f"refusing to use MCP endpoint {resolved!r}: scheme must be "
            f"https (got {parsed.scheme!r}) — an OAuth bearer token and "
            f"every order would otherwise go out in plaintext. Pass "
            f"allow_insecure_url=True explicitly if this is a test.")
    host = (parsed.hostname or "").lower()
    if host != _EXPECTED_MCP_HOST and not host.endswith("." + _EXPECTED_MCP_HOST):
        raise McpDispatchError(
            f"refusing to use MCP endpoint {resolved!r}: host {host!r} is "
            f"not {_EXPECTED_MCP_HOST!r} or a subdomain of it — refusing to "
            f"send the OAuth bearer token and live orders to an untrusted "
            f"host. Pass allow_insecure_url=True explicitly if this is a "
            f"test.")
    return resolved


class RobinhoodMcpHttpTransport:
    """JSON-RPC ``tools/call`` over the MCP streamable-HTTP endpoint.

    Refuses to construct without an OAuth bearer token, and refuses to
    construct against anything but an ``https://`` Robinhood-hosted endpoint
    (see ``_resolve_and_validate_url``). Every HTTP/socket failure, timeout,
    undecodable body, deadline overrun, or oversized body raises
    ``McpDispatchError`` — the dispatcher above turns that into a kill. For a
    mutating call specifically, such a failure first triggers exactly one
    read-only reconciliation attempt (see ``_reconcile_after_failure``) so the
    caller never mistakes "the wire failed" for "nothing happened".
    """

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        timeout_seconds: float = 10.0,
        *,
        allow_insecure_url: bool = False,
        overall_deadline_seconds: Optional[float] = None,
        max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
    ):
        self.url = _resolve_and_validate_url(url, allow_insecure_url)
        tok = token if token is not None else os.environ.get(TOKEN_ENV, "")
        if not tok:
            raise McpDispatchError(
                f"no OAuth bearer token — set {TOKEN_ENV} (complete the "
                f"Robinhood MCP OAuth flow first). Refusing to construct a "
                f"live transport without credentials.")
        self._token = tok
        self.timeout = float(timeout_seconds)
        self.overall_deadline = float(
            overall_deadline_seconds if overall_deadline_seconds is not None
            else self.timeout + _DEFAULT_DEADLINE_MARGIN_SECONDS)
        self.max_response_bytes = int(max_response_bytes)
        self._ids = itertools.count(1)

    # -- request plumbing ----------------------------------------------------
    def _build_request(self, name: str, params: dict) -> tuple[urllib.request.Request, int]:
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
        return req, req_id

    def _send(self, req: urllib.request.Request, deadline_at: float) -> tuple[str, str]:
        """Issue the request and read the body under an overall wall-clock
        deadline and a max-size cap (defect C). Raises ``McpDispatchError`` on
        deadline/size overrun, or the underlying socket/URL error otherwise —
        both are transport-level failures the caller may reconcile on."""
        remaining = deadline_at - time.monotonic()
        if remaining <= 0:
            raise McpDispatchError(
                f"MCP request exceeded its overall deadline of "
                f"{self.overall_deadline}s before it could be sent")
        with urllib.request.urlopen(req, timeout=min(self.timeout, remaining)) as resp:
            ctype = resp.headers.get("Content-Type", "") or ""
            chunks: list[bytes] = []
            total = 0
            while True:
                if time.monotonic() > deadline_at:
                    raise McpDispatchError(
                        f"MCP response read exceeded overall deadline of "
                        f"{self.overall_deadline}s")
                chunk = resp.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > self.max_response_bytes:
                    raise McpDispatchError(
                        f"MCP response exceeded max body size of "
                        f"{self.max_response_bytes} bytes")
                chunks.append(chunk)
            payload = b"".join(chunks).decode("utf-8")
        return payload, ctype

    def __call__(self, full_tool: str, params: dict) -> dict | list:
        name = (full_tool[len(MCP_TOOL_PREFIX):]
                if full_tool.startswith(MCP_TOOL_PREFIX) else full_tool)
        # Captured BEFORE the wire attempt: the anchor for the reconciliation
        # recency window if this call fails (see _reconcile_after_failure).
        attempted_at = datetime.now(timezone.utc)
        req, req_id = self._build_request(name, params)
        deadline_at = time.monotonic() + self.overall_deadline
        try:
            payload, ctype = self._send(req, deadline_at)
        except (urllib.error.URLError, socket.timeout, TimeoutError,
                OSError, UnicodeDecodeError, McpDispatchError) as e:
            if name in GATED_MUTATIONS:
                raise self._reconcile_after_failure(
                    name, params, e, attempted_at) from e
            raise McpDispatchError(
                f"MCP HTTP failure calling {name!r}: {e!r}") from e
        msg = self._extract_message(payload, ctype, req_id, name)
        return self._extract_result(msg, name)

    # -- reconciliation after a mutating transport failure (defect B) -------
    def _reconcile_after_failure(
        self, name: str, params: dict, orig_exc: Exception,
        attempted_at: datetime,
    ) -> McpDispatchError:
        """Exactly ONE read-only ``get_option_orders`` lookup for a PLAUSIBLE
        match to the failed mutation. Never places, cancels, or retries
        anything — a failure here is reported as unverifiable, not as
        "the order failed", because the mutation may well have gone through.

        NOTE: this cannot match on ``ref_id``. ``ref_id`` is still sent with
        every order (see ``_place_params`` in ``robinhood_mcp.py``) — it is
        the broker-side idempotency key — but the real ``get_option_orders``
        response never echoes it back on order rows, so a
        ``o.get("ref_id") == ref_id`` check always fails and silently
        defeats this entire safety path. Do NOT re-add ref_id matching here.

        Instead this matches a composite of what IS actually returned:
        ``placed_agent == "agentic"`` (the account also holds orders placed
        by the human user and by expiring-option auto-exercise/settlement —
        never assume every order is ours), quantity, price (compared
        numerically — the API returns both as strings, e.g. "1.00000" /
        "2.08000000"), and ``created_at`` within ``RECONCILIATION_WINDOW_SECONDS``
        of the attempted placement. There is no ``chain_symbol`` (or any
        other field) in ``place_option_order``'s own params to match against
        — its schema identifies the contract solely via an opaque
        ``option_id`` inside ``legs`` — so the symbol is deliberately not
        part of this composite rather than inventing a field to smuggle
        through the wire payload.

        The match is intentionally BIASED toward "this may be our order":
        any plausible candidate is reported as a possible placement, never
        as a confident one, and "no matching order" is reported only when
        nothing plausible turns up.
        """
        account_number = params.get("account_number")
        window_start = attempted_at - timedelta(seconds=RECONCILIATION_WINDOW_SECONDS)
        read_params: dict = {"placed_agent": "agentic"}
        if account_number:
            read_params["account_number"] = account_number
        # Narrow the query itself (the real account can hold ~90 orders) —
        # ISO 8601 UTC, as the API expects for created_at_gte.
        read_params["created_at_gte"] = window_start.isoformat()
        try:
            req, req_id = self._build_request("get_option_orders", read_params)
            deadline_at = time.monotonic() + self.overall_deadline
            payload, ctype = self._send(req, deadline_at)
            msg = self._extract_message(payload, ctype, req_id, "get_option_orders")
            orders = self._extract_result(msg, "get_option_orders")
        except Exception as recon_exc:  # noqa: BLE001 — report, never re-raise raw
            return McpDispatchError(
                f"{name} transport failure ({orig_exc!r}): order state is "
                f"UNKNOWN and UNVERIFIABLE — the read-only reconciliation "
                f"check also failed ({recon_exc!r}). Do NOT treat this as a "
                f"failed/unplaced order — it may have been placed. Halt and "
                f"verify manually before retrying.")
        match = None
        for o in _rows_for_reconciliation(orders):
            if _is_plausible_match(o, params, attempted_at, window_start):
                match = o
                break
        if match is not None:
            oid = match.get("id") or match.get("order_id")
            return McpDispatchError(
                f"{name} transport failure ({orig_exc!r}): order state is "
                f"UNKNOWN — reconciliation FOUND a plausibly matching order "
                f"(order_id={oid!r}, placed_agent='agentic', quantity/price/"
                f"timing consistent with this attempt). The order MAY HAVE "
                f"BEEN PLACED even though the call appeared to fail. Do not "
                f"retry or resubmit; verify and reconcile manually.")
        return McpDispatchError(
            f"{name} transport failure ({orig_exc!r}): read-only "
            f"reconciliation found no plausibly matching order. Treating as "
            f"not placed, but this is not a guarantee — verify manually "
            f"before assuming so.")

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


def _rows_for_reconciliation(data) -> list:
    """Same shape-tolerant row extraction as ``robinhood_mcp._rows``,
    duplicated locally so this module has no upward dependency — reconciling
    a failed mutation must not need anything but this module's own transport.

    The real ``get_option_orders`` envelope is ``{"data": {"orders": [...]}}``
    — a dict nested one level under a NAMED key, not a bare list under
    ``"data"``. ``{"results": [...]}`` and a bare list are also tolerated
    (older/simpler shapes, and what the tests in this module use)."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    if "results" in data:
        return data.get("results") or []
    inner = data.get("data")
    if isinstance(inner, list):
        return inner
    if isinstance(inner, dict):
        return inner.get("orders") or []
    return []


def _numeric(value) -> Optional[float]:
    """Parse a field the real API may return as a numeric string
    (``"1.00000"``, ``"2.08000000"``) or a native number. ``None``/empty/
    unparseable => ``None`` — never fabricate a number to force a match."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _numeric_match(a, b) -> bool:
    x, y = _numeric(a), _numeric(b)
    if x is None or y is None:
        return False
    return abs(x - y) < 1e-6


def _is_plausible_match(
    o, params: dict, attempted_at: datetime, window_start: datetime,
) -> bool:
    """Composite match for reconciliation — see ``_reconcile_after_failure``
    for why there is no ``ref_id``/``chain_symbol`` in the mix."""
    if not isinstance(o, dict):
        return False
    if o.get("placed_agent") != "agentic":
        return False
    if not _numeric_match(o.get("quantity"), params.get("quantity")):
        return False
    if not _numeric_match(o.get("price"), params.get("price")):
        return False
    created_at = o.get("created_at")
    if not created_at:
        return False
    try:
        created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    except ValueError:
        return False
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return window_start <= created <= attempted_at + timedelta(
        seconds=RECONCILIATION_WINDOW_SECONDS)


def live_dispatcher(
    cfg: RuntimeConfig,
    kill_state: KillState,
    *,
    transport: Optional[Callable[[str, dict], object]] = None,
    url: Optional[str] = None,
    token: Optional[str] = None,
    timeout_seconds: float = 10.0,
    overall_deadline_seconds: Optional[float] = None,
    max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
) -> McpDispatcher:
    """Build the real dispatcher. Without an explicit ``transport`` this
    constructs the HTTP transport, which raises unless an OAuth token is
    present — so calling this in an unconfigured environment stays inert.

    Deliberately has no ``allow_insecure_url`` passthrough: that escape hatch
    is for tests constructing ``RobinhoodMcpHttpTransport`` directly, never
    for this production wiring path."""
    return McpDispatcher(
        transport or RobinhoodMcpHttpTransport(
            url=url, token=token, timeout_seconds=timeout_seconds,
            overall_deadline_seconds=overall_deadline_seconds,
            max_response_bytes=max_response_bytes),
        cfg, kill_state,
    )
