# SuperTrades v3.1 — Day-to-Day Scalp Signal & Execute System

> Durable rulebook: timeless rules only, each stated once. All live/dated data
> (positions, rails, watchlist, counters, settlement) lives in `state.json` —
> the loop reads it first and writes it last every cycle. Broker queries are
> the sole truth for position existence and buying power. Rebuild procedure
> after a session restart: re-arm the cron using the CADENCE AND MODE recorded
> in state.json `mode` (user-set; slow/DND persists until the user reverts it),
> with the pointer prompt in §Loop; let the first cycle reconcile state.json
> against the broker. If the broker reconcile FAILS during a rebuild (MCP not
> reconnected, calls erroring), push a notification immediately — system-failure
> pushes always override DND; a silently dead loop is never acceptable while
> go-live authorization stands.

## 1. Mission & authorization
- Phase-1 compounding: short-dated, high-conviction scalps, managed day-to-day.
- LIVE execution authorized by user ("go live", 2026-07-21): rail-based exits and
  capped entries execute without per-order re-confirmation; every order is
  review→place with a fresh ref_id and reported immediately.
- Kill switches: "pause trading" (alerts-only) · "stop the loop" (kill cron).

## 2. Accounts & guardrails
- Execute ONLY in Agentic cash acct 902341866. Margin acct 812234458 is
  READ-ONLY (alerts only, never trade). Verify agentic_allowed + option level
  via get_accounts when in doubt — never from cached copies.
- Single-leg long calls/puts only. No spreads, shorts, or averaging down.

## 3. Risk limits (single home for all constants) — v4 discipline governor
- Max 1 auto-entry/day AND **max 2 TOTAL entries/day** (auto + manual, tracked via
  reconcile; alert on the 3rd — the loop can't block a manual order but flags it
  loudly and refuses to assist past the cap) · 1 contract/order · never below $30 BP.
- Per-trade contract cost ≤ **25%** of settled BP (v4, was 40%). **Settled BP = the buying_power
  figure get_portfolio returns, nothing else** — never add pending settlement
  or unconfirmed deposits to it. "Settlement-suppressed" means BP < $80; the
  suppression lifts automatically on any BP read ≥ $80. state.json
  `settlement.pending` is informational; entries clear at day rollover once
  settles_on ≤ today.
- Daily halt: day P&L (realized + open) ≤ −$60 → entries stop, exits stay live,
  one push.
- Churn brake: ≥ **3** manual round-trips/day → push with spread-cost estimate (v4, was 4).
  The dominant loss driver in the live run was frequency, not direction — this brake +
  the entry cap + the quality floors (§6) are v4 Layer 1, enforced in engine/reporter.py.
- Exit rails (defaults, materialized per position in state.json with the rule
  version): target +50%, stop −30%, breakeven ratchet arms at +25% HWM.

## 4. Ticker classes (registry + per-ticker assignment in state.json)
- `index_swing` (SPY/QQQ/IWM): overnight OK only at delta ≥ 0.40 AND ≥ 30 DTE.
- `index_scalp` (SPY/QQQ/IWM 0DTE): ONLY via the GEX gate with user-supplied
  levels — never momentum auto-entry. After 3:00pm ET this is the sole
  permitted entry class (GEX-gated flip-reclaim), hard close by 3:55pm ET.
- `single_name` + `sector_etf`: day-trade only — flatten 3:45pm ET unless the
  breakeven ratchet engaged (then push keep/flatten; default flatten 3:55).
- New tickers require user approval, then a class assignment.
- **Position-class mapping** (ticker class + contract → class_defaults key in
  state.json): margin-acct position → `alert_only`; index underlying with
  delta ≥ 0.40 AND ≥ 30 DTE → `swing`; index 0DTE via the GEX gate →
  `0dte_scalp`; everything else (all single names, sector ETFs, and any index
  contract not meeting swing criteria) → `day_trade`.0–1 DTE day_trade
  positions additionally inherit the 0dte hard-exit time.

