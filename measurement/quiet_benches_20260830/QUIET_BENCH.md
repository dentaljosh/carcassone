# Quiet-window benches — the three owed re-reads (2026-08-30)

**Box:** local 5900XT (16C/32T), **EXCLUSIVE TENANT**. `loadavg` 0.10–0.19 immediately
before every bench; the ≤1.05 reads seen during the consumer arms are this bench's own
single-threaded process decaying into the average. **No foreign tenant appeared at any
point in the window.** Machine-readable: `QUIET_BENCH.json`.

These are re-reads of numbers three separate 2026-08-30 rounds banked on a **contended**
box and explicitly labelled "direction only, magnitude owed". Nothing here promotes
anything: two of the three levers are bit-identical by construction, so only throughput
is at stake, and the third is a cross-check census.

> **Output convention.** The source worktrees are read-only to this agent, so every
> artifact lands here and is keyed to its source branch + commit.

---

## 1. Registry flattening — `agent-a396dc03111d62cda` @ `35569f38d4abb5981c3b6287766941a3c8bcf3db`

Owed: `measurement/registry_flattening_20260830/READOUT.md` §6 items 1–3.

### 1a. Bench A — the decompose cost law (§6.1) — **the definitive factors**

Harness unmodified (`registry_flat_bench.rs`, the worktree's own prebuilt release
binary), 4 replicates, 575 samples × 400 reps per arm.

| | contended (banked) | **quiet (this re-read)** |
|---|---|---|
| **slope factor** (ns/placed) | 1.156–1.187× | **1.180–1.190×, mean 1.185×** |
| **decompose factor** | 1.152–1.157× | **1.171–1.179×, mean 1.174×** |
| **decompose + leaf, both povs** | 1.117–1.149× | **1.132–1.138×, mean 1.135×** |
| ref slope, ns/placed | 181.2–210.9 | **121.7–124.8, mean 122.9** |
| flat slope, ns/placed | — | 102.8–104.9, mean 103.7 |
| fit R² (ref) | 0.751–0.864 | **0.991–0.995** |

Two things the quiet box settles:

* **The instrument is now trustworthy.** R² 0.99+ against the contended 0.75–0.86, and
  the reference slope lands at **122.9 ns/placed against the sweep's quiet 5900XT figure
  of 124.73** — i.e. the quiet re-read reproduces the independently-banked quiet cost law
  to ~1.5%. The contended run's 181–211 was 1.5–1.7× inflated, exactly as the READOUT
  suspected.
* **The READOUT's stated caveat runs the wrong way.** §4.2 warned that "a DRAM-contended
  box should *flatter* the flat arm — the quiet factor may be lower than 1.15×". It is
  **higher**: 1.174× quiet vs 1.152–1.157× contended. Contention *understated* the lever.

Against the funding estimate ("an upper bound of ~1.2–1.3× on decompose"): the quiet
slope factor **1.185×** sits just under the bottom of that band, and the estimate is
now **resolved** rather than left open — it was an upper bound and the realized value
lands beneath it, close.

Per-bucket (replicate 4) is in `QUIET_BENCH.json`; the no-small-board-regression claim
holds — the flat arm wins in every one of the ten 8-tile bands, 1.10–1.18×.

### 1b. The consumer arms (§6.2 search slice, §6.3 tier1 playout) — **new measurement**

Neither arm existed. Both were written for this re-read as
`quiet_consumer_bench.rs`, in a **scratch copy** of the crate (the source worktree is
read-only here) — the example and its arm switch are not in any worktree.

*Arm switch:* a `OnceLock` dispatch inserted at the top of
`leaf::decomp::decompose_into` reading `CARC_DECOMP_REF`, routing to the frozen
`decompose_into_ref` when set. Both arms pay the identical branch, so the factor is
unaffected. **Identity receipts:** every root reported the same `chosen_action`,
`node_count` and `root_n`, and every tier1 playout the same `margin` and ply count, in
both arms — READOUT §3's bit-identity re-observed at the consumer level rather than
assumed.

3 alternating ref/flat replicate pairs, `SearchConfig::default()` (sims **1376**):

