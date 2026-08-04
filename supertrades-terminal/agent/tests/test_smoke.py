"""Smoke-test tests — the READ-ONLY diagnostic command must refuse to run
outside its pre-arm invariant, refuse cleanly with no credentials, dispatch
only non-mutating tool names, and never let one failed check abort the rest.
Pure stdlib; NO real MCP tool is ever called — every transport here is an
in-memory fake.

    cd supertrades-terminal && python -m unittest agent.tests.test_smoke -v

Also covers ``preflight()`` — the go/no-go gate before ``tiny_live``,
including the account-pinning rule (migrated from the retired
``agent/mcp_dispatch.py`` / ``test_rh_wire.py`` — see ``PreflightGoNoGo``
below).
"""

from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from agent import cli
from agent.broker.mcp_dispatch import (
    MCP_TOOL_PREFIX,
    REFUSED_TOOLS,
    _MUTATING_PREFIXES,
    McpDispatchError,
)
from agent.broker.robinhood_mcp import RobinhoodMcpBroker
from agent.config import RuntimeConfig
from agent.kill_switch import KillState
from agent.models import AccountState
from agent.smoke import SmokeRefused, build_checks, preflight, run_smoke


class RecordingTransport:
    """In-memory fake transport. Nothing ever leaves the process."""

    def __init__(self, responses: dict | None = None, fail_on: set | None = None):
        self.calls: list[tuple[str, dict]] = []
        self.responses = responses or {}
        self.fail_on = fail_on or set()

    def __call__(self, full_tool: str, params: dict):
        self.calls.append((full_tool, params))
        short = full_tool.rsplit("__", 1)[-1]
        if short in self.fail_on:
            raise ConnectionError(f"simulated network failure for {short}")
        return self.responses.get(full_tool, {"results": []})


# Real schema: eligibility on get_accounts, balance/buying-power on get_portfolio,
# Greeks nested under results[].quote.
GOOD_ACCOUNT = {"data": {"accounts": [{
    "account_number": "A1", "agentic_allowed": True,
    "option_level": "option_level_2",
}]}}
GOOD_PORTFOLIO = {"data": {"total_value": "25000",
                           "buying_power": {"buying_power": "25000"},
                           "cash": "25000"}}
GOOD_INSTRUMENT = {"results": [
    {"id": "i1", "type": "call", "strike_price": "202.5"}]}
GOOD_QUOTE = {"results": [
    {"quote": {"bid_price": "1.18", "ask_price": "1.24", "delta": "0.5", "gamma": "0.05"}}]}
BAD_QUOTE_MISSING_DELTA = {"results": [
    {"quote": {"bid_price": "1.18", "ask_price": "1.24"}}]}


def _responses_for(watchlist, quote_by_symbol=None):
    quote_by_symbol = quote_by_symbol or {}
    resp = {
        MCP_TOOL_PREFIX + "get_accounts": GOOD_ACCOUNT,
        MCP_TOOL_PREFIX + "get_portfolio": GOOD_PORTFOLIO,
        MCP_TOOL_PREFIX + "get_option_positions": {"results": []},
        MCP_TOOL_PREFIX + "get_option_instruments": GOOD_INSTRUMENT,
        MCP_TOOL_PREFIX + "get_option_quotes": GOOD_QUOTE,
    }
    resp.update(quote_by_symbol)
    return resp


INERT = RuntimeConfig(account_number="A1", dry_run=True, armed=False)


class PreflightGate(unittest.TestCase):
    def test_refuses_when_armed_true(self):
        cfg = RuntimeConfig(account_number="A1", dry_run=True, armed=True)
        with self.assertRaises(SmokeRefused):
            run_smoke(cfg, transport=RecordingTransport())

    def test_refuses_when_dry_run_false(self):
        cfg = RuntimeConfig(account_number="A1", dry_run=False, armed=False)
        with self.assertRaises(SmokeRefused):
            run_smoke(cfg, transport=RecordingTransport())

    def test_refuses_before_touching_the_transport(self):
        cfg = RuntimeConfig(account_number="A1", dry_run=False, armed=True)
        transport = RecordingTransport()
        with self.assertRaises(SmokeRefused):
            run_smoke(cfg, transport=transport)
        self.assertEqual(transport.calls, [])  # nothing dispatched at all

    def test_inert_config_is_accepted(self):
        transport = RecordingTransport(responses=_responses_for(["NVDA"]))
        results, code = run_smoke(INERT, transport=transport, watchlist=["NVDA"])
        self.assertEqual(code, 0)


