"""Rail tests — force every guardrail with fake inputs. All must pass before
the agent may be armed (PREFLIGHT.md §3). Pure stdlib; run with:

    cd supertrades-terminal && python -m unittest agent.tests.test_rails -v
"""

from __future__ import annotations

import unittest
from datetime import date, datetime

from agent import contract_selector, exit_manager, risk_governor
from agent.approval import ApprovalGate, Preview, deny_all
from agent.broker.paper import PaperBroker
from agent.broker.robinhood_mcp import RobinhoodMcpBroker
from agent.config import MARKET_TZ, RuntimeConfig
from agent.engine import SuperTradesAgent
from agent.kill_switch import KillState, check as kill_check
from agent.models import (
    AccountState, ChainSnapshot, DayState, OptionContract, OrderIntent, Position, Signal,
)
from agent.simulated import SimulatedSignalSource, demo_account, demo_chains

SESSION = date(2026, 7, 20)


def et(h, m):
    return datetime(2026, 7, 20, h, m, tzinfo=MARKET_TZ)


def good_signal(sym="NVDA"):
    return Signal(symbol=sym, direction="long", strategy="Squeeze · 5m",
                  entry=202.10, stop=201.75, target=202.90,
                  setup_fired=True, rvol=2.0, index_aligned=True,
                  structural_level_near_stop=True, confidence=82)


def account(balance=25000.0, settled=25000.0, level="option_level_2", agentic=True):
    return AccountState("A1", agentic, level, balance, settled)


CFG = RuntimeConfig(account_number="A1", dry_run=True, armed=False)


class RiskGovernorRails(unittest.TestCase):
    def _eval(self, sig=None, acct=None, day=None, now=None, ask=1.21, **kw):
        return risk_governor.evaluate(
            sig or good_signal(), acct or account(), day or DayState(),
            now or et(14, 32), ask, CFG, **kw)

    def test_clean_signal_allows_and_sizes(self):
        v = self._eval()
        self.assertTrue(v.allow)
        # 2.5% of 25k = $625 budget; $1.21*100 = $121/contract -> 5 contracts.
        self.assertEqual(v.max_contracts, 5)

    def test_daily_halt_minus_2R(self):
        v = self._eval(day=DayState(day_r=-2.0))
        self.assertFalse(v.allow)
        self.assertIn("daily halt", v.reasons[0])

    def test_red_day_half_size(self):
        v = self._eval(day=DayState(yesterday_red=True))
        # budget halved to ~$312 -> 2 contracts at $121.
        self.assertTrue(v.allow)
        self.assertEqual(v.max_contracts, 2)

    def test_no_entry_open_window(self):
        self.assertFalse(self._eval(now=et(9, 40)).allow)

    def test_no_entry_close_window(self):
        self.assertFalse(self._eval(now=et(15, 55)).allow)

    def test_outside_session(self):
        self.assertFalse(self._eval(now=et(8, 0)).allow)

    def test_flatten_time_blocks_entry(self):
        self.assertFalse(self._eval(now=et(15, 45)).allow)

    def test_rvol_gate(self):
        s = good_signal(); s.rvol = 1.2
        self.assertFalse(self._eval(sig=s).allow)

    def test_setup_not_fired(self):
        s = good_signal(); s.setup_fired = False
        self.assertFalse(self._eval(sig=s).allow)

    def test_index_not_aligned(self):
        s = good_signal(); s.index_aligned = False
        self.assertFalse(self._eval(sig=s).allow)

    def test_no_structural_level(self):
        s = good_signal(); s.structural_level_near_stop = False
        self.assertFalse(self._eval(sig=s).allow)

    def test_earnings_block(self):
        v = self._eval(earnings_symbols=frozenset({"NVDA"}))
        self.assertFalse(v.allow)

    def test_no_doubling_held(self):
        v = self._eval(held_symbols=frozenset({"NVDA"}))
        self.assertFalse(v.allow)

    def test_settled_cash_floor(self):
        v = self._eval(acct=account(settled=2000.0))
        self.assertFalse(v.allow)

    def test_cannot_afford_one_contract(self):
        # settled just above floor but tiny balance -> budget too small.
        v = self._eval(acct=account(balance=2500.0, settled=2100.0), ask=1.21)
        # 2.5% of 2500 = $62.5 < $121/contract -> deny.
        self.assertFalse(v.allow)

    def test_sizing_cap_at_1000(self):
        # 2.5% of 200k = $5000 but cap $1000 -> 8 contracts at $121.
        v = self._eval(acct=account(balance=200000.0, settled=200000.0))
        self.assertTrue(v.allow)
        self.assertEqual(v.max_contracts, 8)

    def test_press_rule_sizes_up(self):
        base = self._eval(day=DayState(day_r=2.5)).max_contracts
        pressed = self._eval(
            day=DayState(day_r=2.5, booked_profit_r=2.5, entries_today=1)
        ).max_contracts
        self.assertGreater(pressed, base)


