# L1 delta-decompose SPIKE — READ-OUT

**Status: `SPIKE COMPLETE — GATES PASS, FACTOR MEASURED, ESTIMATE REFUTED` (2026-08-30).**
Owner-funded ("go on engine", 2026-08-30). 0 games. Nothing promoted, no production
path touched, `governance/PRODUCTION.yaml` untouched.

**Headline:** the incremental tile-edge decomposition is **correct** — 37,254 tile
edges compared field-for-field (all 25 `Decomp` fields, root ids included) against a
full rebuild with **zero mismatches** — and it is **measurably faster, but far below
the funding estimate**. On a quiet box it buys **1.13× on `decompose` and 1.11× on a
real PUCT expansion slice**, against the sweep's **1.6–2.1× search** estimate.
Worse for the full-build decision: the spike also measured the **ceiling**. Any delta
scheme that keeps `Decomp` field-for-field equal to the rebuild cannot exceed
**1.58× on decompose** ⇒ **≤ ~1.28× on PUCT total**. **Recommendation: do NOT fund
the 2–4 week L1 build as scoped.**

---

## 0. What was asked vs what is here

| Asked | Delivered |
|---|---|
| Convert L1's 1.6–2.1× estimate into a measurement on the tile-phase edge | ✅ measured, quiet box + contended box |
| Reuse the banked "252-position × 19-field + 6-root-array" gate verbatim | ⚠️ **that gate does not exist in the repo** — see §1. An equivalent-or-stronger gate was built (same 19 + 6 = 25 fields, 1,295 positions) |
| Fresh randomized gate, N ≥ 500 games, every tile placement | ✅ 500 games / 35,959 tile edges, PASS |
| Bench ns/edge at matched board sizes + a real search slice | ✅ both, plus a **ceiling** arm the brief did not ask for and which is the decision-relevant number |
| Wheel-action identity check (5/5 roots) | ❌ not applicable — see §1 |
| Handle merge case + farm adjacency | ✅ both exercised by construction; see §4 |
| Honest list of unhandled cases | ✅ §6 |
| Build-cost estimate for full L1 | ✅ §7 |

---

## 1. The "banked gate" the sweep promised is not in the repo

The brief said a **252-position × 19-field + 6-root-array decomposition-equality
gate** was "already written and passing — reuse verbatim". It is not. Searched:
`rust/**` tests, `measurement/**`, `docs/**`, `scripts/**`, `DECISIONS.md`.

* No corpus of 252 positions exists under any name I could find.
* The only decomposition-equality test in the tree is
  `leaf::mod::tests::decompose_into_reuse_matches_a_fresh_decompose` —
  **90 plies of one greedy game, 8 of the 25 fields**. That is a buffer-reuse
  staleness test, not a decomposition-equality gate.
* "19" in the repo resolves to the **invasion screen's nineteen gates**
  (`measurement/invasion_screen_r*_prep/screen_lib.py`), an unrelated thing.
* "5/5 roots" resolves to `measurement/classical_search/MOVE_AGREEMENT_PREREG.md`
  (a BE/PARITY move-agreement check), also unrelated. There is no "wheel-action
  identity" artefact, and none is applicable here: this spike never builds a wheel
  and never changes any action.

**The "19-field + 6-root-array" description is, however, exactly right about
`Decomp`'s shape** — the struct has precisely 19 non-city-root fields and 6 city
root arrays (`city_root_{tiles,shields,cathedral,finished,open_n,delta}`), 25 total.
So the sweep was describing the struct correctly and mis-remembering that a gate
over it had been written. **A gate over all 25 fields now exists**
(`delta::decomp_diff`, `DECOMP_FIELDS == 25`) and is what both gates below use.

---

## 2. What was built

`rust/carc/carc-core/src/leaf/decomp/delta.rs` — `DeltaDecomp`, a parallel entry
point. **The full-rebuild path (`decompose_into`) is untouched**; nothing in
production, in the search, or in `tier1` calls the new code. It is wired only into
its own tests and `examples/l1_spike.rs`.

API:

* `DeltaDecomp::new()` / `from_state(&GameState)`
* `place_tile(r, c, tid)` — apply one tile edge, leave `decomp()` valid
* `unplace_tile(r, c)` — exact structural inverse, **no** label/fact refresh
  (that is what makes a candidate scan cheap)
* `resync()` — recompute labels + facts for the current structure
* `decomp() -> &Decomp`
* `decomp_diff(a, b) -> Result<(), &'static str>` — the 25-field comparator

