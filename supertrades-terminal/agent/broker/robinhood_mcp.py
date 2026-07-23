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
  * This file intentionally ships without a live dispatcher. Providing one is
    the operator's explicit go-live step.
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
                "Wire a real dispatcher (e.g. via Claude Desktop's RH MCP) to read live."
            )
        return self._mcp

    def get_account(self) -> AccountState:
        data = self._require_mcp()("get_accounts", {})
        acct = _first_account(data, self.cfg.account_number)
        return AccountState(
            account_number=acct.get("account_number", self.cfg.account_number or ""),
            agentic_allowed=bool(acct.get("agentic_allowed", False)),
            option_level=acct.get("option_level", "") or "",
            balance=float(acct.get("portfolio_value", acct.get("balance", 0)) or 0),
            settled_cash=float(acct.get("settled_cash", acct.get("cash", 0)) or 0),
            unsettled_cash=float(acct.get("unsettled_funds", 0) or 0),
        )

    def get_positions(self) -> list[Position]:
        data = self._require_mcp()(
            "get_option_positions",
            {"account_number": self.cfg.account_number, "nonzero": True},
        )
        return [_parse_position(p) for p in _rows(data)]

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
            contracts.append(_parse_contract(symbol, inst, _rows(q), session))
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
        return PlaceResult(placed=True, dry_run=False,
                           order_id=res.get("id", ""), detail=res)

    def cancel_all(self) -> None:
        if self._mcp is None or not self.cfg.can_place_live():
            return
        for o in _rows(self._mcp("get_option_orders", {
            "account_number": self.cfg.account_number, "state": "open",
        })):
            self._mcp("cancel_option_order", {"order_id": o.get("id")})


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
def _rows(data) -> list[dict]:
    if isinstance(data, dict):
        return data.get("results") or data.get("data") or []
    return data or []


def _first_account(data, account_number: str | None) -> dict:
    rows = _rows(data) or ([data] if isinstance(data, dict) else [])
    if account_number:
        for a in rows:
            if a.get("account_number") == account_number:
                return a
    return rows[0] if rows else {}


def _parse_contract(symbol, inst, quotes, session) -> OptionContract:
    q = quotes[0] if quotes else {}
    bid = float(q.get("bid_price", 0) or 0)
    ask = float(q.get("ask_price", 0) or 0)
    return OptionContract(
        option_id=inst.get("id", ""),
        symbol=symbol,
        option_type=inst.get("type", "call"),
        strike=float(inst.get("strike_price", 0) or 0),
        expiration=session,
        bid=bid,
        ask=ask,
        delta=float(q.get("delta", 0) or 0),
    )


def _parse_position(p) -> Position:
    exp = p.get("expiration_date", "")
    return Position(
        symbol=p.get("chain_symbol", ""),
        option_id=p.get("option_id", ""),
        option_type=p.get("type", "call"),
        strike=float(p.get("strike_price", 0) or 0),
        expiration=date.fromisoformat(exp) if exp else date.today(),
        quantity=int(float(p.get("quantity", 0) or 0)),
        entry_premium=float(p.get("average_price", 0) or 0) / 100.0,
        current_premium=float(p.get("mark_price", 0) or 0),
        underlying_stop=0.0,
        underlying_target=0.0,
    )