| consumer | shape | **factor (mean, [min, max])** |
|---|---|---|
| **search slice** — whole `search_single` | 3 deck seeds × plies 10/30/50/70/90, 7 timed reps/root | **1.086× [1.066, 1.106]** |
| **tier1 playout** — `tier1_playout` to terminal | 3 deck seeds × plies 8/24/40, 12 playouts/rep | **1.136× [1.133, 1.142]** |

Whole-process wall clock corroborates: 19.2–19.7 s ref vs 17.7–17.9 s flat (**1.08×**).

**What the search number settles.** READOUT §4.3 declined to project search-level gain
from the spike's "decompose ≈ 0.605 of PUCT total" because that share came from a
different box and arm. Measured directly: 1.086×. Inverting
`1/(1−s+s/f)` at the measured `f = 1.174` gives an implied decompose share of
**s ≈ 0.54** of whole-PUCT on this box — near the spike's 0.605, a little below it. The
§4.3 projection at s=0.605 would have said 1.098×; the truth is 1.086×.

**tier1 gets more of it than search does** (1.136× vs 1.086×), which is what the
structure predicts: tier1's per-candidate scorer is nearly all decompose, while PUCT
carries ~46% non-decompose work.

## 2. L1a meeple-phase hoist — `agent-acf104f4eb41c6a55` @ `5aa789725cf906ff9661c3e0b52fd2b4e9a576d5`

Owed: `measurement/arb_costopt_prep/GATES_L0_L1A_20260830.md` §3 item 2 — "L1a bench
re-read on an exclusive box (the 4-root ply table)". Harness unmodified
(`cargo test -p carc-core --release -- --ignored bench_meeple_hoist`), 3 replicates,
1376 sims, 8 interleaved A/B reps per root.

| root | banked (contended) fresh | **quiet fresh** | banked factor | **quiet factor** (r1/r2/r3) |
|---|---:|---:|---:|---|
| `28000000000` ply 30 | 152.01 ms | **69.4 ms** | 1.0563× | **1.0709 / 1.0615 / 1.0701** |
| `28000000000` ply 55 | 182.42 ms | **82.9 ms** | 1.0638× | **1.1016 / 1.0971 / 1.0914** |
| `42` ply 80 | 337.21 ms | **164.6 ms** | 1.0271× | **1.0378 / 1.0307 / 1.0359** |
| `11` ply 105 | 564.87 ms | **279.0 ms** | 1.0165× | **1.0235 / 1.0239 / 1.0272** |
| **POOLED** | 309.13 ms | **149.0 ms** | **1.0309×** | **1.0431 / 1.0398 / 1.0429 → 1.042×** |

* **The contended absolutes were ~2.05× inflated** (149.0 ms pooled quiet vs 309.13 ms).
* **The banked caveat's direction is confirmed:** the readout predicted "the exclusive
  factor is very likely higher than 1.031×" because contention adds a common additive
  term pulling a paired ratio toward 1. It is **1.042×**, and the replicate spread is
  ±0.002 — tight.
* **The ply decay survives, and sharpens.** 1.071 / 1.098 / 1.035 / 1.026 across plies
  30/55/80/105. The early-ply reads now **exceed** the sweep's 1.06–1.07× band (ply 55
  reads 1.09–1.10×), the late-ply reads sit at half of it.
* The readout asked that L1a's search-path contribution be carried as "~1.03–1.06×,
  ply-dependent" rather than a flat 1.06–1.07×. The quiet read supports that shape and
  narrows the pooled value to **1.042×**; the ply-dependent range widens slightly to
  **~1.03–1.10×**.

## 3. OM-D2 residual full join — `agent-a6de39b2de1b23a94` @ `16924e2f5d9007e2ce845204d4dee51ca2cad035`

Owed: `measurement/omm1_refuter_gate_20260830/DEVIATIONS.md` `OM-D2` — the
`build_fired_plies.py --limit 120` leaf-only re-run closing the **10-unverifiable-keys**
caveat. Ran in **2.12 s** at W=30 (the ~20 s estimate was conservative).

