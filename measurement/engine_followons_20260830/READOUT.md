# Engine follow-ons A + B — READ-OUT

**Status: `BUILT — GATES PASS (action-identical). ITEM A KEPT, ITEM B'S PREMISE
REFUTED BY ITS OWN CENSUS. ONE MERGE PRECONDITION OWED.` (2026-08-30).**
Owner-funded ("4- fund", 2026-08-30). 0 games. Nothing promoted;
`governance/PRODUCTION.yaml` untouched; no production config, champion or claim
row moved. Branch `worktree-agent-a560753ee10dc75b7`, unmerged.

**Headline, in two lines:**

* **A — flatten the remaining `tiles::tile()` sites.** All 20 in `engine/mod.rs`
  and all 8 in `leaf/mod.rs` dispositioned; 26 converted to a new flat play
  table, 2 left cold with reasons. Full-game **action-identity vs the
  pre-change build**: identical sha256 at N=250 games in **both** R9 states.
  **≈1.03× contended** on the gate's own mixed workload.
* **B — the tier1/arbiter meeple hoist.** Built, bit-identical, gated — and
  then its own census **refuted the funding estimate**. The hoist can remove at
  most **1.97 % of tier1 decompositions** (ceiling **1.0201×** *if decompose
  were 100 % of playout cost*); realized **1.005×** paired. The L0/L1a commit
  named this "the highest-value follow-on"; **it is not**, and the reason is
  structural (§4.2). It is left implemented, gated and merge-blocked, with an
  explicit **owner decision** attached (§4.4).

---

## 1. Base and composition

Merged into this worktree before starting, per the funding note:

| branch | what | conflicts |
|---|---|---|
| `worktree-agent-a396dc03111d62cda` | registry flattening (`TileFlat`/`FarmFlat`/`flat_registry`) | **merged, zero conflicts** (fast-forward to `35569f38`) |
| `worktree-agent-acf104f4eb41c6a55` | L0 gates + search-side L1a hoist | **already an ancestor of the base** (`5aa78972`); nothing to merge |

So the pre-change reference for every gate below is exactly **`35569f38`** —
the flattening round's tip, with the L1a hoist already in it.

## 2. What changed

### `rust/carc/carc-core/src/tiles/mod.rs` — the PLAY view

A **second** flat table, parallel to `TileFlat` and deliberately *not* an
extension of it:

