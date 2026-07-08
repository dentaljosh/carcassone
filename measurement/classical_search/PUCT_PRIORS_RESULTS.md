# PHASE 1.1 — PUCT-with-heuristic-priors vs the deep-classical champion — RESULTS

**Status (2026-07-07): ✅ FLIP EXECUTED — PUCT-priors is the production champion.** Confirm +148.2/z10.17/n400 (fresh band) + transitivity round-robin (RPS retired: [ROUND_ROBIN_PLAN.md](ROUND_ROBIN_PLAN.md)) → Joshua authorized the flip ("flip and go", 2026-07-07). `governance/PRODUCTION.yaml` champion → `puct_priors_v29_bmild_cap8`; CL-041 SUPERSEDED, CL-043 PROMOTED. The v2.9 leaf is UNCHANGED (pure search win). Open follow-ups gating full trust: K=3 endgame confirm (IN FLIGHT) + fair-PIMC verdict ([ROADMAP](../../docs/PROGRAM_ROADMAP_2026-07-07.md) A2).

**Update (2026-07-08): search-squeeze cells + A2 resolved.** Track-C: **tree-reuse FOLDED into the champion** (`reuse_tree: true`, +39.3/z2.81 n=400 equal-time, ms 1.06 — CL-044); **LCB CLOSED** (wash) and **value_norm=15 CONFIRMED** (both {8,30} wings negative — C4 CLOSED). **A2 fair-PIMC SCREEN** (CL-045): fair +49.0/z2.86, clair +205.0/z6.68, **clairvoyance tax ~156 elo**. Tables in the [Search-variant screen + reuse confirm + A2 fair-PIMC](#search-variant-screen--reuse-confirm--a2-fair-pimc-2026-07-08) section below. K=3 confirm also landed (+108.1/z6.11).

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

## CONFIRM — FIRED (2026-07-06 18:54)
Config `c1.5/τ5/visits/float/2750` at **n=400 on FRESH band 9.4e9**: **+148.2 elo (±19.0 1σ unpaired; paired z=10.17), W276/D9/L115, wr 0.701** vs h6400. Gate was +35 (2σ) → **FIRES, cleared by ~8σ.** Landed *above* the winner's-curse-shrunk prediction (+60–100): the effect is larger/more robust than the max-of-k model implied — expected, since c1.5 was a pre-specified interior point, not a fished argmax. Source: `CONFIRM_PROGRESS_K2.tsv` + cell `summary.json`. **→ champion-flip PROPOSAL is live** ([PHASE1.1_FLIP_PROPOSAL_DRAFT.md](PHASE1.1_FLIP_PROPOSAL_DRAFT.md), pending Joshua's review — MEASUREMENT ONLY, nothing executed).
**K=3 endgame confirm — DONE 2026-07-07: +108.1 elo / paired z=6.11 / n=199** (128W/3D/68L, same band 9.4e9 CRN vs the K=2 confirm). The win **holds strongly at the deeper endgame handoff** — the margin shrinks +148.2 (K=2) → +108.1 (K=3) exactly as expected (each extra endgame ply solved *exactly on both sides* removes a sliver of the midgame-search advantage), but stays 6σ. So the flip is robust toward the production K≤4 config. (seed94 was a pathological K=3 solve — one worker ground it 72 min past the TT cap — skipped → n=199, immaterial. τ bracket + K=4 dropped: the τ axis gates nothing and the K=4 solve is ~40h/run; K=3 answers the endgame-depth question.) results.csv `puct_c1.5_tau5_float_visits_s2750_vs_h6400_k3`.

## Implications if the confirm holds (PROPOSE, do not execute)
1. **Champion flip** to the PUCT-priors agent (a search-algorithm win, not a learned-value win). 2. **The whole ruler ladder is calibrated to HeuristicMCTS** (the thing this beats) → **Phase 3 re-anchoring becomes load-bearing**; historical "parity with deep search" verdicts must be re-read against the new rung. 3. **Phase 1.2 (ID-alpha-beta)** — the review gated it on "1.1 fires" — is now worth doing. 4. **Phase 5 (Gumbel) warm-start** distills from this winner. 5. This **overturns the program's "strength arc converged / every lever closed" headline** (STATUS 2026-07-05): a classical-search lever the reviews flagged as highest-EV was not closed.

Commits: `c1fd320` (build+bench+harness), `d4e3157` (Cython candidate), `b9ad65d` (launcher + round-1 table). Launcher: `scripts/classical_search/run_screen_sweep.sh` (rounds 1–5). Harness: `scripts/classical_search/eval_puct_priors.py`.

## Search-variant screen + reuse confirm + A2 fair-PIMC (2026-07-08)

