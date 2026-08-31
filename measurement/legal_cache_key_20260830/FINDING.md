# The `_legal_cache` non-injective memo key — FIXED, DEFAULT-ON (2026-08-30)

**Status: FIXED 2026-08-30** on the owner's `promote.` against the parked roadmap row
(`05ed019c`). Scope: **python tooling correctness only.** No banked number is edited, no
`governance/PRODUCTION.yaml` field moves, no claim row flips, no strength game was played.
The deployed rust arbiter path was measured HONEST by OM-D2 and is untouched.

⛔ **Banked artifacts keep their numbers.** Every tool that measured under the buggy mask
keeps what it published; the remedy is *supersede-by-rerun*, never a retro-edit. The
re-run list is §6 — listed, not run.

---

## 1. The root cause, in one sentence

`Game.get_valid_moves` memoized the legal mask under `Game.string_representation`, whose
per-tile component `(4 outer edges, shield, chapel, flowers)` is **blind to rotation on a
180°-rotationally-symmetric tile** — the outer edges tie at rot 0 and rot 2 while the
tile's **farm slots** rotate — so two genuinely different sibling afterstates shared one
key and the second was served the first's mask, offering a farmer corner that is
**illegal** there and withholding the legal one.

## 2. The dependency set the key must be injective over

Derived by reading the mask computation, not by guessing
(`Game._compute_mask` → `ActionUtil.get_possible_actions` →
`PossibleMoveFinder.possible_meeple_actions` / `TilePositionFinder`):

| the mask depends on | in the OLD key? | in the NEW key? |
|---|---|---|
| every placed tile's coordinate + description | ✅ | ✅ |
| every placed tile's 4 outer edges / shield / chapel / flowers | ✅ | ✅ |
| **every placed tile's farm-slot geometry** (`farmer_positions` / `tile_connections` / `city_sides`, and their ORDER) | ❌ **the defect** | ✅ `_farm_slot_signature` |
| all players' `placed_meeples` (region-occupancy veto) | ✅ | ✅ |
| current player's `meeples` supply | ✅ | ✅ |
| `big_meeples` / `abbots` supply (gate whole action families) | ❌ | ✅ |
| `phase`, `current_player`, `scores`, `len(deck)`, `last_tile_action.coordinate` | ✅ | ✅ |
| the drawn `next_tile` identity | description only | ✅ full rotation signature |
| `board.offset` (feeds `encode`) | implied by placed coords + per-`Game` window size | same |
| `supplementary_rules` (FARMERS), the R9 farm-data latch | per-`Game` / per-process constants; the memo is per-`Game`, so they cannot cross-contaminate one cache | same |

Two subtleties worth pinning:

* **Farm-slot ORDER is load-bearing, not cosmetic.** `__possible_farmer_position` emits
  `farmer_connection.farmer_positions[0]` as the placement Side. `straight_road` at rot 0
  and rot 2 has the *same two farm regions*, but the slot lists are permuted, so the two
  rotations emit **different farmer action ids** for the same physical field. A key that
  saw only the regions would still collide.
* **It is not only the last-placed tile.** `FarmUtil.find_farm` / `CityUtil.find_city` /
  `RoadUtil.find_road` traverse NEIGHBOURS, so the farm geometry of every reachable placed
  tile selects the region and hence the occupancy veto. That is why the signature is
  folded into **every** placed tile, not just `last_tile_action.tile`.

## 3. Default-ON, and why (the flag decision)

`CARCASSONNE_FIX_LEGAL_CACHE_KEY` was introduced DEFAULT-OFF when the bug was parked. It
is now **DEFAULT-ON**.

* **The R9 / `fixed_v1` latch precedent does not apply.** Those are opt-in because they
  *move engine semantics* — a leg run with R9 on is playing a different game, so it must
  declare itself. This changes no semantics at all: nothing about what a legal move IS
  moves, and every honestly-computed (cache-off) quantity is bit-identical before and
  after. The flag only stops the memo returning **another board's answer**.
