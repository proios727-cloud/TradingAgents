---
name: gex-vex-heatseeker
description: THE signal engine — the single GEX/VEX dealer-positioning system for actionable options trades on SPY, QQQ, NVDA, TSLA, AMD and META. Builds a gamma/vanna map from the live Robinhood option chain (or pasted Skylit/TradingView levels), classifies the dealer regime, and hunts six setups — gamma-flip break, flip reclaim, gap fill, king-node rejection, air-pocket run, and hedge-exhaustion reversal. Use this skill whenever the user mentions GEX, VEX, vanna, charm, gamma flip, zero gamma, king node, call wall, put wall, air pocket, dealer positioning, Skylit, Heatseeker, SpotGamma, gap fill, pin risk, or OPEX pinning — and whenever they ask for a setup, entry, stop, target, or "best trade" on any of the six covered tickers, even without the word gamma. Routing: a broad market scan or watchlist briefing goes to vertex-market-scan; an explicit pullback-scalper request goes to gex-pullback-scalper (a preset of this engine); everything actionable on the six names lands here. Outside the six, say the chain is too thin rather than improvising a map.
compatibility: Requires the Robinhood Trading MCP for live chains and quotes (read-only tools only). Optionally consumes pasted Skylit/Heatseeker or TradingView Supercharts levels. Bundles scripts/gex_map.py (pure Python 3, no dependencies). Emits signals and a ledger — never places or cancels orders.
---

# GEX/VEX Heatseeker

A dealer-positioning engine. It reads where market makers are pinned, where they
are forced to chase, and where there is nothing underneath the price — then hunts
a small number of high-conviction setups built on that structure.

This is decision support. It produces signals, contracts, and levels. **It never
places, previews, cancels, or exercises orders** — the user executes manually.
That boundary is not a limitation to work around; it is the design.

## Scope: six tickers, two tiers

GEX/VEX only means something where the option chain is deep enough that dealer
hedging genuinely moves the tape. On thin chains the math still produces
confident-looking numbers, and those numbers are noise wearing a suit.

- **Tier 1 — SPY, QQQ.** Deepest chains, densest strikes, most reliable levels.
  Full setup list available. This is where the model is strongest.
- **Tier 2 — NVDA, TSLA, AMD, META.** Deep enough to be tradeable, but levels are
  coarser and single-stock news overrides dealer flow more often. Require one
  extra confirmation (see gates) and size smaller.
- **Anything else — out of scope.** If asked about another ticker, say plainly
  that the chain is too thin for a trustworthy map and offer the underlying-only
  read instead. Fabricating levels on XLE or COIN is the fastest way to lose
  money with this skill.

## Step 1 — Build the map

Three sources, in order of preference. Use the best available; say which you used.

**(a) Pasted Skylit / Heatseeker or TradingView levels.** If the user gives you
flip, king node, walls, or a screenshot, use those numbers directly — a vendor
with full-chain intraday data beats a reconstruction. Record the source and time.

**(b) Reconstruct from the live Robinhood chain.** The default when nothing is
pasted. Procedure:

1. `get_equity_quotes` → spot.
2. `get_option_chains` → chain id and available expirations.
3. `get_option_instruments` for the target expirations (0–7 DTE; include the
   nearest weekly and the next one), filtered to strikes within **±3% of spot**
   — that band holds essentially all the gamma that matters intraday.
4. `get_option_quotes` on those instrument ids, **20 at a time**. This returns
   `open_interest`, `gamma`, `vega`, `delta`, `implied_volatility` and same-day
   `volume` — everything the map needs.
5. Write the results to a JSON file in the shape documented at the top of
   `scripts/gex_map.py`, then run it:

```bash
python3 scripts/gex_map.py chain.json --compare-flow
```

`--compare-flow` is the one to reach for by default. Open interest publishes
T+1, so intraday it describes *yesterday's* board. Same-day volume is live but
direction-blind. The flag builds the map both ways and reports how far the flip
level drifts. Small drift means today's flow is not reshaping the board and the
stale map is trustworthy; large drift means the board is being actively rebuilt
and every level on it deserves less weight. **The disagreement is the signal** —
report it, don't hide it.

**(c) Hybrid.** Pasted levels for the flip and walls, reconstructed map for
nodes, pockets and vanna. Common and fine. Just label which came from where.

Read `references/proxy-math.md` before interpreting the numbers — it covers the
dealer sign convention, what the units mean, and where the model is known to be
wrong. That last part matters more than the formulas.

## Step 2 — Classify the regime

Two axes. Together they tell you which *kind* of trade the day supports, and
getting this wrong is more costly than getting a level slightly wrong.

**Gamma sign — how dealers respond to movement:**

