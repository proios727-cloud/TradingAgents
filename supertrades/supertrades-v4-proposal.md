# SuperTrades v4 — proposal (consolidated from the 7/21–7/27 live run)

> Status: PROPOSAL for review. Does not replace v3 until approved. Written premarket
> Mon 7/27 after a full live week + weekend of iteration.

## 0. The one thing the week proved
The account went ~$437 → $322 (−$129 over 4 days). The ledger is unambiguous about *why*:
- **`auto_entries_used = 0` every single day.** The loop never generated or took an entry.
  Every trade was **the user's own discretionary call on the user's own PineScript signals** —
  not fed by this system or anyone here.
- The loop's only actions were **stop executions, rail management, halt enforcement, reconcile.**
- Signal **direction** was usually fine (NVDA/DIS/SPY/QQQ weren't crazy vs the tape).
  The damage was **expression + frequency**: 0DTE contracts, ~$0.30 premiums, and ~8 round-trips
  in one afternoon — each flip paying a 10–30% bid/ask spread tax. The green day (+$65) was
  fewer, planned, windowed entries.

**Conclusion → v4's core reframe:** SuperTrades is not a signal engine. It is a **discipline +
risk layer wrapped around the user's own signals.** Its job is to make over-trading and junk
expression *hard*, execute exits reliably, and turn every trade into learnable, backtestable data.

## 1. Three layers of v4

### Layer 1 — Discipline governor (the highest-leverage change)
Hard, tracked limits on the *user's* activity (the loop can't block a manual order, but it
alerts loudly, logs the violation, and refuses to assist/execute past these):

| Rule | v3 | v4 |
|---|---|---|
| Total entries/day (auto + manual) | 1 auto | **2 total**, hard alert on the 3rd |
| Round-trips/day (churn brake) | alert at 4 | **hard alert at 3**, escalating push each one after |
| 0DTE | allowed via GEX gate | **blocked** unless it's the day's *single* GEX-gated index play |
| Min DTE (single-name day-trade) | none | **≥ 5 DTE** (kill the theta-cliff + spread-heavy lottos) |
| Quality floor (entry) | delta 0.25, spread ≤10% | **delta ≥ 0.35, spread ≤ 12% of ask, premium ≥ $0.40** (so spread isn't 20% of the trade) |
| Per-trade size | ≤ 40% BP | **≤ 25% BP**, 1 contract |
| Daily halt | −$60 | keep −$60 (worked; fired both red days) |

The governor's real output each cycle: a **discipline scorecard** (entries used / round-trips /
0DTE count / quality of open expressions) surfaced in chat, so the *pattern* is visible in real time.

### Layer 2 — Reliable ops (fix what actually broke)
The `ScheduleWakeup` self-timer **stalled repeatedly** — it delayed stops and **missed the DIS 3:45
flatten** (an intended day-trade became an accidental weekend hold). v4:
- **Concentrated cron schedule** (the reshape already drafted, pending user OK): premarket, dense
  around the open, quiet at lunch, 1pm, EOD flatten window, 6pm — instead of a flat hourly ping.
- **Every heartbeat does a real broker reconcile** when state is stale, never a bare selftest.
- **A dedicated EOD-flatten trigger at 3:44** so day-trade flattens can't be missed by a stalled loop.

### Layer 3 — Knowledge + backtest (the learning loop)
- **Obsidian-ready journal** (`supertrades/journal/`): one markdown note per trade / per day /
  **per signal**, with `[[wikilinks]]` + Dataview fields. User syncs the folder into their vault.
- **Per-signal edge tracking:** each PineScript strategy = a note that accumulates its *live*
  win-rate / expectancy / avg-hold. This is how "which of my signals actually has an edge?"
  gets answered with real data instead of feel.
- **Backtest harness:** translate a PineScript strategy's entry/exit logic → Python → run vs
  historical bars (Robinhood historicals) → a signal-edge report. Separates *signal quality*
  from *execution noise*. (Requires the user to share a script or its rules.)

## 2. Build order (proposed)
1. **Today:** resolve the carried DIS 105c at the open (flatten belatedly per the day-trade rule,
   or the user keeps it as a declared swing); get back to a clean flat baseline.
2. **Layer 1 (discipline governor)** — biggest bang; encode the table above into `engine/reporter.py`
   + a new discipline-scorecard console section. Tests for each new limit.
3. **Layer 2 (reliable ops)** — apply the concentrated cron + heartbeat-reconcile + 3:44 flatten trigger.
4. **Layer 3a (Obsidian journal)** — generate per-trade/day/signal markdown; wire into the cycle.
5. **Layer 3b (backtest)** — on the user handing over a PineScript, build the Python replica + report.

## 3. What v4 does NOT try to do
- It does **not** generate its own entry signals. The user's PineScript stays the signal source.
- It does **not** promise to stop a manual order — it makes the cost of over-trading *visible and
  loud* and refuses to *assist* past the governor limits.
- A prettier journal is **not** a discipline fix. Layer 1 is the discipline fix; Layer 3 is for learning.
