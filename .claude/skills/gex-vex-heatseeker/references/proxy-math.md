# Proxy math — what the numbers mean and where they are wrong

Read this before trusting a reconstructed map. The formulas are standard; the
*assumptions* are where the risk lives, and they are not visible in the output.

## The dealer sign convention

Every GEX number published anywhere rests on an assumption about which side of
each contract the dealer is on. Real dealer books are not observable. The
convention used here — and by the mainstream vendors — is:

- Customers **buy puts** for protection, so dealers are **short puts** → puts
  contribute **negative** gamma.
- Customers **sell/overwrite calls**, so dealers are **long calls** → calls
  contribute **positive** gamma.

This is a simplification and it is wrong in individual cases — a day of heavy
retail call buying inverts the call side entirely. It is used anyway for a reason
worth understanding: the levels it produces are the levels *other traders are
also watching*, and a level that enough participants act on becomes real through
their behaviour regardless of whether the underlying assumption held. The map is
partly a model of dealer flow and partly a model of crowd attention. Both matter;
only the first is in the formula.

**Practical consequence:** on a day with obviously unusual flow — a retail call
frenzy, a large put unwind — the sign convention degrades and the map should be
downweighted. The flow cross-check partially detects this.

## Formulas

With `S` spot, `K` strike, `T` years to expiry, `σ` implied vol, `r` risk-free:

```
d1 = [ln(S/K) + (r + σ²/2)T] / (σ√T)
d2 = d1 − σ√T

gamma = φ(d1) / (S·σ·√T)
vanna = −φ(d1)·d2 / σ                 (∂delta/∂vol)
charm = −φ(d1)·(2rT − d2·σ√T) / (2T·σ√T)   (∂delta/∂time)
```

Aggregated per strike, with `sign` = +1 for calls and −1 for puts:

```
GEX   = Σ sign · gamma · OI · 100 · S² · 0.01     → $ delta change per 1% spot move
VEX   = Σ sign · vanna · OI · 100 · S  · 0.01     → $ delta change per 1 vol point
CHARM = Σ sign · charm · OI · 100 / 365           → $ delta change per day
```

Units matter when comparing tickers: these are dollar figures, so NVDA's raw GEX
is not comparable to SPY's. Compare each name against **its own** recent range,
never across names.

## Why gamma is re-derived when scanning for the flip

The flip level is the spot price at which net GEX crosses zero. Finding it
requires asking "what would net GEX be if spot were at X?" — and gamma itself
changes with spot. Reusing the broker's gamma (computed at the *current* spot)
across a scan of hypothetical spot levels produces a flip level that can be off
by a meaningful fraction of a percent, which on a 0DTE trade is the difference
between a setup and a loss. `gex_map.py` re-derives gamma from Black-Scholes at
each scanned level for this reason.

Multiple zero crossings are normal. The nearest is the active boundary; the
others mark where the regime would flip again if price travelled there.

## Known limitations — the honest list

**1. Open interest is T+1.** Intraday, OI describes yesterday's close. Same-day
positioning is invisible to it. This is the single largest weakness, and it hurts
most exactly where the model is most used: 0DTE, where same-day flow *is* the
board. Mitigation is the `--compare-flow` cross-check, which is a detector, not
a fix.

**2. Same-day volume is direction-blind.** The API gives volume but not whether
trades opened or closed, or whether customers bought or sold. The 30% factor in
the flow adjustment is a convention, not a measurement. Treat divergence between
the two maps as a confidence signal, never as a better map.

**3. Implied vol comes from the broker's own model.** Different vendors compute
IV differently, so a reconstructed map will not exactly match Skylit's or
SpotGamma's. Expect small level disagreements. When a pasted vendor level and a
reconstructed one disagree by more than ~0.2%, prefer the vendor's.

**4. Strike window truncation.** The ±3% window drops far-tail strikes. Those
carry little gamma but non-trivial vanna, so **VEX is understated more than GEX
is.** Widen the window when vanna is central to the read.

**5. Dividends and borrow are ignored** (q = 0). Negligible for 0–7 DTE on these
six names; would matter on longer-dated or high-yield underlyings.

**6. Historical maps cannot be rebuilt.** Full-chain OI snapshots are not
retrievable after the fact. There is no way to reconstruct what the board looked
like at a past moment, which means **this model cannot be backtested** — any
backtest that appears to work is using present data to describe the past. Forward
logging is the only valid evaluation, which is why the ledger is part of the
skill rather than an optional extra.

## Sanity checks before trusting a map

Run these; they catch most bad inputs:

- **Flip within ±2% of spot?** Much further out usually means a truncated window
  or a bad IV, not a genuinely distant regime boundary.
- **Net GEX sign matches price behaviour?** If the map says +GEX (damped) but
  price is trending hard all session, the map is stale or the sign convention has
  broken down. Trust the tape.
- **King node has real OI?** A king node built on a few hundred contracts is an
  artifact.
- **Air pockets ≥ 1.8× normal spacing?** The detector uses the board's own median
  spacing; a "pocket" at 1.0× is just the strike ladder.
- **Flow drift < 0.15%?** Above that, the board is contested. Say so in the output.

If two or more checks fail, the correct output is that the map is unreliable —
not a lower-conviction trade off a map you have just concluded is broken.
