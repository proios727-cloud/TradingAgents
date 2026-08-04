# SIGNALS.md — the one signal standard

One vocabulary and one set of binding numbers, shared by the Claude skills
(`gex-vex-heatseeker`, its `gex-pullback-scalper` preset, `vertex-market-scan`)
and the SuperTrades execution agent in `agent/`. Where any skill text, reference
file, or old note disagrees with this page or with `agent/config.py`
**Guardrails, the Guardrails win.** This page changes only with operator
approval, same as the config it mirrors.

## The six setups (the only signal taxonomy)

All actionable signals are one of heatseeker's six dealer-positioning setups.
The old pullback-scalper "plays" are aliases, not separate signals:

| Setup | Regime | Old alias |
|---|---|---|
| Flip break | → −GEX | vacuum continuation (short) |
| Flip reclaim | → +GEX | flip reclaim (reversal long) |
| Gap fill | +GEX | — |
| King-node rejection | +GEX | put-wall bounce (dip buy, at the put wall) |
| Air-pocket run | −GEX | vacuum continuation (fast leg) |
| Hedge exhaustion | deep −GEX | — |

**Pullback-day overlay** (the scalper preset's gate): a "big pullback day"
needs ≥ 2 of — index down ≥ 0.75%, spot below flip, VIX +5%, put wall tagged /
air pocket entered. The overlay filters *which day* to hunt; it adds no setups.

## Entry gates ↔ Guardrails

A setup firing is necessary, not sufficient. Gates map 1:1 to the agent's
entry-confirmation fields:

| Gate | Binding number | Guardrails field |
|---|---|---|
| Volume | RVOL ≥ 1.4 | `rvol_min` |
| Index alignment | SPY/QQQ agree with direction | `index_aligned` |
| Structure | setup triggered, invalidation is a price | `setup_fired`, `structural_level_near_stop` |
| Map confidence | flow-drift < 0.15% or vendor levels | (skill-side gate) |
| Entry windows | none 09:30–09:45 or 15:50–16:00 ET | `no_entry_open/close_minutes` |
| Earnings | no entries within 3 sessions | `earnings_block_sessions` |

## Contract standard

- **Delta 0.45–0.55** (`entry_delta_min/max`); 0.55–0.65 after a >5% gap
  (IV-crush guard); **convexity mode** may go down to 0.30Δ only on A+
  conviction with RVOL ≥ 1.8 (`conv_*` fields) — never lottery pricing below it.
- **Spread ≤ 10% of mid** (`max_spread_pct_of_mid`).
- **Expiry:** automated agent = **0DTE only** (`only_0dte_long`). Manual skill
  plans = 0–3 DTE preferred, 5 max, 0DTE only for A+ before 13:00 ET. A plan
  written for the Agentic account follows the agent rule.

## Risk numbers (binding, from Guardrails)

- **Size (phase ladder, operator-amended 2026-08-04; raised same day to "up
  to $150 allowed"):** fixed **$100**/trade below a $4,000 balance
  (Kickstart), then **2.5% of balance** (Scale — 2.5% × $4k = $100, seamless
  handoff), $1,000 hard cap in every phase. Red-day and week-1 half-size
  multipliers apply to the phase budget. Fixed budgets are additionally clamped to 20% of balance. **Conviction multiplier:** A+ signals
  (confidence >= 70 and RVOL >= 1.8) size 1.5x the phase budget (= $150 at the $100 Kickstart base); scored-but-low-confidence (B)
  size 0.5x; unscored is neutral. One authority: `Guardrails.premium_budget(balance)` x
  `Guardrails.conviction_multiplier(...)`. The settled-cash floor was operator-lowered
  $2,000 → **$300** on 2026-08-04 (its own explicit decision): automated entries halt
  at/below $300 settled — below that the kickstart stake is ~45% drawn down and the
  system alerts instead of digging.
- **Stop:** −50% premium, never widened. **Target:** +90%, or scale half at
  +1R and trail the runner with 30% peak give-back when `scale_and_trail` is on.
- **Daily:** −2R halt · 3 straight losses = kill (both wired in-engine as of
  2026-08-04: every dispatched exit books its R and streak in-session) · press
  total hard-capped at 2× base budget and $1k · half-size after a red day ·
  flat by 15:45 ET on short-dated · never average down · cash-account entries
  only from settled cash.

**Retired** (old `gex-pullback-scalper` rules that contradicted the above —
do not resurrect from its reference files): 5% per-trade sizing, 15% open
heat, −10% premium stop, +5%/+10% scale ladder, 0.30–0.45Δ default band,
0–7 DTE window.

## Tickers

- **Tier 1 (full setups):** SPY, QQQ.
- **Tier 2 (extra confirmation, smaller size):** NVDA, TSLA, AMD, META.
- **Scan-only (no dealer-map signals — chains too thin/news-driven):** COIN,
  XOM, CVX, XLE and the vertex extras (LMT, USO, IWM). They may appear in
  scans and the scorecard, never in a heatseeker block.

## Skill routing

- Broad scan / watchlist briefing → `vertex-market-scan` (dashboard; its GEX
  section is context, not a plan).
- Any actionable setup/entry/stop/target on the six names → `gex-vex-heatseeker`.
- Explicit pullback-scalper request or watcher alert → `gex-pullback-scalper`
  gate, then the heatseeker engine.
- Execution against the Agentic account → only the `agent/` pipeline behind its
  go-live gate; skills never place orders.
