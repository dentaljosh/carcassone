# PRE-REGISTRATION — Leaf residual-mining (error-guided leaf-term discovery)

> **⚠️ STATUS 2026-07-21 — EXECUTED AND CLOSED. Verdict = AMBIGUOUS (one candidate, at the floor
> of the ambiguous band); no HIT; no S1 launched; champion and `governance/PRODUCTION.yaml`
> UNTOUCHED.** Claim **CL-063**. Results + gate arithmetic → `REPORT.md`; canonical numbers →
> [ANALYSIS_688_pooled.json](ANALYSIS_688_pooled.json).
>
> *Original banner, preserved:* this document was committed (`ffe37c8`) BEFORE any fit result was
> computed. Everything below — the residual definition, the complete feature dictionary, the
> split, the multiple-comparisons correction, the gate thresholds and the trigger/closure
> consequences — was fixed in advance. Nothing was edited after the first look at a candidate's
> out-of-sample statistic; the two amendments at the bottom are both dated pre-result.

**Owner:** autonomous run, 2026-07-21. **Prior probability of a hit: ~10–15% — a NULL is the
expected outcome and is a good result.** This is the last new experiment on the current program
ledger; a clean null closes the "leaf accuracy" channel.

---

## 1. Premise (why this is worth one box-night)

CL-062 (+ its 2026-07-21 champion-root amendment) measured the mechanism: **the heuristic
prior's influence on the champion's final decision decays with search depth via
Q-convergence** — at the deployed budget the prior's favourite is played **less than half the
time** (pooled-Q survival 0.6284 → 0.5688 → 0.4862 across per-world 200/344/688 on 436
champion-distribution roots). What the search converges *to* is the leaf's own n-ply backup.
So the improvement target is **the LEAF's accuracy on deep midgame boards**, not root-move
fidelity, and the way to find a term is to look at **where the leaf is wrong** rather than to
guess terms (which is what C7 did, and C7 died — CL-055).

CL-062 re-open trigger **(b)** is literally "a mid-game root band (k_remaining ≫ 3) shows a
materially different profile"; every Gate-B/F3 root to date is a K=3 endgame board. This run
labels a mid-game band, so it also supplies that missing read as a by-product.

## 2. The residual — exact definition

For a root board `s` with mover `m = s.current_player` (TILES phase only):

* **Shallow leaf value**
  `V_leaf(s) = tanh( flat_virtual_score_v2_float(s, m, champion_leaf_cfg) / 15 )`
  — literally the number `HeuristicPriorAgent`'s evaluator hands the search when `s` is a leaf
  (`heuristic_prior_mcts.py`: `value = tanh(leaf_p / value_norm)`, `value_norm = 15`), mover POV,
  in (−1, 1). The champion leaf is `v2_9_2_Bmild_cap8_curve125`, built + runtime-verified through
  `champion_factory.production_prior_cfg()` (F1 guard).
* **Deep pooled-Q**
  `V_deep(s, L) = Σ_a W_pooled(a) / Σ_a N_pooled(a)`
  over the pooled root children of the **DEPLOYED fair-PIMC champion** — `k_dets = 4`
  reshuffled determinizations, per-world PUCT budget `L`, `(N, W_rootpov)` pooled exactly as
  `fair_agent.pool_root_stats` does. This is the backed-up root value of the agent that
  actually plays. Root-player POV (`root_player == m`, asserted).
* **RESIDUAL** `resid(s, L) = V_deep(s, L) − V_leaf(s)`.
  Units: value units, mover POV, range (−2, 2). **Positive = deep search likes the position
  MORE than the leaf says.** A leaf term that predicts `resid` is a term that would move the
  leaf toward what search already believes.

**Primary level `L = 688`** → total `k4 × 688 = 2752` sims = the deployed champion budget
(CL-054). Secondary levels `L ∈ {200, 344, 1376}` come free from the multi-depth snapshot
(one deep search per world, snapshotted at every level, bit-exact **within** a world —
`scripts/measurement_infra/gate_b_fair_pimc.py`, whose `snapshot_world_search` /
`read_children_nw` this harness **imports rather than re-implements**).

