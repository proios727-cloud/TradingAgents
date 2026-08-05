"""Command-line entry: status / dry-run / smoke / arm / disarm / flatten.

    python -m agent.cli status
    python -m agent.cli dry-run [--at 2026-07-20T14:32]
    python -m agent.cli smoke                                # READ-ONLY, hits the real API
    python -m agent.cli refresh-earnings                     # regenerate the dry-run fixture
    python -m agent.cli arm --confirm "I ARM SUPERTRADES"   # refuses unless eligible

Arming only flips the switches; a live order still requires a wired mcp_call
dispatcher (not shipped here) and an eligible, funded Agentic account.
"""

from __future__ import annotations

import argparse
from datetime import datetime

from .approval import ApprovalGate, Preview, deny_all
from .broker.mcp_dispatch import McpDispatchError, TOKEN_ENV
from .broker.paper import PaperBroker
from .broker.robinhood_mcp import RobinhoodMcpBroker
from .config import GUARDRAILS as G
from .config import MARKET_TZ, RuntimeConfig
from .earnings import McpEarningsCalendar, StaticEarningsCalendar
from .engine import SuperTradesAgent
from .fixture_refresh import FixtureRefreshError, refresh as refresh_fixture
from .simulated import (
    EARNINGS_CALENDAR,
    EARNINGS_CALENDAR_AS_OF,
    SimulatedSignalSource,
    demo_account,
    demo_chains,
)
from .smoke import SmokeRefused, format_report, run_smoke


def _parse_at(s: str | None) -> datetime:
    if not s:
        return datetime.now(MARKET_TZ)
    dt = datetime.fromisoformat(s)
    return dt.replace(tzinfo=MARKET_TZ) if dt.tzinfo is None else dt


def cmd_status(_args) -> int:
    cfg = RuntimeConfig()
    print("SuperTrades execution agent — status")
    print(f"  armed        : {cfg.armed}")
    print(f"  dry_run      : {cfg.dry_run}")
    print(f"  can_place_live: {cfg.can_place_live()}  (False = fully inert)")
    print(f"  entry approval required: {cfg.require_entry_approval}")
    print("Guardrails (from GO-LIVE.md):")
    ladder = " / ".join(f"<${b:,.0f}: ${f:,.0f}" for b, f in G.sizing_phases)
    print(f"  sizing        : phases {ladder} / then {G.sizing_pct:.1%}, "
          f"cap ${G.per_trade_cap_usd:,.0f}")
    print(f"  exits         : +{G.target_premium_gain:.0%} target / "
          f"-{G.stop_premium_loss:.0%} stop / flatten {G.force_flatten_et} ET")
    print(f"  daily halt    : {G.daily_halt_r} R")
    print(f"  kill          : {G.consecutive_loss_kill} losses / "
          f"stale >{G.stale_data_seconds:.0f}s / STOP / MCP error")
    print(f"  contract      : Δ {G.entry_delta_min}–{G.entry_delta_max}, "
          f"spread <= {G.max_spread_pct_of_mid:.0%} of mid, 0DTE long only")
    print(f"  earnings      : blackout ±{G.earnings_block_sessions} sessions "
          f"around the gap")
    print(f"  watchlist     : {', '.join(__import__('agent').WATCHLIST)}")

    # The live calendar is inert without a dispatcher, and inert means "blocks
    # everything" — say so plainly rather than letting it look configured.
    now = datetime.now(MARKET_TZ)
    live = McpEarningsCalendar()
    live.blackout(now)
    fixture = StaticEarningsCalendar(EARNINGS_CALENDAR,
                                     as_of=EARNINGS_CALENDAR_AS_OF)
    fixture.blackout(now)
    age = fixture.age_days(now.astimezone(MARKET_TZ).date())
    print("Earnings feed:")
    print(f"  live calendar : {live.last_error or 'wired'}")
    print(f"  dry-run fixture: generated {EARNINGS_CALENDAR_AS_OF} ({age}d ago)"
          f" — {fixture.last_error or 'current'}")
    return 0


