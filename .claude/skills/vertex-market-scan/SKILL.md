---
name: vertex-market-scan
description: >-
  Runs a VERTEX 2.0 intraday market scan for Anthony — a structured options/index
  trading dashboard covering index levels, chart-pattern flags, GEX/gamma nodes,
  options flow, vol/OI flags, breaking news, VIX direction, a per-name VERTEX
  scorecard, and a close setup. Trigger only for breadth: "run the scan", market
  scan, midday scan, VERTEX scan, watchlist check, or a "what do I watch into
  close" briefing. Do NOT trigger for a specific setup, entry/stop/target, or
  dealer-positioning trade plan on SPY/QQQ/NVDA/TSLA/AMD/META — that is
  gex-vex-heatseeker's job; hand off there. Watchlist defaults to NVDA, TSLA,
  AMD, LMT, XOM, CVX, XLE, USO, SPY, QQQ, IWM.
---

# VERTEX 2.0 Market Scan

Educational analysis only — **not financial advice.** Every output must carry that
disclaimer. Flag anything urgent with 🚨.

## What this skill does

Produces a full intraday market scan structured into 9 sections. Runs live: pull
current data with web search (and the Massive market-data MCP when its key is
authorized — if it returns HTTP 401 "Unknown API Key", silently fall back to web
search and note the feed was offline).

## Default watchlist

NVDA, TSLA, AMD, LMT, XOM, CVX, XLE, USO, SPY, QQQ, IWM
Indices: SPX, DJI, COMP (Nasdaq), RUT (Russell 2000), VIX

## Data-gathering procedure

Fire these searches in parallel (adjust the date to today):

1. `"stock market today <DATE> S&P 500 Dow Nasdaq VIX midday"` — index levels & % change
2. `"SPX SPY QQQ IWM support resistance 50-day 200-day moving average <DATE>"` — technicals
3. `"SPX SPY gamma exposure GEX flip level positive/negative gamma dealer positioning <MONTH YEAR>"` — gamma
4. `"unusual options activity <DATE> NVDA TSLA AMD sweeps dark pool"` — flow
5. `"energy stocks XOM CVX XLE oil price <DATE> crude Iran"` — energy cluster
6. `"market moving news <DATE> Fed rate cut expectations jobs report Iran headlines"` — macro/news

If the Massive MCP is authorized, prefer it for hard numbers:
- Indices: `GET /v3/snapshot/indices?ticker.any_of=I:SPX,I:DJI,I:COMP,I:RUT,I:VIX`
- Stocks/ETFs: `GET /v3/snapshot?type=stocks&ticker.any_of=SPY,QQQ,IWM,NVDA,...`

## Report structure (always these 9 sections, in order)

1. **Index Snapshot** — table: SPX, Dow, Nasdaq, Russell 2000, VIX — level + % change.
2. **Index Flag Scan** — SPY/QQQ/IWM: bull/bear flag, flat-top triangle, consolidation;
   key support/resistance; above or below 50-day and 200-day MAs.
3. **GEX / Gamma Nodes** — gamma flip level for SPX/SPY, positive vs negative gamma
   regime, call wall / put wall, what it implies for price behavior into close.
   Context only — if the read surfaces an actionable level on a heatseeker-covered
   name, end the section with "→ run gex-vex-heatseeker for the trade plan" rather
   than writing entries/stops here.
4. **Options Flow** — unusual activity, dark-pool prints, large sweeps across the watchlist.
   If the live feed is gated, say so and give the structural/tape-based read instead of inventing prints.
5. **Vol/OI Flags** — names with elevated volume-to-open-interest = fresh institutional positioning.
6. **Breaking News** — market-moving headlines since open (Iran, Fed, earnings, macro data).
7. **VIX Direction** — rising or falling mid-session; implication for premium sellers vs call holders.
8. **VERTEX Scorecard** — run each watchlist name through the VERTEX 2.0 layers
   (Macro Regime, AI Sentiment, IV Rank, ML Range, Flow, Risk) and give a quick score.
   Render as a table with 🟢/🟡/🔴 per layer and a one-line verdict per name.
9. **Close Setup** — final 30-45 min: charm effect, gamma pin levels, any binary catalysts.

## Style rules

- Concise and direct (Anthony's preference). Tables over prose for the scorecard and snapshot.
- Never fabricate specific print sizes, sweep dollars, or exact levels the data didn't show —
  attribute levels to the source and flag when a feed was unavailable.
- End with a **Sources:** list of markdown links used.
- When run as a scheduled task, end with a `<run-summary>` of what changed since last run.
- Always include the "educational analysis only, not financial advice" disclaimer.