Recorded but NOT the primary target (secondary reads only): `max_child_q` (best-play value
instead of the visit-weighted mean) and `top2_q_gap`.

**Known, accepted properties of this target.**
(i) `E[resid] ≠ 0` by construction — the mover gets to choose, so search is systematically more
optimistic than a 0-ply leaf. That constant is absorbed by the intercept; only the **varying**
part is mined.
(ii) `V_deep` is the search's belief, not ground truth. A leaf term fitted to it can only move
the leaf toward *this search's* n-ply opinion. That is exactly the CL-062 target, and it is
also the ceiling of the method — stated here so it is not discovered later as a surprise.

## 3. The feature dictionary — FIXED IN ADVANCE

Implemented in `leaf_features.py`; the harness asserts the emitted name set equals the
declared set, so code and document cannot drift. **K = 18 candidates** in the
multiple-comparisons family. Sign convention: every `*_diff` is mover-POV (player − opponent).

**Cost tiering** uses C7's measured calibration (`CYTHON_LEAF_REPORT.md` + C7 Stage-0): the
Cython leaf is ~27.5 µs and 27.4% of a search; C7 Term R's **one extra pass** over both
players' placed meeples cost **1.204× per leaf — over the ≤1.10 gate**, while Term F's
farmer-only pass cost ~1.01–1.02×. So:
* **A = FREE** — accumulable inside a pass the leaf ALREADY makes (the `flat_closure_bonus`
  loop over `placed_meeples[p]`, run for both players, already resolving terrain, component
  roots, `open_n`, `city_root_delta`, `_surrounding_count`), or a direct read of `decompose` /
  `state` scalars. **Road meeples currently fall through that loop unused**, so a road
  accumulator there is ~free.
* **B = a real add** — needs a new scan (the deck). Must clear C7's ≤1.10× Stage-0 gate before
  it could ship.
* **C = NOT leaf-viable** — needs move generation. Diagnostic only; a C-tier hit cannot become
  a leaf term.

### Controls (partialled out of every test)
`1` (intercept), `v_leaf`, `v_leaf²`, `tiles_remaining`, `corpus_champ125` (indicator: the two
F0b′ corpora were generated under different leaves, curve100 vs curve125).

### Candidates (K = 18)

