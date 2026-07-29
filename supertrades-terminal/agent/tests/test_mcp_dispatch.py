"""Dispatcher tests — the live MCP wiring must fail closed and never let a
mutating call around the dry-run/armed gates. Pure stdlib; NO real MCP tool is
ever called: every transport here is an in-memory fake.

    cd supertrades-terminal && python -m unittest agent.tests.test_mcp_dispatch -v
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime

from agent.broker.mcp_dispatch import (
    MCP_TOOL_PREFIX,
    McpDispatchError,
    McpDispatcher,
    RobinhoodMcpHttpTransport,
    live_dispatcher,
)
from agent.broker.robinhood_mcp import RobinhoodMcpBroker
from agent.config import MARKET_TZ, RuntimeConfig
from agent.kill_switch import KillState, check as kill_check
from agent.models import OrderIntent


def et(h, m):
    return datetime(2026, 7, 20, h, m, tzinfo=MARKET_TZ)


ELIGIBLE_ACCOUNT = {"results": [{
    "account_number": "A1", "agentic_allowed": True,
    "option_level": "option_level_2",
    "portfolio_value": 25000, "settled_cash": 25000,
}]}


class RecordingTransport:
    """In-memory fake transport. Nothing ever leaves the process."""

    def __init__(self, responses: dict | None = None, error: Exception | None = None):
        self.calls: list[tuple[str, dict]] = []
        self.responses = responses or {}
        self.error = error

    def __call__(self, full_tool: str, params: dict):
        self.calls.append((full_tool, params))
        if self.error is not None:
            raise self.error
        return self.responses.get(full_tool, {"results": []})


def make(cfg: RuntimeConfig, **kw):
    transport = RecordingTransport(**kw)
    kill = KillState()
    return McpDispatcher(transport, cfg, kill), transport, kill


INERT = RuntimeConfig(account_number="A1", dry_run=True, armed=False)
ARMED = RuntimeConfig(account_number="A1", dry_run=False, armed=True)  # fakes only


def intent():
    return OrderIntent("NVDA", "oid-1", "buy", "open", 3, 1.21, "entry")


class DispatcherReads(unittest.TestCase):
    def test_read_dispatches_full_tool_name(self):
        disp, transport, kill = make(INERT)
        out = disp("get_accounts", {})
        self.assertEqual(transport.calls[0][0], MCP_TOOL_PREFIX + "get_accounts")
        self.assertEqual(out, {"results": []})
        self.assertFalse(kill.mcp_error)

    def test_read_passes_params_through(self):
        disp, transport, _ = make(INERT)
        disp("get_option_chains", {"underlying_symbol": "NVDA"})
        self.assertEqual(transport.calls[0][1], {"underlying_symbol": "NVDA"})

    def test_review_is_a_read_and_allowed_while_inert(self):
        disp, transport, kill = make(INERT, responses={
            MCP_TOOL_PREFIX + "review_option_order": {"quote": {}, "order_checks": []}})
        out = disp("review_option_order", {"quantity": "1"})
        self.assertIn("quote", out)
        self.assertFalse(kill.mcp_error)

    def test_list_response_passes_through(self):
        disp, _, _ = make(INERT, responses={
            MCP_TOOL_PREFIX + "get_option_positions": [{"option_id": "x"}]})
        self.assertEqual(disp("get_option_positions", {}), [{"option_id": "x"}])


class DispatcherFailClosed(unittest.TestCase):
    def _assert_killed(self, kill):
        self.assertTrue(kill.mcp_error)
        self.assertTrue(kill_check(kill, et(14, 0)).triggered)

    def test_transport_exception_raises_and_trips_kill(self):
        disp, _, kill = make(INERT, error=ConnectionError("boom"))
        with self.assertRaises(McpDispatchError):
            disp("get_accounts", {})
        self._assert_killed(kill)

    def test_timeout_raises_and_trips_kill(self):
        disp, _, kill = make(INERT, error=TimeoutError("MCP timed out"))
        with self.assertRaises(McpDispatchError):
            disp("get_option_quotes", {"instrument_ids": ["i"]})
        self._assert_killed(kill)

    def test_unparseable_response_raises_and_trips_kill(self):
        disp, _, kill = make(INERT, responses={
            MCP_TOOL_PREFIX + "get_accounts": "not-a-json-object"})
        with self.assertRaises(McpDispatchError):
            disp("get_accounts", {})
        self._assert_killed(kill)

    def test_none_response_raises_and_trips_kill(self):
        disp, _, kill = make(INERT, responses={MCP_TOOL_PREFIX + "get_accounts": None})
        with self.assertRaises(McpDispatchError):
            disp("get_accounts", {})
        self._assert_killed(kill)

    def test_error_payload_raises_and_trips_kill(self):
        disp, _, kill = make(INERT, responses={
            MCP_TOOL_PREFIX + "get_accounts": {"error": "rate limited"}})
        with self.assertRaises(McpDispatchError):
            disp("get_accounts", {})
        self._assert_killed(kill)

    def test_iserror_payload_raises_and_trips_kill(self):
        disp, _, kill = make(INERT, responses={
            MCP_TOOL_PREFIX + "get_accounts": {"isError": True, "content": []}})
        with self.assertRaises(McpDispatchError):
            disp("get_accounts", {})
        self._assert_killed(kill)

    def test_unknown_tool_never_dispatched(self):
        disp, transport, _ = make(INERT)
        with self.assertRaises(McpDispatchError):
            disp("get_earnings_calendar", {})
        self.assertEqual(transport.calls, [])

    def test_exercise_refused_even_when_armed(self):
        disp, transport, kill = make(ARMED)
        with self.assertRaises(McpDispatchError):
            disp("exercise_option", {"option_id": "x"})
        self.assertEqual(transport.calls, [])
        self._assert_killed(kill)

    def test_equity_order_refused_even_when_armed(self):
        disp, transport, kill = make(ARMED)
        with self.assertRaises(McpDispatchError):
            disp("place_equity_order", {"symbol": "NVDA"})
        self.assertEqual(transport.calls, [])
        self._assert_killed(kill)


class DispatcherMutationGate(unittest.TestCase):
    """The dispatcher's defense-in-depth re-check of the SAME armed/dry_run
    config the broker gates on — never a second policy, never a bypass."""

    def test_place_with_dry_run_true_dispatches_nothing(self):
        disp, transport, kill = make(RuntimeConfig(dry_run=True, armed=True))
        with self.assertRaises(McpDispatchError):
            disp("place_option_order", {"quantity": "1"})
        self.assertEqual(transport.calls, [])          # NOTHING hit the wire
        self.assertTrue(kill.mcp_error)                # bypass attempt => kill

    def test_place_with_armed_false_dispatches_nothing(self):
        disp, transport, kill = make(RuntimeConfig(dry_run=False, armed=False))
        with self.assertRaises(McpDispatchError):
            disp("place_option_order", {"quantity": "1"})
        self.assertEqual(transport.calls, [])
        self.assertTrue(kill.mcp_error)

    def test_cancel_disarmed_dispatches_nothing(self):
        disp, transport, _ = make(INERT)
        with self.assertRaises(McpDispatchError):
            disp("cancel_option_order", {"order_id": "o"})
        self.assertEqual(transport.calls, [])

    def test_place_armed_live_dispatches_through_fake(self):
        disp, transport, kill = make(ARMED, responses={
            MCP_TOOL_PREFIX + "place_option_order": {"id": "ORDER-1"}})
        out = disp("place_option_order", {"quantity": "1"})
        self.assertEqual(out["id"], "ORDER-1")
        self.assertEqual(transport.calls[0][0], MCP_TOOL_PREFIX + "place_option_order")
        self.assertFalse(kill.mcp_error)


class BrokerThroughDispatcher(unittest.TestCase):
    """RobinhoodMcpBroker wired with the real dispatcher (fake transport):
    the EXISTING broker gates stay the one code path for placement."""

    def _broker(self, cfg, responses=None, error=None):
        transport = RecordingTransport(responses=responses, error=error)
        kill = KillState()
        broker = RobinhoodMcpBroker.live(cfg, kill_state=kill, transport=transport)
        return broker, transport, kill

    # --- THE required test: dry_run/disarmed place dispatches NOTHING ------
    def test_place_order_dry_run_true_dispatches_nothing(self):
        broker, transport, kill = self._broker(
            RuntimeConfig(account_number="A1", dry_run=True, armed=False))
        res = broker.place_order(intent())
        self.assertFalse(res.placed)
        self.assertTrue(res.dry_run)
        self.assertEqual(transport.calls, [])          # zero MCP traffic
        self.assertFalse(kill.mcp_error)

    def test_place_order_armed_false_dispatches_nothing(self):
        broker, transport, _ = self._broker(
            RuntimeConfig(account_number="A1", dry_run=False, armed=False))
        res = broker.place_order(intent())
        self.assertFalse(res.placed)
        self.assertEqual(transport.calls, [])

    def test_place_order_dry_run_even_if_armed_dispatches_nothing(self):
        broker, transport, _ = self._broker(
            RuntimeConfig(account_number="A1", dry_run=True, armed=True))
        res = broker.place_order(intent())
        self.assertFalse(res.placed)
        self.assertEqual(transport.calls, [])

    def test_cancel_all_disarmed_dispatches_nothing(self):
        broker, transport, _ = self._broker(INERT)
        broker.cancel_all()
        self.assertEqual(transport.calls, [])

    # --- reads go direct, strict parsing, shared kill state ---------------
    def test_get_account_reads_direct_and_parses(self):
        broker, transport, _ = self._broker(
            INERT, responses={MCP_TOOL_PREFIX + "get_accounts": ELIGIBLE_ACCOUNT})
        acct = broker.get_account()
        self.assertEqual(acct.balance, 25000.0)
        self.assertEqual(transport.calls[0][0], MCP_TOOL_PREFIX + "get_accounts")

    def test_get_account_missing_balance_trips_kill(self):
        broker, _, kill = self._broker(INERT, responses={
            MCP_TOOL_PREFIX + "get_accounts": {"results": [{
                "account_number": "A1", "agentic_allowed": True,
                "option_level": "option_level_2"}]}})  # no balance anywhere
        with self.assertRaises(McpDispatchError):
            broker.get_account()
        self.assertTrue(kill.mcp_error)
        self.assertTrue(kill_check(kill, et(14, 0)).triggered)

    def test_get_chain_missing_delta_trips_kill(self):
        broker, _, kill = self._broker(INERT, responses={
            MCP_TOOL_PREFIX + "get_option_instruments": {"results": [
                {"id": "i1", "type": "call", "strike_price": "202.5"}]},
            MCP_TOOL_PREFIX + "get_option_quotes": {"results": [
                {"bid_price": "1.18", "ask_price": "1.24"}]},  # no delta Greek
        })
        with self.assertRaises(McpDispatchError):
            broker.get_chain("NVDA")
        self.assertTrue(kill.mcp_error)

    def test_positions_missing_mark_price_trips_kill(self):
        broker, _, kill = self._broker(INERT, responses={
            MCP_TOOL_PREFIX + "get_option_positions": {"results": [{
                "chain_symbol": "NVDA", "option_id": "o1", "type": "call",
                "strike_price": "202.5", "expiration_date": "2026-07-20",
                "quantity": "2", "average_price": "120"}]}})  # no mark_price
        with self.assertRaises(McpDispatchError):
            broker.get_positions()
        self.assertTrue(kill.mcp_error)

    def test_read_failure_trips_shared_kill_state(self):
        broker, _, kill = self._broker(INERT, error=ConnectionError("mcp down"))
        with self.assertRaises(McpDispatchError):
            broker.get_positions()
        self.assertTrue(kill.mcp_error)
        self.assertIs(broker.kill, kill)  # engine sharing this state will halt

    def test_armed_place_without_order_id_trips_kill(self):
        # Fakes only: armed cfg + fake transport; a dispatched order whose
        # response has no id is an unknown state => kill, never a blank id.
        broker, _, kill = self._broker(ARMED, responses={
            MCP_TOOL_PREFIX + "get_accounts": ELIGIBLE_ACCOUNT,
            MCP_TOOL_PREFIX + "place_option_order": {"state": "queued"}})
        with self.assertRaises(McpDispatchError):
            broker.place_order(intent())
        self.assertTrue(kill.mcp_error)


class HttpTransportInert(unittest.TestCase):
    def test_refuses_to_construct_without_token(self):
        with self.assertRaises(McpDispatchError):
            RobinhoodMcpHttpTransport(url="https://example.invalid/mcp", token="")

    def test_live_dispatcher_without_token_stays_inert(self):
        import os
        old = os.environ.pop("ROBINHOOD_MCP_TOKEN", None)
        try:
            with self.assertRaises(McpDispatchError):
                live_dispatcher(INERT, KillState())
        finally:
            if old is not None:
                os.environ["ROBINHOOD_MCP_TOKEN"] = old


class HttpTransportDecoding(unittest.TestCase):
    """Response decoding is pure functions — tested without any network."""

    def test_json_body_decodes(self):
        msg = RobinhoodMcpHttpTransport._extract_message(
            json.dumps({"jsonrpc": "2.0", "id": 1,
                        "result": {"content": [{"type": "text",
                                                "text": '{"results": []}'}]}}),
            "application/json", 1, "get_accounts")
        self.assertEqual(
            RobinhoodMcpHttpTransport._extract_result(msg, "get_accounts"),
            {"results": []})

    def test_sse_body_decodes(self):
        payload = ("event: message\n"
                   "data: " + json.dumps({"jsonrpc": "2.0", "id": 7,
                                          "result": {"structuredContent":
                                                     {"results": [1]}}}) + "\n\n")
        msg = RobinhoodMcpHttpTransport._extract_message(
            payload, "text/event-stream", 7, "get_accounts")
        self.assertEqual(
            RobinhoodMcpHttpTransport._extract_result(msg, "get_accounts"),
            {"results": [1]})

    def test_garbage_body_raises(self):
        with self.assertRaises(McpDispatchError):
            RobinhoodMcpHttpTransport._extract_message(
                "<html>proxy error</html>", "application/json", 1, "get_accounts")

    def test_jsonrpc_error_raises(self):
        with self.assertRaises(McpDispatchError):
            RobinhoodMcpHttpTransport._extract_result(
                {"id": 1, "error": {"code": -32000, "message": "denied"}},
                "place_option_order")

    def test_tool_iserror_raises(self):
        with self.assertRaises(McpDispatchError):
            RobinhoodMcpHttpTransport._extract_result(
                {"id": 1, "result": {"isError": True,
                                     "content": [{"type": "text", "text": "rejected"}]}},
                "review_option_order")

    def test_non_json_text_content_raises(self):
        with self.assertRaises(McpDispatchError):
            RobinhoodMcpHttpTransport._extract_result(
                {"id": 1, "result": {"content": [{"type": "text",
                                                  "text": "sorry, try again"}]}},
                "get_accounts")

    def test_empty_content_raises(self):
        with self.assertRaises(McpDispatchError):
            RobinhoodMcpHttpTransport._extract_result(
                {"id": 1, "result": {"content": []}}, "get_accounts")


if __name__ == "__main__":
    unittest.main()
