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

One scan cycle, every 5 minutes from 09:30 to 16:00 ET. Read it top to bottom —
the vertical order is the order things actually happen, and it is deliberate.

```
   ┌── ① KILL CHECK ─ first, every cycle, before anything else ────────────┐
   │   STOP · MCP error · data stale >10s · 3 straight losses              │
   │        └─▶ cancel_all (best-effort) ─▶ flatten ALL ─▶ halt ─▶ return  │
   └──────────────────────────────────────────────────────────────────────┘
                                    │ not killed
                                    ▼
   ┌── ② EXITS ─ run even when halted. Getting out is never gated. ───────┐
   │   exit_manager: 15:45 flatten · −50% stop · +90% target ·            │
   │                thesis break · scale ½ at +1R · trail                 │
   │        └─▶ approval (ADVISORY — cannot veto) ─▶ place_order          │
   │            each position isolated: one failure never skips the rest  │
   └──────────────────────────────────────────────────────────────────────┘
                                    │ halted? ─── yes ──▶ return
                                    ▼ no
   ┌── ③ ENTRIES ─ every gate below can say no, and no means no ──────────┐
   │   signals ─▶ risk_governor   THE single entry gate: sizing, −2R halt,│
   │              │               earnings, RVOL, windows, settled cash   │
   │              ▼                                                        │
   │            contract_selector  0DTE only · Δ0.45–0.55 · spread ≤10%   │
   │              ▼                                                        │
   │            broker.review_order  failed review ⇒ BLOCKED (fail closed)│
   │              ▼                                                        │
   │            approval  HARD VETO · default approver DENIES             │
   │              ▼                                                        │
   │            broker.place_order                                        │
   └──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌── every broker call crosses this boundary ───────────────────────────┐
   │   mcp_dispatch  refuses non-allowlisted + mutating tools · re-checks │
   │                 can_place_live() · https-pinned · deadline + size cap│
   │                 timeout on a mutation ⇒ read-only reconcile by       │
   │                 legs[].option_id ⇒ report UNKNOWN, never "failed"    │
   │        ↑ any failure raises ─▶ trips kill_switch ─▶ halts next cycle │
   └──────────────────────────────────────────────────────────────────────┘
                                    │
                              Robinhood MCP
```

The asymmetry running through it: **entries fail closed, exits fail open.**
Anything uncertain on the way in becomes "don't trade". Anything uncertain on
the way out becomes "get out anyway". Every gate is a veto on entry; none of
them can block an exit.

`decision_log.py` records every step above as append-only JSONL — previews,
rejections, approvals, fills, and each distinct failure (`exit_failed`,
`flatten_failed`, `cancel_all_failed`, `exit_approver_error`).

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
| `cli.py` | `status` / `dry-run` / `smoke` / `arm`. |
| `smoke.py` | READ-ONLY diagnostic (`python3 -m agent.cli smoke`): builds the real dispatcher/transport and validates PARSING against the live API while still inert (`armed=False, dry_run=True`) — see "Going live" step 3. |

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
3. **Smoke-test the real API while still inert:** `python3 -m agent.cli smoke`. This builds the REAL dispatcher/transport (`RobinhoodMcpBroker.live` / `broker/mcp_dispatch.py` — the same code path live trading uses, not a fake) and issues only READ calls (`get_accounts`, `get_portfolio`, `get_option_positions`, and `get_option_chains` for every symbol in `WATCHLIST`), run through the same strict parsing the live path uses. No test in this repo has ever made a real HTTP call to Robinhood — every other test uses in-memory fakes — so this is the first point a schema mismatch (a missing/renamed field, which trips the kill switch under strict parsing) can be caught, while `armed=False, dry_run=True`. It refuses outright if that invariant doesn't hold, or if `ROBINHOOD_MCP_TOKEN` is unset (no fallback to a paper broker — that would validate nothing). It prints PASS/FAIL/latency per check and the real exception text on failure, continues after a failure, and exits non-zero if anything failed. Do not proceed past this step until every check passes.
4. Wire the dispatcher: `RobinhoodMcpBroker.live(cfg, kill_state=ks)` builds the real `mcp_call` from `broker/mcp_dispatch.py` — it refuses to construct until `ROBINHOOD_MCP_TOKEN` holds your OAuth bearer token, and refuses to dispatch any placing/cancelling tool while `dry_run=True` or `armed=False`. Pass the same `kill_state` to `SuperTradesAgent(..., kill=ks)` so any MCP failure halts the next cycle.
5. Wire the **same** dispatcher into the live earnings calendar and pass it to the engine:

   ```python
   from agent import McpEarningsCalendar, SuperTradesAgent
   agent = SuperTradesAgent(cfg, broker, signals, kill=ks,
                            earnings=McpEarningsCalendar(mcp_call))
   ```

   Without this the engine falls back to `simulated.EARNINGS_CALENDAR`, a
   hand-maintained fixture that cannot tell you it has gone stale. Do not arm
   on the fixture. `python -m agent.cli status` prints which one is in play.
