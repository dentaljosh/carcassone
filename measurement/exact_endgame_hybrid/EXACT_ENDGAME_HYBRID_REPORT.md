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
correct. **Implication (depth series):** **K=2 full-game (n=400)** is cheap (~10 s/game);
**K=3 full-game screens (n≤200)** are feasible (~80 s/solve, solver-bound → runs on the
CPU-heavy Xeon / local); **K=4 full-game** is marginal (~21 min/solve, 7.4 h tail → needs a
node-budget cap → ~6–10 % timeout-fallback) and worth it only gated on a K=2→K=3 trend;
**K=5+ needs make/unmake or Rust** (deferred). Feasible full-game series = **K=2 → K=3
(→ small K=4)**; K=4/K=5 regret stays micro-validation. (Parity: for any K the agent latches
at k=K or k=K−1 by turn parity, so deeper K = less dilution — K=3 is a *better-powered* test
than K=2, not just "more depth".)

### B.2 — Endgame regret vs exact (already measured; L2-3 / K4 probe)

The endgame *disagreement* the autopsy localized is real, but its **point value is small**,
and h3200 already plays it near-optimally:

**NEW (this branch — RoD1/iter_08/parent scored at K=2 with their v2.8 leaf, n=150 each):**

| agent (v2.8) | K=2 top-1 | mean regret | worst single error |
|---|---|---|---|
| **RoD1** | 0.673 | 0.57 | 9 |
| iter_08 (keep-best) | 0.687 | 0.69 | **15** |
| parent | 0.687 | 0.61 | 9 |
| **heur@3200** (v2.7 ref) | **0.833** | 0.41 | 8 |

The learned nets (RoD1 ≈ iter_08 ≈ parent, all ~0.68 top-1) play the K=2 endgame
**measurably worse** than h3200 (0.833) — reproducing L2-3 (iter8 0.667 / h3200 0.837) with
the v2.8 agents, and confirming the autopsy's "RoD1 ≈ iter_08 ≈ parent" extends to the
endgame. But mean regret is **sub-point** (0.57–0.69) and h3200 is near-optimal → exact
handoff fixes a **real-but-tiny leak** in RoD1 and has little to fix vs h3200. iter_08 carries
the *worst* endgame (regret 0.69, a 15-pt worst case) — consistent with the autopsy's
"iter_08 moves *away* from the ruler in the endgame".

---

## Part C — Full-game exact-hybrid evaluation

**K=2 (full n=400, deck-paired both seats), v2.8 throughout.** Exact tail = RoD1 prefix until
the first TILES decision with k≤2, then clairvoyant+alpha-beta solve. 0 timeouts,
exact-moves/game = 2.0, latched 400/400, K@latch split 200×k=2 / 200×k=1 (the parity 50/50).

| cell | W/D/L | winrate (z) | winrate-Elo | **paired score margin** |
|---|---|---|---|---|
| exact:2 vs **RoD1** | 198/5/197 | **0.501** (z+0.05) | +0.9 (±17.4) | **+0.645 (z+7.49)** |
| exact:2 vs **heur@3200_v2.8** | 206/9/185 | 0.526 (z+1.05) | +18.3 (±17.4) | +1.09 raw (z+0.99) · **Δ +0.652 (z+4.47)** |

(Δ = paired difference vs the cached RoD1-vs-h3200 run on the *identical* decks — isolates the
exact tail.) **The result is consistent and unambiguous:** the exact K=2 tail adds a real,
highly-significant **~+0.65 pt/game** (z+7.5 vs RoD1; deck-controlled z+4.5 vs h3200) —
exactly recovering RoD1's ~0.57-pt/move endgame regret (Part B) — **but moves the WINRATE by
≈ 0** (vs RoD1 literally 0.501; vs h3200 +18.3 Elo but z+1.05, **not** significant). It
**patches the endgame leak without breaking the ruler.** Deck-neutral, exact:2 lifts RoD1 from
the cached −0.36 margin vs h3200 to ≈ +0.29 — a tie-to-slight-margin-lead, not a winrate win.

_(K=3 depth series running — does deeper exact grow the margin enough to move the winrate? →
gates the K=4 decision.)_

## Part D — Slice analysis (why margin improves but winrate doesn't)