What is maintained incrementally: `placed`, `cell_ord`, the city/road/farm node
vectors, the `ord*9+side` id maps, `farm_side_to_node`, the intra-tile edge lists,
and per-node scalar caches of **everything the facts pass otherwise reads out of the
tile registry** (`shield`, `inn`, the neighbour cell, the farmer-side/city-side
slices). `Decomp` turned out to be a pure function of the placed
`(row, col) -> tile_id` map — no meeples, scores, deck or phase — so `place_tile`
needs no `GameState` at all.

What is recomputed per edge (`refresh`): cross-tile edges + open flags, the three
union-find labellings, and all per-root aggregates.

---

## 3. Gates — ALL PASS

Both gates compare **incremental vs full rebuild, all 25 fields, after every tile
placement**. Harness: `rust/carc/carc-core/examples/l1_spike.rs`, plus 5 `cargo test`
unit tests in `delta.rs`.

| Gate | Corpus | Positions | Result |
|---|---|---|---|
| **G1** — deterministic corpus (§1's replacement for the missing banked gate) | 6 deck seeds × 3 fixed policies (first / median / last legal action) | **1,295** | **PASS** (≥ 252 required) |
| **G2** — fresh randomized | **500 random legal games**, LCG-picked actions, deck seeds `700000000000+i` | **35,959 tile edges** | **PASS**, 0 mismatches |
| **G3** — candidate-scan / undo (`place_then_unplace_is_an_exact_inverse`) | every legal tile action from >20 frozen parents, place → compare → undo, then assert the parent is intact | >500 candidates | **PASS** |
| **G4** — `from_state` replay path | 120 plies, seed 7 | 120 | **PASS** |
| **G5** — empty board | 1 | 1 | **PASS** |

**Total: 37,254+ tile edges, zero field mismatches, root ids included.**
A mismatch would have reported the failing field name and the reproducing deck seed;
none did. `cargo test -p carc-core` is green (222 tests: the pre-existing 217 + 5 new).

Reproduce:
```
nice -n 19 cargo run --release --example l1_spike --manifest-path rust/carc/carc-core/Cargo.toml
```

---

## 4. Merge case and farm adjacency — how they are covered

* **Merge (a tile joining N existing components).** Not special-cased, and it does
  not need to be: `refresh` re-runs `label_components_into` over the whole
  (incrementally maintained) edge list, so an N-way merge is handled by the same
  code the rebuild uses. This is also *why* the win is small — see §5.
* **Farm adjacency.** The 2026-05-29 `opposite_farmer_side` involution
  (`Trt → Brb`) is already correct in the Rust engine and covered by
  `tiles::tests::opposite_farmer_side_is_an_involution`. The delta consumes it via
  the same `fs.opposite()` call the rebuild uses, over the same
  `farm_side_to_node` keyspace (`ord*8 + farmer_side`) — the array is spliced and
  id-shifted, not rebuilt. `farm_labels`, `farm_pos0_root`, `farm_anypos_root`,
  `farm_adj` and `farm_root_finished_cities` are 5 of the 25 gated fields and are
  exact across all 37k edges. **Farm connectivity did not bite**, contrary to the
  brief's expectation — because the delta never re-derives farm topology, it splices
  the same node/edge lists.

---

## 5. The measurement

### 5.1 Environment (read this before quoting a number)

The local 5900XT box was **fully saturated** for the whole spike (a live
`eval_fair_puct` round, W=30, loadavg 31.7/32 — result-safe and owner-authorised to
share, but a **timing bench is an exclusive tenant**, memory
`feedback_no_agent_compute_beside_eval`). **All headline numbers are therefore from
the idle laptop** (`laptop-wsl`, i7-14650HX, 24 threads, loadavg 0.00, nothing else
running). The contended 5900XT run is kept as `bench_local_contended.json` for
comparison only — it inflates the factor (the rebuild arm is the DRAM-bound one, so
contention flatters the delta).

⚠️ The quiet-box rebuild law is **76.3 ns/placed** (R² 0.996), not the sweep's
**124.73 ns/placed** — different CPU. Do not cross-quote the absolutes. The
**factor** is the deliverable and it is a within-box, same-binary, interleaved-arm
ratio.

### 5.2 Bench A — ns per tile edge, matched board sizes (quiet laptop, 575 samples, 400 reps each)

Cost laws:

| arm | law (ns) | R² |
|---|---|---|
| full `decompose_into` | `-87.3 + 76.30 · placed` | 0.996 |
| delta (`place` + `unplace`) | `+139.5 + 61.85 · placed` | 0.927 |

| placed | rebuild ns | delta ns | factor |
|---:|---:|---:|---:|
| 0–7 | 311 | 422 | **0.74×** |
| 8–15 | 822 | 889 | 0.92× |
| 16–23 | 1,338 | 1,284 | 1.04× |
| 24–31 | 1,972 | 1,766 | 1.12× |
| 32–39 | 2,570 | 2,266 | 1.13× |
| 40–47 | 3,149 | 2,895 | 1.09× |
| 48–55 | 3,831 | 3,288 | 1.17× |
| 56–63 | 4,519 | 3,728 | 1.21× |
| 64–71 | 5,091 | 4,479 | 1.14× |
| 72–79 | 5,505 | 5,365 | 1.03× |

**Overall decompose factor: 1.125×.** The delta is a *loss* on boards under ~15
tiles (fixed splice/shift overhead beats a cheap whole-board walk) and peaks around
1.2× mid-board.

### 5.3 The CEILING arm — the number that decides the build

Third arm: `refresh()` **alone** at the child board size — cross-tile edges +
union-find labelling + per-root facts, with the enumeration and all registry chasing
already removed. **No delta scheme that keeps `Decomp` field-for-field equal to the
rebuild can go below this**, because all three of those phases are functions of the
whole board *under the rebuild's own id and edge ordering* (§6.1/§6.2).

```
CEILING (refresh-only): 1.576×   —   the delta as built realises 22% of that headroom
```

So the rebuild's cost splits roughly:
* **~63%** cross-edges + union-find + per-root facts (irreducible under struct equality)
* **~37%** node/intra-edge enumeration + the facts pass's registry chases (what the delta removes)
* the delta then hands **~half of that 37% back** as splice/shift/undo bookkeeping.

The "enumeration is ~45%" intuition behind the 1.6–2.1× estimate is a **Python
flat-leaf profile figure** (CLAUDE.md engine notes, 2026-06-12). In Rust the
`Vec<Vec<Side>>` chase is relatively much cheaper and the union-find + facts +
`fill`s dominate. **That is the root cause of the estimate being ~2× optimistic.**

### 5.4 Bench B — a real search slice (PUCT expansion candidate loop)

20 frozen tile-phase roots (5 deck seeds × board sizes ≈16/32/48/64), 690 candidates,
60 reps ⇒ 41,400 candidate evaluations per arm. Each arm does the **whole**
per-candidate cost: `g.clone() + advance(a)` → decomposition → the production
`leaf_terms_with(curve125)`.

| | ns/candidate |
|---|---:|
| `clone + advance` alone (shared floor) | 388 |
| + full rebuild + leaf | 4,982 |
| + delta + leaf | 4,504 |

* **Search-slice factor (whole candidate eval): 1.106×**
* decompose+leaf only (floor removed): 1.116×

### 5.5 Projection to PUCT total

Using the sweep's own decompose share of PUCT (0.605), whole-search factor
`= 1 / (0.395 + 0.605/f_decompose)`:

| f_decompose | whole-PUCT speedup |
|---|---|
| **1.125× (this spike, realised)** | **1.07×** |
| 1.576× (ceiling, exact-label delta, bookkeeping free) | 1.28× |
| 2.1× (the sweep's optimistic end) | 1.46× |

**Even the sweep's own optimistic decompose factor could not have produced a
1.6–2.1× *search* speedup.** The estimate appears to have conflated a decompose-level
factor with a search-level one, on top of the Python-profile issue in §5.3.

### 5.6 A dead end worth recording

A `clone_from(parent) + place_tile` candidate loop (the obvious first design) is
**0.67× — i.e. 1.5× SLOWER than the rebuild.** Cloning ~22 small `Vec`s per
candidate costs more than the whole decomposition. The `place → read → unplace`
apply/undo shape is not an optimisation, it is a **precondition** for L1 being
positive at all. Both arms are in `bench_a_clone_factor` in the JSON.

---

## 6. Honest list of what is NOT handled / what I punted on

1. **This is not an O(1)-per-edge delta and cannot be made one while keeping
   struct equality — reason 1: ordinals shift.** `Decomp` keys every node by
   `tile_ordinal * 9 + side`, where the ordinal indexes the **row-major sorted**
   placed list (`GameState::placed_coords` is a `BTreeSet`). A tile landing
   mid-order shifts every later ordinal — and node id — by a constant. Exact ids
   therefore cost an O(n) renumber on every edge. (Insertions are genuinely
   mid-order in real play; the gates exercise that path, it is not a tail append.)
2. **Reason 2: union-find roots are edge-order dependent.**
   `label_components_into` does `parent[find(u)] = find(v)`, so a component's
   surviving root is "the second endpoint of the last merging edge, resolved
   recursively" — not min-id, max-id, or any local function of the component. An
   incremental union-find with its own root convention yields a
   **relabelled-isomorphic** `Decomp`, not an equal one. That is why `refresh`
   re-runs the labelling instead of maintaining it, and it is why the 1.576×
   ceiling exists.
   * **Mitigation that would break the ceiling (unproven, needs its own gate):**
     every leaf consumer of the root arrays is `fsum`-reduced and the leaf code
     says so in comments at ~10 sites ("the sum is `fsum`-reduced so iteration
     order is irrelevant"). So a relabel-tolerant delta is *probably* leaf-value
     bit-exact. **I did not test this** — it would require re-specifying every
     `Decomp`-equality gate in the repo as an isomorphism check and re-proving
     leaf bit-exactness against the banked corpora. Cost is in §7.
3. **`unplace_tile` leaves `decomp()` stale by design.** Reading it after an undo
   without `resync()` gives the *child's* labels/facts over the *parent's*
   structure. Documented and asserted in the tests; a real integration must not
   expose this footgun.
4. **Not wired into anything.** `tier1::candidate_leaf`, `search::expand` and
   `LeafScratch` still call `decompose_into`. Mergeability was explicitly not
   required; a real integration also has to decide what happens on the **meeple**
   edge (L1a, a sibling agent's — the fact that meeple placements leave `Decomp`
   completely unchanged is confirmed by this spike but deliberately not exploited).
5. **No thread-local / `Scratch`-sharing design.** `DeltaDecomp` owns its own
   `Scratch`; a production version would want the TLS pattern `tier1::ScorerBufs`
   uses, and would want the search's tree structure (parent decomp per node) rather
   than one flat parent.
6. **Not benched on the 5900XT quiet.** The eval round owns that box. The factor is
   a same-box ratio so it should transfer, but the 5900XT is a different memory
   subsystem and the split in §5.3 could move by a few points.
7. **Small-board regression not addressed.** Below ~15 placed tiles the delta is a
   loss (0.74× at 0–7). A production version would need a size threshold, which is
   more branching on the hot path.
8. **The relative-node-id representation was not tried.** Storing
   `city_node_id` as tile-local indices plus a per-ordinal base would cut the
   dominant shift cost ~9× (shift `n-k` bases instead of `9(n-k)` ids), at the price
   of materialising `d.city_node_id` in `refresh` for gate equality. This is the
   most promising remaining lever for closing the 1.125 → 1.576 gap; I judged it
   out of scope once the ceiling made the funding answer clear.

---

## 7. Build-cost estimate for the full L1, given what this spike learned

**As scoped (exact-`Decomp`, tile edge only): ~4–6 days, not 2–4 weeks — and NOT
worth it.** Most of the hard work is already done and in this branch; what remains
is TLS/scratch plumbing, the search-tree integration (parent decomp per node,
apply/undo discipline through the PUCT expansion loop), the small-board threshold,
and re-running the leaf/G2 bit-exactness corpora end to end. But the prize is
**~1.07× on PUCT total** (§5.5) and at best ~1.28× if the remaining bookkeeping were
free. That does not clear the bar for touching the champion's hot path.

**The variant that could clear the bar — relabel-tolerant delta:** maintain the
union-find and the per-root facts incrementally with a stable-id/own-root
convention, dropping struct equality with the rebuild. Then the ceiling in §5.3
no longer applies and the per-edge cost could approach O(nodes touched).
**Cost: ~2–3 weeks, and it is a governance change, not just an engineering one** —
every `Decomp`-equality gate becomes an isomorphism check, leaf bit-exactness must
be re-proven against the banked corpora (§6.2 says it is *likely* safe because every
consumer is `fsum`-reduced, but "likely" is not a gate), and the failure mode is a
silent leaf drift rather than a crash. **Recommend pricing that variant before
funding it, not funding it off this spike.**

**Cheaper unrelated lever this spike surfaced (untested):** the rebuild spends real
time chasing `tiles::tile(tid)`'s `Vec<Vec<Side>>` / `Vec<FarmerConn>`. Flattening
the tile registry into fixed-size `#[repr]` arrays would speed up the **full
rebuild** with **no** structural change, no new gate class, and no apply/undo
discipline. From §5.3 the enumeration+registry share is ~37% of decompose, so an
upper bound of ~1.2–1.3× on decompose for perhaps a day of work — comparable to
everything L1 delivers, at a fraction of the risk. **Not measured; proposed.**

---

## 8. Artefacts

| file | what |
|---|---|
| `rust/carc/carc-core/src/leaf/decomp/delta.rs` | `DeltaDecomp` + `decomp_diff` + 5 unit gates |
| `rust/carc/carc-core/examples/l1_spike.rs` | the gate + bench harness (G1, G2, Bench A incl. ceiling arm, Bench B) |
| `bench_laptop_quiet.json` / `.log` | **the headline run** — idle i7-14650HX |
| `bench_local_contended.json` / `.log` | 5900XT under a live W=30 eval — comparison only, do not quote |

Rev at spike close: see the commit that carries this file. Champion, production
config and all governance rows: **untouched**.
