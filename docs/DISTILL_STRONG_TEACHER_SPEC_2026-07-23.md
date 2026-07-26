# Distill-strong-teacher — SPEC (2026-07-23)

> **STATUS: EXECUTED + CONFIRMED 2026-07-23 → 2026-07-26. The EQUAL-SIMS strength claim is
> CONFIRMED on two disjoint bands (pooled +35.7 ± 12.3 elo, winrate z +2.90, margin z +2.12 over
> 800 deck-paired games). ⚠️ DEPLOYABILITY IS A SEPARATE QUESTION AND CURRENTLY POINTS NEGATIVE —
> the candidate costs 4.3–5.5× per move, and at CL-060's own exchange rate a champion given equal
> wall-clock would gain ~+29 to +34 elo, cancelling the edge. An UNLOADED cost probe decides it.
> NOT promoted; champion + `governance/PRODUCTION.yaml` UNTOUCHED. → CL-067 (Supported/high).**
>
> **CONFIRMATION CELL (band 56e9, n=400 deck-paired, 200 decks, 0 deck_hash mismatches):
> 213W-7D-180L, winrate 0.5413 (z +1.65), elo +28.7 ±17.4, margin +1.18 pts/deck (paired z +1.28).**
> Weaker than the gate but **statistically indistinguishable from it** (elo diff +14.1 ± 24.7,
> z = 0.57) ⇒ winner's-curse shrinkage of a selected first look, **not** the reversal pattern that
> killed c=3 "+47", anchor-fraction "+39" and the flywheel "+88.7" (that one flipped sign to −3.5).
> Neither cell clears 2σ alone; the 2σ result is **pooled**, and pooling was not pre-registered.
>
> **Historical note — the original gate banner read:** GATE = POSITIVE, +42.8 elo at deploy cost,
> a SINGLE SCREEN at the edge; NOT promoted, confirmation on a fresh band owed.
> Gen: 2,400 teacher games at the full 4× budget (k8×1376), 4 chunks, all screened HEALTHY.
> Gate (n=400 deck-paired, band 52e9, deploy budget k4×688 exact-K2): **221W-7D-172L, winrate
> 0.5613, elo +42.8 (1σ ±17.5), winrate z +2.45; deck-paired margin +1.595 pts/deck, paired z
> +1.71** ⇒ ~86% retention of the teacher's +49.85 edge at ¼ its budget. The win-count statistic
> clears 2σ, the margin statistic does not — see DECISIONS 2026-07-26 and **CL-067**
> (Provisional/medium). Champion + `governance/PRODUCTION.yaml` UNTOUCHED.
> **Next step: confirmation cell on a fresh seed band (n≥200) before any promotion.**
> Cell 2 (retention % vs the teacher itself, n=200 band 53e9) was specced but NOT run.

**Status: GEN RUNNING (launched 2026-07-23 23:26 EDT).** Joshua's go: "ok let's try to distill.
work stealing across boxes. w16 each for gen. eval might be higher w." Executed by reusing
`scripts/distill_flywheel/run_distill_sighted.sh` with the teacher config: `TAG=distill_strong_20260723
KDETS=8 CHAMP_SIMS=1376 GAMES=600` ×4 chunks, `SEED_BASE=50e9`, W16 local + W16 laptop shared-claim,
`STALL_GEN=50` (teacher games ~35–40 min — the 15-min default watchdog would death-loop on the silent
start window). Corpus target = 2,400 games (~330k positions), matching the stage-1 corpus that produced
the faithful tie. Live state → STATUS.md; data `/mnt/c/carc-shared/distill_strong_20260723/`.
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
