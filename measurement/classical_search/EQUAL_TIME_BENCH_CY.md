# Phase 1.1 — equal-time re-bench, CYTHON candidate leaf (PUCT-heuristic-priors vs champion h6400)

**Status:** DONE 2026-07-06. Re-runs the equal-time normalization after wiring the
candidate leaf to the **Cython flat leaf** (was pure-Python, capping it at 800 sims).
Supersedes the sims budget in [EQUAL_TIME_BENCH.md](EQUAL_TIME_BENCH.md) for the
strength sweep. MEASUREMENT ONLY — no champion/PRODUCTION change; v2.7/v2.9 leaf
SEMANTICS unchanged (gate below).

Bench: `scripts/classical_search/bench_equal_time_cy.py` · raw:
`measurement/classical_search/equal_time_raw_cy.json`.

## What changed (the candidate leaf now runs Cython)

The candidate (`src/carcassonne_ai/heuristic_prior_mcts.py`) built its per-child
softmax priors from a **pure-Python** flat-leaf reproduction (`leaf_score_float`,
~30× slower), which is why the first bench capped it at 800 sims. It now calls the
Cython flat leaf via two new entry points:

| candidate `leaf_quantize` | now calls | resolution |
|---|---|---|
| `float` (default, prior-resolution) | `flat_leaf.flat_virtual_score_v2_float` → `flat_leaf_cy.flat_virtual_score_v2_cy_float` (**new**, pre-round) | full sub-integer |
| `int` (reference/quantized) | `flat_leaf.flat_virtual_score_v2` → `flat_leaf_cy.flat_virtual_score_v2_cy` (existing Cython int leaf) | int-rounded |

`flat_virtual_score_v2_cy_float` is the **pre-round** sibling of the production int
leaf: both share one C body (`_flat_score_v2_c`) and differ ONLY by the terminal
`int(round(...))`. The pure-Python `leaf_score_float` stays as the reference /
`.so`-absent fallback.

### Correctness gates (semantics unchanged)
- **Production int leaf:** `scripts/reconcile_cy_leaf.py --n 200` → **0 mismatches /
  172662 leaf evals** across 3 configs (the refactor into `_flat_score_v2_c` did not
  touch v2.9 output). Wiring/base/structure all PASS.
- **New float leaf:** on 1210 random midgame states × 2 players (2420 evals),
  `flat_virtual_score_v2_cy_float` is **BIT-IDENTICAL** to pure-Python
  `leaf_score_float` (max abs diff **0.0** — better than the documented ±1), and
  `int(round(cy_float))` == the production int leaf **exactly** (0 diff). So the
  candidate's play at a given sims count is unchanged; only the sims budget grows.
- `tests/test_heuristic_prior_mcts.py`: **8/8 green** (+ `test_flat_leaf_edge_cases` 2/2).

## Setup
- **Box:** local 5900XT (`Doctor`), **single OS thread** (`OMP/MKL=1`, CUDA masked), `nice -n 19`, net-free CPU.
- **Leaf:** v2.9 `Bmild_cap8` via the Cython flat path (`USE_FLAT_LEAF=1`, `USE_CY_LEAF=1`, `USE_CY_REPR=1`; int+float Cython entries asserted bound before timing).
- **Positions:** 20 fixed deterministic non-terminal positions, plies 30–140, legal 1–55 (same builder/seeds as the pure-Python bench).
- **Timed:** only `best_action` per position; median over 20.
- **Champion:** `HeuristicMCTS(heur_leaf="v2_7")`, `c=3.0`, `sims=6400`.
- **Candidate:** `HeuristicPriorAgent` (PUCT + heuristic-leaf priors), `c_puct=1.5`, `τ_p=5`, `final_select=Q`, **Cython leaf**.

## Results (single-thread ms/move)

Champion h6400 re-measured: **median 3139 ms/move** (mean 3187, p90 3744). ±10% band = **[2825, 3453]**.

| candidate variant | sims | median ms/move | ratio vs h6400 |
|---|---:|---:|---:|
| float (Cython) | 800 | 718 | 0.23× |
| float (Cython) | 1500 | 1409 | 0.45× |
| float (Cython) | 2000 | 2090 | 0.67× |
| **float (Cython)** | **2500** | **2845** | **0.91× ✅ in band** |
| **float (Cython)** | **3000** | **3423** | **1.09× ✅ in band** |
| float (Cython) | 3500 | 4029 | 1.28× |
| int (Cython) | 800 | 737 | 0.23× |
| int (Cython) | 1500 | 1527 | 0.49× |
| int (Cython) | 2000 | 2531 | 0.81× |
| **int (Cython)** | **2500** | **3023** | **0.96× ✅ in band** |
| **int (Cython)** | **3000** | **3390** | **1.08× ✅ in band** |
| int (Cython) | 3500 | 4019 | 1.28× |

## Chosen candidate sims (matched wall-clock)

- **float Cython:** interpolated exact 1.00× match at **~2754 sims** (in-band 2500 & 3000). **Recommend `cand_sims ≈ 2750`** for the strength re-run (round; both bracket points are in-band).
- **int Cython:** interpolated exact match at **~2657 sims** (essentially the same — int/float share the leaf body so per-sim cost is equal).

**vs the old bench: 800 sims (pure-Python) → ~2750 sims (Cython) at equal wall-clock ≈ a 3.4× larger sims budget for the candidate.**

## Speedup breakdown / surprise flag

- **Per-leaf (isolated microbench, 600 calls × 3 reps):** pure-Python `leaf_score_float`
  **337 µs/leaf** → Cython float **23.9 µs/leaf** = **14.1×** (int **24.0 µs = 14.0×**).
  (Note: the CLAUDE.md "~30×" is a general figure; for THIS v2.9-curve config the
  measured per-leaf gain is 14×.)
- **Per-sim (this bench):** only **~3.4×** (800 → 2754 equal-time sims), NOT 14×.
  **Surprise / the load-bearing finding:** the leaf is only ~⅔ of the candidate's
  per-sim cost. Expand-all evaluates *L* child afterstates per node expansion, and
  each needs a `game.get_next_state` step + string hash + MCTS bookkeeping — all
  UNCHANGED by the leaf swap. So Amdahl caps the sim-level gain at ~3.4× even though
  the leaf itself is 14× faster. The next lever for MORE candidate sims is the
  **stepping/expansion path** (get_next_state, board hashing), not the leaf.
- Still a real win: the candidate goes from an **8× sims deficit** vs the champion
  (800 vs 6400) to a **~2.3× deficit** (2750 vs 6400) at equal wall-clock — the
  informed expand-all sims now compete much closer to h6400's blind-random-UCT sims.

## Next
Re-run the strength sweep best config (**c_puct=1.5, τ_p=5**, the pure-Python winner
at +107) with the Cython candidate at **`--cand-sims 2750 --champ-sims 6400`**
(float leaf). The `int` reference cell matches at ~2650 sims.
