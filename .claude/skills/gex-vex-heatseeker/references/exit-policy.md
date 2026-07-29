# Exit policy — where the gains actually come from

The request behind this skill was "max gains." This file is the honest answer to
that, and the honest answer is not "trade more."

## The central idea

On a structural model, the exit is not a risk-management afterthought bolted onto
the entry — it *is* most of the edge. Two traders can take identical signals at
identical prices and one compounds while the other bleeds, purely on exit policy.

The reason is that this model already tells you whether moves extend or revert.
That is literally what the gamma regime *is*. Ignoring it at the exit means
throwing away the most valuable thing the map produced.

## Regime-conditional exits

**Positive GEX — take profit fast, at nodes.**

Dealers are damping the move. A position up 40% will give much of it back,
because suppressing that move is precisely what dealer hedging is doing. This is
the mechanism working as designed, not variance.

- Scale 50% at the first node in your favour.
- Complete the exit at the target node.
- **No runners.** A runner in +GEX is a bet against the regime you just
  identified.
- If price stalls at a node for two bars without extending, take the rest. In a
  pinning regime, stalling is the whole story.

**Negative GEX — trail, and let it run.**

Dealers are amplifying. This is where the outsized wins live, and cutting a −GEX
winner at a fixed +30% is the most common way a good model gets turned into a
mediocre one. The distribution of returns here is genuinely fat-tailed; capping
the tail while keeping the losses caps the edge itself.

- Scale 33% at the first node to de-risk.
- Trail the remainder behind each *reclaimed* node — not a fixed percentage.
- Exit fully on a close back through the last reclaimed node, or on regime flip.
- The runner is the point. Most of the model's total return, over enough
  signals, should come from a small number of −GEX runs that were allowed to
  work.

**Air-pocket entries — widest leash on the board.**

There is no structure to stall price until the far edge. Target the far node.
Do not scale inside the pocket: scaling into empty space is paying for
protection against something that is not there. First scale at the far edge.

## Conviction tiering

Size follows setup quality, not conviction-as-a-feeling. The tiering is what makes
"max gains" compatible with survival: it concentrates capital in the small number
of setups that carry the edge, instead of spreading it evenly across everything
that technically passed.

| Tier | Requirements | Size | Runner |
|---|---|---|---|
| **A+** | Tier-1 ticker · aligned vanna · RVOL ≥ 1.8 · flip or air-pocket setup · vendor-confirmed level | Full | Yes, if −GEX |
| **A** | All gates pass, one quality factor missing | Full | Only if −GEX |
| **B** | Tier-2 ticker, or divergent vanna | Half | No |
| — | Anything below | No trade | — |

There is deliberately no C tier. The marginal setup is where accounts die: it
feels like participation and prices like a coin flip after spread. Refusing it is
not passivity — over a month it is probably worth more than any single winner.

## The stop is structural, not a percentage

A percentage stop on an option is a stop on the *premium*, which moves with vol,
theta and spread as much as with your thesis. Stop on the **underlying level**
that invalidates the structure — the flip, the node, the pocket edge. That is the
price at which the reason for the trade stopped being true.

Keep a premium backstop at −50% as a circuit breaker for gaps and vol collapse,
but the structural level should almost always trigger first. If the premium stop
is the one hitting, the contract was too far out or the level was too far away.

## Time stops

Theta is the silent stop and 0DTE gamma cuts both ways.

- 0DTE not working within 30–45 minutes: close it regardless of P&L.
- 1–3 DTE not working by end of session: close it. Overnight gamma risk on a
  short-dated directional position is not a bet this model has an edge on.
- Everything short-dated is flat by 15:45 ET.

## What "max gains" actually decomposes into

Ranked by how much each contributes, based on how this class of model behaves:

1. **Not taking B-minus setups.** The largest single lever, and the least
   satisfying.
2. **Letting −GEX runners run.** Where the fat tail is.
3. **Taking +GEX profits early.** Prevents systematically donating back the
   damped move.
4. **Structural stops instead of premium stops.** Cuts the "stopped out then it
   worked" losses that come from noise in the premium rather than the thesis.
5. **Contract selection (gamma per theta).** Real, but smaller than the above.

Notice that three of the top four are about *restraint*. That is not a moral
point, it is what the arithmetic of the model says.

## What this policy will not do

It will not produce a smooth equity curve. A regime-conditional, runner-dependent
policy has lumpy returns by construction: many small scratches and a few large
wins. Judging it over a handful of trades will mislead — a losing week says
almost nothing, and so does a winning one. The ledger exists so the judgement
gets made on a sample large enough to mean something.
