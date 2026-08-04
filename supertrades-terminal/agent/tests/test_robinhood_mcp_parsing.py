"""Parsing tests driven by REAL captured Robinhood MCP payloads.

These fixtures are verbatim from the live connector (see the task that added
this file / git history) — not invented shapes. They caught three parser bugs
that tripped the kill switch on the very first cycle against the real API:

  1. ``_rows`` assumed ``{"results": [...]}`` or a bare ``{"data": [...]}``
     list; the real envelope nests the collection one level deeper under a
     NAMED key (``data.data.accounts``, ``data.data.positions``).
  2. ``get_accounts`` carries identity/permissions only — no balance field
     exists there. Balances come from a separate ``get_portfolio`` call.
  3. For this CASH account, unsettled funds are folded into the top-level
     ``cash`` figure; real spendable money is ``buying_power.buying_power``.
     ``settled_cash`` must bind to that, never to ``cash``.

Fakes only — no network call, no real MCP tool is ever invoked.
"""

from __future__ import annotations

import unittest

from agent.broker.robinhood_mcp import RobinhoodMcpBroker
from agent.broker.mcp_dispatch import McpDispatchError
from agent.config import RuntimeConfig
from agent.kill_switch import KillState

# --- verbatim captures from the live Robinhood MCP -----------------------

REAL_GET_ACCOUNTS = {"data": {"accounts": [
    {"account_number": "812234458", "rhs_account_number": "812234458",
     "type": "margin", "unsettled_funds": "0.0000",
     "brokerage_account_type": "individual", "is_default": True,
     "agentic_allowed": False, "option_level": "option_level_2",
     "management_type": "self_directed", "affiliate": "rhf",
     "state": "active", "deactivated": False, "permanently_deactivated": False},
    {"account_number": "902341866", "rhs_account_number": "902341866",
     "type": "cash", "unsettled_funds": "430.8200",
     "brokerage_account_type": "individual", "nickname": "Agentic",
     "is_default": False, "agentic_allowed": True,
     "option_level": "option_level_2", "management_type": "self_directed",
     "affiliate": "rhf", "state": "active", "deactivated": False,
     "permanently_deactivated": False},
]}}

REAL_GET_PORTFOLIO = {"data": {
    "total_value": "633.88", "equity_value": "0", "options_value": "0",
    "futures_value": "0", "event_contracts_value": "0", "crypto_value": "0",
    "cash": "633.88", "pending_deposits": "0", "mutual_funds_value": "0",
    "fixed_income_value": "0", "currency": "USD",
    "buying_power": {"buying_power": "203.0600",
                     "unleveraged_buying_power": "203.0600",
                     "display_currency": "USD"},
}}

REAL_GET_OPTION_POSITIONS_EMPTY = {"data": {"positions": []}}

AGENTIC_ACCOUNT_NUMBER = "902341866"


def _fake_mcp(overrides: dict | None = None):
    """A dispatcher stub keyed by short tool name, defaulting to the real
    captures above. ``overrides`` replaces individual tool responses."""
    responses = {
        "get_accounts": REAL_GET_ACCOUNTS,
        "get_portfolio": REAL_GET_PORTFOLIO,
        "get_option_positions": REAL_GET_OPTION_POSITIONS_EMPTY,
    }
    responses.update(overrides or {})

    def mcp(tool, params):
        return responses[tool]

    return mcp


def _broker(account_number=AGENTIC_ACCOUNT_NUMBER, overrides=None):
    cfg = RuntimeConfig(account_number=account_number, dry_run=True, armed=False)
    return RobinhoodMcpBroker(cfg, mcp_call=_fake_mcp(overrides), kill_state=KillState())


class RealAccountsAndPortfolioParsing(unittest.TestCase):
    def test_agentic_account_parses_correctly(self):
        broker = _broker()
        acct = broker.get_account()
        self.assertEqual(acct.account_number, AGENTIC_ACCOUNT_NUMBER)
        self.assertTrue(acct.agentic_allowed)
        self.assertEqual(acct.option_level, "option_level_2")
        self.assertTrue(acct.options_approved)
        self.assertEqual(acct.balance, 633.88)
        # Settled cash is buying power (203.06), NOT the top-level cash
        # figure (633.88), because 430.82 of that cash is unsettled.
        self.assertEqual(acct.settled_cash, 203.06)
        self.assertEqual(acct.unsettled_cash, 430.82)

    def test_account_selection_picks_configured_account_not_first_row(self):
        # The FIRST row in REAL_GET_ACCOUNTS is the margin account
        # (agentic_allowed=False); cfg.account_number names the second
        # (agentic) row. Selection must match on account_number, never
        # blindly take rows[0].
        broker = _broker(account_number=AGENTIC_ACCOUNT_NUMBER)
        acct = broker.get_account()
        self.assertEqual(acct.account_number, AGENTIC_ACCOUNT_NUMBER)
        self.assertTrue(acct.agentic_allowed)

    def test_margin_account_selected_when_configured(self):
        broker = _broker(account_number="812234458")
        acct = broker.get_account()
        self.assertEqual(acct.account_number, "812234458")
        self.assertFalse(acct.agentic_allowed)

    def test_empty_positions_parse_to_empty_list_not_raise(self):
        broker = _broker()
        self.assertEqual(broker.get_positions(), [])

    def test_missing_buying_power_still_raises_and_trips_kill(self):
        bad_portfolio = {"data": {
            "total_value": "633.88", "cash": "633.88",
        }}  # no buying_power at all
        broker = _broker(overrides={"get_portfolio": bad_portfolio})
        with self.assertRaises(McpDispatchError):
            broker.get_account()
        self.assertTrue(broker.kill.mcp_error)

    def test_settled_cash_never_silently_falls_back_to_cash(self):
        # Guardrail-load-bearing: even though "cash" (633.88) is present and
        # numeric, it must never be used for settled_cash when buying_power
        # is missing — that would let a trade size against unsettled funds.
        bad_portfolio = {"data": {"total_value": "633.88", "cash": "633.88"}}
        broker = _broker(overrides={"get_portfolio": bad_portfolio})
        with self.assertRaises(McpDispatchError):
            broker.get_account()

    def test_legacy_results_envelope_still_parses(self):
        # Pre-existing shape used elsewhere/other tests — must keep working.
        legacy_accounts = {"results": [{
            "account_number": "A1", "agentic_allowed": True,
            "option_level": "option_level_2",
        }]}
        # Only the ACCOUNTS envelope is legacy here. get_portfolio has exactly
        # one real shape ({"data": {...}}), so inventing a legacy variant for
        # it would test a payload the API never sends.
        legacy_portfolio = {"data": {
            "total_value": "1000.00",
            "buying_power": {"buying_power": "900.00"},
        }}
        broker = _broker(account_number="A1", overrides={
            "get_accounts": legacy_accounts,
            "get_portfolio": legacy_portfolio,
        })
        acct = broker.get_account()
        self.assertEqual(acct.balance, 1000.00)
        self.assertEqual(acct.settled_cash, 900.00)


if __name__ == "__main__":
    unittest.main()
