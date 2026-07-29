# Heatseeker Signal Ledger

Append one row per signal — **including no-trades**. The no-trades are what tell
you whether the gates are calibrated or merely strict.

Because historical GEX maps cannot be rebuilt, this forward log is the only valid
record of whether the model works. Record bid/ask **at signal time**: a paper win
rate that ignores the spread is measuring a market that does not exist.

| # | Date | Time ET | Ticker | Setup | Regime | Vanna | Map src | Conf | Level | RVOL | Tier | Contract | Bid/Ask @ signal | Entry | Stop | Target | Outcome | R | Notes |
|---|------|---------|--------|-------|--------|-------|---------|------|-------|------|------|----------|------------------|-------|------|--------|---------|---|-------|
| 1 |      |         |        |       |        |       |         |      |       |      |      |          |                  |       |      |        |         |   |       |

**Outcome** — one of: `target` · `stop` · `time-stop` · `scratch` ·
`no-trade (gate: X)` · `no-fill`.

**R** — realised return in multiples of initial risk, measured on the underlying
distance from entry to stop. R is comparable across tickers and contracts;
percentage return on premium is not.

## Weekly review

Five questions, answered from the ledger rather than from memory:

1. **Which setups actually paid?** Group by setup. Fewer than ~10 instances of a
   setup is not yet evidence about that setup.
2. **Did any gate reject a signal that would have worked?** Persistent rejection
   of winners means the gate is miscalibrated, not virtuous. Check RVOL 1.4
   specifically — it is the gate most likely to be too strict.
3. **Did +GEX trades give back gains, or −GEX runners get cut early?** These are
   exit-policy failures and they are invisible in a win-rate column.
4. **How far was realised entry from signal price?** Persistent slippage means
   triggers are being written too late or too vaguely.
5. **Map confidence vs outcome** — did contested-board signals underperform
   stable-board ones? If not, the flow cross-check may be overcautious.

## Sample size

Roughly 30 signals before any per-setup read means much; well over 100 before a
win rate distinguishes a real edge from noise. Two weeks will not get there. Say
so plainly when reporting results rather than over-reading a small sample — an
early winning streak on ten trades is the most expensive thing that can happen to
a new system, because it buys confidence the data has not earned.
