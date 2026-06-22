# v2.8 mechanistic autopsies

> **STATUS (2026-06-22): SCAFFOLD — protocol fixed; case autopsies populated after Phase 4
> root-action audit selects which patches fire on real target cases.** This is the
> "why does v2.7 fail / does v2.8 fix a real structural class" layer requested in the addendum.
> It is deliberately separate from the Elo/agreement numbers: a patch that gains Elo without a
> supported mechanism here is labeled **"empirical gain, mechanism unclear,"** not a clean survivor.

## Protocol (per candidate patch)

1. **Hypothesis** — the specific v2.7 failure mode (farm undervaluation, opponent denial, completion
   timing, trapped meeples, open-edge scarcity, ownership contest, phase misweighting). From
   [V28_PATCH_PROPOSALS.md](V28_PATCH_PROPOSALS.md).
2. **Target cases** — 10–30 concrete positions from [V27_FAILURE_CASES.csv](V27_FAILURE_CASES.csv)
   where the patch should matter: v2.7 choice, deep-search/exact/teacher choice, why the patch should
   flip/improve the rank.
3. **Line autopsy** — for top examples, force the v2.7 line and the candidate-preferred line; let the
   same strong continuation (heur@800 or exact tail) play both; report where the score/margin first
   diverges; classify the divergence (immediate scoring / delayed completion / denial / farm-final /
   meeple recovery / search-horizon).
4. **Counterfactual** (if cheap) — mutate one condition (tiles remaining, meeple count, score margin,
   ownership/control, open-edge count, phase/K) and check the preference changes *as predicted*. If
   not → mark the hypothesis **weak** even if Elo improves.
5. **Patch-specific success** — improves its intended target subset without broad degradation, AND the
   mechanism is supported. Global root-agreement improvement alone does NOT qualify.

## Conclusion vocabulary

| label | meaning |
|---|---|
| **supported** | target subset improves + line autopsy shows the named mechanism + counterfactual holds |
| **weak** | some movement but the mechanism / counterfactual is only partially supported |
| **falsified** | the patch does not flip the target cases, or flips them for the wrong reason |
| **unclear** | (incl. "empirical gain, mechanism unclear") Elo/agreement moved but mechanism unproven |

## Case table (populated in the autopsy run)

| case_id | competing actions (v2.7 / v2.8) | v2.7 eval | v2.8 eval | teacher/exact pref | continuation-line summary | hypothesized mechanism | counterfactual result | conclusion |
|---|---|---|---|---|---|---|---|---|
| _pending Phase 4 selection_ | | | | | | | | |

---
*Scaffold. Filled after Phase 4 identifies which patches fire on which target cases.*