The exact gain does **not** concentrate where it would flip outcomes:
- **vs h3200:** the +0.65 margin lands in **blowouts (paired +2.96)** not **close games
  (−0.44, z−0.51)** — extra endgame points pile up in already-decided games. That is the
  mechanism of the margin/winrate split.
- **vs RoD1:** the gain is ~uniform — close +0.57 (z+5.95), blowout +0.66 (z+4.1) — but +0.57
  pts is too small to flip close games (a flip needs the final margin to cross 0).
- The `margin@latch` slice (already-ahead → 0.84 wr; behind → 0.17 wr) is just "leading at the
  endgame → win", not an exact effect — the paired-Δ controls for it.
- 0 timeouts; solver ~3.4 s/game (vs RoD1) / ~7.6 s/game (vs h3200); nodes/game ~770.
- Full digests: [`partCDF_vs_RoD1.md`](partCDF_vs_RoD1.md), [`partCDF_vs_h3200.md`](partCDF_vs_h3200.md).

## Part E — Endgame mechanism: what the exact tail actually fixes

Top 40 RoD1-suboptimal K=2 positions (from Part B regret), move-types decoded — a striking
single mechanism:

- **Every one is a last-tile *placement* error** (TILES phase, k=2): RoD1 places its final
  tile worse than the exact optimum (`tile_place` vs `tile_place`). **Zero** are meeple
  under-deployment or farmer over-commit — by k=2 the meeples are already placed (meeples
  in hand 0–1), so the leak is pure **scoring-conversion / denial on the last tile**
  (completing a city/road/farm, or denying the opponent), not meeple economy. (Refines the
  L2-3 "iter8 wastes meeples" intuition: at the *very* endgame it's tile placement, not
  meeple deployment, that RoD1 gets wrong.)
- **h3200 already makes the exact fix on 24/40 (60%)** of RoD1's mistakes → little for exact
  to add there. But on **16/40 (40%) h3200 is *also* suboptimal** — on those, exact play
  beats **both** RoD1 and h3200. That 40% is the narrow avenue by which exact endgame play
  can *exceed* the deep heuristic (the autopsy's "one lever that can exceed a heuristic"),
  bounded to the last tile.
- Worst RoD1 error in the set: **9 pts** (seed 3200000129, a 67–64 game decided on the last
  tile). Most are 1–3 pts.

Full table: [`partE_examples_digest.md`](partE_examples_digest.md) / `.csv`.

## Part F — Does exact solve h3200's gap or just patch RoD?
_(pending — interpret against the bar above.)_

## Part G — Distillation feasibility (exact labels as a training target)

**What the solver can label (free, per position):** the optimal action (policy target), V*
(the true optimal-play value target), and `child_values` — the exact value of *every* legal
action (a dense policy/regret target, far richer than a one-hot).

**Generation cost (measured):** K=2 ~5 s/solve, K=3 ~80 s, K=4 ~21 min. An exact-labeled
endgame set is cheap at k≤2 (~20–50k positions ≈ ~2–5 h at W=14), costly-but-feasible at k=3
(~10k ≈ ~16 h at W=14), prohibitive at k≥4 (needs make/unmake or Rust).

**What it could teach — and the headwinds:**
- *Policy head* (better last-tile placement, the Part-E mechanism): **low EV** — policy gains
  **wash out under deep MCTS** (memory: net improvements wash out at high sims) and the gain
  is **sub-point** (Part B regret 0.57). Unlikely to move play-strength.
- *Value head* (the more promising target): the autopsy showed the value head **degrading**
  through the RoD continuation (0.510→0.40). Exact V* at k≤3 is a clean true-optimal signal to
  **recalibrate** endgame value estimates — an auxiliary endgame-value head / oversampling late
  positions with V* targets could improve endgame *calibration* without the policy-washout
  problem. This is the one distillation angle with a plausible mechanism.

**Upper bound on the upside:** the fix is worth ~0.57 pts/move at k=2 and is geometrically
confined to the last 1–3 tiles, so even *perfect* distillation cannot address blocker #2 (the
learned net exceeding the heuristic across the whole game) — it can only sharpen the endgame
tail. Final recommendation gated on Part C (does the exact tail even help in full games).

## Part H — Verdict + 10-line executive summary
_(pending.)_
