"""Dispatcher tests — the live MCP wiring must fail closed and never let a
mutating call around the dry-run/armed gates. Pure stdlib; NO real MCP tool is
ever called: every transport here is an in-memory fake.

    cd supertrades-terminal && python -m unittest agent.tests.test_mcp_dispatch -v
"""

from __future__ import annotations

import json
import os
import socket
import unittest
from datetime import datetime
from unittest.mock import patch

from agent.broker.mcp_dispatch import (
    DEFAULT_MCP_URL,
    MCP_TOOL_PREFIX,
    McpDispatchError,
    McpDispatcher,
    RobinhoodMcpHttpTransport,
    URL_ENV,
    live_dispatcher,
)
from agent.broker.robinhood_mcp import RobinhoodMcpBroker
from agent.config import MARKET_TZ, RuntimeConfig
from agent.kill_switch import KillState, check as kill_check
from agent.models import OrderIntent


def et(h, m):
    return datetime(2026, 7, 20, h, m, tzinfo=MARKET_TZ)


# Real schema: get_accounts carries eligibility (NOT balance); buying power and
# balance come from get_portfolio.
ELIGIBLE_ACCOUNT = {"data": {"accounts": [{
    "account_number": "A1", "agentic_allowed": True,
    "option_level": "option_level_2",
}]}}
ELIGIBLE_PORTFOLIO = {"data": {"total_value": "25000",
                               "buying_power": {"buying_power": "25000"},
                               "cash": "25000"}}


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
        # An equity quote is read-only and harmlessly shaped, but this agent
        # trades options only and never allowlisted it — unsupported still
        # means nothing goes to the wire.
        disp, transport, _ = make(INERT)
        with self.assertRaises(McpDispatchError):
            disp("get_equity_quotes", {})
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
        broker, transport, _ = self._broker(INERT, responses={
            MCP_TOOL_PREFIX + "get_accounts": ELIGIBLE_ACCOUNT,
            MCP_TOOL_PREFIX + "get_portfolio": ELIGIBLE_PORTFOLIO})
        acct = broker.get_account()
        self.assertEqual(acct.balance, 25000.0)          # from get_portfolio
        self.assertEqual(acct.settled_cash, 25000.0)     # buying_power.buying_power
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
            MCP_TOOL_PREFIX + "get_portfolio": ELIGIBLE_PORTFOLIO,
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


class _FakeHttpResponse:
    """Minimal stand-in for the ``http.client.HTTPResponse`` context manager
    ``urllib.request.urlopen`` returns. ``read(n)`` hands back queued chunks
    one at a time so the transport's chunked-read loop is exercised."""

    def __init__(self, chunks: list[bytes], headers: dict | None = None):
        self._chunks = list(chunks)
        self.headers = headers or {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, n: int = -1) -> bytes:
        if self._chunks:
            return self._chunks.pop(0)
        return b""


def _rpc_body(req_id: int, results: list[dict]) -> bytes:
    return json.dumps({
        "jsonrpc": "2.0", "id": req_id,
        "result": {"structuredContent": {"results": results}},
    }).encode("utf-8")


