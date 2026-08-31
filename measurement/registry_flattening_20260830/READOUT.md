# Registry flattening — READ-OUT

**Status: `BUILT — GATES PASS (bit-identical), DIRECTIONAL BENCH CONTENDED` (2026-08-30).**
Owner-funded ("lets do registry flattening", 2026-08-30). 0 games.
Nothing promoted; `governance/PRODUCTION.yaml` untouched; no production config,
champion or claim row moved. This is a pure representation change inside
`leaf::decomp`.

**Headline:** the tile registry that `decompose_into` reads per placed tile is
now a flat `#[repr(C)]` table (`tiles::TileFlat`, 102 B, fixed-size arrays)
instead of `Vec<Vec<Side>>` / `Vec<FarmerConn>` heap structures, and
`tiles::tile()` is not called anywhere in `decompose_into` any more. Output is
**bit-identical** — all 25 `Decomp` fields equal a frozen reference
implementation of the old path across **149,100 positions and 298,200 leaf
values** (both registry flag states), and `cargo test --workspace` is green
(226 passed, 0 failed, 6 ignored).
On a **contended** box the change buys **≈1.16× on `decompose`** (slope
1.16–1.19× over four replicates) and **≈1.13× on decompose + the production
leaf** — direction confirmed, magnitude owed to a quiet window (§4, §6).

---

## 1. What the lever is

The L1 delta spike's §7 closed with an untested proposal:

> the rebuild spends real time chasing `tiles::tile(tid)`'s `Vec<Vec<Side>>` /
> `Vec<FarmerConn>`. Flattening the tile registry into fixed-size `#[repr]`
> arrays would speed up the **full rebuild** with **no** structural change, no
> new gate class, and no apply/undo discipline. […] **Not measured; proposed.**
> — `measurement/l1_delta_decompose_spike_20260830/SPIKE_READOUT.md` §7

That is what this round builds. It is the *cheap* half of the L1 finding: it
touches the full-rebuild path only, so every consumer benefits (search, tier1
playouts post-swap, the exact solver, the FFI leaf) with no new gate class, no
parent/child bookkeeping and no small-board threshold.

## 2. What changed

`rust/carc/carc-core/src/tiles/mod.rs`

* **`TileFlat`** (`#[repr(C)]`, 102 bytes) + **`FarmFlat`** (19 bytes) — the
  seven things `decompose_into` reads per placed tile and nothing else: the city
  groups (one `[u8; 8]` of sides plus a `[u8; 4]` of exclusive group ends), the
  road connections (`[u8; 8]`, pairs flattened), each farm slot's
  `tile_connections` / `farmer_positions` / `city_sides` as fixed arrays with
  counts, `shield`, and `has_inn` (`!inn.is_empty()`, precomputed).
* **`flat_registry()` / `flat_registry_for(r9)` / `tile_flat(id)`** — the flat
  table, `OnceLock`-memoised per R9 flag state exactly like `registry()`, and
  **derived from `registry_for(r9)`** rather than from `generated::`, so it
  cannot drift from the object registry.
* **`FARMER_SIDE_DELTA` / `FARMER_SIDE_OPP`** — const 8-entry LUTs replacing the
  chained `FarmerSide::get_side()` → `Side` → `(dr, dc)` matches and
  `FarmerSide::opposite()` on the farm cross-edge loop.
* Cap constants (`MAX_CITY_SIDES = 8`, `MAX_CITY_GROUPS = 4`, `MAX_ROADS = 4`,
  `MAX_FARMS = 4`, `MAX_FPOS = 4`, `MAX_TCONN = 8`, `MAX_CSIDES = 4`) with a
  **loud assert per tile at table-build time** — the base deck measures
  4 / 2 / 4 / 4 / 4 / 8 / 3, so every cap has headroom and an overflow panics at
  first use rather than truncating silently.

`rust/carc/carc-core/src/leaf/decomp/mod.rs` (was `leaf/decomp.rs`)

* `decompose_into` hoists `tiles::flat_registry()` **once** and indexes it.
  All five registry-reading sites converted: the node/intra-edge enumeration,
  the farm cross-tile edge loop, the city facts pass (`shield` / cathedral), the
  road facts pass (`inn`), and the farm facts pass.
* Two new `Scratch` buffers, `ord_tid` (`ordinal -> TileId`) and
  `farm_node_ord` (`farm node -> ordinal`), filled by the enumeration pass, so
  the later passes reach the tile by index instead of re-running
  `state.get_tile` + `ord_of`.