## 5. Signals & gates
- Momentum leaderboard: intraday % vs prior close across the universe (list in
  state.json), re-ranked on the slow cadence (§Loop).
- Entry conviction: positive day-move AND above intraday VWAP AND (in the
  opening window) above the 15-min opening-range high. Daily RSI as context.
- GEX gate arming (single definition): SPY/QQQ/IWM down ≥ 0.75% intraday OR
  red-after-green → alert "paste GEX flip/wall levels" (CRITICAL if a 0DTE
  position is open — evaluate its stop immediately). IWM is an ARMING SIGNAL
  ONLY — plays and maps are always SPY or QQQ (the gex-pullback-scalper skill's
  scope); never trade IWM through the gate. Never guess levels; the skill owns
  play selection and its own rails.
- GEX maps carry `built_at` + `expiry` and are STALE when expiry < today or
  age > 60 min during market hours — never plan or evaluate against a stale
  map; rebuild first.
- GEX map (approximation): net GEX = callOI×γ − putOI×γ on a $5 grid ±3 nodes
  around spot; king node, walls, V:OI whale rows (flag > 20× with > $1M
  premium). Caveats: OI is T-1, naive sign assumption, aggregate flow only.
- Time-of-day: prefer 9:40–11:00 ET and 3:00–3:30 ET; skip 12:00–14:00 ET
  unless day-move > 3%. No auto-entries 9:30–9:40 ET.

## 6. Contract selection — v4 quality floors
- Delta 0.30–0.50 preferred, **0.35 floor** for entries (v4, was 0.25; 0.08 for
  watchlist rows). Spread ≤ **12%** of ask, hard, **paired with a $0.40 minimum
  premium** so the bid/ask can't be 20%+ of the trade. OI ≥ ~500.
- **No <5-DTE single-name day-trades** (theta-cliff lottos) and **no 0DTE** except a
  single GEX-gated index scalp — 0DTE + churn was the −$115 day. (v4 Layer 1.)
- **Vol-aware pricing (v4.2):** IV > **90%** (or iv_rank in the top 20% of its year) →
  flag "overpaying for vol", **prefer a debit spread** (sell a higher strike to fund the
  long, cutting theta) over a naked call, and the gate **de-ranks** it versus any
  lower-IV eligible pick. IV > **250%** → hard block (uninvestable premium). Applies to
  future entries; existing positions keep their rails.
- **Short-DTE concentration ceiling (v4.2):** any hand-placed (manual/agentic) entry with
  **< 5 DTE** must cost **≤ 35% of settled BP**. This is the *floor under the overrides* —
  it binds even when the daily-2 / midday / min-DTE rails are overridden by hand. The
  engine's auto path stays capped tighter (per-trade ≤ 22% BP). Helper:
  `reporter.short_dte_override_max_usd(bp)`.

## 6b. Profit maximization — give-back trail, scale-out, runner (v4.3)
The fixed +50% target both **capped** upside and **lagged** the poll (QQQ 8/4: +123% peak →
+56% exit). Replace "hard-sell at target" with **let winners run, trail the peak**:
- **Give-back trail** (`giveback` exit_rule, evaluated in `position_exit`): once peak gain
  clears `arm_gain_pct`, exit if the position gives back `peak_frac` of the *peak gain*
  (measured off the persisted high-water mark). Faster clock → tighter trail.
- **Runner** (`target.runner: true`): do NOT cap at +50% — hold and let the trail capture
  the peak. Used for override / high-conviction momentum plays (downside already bounded by
  the §3 concentration ceiling).
- **Scale-out** (`target.scale_out_frac`, multi-contract): bank a slice at the milestone,
  trail the remainder. Single contract → trail only.
- **Exit timing (HARD):** exits go **marketable through the bid** (a resting bid missed the
  QQQ reversal), and the management cadence **tightens to ~8 min once a position is extended**
  (past the ratchet arm) so a peak reversal is caught fast. Exit-time rules are
  **non-discretionary**: **index (SPY/QQQ) positions must be flat by 3:00 ET** — a hard buffer
  *before* the 3:15 backstop, never ridden to the deadline (late-day gamma/pin/theta). DTE is
  a first-class exit input (near-expiry theta forces earlier, marketable exits).