class HttpTransportUrlValidation(unittest.TestCase):
    """Defect A: the resolved endpoint must be https and pinned to the real
    Robinhood host — never plaintext, never an attacker-controlled host."""

    def test_https_default_url_is_accepted(self):
        t = RobinhoodMcpHttpTransport(token="t")
        self.assertEqual(t.url, DEFAULT_MCP_URL)

    def test_http_scheme_rejected(self):
        with self.assertRaises(McpDispatchError) as ctx:
            RobinhoodMcpHttpTransport(
                url="http://agent.robinhood.com/mcp/trading", token="t")
        self.assertIn("https", str(ctx.exception))

    def test_attacker_host_rejected(self):
        with self.assertRaises(McpDispatchError) as ctx:
            RobinhoodMcpHttpTransport(
                url="https://agent.robinhood.com.evil.example/mcp", token="t")
        self.assertIn("evil", str(ctx.exception).lower())

    def test_unrelated_https_host_rejected(self):
        with self.assertRaises(McpDispatchError):
            RobinhoodMcpHttpTransport(url="https://example.com/mcp", token="t")

    def test_localhost_not_special_cased(self):
        with self.assertRaises(McpDispatchError):
            RobinhoodMcpHttpTransport(url="https://localhost/mcp", token="t")

    def test_subdomain_of_expected_host_accepted(self):
        t = RobinhoodMcpHttpTransport(
            url="https://eu.agent.robinhood.com/mcp/trading", token="t")
        self.assertTrue(t.url.startswith("https://eu.agent.robinhood.com"))

    def test_env_var_url_is_still_validated(self):
        old = os.environ.get(URL_ENV)
        os.environ[URL_ENV] = "http://agent.robinhood.com/mcp/trading"
        try:
            with self.assertRaises(McpDispatchError):
                RobinhoodMcpHttpTransport(token="t")
        finally:
            if old is None:
                os.environ.pop(URL_ENV, None)
            else:
                os.environ[URL_ENV] = old

    def test_allow_insecure_url_opt_out_works_when_explicit(self):
        t = RobinhoodMcpHttpTransport(
            url="http://localhost:9999/mcp", token="t", allow_insecure_url=True)
        self.assertEqual(t.url, "http://localhost:9999/mcp")

    def test_allow_insecure_url_not_enabled_by_default(self):
        # No kwarg passed at all — the default must reject, never silently
        # allow. (Regression guard: catches a future `allow_insecure_url=True`
        # default sneaking in.)
        with self.assertRaises(McpDispatchError):
            RobinhoodMcpHttpTransport(url="http://localhost:9999/mcp", token="t")

    def test_allow_insecure_url_is_not_env_configurable(self):
        # There must be no env var that flips this on — only the explicit
        # constructor kwarg. Setting an unrelated/plausible env var must not
        # bypass validation.
        old = os.environ.get(URL_ENV)
        os.environ[URL_ENV] = "http://localhost:9999/mcp"
        os.environ["ROBINHOOD_MCP_ALLOW_INSECURE"] = "true"  # not a real knob
        try:
            with self.assertRaises(McpDispatchError):
                RobinhoodMcpHttpTransport(token="t")
        finally:
            os.environ.pop("ROBINHOOD_MCP_ALLOW_INSECURE", None)
            if old is None:
                os.environ.pop(URL_ENV, None)
            else:
                os.environ[URL_ENV] = old


class HttpTransportDeadlineAndSize(unittest.TestCase):
    """Defect C: an overall wall-clock deadline and a response body cap."""

    @patch("urllib.request.urlopen")
    def test_oversized_response_rejected(self, mock_urlopen):
        mock_urlopen.return_value = _FakeHttpResponse([b"x" * 1000])
        t = RobinhoodMcpHttpTransport(token="t", max_response_bytes=10)
        with self.assertRaises(McpDispatchError) as ctx:
            t(MCP_TOOL_PREFIX + "get_accounts", {})
        self.assertIn("max body size", str(ctx.exception))

    def test_overall_deadline_exceeded_rejected(self):
        # A deadline that has already elapsed must fail before any I/O.
        t = RobinhoodMcpHttpTransport(
            token="t", overall_deadline_seconds=0.0)
        with self.assertRaises(McpDispatchError) as ctx:
            t(MCP_TOOL_PREFIX + "get_accounts", {})
        self.assertIn("deadline", str(ctx.exception))

    def test_deadline_and_cap_are_configurable(self):
        t = RobinhoodMcpHttpTransport(
            token="t", overall_deadline_seconds=42.0, max_response_bytes=123)
        self.assertEqual(t.overall_deadline, 42.0)
        self.assertEqual(t.max_response_bytes, 123)

    def test_default_deadline_sits_above_socket_timeout(self):
        t = RobinhoodMcpHttpTransport(token="t", timeout_seconds=10.0)
        self.assertGreater(t.overall_deadline, t.timeout)


