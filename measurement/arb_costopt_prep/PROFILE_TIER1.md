# PROFILE_TIER1 — where the tie-arbiter's playout second actually goes

**Status: COMPLETE (measurement only).** Owner-funded 2026-08-28 to size "option B"
(a bit-identical engine speedup of the tier1 playout). **No engine source was
modified and nothing here is a deploy claim.** The instrument is an out-of-tree
crate that depends on `carc-core` by path; the laptop repo working tree was not
touched.

---

## 0. Headline

| | |
|---|---|
| Baseline cost | **91.03 ms / playout** (sequential, `legal_mask_cache=false` — the shape `tiearb::arbitrate` deploys) |
| Where it goes | **`GameState::count_final_scores` = 97.4 %.** Everything else together is 2.6 % |
| The advisory's three suspects | `clone` 0.62 % + `legal_mask` rebuild 0.57 % + `apply_action` 0.52 % = **1.71 % combined** |
| Biggest lever | Replace the per-candidate scorer with `leaf::decompose_into` + `leaf::flat_base_score`, **already in the crate and already gate-equal** |
| Measured end-to-end factor | **7.90×** (84.27 → 10.67 ms/playout), **0 / 216 playouts** differed in `(margin, plies)` from production `tier1_playout` |
| Per-candidate scorer factor | **7.84×** (44.75 → 5.71 µs), **0 / 238,203** candidate values differed |

The Fable advisory's estimate (1.5–3×, from clone / apply / mask-rebuild) is both
**too small and mechanistically wrong**: those three cost 1.7 % of the playout
combined, so eliminating all of them entirely buys 1.017×. The real cost is one
call, and the replacement for it is already written, already tested, and already
gate-proven equal.

---

## 1. Box, rev, method

| | |
|---|---|
| Box | `laptop-wsl` (WSL2 Ubuntu on the laptop), **Intel Core i7-14650HX**, 12 cores / 24 threads, 11 GiB to the VM |
| Tenancy | **Exclusive.** load average 0.10 / 0.10 / 0.09 before the first launch; census before and after every run is in `costprobe_src/*.log`. No other substantive process ran on the box for the duration |
| Laptop repo rev | `d3aae29749dd2aafc4cbb98ea3c32209e85b9317`, branch `tiearb2-stage2` — the production arbiter. Nothing was synced, merged, or edited there |
| Toolchain | `rustc 1.96.0 (ac68faa20 2026-05-25)` — the `rust/carc/rust-toolchain.toml` pin. Probe crate release profile is `opt-level = 3`, `lto = "thin"`, default codegen-units, i.e. **byte-for-byte the `rust/carc` workspace release profile** |
| Instrument | `measurement/arb_costopt_prep/costprobe_src/` — an out-of-tree crate at `/home/doctor/costprobe` on the laptop, `carc-core = { path = ... }` |

### 1.1 Why not `perf`

Checked first, per the brief's preference order. Laptop WSL has **no `perf`
binary, no `linux-tools-*` package, no `valgrind`, no `gdb`** (`perf_event_paranoid`
is 2 anyway). Not fought — fell through to method (c), component isolation, but
built properly rather than by python-side subtraction (the Python API exposes only
`tier1_leg` / `tier1_playout_trace`, so no per-ply primitive is reachable from
python at all).

### 1.2 Method: an identity-gated instrumented shadow

`carc-core`'s public API is enough to re-implement the `tier1::tier1_playout`
decision loop verbatim outside the crate. `costprobe_src/src/main.rs` does exactly
that and instruments every stage boundary.

**A breakdown of a different player is worse than no breakdown**, so the shadow is
gated: every shadow playout is run against the real `carc_core::tier1::tier1_playout`
on the same `(world, pick, playout_seed)` and must return the **same margin and the
same ply count**. A single mismatch aborts the probe.

- `identity_gate`: **480 / 480 checked, 0 mismatches** (`probe_none.json`), 480 / 480
  (`probe_cache.json`), 216 / 216 (`swap.json`).

Three passes over identical work isolate the two error terms:

| pass | what it is | result |
|---|---|---|
| `baseline` | the real `tier1::tier1_playout`, untouched — **the number of record** | 91.03 ms/playout |
| `shadow0` | the shadow with timing compiled out (`const TIMED: bool` generic) | **shadow fidelity 0.9985** |
| `shadow1` | the shadow with per-stage timers | **instrumentation tax 1.0018** |

