# OPEN_QUESTIONS — what we most want the reviewer to resolve

This duplicates `OUTSIDE_REVIEW.md §14` in standalone form, and adds the internal
open questions we have NOT resolved. Ordered. Each has a pointer to the evidence.

## The 11 framed questions (answer in order)
1. **Is the reported plateau supported by the evidence?** The claim is "+87 elo vs HeuristicMCTS is a hard ceiling for the current net; three cheap levers (policy-iteration, value-blend, depth-vs-fixed-ref) all fail to move it." Evidence: §6 curves, `results.csv: scalingcurve_*`, `policy_scale` gates. Counter-evidence: the ceiling is measured against a possibly-mis-leafed reference (A8) and a possibly-contaminated seed range (A9).
2. **What are the three most likely root causes of the plateau?** (Our guesses: the v2.7 leaf caps learned strength; the value head can't rank; measurement can't see above amateur. We want independent ranking.)
3. **Is there evidence of a correctness bug** that invalidates learning? Priority suspects: A8 (reference leaf mismatch), G-T2 (value-loss starvation confounds every value verdict), A9 (seed contamination), the FPU POV assumption (`mcts.py:893-895`).
4. **Which current assumptions are least justified?** (See §10.) Candidates: "outcome-corr is irrelevant but ranking is everything," "future-sight isn't a strength lever (n=76)," "more search should help."
5. **Which results have been overinterpreted?** Candidates: the residual +46.5 (z=2.29, pairing-σ caveat); the odometer "ceiling raised ~1 doubling"; the −576 "calibration cliff" as evidence about value heads in general.
6. **What crucial evidence is missing?** (Our list: any above-amateur reference; matched-depth scaling for the *current* best net; a clean A8 re-run; an ablation isolating G-T2.)
7. **What are the highest-information, lowest-cost diagnostics?** (We suspect: fix+re-run A8; one value-loss-weight sweep; quantify A9 contamination by re-running one ladder at seed 1e9.)
8. **Which experiments should we stop running?** (We suspect value-as-leaf rebuilds and flywheel variants have hit diminishing returns; we want confirmation or refutation.)
9. **Is the architecture fundamentally reasonable for this problem?** Specifically: is single-determinization clairvoyant PUCT + a hand-crafted leaf the right frame for a stochastic, farm-dominated, two-consecutive-moves game, or is the AlphaZero formulation itself a poor fit (§10)?
10. **What would you do in the next three experimental cycles?**
11. **Under what results should we abandon or substantially redesign?**

---

## Internal open questions we have NOT resolved (and their status)
- **Q-A8 [unresolved, high].** Does HeuristicMCTS actually run the v1 leaf in all the vs-heuristic evals? (Code says yes, docs say v2.7.) If yes, what do +25/+57/+87 become when the opponent is given v2.7? — *no experiment run.*
- **Q-G-T2 [unresolved, high].** Is the "value-in-loop hurts / value can't rank" verdict an artifact of the ~5–10× value-loss under-weighting? — *no value-loss-weight sweep run before the verdict.*
- **Q-A9 [unresolved, med].** How many ladder/odometer evals overlapped trained-on decks (seed floors 600k/800k vs self-play seeds)? — *unquantified; head-to-head fixed, ladder not.*
- **Q-depth [unresolved, med].** Does the *current best* net's edge grow with matched search depth, or only iter_11's? — *deferred as "multi-hour, doesn't change strategy."*
- **Q-chance [deferred].** Is the clairvoyance-not-a-lever conclusion robust beyond the single n=76 River screen? — *demoted, never re-run on base.*
- **Q-flywheel [unresolved, low].** Why did flywheel iter1 regress the *policy* by ~50 elo? — *labeled "co-adaptation destabilized," not diagnosed.*
- **Q-window [latent].** Can strong play sprawl past the 25×25 window often enough to bias the corpus (overflow games are dropped, not clipped)? — *measured <1% on random play only; stronger play untested.*
- **Q-measurement [strategic, unresolved].** There is no above-amateur reference anywhere. Every verdict bottoms out at HeuristicMCTS ≈ strong-amateur. How can the superhuman win-condition ever be confirmed or falsified with the current instruments? — *flagged as the #1 blocker; no instrument built.*

## Decisions awaiting Joshua (from STATUS.md)
- Accept the residual leaf (`CARCASSONNE_V25_RESIDUAL_SCALE=0.25`) into production + reassess the superhuman goal honestly, **OR** push harder (higher-capacity learned leaf / more careful flywheel).
- Whether to build an above-amateur reference (high-sim HeuristicMCTS rung / external engine bridge / expert game corpus) as a Stage-0 dependency.
