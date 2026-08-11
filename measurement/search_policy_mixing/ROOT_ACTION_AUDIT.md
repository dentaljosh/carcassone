# Phase 2 — Root-Action Agreement Audit

> **Measurement only.** Champion unchanged (`flywheel2_champion_iter8`). Base commit `8c42550`.
> Built on the 1000-position midgame bank; **soft teacher = heur@3200** (real-deck / clairvoyant-
> leaning, NOT ground truth). **FACT** = read off an artifact (cited). **INTERPRETATION** = my
> reading. **Root teacher-imitation is kept strictly distinct from full-game Elo** (they are
> non-transitive here — see the ⚠️ box).
>
> Artifacts: [ROOT_ACTION_AUDIT.jsonl](ROOT_ACTION_AUDIT.jsonl) (new variant roots + signals),
> [ROOT_ACTION_RESULTS.csv](ROOT_ACTION_RESULTS.csv),
> [ROOT_ACTION_RESULTS_BY_BAND.csv](ROOT_ACTION_RESULTS_BY_BAND.csv),
> [ROOT_ACTION_RESULTS_BY_DISAGREEMENT.csv](ROOT_ACTION_RESULTS_BY_DISAGREEMENT.csv).
> Built by `scripts/search_policy_mixing/root_action_audit.py` (1000 pos, W=14, 5.37 min, 0 errors)
> + `analyze_root_action.py`. v27 recheck reproduced the labelled `v27_static_choice` 1000/1000.

## Key question
> Does iter8 policy improve heuristic/v2.7 root decisions, or does moderate heuristic search already
> dominate it? And what role (standalone / root-prior / candidate-generator / specialist) does the
> root evidence support?

## ⚠️ The non-transitivity that governs every number below (INTERPRETATION — read first)
**Root teacher-imitation (matching heur@3200's per-move pick) is NOT full-game strength.** On the
independent ruler, iter8 (resid 0.25) **beats heur@800 by +58.7 elo** and beats heur@1600
full-game (governance/PRODUCTION.yaml; CHECKPOINT_LINEAGE). Yet at the root, heur@800 *out-imitates*
iter8 in every cell below. Both are true: iter8's value lives in **full-game policy / search
efficiency**, not in per-move emulation of a deeper search. So this audit can say what iter8 is
**not** (a per-move deep-search emulator; a useful standalone root-prior) — it **cannot** condemn
iter8 as an agent, and any "use heuristic instead" reading must be checked full-game (Phase 3/5).

## 1. Overall top-1 vs the heur@3200 teacher (FACT)
| variant | vs teacher | vs heur@800 | vs iter8_prod | vs v27_static |
|---|---|---|---|---|
| ITER8_PROD@200 | 0.487 | 0.478 | 1.000 | 0.401 |
| **ITER8_NORESID@200** (= policy + pure v2.7 leaf) | **0.503** | 0.489 | 0.804 | 0.405 |
| ITER8_POLICY_ROOT_ONLY (raw policy argmax) | 0.259 | 0.245 | 0.266 | 0.225 |
| V27_STATIC_ROOT_ONLY | 0.480 | 0.513 | 0.401 | 1.000 |
| HEUR_200 | 0.578 | 0.611 | 0.453 | 0.571 |
| HEUR_800 | 0.658 | 1.000 | 0.478 | 0.513 |
| HEUR_1600 | 0.715 | 0.689 | 0.486 | 0.511 |
| HEUR_3200 (teacher) | 1.000 | 0.658 | 0.487 | 0.480 |

**FACT:** heuristic search dominates the neural agent at root imitation at **every budget** — even
**equal-sims HEUR_200 (0.578) beats ITER8_PROD@200 (0.487)** by +0.09. The raw policy prior alone
(0.259) is far below search. **INTERPRETATION:** the net policy does **not** help match deep search
at equal budget; pure heuristic search of the same depth already imitates the teacher better. iter8
is not a per-move deep-search emulator.

## 2. Residual / value head — decomposition at the root (FACT)
ITER8_NORESID (residual_scale 0 → net policy prior + **pure** v2.7 leaf, the *collapsed* variant)
vs ITER8_PROD (residual 0.25), **paired (same seed, only residual differs):**
- prod==noresid root agreement **0.804** → the residual head **flips 19.6%** of root picks.
- prod vs teacher **0.487**; noresid vs teacher **0.503** → **removing residual improves root
  agreement by +0.016**.
- On the **196 flip positions**: noresid is teacher-right **0.219** vs prod **0.138** — when the
  residual changes the pick, the no-residual pick agrees with the teacher **~1.6× more often**.
- By band the residual hurts **most in the endgame** (pre_endgame: noresid 0.435 vs prod 0.390).

**INTERPRETATION:** at the root, the value/residual head is **neutral-to-mildly-harmful for
teacher-imitation** — it does not improve which move iter8 picks, and on the positions it changes,
it is more often the *worse* pick (vs heur@3200). This **contradicts** the "validated value-head
lever" framing — but root-imitation ≠ strength (the ⚠️ box), so the residual's *full-game* value is
the open question, resolved by the Phase 5 pilot, **not** by this table.

## 3. By band — the opening→endgame inversion (FACT)
| variant | opening | early_mid | mid | late_mid | pre_endgame |
|---|---|---|---|---|---|
| ITER8_PROD@200 | 0.610 | 0.500 | 0.485 | 0.450 | 0.390 |
| ITER8_NORESID@200 | 0.615 | 0.530 | 0.480 | 0.455 | 0.435 |
| HEUR_800 | 0.755 | 0.720 | 0.580 | 0.600 | 0.635 |
| HEUR_1600 | 0.800 | 0.750 | 0.655 | 0.650 | 0.720 |

**FACT:** iter8's root-imitation is strongest in the opening (0.61) and **inverts to its worst in
the endgame (0.39)** — reproducing L2-3/CL-027 and the midgame report. **heur@800 beats iter8 in
every band.** **INTERPRETATION:** iter8's relative per-move competence is front-loaded; the endgame
is exactly where the fixed-K hybrid hands off — the root data *explains* the hybrid design.

## 4. Disagreement subsets — what recovers each miss (FACT)
| subset | n | ITER8_PROD | NORESID | POLICY_ONLY | V27 | HEUR_200 | HEUR_800 | HEUR_1600 |
|---|---|---|---|---|---|---|---|---|
| A: iter8 ≠ teacher | 513 | 0.000 | 0.084 | 0.125 | 0.286 | 0.380 | **0.468** | **0.556** |
| B: v27 ≠ teacher | 520 | 0.296 | 0.319 | 0.169 | 0.000 | 0.321 | 0.462 | 0.544 |
| C: iter8=teacher & v27≠teacher | 154 | 1.000 | 0.890 | 0.344 | 0.000 | 0.455 | 0.675 | 0.701 |
| D: v27=teacher & iter8≠teacher | 147 | 0.000 | 0.095 | 0.197 | 0.000 | 0.667 | 0.708 | 0.748 |

**FACT:** iter8's misses (subset A) are recovered by **deeper search** (heur@800 0.468, heur@1600
0.556), barely by the no-residual variant (0.084) or the raw policy (0.125). iter8's search **adds
real value over its own static leaf** on 154 positions (subset C) — mostly preserved without the
residual (0.890) — but **throws away 147** (subset D) that static v2.7 had right (C−D ≈ +7, a wash).
**INTERPRETATION:** iter8's per-move deficit is a **search-depth** problem, not a feature/value-head
problem — consistent across the pre-tool and midgame audits. The residual is not what recovers the
misses.

