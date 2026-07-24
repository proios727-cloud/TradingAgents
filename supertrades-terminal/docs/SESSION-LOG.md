# SuperTrades — session log & current state (2026-07-24)

A single place to look back on everything built this session, the honest findings,
and where things stand. Newest work is at the bottom of each list.

---

## TL;DR — where we are right now

- **Nothing is trading. Nothing is armed. Nothing is managing your account.** All
  live Robinhood calls this session were **read-only**. The go-live stage is a
  gate only — the broker is inert (no dispatcher token), the risk floor blocks
  entries, and every order path still requires your explicit approval.
- **Two PRs:** #3 **merged** to `main`; #4 **open (draft)** with the newer work.
  Full suite: **102 tests passing.** Repo has no CI.
- **The big honest lesson of the session:** the in-app "Backtest" is a *seeded
  simulation* (fantasy, +18,291%). The *real* backtest on real option prices is
  **slightly negative** (9 sessions, 5 trades, 40% win, −0.72R, −$82). The GEX
  edge is **unvalidated** — an evaluation is running to decide if it's even worth
  forward-testing.

---

## The honest bottom line (the money truths)

1. **The sim is not a backtest.** `data.js:genBacktest` invents a random price
   path and draws synthetic trades against an *assumed* win rate. It proves
   nothing about edge. Tuning it (slippage, win rate) just makes a prettier fake.
2. **The one real backtest is negative.** On real Robinhood 0DTE premium across 9
   sessions: 5 trades, 40% win, **−0.72R, −$82** (1-lot). One +1.8R winner carried
   it; without that it's worse. This is the TA-only subset (VWAP+RVOL).
3. **The real edge (GEX/flow) is untested.** It can't be backtested — no free
   historical intraday option chains exist. It can only be **forward-validated**.
4. **Robinhood does NOT enforce a human approval gate.** That's enforced entirely
   on the Claude side (the PreToolUse hook + allowlist). Your "final entrance" is
   real *because we built it*, not because the broker guarantees it.
5. **Distrust any big return number** — the research found LLM-trading performance
   is systematically overstated when costs/slippage aren't modeled.

---

## What was built (by area)

### 1. The agent team — `.claude/agents/` (PR #3, merged)
Four repo-specific subagents that auto-engage on relevant work:
`risk-guardian` (opus), `quant-strategist` (opus), `python-reviewer`, `terminal-ux`.
The risk-guardian reviewed every money-adjacent change this session (all **SAFE**).

### 2. SuperTrades terminal / sim (PR #3 + #4)
- Risk-adjusted backtest metrics: **Sharpe, recovery factor, max consecutive
  losses** (new "Sharpe · 0DTE" StatCard).
- 0DTE **slippage** modeled in the sim (0.15R round-trip) — honest, though the sim
  is still a sim.

### 3. Execution agent — `supertrades-terminal/agent/` (PR #3 + #4)
All opt-in, default-off, guardian-reviewed SAFE:
- **Trailing-stop exit** (`scale_and_trail`): scale half at +1R, trail the runner
  with a 30% peak give-back. −50% stop / thesis / 15:45 flatten stay hard floors.
- **GEX/gamma convexity contract selection** (`convexity_selection`): on high
  conviction, pick the best `(|Δ|·M + ½·Γ·M²)/ask` contract, floored at 0.30 Δ.
- **Live-order human-approval gate** — `.claude/settings.json` allowlists only
  read tools; `place_option_order`/`cancel_option_order` route through the
  PreToolUse gate (`.claude/hooks/pretrade_gate.py`) which never auto-approves.
- **Staged go-live ladder** (`agent/go_live.py`): `preview → paper → tiny_live
  (1 contract, ≤$75) → scaled`. Enforced at the tool boundary. Runbook:
  `docs/GO-LIVE-STAGES.md`.
- **Real RH MCP wiring** (`robinhood_mcp.py`): validated live and **fixed real
  bugs** — balance/buying-power now from `get_portfolio`, positions enriched
  (call/put + strike + mark), gamma parsed, cancels fixed. `mcp_dispatch.py`
  (fail-closed HTTP dispatcher, inert by default, `preflight()`).

