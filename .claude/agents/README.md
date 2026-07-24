# SuperTrades agent team

Project subagents for this repo. Claude Code auto-discovers every `*.md` here and
delegates to one when a task matches its `description`, or you can call one by
name ("have the risk-guardian review this diff").

| Agent | Model | Owns | Call it when |
|-------|-------|------|--------------|
| **risk-guardian** | opus | Trading safety invariants in `supertrades-terminal/agent/` | Before shipping anything that sizes, places, arms, or gates real orders |
| **quant-strategist** | opus | Signal edge, sizing math, backtests, GEX/flow logic | Designing/tuning a strategy, building or fixing a backtest, sizing decisions |
| **python-reviewer** | sonnet | The `tradingagents/` LangGraph flow, provider clients, schemas, tests | After writing/changing Python, or a general cleanup pass |
| **terminal-ux** | sonnet | The `.dc.html` UI, `_ds` design system, dc-runtime wiring | Changing what the terminal shows or how it looks |

## How they hand off

The edge and the safety of the edge are deliberately split:

- **quant-strategist proposes, risk-guardian clears.** Any change to live
  sizing/exit/gate logic goes through the guardian before it commits — the
  strategist designs the edge, the guardian proves it can't hurt you.
- **python-reviewer** cleans and verifies the Python around both, and hands any
  change that touches a risk gate to **risk-guardian** rather than signing off
  itself.
- **terminal-ux** only reads `data.js`; it never changes trading behavior, so it
  ships UI on its own — but it keeps the `SIMULATED DATA` labeling honest.

The through-line: **honest metrics, inert-by-default execution, one risk gate,
deterministic sims, fully-offline terminal.** Every agent enforces its slice of
that.
