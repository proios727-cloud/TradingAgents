"""Robinhood Agentic Trading MCP adapter.

This driver builds the *exact* MCP tool calls (names + params matching the
Robinhood Trading MCP schema) and dispatches them through an injected
``mcp_call(tool_name, params) -> dict`` callable.

Safety design — read carefully:

  * ``mcp_call`` defaults to ``None``. With no dispatcher wired, the adapter is
    inert: reads raise (nothing to call) and ``place_order`` NEVER sends.
  * ``place_order`` is gated three ways and will only ever dispatch a live
    order when ALL hold: ``cfg.can_place_live()`` (armed and not dry_run), a
    real ``mcp_call`` is wired, and the account is ``agentic_allowed`` with
    options Level 2/3. Otherwise it returns a simulated PlaceResult and logs
    the intended call.
  * A real dispatcher now exists in ``mcp_dispatch.py`` (``McpDispatcher`` over
    the MCP streamable-HTTP endpoint) and is wired via ``RobinhoodMcpBroker.live``
    — but it stays inert without an OAuth token AND ``armed=True, dry_run=False``.
    Constructing this broker directly still defaults to no dispatcher.
  * Fail closed: any MCP error, timeout, or response missing a required field
    (a balance, a Greek, a fill/quote price, an order id) trips the shared
    kill switch and raises. Nothing is ever defaulted or fabricated.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Callable, NoReturn, Optional

from ..config import MARKET_TZ, RuntimeConfig
from ..kill_switch import KillState
from ..models import (
    AccountState,
    ChainSnapshot,
    OptionContract,
    OrderIntent,
    Position,
)
from .base import BrokerAdapter, PlaceResult, ReviewResult
from .mcp_dispatch import McpDispatchError, live_dispatcher

McpCall = Callable[[str, dict], dict]


class RobinhoodMcpBroker(BrokerAdapter):
    def __init__(
        self,
        cfg: RuntimeConfig,
        mcp_call: Optional[McpCall] = None,
        *,
        kill_state: KillState | None = None,
        now_fn: Callable[[], datetime] = lambda: datetime.now(MARKET_TZ),
    ):
        self.cfg = cfg
        self._mcp = mcp_call
        self.kill = kill_state or KillState()
        self._now = now_fn

    @classmethod
    def live(
        cls,
        cfg: RuntimeConfig,
        *,
        kill_state: KillState | None = None,
        transport: Optional[McpCall] = None,
        url: Optional[str] = None,
        token: Optional[str] = None,
        timeout_seconds: float = 10.0,
        now_fn: Callable[[], datetime] = lambda: datetime.now(MARKET_TZ),
    ) -> "RobinhoodMcpBroker":
        """Broker + real MCP dispatcher sharing ONE kill state. Pass the same
        ``kill_state`` to the engine so a dispatch failure halts the next
        cycle. Raises (stays inert) if no OAuth token is configured."""
        ks = kill_state or KillState()
        dispatcher = live_dispatcher(cfg, ks, transport=transport, url=url,
                                     token=token, timeout_seconds=timeout_seconds)
        return cls(cfg, mcp_call=dispatcher, kill_state=ks, now_fn=now_fn)

    # -- fail closed -------------------------------------------------------
    def _trip(self, reason: str) -> NoReturn:
        """Any unparseable/incomplete broker response => kill switch + raise.
        Never fabricate or default a fill price, a Greek, or a balance."""
        self.kill.mcp_error = True
        raise McpDispatchError(reason)

    # -- reads ------------------------------------------------------------
    def _require_mcp(self) -> McpCall:
        if self._mcp is None:
            raise RuntimeError(
                "No mcp_call dispatcher wired — RobinhoodMcpBroker is inert. "
                "Wire a real dispatcher (e.g. via Claude Desktop's RH MCP) to read live."
            )
        return self._mcp

    def get_account(self) -> AccountState:
        """Identity/permissions come from ``get_accounts``; money comes from
        ``get_portfolio`` for that account. The real ``get_accounts`` response
        carries neither ``portfolio_value``/``balance`` nor ``settled_cash`` —
        only ``get_portfolio`` (keyed by ``account_number``) has balances."""
        mcp = self._require_mcp()
        accounts_data = mcp("get_accounts", {})
        try:
            acct = _first_account(accounts_data, self.cfg.account_number)
            if not acct:
                raise ValueError("no account rows in get_accounts response")
            account_number = acct.get("account_number", self.cfg.account_number or "")
        except (KeyError, ValueError, TypeError) as e:
            self._trip(f"unparseable get_accounts response: {e}")

        portfolio = mcp("get_portfolio", {"account_number": account_number})
        try:
            port = _unwrap_object(portfolio)
            # Cash-account settlement (GO-LIVE: never buy with unsettled
            # proceeds; open premium <= settled cash). This is a CASH account:
            # the top-level "cash" figure includes UNSETTLED funds (T+1) that
            # are not yet spendable — real spendable cash is
            # buying_power.buying_power. Do NOT "simplify" this back to
            # "cash"; that would let the risk governor size a trade against
            # money that hasn't settled yet.
            buying_power = port.get("buying_power")
            if not isinstance(buying_power, dict):
                raise ValueError(
                    "missing required field buying_power (settled cash) — "
                    "refusing to default it"
                )
            return AccountState(
                account_number=account_number,
                agentic_allowed=bool(acct.get("agentic_allowed", False)),
                option_level=acct.get("option_level", "") or "",
                # Balances are strict — a missing balance is never defaulted.
                balance=_req_num(port, ("total_value",), "account balance"),
                settled_cash=_req_num(
                    buying_power, ("buying_power",), "settled cash (buying power)"
                ),
                unsettled_cash=float(acct.get("unsettled_funds", 0) or 0),
            )
        except (KeyError, ValueError, TypeError) as e:
            self._trip(f"unparseable get_portfolio response: {e}")

    def get_positions(self) -> list[Position]:
        data = self._require_mcp()(
            "get_option_positions",
            {"account_number": self.cfg.account_number, "nonzero": True},
        )
        try:
            return [_parse_position(p) for p in _rows(data, "positions")]
        except (KeyError, ValueError, TypeError) as e:
            self._trip(f"unparseable get_option_positions response: {e}")

    def get_chain(self, symbol: str) -> ChainSnapshot:
        mcp = self._require_mcp()
        chain = mcp("get_option_chains", {"underlying_symbol": symbol})
        session = self._now().astimezone(MARKET_TZ).date()
        contracts: list[OptionContract] = []
        for inst in _rows(mcp("get_option_instruments", {
            "chain_symbol": symbol,
            "expiration_date": session.isoformat(),
        })):
            q = mcp("get_option_quotes", {"instrument_ids": [inst.get("id")]})
            try:
                contracts.append(_parse_contract(symbol, inst, _rows(q), session))
            except (KeyError, ValueError, TypeError) as e:
                self._trip(f"unparseable option instrument/quote for {symbol}: {e}")
        return ChainSnapshot(symbol=symbol, session_date=session, contracts=contracts)

    # -- review (always safe: simulate only) ------------------------------
    def review_order(self, intent: OrderIntent) -> ReviewResult:
        if self._mcp is None:
            return ReviewResult(ok=True, quote={}, alerts=["(dry run — no live review)"])
        params = _review_params(intent, self.cfg.account_number)
        try:
            res = self._mcp("review_option_order", params)
        except Exception as e:  # noqa: BLE001 — surface as a soft failure
            return ReviewResult(ok=False, error=str(e))
        return ReviewResult(
            ok=True,
            quote=res.get("quote", {}),
            alerts=[c.get("detail", str(c)) for c in res.get("order_checks", [])],
            fees=res.get("fees", {}),
        )

    # -- place (the gated, mutating call) ---------------------------------
    def place_order(self, intent: OrderIntent) -> PlaceResult:
        params = _place_params(intent, self.cfg.account_number)
        intent.mcp_tool = "place_option_order"
        intent.mcp_params = params

        # Gate 1: dry-run / not armed -> never dispatch.
        if not self.cfg.can_place_live():
            return PlaceResult(placed=False, dry_run=True, order_id="",
                               detail={"would_call": params},
                               error="dry-run/disarmed — not dispatched")
        # Gate 2: no dispatcher wired -> never dispatch.
        if self._mcp is None:
            return PlaceResult(placed=False, dry_run=True,
                               detail={"would_call": params},
                               error="no mcp_call dispatcher wired")
        # Gate 3: account eligibility (schema requirement).
        acct = self.get_account()
        if not acct.agentic_allowed or not acct.options_approved:
            return PlaceResult(placed=False, dry_run=True,
                               detail={"would_call": params},
                               error=f"account ineligible "
                                     f"(agentic_allowed={acct.agentic_allowed}, "
                                     f"option_level={acct.option_level!r})")
        # All gates passed and operator armed a live dispatcher: dispatch.
        res = self._mcp("place_option_order", params)
        order_id = (res.get("id") or res.get("order_id")) if isinstance(res, dict) else None
        if not order_id:
            # A dispatched order with no id means its state is unknown — that
            # is a kill, never a fabricated/blank id.
            self._trip(f"place_option_order returned no order id: {res!r}")
        return PlaceResult(placed=True, dry_run=False,
                           order_id=str(order_id), detail=res)

    def cancel_all(self) -> None:
        if self._mcp is None or not self.cfg.can_place_live():
            return
        for o in _rows(self._mcp("get_option_orders", {
            "account_number": self.cfg.account_number, "state": "open",
        })):
            oid = o.get("id") or o.get("order_id")
            if not oid:
                self._trip(f"open order row without an id: {o!r}")
            self._mcp("cancel_option_order", {"order_id": oid})


# --- payload builders (exact MCP schema) --------------------------------
def _leg(intent: OrderIntent) -> dict:
    return {
        "option_id": intent.option_id,
        "side": intent.side,
        "position_effect": intent.position_effect,
    }


def _review_params(intent: OrderIntent, account: str | None) -> dict:
    return {
        "account_number": account,
        "chain_symbol": intent.symbol,
        "underlying_type": "equity",
        "legs": [_leg(intent)],
        "quantity": str(intent.quantity),
        "type": "limit",
        "price": f"{intent.limit_price:.2f}",
        "time_in_force": "gfd",
    }


def _place_params(intent: OrderIntent, account: str | None) -> dict:
    return {
        "account_number": account,
        "legs": [_leg(intent)],
        "quantity": str(intent.quantity),
        "type": "limit",
        "price": f"{intent.limit_price:.2f}",
        "time_in_force": "gfd",
        "ref_id": intent.ref_id or str(uuid.uuid4()),
    }


# --- response parsing helpers -------------------------------------------
def _req_num(d: dict, keys: tuple[str, ...], ctx: str) -> float:
    """Strictly extract a required numeric field. Missing/empty => ValueError
    (the caller trips the kill switch). 0 is a legitimate value; absence is not."""
    for k in keys:
        v = d.get(k)
        if v is not None and v != "":
            return float(v)
    raise ValueError(f"missing required field {'/'.join(keys)} ({ctx}) — "
                     f"refusing to default it")


def _req_str(d: dict, keys: tuple[str, ...], ctx: str) -> str:
    for k in keys:
        v = d.get(k)
        if v:
            return str(v)
    raise ValueError(f"missing required field {'/'.join(keys)} ({ctx}) — "
                     f"refusing to default it")


def _rows(data, key: str | None = None) -> list[dict]:
    """Extract the row list from an MCP response envelope.

    Real Robinhood payloads nest the collection one level deeper under a
    NAMED key — e.g. ``{"data": {"accounts": [...]}}``,
    ``{"data": {"positions": [...]}}`` — not a bare list under ``"data"``.
    Older/simpler shapes some endpoints (and every existing test) use are
    still accepted: ``{"results": [...]}`` and a bare list.

    ``key`` is the collection name the caller already knows (e.g.
    ``"accounts"``, ``"positions"``) — pass it whenever known so a real
    nested dict is read explicitly instead of guessed at. Without a key, a
    nested dict is only unwrapped when exactly one of its values is a list —
    picking among several would silently return the wrong collection.
    """
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
        if key is not None:
            return inner.get(key) or []
        candidates = [v for v in inner.values() if isinstance(v, list)]
        return candidates[0] if len(candidates) == 1 else []
    return []


def _unwrap_object(data) -> dict:
    """Unwrap a single-object MCP response envelope, e.g. ``get_portfolio``'s
    ``{"data": {...fields...}}``. Distinct from ``_rows``: the portfolio
    payload is one object, not a named list of rows. Tolerates the older
    ``{"results": {...}}`` shape and a bare dict for the same reason ``_rows``
    tolerates ``{"results": [...]}``."""
    if not isinstance(data, dict):
        return {}
    inner = data.get("data")
    if isinstance(inner, dict):
        return inner
    results = data.get("results")
    if isinstance(results, dict):
        return results
    if isinstance(results, list) and results and isinstance(results[0], dict):
        return results[0]
    return data


def _first_account(data, account_number: str | None) -> dict:
    rows = _rows(data, "accounts") or ([data] if isinstance(data, dict) else [])
    if account_number:
        for a in rows:
            if a.get("account_number") == account_number:
                return a
    return rows[0] if rows else {}


def _parse_contract(symbol, inst, quotes, session) -> OptionContract:
    """Strict: quote prices and the delta Greek are required — a contract with
    a fabricated 0-bid/0-delta could slip through the spread/delta rails."""
    if not quotes:
        raise ValueError(f"no quote returned for instrument {inst.get('id')!r}")
    q = quotes[0]
    return OptionContract(
        option_id=_req_str(inst, ("id",), "instrument id"),
        symbol=symbol,
        option_type=_req_str(inst, ("type",), "option type"),
        strike=_req_num(inst, ("strike_price",), "strike"),
        expiration=session,
        bid=_req_num(q, ("bid_price",), "bid"),
        ask=_req_num(q, ("ask_price",), "ask"),
        delta=_req_num(q, ("delta",), "delta Greek"),
        gamma=float(q.get("gamma", 0) or 0),
    )


def _parse_position(p) -> Position:
    """Strict: entry/mark premiums and expiration are required — defaulting a
    fill price or an expiry would corrupt every exit decision."""
    return Position(
        symbol=_req_str(p, ("chain_symbol",), "underlying symbol"),
        option_id=_req_str(p, ("option_id",), "option id"),
        option_type=_req_str(p, ("type",), "option type"),
        strike=_req_num(p, ("strike_price",), "strike"),
        expiration=date.fromisoformat(_req_str(p, ("expiration_date",), "expiration")),
        quantity=int(_req_num(p, ("quantity",), "quantity")),
        entry_premium=_req_num(p, ("average_price",), "entry premium") / 100.0,
        current_premium=_req_num(p, ("mark_price",), "mark premium"),
        underlying_stop=0.0,
        underlying_target=0.0,
    )
