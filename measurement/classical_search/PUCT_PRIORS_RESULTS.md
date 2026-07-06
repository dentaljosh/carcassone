# PHASE 1.1 — PUCT-with-heuristic-priors vs the deep-classical champion — RESULTS

**Status (2026-07-06): SCREEN FIRING HARD; confirm pending.** MEASUREMENT ONLY — PRODUCTION.yaml / champion / v2.7 / v2.9 leaf UNCHANGED. A champion-flip is *proposed only* after the pre-registered n=400 confirm.

Pre-registration: [PLAN.md](PLAN.md). Hypothesis (MT-1, the highest-EV review item): production `HeuristicMCTS` uses random-expansion UCT (C=3.0, no priors, one-random-child-per-sim, int leaf) — well below the classical frontier at equal compute. Adding PUCT + heuristic-leaf priors + expand-all should beat it at equal wall-clock.

## The candidate (`src/carcassonne_ai/heuristic_prior_mcts.py`)
A heuristic **evaluator** plugged into the existing tested `NeuralMCTS` PUCT machinery (no new selection loop; `HeuristicMCTS` untouched): priors = `softmax(Δleaf/τ_p)` over per-child afterstates (mover POV); value = `tanh(leaf/norm)`. Knobs: `c_puct`, `τ_p`, `final_select ∈ {Q, visits}`, `leaf_quantize ∈ {int, float}`. Champion baseline = `HeuristicMCTS` v2.9 `Bmild_cap8` leaf @ **h6400** + exact-K endgame handoff. A/B = deck-paired, clairvoyant matched-mode, **equal wall-clock** (candidate sims set so ms/move matches h6400 ±10%), screen endgame at **K=2** (RAM-safe; identical both sides so it cancels for a search A/B; winner confirmed at K=4).

## Numbers are in `experiments/results.csv` (`puct_*` rows) — this doc interprets.

### Equal-time bench
- Pure-Python candidate leaf: cand **800 sims** = 0.96× h6400 (`EQUAL_TIME_BENCH.md`).
- **Cython float leaf** (`d4e3157`, bit-exact to pure-Python: 0.0 diff / 0-of-172662 mismatch): cand **~2750 sims** = equal-time (`EQUAL_TIME_BENCH_CY.md`). **3.4× more sims** at equal wall-clock (per-leaf 14×, per-sim 3.4× — Amdahl: the leaf is ~⅔ of per-sim cost; the expand-all `get_next_state`/hash is the rest). 800-sim games are BIT-IDENTICAL under pure-Python vs Cython (leaf bit-exact), so round-1's 800 numbers == Cython-800.
- **Stepping-path Cython — INVESTIGATED 2026-07-06, DECLINED (not the next lever).** The residual per-sim cost (`get_next_state`→`StateUpdater.apply_action`→custom `__deepcopy__`; hash via `string_representation`) is **Python-object churn on engine objects, not int math** — Cython can't accelerate it without de-objectifying the whole engine. That de-objectify spike **already ran (BACKLOG:57, 2026-06-12)**: measured **~1.1–1.2× cycle / end-to-end break-even**, deferred as multi-week-not-worth-it while GPU-bound. The deepcopy is already 554×-optimized (2026-05-13) and the hash is `_str_repr_cache`-memoized. The "next lever is the stepping path" read was wrong; a thin bit-exact wrapper buys ~nothing. Real (deferred) levers here are make/unmake (solver-only, 3–5d) or the full flat-state engine — neither an overnight task, both fairly deferred. Do NOT re-propose without new evidence.

### Round-1 — c×τ grid, selector=Q, 800 sims (SCREEN_PROGRESS.tsv), n=100 deck-paired, band 9.0e9
| c_puct \ τ_p | **2** | **5** |
|---|---|---|
| 0.5 | −13.9 (z0.79) | +41.9 (z0.91) |
| 1.0 | +56.1 (z0.62) | +63.2 (z2.11) |
| 1.5 | +92.5 (z2.56) | **+107.5 (z2.09)** |
| 2.5 | +27.9 (z2.06) | +100.0 (z4.21) |
(elo ± ~36 1σ; z = deck-paired margin z.) **FIRES** — a coherent positive region; τ=5 (soft priors) ≫ τ=2 at all c; interior c-optimum ~1.5, broad +100–107 plateau at c=1.5–2.5/τ5.

### Round-4 — the `visits` selector (band 9.03e9)
`c=1.0, τ=5, visits, 800` = **+135.0 (z3.58)** vs the SAME config with `Q` = +63.2 → **the selector alone is worth ~+72 elo**, confirming the clairvoyance-gap doc's "~100 elo" (visit-argmax fixes Q-max picking barely-visited overestimated children under a heuristic leaf). Round-4's other cells (τ8/12, int-quant, c2/3) were dropped per the design consult.