* **The reproducibility need is narrow and belongs on the other side of the flag.** Exactly
  one class of work legitimately wants the old behaviour: *replaying a corpus banked under
  it* — above all the tiearb2 Stage-2 rust port's `LegalMaskCache`
  (`legal_mask_cache=True`), built to reproduce the BURNED, unregeneratable Stage-1b bank
  bit-for-bit. Making bug-reproduction the thing that must declare itself is the house rule
  for banked numbers (supersede-by-rerun, never retro-edit) — and it fails safe: a tool
  that says nothing now gets the correct mask, where before a tool that said nothing got
  the wrong one.
* **The rust side is unaffected either way.** `carc-core`'s `LegalMaskCache` carries its
  own key in rust and never reads this env var, so
  `tests/test_tier1_rust.py::test_the_memo_collision_is_real_and_is_what_the_bank_carries`
  still passes unchanged and the G-BITEXACT contract still holds.

**ROLLBACK LEVER:** `CARCASSONNE_FIX_LEGAL_CACHE_KEY=0` in the environment (import-latched,
like `CARCASSONNE_FIX_R9`). It restores the historical key **byte-identically** — the new
components are APPENDED to the key tuple, so the legacy string is unchanged rather than
merely equivalent. It is recorded in every run manifest (`run_manifest._LEAF_ENV_KEYS`), so
a legacy-key run is self-describing. In-process, tests use the `legacy_cache_key` pytest
fixture (`tests/conftest.py`), which also clears the per-Tile signature memo on both sides
of the flip.

## 4. Blast radius that is NOT "tooling only"

`string_representation` is **also the python MCTS transposition key**. Under the old key,
two rotations of a symmetric tile folded onto ONE tree node; under the new key they do not.
So any scripted **python**-MCTS line moves. Three tests encode that:

* `tests/test_intra_reuse.py::test_bit_exact_off_matches_pre_change_fixture` and
  `tests/test_meeple_equiv.py::test_bit_exact_off_matches_pre_change_fixture` — goldens
  banked pre-flip (one pins a literal `final_key`). **Pinned to `legacy_cache_key`**, so
  they keep guarding what they were built to guard instead of re-litigating the key.
* `tests/test_mcts_transposition_c2.py::test_mcts_transposition_visit_dedup` and
  `tests/release/test_rotation_alias.py::test_mcts_does_not_double_count_aliased_visits` —
  their teeth are *"an alias exists"*, which is now false by construction. Pinned to
  `legacy_cache_key` (the C2 dedup is still live code: a legacy-key replay still aliases),
  with a new positive test added on the fixed side.

⚠️ **`tests/release/test_rotation_alias.py` is where this hid for months.** It asserted only
that aliased children have the same legal-move **COUNT** — true even when every farmer id
is wrong — and filed the id difference as benign "P1-A3 rotation-alias label
fragmentation". Count-blindness is the reason a release-audit property test passed over a
live defect.

## 5. Gates

Battery: [`run_gate.sh`](run_gate.sh) → [`gate_fuzz.py`](gate_fuzz.py) +
[`cache_effectiveness.py`](cache_effectiveness.py). Both flags are import-latched, so every
cell is a separate process. Artifacts: `GATE_*.json`, `CACHE_*.json`,
[`gate_battery.log`](gate_battery.log).

**The walk BRANCHES on purpose.** A straight-line self-play walk can never exhibit the
defect — it visits one board per ply, so no two live boards ever share a key. The gate
reproduces the shape every affected tool actually has: ONE `Game` whose memo spans SIBLING
afterstates. At every TILES ply it expands **every** legal tile child and reads that
child's meeple-phase mask through the memoized `Game`, against a second cache-DISABLED
`Game` on the very same `Board` object.

### Results — ALL GATES PASS