def cmd_dry_run(args) -> int:
    now = _parse_at(args.at)
    session = now.astimezone(MARKET_TZ).date()
    cfg = RuntimeConfig(account_number="AGENTIC-DEMO", dry_run=True, armed=False)
    broker = PaperBroker(demo_account(), demo_chains(session))
    signals = SimulatedSignalSource(session)

    # Auto-approve previews in dry run so the full path exercises (nothing is
    # ever sent — the broker is a paper broker and dry_run gates placement).
    def approve(p: Preview) -> bool:
        print(p.render()); print("  -> [dry-run auto-approve]\n"); return True

    agent = SuperTradesAgent(cfg, broker, signals,
                             approval=ApprovalGate(approve, required=True))
    res = agent.run_cycle(now)
    print(f"Cycle @ {res.ts}")
    print(f"  killed          : {res.killed or '—'}")
    print(f"  entries (paper) : {[i.symbol for i in res.placed_entries]}")
    print(f"  exits           : {[(e.position.symbol, e.kind) for e in res.exits]}")
    print(f"  rejected        : {res.rejected}")
    print(f"  human-declined  : {res.previewed_declined}")
    print("\nNo live orders were placed (paper broker, dry_run=True).")
    return 0


def cmd_smoke(_args) -> int:
    # Deliberately the fully-inert default RuntimeConfig(): armed=False,
    # dry_run=True. run_smoke() re-asserts this itself and refuses otherwise
    # — this is belt-and-braces, not the only gate.
    cfg = RuntimeConfig()
    print("SuperTrades smoke test — READ-ONLY calls against the real "
          "Robinhood MCP API.")
    print(f"  armed={cfg.armed}  dry_run={cfg.dry_run}\n")
    try:
        results, code = run_smoke(cfg)
    except SmokeRefused as e:
        print(f"Refusing to run: {e}")
        return 2
    except McpDispatchError as e:
        print("Refusing to run: could not construct the live dispatcher.")
        print(f"  {e}")
        print(f"Set {TOKEN_ENV} (complete the Robinhood MCP OAuth flow) and "
              "retry. This command never falls back to a paper/fake broker —"
              " that would validate nothing.")
        return 2
    print(format_report(results))
    return code


def cmd_refresh_earnings(_args) -> int:
    # Inert config: this reads the calendar and writes a source file. It never
    # touches an order path, and the dispatcher refuses mutations anyway.
    cfg = RuntimeConfig()
    print("Refreshing the dry-run earnings fixture from the live feed "
          "(read-only against Robinhood).")
    try:
        broker = RobinhoodMcpBroker.live(cfg)
    except McpDispatchError as e:
        print(f"Refusing to run: could not construct the live dispatcher.\n  {e}")
        print(f"Set {TOKEN_ENV} (complete the Robinhood MCP OAuth flow) and retry.")
        return 2

    today = datetime.now(MARKET_TZ).date()
    try:
        reports = refresh_fixture(broker._mcp, today)
    except FixtureRefreshError as e:
        print(f"Refused: {e}")
        return 2
    except Exception as e:  # noqa: BLE001 — surface the real text, write nothing
        print(f"Failed: {e!r}\nThe existing fixture is unchanged.")
        return 1

    print(f"\nWrote {len(reports)} report(s), as_of {today}:")
    for r in reports:
        print(f"  {r.symbol:<6} {r.report_date} {r.timing or '(timing unknown)'}")
    print("\nReview the diff in agent/simulated.py and commit it.")
    return 0


def cmd_arm(args) -> int:
    if args.confirm != "I ARM SUPERTRADES":
        print("Refusing: pass --confirm \"I ARM SUPERTRADES\" to arm.")
        return 2
    # A real arm would: verify get_account() agentic_allowed + option_level_2 +
    # funding, verify a live mcp_call is wired, run the rail suite green, then
    # set armed=True, dry_run=False. None of those preconditions are met here.
    print("Refusing to arm: preconditions unmet in this environment —")
    print("  - live dispatcher (broker/mcp_dispatch.py) has no OAuth token wired"
          " (ROBINHOOD_MCP_TOKEN unset -> transport refuses to construct)")
    print("  - Agentic account options Level 2 + funding must be verified live")
    print("  - rail suite must pass green (python -m unittest)")
    print("See agent/README.md → 'Going live'.")
    return 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(func=cmd_status)
    dr = sub.add_parser("dry-run"); dr.add_argument("--at", default=None)
    dr.set_defaults(func=cmd_dry_run)
    sub.add_parser("smoke").set_defaults(func=cmd_smoke)
    sub.add_parser("refresh-earnings").set_defaults(func=cmd_refresh_earnings)
    ar = sub.add_parser("arm"); ar.add_argument("--confirm", default="")
    ar.set_defaults(func=cmd_arm)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
