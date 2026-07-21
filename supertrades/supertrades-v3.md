# SuperTrades v3 — Day-to-Day Scalp Signal & Execute System

> v3 codifies all edits from the 2026-07-21 session. v2 was not available in this
> environment (lives in a prior session/machine) — paste it in any session to merge
> anything missing. This file is the durable source of truth: if the live loop dies
> with a session, rebuild it from here.

## Mission
Phase-1 compounding: grow a small options account quickly but safely via short-dated,
high-conviction call scalps, managed day-to-day on a 5-minute loop. Profits compound;
guardrails are non-negotiable.

## Accounts & hard guardrails
- **Execute ONLY in Agentic cash acct ••••1866** (agentic-allowed, option level 2, cash-only BP).
- **Margin acct ••••4458 is READ-ONLY** — monitor/alert, never trade.
- Single-leg long calls/puts only (level 2). No spreads, no shorts, no averaging down.
- Max **1 auto-entry per day**; max **1 contract** per order; never spend below $30 remaining BP.
- **Daily halt**: if day P&L (realized + open) ≤ **−$60**, no new entries until next day; alert once.
- Every order action is reported to the user immediately (fill, price, updated BP).
- Kill switches: "stop the loop" (kills cron), "pause trading" (revert to alerts-only).

## Signal stack (scored per ticker, every cycle)
1. **Momentum**: intraday % vs prior close (leader board across watchlist tickers).
2. **RSI context**: daily RSI — favor <45 turning up (reversal) or 50–65 rising (continuation).
3. **GEX gate (SPY/QQQ only)**: arm the gex-pullback-scalper skill when SPY or QQQ is
   down ≥0.75% intraday. Requires user-supplied flip/wall levels; never guess strikes.
   Up-days = gate FAIL = no index scalp. A NO TRADE call is a valid output.
- Ticker universe: watchlist underlyings only (RIVN, NVDA, DIS, INTC, TSLA, META, SPY, QQQ).
  New tickers require user approval.

## Contract selection rules
- **Premium cap**: ask ≤ current BP / 100 (hard affordability), target ~$1.00 or less.
- **Short-dated priority**: ≤ 2 weeks to expiry preferred; couple-days OK when signal is hot.
- **Quality floor**: delta ≥ 0.25 for entries (≥ 0.08 minimum for watchlist rows);
  no sub-0.08-delta lotto fills even if cheap. Spread ≤ ~10% of premium; OI ≥ ~500.
- High-IV names (e.g. INTC at 100%+ IV) that price out of the cap: skip, don't reach for junk strikes.
- **Concentration**: no auto-entry in a ticker already held.

## Watchlist management (every 5 min)
- Watchlist = buyable candidates only (position tracking is separate).
- Re-price candidates + standby pool each cycle; auto-add pool contracts drifting under the cap.
- **Same-ticker swaps only** (different strike/expiry of same underlying), and only if
  conviction is intact (momentum + RSI re-check). Conviction faded → remove + alert, don't swap.
- Remove entries whose ask exceeds the cap by >10%.

## Exit ladder (executed automatically when live)
- Positions in Agentic acct: **target +50% → sell to close; stop −30% → sell to close**
  (limit at mark, tick-rounded). ≥30% swing between scans → alert.
- **Breakeven ratchet**: once a position's high-water mark hits +25%, the stop moves to entry.
- **Momentum-stall exit** (low-delta positions): from 3:30pm ET, if the underlying's day is
  flat/red and the position is below +20%, sell — theta wins stalls.
- **Close watch**: alert on any universe ticker crossing ±2% intraday or reversing >1%
  cycle-over-cycle. Gamma-flip proxy: SPY/QQQ turning red after green (or −0.75%) → prompt
  user for GEX flip/wall levels; never guess levels.
- Time stops: monthlies exited ~2 weeks before expiry if flat; short-dated positions not
  working within the planned window get closed — theta is the silent stop.
- Margin-acct positions: alert-only versions of the same rails.
- GEX index scalps (when armed) use the skill's tighter rails: −10% stop, scale 50% @ +5%,
  25% @ +10%, runner only if structure supports.

## Flow watch & delivery (added 15:40 UTC)
- Per-cycle 5-min volume deltas on held contracts: rising delta + favorable price acceleration
  = "flow picking up" push; falling delta 2+ cycles with stalled gains = "flow slowing" push.
- Push notifications (phone/desktop) on: fills ("OPENED"/"CLOSED @ price"), target/stop hits,
  flow shifts on held names, gamma-flip proxy, daily halt. Quiet cycles never push.
- Dashboard republished every cycle at the same URL (data ≤ ~5 min old on refresh):
  https://claude.ai/code/artifact/0a42b805-1b5b-4668-936a-4d0631da0bd4
- Watchlist rows: RIVN 8/7 $19c · DIS 8/21 $110c · NVDA 7/31 $225c (sub-$0.80 adds 15:38 UTC).

## Loop mechanics
- **5-min cron** (session-local): exit scan → watchlist refresh → GEX gate → (if live) entry check.
- **Hourly heartbeat Routine** (durable, survives restarts): verifies the 5-min cron exists;
  if the session restarted, rebuilds the loop from this file before resuming.
- Silent unless: exit trips, order executes, watchlist changes, conviction fades, GEX gate arms,
  or daily halt triggers.
- Known limits: ~5-min granularity (not seconds); cron fires queue while the agent is busy.

## State snapshot — 2026-07-21 (go-live verified 15:15 UTC)
- LIVE. User authorization: "go live" (2026-07-21). Standing authorization covers rail-based
  exits and capped entries executed by the loop (review_option_order → place_option_order,
  fresh ref_id per order, reported immediately); no per-order re-confirmation.
- Verified: 5-min cron alive (8e6f17e8); hourly heartbeat Routine trig_01AuFqYEVYqWvtmJhkvSPAx3
  (fires :09); Agentic acct 902341866 agentic_allowed + option_level_2; order tools reachable.
- Positions: IREN 7/24 $33p @ $0.39 (margin, alert-only, deep loss, Thu time-stop);
  RIVN 8/21 $18c @ $1.41 (rails $2.12 / $0.99); NVDA 8/21 $240c @ $0.85 (rails $1.28 / $0.60).
- Watchlist: RIVN 8/7 $19c (~$0.85, delta 0.39; entry blocked — holding RIVN). Pool: NVDA 7/31
  $220c, DIS 8/21 $105c, SPY 8/7 $765c, TSLA 7/31 $460c (junk-flagged).
- Account $322.62 · BP $87.62 → premium cap $0.87. Day cap: 1 entry. Auto-entries today: 0.
- Console artifact (snapshot dashboard): https://claude.ai/code/artifact/0a42b805-1b5b-4668-936a-4d0631da0bd4

## Changelog
- **v3 (2026-07-21)**: sub-$100→BP-scaled premium cap; short-dated priority; same-ticker
  swap rule; conviction re-check before swaps; GEX gate integration; live execution policy
  with daily halt + entry caps; heartbeat resurrection; account guardrail split codified.
- **v2**: not present in this environment — merge pending user providing it.
