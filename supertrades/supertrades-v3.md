# SuperTrades v3.1 — Day-to-Day Scalp Signal & Execute System

> Durable rulebook: timeless rules only, each stated once. All live/dated data
> (positions, rails, watchlist, counters, settlement) lives in `state.json` —
> the loop reads it first and writes it last every cycle. Broker queries are
> the sole truth for position existence and buying power. Rebuild procedure
> after a session restart: re-arm the 5-min cron with the pointer prompt in
> §Loop, then let the first cycle reconcile state.json against the broker.

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

## 3. Risk limits (single home for all constants)
- Max 1 auto-entry/day · 1 contract/order · never below $30 remaining BP.
- Per-trade contract cost ≤ 40% of settled BP.
- Daily halt: day P&L (realized + open) ≤ −$60 → entries stop, exits stay live,
  one push.
- Churn guard: ≥ 4 manual round-trips/day → push with spread-cost estimate.
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

## 5. Signals & gates
- Momentum leaderboard: intraday % vs prior close across the universe (list in
  state.json), re-ranked on the slow cadence (§Loop).
- Entry conviction: positive day-move AND above intraday VWAP AND (in the
  opening window) above the 15-min opening-range high. Daily RSI as context.
- GEX gate arming (single definition): SPY/QQQ/IWM down ≥ 0.75% intraday OR
  red-after-green → push "paste GEX flip/wall levels" (CRITICAL if a 0DTE
  position is open — evaluate its stop immediately). Never guess levels; the
  gex-pullback-scalper skill owns the play selection and its own rails.
- GEX map (approximation): net GEX = callOI×γ − putOI×γ on a $5 grid ±3 nodes
  around spot; king node, walls, V:OI whale rows (flag > 20× with > $1M
  premium). Caveats: OI is T-1, naive sign assumption, aggregate flow only.
- Time-of-day: prefer 9:40–11:00 ET and 3:00–3:30 ET; skip 12:00–14:00 ET
  unless day-move > 3%. No auto-entries 9:30–9:40 ET.

## 6. Contract selection
- Delta 0.30–0.50 preferred, 0.25 floor for entries (0.08 floor for watchlist
  rows). Spread ≤ 10% of ask, hard. OI ≥ ~500.
- Shortest expiry that passes conviction wins; step OUT an expiry rather than
  force a junk contract. Delta-per-dollar breaks ties.
- Watchlist rules: rows live in state.json; auto-add pool contracts drifting
  under the cap; same-ticker swaps only after a conviction re-check; remove
  rows > cap+10% (suspended while settlement-suppressed, resume at BP > $80);
  no auto-entry into a ticker already held.

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
- Cycle order: reconcile positions vs broker (user fills → realized P&L; new
  positions → instantiate class rails, push) → exits → guards → entry check →
  flow/gate watch → dashboard → state write.
- Efficiency gates: get_portfolio only when an entry is actually possible this
  cycle; quote held contracts + top-3 leaders every cycle, full universe every
  3rd cycle; GEX map refresh ~30 min or on gate arming/node cross; dashboard
  rewrite+republish only when displayed values changed; state.json write only
  on material change; git commit only on events (fills, rail changes, halt,
  day rollover) — never on a timer.
- Day rollover: reset counters, clear crossed flags and cumulative volumes
  (never diff volumes across dates).
- Resilience: hourly heartbeat Routine re-arms the cron from this file if the
  session restarted. Push notifications: fills, rail trips, flow shifts on
  held names, gate arming, halt. Dashboard republishes to the same artifact
  URL (in state.json).

## Changelog
- v3.1 (2026-07-21): /simplify consolidation — spec/state/cron role split,
  single-home rules (after-3pm exception, spread cap, gate trigger), class
  registry + typed exit-rule schema, derived dates, structured settlement,
  efficiency gates (clock no-op, change-gated republish, event-driven commits),
  pointer cron prompt. No trading-behavior changes intended.
- v3 (2026-07-21): initial live system; superseded sections removed in v3.1.
- v2: not present in this environment — merge pending user providing it.