So the shadow is the same code to 0.15 %, and instrumenting it costs 0.18 %.

**Timer-tax correction.** `Instant::now()` was measured in-process at **15.8 ns**.
Each stage boundary is one call, and the number of ticks charged to each stage is
derivable exactly from the counters (`analyze_profile.py::tick_counts`), so each
stage's raw nanoseconds have `n_ticks × 15.8 ns` subtracted before shares are
computed. The correction is < 0.1 % on `count_final_scores` and 3–32 % on the
sub-0.05 % stages (which is why those are reported to 4 decimals and not leaned on).

### 1.3 Uncertainty, stated honestly

- **Shares** carry the shadow-fidelity (0.15 %) and instrumentation (0.18 %) errors
  plus the timer-tax residual. For the dominant stage that is ±0.5 % absolute; for
  the sub-1 % stages, treat the third significant figure as noise.
- **Absolute ms/playout** is one box, sequential, n=480. Cross-check against the
  banked `measurement/tiearb2_stage2_20260817/COST_REMEASURE.json`, which measured
  `c_tier1_rust_w1 = 93.77 ms/playout` on the local 5900XT at `legal_mask_cache=true`:
  the laptop reads **91.29 ms** in that same shape, a **2.6 % difference across two
  boxes and two corpora**. The laptop is a fair proxy.
- **The 7.90× is a paired within-run contrast** on identical work in one process,
  which is the tight class. It is *not* cross-box validated; the mechanism is
  allocator churn (§4), so a different allocator could move it.
- Not measured: `tiearb_threads = 8` scaling (production). These are per-playout
  sequential costs, which is the right currency — threading divides them.

### 1.4 Corpus

6 deck seeds × 10 root plies `{6, 14, 22, 30, 40, 50, 60, 72, 86, 100}` × 4 CRN
determinized worlds × 2 arms = **480 playouts, 45,439 plies, 926,178 candidate leaf
evaluations**. Roots are reached by replaying the middle legal action and then
advanced to the next `Tiles` decision with ≥ 2 arms — the shape the arbiter is
called at. It is a **cost** probe; move quality is irrelevant to what it measures.

---

## 2. The breakdown table

`mode = none` (`legal_mask_cache = false` — what `tiearb::arbitrate` deploys:
`tiearb.rs:443` calls `tier1_playout(world, a, seat, playout_seed, max_plies, None)`).
Timer-tax corrected; shares projected onto the 91.03 ms baseline.

| component | call site | ms / playout | share |
|---|---|---:|---:|
| **`GameState::count_final_scores`** | per candidate, `_best_by_virtual_score` | **88.696** | **97.44 %** |
| `GameState::clone` | per candidate (the scratch afterstate) | 0.563 | 0.62 % |
| `Game::legal_mask` | per ply (the window-mask rebuild) | 0.518 | 0.57 % |
| `GameState::apply_action` | per candidate | 0.473 | 0.52 % |
| `action_space::decode` | per candidate | 0.430 | 0.47 % |
| `Game::advance` | per ply | 0.210 | 0.23 % |
| mask → `Vec<i32>` collect | per ply | 0.108 | 0.12 % |
| argmax + `flatnonzero` | per scored decision | 0.024 | 0.03 % |
| `is_terminal` | per loop iteration | 0.004 | 0.00 % |
| meeple Rule-3 / Rule-2 filter | per meeple decision | 0.003 | 0.00 % |
| `MT19937::randbelow` | per scored decision | 0.002 | 0.00 % |
| residual (unattributed) | — | 0.000 | 0.00 % |

Per-candidate: **45.96 µs** for one `count_final_scores` (88.696 ms ÷ 1,930
candidates/playout). Independently re-measured at **44.75 µs** by the `variant`
binary on a different sample.

Structural counters (per playout): 94.66 plies, 1,930 candidate leaf evaluations,
**34.28 candidates per scored decision**, and **38.9 % of decisions are Rule-1
forced** (17,691 / 45,439) — those skip the candidate loop entirely.

### 2.1 The `legal_mask_cache = true` shape (the banked judge)

Measured as a sensitivity because `G-BITEXACT` and `COST_REMEASURE` graded that
shape (`probe_cache.json`, 480 playouts, gate 480/480):

