"""Command-line entry: status / dry-run / smoke / arm / disarm / flatten.

    python -m agent.cli status
    python -m agent.cli dry-run [--at 2026-07-20T14:32]
    python -m agent.cli smoke                                # READ-ONLY, hits the real API
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
from .config import GUARDRAILS as G
from .config import MARKET_TZ, RuntimeConfig
from .earnings import McpEarningsCalendar
from .engine import SuperTradesAgent
from .simulated import SimulatedSignalSource, demo_account, demo_chains
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
    print(f"  sizing        : {G.sizing_pct:.1%} of balance, cap ${G.per_trade_cap_usd:,.0f}")
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
    live = McpEarningsCalendar()
    live.blackout(datetime.now(MARKET_TZ))
    print("Earnings feed:")
    print(f"  live calendar : {live.last_error or 'wired'}")
    print("  dry-run uses the simulated.EARNINGS_CALENDAR fixture instead")
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
    ar = sub.add_parser("arm"); ar.add_argument("--confirm", default="")
    ar.set_defaults(func=cmd_arm)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