- **Swing rails are HARD:** the give-back trail, daily swing-low stop, and TA+fundamental gate
  are non-discretionary — a break exits, no "one more day"; and swings exit **≥ 1 trading day
  before expiry** (no expiry-week theta cliff).
- **Per-class profile** (materialized from `class_defaults[...].profit_max`), tuned by horizon:
  0dte lock 70% of peak / day lock 60% / **swing lock 50%** / swing_overnight lock 55%.
- **Weekly / swing overlay (TA + fundamentals):** the swing runner gets the most room, but
  keeps holding **only while BOTH** the daily trend is intact (price > rising MA20, higher
  highs, no reversal-on-volume) **and** the growth thesis is intact (no earnings miss /
  guidance cut / negative catalyst via `get_equity_fundamentals` + earnings). If TA breaks OR
  fundamentals deteriorate, exit regardless of the give-back %; trail the stop under the prior
  daily swing-low.
- Shortest expiry that passes conviction wins; step OUT an expiry rather than
  force a junk contract. Delta-per-dollar breaks ties.
- Watchlist rules: rows live in state.json; auto-add pool contracts drifting
  under the cap; same-ticker swaps only after a conviction re-check; remove
  rows > cap+10% (suspended while settlement-suppressed, resume at BP > $80);
  no auto-entry into a ticker already held.
- Relevance prune (EVERY cycle): loop the watchlist and remove any row that no
  longer represents a plausible next entry — (a) that contract was exited/stopped
  same-day (no immediate re-arm into a fresh stop-out), (b) delta < 0.08 watchlist
  floor, (c) the underlying is decisively counter to the row's thesis with no
  setup forming, or (d) row > cap+10% (suspended while settlement-suppressed).
  Mirror every removal to the RH watchlist. Keep rows that still have a live thesis
  even if temporarily unaffordable.
- RH mirror: the Robinhood options watchlist mirrors state.json watchlist+pool.
  On any add/swap/remove, apply the same change via the watchlist MCP tools in
  the same cycle (add_option_to_watchlist / remove_option_from_watchlist);
  state.json remains the source of truth on any conflict.

## 7. Exits (schema-driven; the loop executes ONLY what state.json declares)
- Every position carries `exit_rules` (typed, parameterized) instantiated from
  its class defaults in state.json: target/stop/ratchet %, class session-time
  stops (0DTE hard-exit 3:15pm ET; day-trade flatten 3:45pm ET), derived time
  stops (`days_before_expiry`, never pinned dates), and optional typed extras
  (e.g. underlying_trend_break {day_pct_below, cycles, mark_below};
  momentum_stall {after_et, day_pct_max, mark_below}).
- Sell mechanics: stops post limit at BID, targets at mark; verify fill ~60s;
  one cancel-replace crossing the spread if unfilled; report the actual fill.
- Margin-acct positions: alert-only versions of the same rules.

## 8. Loop mechanics (cron pointer prompt: "Read supertrades/supertrades-v3.md
##    and supertrades/state.json; run one SuperTrades cycle per their rules.")
- Clock gate first: outside 8:55am–4:05pm ET weekdays → no-op (zero MCP calls,
  no writes, no republish). Premarket branch runs 9:05–9:30 ET when
  state.open_plan is unbuilt: roll the day block, read settled BP, gap-scan
  (extended hours), build QQQ+SPY GEX maps, write open_plan, one push.
- Cycle order (orchestrated): (1) reconcile positions vs broker (user fills →
  realized P&L; new positions → instantiate class rails, push); (2) FETCH one
  read-only snapshot via the Robinhood MCP tools (the project's single
  authenticated broker path — quotes, option quotes, GEX chains, account);
  (3) run the engine — `python -m supertrades.engine.run_cycle --state
  supertrades/state.json --snapshot <snapshot.json>` — which fans out one
  concurrent node per ticker / GEX underlying (map+whale+gate) / position /
  candidate, batch fan-ins, and applies EVERY guardrail exactly once in
  `engine/reporter.py`; (4) execute the report's actions via MCP (review→place)
  → dashboard → state write. Node count contract: len(universe) +
  3·len(index tickers) + len(positions) + len(watchlist). Engine health check
  after any rebuild: `python -m supertrades.engine.run_cycle --selftest`.
