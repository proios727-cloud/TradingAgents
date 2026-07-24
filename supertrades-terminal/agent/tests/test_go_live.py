"""Tests for the staged go-live ladder and the deterministic pre-trade gate.

The gate is what makes "my final entrance is required" true instead of assumed,
so every rung and every denial path is pinned here. Pure stdlib; run with:

    cd supertrades-terminal && python -m unittest agent.tests.test_go_live -v
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent import go_live
from agent.go_live import STAGES, decide


def order(side="buy", effect="open", qty="1", price="0.50", otype="limit"):
    inp = {"legs": [{"option_id": "oid", "side": side, "position_effect": effect}],
           "quantity": qty, "type": otype}
    if price is not None:
        inp["price"] = price
    return inp


PLACE = "mcp__Robinhood_Trading__place_option_order"
CANCEL = "mcp__Robinhood_Trading__cancel_option_order"


class PreviewPaperStages(unittest.TestCase):
    def test_preview_denies_live_entry(self):
        d, _ = decide(PLACE, order(), STAGES["preview"], killed=False)
        self.assertEqual(d, "deny")

    def test_paper_denies_live_entry(self):
        d, _ = decide(PLACE, order(), STAGES["paper"], killed=False)
        self.assertEqual(d, "deny")

    def test_preview_not_armed_reason(self):
        _, why = decide(PLACE, order(), STAGES["preview"], killed=False)
        self.assertIn("not armed", why)


class TinyLiveStage(unittest.TestCase):
    def test_tiny_entry_within_caps_asks(self):
        # 1 contract @ $0.50 = $50 premium, under the $75 tiny cap -> human ask.
        d, why = decide(PLACE, order(qty="1", price="0.50"), STAGES["tiny_live"], killed=False)
        self.assertEqual(d, "ask")
        self.assertIn("Arm", why)

    def test_over_premium_cap_denies(self):
        # 1 contract @ $1.00 = $100 > $75 cap.
        d, _ = decide(PLACE, order(qty="1", price="1.00"), STAGES["tiny_live"], killed=False)
        self.assertEqual(d, "deny")

    def test_over_contract_cap_denies(self):
        # 2 contracts > 1-contract cap (even though 2*$0.20*100=$40 < $75).
        d, _ = decide(PLACE, order(qty="2", price="0.20"), STAGES["tiny_live"], killed=False)
        self.assertEqual(d, "deny")

    def test_market_entry_denied(self):
        d, why = decide(PLACE, order(otype="market", price=None), STAGES["tiny_live"], killed=False)
        self.assertEqual(d, "deny")
        self.assertIn("LIMIT", why)

    def test_zero_qty_denied(self):
        d, _ = decide(PLACE, order(qty="0", price="0.50"), STAGES["tiny_live"], killed=False)
        self.assertEqual(d, "deny")


class KillAndExits(unittest.TestCase):
    def test_kill_denies_new_entry(self):
        d, why = decide(PLACE, order(), STAGES["tiny_live"], killed=True)
        self.assertEqual(d, "deny")
        self.assertIn("KILL", why)

    def test_close_always_asks_even_under_kill(self):
        # Selling to close must stay available even during a kill and in preview.
        d, _ = decide(PLACE, order(side="sell", effect="close"), STAGES["preview"], killed=True)
        self.assertEqual(d, "ask")

    def test_cancel_always_asks_never_blocked(self):
        d, _ = decide(CANCEL, {"order_id": "x"}, STAGES["preview"], killed=True)
        self.assertEqual(d, "ask")


class ScaledStageAndSafety(unittest.TestCase):
    def test_scaled_defers_to_risk_gate(self):
        # scaled has no contract cap and a $1k premium ceiling; a normal entry asks.
        d, _ = decide(PLACE, order(qty="5", price="1.20"), STAGES["scaled"], killed=False)
        self.assertEqual(d, "ask")

    def test_scaled_still_caps_at_1000(self):
        d, _ = decide(PLACE, order(qty="10", price="1.50"), STAGES["scaled"], killed=False)  # $1,500
        self.assertEqual(d, "deny")

    def test_unknown_tool_denied(self):
        d, _ = decide("mcp__Robinhood_Trading__place_equity_order", order(), STAGES["tiny_live"], killed=False)
        self.assertEqual(d, "deny")

    def test_never_returns_allow(self):
        # Exhaustive: no input should ever auto-approve a live order.
        for stage in STAGES.values():
            for killed in (True, False):
                for o in (order(), order(side="sell", effect="close"),
                          order(qty="99", price="9.99"), order(otype="market", price=None)):
                    d, _ = decide(PLACE, o, stage, killed=killed)
                    self.assertIn(d, ("ask", "deny"))


class StagePersistence(unittest.TestCase):
    """set_stage -> load_stage must round-trip (regression: writer wrote 'name',
    reader read 'stage', so every load silently fell back to preview)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        d = Path(self._tmp.name)
        self._saved = (go_live._RUNTIME_DIR, go_live.STAGE_FILE, go_live.KILL_FILE)
        go_live._RUNTIME_DIR = d
        go_live.STAGE_FILE = d / "stage.json"
        go_live.KILL_FILE = d / "KILL"

    def tearDown(self):
        go_live._RUNTIME_DIR, go_live.STAGE_FILE, go_live.KILL_FILE = self._saved
        self._tmp.cleanup()

    def test_default_is_preview_when_unset(self):
        self.assertEqual(go_live.load_stage().name, "preview")

    def test_set_then_load_roundtrips(self):
        for name in ("paper", "tiny_live", "scaled", "preview"):
            go_live.set_stage(name)
            self.assertEqual(go_live.load_stage().name, name)

    def test_kill_roundtrips(self):
        self.assertFalse(go_live.kill_engaged())
        go_live.engage_kill("test")
        self.assertTrue(go_live.kill_engaged())
        go_live.clear_kill()
        self.assertFalse(go_live.kill_engaged())


if __name__ == "__main__":
    unittest.main()