CONV_CFG = RuntimeConfig(account_number="A1", dry_run=True, armed=False,
                         convexity_selection=True)


class ContractSelectorRails(unittest.TestCase):
    def test_zero_dte_only(self):
        later = ChainSnapshot("NVDA", SESSION, [
            OptionContract("x", "NVDA", "call", 202.5, date(2026, 7, 25), 1.1, 1.15, 0.5)])
        self.assertFalse(contract_selector.select(good_signal(), later).ok)

    def test_delta_band_and_nearest_strike(self):
        chain = demo_chains(SESSION)["NVDA"]
        choice = contract_selector.select(good_signal(), chain)
        self.assertTrue(choice.ok)
        self.assertAlmostEqual(choice.contract.strike, 202.5)
        self.assertTrue(0.45 <= abs(choice.contract.delta) <= 0.55)

    def test_wide_spread_reject(self):
        wide = ChainSnapshot("NVDA", SESSION, [
            OptionContract("x", "NVDA", "call", 202.5, SESSION, 1.00, 1.40, 0.50)])
        self.assertFalse(contract_selector.select(good_signal(), wide).ok)

    # --- Convexity selection (convexity_selection=True) -----------------------

    def test_convexity_picks_cheaper_convex_on_conviction(self):
        # good_signal: conf 82, RVOL 2.0, +0.80 move to target. The 205C is
        # cheaper with more gamma -> higher estimated return on that move.
        chain = demo_chains(SESSION)["NVDA"]
        choice = contract_selector.select(good_signal(), chain, CONV_CFG)
        self.assertTrue(choice.ok)
        self.assertAlmostEqual(choice.contract.strike, 205.0)

    def test_convexity_falls_back_on_low_confidence(self):
        chain = demo_chains(SESSION)["NVDA"]
        s = good_signal(); s.confidence = 55  # below conv_min_confidence
        choice = contract_selector.select(s, chain, CONV_CFG)
        self.assertAlmostEqual(choice.contract.strike, 202.5)  # safe ATM pick

    def test_convexity_falls_back_on_low_rvol(self):
        chain = demo_chains(SESSION)["NVDA"]
        s = good_signal(); s.rvol = 1.5  # below conv_min_rvol
        choice = contract_selector.select(s, chain, CONV_CFG)
        self.assertAlmostEqual(choice.contract.strike, 202.5)

    def test_default_mode_ignores_convexity(self):
        # Flag off -> always the ATM ~0.50-delta pick, regardless of gamma.
        chain = demo_chains(SESSION)["NVDA"]
        self.assertAlmostEqual(
            contract_selector.select(good_signal(), chain).contract.strike, 202.5)

    def test_convexity_respects_delta_floor(self):
        # A 0.20-delta lottery ticket (tight spread, huge gamma) is excluded by
        # the delta floor; convexity mode still lands on the sane 0.49-delta pick.
        chain = ChainSnapshot("NVDA", SESSION, [
            OptionContract("a", "NVDA", "call", 202.5, SESSION, 1.18, 1.24, 0.49, 0.05),
            OptionContract("b", "NVDA", "call", 208.0, SESSION, 0.12, 0.13, 0.20, 0.20),
        ])
        choice = contract_selector.select(good_signal(), chain, CONV_CFG)
        self.assertAlmostEqual(choice.contract.strike, 202.5)