| | ms/playout | share |
|---|---:|---:|
| `count_final_scores` | 88.420 | 96.86 % |
| *added:* `string_representation` (the memo key) | 0.272 | 0.30 % |
| *added:* HashMap get/insert + `Vec` clone | 0.230 | 0.25 % |
| `Game::legal_mask` (unchanged) | 0.527 | 0.58 % |

**The memo buys nothing and costs 0.55 %.** Counters: **0 hits, 45,439 misses.**
Board states never repeat inside a playout, and the two arms of a leg diverge at
ply 1, so the only hits available in production are the root query and the
documented `string_representation` collisions (57 / 15,360 banked values). Net:
`cache=true` reads **91.29 ms vs `cache=false`'s 91.03 ms** — 0.3 % slower, and the
sign matches the counters. This is a note, not a lever: the cache is load-bearing
*because it is buggy* (`tier1.rs` module docs) and must not be switched for speed.

---

## 3. Cost vs remaining plies — **the phase-gate arithmetic's assumption is wrong**

Playout cost is **not** proportional to remaining plies. The naive fit is bad on
purpose:

```
secs = 48.10 ms + 0.4535 ms/ply       R² = 0.218   (n=480, plies 41–137)
```

The huge intercept and the low R² are the symptom. The mechanism is visible in the
group means — the number of plies falls with root ply, but the **cost per ply rises
1.8×** as the board fills:

| root ply | n | mean plies | mean ms | **ms / ply** |
|---:|---:|---:|---:|---:|
| 6 | 48 | 136.7 | 96.67 | 0.707 |
| 14 | 48 | 128.6 | 100.23 | 0.779 |
| 22 | 48 | 120.7 | 103.52 | 0.858 |
| 30 | 48 | 112.7 | 103.44 | 0.918 |
| 40 | 48 | 102.7 | 100.47 | 0.979 |
| 50 | 48 | 92.7 | 96.10 | 1.037 |
| 60 | 48 | 82.7 | 102.47 | 1.240 |
| 72 | 48 | 70.7 | 83.84 | 1.187 |
| 86 | 48 | 56.7 | 73.21 | 1.292 |
| 100 | 48 | 42.7 | 50.36 | 1.180 |

**Size of the error.** A `cost ∝ plies` model anchored at root ply 6 predicts
`96.67 × 42.7/136.7 = 30.2 ms` at root ply 100. Measured: **50.36 ms**. The
proportional model **understates late-game arbiter cost by 1.67×**, and cost is
roughly *flat* from ply 6 to ply 60 (96.7 → 102.5 ms) despite a 40 % drop in plies.

The mechanism is direct (§4.2): per-candidate `count_final_scores` grows from
6.4 µs on a near-empty board to 66.7 µs at 65–77 placed tiles — a **10.5× rise** —
and candidate counts grow too. Any budget rule that prices a late-game arbiter call
by remaining plies is under-charging it.

---

## 4. Option B, sized

### 4.1 What the lever actually is

`count_final_scores` (`engine/mod.rs:725`) walks each placed meeple and, per meeple,
runs a **from-scratch flood fill** — `find_city` / `find_road` /
`find_farm_by_coordinate` (the last a `HashSet`-based DFS) — then does an
`O(|component| × |placed_meeples|)` linear scan in `*_find_meeples`. It is re-run
from zero for every one of the ~34 candidates at every ply, on a board that changed
by one tile.

`carc-core` **already ships the alternative**: `leaf::decomp::decompose_into`
(whole-board int union-find, allocation-free after warm-up, caller-owned
`Decomp` + `Scratch` buffers) + `leaf::flat_base_score`. `tier1.rs`'s own module
docs name the equality (`virtual_score == flat_leaf.flat_base_score == rust`), the
P2 suite asserts it on every position, and DECISIONS 2026-07-31 (G1) re-proved it
on **134,172 evaluations across the whole game record**.

