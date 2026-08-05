---
name: gex-pullback-scalper
description: Big-pullback-day preset for the gex-vex-heatseeker engine — SPY & QQQ only. Use this skill when the user explicitly asks for the pullback scalper, or names a "big red day", "pullback play", or dip-buying SPY/QQQ on a hard down day. For every other GEX/dealer-positioning, setup, or trade-plan question (including general SPY/QQQ intraday questions), use gex-vex-heatseeker instead — it owns the signal engine. If a pasted watcher alert from gex_watcher.py appears, that's this skill.
compatibility: A preset over gex-vex-heatseeker (which requires the Robinhood Trading MCP or pasted Skylit/vendor levels). Bundles scripts/gex_watcher.py for self-hosted alerting. No broker execution — outputs a trade plan only.
---

# GEX Pullback Scalper — pullback-day preset (SPY & QQQ)

This skill is no longer a standalone system. It is a **preset over the
`gex-vex-heatseeker` engine** for one specific tape: big index pullback days.
It contributes exactly three things — the pullback gate, the session cadence,
and the watcher integration. Everything else (map building, regime read, setup
mechanics, contract selection, exits, logging, output block) comes from
heatseeker, and **risk numbers come from the account playbook** (the sizing phase ($100 fixed under $4k balance, 20%-of-balance clamp, then 2.5%; capped $1,000; A+ conviction 1.5x = up to $150, B 0.5x), −50% premium stop, −2R daily halt, flat by
15:45 ET on short-dated, no averaging down). The old preset-specific rules
(5% sizing, −10% premium stop, +5/+10 scale ladder, 0.30–0.45Δ) are retired —
they contradicted the account standard and the live data.

## Pullback gate (run before the engine)

A "big pullback day" requires at least **two** of:

- SPY or QQQ down **≥ 0.75%** intraday (≥ 1.25% = high-conviction)
- Price **below the gamma flip** (negative-gamma regime)
- VIX up **≥ 5%** on the day or above its recent range
- Price has tagged the **put wall** or entered an **air pocket**

Fewer than two → **NO TRADE**, say so plainly, stop. A no-trade call is a
successful run.

## Then run the engine

Gate passed → run `gex-vex-heatseeker` steps 1–7 restricted to **SPY/QQQ**
(tier 1) with the pullback mapping of its six setups:

- **Dip buy** = king-node rejection at the **put wall** (hold/reclaim, never
  the first touch)
- **Momentum short** = **flip break** or **air-pocket run** below
- **Reversal long** = **flip reclaim** — the highest-quality late-day play

Use heatseeker's entry gates (RVOL ≥ 1.4, index alignment, map confidence,
calendar windows), its contract standard (0–3 DTE, 0.45–0.55Δ, spread ≤ 10%
of mid), its regime-matched exits, and its `== HEATSEEKER ==` output block —
add one line: `Pullback gate: PASS (criteria met: …)`.

## Session cadence (ET)

- **Premarket** — full run on overnight map; output conditional triggers only.
- **Midday (~12:00–13:00)** — re-pull spot/VIX/map, mark the plan to reality,
  update or kill it. Flag lunch-volume traps.
- **Power hour (~15:00)** — runner fates decided; nothing held past 15:45 on
  short-dated; flip-reclaim is the only fresh long worth arming.

## The watcher

`scripts/gex_watcher.py` is the user-run daemon (Polygon-fed) that fires
Discord alerts when the pullback gate arms. A pasted alert = map + gate
pre-checked: confirm VIX (the one criterion it skips), then go straight to
setup selection and risk. Threshold changes are edits to its CONFIG block.