| cell | key | R9 | games | mask comparisons | mismatches | gates |
|---|---|---|---:|---:|---:|---|
| A | **fixed** | off | 300 | **701,953** | **0** | G-MASK ✅ G-COVER ✅ |
| B | **fixed** | **on** | 300 | **702,097** | **0** | G-MASK ✅ G-COVER ✅ |
| C | legacy | off | 300 | 701,578 | **12,712 (1.81%)** | G-WITNESS ✅ |
| D | legacy | on | 60 | 141,577 | **2,747 (1.94%)** | G-WITNESS ✅ |

**G-MASK.** 1,404,050 meeple-phase masks read through the memo across the two fixed
cells, every one equal to the cache-disabled mask. Both R9 states.

**G-COVER.** Nine 180-symmetric tiles in the deck — `chapel`, `city_left_right`,
`city_narrow`, `city_narrow_shield`, `city_top_bottom_flowers`, `crossroads`,
`full_city_with_shield`, `straight_road`, `straight_road_flowers` — and **all 4
rotations of all 9 appeared** in every cell (`coverage_missing: []`). Both banked
witnesses are heavily represented (`city_left_right` 18,504 placements,
`straight_road` 69,156 in cell A).

**G-WITNESS — the teeth check.** On the *identical* 300 games, the legacy key produces
**12,712 wrong masks**, and the colliding tiles are `city_left_right` and
`straight_road` — **both banked witnesses reproduce the old defect on the old key and
read correct on the new** — **plus `chapel`, a third symmetric tile nobody had named.**
First example, verbatim from `GATE_legacy_r9off.json`: seed 880000000, ply 18, tile
`chapel` rot 1 at (4,14) — `cached_minus_fresh: [2506]`, `fresh_minus_cached: [2507]`,
i.e. the memo offered meeple 2506, which is **illegal there**, and withheld 2507, which
is legal. That is the OM-D2 mechanism reproduced from a cold start.

**G-CACHE — memoization survives the longer key.** One MCTS-driven game (40 plies,
`NeuralMCTS` sims=32 against the heuristic-prior evaluator — the shape the memo was
built for), same seed both modes:

| | hit rate | hits | entries | key bytes | secs |
|---|---:|---:|---:|---:|---:|
| fixed | **0.6649** | 1,782 | 898 | 5,001 | 4.87 |
| legacy | 0.6683 | 1,501 | 745 | 2,232 | 4.52 |

**The hit rate is unchanged (−0.34 pp).** The key roughly doubles in size (2.2×) and the
game costs +7.7% wall — measured on a box saturated by an unrelated eval, so read that
as an upper bound, and note it buys back nothing false. In the branching-census shape the
legacy hit rate looks *higher* (0.207 vs 0.066), but that gap is the collisions
themselves: 12,712 of those extra "hits" are provably wrong answers, and the rest are
hits on keys the injective key correctly separates. **A hit that returns another board's
mask is not memoization.**

**Test suite.** The `game_wrapper` / legal-moves / MCTS-transposition / census surface is
green: 358 tests in the first batch (`test_key_collision`, `test_rotation_alias`,
`test_mcts_transposition_c2`, `test_intra_reuse`, `test_meeple_equiv`), plus
`test_legal_cache_rotation` (6, incl. 3 new), `test_legal_moves_cache`,
`test_string_representation`, `test_game_wrapper`, `test_action_space` (25), and
`test_tiletie_census` (11). ⚠️ Seven failures remain in the wider sweep
(`tests/golden::test_fixture_present_and_configs_frozen`, five in
`tests/release/test_factory_manifest.py`, and
`test_tiearb2_stage2::test_a_NON_EMPTY_wheel_relevant_diff_is_DISPOSITIVE_and_voids`).
**All seven were reproduced at unmodified `HEAD` in a clean throwaway worktree** — they
are pre-existing and unrelated (leaf-config-hash drift, `PRODUCTION.yaml` factory shape,
and a git-history-dependent wheel-diff probe).

⚠️ **Process note, disclosed rather than hidden:** the battery's live stdout log was lost
mid-run. A `git stash` used to take the pre-existing-failure baseline unlinked the log
file the running shell held open, so later cells wrote to a deleted inode.
`gate_battery.log` in this directory is therefore **rebuilt from the per-cell JSON
artifacts the gate itself wrote** (which are the artifacts of record, written with a
fresh `open()` per cell and unaffected). No cell was re-run, no number edited. The
baseline was subsequently taken the right way — a separate `git worktree` at `HEAD`.