| # | feature | tier | hypothesis / prior-art status |
|---|---|---|---|
| 1 | `pending_diff` | A | unbanked (would-score-at-end) point differential. With #2 this tests the leaf's **1:1** banked-vs-pending weighting. Review item **P1-L2** ("score as if ended now is structurally biased") was never directly tested. |
| 2 | `running_diff` | A | banked score differential — the paired half of the 1:1 test. |
| 3 | `pending_share` | A | scale-free share of the leaf's edge that is unbanked (risk concentration). |
| 4 | `bonus_overflow_self` | A | closure bonus lost to the `cap=8` truncation. Cap **level** is dead (C5 cap5/cap12 flat; v2.10 cap6 null); this is the **truncation**, a different object. |
| 5 | `bonus_overflow_opp` | A | same for the opponent cap. Note opp-cap moves were the worst C5 cells (oppcap4 −59.6, oppcap12 −66.8). |
| 6 | `road_anticip_diff` | A | **road closure anticipation.** The leaf's bonus covers cities / cloisters / farm-growth and gives roads **exactly zero**. Review **P1-L6**; **NEVER ISOLATED** (C7 Term R bundled roads into a harmful liquidity term). `road_root_open_n` already sits in the Decomp. |
| 7 | `open_city_liability_diff` | A | raw at-risk value in my meepled open cities minus opp's. = **BACKLOG 2026-05-16 item #2 "penalize large open cities" — the one lit-review term never implemented and never run.** |
| 8 | `hopeless_city_diff` | A | meepled unfinished cities with `open_n ≥ 4`, where `closure_p` truncates to 0. The schedule's right tail. |
| 9 | `city_exposure_diff` | A | `Σ city_root_delta × open_n` — tests the **shape** of `closure_p`. Adjacent to C5 `pclose080`/`pclose120` (both sub-gate), but those **rescaled** the schedule; this probes a linear-in-`open_n` mis-shape. |
| 10 | `stuck_meeple_diff` | A | meeples on components that can never close (`open_n == 0`, unfinished — dropped silently by the D16 guard). Adjacent to C7 Term R (HARMFUL) but the **opposite object**: R credited *returnable* meeples; this counts *permanently stranded* ones. |
| 11 | `barren_farm_diff` | A | farm components with **zero** adjacent cities of any kind. Distinct from Term F (dead), which priced contested-field majority flips. |
| 12 | `cloister_far_diff` | A | cloisters needing ≥ 4 more tiles, where `closure_p` gives exactly 0. Schedule right tail, cloister branch. |
| 13 | `open_frontier` | A | `len(state.open_positions)` — how fluid/volatile the board still is. |
| 14 | `frontier_x_leaf` | A | volatility discount: the leaf's edge is worth less on a fluid board. |
| 15 | `leaf_x_tiles` | A | stage-conditioned leaf scaling = review item **M6** "phase-conditioned leaf weights", never implemented. **CL-061 already read this channel as sub-threshold for the value transform (~0.02 nats)** — a null here is confirmatory. |
| 16 | `free_meeples_sum` | A | self+opp free-meeple **total**; the curve prices only the **difference**, so a level effect is unpriced. Distinct from the curve-SCALE axis C5 already peaked. |
| 17 | `deck_city_share` | B | share of remaining tiles with ≥1 city edge. **⚠ ADJACENT TO A 3×-KILLED FAMILY** (deck-aware closure: `tile_counting_closure` + `closure_continuous_slack` null 2026-05-17; `v28_completion` null; `bag_close` null in v2.10 AND again in C5). Included only in a **different functional form** — a global continuous scalar, not a per-feature hard gate. A hit would **not** resurrect `bag_close`; it would name a stage-scalar term. A null is the 4th confirmation. |
| 18 | `n_legal` | **C** | **DIAGNOSTIC ONLY** — needs move generation, so it cannot become a leaf term. Included to see whether the residual is mostly "how many options does the mover have", which would be a *search* story, not a leaf story. |

### Outside the family (not corrected, not gateable)
* `neg_control` — deterministic `uniform(−1,1)` from `blake2b(root_id)`. **Pipeline sanity: it
  MUST land in the null band.** If it does not, the analysis is broken and the run is void.
* `pos_ref_c5_curve` — `curve125_lookup_diff − curve100_lookup_diff`, i.e. **exactly the leaf
  delta that CL-051 added** (+66.8 elo n=400 clairvoyant / +48.8–50.4 fair-confirmed). It is
  already inside `V_leaf`, so it is **not a candidate**; it is reported partialled on the
  *curve100* leaf as a **yardstick** for what a real, adopted, +50-to-+67-elo leaf term looks
  like on this statistic. **The verdict rests on the fixed gate in §5, not on the yardstick.**

## 4. Data, sampling, and the split

**Root corpora (all pre-existing, losslessly replayable via
`scripts/measurement_infra/root_replay.py` — no new deck-seed band is consumed):**

| tag | file | games | generator |
|---|---|---|---|
| `windowaudit` | `measurement/window_audit/gen_games.jsonl` | 1,400 | HeuristicMCTS sims=100, curve100 leaf |
| `champ125` | `measurement/utility_calibration_20260721/gen_games_champ125.jsonl` | 1,500 | HeuristicMCTS sims=100, **curve125** champion leaf |
| `champion` | `measurement/champ_action_logs/champ_games.jsonl` | 449 | **the deployed fair-PIMC champion**, k4×688, seed band 28e9 |

