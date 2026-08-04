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

- **Momentum-class setups** (flip break, air-pocket run, hedge exhaustion,
  HOD break — `Signal.setup_class = "momentum"`) default to **convexity
  selection** (operator standing directive 2026-08-04: max gamma/delta per
  premium dollar for short explosive moves): best Δ·M + ½·Γ·M² per ask on the
  move to destination, down to **0.30Δ floor, never below** — and only when
  the A+ conviction bars hold (confidence ≥ 70, RVOL ≥ 1.8); otherwise the
  ATM band below applies.
- **Reversion-class setups** (king-node bounce, gap fill) keep **delta
  0.45–0.55** (`entry_delta_min/max`); 0.55–0.65 after a >5% gap (IV-crush
  guard).
- **Spread ≤ 10% of mid** (`max_spread_pct_of_mid`) — in every mode.
- **Expiry:** automated agent = **0DTE only** (`only_0dte_long`). Manual skill
  plans = 0–3 DTE preferred, 5 max, 0DTE only for A+ before 13:00 ET. A plan
  written for the Agentic account follows the agent rule.
- **Phase-budget contract gate** (screener stage D): a name is only a
  candidate if a contract exists with Δ ≥ 0.30 AND ask within the phase
  budget AND spread ≤ 10%. No contract, no candidate — however good the
  structure (the 2026-08-04 NVDA/AAPL lesson at Kickstart size).

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
- **Stop:** −50% premium, never widened — the absolute floor in every stage.
- **Exits (five-stage peak ladder — the DEFAULT engine, operator-approved
  2026-08-04; `RuntimeConfig.exit_mode = "ladder"`):** stages ARM when the
  position's **peak** mark touches the arm level; once armed, the exit line is
  `max(leash × peak, floor × entry)` — a ratchet that only rises. Exits
  evaluate the **polled mark** against the line (arms/peaks may ratchet on
  bar highs; downward wicks never sell — shakeout-proof by construction).

  | peak touch | exit line | locks |
  |---|---|---|
  | +25% | entry | breakeven |
  | +45% | max(0.65×peak, 1.05×entry) | ≥ +5% |
  | +70% | max(0.75×peak, 1.35×entry) | ≥ +35% |
  | +90% (target) | max(0.70×peak, 1.60×entry) | ≥ +60% |

  **Lot-aware tranches:** 3+ lots sell one at the +45% arm touch, 2+ lots sell
  one at the target touch, the last lot always trails. Legacy modes remain
  opt-in: `"target"` (+90% closes all) and `"scale_trail"` (half at +1R, 30%
  trail).
- **Continuation re-entry:** after a PROFITABLE full exit only (a stop-out
  closes the name for the session — no revenge trades): scanner must re-fire
  the setup flagged `is_reentry` (reclaim of the exit level on a 5-min close
  with RVOL ≥ 1.4, or a new session high with index alignment), ≥ 15 min
  after the exit, max 1 per name per day, at **half size**.
- **Single owner per position:** whoever opened a position (engine, watcher,
  or an external session) manages its exit ladder alone; everyone else applies
  backstops only (−50% stop, thesis break, 15:45 flatten). Two managers
  walking orders on one position is how exits collide.
- **Daily:** −2R halt · 3 straight losses = kill (both wired in-engine as of
  2026-08-04: every dispatched exit books its R and streak in-session) · press
  total hard-capped at 2× base budget and $1k · half-size after a red day ·
  flat by 15:45 ET on short-dated · never average down · cash-account entries
  only from settled cash.

**Retired** (old `gex-pullback-scalper` rules that contradicted the above —
do not resurrect from its reference files): 5% per-trade sizing, 15% open
heat, −10% premium stop, +5%/+10% scale ladder, 0.30–0.45Δ default band,
0–7 DTE window.

## Tickers (curated universe, operator-approved 2026-08-04)

- **Tier 1 (full maps, tradable in every phase — daily 0DTE, penny spreads,
  Δ≥0.30 contracts from ~$40):** SPY, QQQ, **IWM**.
- **Tier 2 (full maps, tradable at Scale phase / A+ $150 — weeklies, premiums
  need $150+):** NVDA, TSLA, META, **AAPL**, AMD (earnings-gated as usual).
- **Tier 3 (affordable movers — real liquidity at $30–90 ATM weeklies;
  scan-grade maps only, extra confirmation, B-size):** SOFI, HOOD.
- **Situational (macro-catalyst days only):** TLT (CPI/FOMC), GLD (metal
  breaks).
- **Context-only (never heatseeker blocks):** COIN, XOM, CVX, XLE and the
  vertex extras (LMT, USO). They may appear in scans and the scorecard.

**The screener (five gates, run premarket + on intraday rescreens):**
A. liquidity (0–3DTE exists · spread ≤10% at target delta · map-grade OI for
T1/T2) → B. tape (|day move| ≥0.75% or RVOL ≥1.4 · VWAP/HOD structure · index
alignment) → C. dealer map (setup fired/near · flip/wall distance · air-pocket
room ≥2× premium risk) → D. **contract gate** (Δ≥0.30 within phase budget,
spread ≤10% — hard exclude) → E. rank by R:R = (room × Δ+½Γ convexity) ÷
premium risk; top name gets the entry, conviction tier sets size.

## Skill routing

- Broad scan / watchlist briefing → `vertex-market-scan` (dashboard; its GEX
  section is context, not a plan).
- Any actionable setup/entry/stop/target on the six names → `gex-vex-heatseeker`.
- Explicit pullback-scalper request or watcher alert → `gex-pullback-scalper`
  gate, then the heatseeker engine.
- Execution against the Agentic account → only the `agent/` pipeline behind its
  go-live gate; skills never place orders.
