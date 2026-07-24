# Claude + Robinhood Agentic — human-gated single-leg options (0DTE index focus)

*Deep-research synthesis, 2026-07-23. 24 sources, 109 extracted claims, adversarially verified. Confidence tags: **[H]** high / **[M]** medium / **[?]** unconfirmed-or-conflicting.*

---

## TL;DR — the one thing that matters

**Robinhood does *not* enforce a per-order human-approval gate. You must enforce it on the Claude side.** Robinhood's agentic layer gives you a dedicated ring-fenced account, per-trade push notifications, an activity feed, and a one-tap disconnect — plus an *optional* order-preview control — but the agent **can** be configured to place trades with no per-order confirmation, and Robinhood explicitly disclaims all supervision and responsibility. So "my final entrance is required" is a property **you build**, not one Robinhood guarantees. The good news: your SuperTrades architecture (dry-run default, single deterministic risk gate, human approval, kill switch, audit log) is *exactly* the pattern every primary source independently recommends.

---

## 1. What Robinhood's agentic MCP supports for options today

- **It exists and it's live for options.** Robinhood Agentic Trading launched in beta **May 27, 2026** via Robinhood's own MCP server (`https://agent.robinhood.com/mcp/trading`), officially connecting to Claude. It launched **equities-only** with options "coming soon" — but **options have since rolled out** and are still reaching all users. *(Confirmed directly: this session exposes the live options tools below.)* **[H]**
- **Options toolset** (single-leg only — **no spreads/multi-leg**): **[H]**
  - `get_option_chains`, `get_option_quotes`, `get_option_positions`, `get_option_orders`
  - `review_option_order` — **pre-trade preview / dry-run** (validate an order without placing it)
  - `place_option_order` — the live placement tool
  - `cancel_option_order`
  - `get_option_level_upgrade_info` — returns an *apply* link; the agent **cannot** grant itself options access
- **Approval level:** single-leg long calls/puts = **Robinhood Level 2**. Index options carry extra restrictions (e.g., no covered calls on index). **[H]**
- **Account model:** a **separate, dedicated "agentic" account** (self-directed individual, not IRA), funded independently — that funding cap *is* your budget guardrail. The agent can only *trade* there, but on connect it gets **read access to all your Robinhood accounts** (positions, balances, history, account numbers). Setup/OAuth is **desktop-only**. **[H]**
- **No separate paper account** in the RH MCP — but `review_option_order` gives you a genuine preview step, and you build your own sim/dry-run layer client-side (you already have `PaperBroker` + `dry_run`). **[M — one blog says "real money only"; reconciled by the review tool]**
- **Sizing fact:** 1 contract = 100 shares, so a $2.00 premium = $200 buying power. Robinhood's own education recommends **risking ≤ 2–5% of account per options trade** — a broker-endorsed anchor that matches your 2.5%/$1k gate. **[H]**

## 2. Best Claude ↔ Robinhood architecture for a human-gated workflow

Division of labor that every source converges on:

```
Claude (analysis)                      Robinhood MCP (data + execution)
─────────────────                      ────────────────────────────────
scan / signal / GEX+flow read          get_option_chains / _quotes / _positions
size against risk gate  ───────────▶   review_option_order   (preview, no fill)
                                              │
                        ┌─────────────────────┘
                        ▼
              ★ HUMAN ARMS HERE ★   ← you enforce this, client-side
                        │
                        ▼
                                       place_option_order   (only after human OK)
manage exits (trail/stop) ─────────▶   place_option_order (close) / cancel_option_order
```

**Order lifecycle:** signal → **deterministic risk gate** → contract select → `review_option_order` (preview exact params) → **human arm** → `place_option_order` → manage exits. This is your engine's `run_cycle` almost verbatim.

**How to actually enforce the human gate in Claude (this is the crux):** **[H]**
- Put **only read/analysis tools on an allowlist** (`get_option_chains`, `get_option_quotes`, `get_option_positions`, `review_option_order`). **Never** put `place_option_order` / `cancel_option_order` on a bare allow rule — an allow rule *silently skips* the `canUseTool` human callback.
- Force the placement tool to **always prompt**, three redundant ways (defense in depth):
  1. `canUseTool` callback → human approve/reject before the call runs.
  2. A **`PreToolUse` hook** scoped to `mcp__Robinhood_Trading__place_option_order` — hooks run **first** and a hook `deny` holds **even in bypass mode**. This is your non-skippable gate + kill switch.
  3. `_meta["anthropic/requiresUserInteraction"]` on the tool (Claude Code ≥ 2.1.199) forces fall-through to the callback even if an allow rule matches.
- Precedence is **deny > defer > ask > allow** — layer guardrails knowing the most restrictive wins.
- **Never** run the trading agent in `bypassPermissions` or `acceptEdits` mode.
- **`PostToolUse` hook → append-only audit log** (one JSON line per call, full params + timestamp). You already have `DecisionLog`.

## 3. Human-in-the-loop safety best practices (verified)

