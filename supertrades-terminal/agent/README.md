# SuperTrades execution agent

The decision/risk brain for the SuperTrades 0DTE options system, wired to the
**Robinhood Agentic Trading MCP**. It turns the terminal's signals into risk-gated,
previewed order intents and manages exits — with every guardrail from the design
handoff's `GO-LIVE.md` enforced in exactly one place.

> **Safety first.** This ships **inert**: `dry_run=True`, `armed=False`, no live
> order dispatcher. It cannot place a real trade until *you* fund/approve the
> account, wire a dispatcher, and arm it. Even armed, **every entry is previewed
> for your approval** before it's sent.

## Design

One independent component per job; components exchange plain dataclasses and never
read each other's internals. Guardrails live in **one** place.

```
signals ─▶ contract_selector ─▶ risk_governor ─▶ approval ─▶ broker.place_order
                                    (THE gate)   (preview-    (dry-run / arm /
 exit_manager ─────────────────────────────────  every-order) eligibility gated)
 kill_switch  ── checked first every cycle ──▶ cancel all + flatten + halt
```

| File | Responsibility |
|------|----------------|
| `config.py` | **Binding guardrail values** from `GO-LIVE.md` (sizing, exits, halts, kill, cadence). The one place to change limits. |
| `risk_governor.py` | **The single entry gate.** All entry guardrails evaluated here and nowhere else; returns allow + sizing. |
| `contract_selector.py` | Pick the 0DTE contract: today's expiry, strike nearest entry, Δ 0.45–0.55, spread ≤ 10% of mid. |
| `exit_manager.py` | Exits (stay live even when halted): −50% stop, +90% target, thesis break, scale ½ at +1R, 15:45 flatten. |
| `kill_switch.py` | STOP / MCP error / data stale >10s / 3 straight losses → cancel all, flatten, halt. |
| `broker/` | `BrokerAdapter` interface; `RobinhoodMcpBroker` (builds exact MCP calls, gated placement) and `PaperBroker` (in-memory, tests/dry-run). |
| `approval.py` | Preview-every-order gate. Default approver **denies**. |
| `engine.py` | One scan cycle: kill-check → exits → (if not halted) discover → gate → select → preview → place. |
| `decision_log.py` | Append-only JSONL audit trail (feeds the terminal P&L / journal). |
| `simulated.py` | Signal source + paper account mirroring the terminal's `data.js` for dry runs. |
| `cli.py` | `status` / `dry-run` / `arm`. |

## Guardrails (all from `GO-LIVE.md`, enforced in `risk_governor` / `exit_manager` / `kill_switch`)

- 0DTE long calls/puts only — no 0DTE chain that day ⇒ skip the name; no spreads, no shares, never a later expiry.
- Size `min(2.5% × balance, $1,000)` premium/trade; half-size the day after a red day; week-1 caps at `$500`.
- Press rule: only once ≥ +2R is **booked** may later trades size up 2×, funded from that day's profit.
- Exits: +90% target, −50% stop or thesis break, scale ½ at +1R and trail, **flatten all by 15:45 ET**.
- Daily −2R halt (entries stop, exits stay live); no entries first 15 min / last 10 min; no earnings names within 3 sessions; never widen a stop, never average down.
- Cash settlement (T+1): never buy with unsettled proceeds; open premium ≤ settled cash; balance nearing $2,000 → halt + alert.
- Contract: Δ 0.45–0.55 from broker Greeks, reject spread > 10% of mid, limit at mid (reprice once after 5s, abandon after 2 misses).

> Note: the terminal's `data.js` has an illustrative per-strategy risk map
> (`STRATEGY_RISK`, 2–7%). `GO-LIVE.md` **supersedes** it with the flat 2.5% / $1k
> rule — that's what this agent implements.

## Run

```bash
cd supertrades-terminal

# See config + live-safety state (inert by default)
python3 -m agent.cli status

# Full decision path on the simulated feed — places NOTHING (paper broker)
python3 -m agent.cli dry-run --at 2026-07-20T14:32

# Rail tests — every guardrail forced; all must pass before arming
python3 -m unittest agent.tests.test_rails -v
```

The dry run reproduces the dashboard: NVDA squeeze and TSLA gamma-flip, each
previewed as a 0DTE long entry — subject to the earnings blackout below.

## Going live (human-gated — the agent cannot do these for you)

1. In the Robinhood app: apply for **options Level 2** on the Agentic account; **fund** it (~$2,500 — funding is your hard loss cap).
2. Connect the MCP: `claude mcp add robinhood-trading --transport http https://agent.robinhood.com/mcp/trading`; complete OAuth. Reads always-allow; order placement ask-every-time.
3. Wire a real `mcp_call(tool, params)` dispatcher into `RobinhoodMcpBroker` (this repo ships without one).
4. Wire the **same** dispatcher into the live earnings calendar and pass it to the engine:

   ```python
   from agent import McpEarningsCalendar, SuperTradesAgent
   agent = SuperTradesAgent(cfg, broker, signals,
                            earnings=McpEarningsCalendar(mcp_call))
   ```

   Without this the engine falls back to `simulated.EARNINGS_CALENDAR`, a
   hand-maintained fixture that cannot tell you it has gone stale. Do not arm
   on the fixture. `python -m agent.cli status` prints which one is in play.
5. `python3 -m unittest` green + a dry run with zero errors.
6. Only then set `armed=True, dry_run=False`. First possible entry 9:45 ET; keep `require_entry_approval=True` for week 1.

Kill anytime: say **STOP** (cancel all, flatten, halt), disconnect the connector in
Claude settings, or one-tap disconnect in the Robinhood app.

## Earnings blackout

`GUARDRAILS.earnings_block_sessions` (3) blocks entries for that many sessions on
**both** sides of the session carrying a name's earnings gap — before, because a
0DTE long would be held into the print; after, because the IV crush is just as
hostile to long premium. An `am` report gaps its own open; a `pm` report gaps the
next one (Friday `pm` → Monday).

`McpEarningsCalendar` **fails closed**: no dispatcher, an unreachable feed, a
malformed payload, or a row whose date will not parse all block the *entire*
watchlist rather than nothing. "We could not confirm this name is clear" and
"this name has no earnings" must never produce the same answer. Expect the agent
to stop trading on a feed outage — that is the design, not a bug.

## What this is not

Not a market-data feed and not a persistent runtime. Live signal inputs (Massive/
Polygon per the handoff) and a market-hours scheduler are separate wiring; this
package is the risk-gated decision + execution core they plug into.