* **`TilePlayFlat`** (`#[repr(C)]`, 15 bytes) — `terrain: [u8; 9]` (the whole
  `type_cache`, `None` = 0 and `Some(t)` = `t + 1`), three **cardinal
  bitmasks** (`grass_mask` / `city_side_mask` / `road_end_mask`), `city_edges`
  (`sum(len(g) for g in city)` — `bag_stats`' `ne`), and the flags `chapel`,
  `flowers`, `shield`, `has_inn`, `river_empty`, `river_ends_empty`.
* **`play_registry()` / `play_registry_for(r9)` / `tile_play(id)`** —
  `OnceLock`-memoised per R9 flag state and **derived from `registry_for(r9)`**,
  exactly like `flat_registry`, so it cannot drift from the object registry.
* **`SIDE_FROM_U8` / `FARMER_SIDE_FROM_U8`** — const inverse LUTs, so the
  `TileFlat` sites can come back out of `u8` space without a `match`.

**Why a separate table and not more fields on `TileFlat`.** `TileFlat`'s layout
is what the flattening round's banked oracle certificate is *about*; growing it
would perturb a certified structure for the benefit of code that never reads
it. And the two views want different shapes — the decomposition wants ordered
**lists**, the legality path wants **set membership on four cardinal sides**,
which is one `u8` and a shift, not a list walk. The flattening READOUT §5
anticipated exactly this ("would want its own flat view … a different seven
things").

### `rust/carc/carc-core/src/engine/mod.rs`

* **`fits_flat`** — `fits` on bitmasks. The three `Vec<Side>` membership walks
  become `masks_fit(center_mask, [neighbour masks])`: for each cardinal `i` set
  in the centre, the neighbour across `i` must carry `(i + 2) % 4`. `fits`
  itself is kept, unmodified, as the in-binary oracle the gates compare against.
* `possible_playing_positions` calls `fits_flat`, with the play table hoisted
  out of **both** loops and the four `get_tile` neighbour lookups hoisted out of
  the rotation loop (they do not depend on `turns`).
* 17 further reads converted — see the site table in §3.

### `rust/carc/carc-core/src/leaf/mod.rs`

All 7 hot `get_type` sites (`final_scores`, `closure_bonus`, `return_term`,
`denial_term`, `opencity_term`, and the two J-rules terms) now read
`tile_play`. `bag_stats` reads the precomputed `city_edges` instead of walking
`Vec<Vec<Side>>` per deck tile — it walks the **whole remaining deck** (up to 72
tiles) once per leaf evaluation whenever `cfg.bag_close` is on, so this is the
single densest conversion in the file.

### `rust/carc/carc-core/src/tier1.rs` — follow-on B

`best_by_virtual_score` reuses ONE decomposition across all candidates of a
`Phase::Meeples` decision. Bit-identical **by construction**: `decompose_into`
reads only `placed_coords` and `board`, and no meeple-phase action places a
tile. Two things deliberately **not** hoisted:

* **`border_wrap_hazard` stays per candidate.** R12 says hoisting it is *sound*
  in the meeple phase — but it would change how many times `BORDER_FALLBACKS`
  is bumped, which is an **observable** that a gate reads, for ≤ 72 integer
  comparisons. Not worth an observable.
* **The decomposition is filled lazily**, off the first candidate that does not
  take the border fallback, so a meeple decision on a border board pays nothing.

Plus `tier1::with_fresh_decomp` — a gates-only TLS switch, same shape as
`with_legacy_scorer` and `search::with_fresh_decomp`, so an identity gate can
run both routes over the same roots and RNG streams.

## 3. Item A — the site table

All 28 sites the flattening READOUT §5 named. "Hot" is judged against the
**post-swap** cost structure (`PROFILE_TIER1.md` §4.2: once `count_final_scores`
is replaced by the decomp route at 5.7 µs/candidate, move-generation and the
leaf terms stop being rounding error), not the pre-swap one.

### `engine/mod.rs` — 20 sites

| # | line (pre) | function | reads | hot? | disposition | why |
|---|---|---|---|---|---|---|
| 1 | 550 | `play_tile` | `river` | — | **LEFT** | `debug_assert!` — compiled out in release, so there is no read to remove. Converting adds a table lookup to debug builds and buys nothing. |
| 2 | 686 | `remove_meeples_and_collect_points` | `chapel`, `flowers` | **hot** (per ply, 3×3 cloister scan) | converted → `tile_play` | |
| 3 | 737 | `count_final_scores` | `get_type` | warm | converted → `tile_play` | Off tier1's hot path post-swap, but still every terminal + the border fallback + the python-parity route. |
| 4 | 815 | `count_city_points` | `inn.is_empty()` | warm | converted → `has_inn`, table hoisted | |
| 5 | 828 | `count_city_points` | `shield` | warm | converted → play table | |
| 6 | 855 | `count_road_points` | `inn.is_empty()` | warm | converted → `has_inn`, table hoisted | |
| 7 | 889 | `count_farm_points` | `farms[].city_sides` | warm | converted → `TileFlat.csides()` | **Also drops a heap `Vec` clone per farm node** — the sides now land in a fixed stack array. |
| 8 | 942 | `cities_for_position` | `city` groups | **hot** (the `find_city` flood) | converted → `TileFlat.city_group()` | |
| 9 | 971 | `find_cities` | `get_type` | **hot** | converted → `is_type` | |
| 10 | 1020 | `outgoing_roads_for_position` | `road` pairs | **hot** (the `find_road` flood) | converted → `TileFlat.road` | |
| 11 | 1051 | `find_roads` | `get_type` | **hot** | converted → `is_type` | |
| 12 | 1092 | `farm_for_position` | `farms[].tile_connections` | **hot** (every `find_farm` step) | converted → `tconn()` | |
| 13 | 1110 | `find_farm` | `farms[].tile_connections` | **hot** | converted → `tconn()` | |
| 14 | 1127 | `find_farm_by_coordinate` | `farms[].farmer_positions` | warm | converted → `fpos()` | |
| 15 | 1142 | `farm_find_meeples` | `farms[].farmer_positions[0]` | **hot** | converted → `fpos()[0]` | `fpos()` is the LIVE slice, so an empty list still **panics** exactly as `farmer_positions[0]` did. |
| 16 | 1174 | `possible_playing_positions` → `fits` | `grass`, `city_sides_set`, `road_ends` | **hot** (legal-move generation, 4 rotations × every open position, every tile ply) | converted → `fits_flat` | The largest single conversion; needed the new mask fields. |
| 17 | 1258 | `possible_meeple_actions` | `chapel`, `flowers` | cold branch (`abbots == 0` in locked scope) | converted → `tile_play` | Zero-risk: same struct as its neighbours, keeps the function on one table. |
| 18 | 1283 | `possible_meeple_positions` | `chapel`, `get_type` ×2 | **hot** (every meeple ply) | converted → `tile_play` / `is_type` | |
| 19 | 1309 | `possible_farmer_positions` | `farms`, `farmer_positions[0]` | **hot** | converted → `TileFlat.farms()` / `fpos()` | |
| 20 | 1507 | `farm_components` | `farms.len()` | **cold** | **LEFT** | Its own doc says "not used in the hot path" — a debug aid. Converting is zero-risk *and* zero-benefit; leaving it keeps the diff to code that matters. |

### `leaf/mod.rs` — 8 sites

| # | line (pre) | function | reads | hot? | disposition |
|---|---|---|---|---|---|
| 21 | 453 | `final_scores` | `get_type` | **hot** (per leaf, per placed meeple) | converted → `tile_play` |
| 22 | 553 | `bag_stats` | `city` group lengths | **hot when `bag_close`** — walks the whole remaining deck per leaf | converted → `city_edges`, table hoisted out of the closure |
| 23 | 671 | `closure_bonus` | `get_type` | **hot** | converted |
| 24 | 837 | `return_term` | `get_type` | **hot** | converted |
| 25 | 978 | `denial_term` | `get_type` | **hot** | converted |
| 26 | 1050 | `opencity_term` | `get_type` | **hot** | converted |
| 27 | 1209 | J-rules farm counts | `get_type` | **hot** | converted |
| 28 | 1394 | `jr_unclaimed_value` | `get_type(Center)` | **hot** | converted |

**Converted 26 / 28. Left 2, both justified above.** No site's conversion
changed an observable ordering, so nothing had to be reverted (§5 records the
one place where the gate *forced a design change* before that could happen).

**Named but out of scope** (not in the funded list; still on the object
registry, and now the complete remaining set): `repr_key.rs` ×2, `game.rs` ×1,
`leaf/invasion.rs` ×2, `leaf/jrules_prior.rs` ×1, `fair/jrules_filter.rs` ×1,
`tier1.rs` ×1, `engine/board_bounds_tests.rs` ×1 (test-only). `repr_key.rs` is
the interesting one — it is the legal-mask memo key, i.e. hot in tier1 — and it
reads `description` and `type_cache`; it would be the natural next site.

## 4. Gates

### 4.1 Cross-build action identity — **PASS, both R9 states**

`rust/carc/carc-core/examples/flat_play_gate.rs`. The same binary source built
against the pre-change tree (`git archive 35569f38` into a scratch dir — the
repo's own state was never touched) and against HEAD, each emitting a sha256
over **everything observable** about 250 seeded games:

* arm **`engine`** — random-policy self-play: every ply's **complete legal-move
  list in order**, the phase, the mover, the running scores, the chosen action,
  the final scores, the ply count.
* arm **`tier1`** — `RuleBasedPlayer` self-play at **both memo shapes**: the
  action, the candidate set, and **every per-candidate int64 leaf**, plus the
  memo's hit/miss counters. This arm is what grades follow-on B end to end.

A pure **reordering** of a legal-move list moves this digest — which no
score-only comparison would catch, and which is the exact failure class the
2026-05-29 `find_farm` start-dependence bug was.

| build | R9 | games | engine plies | tier1 scored candidates | border fallbacks | `sha256_combined` |
|---|---|---:|---:|---:|---:|---|
| pre-change `35569f38` | off | 250 | 35,984 | 1,157,954 | 0 | `badb8f39ce3d7124…` |
| **HEAD (A+B)** | off | 250 | 35,984 | 1,157,954 | 0 | **`badb8f39ce3d7124…`** |
| pre-change `35569f38` | **on** | 250 | — | — | 0 | `6e85b20fc2bca4e4…` |
| **HEAD (A+B)** | **on** | 250 | — | — | 0 | **`6e85b20fc2bca4e4…`** |

**Identical in both flag states**, and the two flag states differ from each
other — so the R9 arm is doing real work and is not a duplicate run.
Artefacts: `gate_head_base.json` / `gate_prechange_base.json` /
`gate_headr9.json` / `gate_prechange_r9.json` (+ `.log`).

Reproduce:
```
nice -n 19 cargo run --release --example flat_play_gate --manifest-path rust/carc/Cargo.toml
CARCASSONNE_FIX_R9=1 nice -n 19 cargo run --release --example flat_play_gate --manifest-path rust/carc/Cargo.toml
```

### 4.2 The flattening round's own decompose oracle — **RE-RUN, PASS**

Follow-on B changes *which* states get decomposed, so the flattening round's
oracle was re-run at full size in both flag states:

| run | positions | leaf values | result |
|---|---:|---:|---|
| `registry_flat_gate`, base | 74,550 | 149,100 | **ALL PASS** |
| `registry_flat_gate`, R9 | 74,550 | 149,100 | **ALL PASS** |

Artefacts: `decomp_gate_base.{json,log}`, `decomp_gate_r9.{json,log}`.

### 4.3 In-suite — `cargo test --workspace`: **239 passed / 0 failed / 8 ignored**

(226 at the flattening merge; +13 new gates, +2 new `--ignored` diagnostics.)

**Item A, data layer** (`tiles::tests`)
* `play_registry_matches_the_object_registry` — every field of the play table
  against `registry_for`, **all 128 rotated tiles × both R9 flag states**:
  `get_type` on all 9 sides, mask membership on all 9 sides, mask *population*,
  `city_edges`, and the six flags.
* `side_and_farmer_side_from_u8_luts_are_inverses`, `terrain_codec_round_trips`.

**Item A, code layer** (`engine::flat_play_tests`)
* `fits_flat_matches_fits_on_every_single_neighbour_board` — **exhaustive**:
  128 centres × 4 slots × 128 neighbours = **65,536** boards, object vs flat.
  One neighbour at a time is the shape that isolates a wrong opposite-side; a
  full board hides it behind the other conjuncts.
* `fits_flat_matches_fits_on_randomized_quadruples` — **200,000** randomized
  4-neighbour boards; the test refuses a corpus that is all-true or all-false.
* `possible_playing_positions_is_unchanged_across_a_corpus` — the converted
  call site in situ, comparing **elements AND order** against the object body
  rebuilt verbatim inside the test.
* `the_converted_reads_agree_with_the_object_registry_in_situ` — every other
  converted read, re-derived from `tiles::tile()` and compared, over every
  placed tile of a walked corpus (city groups in order, road pairs in order,
  each farm's three lists in order, all 9 terrain slots, all flags).
* `city_edges_equals_the_summed_city_group_lengths` — whole deck, both states.

**Item B** (`tier1::tests`)
* `every_meeple_phase_candidate_shares_the_root_decomposition` — the structural
  claim, on all **25 `Decomp` fields** via `decomp_diff` (the same comparator
  the L1 spike and the flattening round use, so all three grade one surface).
* `a_tile_phase_candidate_generally_moves_the_decomposition` — the **positive
  control**: a tile placement must ALWAYS move it, else the comparator is blind.
* `the_tier1_meeple_hoist_is_decision_identical` — hoist on vs
  `with_fresh_decomp`, comparing action, legal set, candidate set **and every
  per-candidate int64 leaf**, over 16 games (>200 meeple and >200 tile
  decisions).
* `the_tier1_meeple_hoist_leaves_the_playout_bit_identical` — whole playouts,
  margin as **raw f64 bits** plus ply count, 3 seeds × both memo shapes.
* `the_hoisted_decomposition_does_not_leak_across_decisions` — `SCORER_BUFS` is
  thread-local and outlives a decision, so this interleaves 40 different
  meeple-phase boards on ONE thread, twice, against per-board references. A
  stale `decomp_valid` would silently score a later board against an earlier
  decomposition; nothing else in the suite would catch it.

### 4.4 ⛔ The banked §2 G-BITEXACT certificate — **RE-RUN OWED (merge precondition)**

Follow-on B edits `best_by_virtual_score`, **the function G-BITEXACT grades**.
The banked 2026-08-29 PASS —

```
n_playouts_compared     == 15360      n_value_bit_identical == 15360
n_plies_identical       == 15360      n_seed_witness_ok     == 240
sha256_values_rust      == 0c2e39fed5259320bf9891c221796be67b6805c057d98df02f426bc0e6b88e80
```

— **no longer certifies the deployed code.** It is INVALIDATED by this change
and must be re-run to that exact digest before B merges to production use.

**One command, both modes:** `scripts/engine_followons/rerun_g_bitexact.sh`.
It censuses the box, builds a wheel from *this worktree* into a shadow dir
(the venv's `carc_rs` is never touched — house pattern), asserts the shadow
`carc_rs` is the branch build, runs, and adjudicates key-by-key against
`measurement/tiearb2_stage2_20260817/BITEXACT.json` **and** against the literal
`0c2e39fe…`.

```
scripts/engine_followons/rerun_g_bitexact.sh smoke 30   # pre-flight, contended
scripts/engine_followons/rerun_g_bitexact.sh full       # THE GATE, quiet window
```

`--legs-limit` (new, default off) was added to `scripts/tiletie/
verify_tier1_rust.py`. It runs a deterministic prefix of the committed draw and
— by design — leaves `pass:false`, because `pass` is graded against the
committed constants and *a truncated run must FAIL, not trivially satisfy*
(PHASE_A §3). Smoke mode reads a separate `smoke_pass`: zero errors, every
compared playout bit-identical, every seed witness ok, and the **subset**
digests equal (rust vs the banked python records over exactly the legs run).

**Smoke result, run contended beside the live `eval_fair_puct` round
(loadavg ≈ 31):**

| legs | playouts compared | value bit-identical | mismatches | subset digests | wall | verdict |
|---:|---:|---:|---:|---|---:|---|
| 30 of 240 | **1,920** | **1,920** | 0 | **equal** | 4.4 s | **SMOKE PASS** |

⚠️ **This is not the gate and is not banked as one.** Artefact:
`BITEXACT_SMOKE_30legs.json` (`"gate": "G-BITEXACT-SMOKE"`, `"pass": false`,
`"smoke_pass": true`).

**Cost note for the quiet window:** at 30 workers the smoke did 30 legs in
4.4 s *while contended*, so the full 240 legs is on the order of **~35 s**, not
minutes. The gate's "exclusive tenant" requirement is about not stealing 30
workers from the live round — it is **not** a readability requirement, because
the gate's criterion is bit-identity, which contention cannot move. It is
cheap; it just needs a gap.

## 5. What the gates caught

**The cardinal-mask representation is lossy, and it took the data-layer gate to
say so.** `play_registry_matches_the_object_registry` failed on its first run:

```
r9=false id=0 chapel_with_road rot 0: road_ends carries the non-cardinal side Center
```

`road_ends` carries `Side::Center` on the crossroads tiles, and a 4-bit cardinal
mask cannot hold it. The conversion is nevertheless exact, because `fits` reads
these lists in exactly two ways and `Center` is inert in **both** — the centre
tile's own list is walked by a `match` whose only arms are the four cardinals
plus `_ => false`, and a neighbour's list is only ever asked
`.contains(&Side::{Top,Right,Bottom,Left})`. Rather than assert a false
property, the gate was **narrowed to the true one** (mask population == the
count of cardinal members, so a dropped *cardinal* still fires) and the
equivalence was pushed onto `fits_flat_matches_fits_*`, which compares the two
predicates directly over 65,536 exhaustive + 200,000 randomized boards. The
reasoning is written into the assertion, not into a commit message.

Had this been asserted rather than gated, the lossy field would have shipped
with a comment claiming the lists were cardinal-only.

## 6. The numbers — CONTENDED, direction only

### 6.1 Environment (read before quoting anything here)

The local 5900XT ran a **live `eval_fair_puct` round** (`CELL_G3_OPP`, 30
workers, loadavg ≈ 31 of 32 threads) throughout. Per
`feedback_no_agent_compute_beside_eval`, **a timing bench is an exclusive
tenant**, so every absolute below is inflated and every factor is soft.
Everything ran `nice -n 19`, no worker was touched, and every timed run is
seconds-scale. **Nothing in this section is a verdict.** What this round banks
is §4's identity; the speed reads owe a quiet window.

### 6.2 A + B combined — 3 interleaved paired replicates

The `flat_play_gate` workload (250 random-policy games + 250 `RuleBasedPlayer`
games × 2 memo shapes), pre-change binary vs HEAD binary, alternating:

| replicate | pre-change | HEAD | factor |
|---|---:|---:|---:|
| 1 | 15.79 s | 15.26 s | 1.0347× |
| 2 | 15.56 s | 15.14 s | 1.0278× |
| 3 | 15.44 s | 15.03 s | 1.0271× |

**≈1.03× on this workload, direction confirmed, magnitude owed.** ⚠️ This is
*not* a PUCT-search number: the gate's workload is move-generation-heavy and
tier1-greedy, not `Searcher`. It transfers in kind (A converts the leaf terms
`Searcher` runs and the legal generation it drives) but not in magnitude, and
no projection is banked here.

### 6.3 B alone — paired, in-process

`tier1_meeple_hoist_bench` (`--ignored`), 96 whole playouts per arm, hoist on
vs `with_fresh_decomp`, interleaved by replicate:

| arm | ms/playout |
|---|---:|
| fresh (decompose per candidate) | 26.863 |
| hoisted (once per decision) | 26.727 |
| **factor** | **1.005×** |

### 6.4 …and WHY — the census that refutes the estimate

`tier1_decompose_call_census` (`--ignored`, deterministic, not a timing read),
40 games:

| | decisions | scored candidates |
|---|---:|---:|
| no-score (Rule 1 / single candidate) | 2,151 | — |
| **TILE** | 2,837 | **89,315** |
| **MEEPLE** | 771 | **2,581** |

* Meeple share of all scored candidates: **2.81 %**.
* Decompositions the hoist removes: **1,810 of 91,896 = 1.97 %**.
* **Ceiling on the whole-playout factor: 1.0201×** — and that is the ceiling
  *if `decompose_into` were 100 % of playout cost*, which post-swap it is not.

**This is a structural refutation, not a noisy read.** The L1a hoist earned
1.031× on the **search** path because PUCT expands meeple-phase nodes and pays
a leaf per child there. Tier1 is a **greedy 1-ply argmax**: its expensive
decisions are the tile-phase ones with ~31 candidates each, and those are
exactly the ones the hoist cannot touch. The candidate counts run **97 : 3**
against it. The L0/L1a commit's "where arb-on's 1.70× lives" is true of tier1
*as a whole* and false of tier1's *meeple phase*, and nothing before this
census distinguished the two.

### 6.5 The decision B leaves on the table

B is bit-identical, gated, free at runtime, and removes ~2 % of decompositions.
It also **costs a full G-BITEXACT re-run and puts a certified function under
edit** — for a ceiling of 1.0201×. That trade is the owner's call, not this
round's, so B is left implemented and **merge-blocked on §4.4** with both
numbers on the table:

* **Take it** — the re-run is ~35 s of quiet box, the gates are written, and
  2 % is 2 %.
* **Drop it** — revert `tier1.rs` alone (A does not depend on it; the §4.1
  digest would need one re-read) and the banked `0c2e39fe…` certificate stays
  valid, untouched.

**A is not affected either way** — it does not edit `best_by_virtual_score`,
and its own identity gate is already green in both R9 states.

## 7. Honest list of what was NOT done

1. **No quiet-window read of anything.** §6 is contended throughout. The A/B
   factor, the B factor and the census's ceiling all want a re-read; the census
   is deterministic and will not move, the two factors will.
2. **No PUCT-search arm.** The workload benched is move-gen + tier1-greedy.
   The consumer-level number the decision actually cares about — A's effect on
   `Searcher` — is not measured here.
3. **The full 240-leg G-BITEXACT is OWED**, §4.4. The 30-leg smoke can only
   refuse the gate, never grant it.
4. **8 `tiles::tile()` sites remain** outside the funded two files (§3), and
   `repr_key.rs` — the tier1 legal-mask memo key — is the highest-value one
   left. It needs `description`, which the play table does not carry.
5. **`fits` is now duplicated logic** (object `fits` + `fits_flat`) and will
   bit-rot by design, exactly as `decomp::refimpl` does. That is the trade: an
   in-binary oracle is what makes "identical" checkable rather than asserted.
6. **The two left-alone sites** (`play_tile`'s `debug_assert`, `farm_components`)
   are documented in §3, not silently skipped.
7. **No elo claim, no strength claim, no promotion.** Output is action-identical,
   so strength is unchanged **by construction**; only throughput is at stake.

## 8. Artefacts

| file | what |
|---|---|
| `rust/carc/carc-core/src/tiles/mod.rs` | `TilePlayFlat`, the play registry, the two inverse LUTs, 3 new tests |
| `rust/carc/carc-core/src/engine/mod.rs` | `fits_flat` + `masks_fit`; 18 converted reads |
| `rust/carc/carc-core/src/engine/flat_play_tests.rs` | **new** — the 5 Item-A code gates |
| `rust/carc/carc-core/src/leaf/mod.rs` | 8 converted reads |
| `rust/carc/carc-core/src/tier1.rs` | follow-on B: the hoist, `with_fresh_decomp`, 5 gates + 2 `--ignored` diagnostics |
| `rust/carc/carc-core/examples/flat_play_gate.rs` | **new** — the cross-build action-identity digest |
| `scripts/engine_followons/rerun_g_bitexact.sh` | **new** — the §4.4 re-run, one command, smoke + full |
| `scripts/tiletie/verify_tier1_rust.py` | `--legs-limit` smoke mode (default off; full-gate behaviour unchanged) |
| `gate_{head,prechange}_{base,r9}.{json,log}` | the four action-identity runs |
| `decomp_gate_{base,r9}.{json,log}` | the re-run decompose oracle |
| `BITEXACT_SMOKE_30legs.json` | the contended pre-flight — **not** the gate |

Champion, production config and all governance rows: **untouched**.
