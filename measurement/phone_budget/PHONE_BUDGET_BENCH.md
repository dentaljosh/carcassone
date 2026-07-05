# Phone-budget bench — single-thread ms/move for the deployable agents (2026-07-05)

**What / why.** Settle what search depth a phone can afford, for the deployment arc. Single-thread,
pure-CPU (OMP=1, `CUDA_VISIBLE_DEVICES=""`), production v2.9 Bmild_cap8 env on the Cython flat-leaf path.
Reference core = the local 5900XT desktop core (x86_64). A phone core is ~2–4× slower → the projection
columns. `scripts/bench_phone_budget.py` (commit `e527a88`), raw `measurement/phone_budget/raw_local.json`.

Provenance verified: cython leaf ACTIVE (`cython_leaf_active=true`), leaf micro **21.1 µs/eval**.

## Classical HeuristicMCTS (v2.9 Bmild_cap8) — measured single-thread

| sims | ms/move (median) | p90 | full-game s | phone @2× | phone @3× |
|---|---|---|---|---|---|
| h800  | 326  | 446  | 52  | 0.7 s | 1.0 s |
| h1600 | 669  | 920  | 106 | 1.3 s | 2.0 s |
| h3200 | 1348 | 1827 | 222 | 2.7 s | 4.0 s |
| h6400 | 2854 | 4638 | 511 | 5.7 s | 8.6 s |

Scales ~2× per doubling (as expected). **NB the leaf is only ~5% of move time** — h1600 = 1600×21µs = 34 ms
of leaf vs 669 ms measured; the other ~95% is MCTS machinery (expansion / board apply / selection / backup).
So the Cython leaf speedup is real but the tree overhead dominates on-device.

## Net forward cost (the correction)

**7.4M-param net, batch-1, CPU, 1 thread = 12.1 ms/forward.** This is the important number and it corrects an
earlier over-claim ("net@s200 is instant"). That was true for GPU/NPU (forward ~1–2.5 ms, or batched to tens of
µs) — **NOT for a CPU-only phone**, where a forward is ~12 ms × (2–4× phone) ≈ 25–50 ms. NeuralMCTS does ~one
forward per simulated node, so **net @ sims=200 on a CPU-only phone ≈ 200 × 25–50 ms ≈ 5–10 s/move** — i.e.
*comparable to or slower than* classical h3200, for the same strength tier (RoD-v2 iter_02 ≈ h3200).

## Deployment picture (corrected)

- **CPU-only phone:** classical **h1600–h3200** is the strong engine (1.3–4 s/move, strong-human tier), and the
  neural net @ s200 is **Pareto-similar** to h3200 classical (≈ same cost, ≈ same strength) — neither dominates.
  Classical is the simpler, dependency-free choice here.
- **NPU / GPU phone** (Apple Neural Engine et al., forward ~1 ms): the neural forward gets cheap → net @ s200
  becomes ~instant and the **neural agent pulls ahead** (or you spend the budget going deeper). This is where the
  "net is the right phone engine" claim actually holds.
- **h6400** (5.7–8.6 s/move on phone) = a patient **"analysis / strong mode"**, not real-time play.
- Fairness: the deployable honest agent (fair PIMC, `src/carcassonne_ai/fair_agent.py`) costs **K× a single search**
  (K determinizations), so multiply the above by K — the K×depth budget tradeoff is the open tuning question
  (e.g. K=4×h800 ≈ h3200-cost). Measured separately.

**Bottom line for a product:** a **CPU-only** phone ships **classical h1600–h3200** (or the Pareto-equal net@200)
at strong-human tier with 1–4 s/move; an **NPU** phone ships the **neural net** and can afford more depth. h6400+
is a desktop/analysis tier either way.