Track-C "search squeeze": pre-registered A/B cells vs the confirmed champion (c1.5/τ5/visits/float @ 2750, reuse OFF), each flag-gated bit-exact-off, deck-paired, K=2, both boxes. Numbers are in `experiments/results.csv` (`rr_puct2750-*` + `fair_puct2752_*` rows); this interprets. **The equal-wall-clock guard (ms-ratio ∈ [0.9,1.1]) makes every screen a valid same-compute A/B — a positive elo is free effective depth, not a time discount.**

### Screen — n=200 paired, K=2 (band per finding; `--no-results-csv`)
| cell | elo | paired-z | ms-ratio | W/D/L | verdict |
|---|---|---|---|---|---|
| **reuse (`reuse_tree`)** | **+47.2** | **1.73** | 1.065 ✓ | 112/3/85 | **WINNER → confirm** |
| lcb (`final-select lcb`) | 0.0 | 0.11 | 1.001 | 96/8/96 | DROP — wash vs visits (**C2 CLOSED**) |
| vn8 (`value_norm 8`) | −24.4 | −0.80 | 0.996 | 91/4/105 | DROP |
| vn30 (`value_norm 30`) | −36.6 | −0.66 | 0.983 | 88/3/109 | DROP — {8,30} both < 0 → **vn15 optimal, C4 CLOSED** |
| null (champ vs champ) | 0.0 | — (nan) | 1.000 | 96/8/96 | seat-bias CLEAN |

(elo ± ~25 1σ per cell.) tree-reuse is the only mover; LCB adds nothing at 2750 (visits stays); value_norm=15 is confirmed optimal (both wings negative).

### Reuse CONFIRM — n=400 paired, K=2, fresh band 1.1e10, both boxes → **FIRED**
Config `reuse_tree ON` vs champion `reuse OFF` (c1.5/τ5/visits/float/2750): **+39.3 elo (±17.5 1σ; paired z=2.81), wr 0.556 (W217/D11/L172), ms-ratio 1.060 (equal-wall-clock VALID).** Clears the ≥+15 keep-gate decisively. Screen +47.2 → confirm +39.3 (mild winner's-curse shrink; z rose 1.73→2.81 at higher n). **→ FOLDED into the champion: `governance/PRODUCTION.yaml` `agent_knobs.reuse_tree: true` (CL-044).** A search-efficiency knob on the SAME agent (re-root the tree between moves instead of `clear()` per move), not a new agent — the reused subtree gives free effective depth, so it dodges the sims-washout that kills prior/value tweaks. (The finding-doc snapshot was n=378/+38.8 mid-aggregation; the run completed to n=400/+39.3 — same conclusion.) Open: reuse × fair-PIMC determinization re-check (the re-root assumes a stable transposition table across moves; fair PIMC resamples the deck each move — A2 below ran the reuse-OFF champion). `results.csv rr_puct2750-reuse_confirm_n400_k2`; summary.json in `/mnt/c/carc-shared/classical_search/rr_puct2750-reuse_confirm_n400_k2/`.

### A2 fair-PIMC deployable screen — n=100/arm, K=2 (ROADMAP A2 → CL-045)
Champion PUCT-priors, k_dets=8 × sims=344 = 2752 total (≈ champion 2750), exact-K=2 marginalized (honest hidden-bag) endgame, vs a **clairvoyant HeuristicMCTS h800** (c=3.0, v2.9 leaf) rung fixed in BOTH arms. Seed band 1.3e10.

| arm | champion mode | elo vs h800 | paired-z | W/D/L | wr |
|---|---|---|---|---|---|
| **fair** | blind, 8 determinizations | **+49.0** (±35.1) | **2.86** | 56/2/42 | 0.570 |
| **clair** | descends the true deck | **+205.0** (±41.0) | **6.68** | 76/1/23 | 0.765 |

**Clairvoyance tax = clair − fair = 205 − 49 ≈ 156 elo** (~6× the stale iter8 CL-022 ~26.6). Reading: the champion plays BLIND against a deck-SIGHTED rung and still wins (+49/z2.86 → genuinely > h800 under honest play; conservative — fair-vs-fair would score higher), but ~156 elo of its clairvoyant dominance is deck-knowledge it cannot use in a real match. **Measurement-validity:** any superhuman/human claim must be graded FAIR; the clairvoyant HeuristicMCTS-calibrated strength ladders OVERSTATE deployable strength for this champion → Phase-3 ruler re-anchor ([ROADMAP](../../docs/PROGRAM_ROADMAP_2026-07-07.md) Track D) is now load-bearing. **n=100 is a SCREEN (±35 1σ/arm)** — the tax magnitude is screen-grade; the paired z (2.86/6.68) is the strong part. Follow-ups: n=400 fair confirm + a determinized-rung fair-vs-fair variant (cleaner deployable number); K∈{4,8} rows RAM/attended-only. `results.csv fair_puct2752_kd8_s344_vs_h800clair_k2_{fair,clair}`; launcher `scripts/classical_search/{eval_fair_puct.py,run_fair_grid.sh}` (`cf40ca5`); tests `67470f1`.
