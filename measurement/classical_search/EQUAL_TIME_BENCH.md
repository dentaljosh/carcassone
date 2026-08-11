# Phase 1.1 — equal-time normalization bench (PUCT-heuristic-priors vs champion h6400)

**Status:** DONE 2026-07-05. Sets the candidate `sims` the strength sweep runs at
(matched wall-clock, not matched sims). MEASUREMENT ONLY — no champion/PRODUCTION change.

Bench: `scripts/classical_search/bench_equal_time.py` · raw:
`measurement/classical_search/equal_time_raw.json`.

## Setup
- **Box:** local 5900XT (`Doctor`), **single OS thread** (`OMP/MKL=1`, CUDA masked), `nice -n 19`, net-free CPU.
- **Leaf:** v2.9 `Bmild_cap8` via the **Cython flat path** (`USE_FLAT_LEAF=1`, `USE_CY_LEAF=1`, curve support asserted active before timing — a python fallback would inflate every number ~30×).
- **Positions:** 20 fixed (deck+trajectory deterministic) non-terminal positions spanning **plies 30–140** (legal-move counts 1–55), so the ms/move median reflects the early/mid/late mix a real game sees.
- **Timed:** only `best_action` (the search) per position; median over the 20 positions.
- **Champion:** `HeuristicMCTS(heur_leaf="v2_7")`, `c=3.0`, `sims=6400`.
- **Candidate:** `HeuristicPriorAgent` (PUCT + heuristic-leaf priors), `c_puct=1.5`, `τ_p=5`, `leaf_quantize=float`, `final_select=Q`.

## Results (single-thread ms/move)

| agent | sims | median ms/move | mean | p90 | ratio vs h6400 |
|---|---:|---:|---:|---:|---:|
| **champion HeuristicMCTS** | **6400** | **3081** | 3106 | 3704 | 1.00× |
| candidate PUCT-priors (float) | 100 | 407 | 512 | 747 | 0.13× |
| candidate PUCT-priors (float) | 200 | 878 | 1074 | 1816 | 0.29× |
| candidate PUCT-priors (float) | 400 | 1422 | 1749 | 2944 | 0.46× |
| candidate PUCT-priors (float) | 600 | 2279 | 2359 | 3320 | 0.74× |
| **candidate PUCT-priors (float)** | **800** | **2953** | 2947 | 3692 | **0.96×** ✅ within band |
| candidate PUCT-priors (float) | 1000 | 3384 | 3545 | 4550 | 1.10× (within band, high edge) |

±10% band on the champion median = **[2773, 3389] ms/move**.

## Chosen candidate sims

**`cand_sims = 800`** — median **2953 ms/move = 0.96× h6400**, comfortably inside the ±10% band and the closest to parity. (Log-linear interpolation puts an exact 1.00× match at ~sims 859; 800 is the cleaner round value and already within tolerance. 1000 also lands in-band but at the +10% edge.)

## Interpretation / surprise flag

At equal wall-clock the candidate runs **800 sims vs the champion's 6400 — an ~8× sims deficit**. This is the expected cost of the design: expand-all + a **per-legal-child afterstate leaf eval at every node expansion** (≈ *L* extra leaf evals + *L* `get_next_state` steps per expansion, *L* = legal-move count, which peaks mid-game). The candidate's per-sim cost is ~8× the champion's per-sim cost. Whether 800 informed (prior-guided, expand-all) sims beat 6400 blind-random-expansion UCT sims is exactly the H1.1 question the strength sweep answers. Note also the candidate leaf here is **pure-Python** (float = pre-round path, not the Cython int leaf) — an int-quantize candidate on the Cython path would be cheaper per leaf and afford more sims; that is one of the reference cells in the sweep.

The strength sweep should launch the candidate at **`--cand-sims 800 --champ-sims 6400`**.