**PRIMARY sample** = `windowaudit` + `champ125` (2,900 games). **REPLICATION sample** =
`champion` (449 games) — the on-distribution check, held to a lower bar because it is ~6×
smaller.

**Sampling rule (deterministic):** TILES-phase plies only (even action indices); eligible band
`tiles_remaining ∈ [20, 55]` (i.e. plies 34…104), which excludes the opening (leaf ≈ 0, low
variance) and the endgame band where the K ≤ 2 solver latches; **3 roots per game**, uniform
without replacement, `random.Random(deck_seed*7919 + 11)`. Expected ≈ **8,700 primary +
1,347 replication** roots. A root that would latch the exact-endgame solver is **rejected, not
labelled** (asserted, not assumed).

**Split — BY DECK SEED, never by position.** Positions inside one game share a board lineage
and are strongly correlated. All out-of-sample quantities come from **5-fold GROUPED
cross-fitting where the group is `deck_seed`** (a game is wholly in one fold). Every root
therefore gets an out-of-fold prediction and the whole sample contributes OOS.

**Effective n.** Reported explicitly: `n_roots`, `n_games`, the residual's intra-game
correlation `ρ_ICC`, the design effect `1 + (m̄ − 1)·ρ_ICC`, and `n_eff = n_roots / deff`. All
confidence intervals are **game-clustered bootstrap** (2,000 resamples **of games**, not of
positions). No CI or p-value in the report may be computed as if roots were independent.

## 5. The test statistic, the correction, and the GATE

**Statistic (per candidate f): out-of-sample partial correlation, cross-fitted.**
Following the standard double/debiased-ML recipe, with the group-5-fold split above:
1. `ê_r = resid − Ê[resid | C]`, where `Ê[·|C]` is an OLS on the control set C fitted on the
   4 training folds and evaluated on the held-out fold.
2. `ê_f = f − Ê[f | C]`, same cross-fitting.
3. `ρ_f = corr(ê_r, ê_f)` over all out-of-fold rows.
p-value from a game-clustered bootstrap of `ρ_f` (2,000 resamples of games), two-sided.

**Multiple comparisons.** Family = the **K = 18 candidates** (controls, `neg_control` and
`pos_ref_c5_curve` are outside it). **Holm–Bonferroni** at family-wise α = 0.05 is the
decision rule; Benjamini–Hochberg FDR at q = 0.10 is reported alongside as secondary
information only.

**THE GATE — declared in advance.** At the primary level L = 688 on the PRIMARY sample:

| verdict | condition |
|---|---|
| **HIT** | some candidate has **\|ρ_f\| ≥ 0.10** AND Holm-adjusted p < 0.05 AND tier ∈ {A, B} AND the **same-signed** partial correlation on the `champion` replication sample with **\|ρ\| ≥ 0.05**. |
| **AMBIGUOUS** | some candidate has Holm-adjusted p < 0.05 with **0.05 ≤ \|ρ_f\| < 0.10**; OR reaches ≥ 0.10 but fails the replication sign/size check; OR reaches ≥ 0.10 but is tier **C** (not leaf-viable). |
| **NULL** | no candidate reaches Holm-adjusted p < 0.05 with **\|ρ_f\| ≥ 0.05**. |

The band **0.05 ≤ \|ρ\| < 0.10 is explicitly the ambiguous band** and does not by itself buy an
S1 screen. With the expected `n_eff` (≈ 5,000–5,500) and Holm at K = 18, the smallest
detectable effect is ≈ \|ρ\| 0.05, so the NULL threshold sits at the detection limit by
construction — i.e. a NULL here is a **powered** null for effects ≥ 0.05, not a
noisy-plateau non-conclusion.

**Pipeline validity conditions (checked BEFORE reading any candidate):**
* `neg_control` must be non-significant. If it fires, the run is void and is re-run, not
  reinterpreted.
