# SuperTrades v3 — Orchestrated Cycle Engine

Fan-out / layered fan-in rewrite of the per-cycle loop (2026-07-23). The old
serial pipeline (`scalp rails → position discovery → flow watch → dashboard
republish`) is replaced by:

```
discovery (state.json) ──► fan-out: one concurrent node per unit
                             ├─ ticker_signal   × len(universe)
                             ├─ gex_map / whale_flow / pullback_gate × 3 per index underlying
                             ├─ position_exit   × len(positions)
                             └─ candidate_entry × len(watchlist)
                           ──► layered fan-in (batches of 30, recursive)
                           ──► final reporter: EVERY guardrail, exactly once
```

## Why
- **Speed**: all ticker/underlying/position/candidate checks run concurrently
  instead of serially, so cycle time stays flat as the watchlist grows.
- **Auditability**: guardrails (daily halt −$60, max 1 auto-entry/day,
  settlement suppression, BP floor, per-trade 40% cap, delta/spread/OI floors,
  time windows, already-held, index-0DTE-requires-GEX-gate, alert-only
  routing, class time stops, churn guard, DND push precedence) live in ONE
  file — `engine/reporter.py` — instead of scattered through a pipeline.
  Nodes only observe and propose; a static test enforces the separation.

## Layout
| File | Role |
|---|---|
| `engine/orchestrator.py` | generic engine: `Node`, `fan_out`, `layered_fan_in`, `run` |
| `engine/nodes.py` | six pure async node functions (proposals only, no guardrails) |
| `engine/discovery.py` | builds the node list from `state.json`; node-count contract |
| `engine/reporter.py` | summarizer + **the single guardrail gate** + console payload |
| `engine/run_cycle.py` | CLI entry; synthetic snapshot builder for offline runs |
| `engine/tests/` | stage-gate tests (unittest, stdlib only) |
| `supertrades-v3.md` | durable rulebook — wins on any conflict |
| `state.json` | live ledger: positions, watchlist, counters, mode |
| `pages/` | console + index-desk dashboards (layout unchanged by this rewrite) |

## Run it
```bash
# offline health check (synthetic snapshot; what a rebuilt session runs first)
python -m supertrades.engine.run_cycle --selftest

# a real cycle: the loop's MCP fetch step writes snapshot.json, then
python -m supertrades.engine.run_cycle \
    --state supertrades/state.json --snapshot /path/to/snapshot.json
# → prints JSON: console payload, actions (exits/entry/alerts), guardrail audit

# tests
python -m unittest discover -s supertrades/engine/tests -v
```

## Broker data path (important)
There is **no `robin_stocks` module in this repo and no Python login flow** —
the project's one authenticated Robinhood path is the session's Robinhood MCP
server. The engine therefore never calls the broker: the loop's fetch step
gathers a read-only snapshot via MCP, the engine computes the report, and the
loop executes the report's actions via MCP (review→place, Agentic acct
902341866 only). This satisfies "do not duplicate Robinhood auth" by design.

## Invariants (tested)
- Node count = `len(universe) + 3·len(index tickers) + len(positions) + len(watchlist)`
- A halted account (`day P&L ≤ −$60`) suppresses **every** entry recommendation
  regardless of node output, while exits stay live
- Nodes emit identical proposals under a halted account (no guardrail leakage)
- No guardrail constant exists outside `engine/reporter.py` (static check)
- A failing node never sinks the cycle; fan-in recurses past 30 items
- Margin-account (812234458) positions only ever produce alerts, never orders
