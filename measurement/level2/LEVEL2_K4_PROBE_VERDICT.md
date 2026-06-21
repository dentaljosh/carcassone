# L2 K=4 Solver-Grounded Late-Game Probe — how close are the agents to EXACT play at K=4?

**Status: IN PROGRESS (2026-06-19).** Measurement only — no training, no promotion.
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

## EXPANSION (active) — balanced 50/source × 4 = 200 K=4 positions
Confirms the 3 hypotheses with difficulty controls (best-vs-2nd gap, #near-optimal-within-1pt, random-legal
baseline regret, score-margin-entering-K4, source bucket): **(H1)** iter8 near-optimal on its own endgames;
**(H2)** iter8 poor on sharper/OOD endgames; **(H3)** heuristics generalize across sources better. Running
(`/mnt/c/carc-shared/l23_k4_expand_probe/`, AB @1M); aggregate with `aggregate_k4_probe.py`.
**Status as of 2026-06-21:** ~104/200, local-solo W=8 (gentle — see hardware note). _Verdict table PENDING completion._

## Perfect-information vs bag-expectation — _PENDING (marginalized K=4 tractability test; needs make/unmake)_

## K=5 feasibility — _PENDING (small probe, only AFTER the K=4 expansion verdict)_

## Hardware note (run ops, 2026-06-21)
The local 5900XT threw a repeated fatal **MCE (Cache Hierarchy Error, physical core 1 / APIC ID 2)** twice
under heavy all-core load → unclean shutdowns. Root cause: PBO Curve Optimizer too aggressive on core 1
(−20 all-core; −15 was stable). Probe throttled to W≤8 on local until the curve is fixed. Run is fully
crash-resumable (shared-claim + per-position cache on the share), so the MCEs cost time, not data. Other
session "crashes" were clean WSL VM restarts (no WHEA), not hardware.

## Conclusions — _PENDING expansion completion_
