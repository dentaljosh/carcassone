# TILE-TIE PRICING — the production-knob SMOKE

**Status: RAN 2026-08-12.** Purpose: (a) de-risk the cross-leg CRN claim that the whole K-way
design rests on, and (b) measure `c`, the worker-seconds per oracle playout, so
[DESIGN.md §7.4](DESIGN.md) can price the run. It is **not** a measurement of the pre-registered
statistics and no result from it is read as one.

Command:

```
.venv/bin/python -u scripts/tiletie/run_tiletie.py --smoke --yes --workers 8 \
  --smoke-profile fixed_v1
```

Production knobs, unchanged from the real run: `M = 32`, `--oracle-sims 100`,
`--world-seed-salt tiletie-v1`, `clair-puct`, `--max-plies 400`. **Only the position count
differs** (5 instead of n, and only positions with ≥3 arms so that leg1 and leg2 both exist).

---

## 1. Preflight — all four checks PASS

| check | result |
|---|---|
| **rust identity gate re-verified AT HEAD** | **PASS — 8 positions, 376 field checks, 0 mismatches** → `GATE_BACKEND_RECHECK.json` (the committed `measurement/rustport_p6/GATE_ORACLE_PILOT_BACKEND.json` was NOT overwritten) |
| production leaf hash | **PASS** — `harness_leaf_hash = a36d2e15a3b3d71d` |
| git clean under `src/` + `engine/` | **PASS** — rev `79e93f2`, no dirty paths |
| positions plan integrity | **PASS** — 12 leg files, every rid present in `ARMS.json`, line counts match `POSITIONS_PLAN.json` |

The gate result is byte-for-byte the same shape as the budget-headroom run's own
re-verification (*"8 positions, 376 field checks, 0 mismatches"*), i.e. the ruler is the ruler.

---

## 2. Two real bugs the smoke caught (both would have been silent or costly)

1. **`select_smoke_positions` was not profile-aware.** It chose the globally-first eligible rids
   from `ARMS.json` and then filtered a *per-profile* leg file, so the intersection was empty
   and the smoke "ran" in 0.2 s with 0 positions. Two consecutive smokes reported a clean-looking
   ETA off **zero work**. Fixed to filter eligible rids on `rules_profile` before selecting.
   ⚠️ *An instrument that reports a throughput number without doing any work is the exact failure
   mode the standing "verify parallelism / verify numbers before reporting" rules exist for.*