class HttpTransportMutationReconciliation(unittest.TestCase):
    """Defect B: a transport-level failure on a mutating call must trigger
    exactly one read-only reconciliation, never a bare "it failed"."""

    def _transport(self):
        return RobinhoodMcpHttpTransport(token="t")

    @patch("urllib.request.urlopen")
    def test_timed_out_place_found_on_reconciliation_is_unknown_not_failed(
            self, mock_urlopen):
        def side_effect(req, timeout=None):
            if mock_urlopen.call_count == 1:
                raise socket.timeout("timed out")
            return _FakeHttpResponse([_rpc_body(
                2, [{"ref_id": "REF-1", "id": "ORDER-9"}])])
        mock_urlopen.side_effect = side_effect

        t = self._transport()
        with self.assertRaises(McpDispatchError) as ctx:
            t(MCP_TOOL_PREFIX + "place_option_order",
              {"ref_id": "REF-1", "account_number": "A1"})
        msg = str(ctx.exception)
        self.assertIn("REF-1", msg)
        self.assertIn("UNKNOWN", msg)
        self.assertIn("MAY HAVE BEEN PLACED", msg)
        self.assertIn("ORDER-9", msg)
        self.assertNotIn("not placed", msg)  # must not claim it failed

    @patch("urllib.request.urlopen")
    def test_timed_out_place_not_found_on_reconciliation_reports_not_placed(
            self, mock_urlopen):
        def side_effect(req, timeout=None):
            if mock_urlopen.call_count == 1:
                raise socket.timeout("timed out")
            return _FakeHttpResponse([_rpc_body(2, [])])
        mock_urlopen.side_effect = side_effect

        t = self._transport()
        with self.assertRaises(McpDispatchError) as ctx:
            t(MCP_TOOL_PREFIX + "place_option_order",
              {"ref_id": "REF-2", "account_number": "A1"})
        msg = str(ctx.exception)
        self.assertIn("REF-2", msg)
        self.assertIn("not placed", msg)

    @patch("urllib.request.urlopen")
    def test_reconciliation_failure_reported_as_unverifiable_not_failed(
            self, mock_urlopen):
        mock_urlopen.side_effect = socket.timeout("timed out")  # every call
        t = self._transport()
        with self.assertRaises(McpDispatchError) as ctx:
            t(MCP_TOOL_PREFIX + "place_option_order",
              {"ref_id": "REF-3", "account_number": "A1"})
        msg = str(ctx.exception)
        self.assertIn("REF-3", msg)
        self.assertIn("UNKNOWN", msg)
        self.assertIn("UNVERIFIABLE", msg)
        # Never claim it failed outright — state is unknown, not negative.
        self.assertNotIn("the order failed", msg.lower())

    @patch("urllib.request.urlopen")
    def test_reconciliation_never_issues_a_mutating_call(self, mock_urlopen):
        bodies: list[dict] = []

        def side_effect(req, timeout=None):
            bodies.append(json.loads(req.data))
            if len(bodies) == 1:
                raise socket.timeout("timed out")
            return _FakeHttpResponse([_rpc_body(2, [])])
        mock_urlopen.side_effect = side_effect

        t = self._transport()
        with self.assertRaises(McpDispatchError):
            t(MCP_TOOL_PREFIX + "place_option_order", {"ref_id": "REF-4"})
        self.assertEqual(len(bodies), 2)
        self.assertEqual(bodies[0]["params"]["name"], "place_option_order")
        self.assertEqual(bodies[1]["params"]["name"], "get_option_orders")

    @patch("urllib.request.urlopen")
    def test_non_mutating_read_failure_does_not_reconcile(self, mock_urlopen):
        calls = []

        def side_effect(req, timeout=None):
            calls.append(req)
            raise socket.timeout("timed out")
        mock_urlopen.side_effect = side_effect

        t = self._transport()
        with self.assertRaises(McpDispatchError):
            t(MCP_TOOL_PREFIX + "get_accounts", {})
        self.assertEqual(len(calls), 1)  # no reconciliation attempt at all


if __name__ == "__main__":
    unittest.main()