- **Positive GEX (spot above flip):** dealers sell rallies and buy dips to stay
  hedged. Moves get damped. Price gravitates to big nodes. Favors fades, pins,
  gap fills, and mean reversion. Breakouts mostly fail.
- **Negative GEX (spot below flip):** dealers sell into weakness and buy into
  strength. Moves get amplified. Favors continuation, squeezes, and air-pocket
  runs. Fades get run over.

**Vanna alignment — whether a vol change reinforces or fights the gamma read:**

- **Aligned** (net GEX and net VEX same sign): gamma and vanna push the same
  way. Cleanest trends and hardest pins live here. Highest conviction.
- **Divergent**: dealer flows work against each other. This is what chop and
  whipsaw actually are underneath. Demand more confirmation, size smaller, and
  be quicker to take profit.

## Step 3 — The six setups

Full mechanics, triggers and invalidations are in `references/setups.md` — read
it before writing a plan. Summary:

| Setup | Regime | Core idea |
|---|---|---|
| **Flip break** | crossing into −GEX | Price loses the flip from above; dealer hedging turns amplifying. Continuation short. |
| **Flip reclaim** | crossing into +GEX | Price reclaims the flip from below and holds; amplification turns to damping. Continuation long. |
| **Gap fill** | +GEX | Overnight gap with dealers pinning; price drawn back toward prior close / king node. |
| **King-node rejection** | +GEX | Price tags the dominant node and stalls; fade back toward the middle of the board. |
| **Air-pocket run** | −GEX | Price enters a gap with no dealer support until the next node. Fastest moves on the board. |
| **Hedge exhaustion** | deep −GEX | Move overextends past the last node with vanna diverging; dealers finish hedging and the push dies. Reversal. |

The two the user asked for by name — **flip** and **gap fill** — are opposite-regime
trades. Flip plays trade the *transition*; gap fills trade the *pin*. Running a
gap fill in negative gamma is the single most common way this model loses: the
gap doesn't fill, it extends.

## Step 4 — Entry gates

A setup firing is necessary, not sufficient. All of these must hold:

- **Structure:** one of the six setups is genuinely triggered, with the level
  named and the invalidation a specific price, not a feeling.
- **Volume:** RVOL ≥ 1.4 versus the elapsed-session fraction of the 2-week
  average. Level breaks on flat volume are traps — this gate is what kept the
  system flat through a full day of drifting lows on 2026-07-24, correctly.
- **Alignment:** for a directional trade, SPY or QQQ agrees with the direction.
  A long NVDA setup against a red tape is a tier-2 trade with a tier-1 excuse.
- **Map confidence:** flow cross-check drift < 0.15%, or pasted vendor levels.
  Contested board → no new risk.
- **Tier 2 extra:** NVDA/TSLA/AMD/META additionally require either an aligned
  vanna read or a pasted vendor level. Two out of three is not enough on a
  single name.
- **Calendar:** no entries with earnings within 3 sessions; none in the first
  15 or last 10 minutes of the session.

If a gate fails, the output is **NO TRADE** with the failed gate named. A no-trade
call is a successful run — the gates exist because most hours of most days do not
contain an edge, and a system that always finds one is broken.

## Step 5 — Contract selection

Aiming for gamma per unit of theta, because these are structural moves expected
to resolve in minutes to hours, not days.

- **Expiry:** 0–3 DTE preferred, 5 max. 0DTE only for A+ setups before 13:00 ET.
  (The automated SuperTrades agent is stricter — 0DTE-only per its GO-LIVE
  guardrails; plans written for the Agentic account must respect that.)
- **Delta:** 0.45–0.55 (the account standard). Shift to 0.55–0.65 if the
  underlying gapped more than 5% (IV-crush guard). Cheaper convex contracts down
  to 0.30Δ are allowed only in convexity mode: A+ conviction with RVOL ≥ 1.8 —
  never on lottery pricing below that floor.
- **Spread:** ≤ 10% of mid. Walk to a nearer strike rather than pay a wide book.
- Use `get_option_chains` → `get_option_instruments` → `get_option_quotes` for
  live greeks. Check affordability against real buying power via `get_portfolio`
  before naming a contract; if nothing fits, say "signal fired, no affordable
  contract" rather than naming one the account cannot take.

## Step 6 — Payoff policy: where the gains actually come from

The instinct behind "max gains" is usually *more trades*. That is backwards. On a
structural model like this one, expectancy is dominated by two things: refusing
the mediocre setups, and letting the regime dictate the exit. Read
`references/exit-policy.md` for the full logic. The core of it:

**Match the exit to the regime, because the regime is a statement about whether
moves extend or revert.**