class TokenMissingRefusesCleanly(unittest.TestCase):
    def test_no_token_raises_dispatch_error_not_traceback_worthy_exception(self):
        old = os.environ.pop("ROBINHOOD_MCP_TOKEN", None)
        try:
            with self.assertRaises(McpDispatchError):
                run_smoke(INERT)  # no transport override -> real HTTP transport
        finally:
            if old is not None:
                os.environ["ROBINHOOD_MCP_TOKEN"] = old

    def test_cli_smoke_refuses_cleanly_without_token(self):
        old = os.environ.pop("ROBINHOOD_MCP_TOKEN", None)
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(["smoke"])
            self.assertNotEqual(code, 0)
            out = buf.getvalue()
            self.assertIn("Refusing to run", out)
            self.assertIn("ROBINHOOD_MCP_TOKEN", out)
        finally:
            if old is not None:
                os.environ["ROBINHOOD_MCP_TOKEN"] = old

    def test_cli_smoke_never_falls_back_to_paper_broker(self):
        # A missing token must not silently pass by routing through a fake —
        # assert the failure mode is the dispatcher's own McpDispatchError
        # message, not a "success" from an unwired/paper path.
        old = os.environ.pop("ROBINHOOD_MCP_TOKEN", None)
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(["smoke"])
            self.assertNotEqual(code, 0)
            self.assertNotIn("checks passed", buf.getvalue())
        finally:
            if old is not None:
                os.environ["ROBINHOOD_MCP_TOKEN"] = old


class OnlyNonMutatingToolsDispatched(unittest.TestCase):
    def test_only_read_tool_names_hit_the_transport(self):
        watchlist = ["NVDA", "TSLA"]
        transport = RecordingTransport(responses=_responses_for(watchlist))
        run_smoke(INERT, transport=transport, watchlist=watchlist)
        called = {full.rsplit("__", 1)[-1] for full, _ in transport.calls}
        self.assertTrue(called)  # sanity: something was actually called
        for name in called:
            self.assertNotIn(name, REFUSED_TOOLS)
            self.assertFalse(
                name.startswith(_MUTATING_PREFIXES),
                f"smoke test must never dispatch a mutating-shaped tool: {name}",
            )
        # And specifically the expected read set — nothing extra snuck in.
        # (get_account also reads get_portfolio; the earnings blackout reads
        # get_earnings_calendar; get_chain goes straight to get_option_instruments.)
        expected = {"get_accounts", "get_portfolio", "get_option_positions",
                    "get_option_instruments", "get_option_quotes",
                    "get_earnings_calendar"}
        self.assertTrue(called.issubset(expected), called - expected)

    def test_build_checks_only_uses_broker_parsed_accessors(self):
        watchlist = ["NVDA"]
        transport = RecordingTransport(responses=_responses_for(watchlist))
        from agent.broker.robinhood_mcp import RobinhoodMcpBroker
        broker = RobinhoodMcpBroker.live(INERT, transport=transport)
        checks = build_checks(broker, watchlist)
        names = [n for n, _ in checks]
        self.assertIn("get_accounts (broker.get_account)", names)
        self.assertIn("get_option_positions (broker.get_positions)", names)
        self.assertTrue(any("get_option_chains:NVDA" in n for n in names))


