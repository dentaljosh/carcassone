# Distill-strong-teacher — SPEC (2026-07-23)

**Status: PLANNED, not launched.** The one live learned-component thread after C0 (DEAD),
F6 (NULL), and the budget-curve extension. Approved-in-principle by Joshua 2026-07-23
("ok, so the shape would be gen at 4x, train, eval vs the champ?" → refined below).
Champion / `governance/PRODUCTION.yaml` UNTOUCHED until an eval clears the gate.

## Why this is NOT a repeat of the failed distillation

The 2026-07 distill flywheel (CL-058) distilled the **deploy champion** — which is already
*cheap*. You cannot exceed the strength of what you copy, so it capped at a **tie** (100-100-0),
wall-clock-neutral, no win possible. It then tried to *grow past* the champ via self-play
iteration; that produced no robust growth (the it16 "+88.7" was a low-sims mirage → +1.7 at
deploy depth → −3.5 fresh-deck). Dead.

**This is different because we now have a teacher that is STRONGER than deploy.** The budget-curve
extension (2026-07-23, under CL-060 reopened) found a **~+40-elo-over-deploy plateau**:
- 4× budget, best allocation **k8×1376 = 11008**: **+49.85 elo (z 3.48)** over deploy
- 8× budget, best allocation **k16×1376 = 22016**: **+35.58 elo (z 2.68)** over deploy
  (the k8×2752 8× allocation was under-determinized → +3.51 flat; allocation is critical,
  ~32-elo swing; deck-matched k16−k8 = +2.985 pts/deck z 1.71.)
- 4× ≈ 8× within cross-band noise ⇒ the curve **plateaus at ~+40 over deploy, reached by ~4×**.

So the **cheapest +40 teacher is the 4× config `k8×1376 = 11008`** (same tier as 8×, half the cost).
That teacher is +40 stronger than deploy **and** 4× more expensive. Those two facts together are
exactly what makes distillation worth doing: copy the strong-but-expensive teacher into a cheap net.

## The prize (two equivalent framings)

| framing | result if the distill retains strength |
|---|---|
| vs the **teacher** | same strength, ~4× cheaper → **wall-clock win** |
| vs the **deploy champ** | **+40 elo stronger at ~the same cost** → production upgrade |

**Even partial retention wins:** +20 of the +40 at deploy cost is still a real upgrade over the
current champion — something the last distillation (capped at a tie) could never deliver.

## The shape (ONE-SHOT distill of a FIXED teacher — NOT a flywheel)

1. **GEN** — run the FIXED teacher `k8×1376 = 11008` (fair PIMC, curve125 leaf) as self-play,
   recording the teacher's **pooled-visit policy distribution** at each move = the distillation
   target. ⚠️ Gen at the teacher's **FULL 4× budget** — the last flywheel's "¼-budget gen" would
   dilute exactly the strength we're trying to capture. This is the expensive line item (~4×
   per-move; box-days). **No teacher policy-targets are banked** — the earlier 4× cells recorded
   game *outcomes*, not visit distributions — so a dedicated gen run is required. **Scope the gen
   size (positions/games) before committing the boxes.**
2. **TRAIN** — supervised policy distillation: net **policy head** → teacher's pooled-visit
   policy (cross-entropy/KL). **Value loop SEVERED** — value stays the heuristic leaf (C0/CL-039
   killed net value; nothing to gain). Training is GPU-latency-bound, not the bottleneck.
3. **EVAL** — the net-priors agent (net policy priors + heuristic leaf + fair PIMC) **at DEPLOY
   budget (k4×688) and PRODUCTION depth**, vs the deploy champ AND vs the teacher.
   - ⚠️ **Eval at production depth, NOT k2×200.** The last flywheel's "+88.7" was a low-sims
     mirage that washed out at deploy depth (CL-058, sims-washout). Only the deploy-config eval
     counts.
   - ⚠️ **Eval at DEPLOY budget, not 4×.** The prize is teacher-strength *cheap*; evaluating at 4×
     just re-asks "do priors help at 4×" and misses the point.
   - Optionally sweep a couple of budgets (deploy, half-deploy) to find the cheapest budget that
     retains teacher strength — the EQWALL-style read, but with the strong teacher.

## Win condition
Net-priors agent at deploy cost **beats the champ** (deck-paired, production depth, n≥400). Full
retention ≈ +40; partial (+20) is still a production upgrade. If it merely ties the champ (like the
last distillation of the deploy champ did), the strong teacher's edge did NOT distill → this thread
closes and the analyzer pivot stands.

## The honest risk (the guarded prior)
The teacher's +40 edge comes from **more determinizations = better hidden-info marginalization** —
the *least-distillable* kind (a forward pass can't literally "sample 16 hidden worlds"). The net
would have to learn a policy that *implicitly encodes* the marginalized answer. Encouraging
counter-evidence: the last distillation **proved a net can faithfully copy a k4-marginalized policy**
(that's why it tied the champ). This bet asks whether it copies a k8/k16-marginalized policy — the
*same kind of thing, more of it*. Guarded, but plausible, and the asymmetric payoff (partial
retention still wins) makes it worth one clean run.

## Open design questions to settle at launch
- **Teacher config:** k8×1376 (4×, cheapest +40) is the default gen teacher. (k16×1376 8× is the
  same strength tier at 2× the gen cost — no reason to gen at 8×.)
- **Gen size:** how many teacher games/positions for a faithful policy distill? Scope from the last
  flywheel's corpus sizes, adjusted for 4× per-move cost.
- **Reuse the last flywheel's recipe** (severed value loop, strong-teacher warmstart, pooled-visit
  targets, sighted rep) EXCEPT: gen at full teacher budget (not ¼), one-shot (no iteration),
  eval at production depth only.

## Related closed threads (context)
C0/CL-065 (net can't beat the leaf's value ordering even from solver labels) · CL-058 (the flywheel
GROWTH null) · CL-039/042 (net value inert) · the EQWALL result (net-priors tie the deploy champ,
wall-clock-neutral — because the deploy champ was cheap; this teacher is not).
