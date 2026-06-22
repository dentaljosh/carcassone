# L2 K=4 Solver-Grounded Late-Game Probe — how close are the agents to EXACT play at K=4?

**Status: COMPLETE (2026-06-21).** Measurement only — no training, no promotion.
Champion of record unchanged (iter8, [governance/PRODUCTION.yaml](../../governance/PRODUCTION.yaml)).

## Question
Extends L2-3 (CL-025: exact K=2 endgame regret; iter8 plays the endgame *worst*) from K=2 to **K=4**:
how close are iter8 / heur@800 / heur@3200 / hybrid to EXACT solved play four tiles from the end?
The L2-3 solver capped at K=2 (deepcopy solver, no pruning); K≥4 was intractable.

## What unlocked K=4 (the engineering)
- **Exact alpha-beta** for the clairvoyant solver ([endgame_solver.py](../../scripts/level2/endgame_solver.py),
  `solve(alphabeta=True)`). TT carries fail-soft bound flags; the no-prune `_value` path is kept as the
  **validation oracle** — alpha-beta is exact iff it never changes V*/optimal-set, gated bit-equal on the
  already-solved K=2/K=3 positions (0 mismatch). Marginalized (bag-expectation) keeps the no-prune path
  (chance nodes break minimax cutoffs).
- **Make/unmake / Rust were NOT needed for K=4 clairvoyant** — alpha-beta alone makes it tractable
  (~11× node reduction vs the no-prune extrapolation). Rust was scoped (~1–1.5k LOC of vendored engine +
  a bit-exact validation gauntlet, for ~+1 K of reach) and deferred; make/unmake (a ~3–5× speedup that
  reuses the trusted engine) is deferred to the 100–150 expansion / the marginalized labels.
- **Multi-source suite** ([gen_endgame_multisource.py](../../scripts/level2/gen_endgame_multisource.py)):
  greedy / iter8 / heur@3200 / hybrid:8:3200 self-play, K=4+K=5 snapshots, action-replay reconstruction
  (bit-exact). 96 positions, 12/source/K. The selection-bias control.

## Feasibility (clairvoyant alpha-beta, greedy positions, budget 1M) — TRACTABLE
| | nodes | solve time | legal_n |
|---|---|---|---|
| solved | **7/7** measured (1 straggler killed for compute) | — | — |
| median | ~210k | ~14 min | — |
| range | 130k – 444k | 583s – **3167s (~53min)** | 24 – 62 |