### 4. Real backtesting (PR #4)
- **`replay_backtest.py`** — fills trades on REAL historical option premium (not a
  model). `python -m agent.replay_backtest <fixture.json>`. Fixture of real SPY
  2026-07-24 data + tests.
- **`pine/supertrades.pine`** — TradingView strategy for real backtest/replay on
  real bars; date-range window + on-chart real-stats table. Trades the underlying
  (R-edge transfers, not 0DTE $).

### 5. GEX engine — the real edge input (PR #4)
- **`gex.py`** — net GEX, gamma flip, call/put walls, king node, ±gamma regime
  from a live chain (gamma + OI, free from RH). `gex_confirms()` gate keys off the
  flip + flow skew.
- **`gex_live.py`** — `python -m agent.gex_live SYMBOL SPOT chain.json` renders the
  map and appends to `.supertrades/gex_log.jsonl` (the forward-validation record).

---

## Useful commands

```bash
cd supertrades-terminal

python -m unittest discover agent/tests        # 102 tests
python -m agent.cli dry-run                     # paper decision cycle (no money)
python -m agent.go_live status                  # where on the go-live ladder
python -m agent.replay_backtest agent/tests/fixtures/spy_0dte_2026-07-24.json
python -m agent.gex_live SPY 739.6 <chain.json> # live GEX map + forward-log
python3 -m http.server 8099                     # the terminal UI (SIMULATED DATA)
```

---

## Git & PR state
- Branch: `claude/agent-team-model-enhancement-xcm1b5`
- **PR #3** — merged to `main` (agent team, metrics, trailing stop, convexity, gate).
- **PR #4** — open draft: RH wiring fix, Pine strategy, slippage, real backtest,
  GEX engine, live GEX CLI. 8 commits, 102 tests.

## Live account state (read-only, as of 2026-07-24)
- Agentic account ••••1866: cash, **agentic_allowed=true, Level 2**, **~$434 total
  / $334 buying power**, one open NVDA call (exp 07-31, unmanaged).
- ⚠️ The risk governor's **$2,000 settled-cash floor blocks all entries** on $334 —
  you'd fund more or lower the floor (a guardrail change) before live.

## Live GEX read (2026-07-24 ~14:49 ET) — context, not a signal
- **SPY** 739.6: −gamma, flip **740** (spot just below), king node 740, call wall 742.
  Gate: long → *reclaim 740 first*; short → confirmed.
- **QQQ** 684.7: strongly −gamma (−3.4B), flip/king node **685** (spot just below),
  call wall 695. Gate: long → *reclaim 685 first*; short → not confirmed (mixed flow).
- Read: both pinned at their flips in a big-move regime — **685/740 are the triggers.**

## Safety posture
- `dry_run=True`, `armed=False` defaults intact; single `risk_governor` gate;
  exits-always-live; kill switch first; `place_option_order` never allowlisted.
- Stage file may read `tiny_live` (you set it), but it's inert — no dispatcher,
  no engine loop, floor blocks entries. Reset with `python -m agent.go_live set preview`.

## Open threads / next steps
- **GEX strategy evaluation** — an adversarial 4-lens review + honest go/no-go is
  running; verdict + a rigorous forward-validation protocol pending.
- **Recurring GEX forward-log** — decision pending (scheduled vs manual). Caveat:
  scheduled/fresh sessions may lack live RH auth, so a cron job could no-op.
- **Real flow feed** — true sweep flow needs a paid tape (Unusual Whales/FlowAlgo);
  current `flow_skew` is an honest volume/OI proxy only.

## Reality-check appendix — the numbers side by side
| Source | Result | Trust it for |
|---|---|---|
| `genBacktest` (in-app sim) | +18,291% | **nothing** — seeded fiction |
| Real 0DTE backtest (9 real sessions) | **−0.72R, −$82, 40% win** | the honest TA-only edge (~coin flip, slightly negative) |
| Pine strategy (real TV bars) | run it yourself | the setup's real R-behavior on real data |
| GEX gate | **unvalidated** | nothing yet — forward-test to find out |