### Design consult (Fable, 2026-07-06) — verdicts folded into round-5
- **Fix τ=5** (4/4 sign, mean +38), **fix selector=visits** (mechanism + z3.6), **drop leaf_quantize as an axis** (no >10-elo mechanism; default float). **c is the only open axis, and it must be re-tuned at 2750** (PUCT √N term drifts the optimum with sims). **Screen at the deployable 2750, not 800** (equal-wall-clock makes it ~free; comparing to matching 800 gives the "does more sims help" read — DON'T assume positive, cf. sims-washout history).
- **Winner's curse**: max of k≈8 σ≈35 cells ≈ **+60–70 elo selection bias** → read +135 as a true **~+90–110**; **a confirm at ~+70 is SUCCESS, not regression.** Absolute level is band-conditional → the **fresh-band n=400 is the only official number.** Confirm **top-1** (fresh band decorrelates level; within-plateau choice costs ≤20 elo). No dense grid / BayesOpt (one continuous axis).

### Round-5 — RUNNING (Fable plan; SCREEN_PROGRESS_R5.tsv; band 9.03e9, per-c PAIRED)
Fix τ=5/visits/float. Cells: `visits@{800,2750} × c{1.0,1.5,2.5}` (same-c cells share a deck band → paired sims read; reuses round-4's cached 800 cells) + `Q@2750/c1.5` (paired Q-vs-visits at 2750 = does the +72 selector effect survive the sims change). Pick **c\*** by **neighbor-smoothing, not argmax**.

**c\* selection rule — PRE-COMMITTED (before the 2750 cells landed; band-confounded per-cell contrasts + winner's curse make a raw argmax unsafe):** default **c\*=1.5** (interior of the fired plateau, round-1's Q-peak, central and robust). Override to c=1.0 or c=2.5 **only** if that cell's 2750/visits elo exceeds *both* the c=1.5 cell *and* its own smoothed-neighbor mean by **>1σ (35 elo)**. Rationale: a single-cell bump within noise is not a real optimum (the c=3 "+47 elo" noise-spike lesson); the fresh-band n=400 confirm — not the screen — is the official number. **Washout guard:** independently of c\*, if the 2750/visits cells collapse toward zero vs their 800 siblings (paired, same band), the gain is a sims=800 artifact → do NOT launch the confirm; audit the 800↔2750 parity first (cf. the net-eval sims-washout history).

**800 visits landscape (n=100, per-cell bands → cross-c contrasts carry band noise):** c1.0 **+135** (z3.58) · c1.5 **+52.5** (z1.99) · c2.5 **+92.5** (z1.79) — non-monotonic and jumpy = noise/band-dominated, consistent with a common ~+90 plateau. The "selector = +72" headline (round-4) was measured at c=1.0 only; this landscape shows the selector×c effect is not a clean constant. The clean selector read is the *paired* Q-vs-visits at 2750/c1.5 (same decks), pending.

## Pre-registered CONFIRM (pending round-5)
Config `c*/τ5/visits/float/2750` at **n=400 on a FRESH band (9.4e9)**, gate **paired-elo ≥ +35 (2σ) → propose champion flip**. Expected landing **+60–100** (winner's-curse-shrunk). If (0,+35): extend the SAME band to n=800, gate +25 (do NOT re-roll bands). If ≤0: the plateau was band-luck — audit the 800/2750 parity first. Then a **K=4 n=200** check (real champion endgame). 

## Implications if the confirm holds (PROPOSE, do not execute)
1. **Champion flip** to the PUCT-priors agent (a search-algorithm win, not a learned-value win). 2. **The whole ruler ladder is calibrated to HeuristicMCTS** (the thing this beats) → **Phase 3 re-anchoring becomes load-bearing**; historical "parity with deep search" verdicts must be re-read against the new rung. 3. **Phase 1.2 (ID-alpha-beta)** — the review gated it on "1.1 fires" — is now worth doing. 4. **Phase 5 (Gumbel) warm-start** distills from this winner. 5. This **overturns the program's "strength arc converged / every lever closed" headline** (STATUS 2026-07-05): a classical-search lever the reviews flagged as highest-EV was not closed.

Commits: `c1fd320` (build+bench+harness), `d4e3157` (Cython candidate), `b9ad65d` (launcher + round-1 table). Launcher: `scripts/classical_search/run_screen_sweep.sh` (rounds 1–5). Harness: `scripts/classical_search/eval_puct_priors.py`.
