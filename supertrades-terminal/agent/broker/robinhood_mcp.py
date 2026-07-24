"""Robinhood Agentic Trading MCP adapter.

This driver builds the *exact* MCP tool calls (names + params matching the
Robinhood Trading MCP schema) and dispatches them through an injected
``mcp_call(tool_name, params) -> dict`` callable.

The read/parse layer here was validated against the LIVE Robinhood Trading MCP
(get_accounts, get_portfolio, get_option_positions, get_option_chains,
get_option_instruments, get_option_quotes) — every response is the
``{"data": {...}, "guide": "..."}`` envelope, buying power lives in
get_portfolio (not get_accounts), option Greeks (incl. gamma) live in
get_option_quotes under ``results[].quote``, and positions carry no strike /
type / mark, so they are enriched from the instrument + quote.

Safety design — read carefully:

  * ``mcp_call`` defaults to ``None``. With no dispatcher wired, the adapter is
    inert: reads raise (nothing to call) and ``place_order`` NEVER sends.
  * ``place_order`` is gated three ways and will only ever dispatch a live
    order when ALL hold: ``cfg.can_place_live()`` (armed and not dry_run), a
    real ``mcp_call`` is wired, and the account is ``agentic_allowed`` with
    options Level 2/3. Otherwise it returns a simulated PlaceResult and logs
    the intended call.
  * This file intentionally ships without a live dispatcher. Providing one is
    the operator's explicit go-live step (see ``mcp_dispatch.py``).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Callable, Optional

from ..config import MARKET_TZ, RuntimeConfig
from ..models import (
    AccountState,
    ChainSnapshot,
    OptionContract,
    OrderIntent,
    Position,
)
from .base import BrokerAdapter, PlaceResult, ReviewResult

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
        now_fn: Callable[[], datetime] = lambda: datetime.now(MARKET_TZ),
    ):
        self.cfg = cfg
        self._mcp = mcp_call
        self._now = now_fn

    # -- reads ------------------------------------------------------------
    def _require_mcp(self) -> McpCall:
        if self._mcp is None:
            raise RuntimeError(
                "No mcp_call dispatcher wired — RobinhoodMcpBroker is inert. "
                "Wire a real dispatcher (see mcp_dispatch.build_broker) to read live."
            )
        return self._mcp

    def get_account(self) -> AccountState:
        mcp = self._require_mcp()
        accounts = _rows(mcp("get_accounts", {}), "accounts")
        acct = _pick_account(accounts, self.cfg.account_number)
        num = acct.get("account_number", self.cfg.account_number or "") or ""
        # Buying power is NOT on get_accounts — it lives in get_portfolio.
        port = _data(mcp("get_portfolio", {"account_number": num})) if num else {}
        bp = port.get("buying_power") or {}
        settled = float(bp.get("buying_power", port.get("cash", 0)) or 0)
        cash = float(port.get("cash", 0) or 0)
        return AccountState(
            account_number=num,
            agentic_allowed=bool(acct.get("agentic_allowed", False)),
            option_level=acct.get("option_level", "") or "",
            balance=float(port.get("total_value", 0) or 0),
            settled_cash=settled,
            unsettled_cash=max(0.0, cash - settled),
            open_premium=float(port.get("options_value", 0) or 0),
        )

    def get_positions(self) -> list[Position]:
        mcp = self._require_mcp()
        raw = _rows(
            mcp("get_option_positions",
                {"account_number": self.cfg.account_number, "nonzero": True}),
            "positions",
        )
        out: list[Position] = []
        for p in raw:
            oid = p.get("option_id", "")
            inst = _first(_rows(mcp("get_option_instruments", {"ids": oid}), "instruments"))
            quote = _quote(mcp("get_option_quotes", {"instrument_ids": [oid]}))
            out.append(_parse_position(p, inst, quote))
        return out

    def get_chain(self, symbol: str) -> ChainSnapshot:
        mcp = self._require_mcp()
        session = self._now().astimezone(MARKET_TZ).date()
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
        # Gate 3: account eligibility (schema requirement). A read failure here
        # must reject cleanly, not raise mid-cycle — fail closed, place nothing.
        try:
            acct = self.get_account()
        except Exception as e:  # noqa: BLE001
            return PlaceResult(placed=False, dry_run=True,
                               detail={"would_call": params},
                               error=f"eligibility read failed — not dispatched ({e})")
        if not acct.agentic_allowed or not acct.options_approved:
            return PlaceResult(placed=False, dry_run=True,
                               detail={"would_call": params},
                               error=f"account ineligible "
                                     f"(agentic_allowed={acct.agentic_allowed}, "
                                     f"option_level={acct.option_level!r})")
        # All gates passed and operator armed a live dispatcher: dispatch.
        res = _data(self._mcp("place_option_order", params))
        return PlaceResult(placed=True, dry_run=False,
                           order_id=res.get("id", ""), detail=res)

    def cancel_all(self) -> None:
        if self._mcp is None or not self.cfg.can_place_live():
            return
        # There is no "open" order state; fetch recent and cancel the live ones.
        orders = _rows(self._mcp("get_option_orders",
                                  {"account_number": self.cfg.account_number}), "orders")
        for o in orders:
            if str(o.get("state", "")).lower() in _OPEN_ORDER_STATES:
                self._mcp("cancel_option_order", {
                    "account_number": self.cfg.account_number,
                    "order_id": o.get("id"),
                })


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
def _data(resp):
    """Unwrap the Robinhood MCP ``{"data": ..., "guide": ...}`` envelope."""
    if isinstance(resp, dict) and "data" in resp:
        return resp["data"]
    return resp


def _rows(resp, key: str) -> list[dict]:
    """Pull the list under ``data[key]`` (e.g. accounts/positions/instruments/
    orders), tolerating a bare list or already-unwrapped dict."""
    d = _data(resp)
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        v = d.get(key)
        if isinstance(v, list):
            return v
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
    return OptionContract(
        option_id=inst.get("id", ""),
        symbol=symbol,
        option_type=inst.get("type", "call"),
        strike=float(inst.get("strike_price", 0) or 0),
        expiration=session,
        bid=float(quote.get("bid_price", 0) or 0),
        ask=float(quote.get("ask_price", 0) or 0),
        delta=float(quote.get("delta", 0) or 0),
        gamma=float(quote.get("gamma", 0) or 0),  # enables convexity selection live
    )


def _parse_position(p, inst, quote) -> Position:
    exp = p.get("expiration_date", "")
    mult = float(p.get("trade_value_multiplier", 100) or 100)
    mark = quote.get("mark_price", quote.get("adjusted_mark_price", 0))
    return Position(
        symbol=p.get("chain_symbol", ""),
        option_id=p.get("option_id", ""),
        # `type` on a position is long/short (direction) — the call/put comes
        # from the instrument.
        option_type=inst.get("type", "call"),
        strike=float(inst.get("strike_price", 0) or 0),
        expiration=date.fromisoformat(exp) if exp else date.today(),
        quantity=int(float(p.get("quantity", 0) or 0)),
        entry_premium=float(p.get("average_price", 0) or 0) / (mult or 100),
        current_premium=float(mark or 0),
        underlying_stop=0.0,
        underlying_target=0.0,
    )
