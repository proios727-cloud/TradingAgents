# SuperTrades Terminal

A runnable implementation of the **`SuperTrades Terminal.dc.html`** design, imported from the
Claude Design project *"Matching app for supertrades"* and wired up so it runs as a
self-contained web app.

This is the **desktop terminal UI running on the bundled deterministic simulation** — the
same prototype behavior shown in the design, made to run locally with no build step and no
network dependency. It is **not** the live execution agent: nothing here connects to a
broker, pulls live market data, or places orders. See [Scope](#scope) below.

## Screens

Single-page terminal (52px top bar + left nav rail) with all eight design views:

| View | What it shows |
|------|---------------|
| **Signals** | Live signal feed — signal cards with entry/stop/target, confidence meters, factor chips (GEX / flow / TA / HVN / MKT), R:R, and a detail drawer |
| **Chart** | 5-minute candles (`genCandles`) with levels |
| **Scanner** | Watchlist scan across SPY, QQQ, NVDA, TSLA, AMD, META, COIN, MSTR, XOM, CVX, XLE |
| **GEX** | Gamma-exposure map — spot / flip / king node / call & put walls / net GEX, and a gamma-profile-by-strike bar chart |
| **P&L** | Session P&L, open positions, and the trade log |
| **Backtest** | 90-session bar-by-bar replay (`genBacktest`) — balance curve, win rate, avg R, max drawdown, per-strategy breakdown |
| **Alerts & Settings** | Alert stream and configuration |

All numbers come from `data.js` — a deterministic, seeded simulation (`mulberry32`). The
top-bar badge reads **SIMULATED DATA** to make that explicit.

## Run it

The page loads ES modules and is transpiled at runtime, so it must be served over HTTP
(opening the file with `file://` will not work). From this directory:

```bash
cd supertrades-terminal
python3 -m http.server 8099
```

Then open:

```
http://127.0.0.1:8099/
```

(The root redirects to `SuperTrades Terminal.dc.html`.) Any static file server works —
e.g. `npx serve -l 8099` — the only requirement is HTTP.

### Confirm it matches the design

Load the URL and step through the nav rail. You should see the green-on-black terminal with
the SPY/QQQ/TSLA ticker strip, the `−GAMMA REGIME` banner, the signal feed, and session P&L
`+$1,907.00` on **Signals**; the gamma-profile bar chart on **GEX**; and the
`+16068.3% / 71% win / +0.98R / −17.1% max DD` balance curve on **Backtest** — identical in
layout and styling to `SuperTrades Terminal.dc.html` in the Claude Design project.

## How it's wired

- **`SuperTrades Terminal.dc.html`** — the design file (a Design-Canvas `.dc.html`). Its
  `<x-dc>` template + inline logic class are rendered by the dc-runtime in `support.js`,
  which mounts a React root into `#dc-root` on load.
- **`data.js`** — the deterministic market simulation and the ported logic
  (`genCandles`, `genGex` inputs, `genBacktest`, signal/position/trade fixtures).
- **`_ds/…`** — the design-system: token CSS (colors, typography, spacing, effects, fonts,
  base) plus the component bundle (`_ds_bundle.js`: Badge, Card, Tabs, Toast, Button, Input,
  Select, Switch, ConfidenceMeter, DataTable, SignalCard, StatCard, TickerChip).
- **`vendor/`** — React 18.3.1, ReactDOM 18.3.1, and Babel-standalone 7.29.0 (UMD builds),
  vendored locally and preloaded ahead of `support.js`. The runtime detects
  `window.React` / `window.ReactDOM` / `window.Babel` already present and **skips its CDN
  fetch**, so the terminal runs fully offline. (Web fonts still load from Google Fonts when
  online; offline they fall back to the system font stack in the type tokens.)

The only change from the raw design export is the three vendored `<script>` tags added to
the `.dc.html` `<head>` for offline running — everything else is the design as delivered.

## Scope

This directory is the **UI on simulated data only**. The broader SuperTrades handoff
(in the design project's `design_handoff_supertrades_*` bundles and `GO-LIVE.md`) describes
a separate live execution agent — Robinhood Agentic MCP, Massive market data, real 0DTE
orders, risk governor, kill switches. **None of that is implemented or wired here**, by
design: that path is human-gated (funded, approved, and armed by the operator, with every
order previewed) and must not be built or armed autonomously. This terminal is the
front-end the operator watches; hooking it to live data/execution is a deliberate, separate
step.
