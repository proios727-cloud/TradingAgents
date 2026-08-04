---
type: moc
tags: [supertrades, dashboard]
---

# SuperTrades — Journal Dashboard

Map-of-content for the trading journal. Open this vault in Obsidian for backlinks, graph, and daily-note automation.

## This week
- [[Daily/2026-08-04]]

## Quick views (Obsidian Dataview — install the community plugin to render)
```dataview
TABLE account_open, account_close, day_pnl, realized, round_trips, halted
FROM #supertrades/daily
SORT date DESC
LIMIT 20
```

```dataview
TABLE symbol, class, signal_source, entry_price, exit_price, pnl, outcome
FROM #supertrades/trade
SORT entry_time DESC
LIMIT 30
```

## Reference
- Rulebook: [[../supertrades-v3]]
- Engine: `supertrades/engine/` (orchestrator, reporter = single guardrail gate, ops = reliable-ops)
- Reflections log: `~/.claude/skills/financial-evolution/reflections.json`

## How entries get here
- The loop calls `supertrades/engine/journal.py` to append the day's reconcile/cycle/fill lines into `Daily/<date>.md` and to stamp a `Trades/<contract>.md` note on each fill.
- You (or the engine) fill the **EOD review** each afternoon — that reflection is the point of the vault.