2. ⭐ **The rust clairvoyant ruler cannot mirror `fixed_v1`** — 5/5 positions failed with
   > *"the clairvoyant Rust ruler cannot mirror `['start_row/start_col', 'fixed_start_tile',
   > 'cloister_scan_fix', 'draw_rule']`: `RustCarryClairvoyantAgent` seeds
   > `MirrorState.from_deck()` with no geometry/rules config (unlike the fair `RustFairAgent`,
   > which forwards them), so it would run the engine-default rules against a game that does
   > not."*

   This is the harness **failing loud rather than grading 23 of 26 E4 games under the wrong
   rules**. Backend is now resolved per **(judge, profile)** — `run_tiletie.backend_for` /
   `RUST_OK_PROFILES` — and DESIGN §2.0 carries the consequence. **This re-priced the whole
   run** and it cost a 5-position smoke instead of a multi-hour one.

---

## 3. Measured cost — `c`, per backend

leg1, `fixed_v1`, **python** backend: 5 positions, **5/5 ok, 0 failed, `crn_verified_all` true**,
wall 1,199.9 s at `--workers 8` (the pool caps at `min(W, todo) = 5`).

| position | ply | worker-secs (`elapsed_secs`) |
|---|---|---|
| `tt_e4_1785982194_705585_p10` | 10 | **1,199.8** |
| `tt_e4_1785982194_705585_p34` | 34 | 1,042.9 |
| `tt_e4_1785982194_705585_p106` | 106 | 421.1 |
| `tt_e4_1785982194_705585_p114` | 114 | 359.1 |
| `tt_e4_1785982194_705585_p134` | 134 | **129.7** |
| **Σ** | | **3,152.6** |

```
playouts        = 5 positions x 2 arms x 32 worlds = 320
c_python        = 3152.6 / 320 = 9.85 worker-s per playout      <- COST FROM THIS
c_python (wall) = 1199.9 x 5 / 320 = 18.75                      <- 1.9x too high, do NOT use
```

⚠️ **Cost from `Σ elapsed_secs`, never from `wall × W`.** The pool's wall is set by its slowest
member, and these positions differ by **9.3×** (1,199.8 s vs 129.7 s). The launcher prints the
wall-based figure; DESIGN §7.4 costs from the sum.

⭐ **The 9.3× spread is phase, not noise** — early roots have far longer clairvoyant playouts to
terminal. Every ETA is therefore a function of the sampled phase mix, and the read-out must check
`phase_bucket` / `tercile` balance after the fact rather than assuming it.

⚠️ **Contention caveat.** The census legs and an unrelated 6-worker `oracle_score_pilot` job from
another agent were on the box during parts of this session. leg1 ran after that job ended
(loadavg ~1.2–3.6), so `c_python` is close to clean, but it is still an **upper bound**, not a
quiet-box number. Per the standing rule that a throughput farm beside a timing bench contaminates
the bench, re-measure before treating any ETA as a commitment.

⚠️ **`c_rust = 1.65` is NOT measured here** — it is carried from the budget-headroom run, whose
positions are CL-070 *disagreements* (mid/late-skewed, i.e. cheap). A `walled`/rust smoke is the
outstanding item before the rust arm's ETA is a commitment. Do not read `9.85 / 1.65` as the
backend speedup; the identity gate measures that at 9.41–9.48× on matched positions.

---

## 4. The nuisance parameter — sd (and ONLY sd)

`sd_delta_positions = 2.2569` at M = 32 (`sd_delta_projected_by_m`: M8 3.438 · M16 **2.709** ·
M32 2.257 · M64 1.993).

This is the **planning sd for §7.2**, and it came in **better than the transplanted 3.0–3.16**:
the leaf-tied population is tighter than the CL-070 disagreement population, as the "tied
siblings are similar" prior predicts. At the M = 16 cross-fit column (2.709):
**±35 elo needs n ≈ 228 · ±17 elo needs n ≈ 965.**

⚠️ **n = 5. This is a coarse read of a nuisance parameter, not a verdict.**

🚫 **The smoke's mean delta is deliberately NOT recorded in this file.** It is a 5-position read
of a quantity DESIGN.md pre-registers, and quoting it would be peeking at the result the run
exists to measure. Only the sd is carried forward — which is exactly what the original oracle
pilot was built for.

---

## 5. The CRN cross-leg witness

The K-way design (DESIGN §2.1) rests on: *because world and playout seeds are keyed on `rid` +
the run-wide salt and not on the arms, separate per-leg invocations sharing a `rid` see the same
M worlds.* If that is false, cross-arm CRN collapses and the run is void.

The witness re-loads each leg's `records/<rid>.json` and asserts, per rid:

1. `values_a` **bit-identical** across legs (raw f64 bit patterns via `struct.pack('<d', x)`, the
   same surface the rustport identity gate uses — never `==` on floats, never `approx`);
2. `world_seeds` and `playout_seeds` identical across legs;
3. `afterstate_deck_hash_a` identical across legs and `crn_verified` true in every leg.

It is a reusable function (`run_tiletie.check_crn_cross_leg`) so the post-run analyser re-applies
it to the full run, and the smoke **exits non-zero on FAIL**.

### ✅ RESULT: **PASS — 5/5 rids**

`SMOKE_MANIFEST.json` → `crn_cross_leg_identical: true`, `crn_cross_leg_checked_rids` = all five.
`crn_verified` is true in all 10 records (both legs), 10/10 ok, 0 failed.

⇒ **the K-way decomposition is sound.** Separate `oracle_score_pilot` invocations sharing a
`rid` and the run-wide salt do see identical worlds and identical playout seeds, so every arm at
a position is fully CRN-paired against every other — with the instrument **unmodified**. The
reference arm's `values_a` is bit-identical across legs, which also means the harness is
deterministic at these knobs on this revision.

---

## 6. Two costs measured across both legs

Σ `elapsed_secs` over all 10 records = **6,310.1 worker-s** / 640 playouts =
**`c_python` = 9.86 worker-s/playout** (leg1 alone gave 9.85 — stable).

The leg-2 re-run also exposed that the smoke hardcoded `resume=False`; a 40-minute python smoke
that cannot resume is how an interrupted run becomes an 80-minute one. Fixed to honour
`--resume`/`--no-resume` (the pilot writes per-position records via tmp + `os.replace`, so
resuming is safe).

---

## 7. ⭐ The finding the smoke was not looking for

Two of the five positions returned **`distinct_afterstates = 0`** — the tied arms reached the
*same* board in all 32 worlds. That is a **transposition**, not a value tie, and it prompted
`scripts/tiletie/transposition_census.py`, which measured it over the whole tied population:
**23.8% (E4) / 27.8% (self-play) of exact-tie sets collapse to a single board.**

See [DESIGN.md](DESIGN.md) §6 threat 3 for the consequence — arms are now deduplicated by
successor board key, all-transposition positions are counted as analytic zeros instead of being
scored, and the census's 66.0% is restated as a leaf-**silence** rate whose genuine-blindness
component is ≈53%.