class EarningsCheckSurfacesAFailClosedFeed(unittest.TestCase):
    """A blackout that fell back closed is a legitimate frozenset covering the
    whole watchlist. It must FAIL the smoke check, not pass quietly — that
    state means the armed agent would take no trade and merely look idle."""

    def _earnings_result(self, results):
        return next(r for r in results if "get_earnings_calendar" in r.name)

    def test_reachable_feed_passes_and_reports_the_blackout(self):
        watchlist = ["NVDA", "MSFT"]
        resp = _responses_for(watchlist)
        resp[MCP_TOOL_PREFIX + "get_earnings_calendar"] = {"results": [
            {"symbol": "MSFT", "report": {"date": "2026-07-29", "timing": "pm"}},
        ]}
        results, _ = run_smoke(
            INERT, transport=RecordingTransport(responses=resp), watchlist=watchlist)
        check = self._earnings_result(results)
        self.assertTrue(check.ok, check.error)

    def test_unreachable_feed_fails_the_check(self):
        watchlist = ["NVDA", "MSFT"]
        transport = RecordingTransport(
            responses=_responses_for(watchlist),
            fail_on={"get_earnings_calendar"},
        )
        results, code = run_smoke(INERT, transport=transport, watchlist=watchlist)
        check = self._earnings_result(results)
        self.assertFalse(check.ok)
        self.assertIn("failed closed", check.error)
        self.assertEqual(code, 1)


class MidRunFailureDoesNotAbort(unittest.TestCase):
    def test_one_failed_check_does_not_skip_the_rest(self):
        watchlist = ["NVDA", "TSLA", "AMD"]
        transport = RecordingTransport(
            responses=_responses_for(watchlist),
            fail_on={"get_option_positions"},
        )
        results, code = run_smoke(INERT, transport=transport, watchlist=watchlist)
        self.assertEqual(code, 1)
        names = [r.name for r in results]
        # every check ran, including the ones after the failure
        # (account + positions + one per symbol + earnings)
        self.assertEqual(len(results), 3 + len(watchlist))
        by_name = {r.name: r for r in results}
        failed = [r for r in results if not r.ok]
        self.assertEqual(len(failed), 1)
        self.assertIn("get_option_positions", failed[0].name)
        self.assertIn("simulated network failure", failed[0].error)
        # the chain checks after the failed positions check still executed and passed
        chain_results = [r for r in results if "get_option_chains" in r.name]
        self.assertEqual(len(chain_results), len(watchlist))
        for r in chain_results:
            self.assertTrue(r.ok, r.error)

    def test_parse_failure_reports_the_real_exception_text(self):
        watchlist = ["NVDA"]
        transport = RecordingTransport(responses=_responses_for(
            watchlist,
            {MCP_TOOL_PREFIX + "get_option_quotes": BAD_QUOTE_MISSING_DELTA},
        ))
        results, code = run_smoke(INERT, transport=transport, watchlist=watchlist)
        self.assertEqual(code, 1)
        chain_result = next(r for r in results if "get_option_chains" in r.name)
        self.assertFalse(chain_result.ok)
        self.assertIn("delta", chain_result.error.lower())


class ExitCodeTally(unittest.TestCase):
    def test_zero_when_all_pass(self):
        watchlist = ["NVDA"]
        transport = RecordingTransport(responses=_responses_for(watchlist))
        _, code = run_smoke(INERT, transport=transport, watchlist=watchlist)
        self.assertEqual(code, 0)

    def test_nonzero_when_any_fails(self):
        watchlist = ["NVDA"]
        transport = RecordingTransport(
            responses=_responses_for(watchlist), fail_on={"get_accounts"})
        _, code = run_smoke(INERT, transport=transport, watchlist=watchlist)
        self.assertEqual(code, 1)


class OnlyOneDispatcherExists(unittest.TestCase):
    """``agent/mcp_dispatch.py`` (the earlier, blocklist-based, non-kill-wired
    parallel dispatcher) is retired. This guards against it reappearing —
    accidentally restored by a merge, a stray revert, etc. The production
    dispatcher lives at ``agent/broker/mcp_dispatch.py`` only."""

    def test_top_level_mcp_dispatch_module_does_not_exist(self):
        import importlib
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("agent.mcp_dispatch")

    def test_top_level_mcp_dispatch_file_is_gone(self):
        import agent
        from pathlib import Path
        self.assertFalse(
            (Path(agent.__file__).parent / "mcp_dispatch.py").exists())


AGENTIC = "902341866"
OTHER = "812234458"