- Efficiency gates: get_portfolio only when an entry is actually possible this
  cycle; quote held contracts + top-3 leaders every cycle, full universe every
  3rd cycle; GEX map refresh ~30 min or on gate arming/node cross; dashboard
  rewrite+republish only when displayed values changed; state.json write only
  on material change; git commit only on events (fills, rail changes, halt,
  day rollover) — never on a timer.
- **Day rollover — runs FIRST on ANY in-hours cycle where state.trading_date
  != today** (not only in the 9:05–9:30 window; a late resurrection still
  rolls before doing anything else): reset the ENTIRE day block (realized_pnl
  → 0, auto_entries_used → 0, manual_round_trips → 0, churn_threshold_hit →
  false, halted → false), clear prior_cycle ENTIRELY (marks, cumulative
  volumes, day_pct, crossed flags, note — never diff any of them across
  dates), mark all gex_map entries stale, clear settled settlement entries,
  set trading_date. Then run the premarket plan if before 9:40 ET, else
  proceed straight to the normal cycle. Additionally, prune prior_cycle keys
  for any position the moment it closes intraday.
- Resilience (v4 Layer 2 — reliable ops): the self-scheduling wakeup is NOT trusted
  as the sole timer (it stalled repeatedly on 7/23–7/24 and carried a day-trade over
  the weekend by missing its 3:45 flatten). Instead:
  (a) **Concentrated cron** fires the loop at the hours that matter — premarket 8/9 ET,
      the 9:40 entry window, 10/11 ET, 1 PM, and 6 PM — plus a **dedicated 3:44 PM ET
      flatten trigger** so a day-trade close can never be missed by a stalled tick.
  (b) **Every fire computes the same `engine/ops.cycle_intent(...)`** — a deterministic
      decision on what THIS cycle MUST do (no-op / rollover / premarket plan / flatten /
      reconcile / run) from the ET clock + state, so no source can skip a required action.
  (c) **A stale state (>20 min in-hours) forces a full broker reconcile**, never a bare
      selftest — the mistake that let 3 user positions go untracked for hours on 7/23.
  Heartbeats still re-arm the cron from this file after a restart (cadence/mode from
  state.mode; failure-path push per the rebuild procedure above).
- Delivery: BOTH pages in state.json `pages` (console + index desk) are
  maintained per its publish_rule (edit repo file, publish with file_path AND
  stored url). The index desk's alert feed accumulates every DND-muted alert.
- Push precedence: state.mode governs. Under DND only executed orders, the
  daily halt, and system failures push; everything else (including the
  premarket open-plan summary) goes to the pages and ledger silently. Every
  state.json write bumps updated_at.

## 6c. Win rate + expectancy — lock the win, cut losers, run a piece (v4.4)
Review of the live window (6 closes, ~33% win rate, gross ≈ −$7) showed the edge wasn't
the winners (+50–64% clean targets) — it was **two oversized losses (NVDA −55%, DIS −42%,
past the −30% stop)** plus **winners round-tripping** (QQQ +123%→+56%). "Max win rate" naively
(tiny scalps) would kill the big wins that carry expectancy. The logical target is **max
expectancy = win_rate·avg_win − loss_rate·avg_loss**, raised on all three terms:
- **Lock the win early (`green_lock`):** once a trade's peak clears `arm_pct` (~+20%), a
  small-green floor at `floor_pct` (+5–10%) goes live — a brief winner can no longer become a
  loss. Raises win_rate without capping upside (the runner/trail still owns the top). Per-class
  in `class_defaults[...].green_lock`.
