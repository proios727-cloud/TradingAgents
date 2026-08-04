# SuperTrades agent team

Project subagents for this repo. Claude Code auto-discovers every `*.md` here and
delegates to one when a task matches its `description`, or you can call one by
name ("have the risk-guardian review this diff").

## Engineering desk

| Agent | Model | Owns | Call it when |
|-------|-------|------|--------------|
| **risk-guardian** | opus | Trading safety invariants in `supertrades-terminal/agent/` | Before shipping anything that sizes, places, arms, or gates real orders |
| **quant-strategist** | opus | Signal edge, sizing math, backtests, GEX/flow logic | Designing/tuning a strategy, building or fixing a backtest, sizing decisions |
| **python-reviewer** | sonnet | The `tradingagents/` LangGraph flow, provider clients, schemas, tests | After writing/changing Python, or a general cleanup pass |
| **terminal-ux** | sonnet | The `.dc.html` UI, `_ds` design system, dc-runtime wiring | Changing what the terminal shows or how it looks |

## Market desk

Diverse, strategy-driven financial professionals. Advisory only: they analyze,
price, and plan — none of them edits code or places orders, and none gives
buy/sell instructions. All of them work from live data (fetched via web or
connected tools), state their assumptions, and report honest metrics.

| Agent | Lens | Call it when |
|-------|------|--------------|
| **macro-strategist** | Top-down: rates, inflation, dollar, sector rotation | A decision depends on the market regime or the macro calendar |
| **fundamental-value-analyst** | Bottom-up: balance sheets, cash flow, valuation ranges | "What is this company worth" / is a long-term hold's thesis intact |
| **technical-momentum-trader** | Price action: trend, levels, volume, R-multiples | Timing an entry/exit, placing a stop, building a trade plan |
| **volatility-options-strategist** | Vol: IV vs RV, Greeks, theta, structure selection | Pricing any option trade, 0DTE expectancy, earnings vol events |
| **portfolio-risk-officer** | Exposure: concentration, correlation, Kelly sizing, drawdown | Before sizing anything; when one theme dominates the book |
| **behavioral-finance-coach** | Discipline: tilt, escalation, rule compliance | After big win/loss days; when frequency or size creeps |
| **wealth-planner** | Household: cash flow, debt strategy, net worth, capital budgets | "Where should the next dollar go" — questions bigger than a trade |

The market desk's through-line mirrors the engineering one: measured edge or no
size (negative Kelly ⇒ zero), risk is signed off at the book level by the
portfolio-risk-officer, and process compliance is graded by the coach —
outcomes are variance until the log says otherwise.

## How the engineering desk hands off

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