- **All measured positions SOLVED under the 1M budget — no budget-driven selection bias** (even the
  hardest, legal_n=62, solved in ~53min without timing out). The cost has a steep **legal_n-dependent
  tail** (≈4.5ms/node Python; make/unmake's 3–5× would matter most here for the expansion).
- PERFECT-INFORMATION (clairvoyant) labels only at this stage. BAG-EXPECTATION (marginalized) is a
  separate, much harder solve (no alpha-beta) — tested separately below.

## PILOT (clairvoyant, 44 solved of 48 mixed-source, 12/source) — headline + a source effect
Agent regret vs the EXACT optimum (top-1 = fraction agent's move is optimal):

| agent | n | top-1 | mean regret | >2 | >5 |
|---|---|---|---|---|---|
| heur@3200 | 44 | **0.750** | 0.91 | 0.11 | 0.04 |
| heur@800 | 44 | 0.727 | 0.93 | 0.11 | 0.04 |
| greedy | 44 | 0.682 | 1.46 | 0.18 | 0.09 |
| **iter8** | 44 | **0.636** | 1.46 | 0.20 | 0.07 |

- **iter8 plays the K=4 endgame the WORST overall** — replicates L2-3 K=2 (CL-025) at greater depth; endgame optimality decoupled from full-game Elo.
- **By-source (the multi-source control's payoff), top-1:**
  | positions from → | iter8 | heur@3200 | greedy |
  |---|---|---|---|
  | iter8-generated | **0.92** | 0.92 | 0.83 |
  | heur@3200-gen | 0.73 | 0.82 | 0.73 |
  | hybrid-gen | 0.50 | 0.60 | 0.60 |
  | greedy-generated | **0.36** | 0.64 | 0.55 |
  iter8 is **near-optimal on the endgames it reaches (0.92)** but **worst on greedy/hybrid endgames (0.36/0.50)** — two compounding effects: iter8-generated K=4 positions are *easier* (all agents ~0.92) AND iter8 mishandles the sharper/OOD endgames others reach. A greedy-only suite would have mis-read this as pure skill deficit. **Small n (10–12/cell) → EXPANSION underway to confirm.**
- **Selection bias: minimal.** 96% solved (44/46), solved-rate even across sources (greedy 11/12, heur 11/11, hybrid 10/11, iter8 12/12); solved positions reach legal_n=72 while unsolved max 60 → not a low-branching bias.

## RESULTS — balanced 200 K=4 positions (50/source × 4), CLAIRVOYANT @1M — COMPLETE 2026-06-21
200/200 attempted, **187 solved (94%)**, 13 genuine 1M-node budget-hits (greedy 7, heur@3200 2, hybrid 2,
iter8 2 — these EXCEED the budget even uncapped; correct selection-bias data, NOT failures). Solve cost:
nodes median 108k / max 973k, secs median ~21min / max ~7.4h. Run on 3 boxes with the **COMPACT blake2b-128
TT key** (`6f9dd08`, validated bit-identical 12/12 incl. node counts); local W dropped 5→3 mid-run after
monsters hit ~10.6GB (see run-ops note). Aggregated with `aggregate_k4_probe.py` → `K4_PROBE_RESULTS.json`.

**Agent regret vs the EXACT optimum (n=187, overall; top-1 = fraction the agent's move is optimal):**
| agent | top-1 | mean regret | >2pt | >5pt |
|---|---|---|---|---|
| **heur@3200** | **0.679** | 1.07 | 0.13 | 0.05 |
| heur@800 | 0.652 | 1.21 | 0.14 | 0.06 |
| greedy | 0.647 | 1.33 | 0.16 | 0.08 |
| **iter8** | **0.561** | 1.48 | 0.20 | 0.06 |

→ **iter8 plays the K=4 endgame WORST overall** (top-1 0.561 vs heur@3200 0.679) — robustly replicates L2-3
K=2 (CL-025, top-1 0.667) and K=3. Endgame optimality stays decoupled from full-game Elo.

**Top-1 by source (the multi-source disentangler — does the ranking hold across generators?):**
| positions from → | iter8 | heur@3200 | heur@800 | greedy | n |
|---|---|---|---|---|---|
| iter8-generated | 0.65 | 0.73 | 0.71 | **0.75** | 48 |
| heur@3200-gen | 0.58 | 0.73 | 0.69 | 0.65 | 48 |
| hybrid-gen | 0.56 | 0.67 | 0.60 | 0.60 | 48 |
| greedy-generated | **0.44** | 0.58 | 0.60 | 0.58 | 43 |

**Difficulty by source** (within1 = # moves within 1pt of optimal; randReg = random-legal regret):
| source | within1 | randReg | iter8 top-1 |
|---|---|---|---|
| iter8-gen | 28.5 | 1.1 | 0.65 |
| heur@3200-gen | 24.0 | 1.1 | 0.58 |
| greedy-gen | 7 | 1.9 | 0.44 |
| hybrid-gen | 6 | 2.0 | 0.56 |

**Sharpness split** (best-vs-2nd-best gap): forgiving (gap<2, n=149) iter8 top-1=0.60 vs sharp (gap≥2, n=38)
iter8=0.40, mean regret 1.01→3.34. All agents degrade on sharp positions; **iter8 degrades the worst.**

## VERDICT — the 3 hypotheses
- **(H1) iter8 near-optimal on its OWN endgames — NOT supported as stated (the pilot's 0.92 was n=12 noise).**
  iter8 scores only **0.65** on iter8-generated endgames (mediocre, not near-optimal) and is BEATEN there by
  greedy (0.75) and heur@3200 (0.73). What IS true: iter8-generated endgames are objectively EASIER
  (within1=28.5, randReg=1.1 — many moves near-optimal), so iter8 merely *looks* least-bad on its own source.
- **(H2) iter8 poor on sharper / OOD endgames — SUPPORTED.** iter8 is worst on greedy-generated (0.44 vs
  0.58–0.60) and worst on sharp gap≥2 positions (0.40, regret 3.34). Conservative: the 7 excluded greedy
  budget-hits are even higher-branching (unsolved legalN med 49 vs solved 40), likely sharper still.
- **(H3) heuristics generalize across sources better — SUPPORTED.** heur@3200 is the most consistent across
  generators (0.58–0.73) and best overall (0.679); iter8 is the most variable (0.44–0.65) and worst overall.

**Net:** the headline (iter8 worst at the endgame) is robust K=2→K=3→K=4. The pilot's dramatic source split
(0.92 own / 0.36 greedy) was small-n noise; the real effect is tamer (0.65 / 0.44) but the same direction —
two compounding effects: (1) iter8 *reaches* easier endgames (forgiving, many near-optimal moves), and
(2) iter8 still handles the SHARP endgames others reach the worst. Consistent with the hybrid-handoff finding
(CL-026): iter8's endgame weakness is real and locally patchable by handing off to heur@3200 near game end.

## Perfect-information vs bag-expectation — _PENDING (marginalized K=4 tractability test; needs make/unmake)_

## K=5 feasibility — _PENDING (small probe, only AFTER the K=4 expansion verdict)_

## Hardware / run-ops note (2026-06-21) — failure modes, all understood
1. **Hardware MCE:** the local 5900XT threw a repeated fatal *Cache Hierarchy Error on physical core 1
   (APIC ID 2)* twice under heavy all-core load → unclean shutdowns. Root cause: PBO Curve Optimizer too
   aggressive on core 1 (−20 all-core; −15 was stable). **FIXED 2026-06-21 (core 1 → −15).** Thermal limit
   gone — but **memory still caps W** (see #2): the constraint is RAM, not thermals.
1b. **TT-cap rejected for K=4:** a `CARCASSONNE_TT_CAP` (freeze-at-cap, correctness-neutral memoization
   bound) was built to let small boxes join, but it can only *reduce* the solved set — node-inflation pushes
   more positions over the budget, and it never makes an unsolvable position solve (`greedy_s3500000000` is
   a 1M-budget-hit even uncapped). The laptop (11GB) can't solve a 12GB monster regardless, so the cap buys
   nothing for K=4. Kept as a tool for K=5 (where the memory wall is worse). The probe stays **uncapped**.
2. **OOM (the W ceiling — and it's SOURCE-dependent):** the AB solver's transposition table balloons on
   hard positions — observed **~12GB for a single worker** (above the initial 6GB estimate) at the 1M
   budget. The ceiling depends on the *source*: greedy/heur@3200/hybrid endgames solve at W=4–6, but the
   **iter8-generated endgames need W=2** (each worker climbs to ~12GB → W=4 pinned memory to ~790MB-free,
   the OOM edge). That iter8 positions produce *bigger, less-prunable* game trees is itself evidence for
   H2 (iter8 reaches sharper/more complex endgames). At W=12–16 several big-TT positions at once exhausted
   the 41GB WSL VM → oom-killer → forced restart. **Memory caps W hard and per-source: W≤4 for the
   easy-source blocks, W=2 for the iter8 tail @1M**; a TT-size cap would permit higher W but is deliberately
   NOT applied mid-suite (it would change the solved/unsolved boundary → a selection-bias artifact).
Probe runs local-solo (W=4 easy-source blocks, dropped to W=2 for the iter8 tail). Fully crash-resumable
(shared-claim + per-position cache), so these cost time,
not data. Other session "crashes" were clean WSL VM restarts (no WHEA), not hardware.

## Conclusions
1. **iter8 plays the K=4 endgame worst of all four agents** (top-1 0.561 vs heur@3200 0.679) — the L2-3
   endgame-weakness finding holds and deepens from K=2 to K=4. Endgame precision ≠ full-game Elo.
2. **The pilot's headline source effect was partly noise.** The real disentangled picture: iter8 reaches
   *easier* endgames (the selection effect is real) AND mishandles sharp/OOD endgames worst (the skill
   deficit is real) — both effects present, each ~2–3× smaller than the n=12 pilot suggested.
3. **Heuristics (esp. heur@3200) generalize across position sources; iter8 does not.** This is the
   measurement backing for the hybrid-handoff patch (CL-026) — hand the endgame to heur@3200.
4. **Measurement only.** Champion (iter8) unchanged. Next exact-solver steps (marginalized/bag-expectation
   labels, K=5) are gated on a make/unmake solver — see BACKLOG (deepcopy churn is the binding constraint).
