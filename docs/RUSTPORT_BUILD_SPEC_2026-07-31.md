# Rust engine+search core ("carc-core") — build spec

> **STATUS: BUILDING (approved by Joshua 2026-07-31 ~15:00, "this is all good to me... lets
> see how far this gets in 36 hours").** Committed BEFORE the first line of Rust (house
> prereg style). Orchestration: main session (Fable) orchestrates; engineer subagents run
> Opus ("make sure you're the only fable dude"). Local box has ~16 spare SMT threads
> alongside the leaf-ablation chain — builds/tests may use them (nice -19).

## Goal & decisions

**v1 = phone champion parity.** Rust core under PyO3 (`carc_rs`); Python stays the
orchestrator everywhere (farms + Chaquopy bridge keep provenance/config/UI). The k8×1376 =
11008 champion runs on the Pixel via k world-threads inside one GIL-released call
(Chaquopy has no mp; the GIL forbids Python threads — that's the entire ~50-elo mobile
carve-out). Joshua's semantics decision: **default = byte-compatible with today's engine**
(walled 35×35, row-6 start); centered-start (6→18, EVEN shift only) + retail-start-tile
ship as opt-in flags from day one (mirroring worktree commits `b7d61ab`/`6d8385d`/`8d877fc`).
No PRODUCTION.yaml change; no strength claim — behavior identity transfers CL-060/071's
measured strength (the CL-071 precedent).

## Non-negotiable bars

1. **Bit-exactness**: `test_kparallel`-style full-game action identity incl. raw-float
   pooled-W equality; per-phase `scripts/rustport/reconcile_*.py` gates, "0 mismatches,
   full stop" (the reconcile_cy_leaf precedent).
2. **The record replays**: CPython MT19937 (`seed`/`Random(n)`/`_randbelow`/`shuffle`)
   reproduced exactly; all 449 `champ_games.jsonl` games + both E4 phone archives replay
   bit-identically (per-ply byte-equal `string_representation`).
3. **Quirks are features**: tied-feature full points · farm involution TRT→BRB ·
   complete-DFS find_farm with stable `(coord, farm_slot_idx)` keys (Python uses `id()`) ·
   PassAction-in-TILES patch · cloister 3×3 · `has_cathedral` driven by `tile.inn` ·
   `(row,col)`-sorted open-position emission × rot 0..3 · banker's rounding
   (`round_ties_even`) · `math.fsum` (Shewchuk) reductions, fixed R-then-F add order ·
   float32 prior round-trips + numpy **pairwise** sums at the two prior sites ·
   pooled merge in world order 0..k−1 · `pooled_q_argmax` tiebreak (Q, N, −action),
   min_pooled_visits=2 · strict-> PUCT argmax (first-best = lowest index), fpu None ⇒
   unvisited q=0.0 · forced-move short-circuit · one-way TILES-phase exact latch at
   k_remaining≤2, marginalized expectiminimax (bag grouped by description), terminal =
   flat_base_score P0 POV, `min(optimal_actions)`, node-count budget, BudgetExceeded ⇒
   PIMC for that move only · meeple tuples in `placed_meeples` list insertion order
   (feeds the repr key).

## Architecture (see plan session 2026-07-31; recon reports in the git-tracked spec's history)

- Workspace `rust/carc/` — members `carc-core` (pure Rust), `carc-py` (pyo3 cdylib,
  module `carc_rs`, top-level package per the carc_cy Chaquopy asset-split rationale),
  `carc-cli` (replay/digest binary). Sibling of carc-orch, NOT merged into it (libtorch,
  x86-scoped mold config).
- `carc-core::compat`: `mt19937.rs` · `fsum.rs` (CPython math_fsum port) · `npsum.rs`
  (numpy pairwise, blocked 8-way unrolled, threshold 128, f32+f64) · `libm_compat.rs`
  (`exp64` from ARM optimized-routines — common ancestor of glibc ≥2.27 and bionic;
  `tanh64` from fdlibm; NOT the musl-derived libm crate).
- **Tile data codegen, checked in**: `scripts/rustport/export_tile_data.py` →
  `tiles/generated.rs` (+ source sha256 header); drift-guard test compares hashes + full
  semantic digest incl. dict insertion order. No Python-invoking build.rs.
- **FFI = mirror state advanced by action ints** (the replay contract as wire format):
  `FairAgentRs.new(cfg)` · `start_game_from_seed(deck_seed)` (MT-compat; farms/tests) ·
  `start_game_from_deck(Vec<String>)` (phone path — no RNG dependence) ·
  `advance(action)` every applied action both seats · `choose_action(move_idx)` under
  `allow_threads` (latch + solver + PIMC inside) · `state_digest()` / `string_repr()` ·
  `stats()`. Adapter `src/carcassonne_ai/rust_agent.py` with reconcile mode
  (`CARC_RS_RECONCILE=1`: per-move digest assert, hard error). Factory `backend="rust"`
  selector; semantic guards (leaf value panel, curve125, fingerprints) run against
  carc_rs. Bridge: `advance` at the single step choke point; Python engine stays
  authoritative for UI/legality/save.
- **Node keying**: emit exact `string_representation` bytes (`repr_key.rs`);
  `FxHashMap<Box<str>, NodeId>`; NodeId equality = Python object-identity dedup. Byte
  equality is itself a gate. Hash-interning only after gates are green.
- **Threading**: determinizations generated sequentially (preserves `Random(base+1)` draw
  order), k world-jobs on `std::thread::scope` over `min(k, threads)` workers, merge =
  sequential fold in world order. Phone default threads ≈ big+mid cores (G7 soak tunes).