6. `python3 -m unittest` green + a dry run with zero errors.
7. Only then set `armed=True, dry_run=False`. First possible entry 9:45 ET; keep `require_entry_approval=True` for week 1.

Kill anytime: say **STOP** (cancel all, flatten, halt), disconnect the connector in
Claude settings, or one-tap disconnect in the Robinhood app.

## Earnings blackout

`GUARDRAILS.earnings_block_sessions` (3) blocks entries for that many sessions on
**both** sides of the session carrying a name's earnings gap — before, because a
0DTE long would be held into the print; after, because the IV crush is just as
hostile to long premium. An `am` report gaps its own open; a `pm` report gaps the
next one (Friday `pm` → Monday).

**The live calendar updates itself while trading.** `McpEarningsCalendar`
refetches once per session date, so an armed agent picks up new and moved
report dates on its own — there is nothing to maintain on the live path.

The dry-run fixture in `simulated.py` is the part that goes stale, so it now
says so. It carries an `EARNINGS_CALENDAR_AS_OF` stamp, and past
`STATIC_FIXTURE_MAX_AGE_DAYS` (21) `StaticEarningsCalendar` stops answering and
fails closed rather than quoting a previous reporting cycle. Regenerate it from
the live feed and commit the diff:

```
python -m agent.cli refresh-earnings
```

That command is read-only against Robinhood; the only thing it writes is the
generated block in `agent/simulated.py`. It refuses to write an empty fixture —
every watchlist name being genuinely report-free is indistinguishable from a
feed that answered with nothing, and the second would silently erase the
blackout. `python -m agent.cli status` prints the fixture's age.

`McpEarningsCalendar` **fails closed**: no dispatcher, an unreachable feed, a
malformed payload, or a row whose date will not parse all block the *entire*
watchlist rather than nothing. "We could not confirm this name is clear" and
"this name has no earnings" must never produce the same answer. Expect the agent
to stop trading on a feed outage — that is the design, not a bug.

## Where this runs, and where it must not

**Build and change it anywhere** — a Claude Code session, cloud or local, is fine
for editing, reviewing, and dry runs. Nothing here can place an order.

**Run it on a machine you control, with you present.** Not in an ephemeral cloud
container, and not unattended:

- The loop needs to stay alive from 09:45 to 15:45 ET. A session container gets
  reclaimed; the 15:45 force-flatten is not something to lose to a timeout.
- The OAuth token lives in that machine's environment. It cannot be carried into
  a fresh remote session.
- Per "Credential failure disables exits" below, a token that expires mid-session
  leaves positions open and the agent blind. Someone has to be there to notice.

What to have open while it runs: the terminal running the loop, the Robinhood app
(your manual kill path and the only way to close a position the agent can't), and
the decision journal — a burst of `flatten_failed` means go close positions by
hand, now.

**One account, one owner.** `get_positions()` returns every option position in the
account, with no notion of which ones the agent opened. Point it at an account you
also trade manually and its stop, target, and 15:45 flatten will act on *your*
positions too. Give it a dedicated account.

## Changing this repo

- `config.py` holds the binding guardrail values. It is deliberately the only
  place limits live — change a limit there, never by special-casing at a call
  site. Treat a change to it as a risk decision, not a code change.
- Guardrails are enforced in exactly one place each (`risk_governor` for entries,
  `exit_manager` for exits, `kill_switch` for halts). If you find yourself adding
  a second check somewhere else, that is the bug.
- `python3 -m unittest` must be green before anything is armed. The 48 rail tests
  force every guardrail; they are the contract.
- Parsers are strict on purpose — a missing field raises and trips the kill
  switch rather than defaulting. Do not "fix" a live schema mismatch by adding a
  fallback; fix the parser against the real response and add it as a fixture.
- After any change to broker or dispatcher code, re-run `python3 -m agent.cli
  smoke` against the live API before arming again.

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

What the code does do: a timed-out **mutating** call is reconciled against a
narrowed `get_option_orders` window (`placed_agent`/`created_at_gte`) and
matched primarily on the `legs[].option_id` the API echoes back, falling back
to `placed_agent == "agentic"` + quantity + price + recency when a response
carries no legs — the real API never echoes `ref_id` back on order rows, so
that can't be the match key — and reported as **unknown state**, never as
"failed" — a timeout is not proof the order never reached the broker. Failures
never synthesize a default price, balance, or Greek. And exits are
advisory-approved, never vetoable, so nothing on the *human* side can hold a
position open; this section is about the case where the machine side cannot act
at all.

## What this is not

Not a market-data feed and not a persistent runtime. Live signal inputs (Massive/
Polygon per the handoff) and a market-hours scheduler are separate wiring; this
package is the risk-gated decision + execution core they plug into.