**The caveat's mechanism, found:** `_g_fire_join` recorded `disagreement_examples` under
`if len(examples) < 10`. That hard cap *is* the 10 unverifiable keys — the other 10
disagreeing plies were never written down. The re-run records **every** disagreeing key
together with the census's own `gap`, so each is verifiable.

The join reproduces the banked slice exactly:

| | banked | re-run |
|---|---:|---:|
| joined keys | 4,443 | **4,443** |
| disagreements | 20 | **20** |
| agreement | 0.99550 | **0.995499** |
| `G-FIRE` | PASS | **PASS** (fired/tied 0.8167, in the 0.60–1.00 bracket) |

### ✅ All 20 disagreeing plies now have verifiable witnesses — 0 unverifiable.

Classified by the census's own `gap = top1 − top2`:

| class | banked (of the 10 recorded) | **full join (of all 20)** |
|---|---:|---:|
| **ULP** (`1.776e-15`) | 2 | **2** |
| **REAL** (a real gap) | 8 | **18** |
| unrecorded / unverifiable | **10** | **0** |

**Every one of the 10 previously-unrecorded keys is REAL class.** The ULP count is
unchanged at exactly 2, so the benign fraction is **2/20 = 10%**, not the 2/10 = 20% the
partial record implied. `DEVIATIONS.md` wrote that classifying the residual "makes it
worse, not better"; the full join makes it worse again, by the same argument extended to
the whole set.

The 18 REAL witnesses (`deck_seed`, `ply`, `gap`) — 8 banked, **10 new**:

| deck_seed | ply | gap | | deck_seed | ply | gap |
|---|---:|---:|---|---|---:|---:|
| 28000000059 | 138 | 1.00 | | 28000000078 | 52 | 0.60 ⬅ new |
| 28000000086 | 24 | 1.00 ⬅ new | | 28000000017 | 30 | 0.50 |
| 28000000015 | 72 | 1.00 | | 28000000050 | 24 | 0.50 |
| 28000000011 | 24 | 0.75 | | 28000000096 | 18 | 0.50 ⬅ new |
| 28000000022 | 66 | 0.75 | | 28000000012 | 112 | 0.40 |
| 28000000076 | 112 | 0.75 ⬅ new | | 28000000106 | 22 | 0.35 ⬅ new |
| 28000000093 | 20 | 0.75 ⬅ new | | 28000000115 | 60 | 0.30 ⬅ new |
| 28000000100 | 94 | 0.75 ⬅ new | | 28000000052 | 48 | 0.25 |
| 28000000072 | 12 | 0.60 ⬅ new | | 28000000096 | 124 | 0.10 ⬅ new |

ULP class: `(28000000031, 110)` and `(28000000031, 114)`, both gap `1.7763568394e-15`.

**One shape the partial record hid.** The banked 8 REAL gaps were all clean multiples of
a quarter point (0.25/0.40/0.50/0.75/1.00). The 10 new ones include **0.10, 0.30, 0.35,
0.60, 0.60** — the divergence is not confined to quarter-point ties. It also reaches a
gap as small as **0.10**, and `(28000000096, 124)` at 0.10 is the tightest REAL witness
in the set. `DEVIATIONS.md`'s owed follow-on (localise the REAL class by diffing
`tiearb_probe`'s `chain_values` against `chain_census.chain_values` per-action) now has
**18** witnesses to choose from instead of 8, and the new low-gap ones are the cheapest
place to start. That localisation was **not** run here.

Artifacts: `omd2_fulljoin_limit120/{FIRE_CENSUS.json,FIRED_PLIES.jsonl}` — the census
JSON carries the full `witnesses` array. The patch is confined to `_g_fire_join`'s
reporting (the cap, plus the gap lookup); the join predicate, the population and the
`G-FIRE` bar are untouched, which is why the counts reproduce exactly.

---

## Nothing promoted

No `experiments/results.csv` row, no claim id, no band, no `governance/PRODUCTION.yaml`
field, no strength game. Items 1 and 2 are throughput re-reads of bit-identical levers;
item 3 is a cross-check census whose gate re-passed. Each source round's own §-owed list
is what these discharge, and the merge decisions they gate remain the source rounds' to
make.
