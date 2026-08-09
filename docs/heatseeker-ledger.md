# Heatseeker Signal Ledger

Append one row per signal — **including no-trades**. The no-trades are what tell
you whether the gates are calibrated or merely strict.

Because historical GEX maps cannot be rebuilt, this forward log is the only valid
record of whether the model works. Record bid/ask **at signal time**: a paper win
rate that ignores the spread is measuring a market that does not exist.

| # | Date | Time ET | Ticker | Setup | Regime | Vanna | Map src | Conf | Level | RVOL | Tier | Contract | Bid/Ask @ signal | Entry | Stop | Target | Outcome | R | Notes |
|---|------|---------|--------|-------|--------|-------|---------|------|-------|------|------|----------|------------------|-------|------|--------|---------|---|-------|
| 1 | 2026-07-29 | 15:42 | SPY | NO TRADE | -GEX (net -6.82B/1%) | divergent (VEX +213M) | RH-reconstructed (7/30+7/31, ±3%) | contested (flip drift 0.75%) | flip 750.46 OI / 744.96 flow; king 725; put wall 725; call wall 750 | n/a — intraday bars unreliable | 1 | — | — | — | — | — | no-trade (gate: calendar + map conf + RVOL unverifiable) | Spot 733.89 (-0.94%). Deep -GEX, board being rebuilt intraday. Air pockets below: 730–733, 727–730; above: 736–740, 743–750. Conditional triggers written for 7/30 open. |

**Outcome** — one of: `target` · `stop` · `time-stop` · `scratch` ·
`no-trade (gate: X)` · `no-fill`.

**R** — realised return in multiples of initial risk, measured on the underlying
distance from entry to stop. R is comparable across tickers and contracts;
percentage return on premium is not.