# Two-account get_accounts response — one agentic, one not — matching the
# real live-captured shape (see agent/broker/robinhood_mcp.py docstring).
TWO_ACCOUNTS = {"data": {"accounts": [
    {"account_number": OTHER, "agentic_allowed": False, "option_level": "option_level_2"},
    {"account_number": AGENTIC, "agentic_allowed": True, "option_level": "option_level_2"},
]}}
GOOD_PORTFOLIO_2 = {"data": {"total_value": "434.36", "options_value": "0",
                             "cash": "334.36", "buying_power": {"buying_power": "334.36"}}}
ZERO_CASH_PORTFOLIO = {"data": {"total_value": "434.36", "options_value": "0",
                                "cash": "0", "buying_power": {"buying_power": "0"}}}


def _preflight_mcp(accounts=TWO_ACCOUNTS, portfolio=GOOD_PORTFOLIO_2):
    def call(tool, params):
        if tool == "get_accounts":
            return accounts
        if tool == "get_portfolio":
            return portfolio
        return {}
    return call


def _preflight_broker(account_number, **overrides):
    accounts = overrides.pop("accounts", TWO_ACCOUNTS)
    portfolio = overrides.pop("portfolio", GOOD_PORTFOLIO_2)
    cfg = RuntimeConfig(account_number=account_number, dry_run=True, armed=False, **overrides)
    return RobinhoodMcpBroker(cfg, _preflight_mcp(accounts, portfolio))


class PreflightGoNoGo(unittest.TestCase):
    def test_passes_on_a_good_account(self):
        ok, reasons, acct = preflight(_preflight_broker(AGENTIC))
        self.assertTrue(ok, reasons)
        self.assertEqual(acct.account_number, AGENTIC)

    def test_fails_when_not_agentic(self):
        ok, reasons, _ = preflight(_preflight_broker(OTHER))
        self.assertFalse(ok)
        self.assertTrue(any("agentic" in r for r in reasons), reasons)

    def test_fails_when_option_level_below_2(self):
        accounts = {"data": {"accounts": [
            {"account_number": AGENTIC, "agentic_allowed": True, "option_level": "option_level_0"},
        ]}}
        ok, reasons, _ = preflight(_preflight_broker(AGENTIC, accounts=accounts))
        self.assertFalse(ok)
        self.assertTrue(any("option level" in r for r in reasons), reasons)

    def test_fails_when_settled_cash_is_zero(self):
        ok, reasons, _ = preflight(
            _preflight_broker(AGENTIC, portfolio=ZERO_CASH_PORTFOLIO))
        self.assertFalse(ok)
        self.assertTrue(any("settled buying power" in r for r in reasons), reasons)

    def test_fails_when_account_number_is_unset(self):
        ok, reasons, acct = preflight(_preflight_broker(None))
        self.assertFalse(ok)
        self.assertTrue(any("account_number is unset" in r for r in reasons), reasons)
        # A live account was still readable (inference resolved *something*
        # for get_account()) — the point is preflight refuses to trust it.
        self.assertIsNotNone(acct)

    def test_fails_when_configured_account_number_is_not_agentic_allowed(self):
        # Pinned to the non-agentic account explicitly — must fail even though
        # it matches a real row, because that row isn't agentic_allowed.
        ok, reasons, _ = preflight(_preflight_broker(OTHER))
        self.assertFalse(ok)
        self.assertTrue(
            any("does not match an agentic_allowed account" in r for r in reasons),
            reasons,
        )

    def test_fails_when_configured_account_number_matches_no_row_at_all(self):
        ok, reasons, _ = preflight(_preflight_broker("no-such-account"))
        self.assertFalse(ok)
        self.assertTrue(
            any("does not match an agentic_allowed account" in r for r in reasons),
            reasons,
        )

    def test_soft_fails_when_account_read_raises(self):
        class Unreadable(RobinhoodMcpBroker):
            def get_account(self):
                raise RuntimeError("boom")

        cfg = RuntimeConfig(account_number=AGENTIC, dry_run=True, armed=False)
        broker = Unreadable(cfg, _preflight_mcp())
        ok, reasons, acct = preflight(broker)
        self.assertFalse(ok)
        self.assertIsNone(acct)
        self.assertTrue(any("cannot read account" in r for r in reasons), reasons)


if __name__ == "__main__":
    unittest.main()
