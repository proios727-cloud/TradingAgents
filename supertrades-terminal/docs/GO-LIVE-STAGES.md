# Go-live staging — preview → paper → tiny live → scaled

This is the deliberate ladder from "Claude previews orders" to "real money, small,
under a hard cap." Each rung has **machine-checkable limits** enforced at the tool
boundary by the PreToolUse gate (`.claude/hooks/pretrade_gate.py` →
`agent/go_live.py:decide`), *independently of* whatever the engine thinks its
config is. Climb **one rung at a time**, and only after the rung below is boring.

Why this exists: the research (see `claude-robinhood-options.md`) found that
**Robinhood does not enforce a per-order human gate** — approval is optional at
their layer. So "my final entrance is required" has to be enforced on the Claude
side. This is that enforcement, plus a staged path so a single misconfiguration
can't jump you from paper to full size.

## The ladder

| Stage | dry_run | armed | Per-entry cap | What it's for |
|-------|:-------:|:-----:|---------------|---------------|
| `preview` (default) | ✓ | ✗ | — (no orders) | Analysis + `review_option_order` only. Nothing can be placed. |
| `paper` | ✓ | ✗ | — (no orders) | Full decision path on the `PaperBroker`. Still no live order. |
| `tiny_live` | ✗ | ✓ | **1 contract, ≤ $75** | Real money, deliberately tiny. Prove fills, slippage, and the arm flow are real. |
| `scaled` | ✗ | ✓ | ≤ $1,000 (risk gate governs) | Sizing handed back to `risk_governor` (2.5%/$1k). Only after `tiny_live` is boring. |

The gate **never auto-approves a live entry**: a permitted entry is surfaced to
you as an *ask* (with the full order shown); a cap/kill/shape violation is a hard
*deny*. **Closes and cancels are never blocked** — you can always get flat.

## Operating it

```bash
cd supertrades-terminal

python -m agent.go_live status            # where am I? (stage, kill state)
python -m agent.go_live set paper         # climb one rung
python -m agent.go_live set tiny_live     # real money, tiny cap
python -m agent.go_live kill "reason"     # ENGAGE kill — denies all new entries now
python -m agent.go_live clear-kill        # stand down
```

State lives in `supertrades-terminal/.supertrades/` (git-ignored, per-machine):
`stage.json`, a `KILL` flag file, and `audit.jsonl` (every Robinhood tool call,
appended by the PostToolUse hook). No stage file → **preview** (fail-safe).

## Recommended progression (don't skip)

1. **preview** — let it scan and `review_option_order` only. Confirm the contracts
   and previews look sane against the terminal/GEX read.
2. **paper** — run full cycles on the `PaperBroker`. Watch the decision log; confirm
   the risk gate, trailing stop, and (if on) convexity picks behave.
3. **tiny_live** — fund the Agentic account with only what you'll risk. One
   contract, ≤ $75. **`review_option_order` → eyeball the gate's echoed params →
   arm.** Do this for *days*, not trades, until fills and slippage hold no surprises.
4. **scaled** — only now hand sizing to the risk governor.

## Hard rules (the research, distilled)

- **Distrust the backtest.** LLM-trading performance is systematically overstated
  when transaction costs/slippage aren't modeled (1 of 19 studies modeled costs).
  Believe *live tiny fills*, not a curve.
- **Approve on the numbers, not the narrative.** An LLM's stated reasoning may not
  reflect its actual decision — the gate shows you the exact contract/qty/price;
  arm on that.
- **The gate is deterministic, never a confidence score.** Caps are dollars and
  contracts and a kill file — the only kind of guardrail that holds against a
  well-formed hallucination.
- **Never put `place_option_order` on an allow rule** — an allow rule silently
  skips the human callback. Keep it in `ask` + the PreToolUse gate.

## Operator notes (from the safety review)

- **Keep the engine's `RuntimeConfig` and the stage file in agreement.** The
  hook-layer stage (`go_live.py`) and the engine's `dry_run`/`armed` config are
  separate switches on separate layers — the gate does not push the stage into
  `RuntimeConfig`. Don't run the engine armed while the stage says `preview`, or
  vice-versa. The stage file is the *outer* wall; the engine config is the inner
  one. When in doubt, the gate still fail-closes.
- **The stage caps apply to buy-side entries only.** Sell/close and cancel always
  fall through to a human "ask" (so you can always get flat) — they are not
  premium/contract-capped. The strategy is long-only, so this is intended.
- **The audit log is best-effort.** A full/unwritable disk drops audit lines
  without halting trading. Periodically confirm `.supertrades/audit.jsonl` is
  actually growing.
