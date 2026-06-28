# Value/Search Conversion Autopsy — Plan (Stage 0)

**Date:** 2026-06-27 · **Branch:** rod_v2_flywheel · **MEASUREMENT / DIAGNOSTIC ONLY.**
No promotion · PRODUCTION.yaml unchanged · champion unchanged · v2.9 evaluator frozen + unchanged.

This is **not** another policy-distillation experiment, **not** a new flywheel, and **not** more
policy mining. Path-3 (high-gap distillation) proved the policy signal is *learnable but
non-converting*. The remaining question is **where the value/search bottleneck is.**

## The one question

> Path-3 proved high-gap policy signal **exists**, the net **can learn it** (held-out prior top1
> 0.000→0.18, regret −27%), yet **NMCTS/game strength does not improve**. Where exactly is the
> remaining bottleneck — and is any value/search intervention game-converting?

Central diagnostic question: **Where does `h6400_v2.9` beat `NMCTS@200`?** Candidate bottlenecks:
A policy/exploration · B value/leaf · C search budget/horizon · D neural-residual corruption ·
E root-fix-but-tree-nonconversion · F endgame-specific value/horizon.

## Anchor — the Path-3 result this autopsy starts from

> **"Policy signal exists and is learnable, but it is not the binding constraint under search."**

Reproduced from the committed Path-3 artifacts (`measurement/high_gap_distillation/`, commit
`addbc32`; numbers are read from `HIGH_GAP_RESULTS.md`, not re-run here — Stage 1 re-derives the
NMCTS leg natively as the reproduction check):

| fact | measurement | source |
|---|---|---|
| **R2 prior improves on held-out high-gap** | hard TEST top1 **0.000→0.179**, regret **0.1130→0.0834** (−27%); endgame top1 0.000→0.176 | HIGH_GAP_RESULTS Stage 5 (n=1390) |
| **R2 NMCTS@200 washes out to iter04** | searched top1 vs h6400 **iter04 0.497 = R2 0.497**; NMCTS regret iter04 **0.0191** ≤ R2 0.0242 (R2 slightly *worse*) | HIGH_GAP_RESULTS Stage 5b (n=400) |
| **only endgame NMCTS moves** | endgame NMCTS top1 iter04 0.483 → R2 **0.552**; eg regret 0.0164→0.0139 | HIGH_GAP_RESULTS Stage 5b |
| **R2 games vs h6400 do NOT convert** | WR **0.409** (n=126 paired) **< iter04 0.463** (n=400); elo −64 vs −26 | HIGH_GAP_RESULTS Stage 6 |

**Mechanism Path-3 established:** at production depth, **search already extracts the
decision-relevant move from the *existing* (bad) prior** — iter04's prior is wrong on every hard
state (top1 0.000) yet NMCTS@200 recovers the h6400 move 49.7% of the time, exactly as often as the
repaired R2. So a better *prior* is redundant at the root. The repair's broad-distribution cost
(ordinary top1 1.0→0.95) is the part search does *not* wash out → games regress. The binding
constraint is therefore the **value/search**, not policy exposure. This autopsy localizes it.

## Frozen substrate (unchanged — identical to Path-3 / the autopsy / repair harnesses)

v2.9 leaf "Bmild_cap8": curve `(-8,-4,-1,0,2,3,4,5)`, `bonus_cap=8`, `opp_cap=8`,
`drop_three_open=0`, `config_hash 7fc930b82801cb43`. Env hard-set before any carcassonne import.
Production NMCTS = `_make_iter8_mcts`: `simulations=200`, `c_puct=3.0`, `residual_scale=0.25`,
v2.9 leaf, `meeple_k=2.0` (inert under the curve).

## Definitions

### Teacher (the reference NMCTS must match)
`h6400_v2.9` = `HeuristicMCTS@6400` on the frozen v2.9 leaf. Per-root, per-legal-action **adjusted Q**
(root-player POV; child Q negated since the move flips the mover) via id-deduped root children —
the extraction validated in `probe_q_separation.py`, already computed for **11,683 roots** across the
Path-3 pilot (1616) + scaled-leg-A (10,067) probes (`measurement/high_gap_distillation/qprobe/` +
`scaled/qprobe_A/`). `h3200_v2.9` available as a shallower-classical reference.
`h12800_v2.9` / exact-K used only to spot-check teacher stability on a subset.