- **In positive GEX, take profit fast at nodes.** Dealers are actively damping
  the move. The trade that is up 40% will give it back — that is the mechanism
  working as designed, not bad luck. Scale early, no runners into a pin.
- **In negative GEX, trail and let it run.** Dealers amplify. This is where the
  outsized wins live, and cutting a −GEX winner at a fixed +30% is how a good
  model gets turned into a mediocre one. Trail behind reclaimed nodes.
- **Air-pocket entries get the widest leash** — there is no structure to stall
  the move until the far side of the gap. Target the far node, not a percentage.

**Conviction tiering.** Size and exit style follow setup quality, not enthusiasm:

- **A+** — tier-1 ticker, aligned vanna, RVOL ≥ 1.8, flip or air-pocket setup,
  vendor-confirmed level. 1.5x phase budget, runner allowed.
- **A** — all gates pass, one quality factor missing. Full size, no runner in
  +GEX.
- **B** — gates pass on a tier-2 name or with divergent vanna. 0.5x phase budget, take
  profit at the first node, no runner.
- Below B does not trade. There is no C tier, deliberately.

Standing risk rules from the account playbook still bind and are not overridden
here: the sizing phase ($100/trade fixed under a $4k balance with a 20%-of-balance clamp, then 2.5%, always capped $1,000; A+ conviction sizes 1.5x = up to $150, B 0.5x), −2R daily halt, half-size after a red
day, never average down, never widen a stop, flat by 15:45 ET on short-dated.

## Step 7 — Log every signal

Append every signal — taken or not — to the ledger at
`assets/ledger-template.md`, or to the project doc if the signal-keeper is
running. Record: timestamp, ticker, setup, regime, map source and confidence,
the level, the contract with its live bid/ask **at signal time**, entry, stop,
target, conviction tier, and the gate that failed if it was a no-trade.

This is the part that compounds. Historical GEX cannot be reconstructed — open
interest snapshots are not retrievable after the fact — so a backtest of this
model is not possible, and any that appears to work is reading the future. A
forward log is the only honest way to learn whether the setups pay. Recording
bid/ask at signal time is what makes the results real rather than flattering:
without it, a paper win rate quietly ignores the spread that would have eaten
the edge. Log the no-trades too; the gates are a hypothesis under test as much
as the setups are.

## Output format

Lead with at most three sentences of read. Then this block, always:

```
== HEATSEEKER — [TICKER] — [time ET] ==
Map source: [Skylit / RH-reconstructed / hybrid]  | Confidence: [stable/contested]
Spot: [x]  | Regime: [+GEX / -GEX]  | Vanna: [aligned/divergent]
Flip: [level] ([+/-]x% away)  | King: [x]  | Call wall: [x]  | Put wall: [x]
Air pockets: [ranges or none]

Setup: [name / NO TRADE]
Conviction: [A+ / A / B / no-trade]
Gates: structure [pass/fail] · RVOL [x] · index align [pass/fail] · map conf [pass/fail]
Trigger: [specific, observable condition]
Contract: [e.g. SPY 2026-07-31 740C, 0.52d, bid/ask 6.03/6.06]
Entry: [underlying level]  | Stop: [underlying level]  | Target: [node]
Exit style: [fast-scale at nodes (+GEX) / trail behind nodes (-GEX)]
Invalidation: [what kills the whole thesis]
```

Keep it factual. No profit projections, no hype, no "this should print." The
block is the deliverable; commentary above it is context, not persuasion.

## Session modes

- **Premarket:** build the map on overnight positioning, identify the gap and
  whether the regime supports filling it, and write conditional triggers.
- **Intraday:** rebuild the map every 30 minutes (it moves), re-run the flow
  cross-check, and re-check gates before every entry.
- **Power hour:** charm dominates — read the charm table for pin pull, decide
  runner fates, and take nothing new after 15:35 on 0DTE.
- **OPEX:** pinning is strongest and air pockets are least reliable. Favor
  node-rejection fades; distrust breakouts.

## Relationship to other skills

This engine is the single source of setup logic. The others are views over it:

- **`gex-pullback-scalper`** — a preset of this engine for big pullback days on
  SPY/QQQ: it runs its pullback gate, then hands off to steps 1–7 here. It has
  no signal or risk rules of its own anymore.
- **`vertex-market-scan`** — the dashboard. Its GEX section is context, not a
  trade plan; when a scan surfaces an actionable level on one of the six names,
  it routes here for the plan.
- **SuperTrades agent (repo cowork)** — the shared vocabulary and the binding
  risk numbers live in `supertrades-terminal/docs/SIGNALS.md` and
  `agent/config.py` Guardrails. Where a number here and a number there disagree,
  **Guardrails win**. If a signal-keeper session is running, this engine feeds
  its watchlist; the keeper owns watchlist writes and never places orders.