- **Cut losers hard (cap avg_loss):** −30% stop is marketable and checked every cycle;
  single-names don't sit overnight into gap risk (the −55%/−42% slips came from stops not being
  honored fast enough). Reliable-ops flatten (§Layer 2) is the backstop.
- **Run a piece (protect avg_win):** never-red floor + give-back trail keep the runner alive so
  the occasional +100%+ still lands. Scale-out banks the win on ≥2 lots.
- **Sizing insight:** the cleanest win-rate + growth combo needs **≥2 contracts** — bank 1 at
  the first target (locks the win), run 1 under the trail (captures growth). Budget-permitting,
  prefer 2×small over 1×large so scale-out is available.
- **Visibility:** `state.performance` tracks win_rate / avg_win / avg_loss / expectancy so the
  system sees its own edge and can adapt (auto-updater on close is the next wire-up).

## Changelog
- v4.4 (2026-08-04): WIN-RATE / EXPECTANCY layer. `green_lock` exit_rule (arm a small-green
  floor once peak clears ~+20% → brief winners can't round-trip to losses); per-class green_lock
  profiles; `state.performance` tracker (win_rate/expectancy). Framed by a review of the live
  window (33% win rate, edge erased by 2 oversized losses). +4 tests; suite 54/54.
- v4.3 (2026-08-04): PROFIT-MAX / GIVE-BACK TRAIL. New `giveback` exit_rule + runner
  (uncap winners) + multi-contract scale-out in the exit engine; per-class profit_max
  profiles (0dte tight → swing wide) with a TA+fundamental overlay for weekly swings;
  marketable exits + cadence that tightens to ~8min when extended. Applied live to the
  INTC runner. Prompted by QQQ 8/4 (+123% peak → +56% exit). +8 tests; suite 50/50.
- v4.2 (2026-08-04): VOL-AWARE PRICING + SHORT-DTE CONCENTRATION CEILING, both in the
  single reporter gate. `candidate_entry` now surfaces IV/iv_rank (fact only). The gate
  flags IV > 90% (prefer a debit spread), de-ranks high-IV vs lower-IV picks, and hard-blocks
  IV > 250%; and blocks any < 5-DTE entry costing > 35% BP — a ceiling that binds even under
  hand overrides (`reporter.short_dte_override_max_usd`). Prompted by the 8/4 INTC 1-DTE
  (IV ~122%, ~49% BP) taken over-cap; that open position is grandfathered. +7 tests; suite 42/42.
- v4.0 Layer 1 (2026-07-27): DISCIPLINE GOVERNOR live in engine/reporter.py after the
  7/21–7/24 live run showed frequency (not direction) was the loss driver. Tightened:
  entries ≤ 2/day total (was 1 auto only), per-trade ≤ 25% BP (was 40%), delta ≥ 0.35
  (was 0.25), spread ≤ 12% + premium ≥ $0.40, no <5-DTE day-trades, no non-index 0DTE,
  churn brake at 3 (was 4). Adds a per-cycle discipline scorecard to the console. Nodes
  never generate entries — the loop is a discipline+risk layer over the user's own signals.
  9 new tests; suite 23/23. Layers 2 (reliable ops) + 3 (Obsidian journal + backtest)
  proposed in supertrades-v4-proposal.md, not yet built.
- v3.2 (2026-07-23): per-cycle loop rewritten from serial pipeline to fan-out /
  layered fan-in (`supertrades/engine/`): independent nodes propose, a single
  reporter gate decides. No guardrail values changed; snapshot fetch stays on
  the existing Robinhood MCP path (no second login). Tests:
  `python -m unittest discover -s supertrades/engine/tests`.
- v3.1 (2026-07-21): /simplify consolidation — spec/state/cron role split,
  single-home rules (after-3pm exception, spread cap, gate trigger), class
  registry + typed exit-rule schema, derived dates, structured settlement,
  efficiency gates (clock no-op, change-gated republish, event-driven commits),
  pointer cron prompt. No trading-behavior changes intended.
- v3 (2026-07-21): initial live system; superseded sections removed in v3.1.
- v2: not present in this environment — merge pending user providing it.