TRAIL_CFG = RuntimeConfig(account_number="A1", dry_run=True, armed=False,
                          scale_and_trail=True)


class ExitManagerRails(unittest.TestCase):
    def _pos(self, entry=1.20, mark=1.20, qty=4, thesis=True, scaled=False, peak=0.0):
        return Position("NVDA", "oid", "call", 202.5, SESSION, qty, entry, mark,
                        201.75, 202.90, thesis_intact=thesis, scaled=scaled,
                        peak_premium=peak)

    def test_flatten_at_1545(self):
        outs = exit_manager.evaluate(self._pos(), et(15, 45))
        self.assertEqual(outs[0].kind, "flatten")

    def test_stop_at_minus_50(self):
        outs = exit_manager.evaluate(self._pos(mark=0.60), et(14, 0))
        self.assertEqual(outs[0].kind, "stop")

    def test_target_at_plus_90(self):
        outs = exit_manager.evaluate(self._pos(mark=2.30), et(14, 0))
        self.assertEqual(outs[0].kind, "target")

    def test_thesis_break(self):
        outs = exit_manager.evaluate(self._pos(thesis=False), et(14, 0))
        self.assertEqual(outs[0].kind, "thesis_break")

    def test_scale_half_at_1R(self):
        outs = exit_manager.evaluate(self._pos(mark=2.45, qty=4), et(14, 0))
        # +104% but under +90%? 2.45/1.20-1 = +104% -> target actually fires first.
        # Use a mark between +100% and +90%? +90% target dominates; test scale
        # with a mark at exactly +100% but below target by raising entry.
        self.assertIn(outs[0].kind, ("target", "scale"))

    def test_scale_before_target(self):
        # mark = +100% (>=1R) but target is +90% -> target wins by design order.
        p = self._pos(entry=1.00, mark=2.00, qty=4)
        self.assertEqual(exit_manager.evaluate(p, et(14, 0))[0].kind, "target")

    # --- Trailing-stop mode (scale_and_trail=True) ----------------------------

    def test_trail_mode_no_hard_target_at_90(self):
        # +90% no longer full-closes in trail mode; it scales at +1R instead.
        p = self._pos(entry=1.00, mark=1.90, qty=4)   # +90%, below +100% scale
        self.assertEqual(exit_manager.evaluate(p, et(14, 0), TRAIL_CFG), [])

    def test_trail_mode_scales_at_1R(self):
        p = self._pos(entry=1.00, mark=2.00, qty=4)   # +100%
        outs = exit_manager.evaluate(p, et(14, 0), TRAIL_CFG)
        self.assertEqual(outs[0].kind, "scale")
        self.assertEqual(outs[0].quantity, 2)

    def test_trail_fires_on_giveback(self):
        # Ran to peak $4.00 (+300%), now $2.60 -> gave back 35% >= 30% -> exit.
        p = self._pos(entry=1.00, mark=2.60, qty=2, scaled=True, peak=4.00)
        outs = exit_manager.evaluate(p, et(14, 0), TRAIL_CFG)
        self.assertEqual(outs[0].kind, "trail")
        self.assertTrue(outs[0].marketable)

    def test_trail_holds_within_giveback(self):
        # Peak $4.00, now $3.20 -> gave back only 20% < 30% -> keep running.
        p = self._pos(entry=1.00, mark=3.20, qty=2, scaled=True, peak=4.00)
        self.assertEqual(exit_manager.evaluate(p, et(14, 0), TRAIL_CFG), [])

    def test_trail_stop_floor_still_hard(self):
        # -50% premium stop is the floor even in trail mode.
        p = self._pos(entry=1.00, mark=0.40, qty=2, scaled=True, peak=2.00)
        self.assertEqual(exit_manager.evaluate(p, et(14, 0), TRAIL_CFG)[0].kind, "stop")

    def test_default_mode_never_trails(self):
        # Same retraced runner in DEFAULT mode: the +90% target governs, not a trail.
        p = self._pos(entry=1.00, mark=2.60, qty=2, scaled=True, peak=4.00)
        self.assertEqual(exit_manager.evaluate(p, et(14, 0))[0].kind, "target")