### Students (under test)
- `RoD2_iter04` = `/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_04.pt` (primary baseline — healthiest).
- `RoD2_iter06` = `.../iter_06.pt` (secondary).
- `R2` (Path-3 repaired policy) = `/mnt/c/carc-shared/high_gap_distillation/R2_from_iter04.pt`.
  Used only to confirm the policy-repair washout, never as a promotion candidate.
- All RoD nets: 12 scalar features, 96 filters, 6 blocks, `value_global_pool=False`; encode with
  `Game(include_farm_scalars=True)`.

### A "miss" (decision-relevant NMCTS failure)
A root is a **miss** when h6400 has a meaningful preference (Q-gap ≥ 0.02 **or** student regret ≥ 0.02)
**and** baseline `iter04 NMCTS@200` (a) chooses a different top move, **or** (b) puts low visit share
on the h6400 top move, **or** (c) has h6400-Q regret ≥ 0.02 on its searched move. Target ≥300 useful
miss states, prefer 1k+.

## Stages

- **Stage 0 — reproduce + anchor** (this doc). DONE.
- **Stage 1 — build the miss set.** Run baseline `iter04` and `R2` NMCTS@200 over the high-gap
  (gap≥0.02) labeled pool, record searched move + visit share on h6400 top + adjusted search-Q +
  regret per root; filter to misses; stratify by phase / score-state / legal-n / k_remaining.
  → `VALUE_SEARCH_MISS_SET.md`.
- **Stage 2 — intervention matrix** on the miss set (controlled root-level interventions):
  I0 baseline · I1 more sims (400/800/1600) · I2 teacher-prior injection at root · I3 prior
  ablation (net / R2 / flat-uniform) · I4 neural-value/residual ablation (rs 0 / 0.25 / 0.5) ·
  I5 leaf/depth substitution (vs classical h3200/h6400) · I6 forced-move child evaluation
  (does value recognize the better child?) · I7 endgame-only slice. → `VALUE_SEARCH_INTERVENTIONS.md`.
- **Stage 3 — classify misses** into buckets (not-explored / explored-but-undervalued /
  prior-sensitive / search-budget-sensitive / value-scale-sensitive / horizon / teacher-unstable /
  endgame-specific); **counts by bucket × phase, a table not anecdotes.** → `VALUE_SEARCH_RESULTS.md`.
- **Stage 4 — root gate.** An intervention earns games ONLY if it improves h6400 top1 (+10pp) AND
  mean regret (−≥20%) AND endgame regret (−≥20%) with no major ordinary regression. If none passes:
  STOP, write the decision, no games.
- **Stage 5 — small game screen** (only the single best gate-passing intervention): candidate vs
  h6400_v2.9 / h3200_v2.9 / iter04 baseline, n=100–200 paired, top-up 400 only on real improvement.
- **Stage 6 — `VALUE_SEARCH_DECISION.md`** (answers the 9 questions; outcome A–F).

## Hard constraints (governance)

Do NOT: change the v2.9 evaluator · change PRODUCTION.yaml · promote any checkpoint · start a new
flywheel · do more policy distillation · add a heuristic term · run large game batches before the
diagnostic gates justify them · propose new architecture unless this autopsy proves value
representation is the blocker. **Diagnose the value/search bottleneck; answer the 9 questions; stop
for review.**

## Artifacts

`scripts/rod_v2/value_search/{miss_harness.py, forced_move.py, agg_miss.py}` ·
`measurement/value_search_autopsy/{VALUE_SEARCH_PLAN.md, VALUE_SEARCH_MISS_SET.md,
VALUE_SEARCH_INTERVENTIONS.md, VALUE_SEARCH_RESULTS.md, VALUE_SEARCH_DECISION.md, data/}`.