- **OWASP MCP guidance (primary):** *require explicit human confirmation for financial/destructive tool calls; never auto-approve.* The confirmation UI must show **full tool-call parameters, not a summary name**, and must **not be bypassable by LLM-generated text**. Log every invocation with params/context/timestamp; alert on abnormal call frequency; use least-privilege short-lived scoped tokens + per-session rate limits. **[H]**
- **Deterministic gate > probabilistic guardrails (primary + blog).** Confidence scores, output filters, and "LLM-as-judge" **structurally fail** as safety mechanisms — a well-formed hallucinated action (wrong ticker/contract) is indistinguishable from a correct one to a probabilistic filter. You need a **binary admissibility allowlist** gate before any action touches production. *This is precisely your `risk_governor` — a single deterministic gate. The research strongly validates that design choice.* **[H]**
- **Treat all tool/market responses as untrusted** — MCP tool descriptions, schemas, and returns are a **prompt-injection surface** ("tool poisoning"); malicious/garbled market data could steer the model. **[H]**
- **Cash-account / T+1 / PDT:** options proceeds settle T+1; never buy with unsettled cash (you already model `settled_cash`). PDT applies to margin accounts making 4+ day trades in 5 days — 0DTE scalping is inherently day-trading, so mind the ≥$25k PDT floor or use a cash account and respect settlement. **[M — general brokerage rules, not RH-agentic-specific]**
- **Position sizing / daily loss:** broker-endorsed 2–5%/trade; your −2R daily halt, red-day half-size, and press-from-booked-profit rules are consistent with best practice. **[H]**

## 4. Risks, failure modes, limitations

- **The academic base is weak (arXiv:2605.19337, "Agentic Trading: When LLM Agents Meet Financial Markets"):** of 19 LLM-trading studies, **only 1 models transaction costs, 0 reach top-tier reproducibility.** Published LLM-trading returns are *largely unverified and likely overstated* once real execution frictions are added. Treat any "AI trading returns" claim (including flashy backtests) with heavy skepticism. **[H]**
- **Hallucinations propagate through agent loops** — one bad fact/tool output cascades through later steps. **[H]**
- **LLM rationales ≠ true reasoning** — you cannot trust the model's stated "why" as the basis for approving a trade; approve on the **numbers and params**, not the narrative. Auditability requires grounded, time-stamped tool calls + data snapshots, not the model's story. **[H]**
- **0DTE execution realism:** fills depend on price proximity to the ask; **mid/mark may not fill**; no bids → mark shows $0.01. Tight spreads exist **only in liquid hours** — half-days/holidays bring gamma pinning, morning head-fakes, final-hour gamma acceleration, and violent whipsaws. Your spread guard (≤10% of mid) and liquid-hours windows matter. **[H]**
- **Robinhood disclaims everything** — it does **not** supervise, monitor, or audit agents; you assume all risk; your data leaves RH's security perimeter once shared with the AI provider. A practitioner running it live judged the beta "more likely to lose money than make it." **[H]**
- **Regulation is unsettled:** no new SEC/CFTC/FINRA rules specific to agentic trading; existing tech-neutral rules apply. **FINRA's 2026 report flagged autonomous AI without human validation as an emerging risk**, and House Democrats pressed the SEC (July 31, 2026 deadline). **Liability for an unintended agent trade is legally unresolved.** This is itself an argument for keeping your human gate. **[H]**

## 5. Concrete recommendations for *your* build

1. **Keep human-arm mandatory in code, not config.** Enforce it with a `PreToolUse` hook on `place_option_order` + `canUseTool` + `requiresUserInteraction` — belt, suspenders, and a second belt. Don't rely on Robinhood's optional preview.
2. **Allowlist read tools; gate write tools.** Auto-approve `get_option_*` + `review_option_order`; always-prompt `place_option_order` / `cancel_option_order`.
3. **`review_option_order` before every `place_option_order`** — preview the exact contract, qty, and limit; show the operator full params, not a summary.
4. **Your `risk_governor` is the deterministic admissibility gate** the literature says you need — keep it the single gate, keep it binary, never let a confidence score substitute for it.
5. **Audit every call** via a PostToolUse hook into your append-only `DecisionLog` (grounded, timestamped) — the only trustworthy record.
6. **Fund the agentic account with only what you'll risk** — the account balance is a hard budget wall RH actually enforces.
7. **Exits can be less-gated than entries** (a blocked stop-loss is dangerous) — which is exactly your `require_exit_approval=False` while `require_entry_approval=True`.
8. **Distrust the backtest.** The research is blunt that LLM-trading performance is systematically overstated without transaction-cost/slippage modeling — bias toward paper + small live before believing any curve.

---

## Sources (selected)

**Primary — Robinhood:** agentic-trading-overview, "Robinhood is now open to agents" (newsroom), agentic-trading product page, trading-with-your-agent, basic-options-strategies.
**Primary — Anthropic / Claude Agent SDK:** permissions, hooks, mcp docs (canUseTool, PreToolUse/PostToolUse, `requiresUserInteraction`, allowedTools).
**Primary — safety:** OWASP MCP Security Cheat Sheet; OpenAI Agents SDK guardrails-approvals; arXiv:2605.19337 "Agentic Trading: When LLM Agents Meet Financial Markets."
**Practitioner/blog:** 0xnakamura (Medium), austin-starks (Medium, skeptical), ryandoser.com, trayd-mcp (GitHub), fintechlaw.ai (governance/liability), menthorq.com (0DTE illiquidity), builtin.com (kill switches), finder.com.

**Refuted/weakened by verification (do not rely on):** "a single MCP URL works out of the box with most agents"; "the documented safety model is budget-account+notifications *instead of* any approval gate"; "autonomous placement is the default." Reality is nuanced: approval is *available and configurable* but *not enforced* — hence recommendation #1.