## 6. Downstream re-runs this LICENSES (listed, NOT run)

Everything below read meeple-phase masks through a `Game(enable_legal_moves_cache=True)`
whose memo spans sibling afterstates, so its banked rows are computed off a partly illegal
continuation set. **Each keeps its published numbers; a re-run supersedes, it does not
correct in place.** Ordered by how load-bearing the artifact is.

1. **Tile-tie census honest-mask rerun** — `scripts/tiletie/run_census.py`
   (*already approved separately*).
2. **Meeple-tie census** — `scripts/tiletie/meeple_tie_census.py` and its banked copy
   `measurement/meeple_tie_census_20260824/meeple_tie_census.py`. This is the artifact
   OM-D2 localised: the bank **under-counts exact ties** and mis-values chain values at the
   tie partner (`measurement/omd2_chain_values_20260830/`).
3. **EV-loss grader / analyzer replay family** — `scripts/analyzer/ev_loss.py`,
   `replay_stats.py`, `autopsy_extract.py`, `farmwar_stratify.py`, `j13_pregate.py`,
   `f6_winprob_pregate.py`. Grades meeple decisions; pooled-Q rows are affected wherever a
   symmetric tile was the played tile.
4. **The 2026-08-30 mechanism censuses** —
   `measurement/cl083_mech_censuses_20260830/census2_followthrough.py`,
   `measurement/hpm1_fieldfate_gate_20260830/fieldfate_census.py`.
5. **E4 pricing / continuation family** — `measurement/e4_ply_pricing_20260827/{build_targets,
   price_plies,cf_probe,emit_endgame_positions,rust_python_diff}.py`,
   `measurement/e4_continuation_20260828/continue_plies.py`,
   `measurement/e4_exploit_grading_20260825/stage_a_census.py`.
6. **measurement_infra replay/labeling tooling** — `scripts/measurement_infra/{root_replay,
   snapshot,sample_agreement_roots,meeple_dedup_census,reconstruct_crash_root}.py` and the
   three `gen_*_fixture.py` generators (**the generators must stay legacy-pinned** while
   their goldens stand — see §4).
7. **Older probes, low priority** — `measurement/utility_calibration_20260721/extract_margins.py`,
   `measurement/jrules_on_search_20260813/jr_dose_probe.py`,
   `measurement/invasion_term_build/test_invasion_shapes.py`,
   `measurement/c1_pricing_prep/{preflight_c1,selftest_c1}.py`,
   `measurement/s0{_exploiter_prep/s0_smoke,v2_scripted_prep/s0v2_{devplay,smoke}}.py`,
   `measurement/fpu_resurrection_prep/selftest_fixture/identity_fixture.py`.
8. **Python-MCTS play surfaces** (transposition key, not the memo) —
   `src/carcassonne_ai/{mcts,ameneyro_mcts,warmstart,champion_factory}.py`. Production play
   is the **rust** backend, so this is analysis/tooling; any *python*-backend line replayed
   from a banked action sequence needs the legacy pin or a re-run.
9. **Android bridge** — `android/app/src/main/python/android_bridge.py` builds a
   cache-enabled `Game`, but the phone plays the **rust** champion; worth a read-only
   confirm that no python mask feeds a shipped decision.

## 7. What was deliberately NOT done

* No banked artifact edited, no re-run launched, no `results.csv` row, no claim id.
* `governance/PRODUCTION.yaml` untouched.
* The **rust** `LegalMaskCache` was not changed — it must keep reproducing the bank.
* Whether the deployed arbiter's `arb_legal_mask_cache=True` continuation carries an
  analogous rust-side memo collision is **out of scope here**; OM-D2 measured the shipped
  `tiearb_probe` chain values as honest (`rust == py_nocache`, 10/10 witnesses).