⚠️ The old parked verdict (DECISIONS 1038–1049, "union-find cannot reproduce
`find_farm` because it is start-dependent") is **python-era and superseded** — the
2026-05-29 `TRT→BRB` fix made `find_farm` start-independent, and `leaf::decomp` is
the union-find that verdict said could not exist.

### 4.2 Measured, per candidate (`variant.json`, 238,203 candidate evaluations)

**Identity gate: 238,203 checked, 0 mismatches** on the i64 the candidate loop
consumes.

| | µs / candidate |
|---|---:|
| `count_final_scores` (**engine route, deployed**) | **44.753** |
| `decompose_into` (decomp route) | 5.425 |
| `flat_base_score` over the `Decomp` (decomp route) | 0.281 |
| — decomp route total | **5.706** |
| `GameState::clone` (needed by both) | 0.316 |
| `apply_action` (needed by both) | 0.257 |

**Scorer factor: 7.84×.** And it widens with board occupancy — the engine route is
what scales badly:

| placed tiles | n | `count_final_scores` µs | decomp route µs | factor |
|---|---:|---:|---:|---:|
| 0–12 | 2,818 | 6.36 | 1.35 | 4.7× |
| 13–25 | 17,589 | 15.79 | 2.56 | 6.2× |
| 26–38 | 39,310 | 27.10 | 3.79 | 7.1× |
| 39–51 | 62,140 | 38.96 | 5.10 | 7.6× |
| 52–64 | 74,729 | 54.90 | 6.79 | 8.1× |
| 65–77 | 41,617 | 66.71 | 8.09 | 8.2× |

### 4.3 Measured, end to end (`swap.json`, 216 playouts)

The `swap` binary runs the whole playout twice on the same `(world, pick, seed)` —
once with the engine scorer, once with **only the per-candidate scorer swapped**,
buffers reused — and gates **both** against production `tier1_playout`.

**Identity gate: engine-route shadow 0 / 216 mismatches; decomp-route shadow
0 / 216 mismatches**, comparing `(margin, plies)` — which transitively covers the
argmax tie set and every downstream `randbelow` draw.

| | s / playout |
|---|---:|
| engine route (production) | 0.084267 |
| decomp route | 0.010667 |
| **end-to-end factor** | **7.90×** |

| root ply | n | engine ms | decomp ms | factor |
|---:|---:|---:|---:|---:|
| 6 | 36 | 88.39 | 11.95 | 7.40× |
| 22 | 36 | 97.25 | 12.00 | 8.10× |
| 40 | 36 | 100.92 | 12.05 | 8.38× |
| 60 | 36 | 96.85 | 11.58 | 8.36× |
| 86 | 36 | 71.77 | 9.27 | 7.75× |
| 100 | 36 | 50.42 | 7.16 | 7.05× |

The end-to-end 7.90× slightly **beats** the arithmetic from §4.2 (which predicts
`91.03 / (2.33 + 88.70/7.84) = 6.67×`). The gap is real and has a mechanism: in
`variant` the two routes interleave and evict each other's working set, whereas in
`swap` the reused `Decomp`/`Scratch` buffers stay hot. Take 6.7× as the
conservative floor and 7.9× as the measured in-situ value.

### 4.4 Allocation pressure — the mechanism

From the `allocount` build (a counting `GlobalAlloc`, separate binary so it never
perturbs a timing pass), over 120 baseline playouts:

- **1,333,096 allocations per playout**
- **118.63 MB allocated per playout**
- peak RSS **3.9 MiB**

That is **~690 allocations and ~61 KB of churn per single `count_final_scores`
call** — a `HashSet` per `find_farm`, `Vec`s per `City`/`Road`/meeple list, all
freed immediately. It is pure allocator traffic against a 3.9 MiB live set.
`decompose_into` is allocation-free after warm-up by construction, which is why the
factor is ~8× and not ~2×.

### 4.5 What this buys, in the program's own currency

`governance/PRODUCTION.yaml` records the desktop fold at **B = 64 CRN worlds,
J ≤ 4 arms, `threads: 8`**, with the accepted cost **`rho_wall(64) = 2.4897`**
sequential-amortized arbiter overhead (≈ 3.5× total per move) against the retired
N4 bar of 1.20. Playout cost enters `rho` linearly, so at the measured factor:

| | `rho_wall(64)` |
|---|---:|
| today | 2.4897 |
| at the conservative 6.7× | **0.372** |
| at the measured 7.9× | **0.315** |

Either lands ~3–4× **under** the 1.20 bar. Equivalently, at today's wall budget the
same money buys **B ≈ 430–500** instead of 64. On mobile (`threads: 2`, Pixel,
1.551 s/move ceiling) the same factor applies to the arbiter's share of the move.

**No promotion, no deploy, no elo claim is made here.** This is a cost measurement;
what a bigger B or a cheaper move is *worth* is a separate, strength-side question
and the `tiearb_widening` ladder owns it.

### 4.6 What the bit-identity gate would have to check

Already passed here:

1. **Per-candidate value identity** — 238,203 / 238,203 exact (`variant.json`), on
   real afterstates of both phases.
2. **Trajectory identity** — 216 / 216 playouts identical in margin *and* ply count
   (`swap.json`), which covers the tie set and the RNG stream.

Still open, and the gate must cover them:

3. **The banked `G-BITEXACT` sample** — 15,360 playout values from the Stage-1b
   corpus, at `legal_mask_cache = true`. My swap ran `cache = None` (what
   `arbitrate` deploys); the banked judge is the other shape and its memo
   collisions are load-bearing.
4. **`tiearb::arbitrate`'s own identity gate** — the f64 reduction order, the salt /
   digest path, and `threads ∈ {1,2,4,8}` (its existing
   `threading_is_bit_identical_to_sequential` test).
5. **⚠️ Border pathologies — the routes are KNOWN to disagree.** DECISIONS
   2026-07-31 records that `count_final_scores` **dies** on last-row and col-34
   placements where `flat_leaf.flat_base_score` **scores fine** — "the routes
   disagree … a Python-internal inconsistency now pinned by both drivers". A swap
   therefore converts a crash into a value on those positions. They should be
   unreachable under the production centred window, but the gate must *prove*
   unreachability rather than assume it, because this is the one place where
   bit-identity is already known to fail.
6. **`farm_off` must be `false`.** `leaf::flat_base_score` delegates to
   `flat_base_score_farm(.., farm_off = false)`; only the leaf's own base term
   passes `true`. Passing `true` here would silently change the player.
7. **Buffer ownership.** The 7.9× needs ONE `Decomp` + `Scratch` pair reused across
   candidates, plies and playouts. Threading them into `RuleBasedPlayer` /
   `tier1_playout` is an API change, and with `tiearb_threads = 8` each worker
   thread needs its own pair — the same pattern `tiearb.rs` already uses for
   `LeafScratch`. A per-call `decompose()` (the allocating wrapper) would throw the
   win away.

---

## 5. Surprises

1. **The advisory's mechanism is wrong, and its number is 2.5–5× too small.**
   Clone + mask-rebuild + apply are **1.71 % combined**. There is no "incrementalize
   the clone" lever; there is one call worth 97.4 %.
2. **The fix is already in the repo, already tested, and already gate-proven equal
   to the thing it would replace.** Option B is not "write an incremental scorer",
   it is "call `leaf::decompose_into` instead of `count_final_scores`, and thread
   two scratch buffers". That is a much smaller change than 1.5–3× would justify,
   for a much bigger win.
3. **Cost is not proportional to remaining plies** (§3) — the proportional model
   under-charges a late-game arbiter call by 1.67×, and cost is nearly flat from
   ply 6 to ply 60.
4. **The legal-mask memo has a 0 % hit rate inside a leg** and costs 0.55 %. It is
   still mandatory for bit-exactness (its collisions are the banked judge), but it
   is not a performance feature and never was.
5. **118 MB of allocator churn per playout** against a 3.9 MiB live set.
6. **A parked 2026-05 verdict is stale.** "Union-find cannot reproduce `find_farm`"
   was true of the pre-fix python engine; `leaf::decomp` is that union-find, and it
   agrees with `count_final_scores` on 238,203 / 238,203 candidates.

---

## 6. Artifacts

| file | what |
|---|---|
| `probe_none.json` | the breakdown, `legal_mask_cache=false` (deployed shape), 480 playouts |
| `probe_cache.json` | the breakdown, `legal_mask_cache=true` (banked-judge shape), 480 playouts |
| `probe_alloc.json` | allocation census (counting `GlobalAlloc` build), 120 playouts |
| `variant.json` | per-candidate engine-route vs decomp-route, 238,203 candidates, bucketed by board occupancy |
| `swap.json` | end-to-end playout with only the scorer swapped, 216 playouts, both routes gated |
| `ANALYSIS.json` | timer-tax-corrected tables emitted by `analyze_profile.py` |
| `analyze_profile.py` | the corrections and the fits; documents the tick-count model |
| `costprobe_src/` | the instrument (out-of-tree crate) + the three run scripts + their logs |
| `full.log`, `variant.log`, `swap.log` | before/after census for every timing run |
