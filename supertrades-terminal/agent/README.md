# SuperTrades execution agent

The decision/risk brain for the SuperTrades 0DTE options system, wired to the
**Robinhood Agentic Trading MCP**. It turns the terminal's signals into risk-gated,
previewed order intents and manages exits — with every guardrail from the design
handoff's `GO-LIVE.md` enforced in exactly one place.

> **Safety first.** This ships **inert**: `dry_run=True`, `armed=False`, and the
> live dispatcher (`broker/mcp_dispatch.py`) refuses to construct without your
> OAuth token — and refuses to dispatch anything mutating while dry-run/disarmed.
> It cannot place a real trade until *you* fund/approve the account, connect the
> MCP, and arm it. Even armed, **every entry is previewed for your approval**
> before it's sent.

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
| `broker/` | `BrokerAdapter` interface; `RobinhoodMcpBroker` (builds exact MCP calls, gated placement); `mcp_dispatch.py` (the real `mcp_call` dispatcher onto the `mcp__Robinhood_Trading__*` tools — fail-closed, kill-switch-tripping, inert without an OAuth token); `PaperBroker` (in-memory, tests/dry-run). |
| `approval.py` | Preview-every-order gate. Default approver **denies**. Approval is **asymmetric**: a decline is a hard veto for entries only. With `require_exit_approval=True`, exit tickets are still previewed and the operator's answer journaled (`exit_approval_advisory`), but it is **advisory only** — protective exits (stop, thesis break, 15:45 flatten) always place, regardless of a decline, an approver error, or no approver being wired. |
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

The dry run reproduces the dashboard: NVDA squeeze → a previewed 202.5-call entry;
TSLA gamma-flip → **rejected by the earnings filter** (hyperscaler week).

## Going live (human-gated — the agent cannot do these for you)

1. In the Robinhood app: apply for **options Level 2** on the Agentic account; **fund** it (~$2,500 — funding is your hard loss cap).
2. Connect the MCP: `claude mcp add robinhood-trading --transport http https://agent.robinhood.com/mcp/trading`; complete OAuth. Reads always-allow; order placement ask-every-time.
3. Wire the dispatcher: `RobinhoodMcpBroker.live(cfg, kill_state=ks)` builds the real `mcp_call` from `broker/mcp_dispatch.py` — it refuses to construct until `ROBINHOOD_MCP_TOKEN` holds your OAuth bearer token, and refuses to dispatch any placing/cancelling tool while `dry_run=True` or `armed=False`. Pass the same `kill_state` to `SuperTradesAgent(..., kill=ks)` so any MCP failure halts the next cycle.
4. `python3 -m unittest` green + a dry run with zero errors.
5. Only then set `armed=True, dry_run=False`. First possible entry 9:45 ET; keep `require_entry_approval=True` for week 1.

Kill anytime: say **STOP** (cancel all, flatten, halt), disconnect the connector in
Claude settings, or one-tap disconnect in the Robinhood app.

## Credential failure disables exits, not just entries

**Read this before running with an open position.**

Every broker call goes over one authenticated HTTPS connection. The transport
collapses all HTTP failures into a single `McpDispatchError`, which trips the
kill switch: cancel all working orders, flatten every position, halt for the
day. That is the right response to a *transient* error. It is **not** sufficient
for a *credential* error — and the two are indistinguishable at the transport,
because `urllib` raises `HTTPError` for both a 401 and a 500 and the body is
never read.

If the OAuth token expires or is revoked mid-session with positions open:

1. The next broker call fails → kill switch trips.
2. The kill path runs `cancel_all()` then `_flatten_all()`.
3. **Both are also broker calls, so they fail too** — same cause.
4. Each position is journaled as `flatten_failed` and left **open**.
5. The agent is halted, holding, and blind.

Per-position isolation means you get one `flatten_failed` record per position
instead of a silent abort on the first — you can see exactly what is still open.
It does not, and cannot, close them. **No code change fixes this.** An agent
that reaches its broker over an authenticated socket cannot close a position
when its credentials stop working.

Operationally:

- **Do not run unattended.** The 15:45 ET force-flatten is only as reliable as
  the connection it runs over.
- **A `flatten_failed` burst is a page, not a log line.** Open the Robinhood app
  and close the positions by hand, now. If the cause is credential expiry, every
  later cycle fails identically — waiting accomplishes nothing.
- **Re-auth before the session, not during it.** Complete the OAuth flow fresh
  each trading day. A token minted days earlier that expires at 14:00 with an
  open book is the scenario this section exists for.
- **Know your manual kill paths.** Disconnecting the connector, the one-tap
  disconnect in the app, and closing positions directly in the app all work
  regardless of what the agent can reach.

What the code does do: a timed-out **mutating** call is reconciled against
`get_option_orders` by `ref_id` and reported as **unknown state**, never as
"failed" — a timeout is not proof the order never reached the broker. Failures
never synthesize a default price, balance, or Greek. And exits are
advisory-approved, never vetoable, so nothing on the *human* side can hold a
position open; this section is about the case where the machine side cannot act
at all.

## What this is not

Not a market-data feed and not a persistent runtime. Live signal inputs (Massive/
Polygon per the handoff) and a market-hours scheduler are separate wiring; this
package is the risk-gated decision + execution core they plug into.
