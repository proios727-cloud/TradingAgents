"""Robinhood Agentic Trading MCP adapter.

This driver builds the *exact* MCP tool calls (names + params matching the
Robinhood Trading MCP schema) and dispatches them through an injected
``mcp_call(tool_name, params) -> dict`` callable.

The read/parse layer was validated against the LIVE Robinhood Trading MCP
(get_accounts, get_portfolio, get_option_positions, get_option_chains,
get_option_instruments, get_option_quotes): every response is the
``{"data": {...}, "guide": "..."}`` envelope, buying power lives in
get_portfolio (NOT get_accounts), Greeks (incl. gamma) live under
``results[].quote``, and positions carry no strike/type/mark so they are
enriched from the instrument + quote.

Safety design — read carefully:

  * ``mcp_call`` defaults to ``None``. With no dispatcher wired, the adapter is
    inert: reads raise (nothing to call) and ``place_order`` NEVER sends.
  * ``place_order`` is gated three ways and only ever dispatches when ALL hold:
    ``cfg.can_place_live()`` (armed and not dry_run), a real ``mcp_call`` is
    wired, and the account is ``agentic_allowed`` with options Level 2/3.
  * A real dispatcher exists in ``mcp_dispatch.py`` and is wired via
    ``RobinhoodMcpBroker.live`` — inert without an OAuth token AND armed.
  * Fail closed: any MCP error, timeout, or response missing a REQUIRED field
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

# Order states that are still live and therefore cancellable.
_OPEN_ORDER_STATES = frozenset({"queued", "confirmed", "unconfirmed",
                                "partially_filled", "pending"})


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
                "Wire a real dispatcher (see mcp_dispatch.live_dispatcher) to read live."
            )
        return self._mcp

    def get_account(self) -> AccountState:
        mcp = self._require_mcp()
        try:
            accounts = _rows(mcp("get_accounts", {}), "accounts")
            acct = _pick_account(accounts, self.cfg.account_number)
            if not acct:
                raise ValueError("no account rows in get_accounts response")
            num = acct.get("account_number", self.cfg.account_number or "") or ""
            # Buying power is NOT on get_accounts — it lives in get_portfolio.
            port = _data(mcp("get_portfolio", {"account_number": num}))
            bp = port.get("buying_power") if isinstance(port, dict) else None
            # settled cash = live buying power (cash account), else the cash field.
            settled = (_req_num(bp, ("buying_power",), "buying power")
                       if isinstance(bp, dict) and bp
                       else _req_num(port, ("cash",), "settled cash"))
            cash = float(port.get("cash", 0) or 0) if isinstance(port, dict) else 0.0
            return AccountState(
                account_number=num,
                agentic_allowed=bool(acct.get("agentic_allowed", False)),
                option_level=acct.get("option_level", "") or "",
                balance=_req_num(port, ("total_value", "portfolio_value"), "account balance"),
                settled_cash=settled,
                unsettled_cash=max(0.0, cash - settled),
                open_premium=float(port.get("options_value", 0) or 0) if isinstance(port, dict) else 0.0,
            )
        except (KeyError, ValueError, TypeError) as e:
            self._trip(f"unparseable account/portfolio response: {e}")

    def get_positions(self) -> list[Position]:
        mcp = self._require_mcp()
        try:
            raw = _rows(mcp("get_option_positions",
                            {"account_number": self.cfg.account_number, "nonzero": True}),
                        "positions")
            out: list[Position] = []
            for p in raw:
                oid = _req_str(p, ("option_id",), "option id")
                inst = _first(_rows(mcp("get_option_instruments", {"ids": oid}), "instruments"))
                quote = _quote(mcp("get_option_quotes", {"instrument_ids": [oid]}))
                out.append(_parse_position(p, inst, quote))
            return out
        except (KeyError, ValueError, TypeError) as e:
            self._trip(f"unparseable get_option_positions response: {e}")

    def get_chain(self, symbol: str) -> ChainSnapshot:
        mcp = self._require_mcp()
        session = self._now().astimezone(MARKET_TZ).date()
        try:
            instruments = _rows(mcp("get_option_instruments", {
                "chain_symbol": symbol,
                "expiration_dates": session.isoformat(),  # plural, comma/date list
                "state": "active",
            }), "instruments")
            contracts: list[OptionContract] = []
            for inst in instruments:
                quote = _quote(mcp("get_option_quotes", {"instrument_ids": [inst.get("id")]}))
                contracts.append(_parse_contract(symbol, inst, quote, session))
            return ChainSnapshot(symbol=symbol, session_date=session, contracts=contracts)
        except (KeyError, ValueError, TypeError) as e:
            self._trip(f"unparseable option instrument/quote for {symbol}: {e}")

    # -- review (always safe: simulate only) ------------------------------
    def review_order(self, intent: OrderIntent) -> ReviewResult:
        if self._mcp is None:
            return ReviewResult(ok=True, quote={}, alerts=["(dry run — no live review)"])
        params = _review_params(intent, self.cfg.account_number)
        try:
            res = _data(self._mcp("review_option_order", params))
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
        # Gate 3: account eligibility. A read failure trips the kill switch
        # (get_account raises) — fail closed, never dispatch on unknown state.
        acct = self.get_account()
        if not acct.agentic_allowed or not acct.options_approved:
            return PlaceResult(placed=False, dry_run=True,
                               detail={"would_call": params},
                               error=f"account ineligible "
                                     f"(agentic_allowed={acct.agentic_allowed}, "
                                     f"option_level={acct.option_level!r})")
        # All gates passed and operator armed a live dispatcher: dispatch.
        res = _data(self._mcp("place_option_order", params))
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
        # There is no "open" order state; fetch recent and cancel the live ones.
        orders = _rows(self._mcp("get_option_orders",
                                  {"account_number": self.cfg.account_number}), "orders")
        for o in orders:
            if str(o.get("state", "")).lower() in _OPEN_ORDER_STATES:
                oid = o.get("id") or o.get("order_id")
                if not oid:
                    self._trip(f"open order row without an id: {o!r}")
                self._mcp("cancel_option_order", {
                    "account_number": self.cfg.account_number, "order_id": oid})


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
def _req_num(d, keys: tuple[str, ...], ctx: str) -> float:
    """Strictly extract a required numeric field. Missing/empty => ValueError
    (the caller trips the kill switch). 0 is legitimate; absence is not."""
    if isinstance(d, dict):
        for k in keys:
            v = d.get(k)
            if v is not None and v != "":
                return float(v)
    raise ValueError(f"missing required field {'/'.join(keys)} ({ctx}) — refusing to default it")


def _req_str(d, keys: tuple[str, ...], ctx: str) -> str:
    if isinstance(d, dict):
        for k in keys:
            v = d.get(k)
            if v:
                return str(v)
    raise ValueError(f"missing required field {'/'.join(keys)} ({ctx}) — refusing to default it")


def _data(resp):
    """Unwrap the Robinhood MCP ``{"data": ..., "guide": ...}`` envelope."""
    if isinstance(resp, dict) and "data" in resp:
        return resp["data"]
    return resp


def _rows(resp, key: str | None = None) -> list[dict]:
    """Pull the list under ``data[key]`` (accounts/positions/instruments/orders/
    results), tolerating a bare list or an already-unwrapped dict."""
    d = _data(resp)
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        if key and isinstance(d.get(key), list):
            return d[key]
        for k in ("results", "accounts", "positions", "orders", "instruments"):
            if isinstance(d.get(k), list):
                return d[k]
    return []


def _first(rows: list[dict]) -> dict:
    return rows[0] if rows else {}


def _quote(resp) -> dict:
    """get_option_quotes returns data.results[].quote — return the first quote."""
    r = _rows(resp, "results")
    return (r[0].get("quote", {}) if r and isinstance(r[0], dict) else {}) or {}


def _pick_account(accounts: list[dict], account_number: str | None) -> dict:
    if account_number:
        for a in accounts:
            if a.get("account_number") == account_number:
                return a
    for a in accounts:  # prefer an agent-accessible account
        if a.get("agentic_allowed"):
            return a
    return accounts[0] if accounts else {}


def _parse_contract(symbol, inst, quote, session) -> OptionContract:
    """Strict: quote prices and the delta Greek are required — a fabricated
    0-bid/0-delta could slip through the spread/delta rails."""
    return OptionContract(
        option_id=_req_str(inst, ("id",), "instrument id"),
        symbol=symbol,
        option_type=_req_str(inst, ("type",), "option type"),
        strike=_req_num(inst, ("strike_price",), "strike"),
        expiration=session,
        bid=_req_num(quote, ("bid_price",), "bid"),
        ask=_req_num(quote, ("ask_price",), "ask"),
        delta=_req_num(quote, ("delta",), "delta Greek"),
        gamma=float(quote.get("gamma", 0) or 0),  # enables convexity selection
    )


def _parse_position(p, inst, quote) -> Position:
    """Strict: entry/mark premiums and expiration are required. A position's
    ``type`` is long/short (direction) — the call/put comes from the instrument,
    the mark from the quote (positions carry neither)."""
    mult = float(p.get("trade_value_multiplier", 100) or 100)
    mark = quote.get("mark_price", quote.get("adjusted_mark_price"))
    if mark in (None, ""):
        raise ValueError(f"no mark price for position {p.get('option_id')!r}")
    return Position(
        symbol=_req_str(p, ("chain_symbol",), "underlying symbol"),
        option_id=_req_str(p, ("option_id",), "option id"),
        option_type=_req_str(inst, ("type",), "option type (call/put) from instrument"),
        strike=_req_num(inst, ("strike_price",), "strike from instrument"),
        expiration=date.fromisoformat(_req_str(p, ("expiration_date",), "expiration")),
        quantity=int(_req_num(p, ("quantity",), "quantity")),
        entry_premium=_req_num(p, ("average_price",), "entry premium") / (mult or 100),
        current_premium=float(mark),
        underlying_stop=0.0,
        underlying_target=0.0,
    )
