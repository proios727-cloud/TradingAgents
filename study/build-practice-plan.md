# Build Practice Plan — staged, each stage ships something

Rule for every stage: define "done" before starting; validate with a tool, not by eyeballing.

---

## Stage 0 — Beginner exercise (≈1 evening)
**Goal:** fluency with the loop, zero MCP.
- [ ] Install Claude Code, auth, open any Python repo (this one works)
- [ ] `/init` → read the generated CLAUDE.md → add 3 real conventions you care about
- [ ] In plan mode: ask for a small refactor or test addition; review plan; approve; run tests
- [ ] Practice: `Esc` interrupt, `/compact`, Shift+Tab mode switching
- **Done when:** one merged commit produced end-to-end via plan→approve→validate.

## Stage 1 — First useful workflow (skill, no MCP)
**Goal:** encode a repeated task as a skill.
- [ ] Pick something you do weekly (e.g. "summarize a backtest run into a standard report")
- [ ] Write `.claude/skills/backtest-report/SKILL.md`: trigger description, steps, output template
- [ ] Add one hook: run `pytest` (or a linter) automatically after edits — deterministic guardrail
- [ ] Run the skill on 3 different inputs; tighten the template where outputs drift
- **Done when:** invoking the skill produces a correctly-formatted report with zero follow-up prompts.

## Stage 2 — First MCP setup (consume, don't build)
**Goal:** wire an existing server correctly and feel the cost.
- [ ] Pick from the hierarchy: GitHub MCP, or Chrome DevTools MCP (Torti's), or a market-data server
- [ ] `claude mcp add <name> -- npx -y <package>` (project scope if repo-relevant)
- [ ] Verify via `/mcp`; smoke-test one forced tool call
- [ ] Note context usage with server on vs off; then `claude mcp remove` anything idle
- **Done when:** one task completed that was impossible without the server, and you've removed an unused server on purpose.

## Stage 3 — First custom MCP server (Python, this repo)
**Goal:** Talebi's pattern applied to trading data.
- [ ] `uv init trading-mcp && uv add "mcp[cli]"`
- [ ] Wrap 2–3 existing TradingAgents/yfinance functions:
      `@mcp.tool get_ohlcv(ticker, days)`, `@mcp.tool get_fundamentals(ticker)`,
      `@mcp.resource watchlist` (CSV → markdown)
- [ ] Fat docstrings (description/args/returns); prompts in separate .md files
- [ ] `mcp.run(transport="stdio")` → `claude mcp add trading -- uv run server.py`
- [ ] Test: "compare 30-day momentum of my watchlist" must trigger correct tool calls
- **Done when:** Claude answers a market question using only your tools, with correct arguments, three prompts in a row.

## Stage 4 — First multi-step real-world workflow
**Goal:** small agent team + validation loop on a real deliverable.
- [ ] Define 2 subagents in `.claude/agents/`:
      **analyst.md** (may use trading-mcp; produces `analysis/<date>-<ticker>.md` from a template)
      **risk-reviewer.md** (read-only; checks analysis against a risk checklist, writes verdict)
- [ ] Routing rule in CLAUDE.md: every analysis must pass risk review before being marked final
- [ ] Hook: block writes outside `analysis/`; never allow order-execution paths
- [ ] Run the pipeline on 3 tickers; fix role overlap and template drift as it appears
- [ ] Optional extension: n8n-mcp to schedule the pipeline, or a Routine/cron for a daily run
- **Done when:** one command ("run today's analysis on X") produces analyst output + risk verdict as files, unattended.

---

**Escalation principle (from all sources):** context → skill → existing MCP → custom MCP → orchestration. Never jump a level while the previous one still solves the problem.
