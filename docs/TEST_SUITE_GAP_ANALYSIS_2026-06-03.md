# Test-suite gap analysis (review agent, 2026-06-03)

> **Status: CLEAN-HISTORICAL** — point-in-time review-agent record; the actioned items live in REVIEW_LOG.md.

**Inventory:** 40 test files, **363 tests**, ~6,260 lines in `tests/`. Plus 3 standalone
`scripts/verify_*.py` that are **NOT in the pytest tree** (never run as regression gates).

**Headline:** two of the four shipped bugs (C1, C2) are guarded ONLY by those un-wired verify
scripts → reintroducing C1 (farm double-count) would leave all 363 tests green. The central
failure **F-B1 (learned value never in the search loop) has no test at all.** The v2.7 leaf,
symmetry aug, and `find_farm` start-independence are genuinely well covered.

## Bugs-shipped → would a current pytest catch a regression?
| Bug | Caught? | Gap / test to add |
|---|---|---|
| **C1 farm double-count** (`count_farm_points`) | **NO** — no pytest touches it; only `scripts/verify_farm_dedup_fix.py`. `test_farm_index.py:107` even asserts the *old* identity-set behavior. | Port the verify script: random games → every farm `count_farm_points == position-set-dedup ref`. |
| **C2 visit transposition** | **PARTIAL** — `test_transposition_table_shares_nodes…` pins node-sharing, not visit-dedup. `test_root_visit_distribution_matches_search_output` is circular (two views of same struct). | Force a symmetric collision; assert deduped vector shares no child + mass == unique-child sum. |
| **C2 selection residual** (`child_canon`/`child_aliases`/`_select_child_puct`) | **NO** — zero pytest references these symbols. | Pin the alias invariant (1 canonical + n−1 skipped aliases, folded prior). |
| **Engine farmer-adjacency** (start-dependent `find_farm`) | **PARTIAL→mostly YES for mechanism** (`test_find_all_farms_matches_find_farm` pins start-independence), **NO for the process dimension** (bug only showed across processes; suite is all single-process). | (a) `opposite_farmer_side` is an involution; (b) cross-process: same seed → identical scores across spawned workers. |
| **F-B1 value-not-in-loop** (central failure) | **NO** — no test asserts the net *value* (vs priors) changes a move. Blend tests check arithmetic only. | Two evaluators differing only in value → different `best_action`/visits; + guard that prod play routes net value into the leaf. |

## Critical contracts with NO/weak coverage (risk-ranked)
1. **`count_farm_points` (C1 path)** — reward signal + leaf farm term; script-only. HIGHEST.
2. **NeuralMCTS value→move influence (F-B1)** — Stage B's whole thesis; can silently regress to leaf-only.
3. **C2 selection dedup (`child_canon`)** — touches every symmetric-tile policy target.
4. **Cross-process scoring determinism** — the exact farmer-adjacency failure mode; untested.
5. **Tied-feature scoring engine patch** — documented fix, zero coverage.
6. **`value_blend` end-to-end** — math pinned (test_evaluators), but not that the blend *steers MCTS*.

Well-covered (don't spend effort here): symmetry aug (16 equivariance asserts), open_positions/placed_coords sync, find_all_farms start-independence, v2.7 leaf invariants, self-play target encodings + mask integrity + save/load, canonical perspective flip, NaN/inf/negative-prior hardening.

## Weak/brittle tests to fix
- `test_root_visit_distribution_matches_search_output` — circular, masquerades as C2 coverage; make adversarial.
- `test_run_phase4_smoke.py` — CLI-arg routing only, no gameplay (fine, just not self-play coverage).
- `test_evaluators.py` — shape/finiteness smoke by design (fp16 numerics need GPU); evaluator numeric contract untested in CI.
- `test_v2_matches_v1_at_terminal` — loose (`same sign OR within 5pts`).
- Determinism tests lean on global `random.seed()`; cross-file RNG ordering is a latent fragility.

## Top 5 tests to add (highest ROI first)
1. ✅ **DONE (be46466)** `count_farm_points` == position-set-dedup ref over random games (C1) → `tests/test_farm_dedup_c1.py`.
2. ✅ **DONE (be46466)** Net VALUE (via value_blend) changes a NeuralMCTS search (F-B1) → `tests/test_value_in_loop_fb1.py` (guards the G-S1 wiring).
3. ✅ **DONE (be46466)** MCTS visit-dedup collision-free + mass==unique-sum + `child_canon` alias structure (C2) → `tests/test_mcts_transposition_c2.py`.
4. ⬜ Cross-process scoring determinism: same seed → identical scores across spawned workers (farmer-adjacency class). *Still open (multi-process, fiddly).*
5. ⬜ Tied-feature scoring pays all tied owners in full (engine patch). *Still open (needs a constructed tied feature).*

**Status:** top 3 (the two worst regression holes C1/C2 + the Stage-B-guarding F-B1) CLOSED
overnight; all 3 pass with teeth-assertions confirming they exercise the bug-prone paths.
#4 and #5 remain (lower urgency; deferred — #4 contends with running jobs, #5 needs careful
engine setup). The verify scripts are now superseded for C1/C2 by the pytest ports.

**Cheapest move:** wire the 3 `scripts/verify_*.py` into pytest (or port their core asserts) —
closes #1 and #3 immediately, since they already encode exactly the C1/C2 checks.

*Acting on this (writing the tests) is deferred — Joshua's call on priority/design. #2 is the
one most worth adding alongside the Stage-B merge (it guards the G-S1 value-in-loop wiring).*
