"""Robinhood MCP wiring tests.

Every fixture below is the REAL response shape captured from the live Robinhood
Trading MCP on 2026-07-24 (the {"data": {...}, "guide": ...} envelope, buying
power in get_portfolio, Greeks under results[].quote, positions carrying
long/short + no strike/mark). These pin the broker's parsers to the actual API
and would have caught the bugs the live test surfaced. Pure stdlib.

    cd supertrades-terminal && python -m unittest agent.tests.test_rh_wire -v
"""

from __future__ import annotations

import unittest
from datetime import date, datetime

from agent import mcp_dispatch
from agent.broker.robinhood_mcp import RobinhoodMcpBroker
from agent.config import MARKET_TZ, RuntimeConfig
from agent.mcp_dispatch import HttpMcpDispatcher, build_broker, preflight

AGENTIC = "902341866"
SESSION = date(2026, 7, 24)

# --- live-captured fixtures ------------------------------------------------
ACCOUNTS = {"data": {"accounts": [
    {"account_number": "812234458", "agentic_allowed": False, "option_level": "option_level_2"},
    {"account_number": AGENTIC, "agentic_allowed": True, "option_level": "option_level_2"},
]}}
PORTFOLIO = {"data": {"total_value": "434.36", "options_value": "100", "cash": "334.36",
                      "buying_power": {"buying_power": "334.3600"}}}
POSITIONS = {"data": {"positions": [
    {"option_id": "opt-1", "chain_symbol": "NVDA", "type": "long", "quantity": "1.0000",
     "average_price": "103.0000", "expiration_date": "2026-07-31", "trade_value_multiplier": "100.0000"},
]}}
POS_INSTRUMENT = {"data": {"instruments": [
    {"id": "opt-1", "strike_price": "120.0000", "type": "call", "expiration_date": "2026-07-31"},
]}}
CHAIN_INSTRUMENTS = {"data": {"instruments": [
    {"id": "i-640c", "strike_price": "640.0000", "type": "call", "expiration_date": "2026-07-24"},
]}}
QUOTE = {"data": {"results": [{"quote": {
    "bid_price": "1.00", "ask_price": "1.10", "mark_price": "1.05",
    "adjusted_mark_price": "1.05", "delta": "0.50", "gamma": "0.06"}}]}}
ORDERS = {"data": {"orders": [
    {"id": "o-open", "state": "confirmed"},
    {"id": "o-done", "state": "filled"},
]}}


def fake_mcp(record=None):
    """A stand-in dispatcher returning the live-shaped fixtures by tool + args."""
    def call(tool, params):
        if record is not None:
            record.append((tool, params))
        if tool == "get_accounts":
            return ACCOUNTS
        if tool == "get_portfolio":
            return PORTFOLIO
        if tool == "get_option_positions":
            return POSITIONS
        if tool == "get_option_instruments":
            return POS_INSTRUMENT if "ids" in params else CHAIN_INSTRUMENTS
        if tool == "get_option_quotes":
            return QUOTE
        if tool == "get_option_orders":
            return ORDERS
        if tool == "cancel_option_order":
            return {"data": {"id": params.get("order_id"), "state": "cancelled"}}
        return {}
    return call


def cfg(**kw):
    base = dict(account_number=AGENTIC, dry_run=True, armed=False)
    base.update(kw)
    return RuntimeConfig(**base)


def broker(**kw):
    now = lambda: datetime(2026, 7, 24, 12, 45, tzinfo=MARKET_TZ)
    return RobinhoodMcpBroker(cfg(**kw), fake_mcp(), now_fn=now)


class AccountParsing(unittest.TestCase):
    def test_balance_from_portfolio_not_accounts(self):
        acct = broker().get_account()
        self.assertAlmostEqual(acct.balance, 434.36)        # total_value
        self.assertAlmostEqual(acct.settled_cash, 334.36)   # buying_power.buying_power
        self.assertAlmostEqual(acct.open_premium, 100.0)

    def test_picks_agentic_account_and_level(self):
        acct = broker().get_account()
        self.assertEqual(acct.account_number, AGENTIC)
        self.assertTrue(acct.agentic_allowed)
        self.assertEqual(acct.option_level, "option_level_2")
        self.assertTrue(acct.options_approved)


