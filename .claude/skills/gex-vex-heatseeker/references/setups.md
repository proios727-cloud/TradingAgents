# The Six Setups — mechanics, triggers, invalidations

Each setup below is a claim about *what dealers are being forced to do*. If you
cannot state that mechanism in a sentence, you do not have the setup — you have a
chart pattern with a gamma vocabulary bolted on.

Contents: 1. Flip break · 2. Flip reclaim · 3. Gap fill · 4. King-node rejection ·
5. Air-pocket run · 6. Hedge exhaustion · 7. Conflict resolution

---

## 1. Flip break (continuation short)

**Mechanism.** Above the flip, dealers are long gamma and damp every move. Below
it they are short gamma: they must sell as price falls and buy as it rises. The
same selling that was absorbed an hour ago now gets amplified. The flip is not a
support level — it is the boundary where the market's shock absorber inverts.

**Trigger.** A 5-minute close below the flip, then a *failed retest* — price
returns to the flip from below and is rejected. Entering on the first break is
the common error; flips are probed constantly and most probes fail.

**Confirmation.** RVOL ≥ 1.4 on the breaking bar. Index aligned lower. Ideally
an air pocket sitting immediately below — that is what turns a break into a run.

**Target.** Next significant node below, or the far side of the air pocket.

**Invalidation.** 5-minute close back above the flip. This is fast and it should
be — being wrong about a regime boundary is expensive.

**Best conditions.** Aligned vanna, morning session, flip within 0.5% of spot so
the transition is live rather than theoretical.

---

## 2. Flip reclaim (continuation long)

**Mechanism.** The mirror, and the higher-quality of the two. Price climbs back
above the flip and dealer flow switches from amplifying to damping. Downside
momentum loses its engine. The reclaim tends to be stickier than the break
because the new regime actively suppresses the move that would invalidate it.

**Trigger.** 5-minute close above the flip, then a *hold* — a pullback that finds
support at or above the flip rather than slicing back through.

**Confirmation.** RVOL ≥ 1.4. Index aligned higher. Best after a genuine flush,
when the reclaim represents exhausted selling rather than drift.

**Target.** Call wall or the next node above. In +GEX the call wall is a real
ceiling — dealers sell into it — so take profit there rather than through it.

**Invalidation.** 5-minute close back below the flip.

**Best conditions.** Post-flush, aligned vanna, late morning or the 14:00–15:00
window. This is the highest-expectancy setup in the model.

---

## 3. Gap fill (mean reversion, positive gamma only)

**Mechanism.** Overnight gaps leave price displaced from where the bulk of open
interest sits. In positive gamma, dealer hedging pulls price back toward the
dense part of the board — often prior close, often the king node. The fill is
dealer flow, not sentiment.

**Regime requirement — the one that matters.** This setup is **only valid in
+GEX**. In negative gamma the same gap *extends* rather than fills, because
dealers amplify the displacement instead of absorbing it. Running a gap fill in
−GEX is the most reliable way to lose money with this model. Check the regime
before the pattern, every time.

**Trigger.** Gap of ≥ 0.4% with spot in +GEX, and the first 15-minute range
failing to extend the gap direction. Enter on the reversal back toward the fill
target, not at the open.

**Target.** Prior close, or the king node if it sits between spot and the prior
close — dealers defend the node harder than they defend a number on a chart.

**Invalidation.** Gap extends 0.3% beyond the opening extreme, or the regime
flips to −GEX mid-move. The second is the dangerous one: a gap fill that turns
into a −GEX trend has no natural stop.

**Note on partial fills.** Most gaps fill partially. Take the majority of the
position at the first significant node, not at the theoretical full fill.

---

## 4. King-node rejection (fade, positive gamma)

**Mechanism.** The king node is the strike with the largest absolute gamma. In
+GEX it acts as a magnet on approach and a wall on contact: dealers hedge
hardest there, so price stalls. The fade is a bet on that hedging holding.

**Trigger.** Price tags the king node and stalls — two consecutive 5-minute bars
failing to extend past it, ideally with a rejection wick.

**Confirmation.** +GEX confirmed. Aligned vanna. Volume *fading* on approach,
not building — building volume into a node is the tell that it is about to break.

**Target.** Middle of the board, or the next node back toward the flip.

**Invalidation.** 5-minute close beyond the node with rising volume. A node that
breaks on volume often becomes an air-pocket run in the opposite direction, so
be ready to flip the read rather than fight it.

**Do not run this in −GEX.** Nodes get sliced in negative gamma.

---

## 5. Air-pocket run (momentum, negative gamma)

**Mechanism.** An air pocket is a gap in the strike ladder where no strike carries
meaningful gamma. There is nothing for dealers to hedge against, so nothing slows
price down. Combined with −GEX amplification, this is where the fastest and
largest moves on the board happen.

**Trigger.** Price enters the pocket with momentum in −GEX, having broken the
node at the near edge on RVOL ≥ 1.4.

**Target.** The node at the far edge. Do not target a percentage — target the
structure. The whole point is that there is nothing in between.

**Stop.** Back inside the broken node at the near edge. Pockets are fast in both
directions; a failed pocket entry retraces hard.

**Why this is the max-gain setup.** It has the best ratio of distance-to-target
versus distance-to-invalidation on the whole board, because the target is defined
by structure rather than hope. It is also the setup most worth a runner — see
`exit-policy.md`.

**Caveat.** Pockets are least reliable near OPEX, when pinning dominates.

---

## 6. Hedge exhaustion (reversal, deep negative gamma)

**Mechanism.** In a −GEX push, dealers hedge continuously in the direction of the
move. That hedging is finite: once they are hedged, the mechanical flow stops.
Price has overshot the board with no remaining forced flow behind it, and it
snaps back. This is the "dealer hedge exhaustion" reversal.

**Trigger.** All of: price extended past the last significant node with no node
ahead; vanna **divergent** from gamma (the tell that the flows have stopped
reinforcing); momentum decelerating across consecutive 5-minute bars; RVOL
rolling over from a spike rather than holding.

**Target.** Back to the last significant node, then the flip.

**Invalidation.** A new momentum leg on rising volume. This setup fights an
active trend, which makes it the most dangerous of the six.

**Discipline.** Counter-trend and easy to enter early. Require *decelerating*
momentum — not merely extended price. "It has gone too far" is not a trigger.
This setup never gets full size and never gets a runner.

---

## 7. When two setups conflict

Two rules resolve nearly every conflict:

1. **Regime wins over pattern.** A gap-fill pattern in −GEX is not a gap fill.
   A node-rejection in −GEX is not a rejection. Classify the regime first, then
   look for setups that belong to it.
2. **Transition beats state.** If price is actively crossing the flip, the flip
   trade supersedes any pin, fade or fill setup — the board is mid-repricing and
   the levels a state-based setup depends on are the ones being invalidated.

If two setups in the same regime genuinely conflict — say price sits exactly on
the king node with an air pocket just beyond — do not pick. State both triggers
and which one arms which direction, and wait for the resolution. Sitting on a
level is not a setup; leaving it is.
