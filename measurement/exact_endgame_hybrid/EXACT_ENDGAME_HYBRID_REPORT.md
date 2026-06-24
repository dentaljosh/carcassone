# Exact Endgame-Solver Hybrid — REPORT

> **Status: IN PROGRESS** (branch `exact-endgame-hybrid`, opened 2026-06-24).
> **Measurement / engineering only.** No promote, no PRODUCTION.yaml change, v2.7 frozen,
> v2.8 opt-in. The exact tail is leaf-independent (true terminal score), so nothing here
> touches the production leaf.

## The question (and the conservative prior)

The [iter_08 autopsy](../rod_v28_overnight_flywheel/autopsy/AUTOPSY_RoD_v28_iter08.md)
localized the learned agents' persistent gap vs the deep heuristic to the **endgame**
(all learned nets agree with heur@3200_v2.8 only ~0.51 at the root-move level, *lowest*
in late_mid / pre_endgame). This branch tests the one lever that can *provably exceed* a
heuristic there: hand off the final K placements to an **exact solver**.

**Prior (conservative, pre-registered):** exact handoff patches a *small, real, sub-point*
endgame leak in RoD1; it likely beats RoD1 by a point or two but only *ties* heur@3200_v2.8,
which already plays the K=2 endgame near-optimally. High **diagnostic** value (a source of
truth in the plateau region); low odds of a new champion. Support / falsify / sharpen it.

## Why a clairvoyant exact solver is the FAIR comparison here

Production NeuralMCTS **and** HeuristicMCTS are already **clairvoyant in search** — they
descend the true pre-shuffled deck (`state.deck`), which is exactly what the
[clairvoyance-gap eval](../clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md) measured (+26.6 elo).
So **clairvoyant-exact vs clairvoyant-RoD1/h3200 is a like-for-like, same-information
comparison** — and it is the cheap one (alpha-beta is sound only for minimax). That is the
default arm below, labelled as such. The *marginalized* (fair-information / hidden-bag)
solver is a separate, far more expensive question (no alpha-beta → ~K≤2) and is **never
silently mixed** with clairvoyant-search opponents.

The exact solver is **minimax-optimal vs a worst-case opponent** — NOT a best-response to
the specific (suboptimal) RoD1/h3200 it faces. A conservative, valid endgame policy; not an
oracle exploiter.

## Agents & provenance

| agent | checkpoint / spec | sha256 (16) | leaf | play config |
|---|---|---|---|---|
| **RoD_iter_01** ("RoD1") | `rod_v28_continuation/ckpt/iter_01.pt` | `a8b824df0786284c` | v2.8 (meeple_k=2) | NeuralMCTS s200 c3.0 resid0.25 |
| iter_08 (keep-best, non-promoted) | `rod_v28_overnight_flywheel/ckpt/iter_08.pt` | `5843b3cf0d172f73` | v2.8 | NeuralMCTS s200 c3.0 resid0.25 |
| ITER8_V28_PARENT | `flywheel_residual_attempt2/ckpt/iter8.pt` | `0d355002e26a968e` | v2.8 | NeuralMCTS s200 c3.0 resid0.25 |
| **heur@3200_v2.8** | `heur@3200` + meeple_k=2 | — | v2.8 | HeuristicMCTS 3200 sims, v2_7 leaf+mk2 |
| **exact_hybrid_K:mode** | `exact:K:clair\|marg` (RoD1 prefix) | (uses RoD1) | prefix v2.8; **tail leaf-independent** | RoD1 until first TILES k≤K, then exact solver |

