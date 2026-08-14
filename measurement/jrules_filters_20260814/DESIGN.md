# J-RULES SURFACE C — the anchor's HARD FILTERS as ROOT FILTERS on the champion's fair-PIMC root

> **STATUS AT WRITING: 🔧 BUILT + PROVEN DEFAULT-OFF — 2026-08-14. Code on the
> worktree branch, DEFAULT-OFF everywhere.**
> **0 games · no band claimed · no `results.csv` row · no claim minted ·
> [`governance/PRODUCTION.yaml`](../../governance/PRODUCTION.yaml) untouched ·
> [`governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) untouched.**
> Nothing in this document is a strength statement. The only strength numbers
> below are surface A's, surface B's and CL-080's, quoted as evidence about
> *other* levers. The calibration state is stamped in
> [`CALIB_READOUT.md`](CALIB_READOUT.md) when it exists; the read-rule
> ([`CALIB_READ_RULE.md`](CALIB_READ_RULE.md)) was committed BEFORE any rate
> was read.

Parents:
* [`../jrules_on_search_20260813/`](../jrules_on_search_20260813/DESIGN.md) —
  **surface A** (static leaf terms), RAN 2026-08-13, adjudicated *loss,
  confounded by budget* (margin −2.4912 pts/deck, z −3.8564, elo −33.98 ±
  12.34, n=800; `ms_ratio` 1.2116 > the 1.20 N4 trigger). Its §7 scope names
  "J10f + J3's hard floor (root filters, deferred, not built)" as untouched by
  every branch — **this build is those filters**.
* [`../jrules_priors_20260814/`](../jrules_priors_20260814/DESIGN.md) —
  **surface B** (PUCT priors), RAN 2026-08-14, a MEASURED CLEAN NULL (margin
  −0.0175 pts/deck, z −0.0282, elo −3.0 ± 24.6 at 2σ; `ms_ratio` 1.1751 <
  1.20). The pre-registered failure mode fired: **the sims-washout** — 11,008
  sims of PUCT washed out a demonstrably-live 13.05%-pick-flip prior
  perturbation entirely.

This is the **last untested encoding surface** for the anchor's strategy on
the champion's own search.

---

## 1. Why a root filter might differ where priors did not — and why it might not

**The mechanical argument.** A prior BIASES visit allocation, and the search
can override it with evidence — surface B measured exactly that: the boost
flipped 203/1,556 champion picks in shallow-consultation (the calibration
proved it live and expressive), and 11,008 sims of PUCT then returned the
leaf's own verdict anyway. More search = more washout; the prior surface is
*advisory* by construction.

A root filter has the opposite shape. It **removes actions from the root
candidate set before the search runs**. A removed action gets zero visits in
every determinization, never enters the pooled (N, W) accumulators, and cannot
win the pooled-Q argmax — **no amount of search brings it back**. It is the
strategy expressed as a CONSTRAINT rather than a preference. The washout
mechanism that nulled surface B *cannot* null surface C: where the bot's rules
disagree with the champion's pick, the filtered agent is FORCED off the
champion's move.

**Why the CL-080 / surface-A mechanism does not apply either.** Both leaf-term
losses shared one named mechanism: the **double-count** — a static term
re-pricing what the 11,008-sim search already prices, distorting every backed-up
value. A filter adds no score anywhere. Leaf values, priors, backups and the
pooled-Q rule are all the unmodified champion's; the only change is *which root
children exist*.

**The danger, stated as plainly as the promise.** A prior that is wrong gets
outvoted; a filter that is wrong throws the best move's evidence away
**unexaminably**. When F-J10 drops the winning early farm claim, the champion's
own 11,008 sims of knowledge about that move are discarded, not weighed. This
is the most aggressive of the three encodings, and its failure mode is a clean,
attributable LOSS (not a null): every excluded champion-preferred move is a
forced deviation to the search's second choice.

**Weaknesses of the argument, up front:**

1. *The filter only binds where the rules and the champion disagree* — and the
   bot's hard filters encode caution (don't farm early, don't spend the last
   meeple, don't pass in the endgame). If the champion already obeys them most
   of the time, the exclusion rate is small and an n=800 cell cannot resolve
   the effect (the calibration's NO-EXPRESSION branch exists for exactly this).
2. *Forced deviation ≠ better play.* The honest prior from the whole
   hand-crafted record (CL-055/063/074/078/079/080, surface A, surface B) is
   LOSS OR NULL; for a filter specifically, the directional prior is LOSS,
   because every binding event overrides a deeper search with a shallower rule.
3. *The rules were calibrated on the bot's one-ply base, not at depth.* The
   thresholds (block fractions, reserve floor) were interviewed and
   tournament-tuned on a greedy base; at 11,008 sims the same thresholds may
   bind at the wrong times. §7 of the prereg scopes the verdict accordingly:
   this prices THE ENCODING at this mask, not the strategy.

**What the cell buys either way:** with A = a budget-confounded loss and B = a
clean null, a clean surface-C result of ANY sign completes the triptych — the
same human strategy priced as (a) evaluation, (b) advice, (c) constraint. A
loss here would close the last encoding surface with the double-count excuse
unavailable; a win would be the first positive human-strategy transfer in the
program's record.

## 2. Where the filter binds — the real production path

The champion of record (`governance/PRODUCTION.yaml champion.fair_deploy`)
plays through **`carc_core::fair::FairAgent`** (rust; python adapter
`rust_agent.RustFairAgent`): per move it draws `k_dets=8` determinizations,
runs a fresh 1,376-sim PUCT search per world, merges the deduped root stats
and picks by pooled-Q. **Root candidates are assembled per world inside
`Searcher::evaluate` at the root expansion** (`legal_actions()` → Δleaf softmax
priors), and the cross-world decision is `pooled_q_argmax`.

The filter binds at the START of `FairAgent::pimc_move` (`fair/mod.rs`):

1. after the forced-move short-circuit, **before** the determinization RNG is
   even constructed (the filter consumes no randomness — placement is provably
   inert to the RNG stream);
2. `fair::jrules_filter::jrules_root_filter(g, mask, min_keep)` runs ONCE on
   the TRUE root (every input is fair information: the board, both reserves,
   `k_remaining`);
3. the surviving candidate set is handed to every world's search as a
   ROOT-only allowlist (`Searcher::search_with_root_allow`): the root
   expansion's `legal` is restricted to it, so the prior softmax renormalizes
   over the survivors and **no simulation can ever visit a dropped action**;
   interior nodes are untouched (this is deliberately NOT the costlier
   in-tree surface);
4. pooled stats and pooled-Q then see only kept actions by construction.

**Deliberate scope of the binding, documented:**

* **MEEPLE-phase roots only** — fidelity to the bot: `joshua_bot._apply_filters`
  runs only on meeple candidates (tile candidates are shaped by the filters
  only *inside* its scoring lookahead, which has no analogue here).
* **PIMC decisions only** — forced moves (bot precedence 0) and exact-solver
  decisions (`k ≤ exact_K = 2`, where F-J3 has released and F-J10/F-J9 cannot
  bind) are untouched. A `BudgetExceeded` solver fallback re-enters
  `pimc_move` and IS filtered (F-END can legitimately bind there).
* **Python fair agent: fail-loud, not implemented** — surface C is rust-only
  (`make_heuristic_prior_evaluator` raises on a set mask), same rule as
  surface B.

## 3. Encoding table — the bot's hard filters, what is and is not expressed

Applied in the bot's FIXED order; each filter individually guarded (§4).
Parameters are `joshua_bot.PRESETS["current"]` — the tournament-selected epoch
— FROZEN as `JF_*` constants and pinned by
`tests/test_jrules_filter.py::test_constants_match_joshua_bot`.

| bit | filter | predicate (verbatim from the bot) | not expressed / deviations |
|---|---|---|---|
| 1 | **F-END** endgame deployment | `k_remaining <= my_reserve` ⇒ drop PASS (an unplaced meeple is wasted points). Overrides J3. | — |
| 2 | **F-J10** early-farmer block | `k > 0.55·k0` ⇒ drop every FARMER claim (the J10 "current" epoch's stated adaptation) | ⚠️ `k0` FROZEN at 72 (`JR_K0` precedent — the bot latches k0 at its first move, = 72 in every real game); the farm-aggressive `early` epoch (frac 0) is not a rung |
| 4 | **F-J9** cloister caution | `k > 0.55·k0` ⇒ drop CLOISTER claims unless the 3×3 already holds ≥ 6 tiles | the bot's OPT-IN axis, default OFF, tournament no-conviction (z −1.47) ⇒ **not in the `current` stack**; the bit exists for the `all` ablation arm only |
| 8 | **F-J3** own-reserve floor | not endgame ∧ `k > 8` ∧ `my_reserve ≤ 1` ⇒ drop meeple placements unless the feature **finishes this turn** (`closes_own`) or the placement **ties/takes a contested feature** (`swings_majority`, counts read on the child afterstate) | ⚠️ the `j8_break_reserve_floor` pivotal-overcommit exemption is FROZEN OFF (the selected preset carries `False`); a `j8brk` variant is a named, unexercised option needing its own calibration |

Mask semantics: **11 = END|J10|J3 = the bot's `current` stack** (the primary
candidate); 15 adds F-J9; single bits are the ablation arms. A filter is
binary — **there is no dose**, which is why the calibration ladder is the mask
lattice, not a dose ladder.

## 4. Knobs — SearchConfig-side, like surface B; the never-empty guard

| knob | default | semantics |
|---|---|---|
| `jrules_filter_mask` | **0 = OFF** | mask 0 short-circuits before any filter code runs — the champion, bit-for-bit. ⚠️ Unlike `jrules_prior_mask`, **0 is VALID here — it IS the off state** (a filter has no dose knob) |
| `jrules_filter_min_keep` | 1 | **the never-empty guard**: a filter that would leave fewer than `min_keep` root candidates YIELDS (is skipped for that ply) and the yield is counted. `min_keep=1` is exactly the bot's own "skipped if it would empty the candidate set" (F-J3's precedent named in the brief). The guard is per-filter, in application order, exactly as the bot's `_keep` is |

⚠️ **BECAUSE THESE ARE NOT LEAF FIELDS, NO LEAF HASH MOVES** (verified: the
live-mask config's leaf hashes `a36d2e15a3b3d71d`, equal to the champion's).
Every moved-hash wiring gate is INERT on this surface — liveness is proven by
(1) the RESOLVED `cand_jrules_filter.{mask,min_keep}` in the manifest, (2) the
construction-time positive control (`_assert_surface_c_live` — a pinned root
where F-J10 provably drops a farmer claim), and (3) the per-game
`cand_jf.dropped_total` telemetry summed over the cell (**the filter must have
fired at least once, or the cell is a champion-vs-champion null wearing a
measurement's shape**).

Yield counts are surfaced everywhere the drop counts are: per move
(`last_move.jf_yields`), per game (`stats().jf_yields`,
`GameResult.cand_jf.yields`), per calibration ply (`yield_<arm>`), and in the
rollup (`yield_rate` — the SAFETY branch's input).

## 5. What was built

| surface | change |
|---|---|
| `carc-core/src/fair/jrules_filter.rs` | the filter: `JF_*` frozen constants + mask bits, per-action tags (`_tag_meeple` ported — farmer/cloister geometry cheap, F-J3's child-afterstate tags computed lazily only when F-J3 is armed), the four filters in order with the per-filter `min_keep` guard, `FilterOutcome{kept, dropped, fires, yields, applicable}` |
| `carc-core/src/fair/mod.rs` | `FairAgent::pimc_move` binding (§2); cumulative counters `jf_fires/jf_yields/jf_dropped_total/jf_applicable_moves`; `MoveInfo.jf_*`; `search_worlds(..., root_allow)`; the pathological empty-pool fallback stays inside the kept set |
| `carc-core/src/search/mod.rs` | `SearchConfig.jrules_filter_{mask,min_keep}`; `Searcher.root_allow` + `search_with_root_allow` (root-expansion-only restriction; an emptied root fails LOUD — unreachable behind the guard) |
| `carc-py/src/lib.rs` | `SearchConfigRs` trailing kwargs (validated even at mask 0) + `jrules_filter` getter + live-only repr suffix; `FairAgentRs.stats()/last_move()` jf keys; **`jrules_filter_probe` on BOTH `MirrorState` (parity surface) and `FairAgentRs` (the instrument's per-ply read)** |
| `heuristic_prior_mcts.py` | `HeuristicPriorConfig.jrules_filter_{mask,min_keep}` + validation + `as_manifest`; `make_heuristic_prior_evaluator` fail-louds on a set mask (rust-only) |
| `rust_agent.search_config_rs` | conditional kwargs — forwarded ONLY when the mask is nonzero, so a stale `carc_rs` serves every champion config and raises `TypeError` on a live mask (fail-closed loud; **verified live against the installed pre-C wheel**) |
| `jrules_filter.py` | the python REFERENCE MIRROR (parity target; never a production path) |
| `eval_fair_puct.py` | `--cand-jrules-filter-{mask,min-keep}` (candidate side ONLY), launch-time stale-wheel probe, `[smoke]` liveness banner, manifest key `cand_jrules_filter` (the RESOLVED dict), `GameResult.cand_jf` per-game liveness telemetry |
| `jrules_filter_e4_replay.py` | the calibration instrument (§8) |
| tests | `tests/test_jrules_filter.py` (22) + `tests/test_jrules_filter_e4_replay.py` (17) + 6 rust unit gates (4 in `fair/jrules_filter.rs`, 2 in `fair/mod.rs`) |

## 6. Proofs (this worktree's wheel, pinned toolchain 1.96.0)

| proof | status |
|---|---|
| **BIT-IDENTITY, F-c style** — the F-c golden gate re-run on this wheel: **208 real production searches** hash to the RECORDED pre-F-c digest `6cd80a92…` (736,607 leaf evals; `tests/test_window_truncation_failloud.py`) | ✅ both tests pass — chains the proof back through F-c to the recorded baseline |
| champion leaf fingerprint `a36d2e15a3b3d71d` recomputes unchanged; the LIVE-mask config's leaf hash EQUALS it (the inverted gate) | ✅ |
| mask-0 with a MOVED `min_keep`, byte-identical fair agent (pooled floats bit-for-bit) | ✅ rust unit gate + the pyo3 twin |
| live filter restricts the PIMC root: chosen action ∈ kept, pooled pool ∩ dropped = ∅, counters record the drop | ✅ rust unit gate + the pyo3 twin |
| never-empty guard yields instead of emptying; kept ∪ dropped == legal in order | ✅ rust unit gates |
| **rust ↔ python filter parity on replayed games** — applicability, kept/dropped sets, per-filter fire/yield flags, 2 seeds × 4 masks (11/15/2/8), ≥60 plies each ≥10 applicable | ✅ `test_rust_python_filter_parity_on_replayed_games` |
| stale wheel: default-off configs served; nonzero mask → `TypeError` at `search_config_rs`; harness probes at LAUNCH | ✅ verified live against the installed pre-C wheel |
| stale wheel: test suite **SKIPS LOUDLY** (11 skips naming the per-box rebuild) instead of passing vacuously | ✅ 11 passed / 11 skipped observed |
| neighbours undisturbed | ✅ `test_jrules_priors` + `test_jrules_term` + F-c suite green · `rustport/test_p3_search` + `test_p4_fair` green · carc-core `cargo test` **116 passed** · `reconcile_leaf --configs jrules --corpus golden` **83,824 values, 0 mismatches** on this wheel |
| end-to-end: `eval_fair_puct --smoke --backend rust --cand-jrules-filter-mask 11` plays clean with the liveness banner | ✅ |

⚠️ **PER-BOX REBUILD FOOTGUN (unchanged from surfaces A/B):** every box that
runs anything surface-C must rebuild + reinstall the `carc_rs` wheel
(`maturin build --release` in `rust/carc/carc-py`), then re-run
`tests/test_jrules_filter.py` (0 of the 11 rust-gated skips may fire) and the
F-c golden gate there. A stale box is fail-closed (TypeError), never silent.

## 7. Cost — MEASURED

A root filter runs **once per meeple-phase move** (not per node). Two figures,
measured on the local 5900XT (idle box), production geometry:

* **The probe alone** (what the calibration pays): see
  [`CALIB_READOUT.md`](CALIB_READOUT.md) `mean_secs_per_graded_ply` — the
  probe is microseconds against a multi-second champion search.
* **Full-agent A/B at deploy budget** (what the cell pays): mask 11 vs mask 0
  on identical fixed roots, k8×1376, same seeds — see
  [`COST_BENCH.md`](COST_BENCH.md). Expectation: ≈1.00× (the filter's tag
  computation is one decomposition per candidate meeple action AT MOST — and
  only on plies where F-J3 is armed — vs 11,008 search decompositions), and a
  live drop can make the move CHEAPER (fewer root children). The prereg still
  carries the N4 `ms_ratio` 1.20 trigger read off the real cell, as always.

## 8. Calibration — instrument + read-rule (committed BEFORE any rate)

* **Instrument:**
  [`jrules_filter_e4_replay.py`](../../scripts/classical_search/jrules_filter_e4_replay.py)
  — the surface-B instrument's sibling over the SAME banked E4 corpus (**31
  archives** at grading time), same graded-ply rule, same budget-from-archive
  rule, same CRN seed, per-ply resumable, one subprocess per archive. The one
  structural difference: **a filter's flip rate IS its exclusion rate** — per
  graded ply ONE champion search names `champ_pick`, then every arm is a pure
  probe (`FairAgentRs.jrules_filter_probe`): `excluded = champ_pick ∈ dropped`.
  No candidate searches are bought. ⚠️ Disclosed limit: exclusion is a LOWER
  bound on behavioural change (visit reallocation among kept actions is
  uncounted; counting it costs surface B's price per arm and is not bought for
  a calibration).
* **The ladder** (pre-registered; a filter has no dose, so the mask lattice IS
  the ladder): `j10:2` · `j3:8` · `current:11` · `all:15`, `min_keep=1`
  everywhere.
* **Read-rule:** [`CALIB_READ_RULE.md`](CALIB_READ_RULE.md) — committed in
  this same worktree branch **before any arm's exclusion rate has been read by
  anyone**. FUND-SMALLEST in the 10–25% window; NO-EXPRESSION stop branch; and
  the new **SAFETY branch**: a guard-yield rate above 5% of graded plies marks
  the config malformed (the rules contradict the position too often) and it is
  not funded regardless of its exclusion rate.
* **Positive control** (`_assert_surface_c_live`): pinned root where the
  F-J10 probe provably drops a farmer claim — runs before any grading, per
  process, because no hash can prove this surface live.

## 9. Deploy cell — DRAFT prereg

[`DEPLOY_PREREG.md`](DEPLOY_PREREG.md) — cloned from surface B's adjudicated
prereg: n=800 deck-paired (400 decks × 2 seats), fair PIMC k8×1376 = 11008
BOTH arms, rust both sides, `fixed_v1` + R9, exact-K 2 shared, margin z
primary, N0–N5 branch map with the `ms_ratio` 1.20 N4 trigger, **band =
`CLAIMED-BY-ORCHESTRATOR` placeholder**, workers laptop W22 / local W30, and
the wiring gates including the three surface-C liveness gates (§4). It is a
DRAFT until the calibration names a mask and the owner claims a band.

## 10. Expectation management

The pre-stated prior is a **LOSS or an unresolvable small effect**, and unlike
surface B the interesting failure mode here is the LOSS: every binding event
substitutes a one-ply-calibrated rule for an 11,008-sim search verdict. What
is genuinely different this time: (i) the washout CANNOT null it — a filtered
move stays filtered at any sims; (ii) the double-count CANNOT sink it — no
score is added anywhere; (iii) the encoding is the bot's own hard-filter code
path, predicates and order intact, with the two freezes (§3) disclosed. The
value of the cell is that it completes the encoding triptych: evaluation
(lost, confounded), advice (clean null), constraint (this). A powered result
of either sign closes the "how should human strategy enter the search"
question for this anchor's ruleset.

## 11. Launch-blocking gates

| # | gate | state |
|---|---|---|
| **C-G1** | worktree merged to the main tree at a quiet window | ⛔ pending |
| **C-G2** | `pytest tests/test_jrules_filter.py` green on the run box with its wheel (22 pass, 0 of the 11 rust-gated skips firing) | ✅ on this worktree's wheel; **per-box** |
| **C-G3** | `carc_rs` wheel rebuilt on EVERY box that runs anything — F-c golden digest + `reconcile_leaf --configs jrules` + the 22 tests re-run there | ✅ local worktree wheel; ⛔ main venv + laptop |
| **C-G4** | the instrument's positive control passes on the run box (`_assert_surface_c_live` — runs automatically at every grading) | ✅ this wheel |
| **C-G5** | calibration ladder run + `CALIB_READ_RULE.md` applied mechanically | see `CALIB_READOUT.md` |
| **C-G6** | fresh band claimed in `governance/BAND_REGISTRY.csv` | ⛔ owner's call |
| **C-G7** | first-block `ms_ratio` read from the cell against the §7 expectation (≈1.00×) | ⛔ at launch |