class PositionEnrichment(unittest.TestCase):
    def test_call_put_from_instrument_not_long_short(self):
        pos = broker().get_positions()[0]
        # position `type` is "long"; the call/put must come from the instrument.
        self.assertEqual(pos.option_type, "call")
        self.assertAlmostEqual(pos.strike, 120.0)

    def test_mark_from_quote_entry_from_average(self):
        pos = broker().get_positions()[0]
        self.assertAlmostEqual(pos.current_premium, 1.05)          # quote mark
        self.assertAlmostEqual(pos.entry_premium, 1.03)            # 103.00 / 100 multiplier
        self.assertGreater(pos.premium_change_pct, 0)              # not a false -100% stop


class ChainParsing(unittest.TestCase):
    def test_reads_gamma_and_greeks(self):
        chain = broker().get_chain("SPY")
        c = chain.contracts[0]
        self.assertAlmostEqual(c.delta, 0.50)
        self.assertAlmostEqual(c.gamma, 0.06)     # was never parsed before — convexity needs it
        self.assertAlmostEqual(c.ask, 1.10)
        self.assertEqual(c.strike, 640.0)

    def test_uses_plural_expiration_dates(self):
        rec = []
        b = RobinhoodMcpBroker(cfg(), fake_mcp(rec),
                               now_fn=lambda: datetime(2026, 7, 24, 12, 45, tzinfo=MARKET_TZ))
        b.get_chain("SPY")
        inst_calls = [p for t, p in rec if t == "get_option_instruments"]
        self.assertTrue(any("expiration_dates" in p for p in inst_calls))
        self.assertFalse(any("expiration_date" in p and "expiration_dates" not in p
                             for p in inst_calls))


class CancelAll(unittest.TestCase):
    def test_cancels_only_open_with_account_number(self):
        rec = []
        b = RobinhoodMcpBroker(cfg(dry_run=False, armed=True), fake_mcp(rec))
        b.cancel_all()
        cancels = [p for t, p in rec if t == "cancel_option_order"]
        self.assertEqual(len(cancels), 1)                         # only the "confirmed" one
        self.assertEqual(cancels[0]["order_id"], "o-open")
        self.assertEqual(cancels[0]["account_number"], AGENTIC)   # required field present

    def test_disarmed_cancels_nothing(self):
        rec = []
        b = RobinhoodMcpBroker(cfg(dry_run=True, armed=False), fake_mcp(rec))
        b.cancel_all()
        self.assertEqual(rec, [])


class DispatcherSafety(unittest.TestCase):
    def test_no_token_fails_closed(self):
        with self.assertRaises(RuntimeError):
            HttpMcpDispatcher("https://x", "")

    def test_write_tool_blocked_when_readonly(self):
        d = HttpMcpDispatcher("https://x", "tok", allow_write=False, transport=lambda req: {})
        with self.assertRaises(PermissionError):
            d("place_option_order", {})

    def test_read_tool_passes_through_and_unwraps(self):
        d = HttpMcpDispatcher(
            "https://x", "tok", allow_write=False,
            transport=lambda req: {"result": {"content": [{"type": "text", "text": '{"data":{"ok":1}}'}]}})
        self.assertEqual(d("get_accounts", {}), {"data": {"ok": 1}})

    def test_write_allowed_when_armed(self):
        seen = {}
        d = HttpMcpDispatcher("https://x", "tok", allow_write=True,
                              transport=lambda req: seen.update(req) or {"result": {"structuredContent": {"id": "1"}}})
        self.assertEqual(d("place_option_order", {"q": 1}), {"id": "1"})
        self.assertEqual(seen["params"]["name"], "place_option_order")


class BuildBrokerAndPreflight(unittest.TestCase):
    def test_no_token_builds_inert_broker(self):
        # No ROBINHOOD_AGENT_TOKEN in the test env -> inert (dispatcher is None).
        b = build_broker(cfg())
        self.assertIsNone(b._mcp)

    def test_explicit_mcp_call_is_used(self):
        b = build_broker(cfg(), mcp_call=fake_mcp())
        self.assertIsNotNone(b._mcp)

    def test_preflight_ok_on_eligible_account(self):
        ok, reasons, acct = preflight(broker())
        self.assertTrue(ok, reasons)
        self.assertEqual(acct.account_number, AGENTIC)

    def test_preflight_flags_ineligible(self):
        class Bad(RobinhoodMcpBroker):
            def get_account(self):
                from agent.models import AccountState
                return AccountState("x", agentic_allowed=False, option_level="",
                                    balance=0, settled_cash=0)
        ok, reasons, _ = preflight(Bad(cfg(), fake_mcp()))
        self.assertFalse(ok)
        self.assertTrue(any("agentic" in r for r in reasons))


if __name__ == "__main__":
    unittest.main()