**Baselines that set the bar (from the autopsy's cached deck-paired matches):**
- RoD1 vs heur@3200_v2.8 (n=800): paired **−0.36** (z−0.47) → RoD1 **ties** the ruler.
- iter_08 vs heur@3200_v2.8 (n=800): paired **−0.38** (z−0.48) → also ties.
- RoD1 vs ITER8_V28_PARENT (n=400): **+53.4 elo**, paired +3.68 (z+3.51).

For exact handoff to "exceed h3200" it must show paired margin **clearly > 0** vs h3200
(RoD1 sits at −0.36). For "beats RoD1" it must show paired margin > 0 vs RoD1.

---

## Part A — Engineering (the `exact:K:MODE` agent)

Implemented as a drop-in agent in [`scripts/level2/eval_hybrid_handoff.py`](../../scripts/level2/eval_hybrid_handoff.py)
(`_ExactAgent`), reusing the existing latched-handoff harness (pairing, claim, carc-orch
SHM, manifest) and the existing exact solver
[`scripts/level2/endgame_solver.py`](../../scripts/level2/endgame_solver.py).

- **Latch:** identical trigger to `hybrid:K:N` — first **TILES**-phase decision with
  `k_remaining = len(deck) + (next_tile is not None) ≤ K`. One-way, turn-atomic (the
  boundary tile's meeple stays with the solver). No fall-through back to neural after latch.
- **Choice:** `min(optimal_actions)` from `solve()` — deterministic; value-irrelevant within
  the optimal set under optimal play.
- **Modes:** `clair` → clairvoyant minimax + alpha-beta (default); `marg` → marginalized
  expectiminimax (no AB).
- **Timeout fallback:** a solve exceeding the node budget (`BudgetExceeded`) falls back to
  the **neural** move for that one decision (stays latched, retries next ply on the smaller
  tree); counted as `n_timeouts`, never hidden.
- **Per-handoff logging (in `GameResult`):** `latch_k`, `latch_score` (margin at handoff,
  mover-perspective), `latch_meeples`, `latch_nlegal`, `exact_moves`, `n_timeouts`,
  `solver_secs`, `solver_nodes`, `max_solve_secs` — both seats.

**Verification (GPU integration smoke, exact:2:clair vs RoD1, 2 paired games):** PASSED —
`plumbing + handoff verified`. Latch fires one-way at k≤2 (TILES); exact moves are **legal**
(both games ran to terminal, no illegal-action error); neural prefix (70/game) + exact tail
(2/game) both exercised; 0 timeouts. Per-game solver ~0.2–12 s.

**⚠️ Parity dilution (material for interpreting Part C):** k_remaining counts down by 1 per
draw, alternating players, so whether the exact agent's first sub-threshold TILES decision
lands at k=2 or k=1 is a coin-flip. In ~half the games it latches at **k=1** (a near-forced
last tile → exact ≈ neural); only the other ~half get a meaningful **k=2** solve. So exact:2
changes the agent's play in only ~50% of games — it **structurally halves** the measurable
full-game effect. (exact:3 would always catch ≥k=2, but K=3 is micro-only at 80 s/solve.)

---

## Part B — Micro-validation & solver tractability

### B.1 — Solver cost by K (the full-game feasibility gate)

Clairvoyant + alpha-beta, real L2-3 suite positions
([`scripts/exact_hybrid/bench_solver_by_k.py`](../../scripts/exact_hybrid/bench_solver_by_k.py)):

| K | solved | sec median | sec max | nodes median | full-game verdict |
|---|---|---|---|---|---|
| 2 | 13/13 | **~5 s** | 25.6 s | ~2,200 | **feasible** (~2 solves/game ≈ ~10 s/game) |
| 3 | 3/3 | **80 s** | 119 s | ~26k | **MICRO-ONLY** (~160 s/game tail) |
| 4 | (K4 probe) | ~21 min @1M | 7.4 h | 108k | **infeasible for full games** |

0 illegal moves across the bench — the exact-tail choice path (`min(optimal_actions)`) is
correct. **Implication:** the full-game exact-hybrid is **K=2 only**. K=3/K=4/K=5 are
*micro-validation only* — deeper-K full-game would need make/unmake (~3–5×) or Rust
(scoped + deferred in the K4 probe).

### B.2 — Endgame regret vs exact (already measured; L2-3 / K4 probe)

The endgame *disagreement* the autopsy localized is real, but its **point value is small**,
and h3200 already plays it near-optimally:

| agent | K=2 top-1 (n=150) | K=2 mean regret | K=3 top-1 (n=68) |
|---|---|---|---|
| heur@3200 | **0.837** | 0.40 pts | 0.618 |
| heur@1600 | 0.780 | 0.46 | 0.647 |
| iter8 (≈ RoD1 parent) | **0.667 (worst)** | 0.61 | **0.574 (worst)** |

So: RoD1's lineage plays the endgame **worst**; h3200 plays it **near-optimally**; mean
regret is **sub-point**. This is the mechanistic basis of the conservative prior — exact
handoff should help RoD1 more than it pressures h3200. _(RoD1/iter_08 added directly at K=2:
pending the cheap re-solve.)_

---

## Part C — Full-game exact-hybrid evaluation
_(pending — screens then top-ups; every cell reports WDL, winrate, winrate-Elo, paired
margin, paired_z, n decks, timeouts, solver runtime, handoff K-distribution.)_

## Part D — Slice analysis
_(pending.)_

## Part E — Endgame mechanism examples
_(pending — 20–50 positions: RoD1 vs h3200 vs exact choice + mechanism label.)_

## Part F — Does exact solve h3200's gap or just patch RoD?
_(pending — interpret against the bar above.)_

## Part G — Distillation feasibility
_(pending.)_

## Part H — Verdict + 10-line executive summary
_(pending.)_