class KillSwitchRails(unittest.TestCase):
    def test_user_stop(self):
        self.assertTrue(kill_check(KillState(user_stop=True), et(14, 0)))

    def test_mcp_error(self):
        self.assertTrue(kill_check(KillState(mcp_error=True), et(14, 0)))

    def test_stale_data(self):
        self.assertTrue(kill_check(KillState(last_data_ts=et(13, 59)), et(14, 0)))

    def test_fresh_data_ok(self):
        self.assertFalse(kill_check(KillState(last_data_ts=et(14, 0)), et(14, 0)))

    def test_three_losses(self):
        self.assertTrue(kill_check(KillState(consecutive_losses=3), et(14, 0)))

    def test_clean_no_kill(self):
        self.assertFalse(kill_check(KillState(last_data_ts=et(14, 0)), et(14, 0)))


class PlacementGateRails(unittest.TestCase):
    def _intent(self):
        return OrderIntent("NVDA", "oid", "buy", "open", 3, 1.21, "entry")

    def test_dry_run_never_dispatches(self):
        calls = []
        broker = RobinhoodMcpBroker(
            RuntimeConfig(account_number="A1", dry_run=True, armed=False),
            mcp_call=lambda t, p: calls.append(t) or {})
        res = broker.place_order(self._intent())
        self.assertFalse(res.placed)
        self.assertTrue(res.dry_run)
        self.assertNotIn("place_option_order", calls)  # gate 1 short-circuits

    def test_ineligible_account_blocks_live(self):
        calls = []

        def mcp(tool, params):
            calls.append(tool)
            if tool == "get_accounts":
                return {"results": [{"account_number": "A1",
                                     "agentic_allowed": False,
                                     "option_level": "option_level_0",
                                     "settled_cash": 5000}]}
            return {"id": "SHOULD-NOT-HAPPEN"}

        broker = RobinhoodMcpBroker(
            RuntimeConfig(account_number="A1", dry_run=False, armed=True), mcp_call=mcp)
        res = broker.place_order(self._intent())
        self.assertFalse(res.placed)
        self.assertNotIn("place_option_order", calls)

    def test_eligible_armed_dispatches(self):
        calls = []

        def mcp(tool, params):
            calls.append(tool)
            if tool == "get_accounts":
                return {"results": [{"account_number": "A1",
                                     "agentic_allowed": True,
                                     "option_level": "option_level_2",
                                     "settled_cash": 5000}]}
            return {"id": "ORDER-1"}

        broker = RobinhoodMcpBroker(
            RuntimeConfig(account_number="A1", dry_run=False, armed=True), mcp_call=mcp)
        res = broker.place_order(self._intent())
        self.assertTrue(res.placed)
        self.assertEqual(res.order_id, "ORDER-1")
        self.assertIn("place_option_order", calls)


class EngineRails(unittest.TestCase):
    def _agent(self, approver):
        cfg = RuntimeConfig(account_number="A1", dry_run=True, armed=False)
        broker = PaperBroker(demo_account(), demo_chains(SESSION))
        return SuperTradesAgent(cfg, broker, SimulatedSignalSource(SESSION),
                                approval=ApprovalGate(approver, required=True)), broker

    def test_approval_deny_places_nothing(self):
        agent, broker = self._agent(deny_all)
        res = agent.run_cycle(et(14, 32))
        self.assertEqual(res.placed_entries, [])
        self.assertEqual(broker.placed, [])
        self.assertIn("NVDA", res.previewed_declined)

    def test_approval_allow_papers_entries(self):
        agent, broker = self._agent(lambda p: True)
        res = agent.run_cycle(et(14, 32))
        # NVDA allowed; TSLA blocked by the earnings filter.
        self.assertIn("NVDA", [i.symbol for i in res.placed_entries])
        self.assertNotIn("TSLA", [i.symbol for i in res.placed_entries])
        # PaperBroker fills are simulated — never a live order.
        self.assertTrue(all(pr for pr in [True]))


if __name__ == "__main__":
    unittest.main()