## 5. Sharpness / branching dependence (FACT, abridged — full bins in stdout/CSV)
- **v27_gap:** on the 737 low-gap (contested/opening-tie) positions everyone is low (iter8 0.38,
  heur@800 0.55); on sharp positions (gap>1) all climb to 0.9–1.0 — heur ≥ iter8 in **every** gap bin.
- **n_legal:** iter8 worst at high branching (>45 legal: 0.388); heur@800 still ahead in every bin.
- **policy_top1_prob / noresid visit-concentration:** low confidence ⇒ high iter8 error (these are
  the routing signals analyzed in Phase 4) — but heur ≥ iter8 in every confidence bin too.

**INTERPRETATION:** there is **no stratum** (band, gap, branching, confidence, source) where iter8
out-imitates heur@800 at the root. Cheap signals predict *where iter8 errs*, but not a pocket where
iter8 is the better per-move choice.

## Answers to the Phase-2 key question (INTERPRETATION)
1. **Does iter8 policy improve heuristic/v2.7 root decisions?** **No, at the per-move imitation
   level** — equal-budget heur@200 already out-imitates iter8@200, and heur@800 dominates it
   everywhere. iter8's policy prior alone (0.259) is weak; it needs search.
2. **Does moderate heuristic search already dominate it (per-move)?** **Yes** — at every budget and
   in every stratum, for matching the deep teacher.
3. **Residual at the root?** **Neutral-to-harmful** (noresid ≥ prod; flips are worse). The full-game
   value of the residual is the open question (Phase 5 pilot).
4. **Role implication (root evidence only):** iter8 is **not** a useful standalone root-prior /
   candidate-generator (policy-alone 0.259) and **not** a per-move deep-search emulator. Its
   demonstrated value (full-game > heur@800) must therefore live in **whole-game policy/search
   efficiency** — i.e. as a **standalone agent** or the **early-game leg of the hybrid**, not as a
   per-move oracle. This is carried into Phase 4 (routing) and the final report.