- **Android wheels**: `android/tools/build_rust_wheels.py` cloning build_cy_wheels
  (shared helpers → `_chaquopy_common.py`): NDK linker env (NOT `PYO3_CROSS_LIB_DIR` — see the P7 gate-row correction), explicit `-lpython3.12`,
  `-Wl,-z,max-page-size=16384`, readelf assertions, wheel `cp312-cp312-android_21_<abi>`,
  content-addressed version; gradle `buildRustWheels` cloned from `BuildCyWheels`.
  maturin = desktop dev wheels (cp312 + cp314).

## Phases & gates

| phase | scope | gate |
|---|---|---|
| **P0** | workspace + compat primitives + desktop dev wheel | **G0**: 10⁴ (seed,n) shuffle reproductions incl. ≥2⁶⁴ seeds + exact deck lengths; Random(n).shuffle; fsum/npsum bit-exact fuzz; **exp/tanh fleet harness** on corpus-harvested inputs + 10⁸ fuzz (local/laptop/M5; device leg deferred to P7 — E4 ARM↔x86 losslessness is the interim evidence). G0 decides the libm strategy. |
| **P1** | engine core + action space + repr key (minimal vertical slice) | **G1**: replay golden + 449 champ games + 2 E4 archives, per-ply byte-equal repr/mask-sha/scores/terminals/base-score; 10⁴-game lockstep fuzz (Workflow; needs boxes). In-phase: count_final_scores set-order property test — order-sensitivity ⇒ ESCALATE. |
| **P2** | leaf v2.9.2 | **G2**: golden fixture leaf values bit-exact (448 frozen on disk — the "4,492" in the plan counted all fixture value types; corrected at P2 close); reconcile vs flat_leaf_cy on midgame/K3/distill corpora; `_LEAF_VALUE_PANEL`. ✅ **PASSED 2026-07-31 night, 0/3,341,772** (DECISIONS same date). |
| **P3** | single-world PUCT search + **per-sim trace harness** (bisect first divergent sim — built before k-parallel) | **G3**: action + per-action (N,W) raw-float equality at sims=1376; desktop sims/s bench. ✅ **PASSED 2026-07-31 late night, 0/9,425 searches (6.91M sims); 9.55× Python** (DECISIONS same date). |
| **P4** | fair agent: k-parallel PIMC + latch + marginalized solver (ported in v1; Python solver = oracle) | **G4**: test_kparallel template vs RustFairAgent; solver value/optimal-set equality; move-by-move identity on all corpora at k8×1376. ✅ **PASSED 2026-08-01 early, 0/305,515; every-ply-k8 full-corpus leg queued (~280 CPU-h), covered via stride-30-all-games + every-ply@k4×688** (DECISIONS same date). |
| **P5** | flags (fixed_start_tile / start_rule / centered 6→18) vs worktree diffs | **G5**: worktree tests reproduced; even-shift property; G1–G4 re-run flags-off. ✅ **PASSED 2026-08-01 pre-dawn, 0 mismatches all legs** (DECISIONS same date). |
| **P6** | desktop integration (adapter, factory selector, reconcile mode) | **G6**: deck-paired Rust-vs-Python champion **100% action agreement ≥100 games** (⇒ no elo owed); throughput ≥ Cython path. |
| **P7** | Android wheel + on-device | **G7**: on-device replay identity vs desktop; k8×1376 median ≤2 s/move (20-position battery); 50-move thermal soak; emulator smoke. ✅ **PASSED 2026-08-01 morning on the Pixel 9 Pro: 1.551 s/move median @k8×1376, thermal 1.007×, replay 0/3,165, bionic = msun/exp64_fma per-ABI via the enum — fallback NOT invoked** (DECISIONS same date; `measurement/rustport_p7/G7_REPORT.md`). ⚠️ Spec correction: `PYO3_CROSS_LIB_DIR` is UNUSABLE vs Chaquopy's target artifact (no stdlib ⇒ pyo3 hard-fails); explicit `-L/-lpython3.12` + readelf DT_NEEDED asserts carry its purpose. |

Perf expectation: Pixel does 2,752 sims/1.7 s through Python today; Rust central estimate
0.2–0.35 s/move at 11,008 (pessimistic 0.5–0.8) ⇒ 3–8× thermal headroom. Budget stays
sim/node count — no wallclock cutoff (parity).

## Acceptance (pre-registered)

Primary: full action identity + raw-float pooled-W equality on all corpora and platforms.
Fallback (ONLY if a platform's transcendental parity proves unattainable at G0/G7):
≥99.9% per-move agreement over ≥100 games, every divergence root-caused to a ≤1-ulp
transcendental tie via the trace harness, recorded in DECISIONS.md. Never silently
downgraded.

## Top risks

1. transcendental divergence (np.exp SIMD dispatch; bionic vs glibc) — G0 harness +
   site-keyed compat fns + the pre-registered fallback;
2. engine quirk semantics (farm keys, meeple list order, count_final_scores set order) —
   G1 lockstep fuzz + order-permutation test with escalation;
3. numpy pairwise reductions + f32 prior renormalization — compat::npsum + prior-vector
   bit-equality gate;
4. mirror-state drift — reconcile-mode hard error + single bridge choke point +
   from_deck resync;
5. debug long tail — the trace harness exists before it is needed.

## Out of scope (v1)

Global rules flip (flags only) · tree parallelism (unlocked, separate lever) ·
WASM/iOS builds (architecture must not preclude; core crate stays pyo3-free) ·
replacing the bridge's Python engine.