* `n_ok / n_attempted ≥ 0.98`, `exact_latch == 0`, and the within-world bit-exactness contract
  of the imported snapshot path must hold on the verification subsample.

## 6. What a HIT triggers, what a NULL closes

**HIT →** the named feature enters the project's standard leaf-term pipeline, **unchanged from
C7's**, and nothing is written to `governance/PRODUCTION.yaml` on residual evidence alone:
* **Stage 0 — cost gate.** Implement in all leaf paths and measure per-leaf cost; **≤ 1.10×
  median** or it does not ship (this is the gate C7 Term R failed at 1.204×).
* **S1 — dose screen.** 3 doses, n = 100/cell CRN on a fresh band, champion vs
  champion+term. Gate (C7's, verbatim): **≥ +35 elo AND paired_z ≥ 1.5** at the best cell.
  A monotone axis pointing at 0 is a null, and re-dosing after a null is forbidden.
* **S2 — n = 400 fresh-band confirm**, deck-paired.
* **S3 — FAIR confirm.** Leaf changes transfer fair by construction (same `LeafConfig` in every
  determinization) but the magnitude does not; S3 prices it. Only S3 can propose a champion
  change, and only Joshua can adopt it.
Estimated cost if it fires: ~1–1.5 dev-days (the 6-path build tax) + ~1–2 box-days of S1–S3.

**NULL →** closes the "leaf accuracy on midgame boards" channel as an autonomous lever, on
top of C7 (CL-055, "the leaf's remaining headroom is NOT in cheap adjacent terms"), CL-034
(offline structural gains wash out under search) and CL-036 (post-search residual is inert to
learned structure). It does **not** claim the leaf is optimal — it claims that **the leaf's
error against its own deep backup is not predicted by any cheap, interpretable, leaf-viable
feature we can name**, which is the strongest available form of "guessing more terms is not
the move".

**AMBIGUOUS →** written up as "a signal exists but below the conversion bar"; no S1 is launched
without Joshua. The named feature and its ρ go on the roadmap as a documented, sized option.

## 7. Honest prior, and the ways this could mislead

Prior ≈ 10–15%, driven down by four independent pieces of prior art:
CL-055 (cheap adjacent terms are dead), CL-034 (a 50-scalar learned comparator beat the leaf
**offline** by −41% sibling regret and **washed out under search**), CL-036 (a typed
feature-GNN on the **post-search residual** was inert), and
`V27_FAILURE_TAXONOMY` (~67% of the leaf's disagreements with stronger references are
structural/horizon, i.e. not leaf-addressable). CL-034 is the sharpest warning: **a statistical
edge on a leaf-accuracy target has already, once, failed to convert to strength.** That is
precisely why a HIT here buys an S1 screen and nothing more.

Threats to validity, declared up front:
1. **Target ≠ truth.** `V_deep` is a 2,752-sim search's belief. Fitting it makes the leaf more
   like this search, which is the CL-062 target but is not the same as making it more correct.
2. **Root distribution.** The primary sample is h100 self-play, ~28× shallower than the
   champion. Mitigation: the pre-registered `champion` replication sample, and CL-062's finding
   that the depth-decay magnitude was near-identical across two materially different root
   distributions.
3. **Deck luck.** `V_deep` pools only 4 determinizations, so it retains real deck-realization
   variance. That inflates the residual's noise and therefore **shrinks** measured
   correlations — it biases toward a NULL, not toward a false hit.
4. **Correlated features.** Several candidates are near-collinear (7/8/9 are all city-exposure
   shapes). Holm is conservative under positive dependence; the full candidate correlation
   matrix is reported so a "hit" cannot be read as 18 independent chances.
5. **A linear probe.** The controls and probes are OLS. A purely non-linear residual structure
   would be missed. Accepted deliberately: a term that cannot be written linearly cannot be a
   cheap leaf term either.

## 8. Free-pass corpora (hypothesis generation ONLY — can never be the verdict)

Two already-on-disk sets are used **first**, to validate the pipeline end-to-end and to see
which features look alive:
`measurement/gate_b_fair_pimc_champion/` + `measurement/gate_b_depth_transfer_champion/`
(436 champion-distribution roots each) and `measurement/f3_public_state_oracle/`
(exact-solver-solved roots). **Both are `k_remaining = 3` ENDGAME boards.** They are
mechanically incapable of passing or failing the §5 gate — every write-up of them, here and in
`REPORT.md`, is labelled **ENDGAME-BOUNDED, HYPOTHESIS-ONLY**. No threshold, no correction and
no verdict is derived from them, and a feature that looks alive there gets **no** advantage in
the primary analysis: the §3 dictionary is frozen by this commit, before the free pass runs.

## 9. Artifacts

`PREREG.md` (this file) · `leaf_features.py` (the dictionary) · `mine_residual.py` (labeler,
emits `manifest_*.json` computed from the resolved config) · `analyze_residual.py` (the
pre-registered estimator + gate arithmetic) · `records*.jsonl` · `REPORT.md` (results +
verdict). Close-out: `experiments/results.csv` row, a `governance/CLAIM_REGISTRY.csv` claim,
status banners here and on `REPORT.md`, the `STATUS.md` top block, a
`docs/PROGRAM_ROADMAP_2026-07-07.md` line, and `python3 scripts/doc_lint.py` clean.

---

## AMENDMENT 1 — 2026-07-21, BEFORE any primary fit result

**What changed:** §4 said TILES-phase roots are "the even action indices". That is factually
wrong for some games: the engine **skips the meeple phase** whenever the mover has no placeable
meeple, so any game containing such a turn has its action-index parity flipped from that turn
on. The pre-flight caught it — 3 of 48 roots landed in MEEPLES phase, all three in a single
game (`windowaudit` deck_seed 7000013), and the harness's phase assertion rejected them loudly
(working as intended).

**The correction:** TILES-phase selection is now determined **by replay, not by parity**. If the
sampled ply replays into a MEEPLES state, the harness applies that single meeple action to reach
the next TILES phase and labels that root, recording `ply_used` and `ply_shifted` on every
record. From a MEEPLES state one action always lands on TILES, so the shift is at most 1 ply and
`tiles_remaining` is unchanged.

**Why this is a bug fix and not a plan change:** the pre-registered *intent* — "TILES-phase
midgame roots, 3 per game, drawn uniformly from the eligible band by a deck-seed-seeded RNG" —
is unchanged; only a broken implementation detail of *how a TILES ply is identified* is fixed.
Nothing about the residual definition, the feature dictionary, the split, the correction or the
gate moves. No primary fit result had been computed when this was made.

## AMENDMENT 2 — 2026-07-21, BEFORE any primary fit result: depth levels + measured ETA

Per-world snapshot levels are **{200, 344, 688, 1376}** (totals k4×… = 800 / 1376 / 2752 /
5504). §2's primary level is unchanged at **L = 688** (the deployed k4×688 = 2752 budget); 1376
is a free-ish secondary that supports the depth-trend read (does the residual's structure
strengthen as search deepens?).

Measured pre-flight at production knobs (laptop, W=10, same levels/k_dets/leaf as the scaled
run): **45/48 ok, median 5.89 s/root**, `resid(688)` mean +0.067 sd 0.141. At W=12 over the
10,047 pre-registered roots (8,700 primary + 1,347 replication) that is **≈1.4–1.7 h wall-clock
on the laptop** — well inside the box-night budget, so no scope reduction is needed.

**Box assignment:** laptop only. The local box is running another agent's B3 capacity-probe
ladder (~8–13 h) after a WSL VM teardown caused by that job's memory footprint, so it is not
used here even though this workload is memory-light (~100 MB/worker).