* **Public interface unchanged**: `decompose_into(&GameState, &mut Decomp, &mut
  Scratch)`, `decompose`, `Decomp`, `Scratch` all keep their signatures and
  fields. The L1a hoist call-sites and the tier1 swap consume it unmodified.

`rust/carc/carc-core/src/leaf/decomp/refimpl.rs` — **new, frozen**

* `decompose_into_ref` is `decompose_into` verbatim as of rev `ec0e52bb`, the
  object-registry path, kept as the gates' in-binary oracle. It is on no
  production path. Its module doc says in plain words: do not optimise it, do
  not refactor it, and never edit it in the same motion as `decompose_into`.
* `decomp_diff(a, b) -> Result<(), &'static str>` and `DECOMP_FIELDS == 25`,
  **lifted verbatim from the L1 spike's `delta::decomp_diff`** so both rounds
  compare exactly the same surface (19 structural fields + the 6 city root
  arrays, root ids included).

## 3. Gates — ALL PASS

Harness: `rust/carc/carc-core/examples/registry_flat_gate.rs` (corpus shape,
seeds, policies and LCG lifted from the spike's `l1_spike.rs`), plus in-suite
`cargo test` arms.

Every gate compares `decompose_into` (flat) against `decompose_into_ref`
(object) at **every ply — tile and meeple phases alike**, on all 25 `Decomp`
fields, and additionally compares the production leaf computed from each.

| Gate | Corpus | Positions | Leaf values | Result |
|---|---|---:|---:|---|
| **G0** — fresh game | 1 | 1 | — | **PASS** |
| **G1** — deterministic corpus, base registry | 6 deck seeds × 3 fixed policies (first / median / last legal) | **2,591** | 5,182 | **PASS** (≥ 252 required) |
| **G2** — randomized, base registry | **500 random legal games**, LCG action picks, deck seeds `700000000000+i` | **71,959** | 143,918 | **PASS** |
| **G1/G2 — R9 registry** (`CARCASSONNE_FIX_R9=1`, second process) | identical corpora against the R9 farm-override table | **74,550** | 149,100 | **PASS** |

**Total: 149,100 positions × 25 fields, and 298,200 leaf values, zero
mismatches.** The leaf arm compares `leaf_terms_with(curve125)` for both povs
bit-for-bit (`value`, and `to_bits()` on `score`, `base`, `bonus_self`,
`bonus_opp`, `meeple_term`, `return_term`, `flip_term`) — the L1a
bit-exactness precedent, applied to a decomposition rather than a hoist.

Reproduce:
```
nice -n 19 cargo run --release --example registry_flat_gate --manifest-path rust/carc/Cargo.toml
CARCASSONNE_FIX_R9=1 nice -n 19 cargo run --release --example registry_flat_gate --manifest-path rust/carc/Cargo.toml
```
Logs: `gate_base.log`, `gate_r9.log`. A failure names the first differing field
and the reproducing deck seed and exits non-zero; neither did.

### In-suite arms (`cargo test --workspace`)

* `tiles::tests::flat_registry_matches_the_object_registry` — every list the
  flat table carries, for **all 128 rotated tiles in BOTH registry flag
  states**, compared element-by-element in source order against `registry_for`.
  This is the gate that pins the ordering claim at the data layer.
* `tiles::tests::farmer_side_luts_match_the_functions` — the two const LUTs vs
  the `match`es they replace, all 8 half-sides. If `opposite()` or `get_side()`
  is ever edited again (the 2026-05-29 `Trt → Brb` involution fix lived
  exactly here), this fires.
* `leaf::decomp::tests::flat_registry_decomposition_is_bit_identical_to_the_object_path`
  — a fast deterministic slice of G1 inside the suite so a regression cannot
  land silently between example runs.
* `leaf::decomp::tests::scratch_reuse_across_shrinking_boards_is_clean` — the
  two new reused `Scratch` buffers, walked big → small → big against a
  fresh-`Scratch` oracle, so a shrinking board cannot read a stale tail.

### On the iteration-order hazard

The 2026-05-29 `find_farm` start-dependence bug lived exactly in this code, so
the ordering claim is stated explicitly rather than assumed:

* The flat table preserves **every** source order — city group order, side
  order within a group, road-pair order, farm-slot order, and the order of each
  farm's three lists. `flat_registry_matches_the_object_registry` asserts that
  element-by-element for all 128 tiles × both flag states.
* Node ids, the union-find edge push order, and therefore the surviving roots
  are all functions of those orders and of `placed` (unchanged). The 25-field
  comparator includes `city_labels` / `road_labels` / `farm_labels` and every
  root-keyed array, so a relabelling — not just a repartitioning — fails the
  gate. It did not fire on 149,100 positions.
* `FARMER_SIDE_DELTA` / `FARMER_SIDE_OPP` are the only *semantic* substitutions
  (LUT for `match`), and they carry their own equality test against the
  functions.

## 4. The bench — CONTENDED, direction only

### 4.1 Environment (read before quoting any number)

The local 5900XT was running a **live `eval_fair_puct` round** for the whole of
this work (≈17 worker processes, loadavg ≈18 of 32 threads). Per
`feedback_no_agent_compute_beside_eval`, **a timing bench is an exclusive
tenant** — so every absolute below is inflated and the *factor* is soft. The
round was left undisturbed: everything ran `nice -n 19`, no worker was killed,
and the bench is seconds-scale, not minutes.

**Nothing in this section is a verdict.** The claim this round actually banks is
the bit-identity in §3; the speed claim owes a quiet-window re-read (§6).

### 4.2 Bench A — ns per decompose vs placed tiles

Harness `rust/carc/carc-core/examples/registry_flat_bench.rs` — the same shape as
the spike's Bench A: capture the board after every tile placement across 8 deck
seeds, then time both arms on the **same** `GameState`s, interleaved, and
least-squares fit `ns = a + b · placed`.

Four replicates were run back-to-back under the same contention. The **absolute
slopes drift 181–211 ns/placed across replicates** — that drift *is* the
contention, and it is why no absolute here may be quoted. The **factor is
stable**:

| replicate | ref law (ns) | flat law (ns) | slope factor | decompose factor | decompose+leaf factor |
|---|---|---|---:|---:|---:|
| 1 | −288.6 + 210.92·placed (R² 0.832) | −79.3 + 177.68·placed (R² 0.864) | 1.187× | 1.157× | 1.138× |
| 2 | −318.4 + 189.05·placed (R² 0.846) | −173.4 + 159.76·placed (R² 0.819) | 1.183× | — | 1.122× |
| 3 | −186.3 + 181.17·placed (R² 0.837) | −141.6 + 156.73·placed (R² 0.817) | 1.156× | 1.152× | 1.117× |
| 4 (banked artefact) | −370.1 + 185.66·placed (R² 0.805) | −272.2 + 159.76·placed (R² 0.751) | 1.162× | 1.152× | 1.149× |

* **decompose ns/placed: ≈186–211 → ≈157–178, a slope factor of 1.16–1.19×**
  (4 replicates, 575 samples each, 400 reps per sample per arm).
* **decompose factor over the whole sample set: 1.15–1.16×.**
* **decompose + the production leaf, both povs: 1.12–1.15×.**

Per-bucket (replicate 4, mean ns per call in each 8-tile band):

| placed | ref ns | flat ns | factor |
|---:|---:|---:|---:|
| 0–7 | 696 | 634 | 1.098× |
| 8–15 | 1,928 | 1,715 | 1.124× |
| 16–23 | 3,013 | 2,741 | 1.099× |
| 24–31 | 4,199 | 3,735 | 1.124× |
| 32–39 | 5,890 | 4,966 | 1.186× |
| 40–47 | 7,694 | 6,617 | 1.163× |
| 48–55 | 9,900 | 8,504 | 1.164× |
| 56–63 | 10,729 | 9,381 | 1.144× |
| 64–71 | 12,186 | 10,482 | 1.163× |
| 72–79 | 11,933 | 10,604 | 1.125× |

Unlike the L1 delta, there is **no small-board regression** — the flat path wins
at every board size, because it removes work rather than trading a rebuild for
bookkeeping. That is the structural difference between the two levers and it is
why this one needs no size threshold.

**Read this as `~1.15×, direction confirmed, magnitude owed`,** and note two
caveats that push in *opposite* directions, neither of them priced:

* The reference arm is the pointer-chasing one, so a DRAM-contended box should
  **flatter** the flat arm — the quiet factor may be lower than 1.15×.
* The contended `ref` slope (≈186–211 ns/placed) is ~1.5–1.7× the sweep's quiet
  5900XT figure of 124.73 ns/placed, and R² fell from the spike's 0.996 to
  ≈0.75–0.85, so the fit itself is much noisier than the quiet-box one.

Against the funding estimate: the spike proposed "an upper bound of ~1.2–1.3× on
decompose." The contended measurement lands **at or just below the bottom of
that band**, which is the expected place for an upper bound to land — but the
estimate is **not yet confirmed or refuted**, because a contended bench cannot
settle a 1.15-vs-1.25 question.

### 4.3 What is NOT claimed

* Not a search-level number. The spike measured decompose ≈ 0.605 of PUCT
  total; on that share a decompose factor `f` projects to
  `1 / (0.395 + 0.605/f)` on whole-PUCT — but that share was measured on a
  different box under a different arm, and this bench is contended. No
  projection is banked here.
* Not an elo claim. Output is bit-identical, so strength is unchanged **by
  construction**; the only thing at stake is throughput.
* Not benched on a quiet box, on the laptop, or on the M5.

## 5. Honest list of what was NOT done

1. **`tiles::tile()` is untouched everywhere else.** `engine/mod.rs` (20 sites,
   the placement/legality path), `leaf/mod.rs` (8), `repr_key.rs`,
   `leaf/invasion.rs`, `leaf/jrules_prior.rs`, `tier1.rs` and `game.rs` all
   still walk the object registry. Those are separate, independently-gateable
   follow-ons; `engine/mod.rs` is the biggest remaining block and would want its
   own flat view (it reads `type_cache`, `city_sides_set`, `road_ends`,
   `unplayable_sides` — a different seven things).
2. **The frozen reference is duplicated code and will bit-rot by design.** That
   is the trade: an in-binary oracle is what makes "bit-identical" checkable
   rather than asserted. If the decomposition ever genuinely changes, the gate
   fails first and the port is deliberate.
3. **No R9 cross-check of the *flat build itself* beyond the registry equality
   test** — the R9 gate run re-runs the whole corpus, but R9 changes farms only,
   so it exercises the farm arrays hardest and the city/road arrays no
   differently than the base run.
4. **Caps are base-deck-sized.** Inns & Cathedrals / Abbots / river tiles are
   out of locked scope; if the deck ever grows, the build-time asserts fire
   loudly (they do not truncate).
5. **`Scratch` grew by two vectors** (`ord_tid`, `farm_node_ord`) — a few
   hundred bytes of retained capacity per `Scratch`, i.e. per search thread.
   Not measured as a footprint change; it is far below the buffers already
   there.

## 6. What the quiet-window re-read owes

1. **Re-run Bench A on an idle box** (the laptop is the spike's reference
   environment — its rebuild law was 76.30 ns/placed at R² 0.996, so a matched
   re-run there is directly comparable to the spike's numbers, which the 5900XT
   ones are not).
2. **A real search slice**, not just `decompose`: the spike's Bench B shape
   (frozen tile-phase roots, `clone + advance` → decompose → `leaf_terms_with`)
   gives the consumer-level factor the decision actually cares about.
3. **A tier1 playout arm** post-swap, since tier1 is the other full-rebuild
   consumer.
4. Only after (1)–(3): decide whether this merges to the main tree, and where
   the number lands in `experiments/results.csv` / the roadmap. Until then this
   round has produced a **correctness result** (bit-identity, gated) and a
   **direction**, not a promotion.

## 7. Artefacts

| file | what |
|---|---|
| `rust/carc/carc-core/src/tiles/mod.rs` | `TileFlat` / `FarmFlat`, the flat registry, the two const LUTs, 2 new tests |
| `rust/carc/carc-core/src/leaf/decomp/mod.rs` | the flattened `decompose_into` + 2 new tests |
| `rust/carc/carc-core/src/leaf/decomp/refimpl.rs` | the FROZEN object-registry reference + `decomp_diff` + `DECOMP_FIELDS` |
| `rust/carc/carc-core/examples/registry_flat_gate.rs` | G0/G1/G2, base and R9, JSON + non-zero exit on failure |
| `rust/carc/carc-core/examples/registry_flat_bench.rs` | Bench A (cost-law fit), same shape as the spike's |
| `gate_base.log` / `gate_r9.log` | the two gate runs |
| `bench_local_contended.json` / `.log` | the contended 5900XT bench — **direction only, do not quote** |

Champion, production config and all governance rows: **untouched**.
