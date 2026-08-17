# PROGRESS LOG — tiearb2_20260816 (terminal-grounded tie arbitration, Stage 1b / successor)

Append-only. Timestamps are local (WSL2, box = 5900XT local unless stated).

## Owner authorization

2026-08-16, verbatim:

> "fund. both boxes. laptop w22, local w14 for now, but make it easy to bump to
> w30 later. get an agent on it"

⇒ Both boxes funded. Worker counts live in [WORKERS.conf](WORKERS.conf) — a
one-line edit bumps `W_LOCAL` 14 → 30. **The owner named W_LOCAL=30 as the value
he may bump to.**

---

## Log

- **[t0] Orientation.** Read the spent Stage-1 artifacts
  (`../tiearb_20260816/{READOUT,DESIGN,READ_RULE}.md`) and `docs/LEVER_INDEX.md`
  rows 212–217. Recorded re-open bar: successor needs (a) a NEW corpus at
  n ≈ 924+, (b) a fresh read-rule, (c) an argument handling the dev/holdout
  discrepancy, (d) an answer to the cost question.
- **[t0] Census.** Local: 0 python processes, loadavg 0.10, 32T, 41 GB.
  Laptop (`ssh laptop`): 0 python processes, loadavg 0.01, 24T, 11 GB.
  **Both boxes idle.** No co-tenant.
- **[t0] Run dir created**, `WORKERS.conf` written (the one-line worker bump).
- **[t1] Supply verdict.** The spent corpus is **root-exhausted**, not merely spent:
  its self-play stratum consumed the whole CL-070 bank (495 `TILES` roots) and
  sampled 432 of the 449 games in `champ_action_logs/champ_games.jsonl`. ~30,132
  eligible plies remain in those games but **every one belongs to a game that is
  already a `root_id`** (`root_id = sp_<deck_seed>`), so topping up buys positions
  and no roots — exactly what the re-open bar forbids. The only other un-mined
  supply is 320 E4 positions over 26 root clusters, 24 of which already
  contributed. ⇒ **fresh self-play games are required**, as the funding brief
  anticipated.
- **[t1] Stage-1 slice decomposition** → [STAGE1_SLICE_DECOMP.json](STAGE1_SLICE_DECOMP.json).
  The dev/holdout failure is a **baseline level shift, not a mechanism failure**:
  `rnd` moved +0.3978 (z 2.97) across the slices vs `arb`'s +0.2971 (z 2.53), and
  `arb − rnd` is flat (z −0.71, root-permutation abs-percentile 0.561). Composition
  drift (arm-count 24.1 pp, phase 16.8 pp) explains 11–29% of the `arb` gap and
  25–52% of the `ora` gap. Realized sd(`arb`) 1.5819, cluster design effect **0.943**
  (range 0.932–1.034 over 24 cells) at 1.837 positions/root ⇒ **size on the naive
  sd/√n**. This is a post-hoc read of *published* Stage-1 numbers; it re-labels
  nothing and `measurement/tiearb_20260816/` is untouched.
- **[t2] 15:45 EDT — PHASE 1 LAUNCHED, both boxes.** 850 games, k4×688, `walled`,
  deck-seed band 28100000000..28100000849, `--shared-claim`. Local W14 launched at
  commit `fccd8cb5`; laptop bundle-synced `e86da34b → fccd8cb5` then launched W22.
  **Parallelism verified by `ps`: 14 local workers at 99.8% CPU, 22 on the laptop.**
  Both logs report `leaf_hash=6dfffd57051690f2`, matching
  `champ_action_logs/CORPUS_MANIFEST.json` exactly. ETA ≈3.8 h at 36 workers.
  A completion/death Monitor is armed on the share shard count (`watch_gen.sh` —
  it fires on **both** completion and both-box death, so silence is not success).
- **[t3] BLIND-ORDERING COMMIT `b46e7199`** — [DESIGN.md](DESIGN.md) +
  [READ_RULE.md](READ_RULE.md), committed **before** the instrument, **before** the
  pilot, and **before one fresh position was scored by either judge**. Only corpus
  substrate precedes it.
- **[t4] ⚠️ ETA CORRECTION, surfaced not smoothed.** The pre-launch ETA of **3.8 h**
  for phase 1 was derived from the 2026-07-21 corpus log (73.2 s/game at **W8** =
  586 worker-s/game) and is **WRONG**. Realized: local W14 reports **61.7 s/game**
  = **864 worker-s/game**, i.e. **1.47× more worker-seconds per game**, and the
  combined two-box rate over the first 14 min is **≈98.6 games/h** ⇒ phase 1 is
  **≈8.6 h**, not 3.8 h. **Cause: the DRAM wall, not a bug** — W14 delivers only
  **1.18×** W8's throughput on this memory-bound workload, which is exactly the
  standing `feedback_worker_count_by_bottleneck` finding (self-play is
  DRAM-latency-bound; the W optimum is ≈14–16 *regardless of core count*, and
  per-worker throughput falls steeply past ~8). Two candidate causes were checked
  and **excluded**: the F9 W4 wall sentinel is a **pure observer** with no search
  of its own (it reads `board.state` after a ply; `src/carcassonne_ai/wall_sentinel.py`
  has no search entry point), and the budget/leaf/profile all match the reference
  corpus exactly. ⇒ **No config change is warranted and none was made.**
  Revised total wall ≈ **8.6 h gen + ~1 h mining + ~6 h scoring ≈ 16 h** — long, but
  within the funding brief's explicit "mining + scoring may run overnight".
  ⚠️ `W_LOCAL` was **NOT** bumped: the owner authorized *making the bump easy*
  ("w14 **for now**, but make it easy to bump to w30 later"), not taking it. It
  remains a one-line edit in [WORKERS.conf](WORKERS.conf). (It would buy little in
  any case — the same DRAM wall caps W30 near W14.)
- **[t4] Pre-committed contingency if supply undershoots** (recorded now, before any
  statistic exists): prefer raising `--max-per-game` on the **same** 850 games
  (census costs 0.0192 s/ply — effectively free) over generating more games. This
  trades positions-per-root upward, so the realized **cluster design effect must be
  re-measured and reported**; the cluster-robust se is the reported se on every
  branch regardless. `G-N = 1,040` is **not** renegotiable under any contingency.
- **[t5] Guard calibration — pre-registered, computed before any fresh number.**
  Using Stage 1's realized sds and its `walled` cut (the population this corpus is
  100% of: `ora +0.2450`, `arb +0.2043`, sd 1.6526 / 1.5819):

  | n | z(ora) | z(arb) | 2σ on `F_fixed` |
  |---|---|---|---|
  | 1,400 (pooled target) | 5.55 | 4.83 | **0.302** |
  | 1,040 (pooled floor `G-N`) | 4.78 | 4.16 | **0.350** |
  | 700 (one slice at target) | 3.92 | 3.42 | 0.427 |
  | 400 (slice floor) | **2.97** | 2.58 | 0.564 |

  ⇒ **the informativeness guard cannot trivially fire**: even at the *slice floor*
  `z(ora_s) = 2.97 > 2.0`, so a slice reads UNINFORMATIVE only when it is genuinely
  low-signal — as Stage 1's holdout was, at `z(ora) = 1.19`. And `C_split` is a real
  check, not a formality: `P(arb_s < 0)` by chance at n=700 is **0.00032**.
  `G-DENOM` (pooled `z(ora) ≥ +2`) is met with a factor of ~2.8 in hand.
- **[t5] §0.A.1 PRE-RUN AMENDMENT** (recorded before the pilot, before any scoring):
  the CRN salt stays **`tiletie-v1`**. `WORLD_SEED_SALT` is a hardcoded constant in
  `run_tiletie.py`, not a flag, and exposing it would mean editing a shared script
  while runs are live. **This costs nothing** — `world_seed` is keyed on the `rid`,
  and the fresh rids (`tt_sp_281000000xx_*`) cannot collide with the spent ones, so
  every world is an independent draw regardless of salt. `READ_RULE.md` untouched
  (verified by grep: it contains no salt reference).
- **[t6] 20:07 EDT — PHASE 1 COMPLETE. 850/850 games.** Realized wall **≈4.4 h**
  (15:45 → 20:07), against the corrected estimate of ≈7.8 h — **faster than
  forecast**, because the owner bumped `W_LOCAL` 14 → **30** mid-run
  (*"didnt we bench that its optimal w is above 30?"*) and a W16 joiner pool on the
  shared claim lifted combined throughput **185 → 228 games/h**. ⇒ **the old
  W≈14–16 DRAM-wall figure is PYTHON-era and does NOT bind the rust-era gen path**
  — my [t4] diagnosis was right about the mechanism but wrong to treat W14 as the
  knee. Split: laptop 454 games, local 396. Both boxes censused **idle** afterwards
  (0 python procs, loadavg 0.71 / 0.22); sentinel reports **0 aborted, 0 overflow**
  over 846 games.
- **[t6] Builders landed while phase 1 ran** — corpus pipeline `3dbaa8bf`
  ([CORPUS_PIPELINE.md](CORPUS_PIPELINE.md)) and the instrument `504ddad1`
  (`split_tiearb2.py`, `analyze_tiearb2.py`, 53 tests; 105 green with Stage 1's 52).
  ⭐ Two verifications worth recording: the honest arm at **B=16 is BIT-IDENTICAL**
  to Stage 1's estimator (checked against `crossfit_regret` over 200 random
  matrices × 2 folds **and** end-to-end against `analyze_tiearb`'s own
  `per_position.jsonl`), and the branch table is machine-swept over **54,000 cells**
  by a `_reference_branch` that re-transcribes READ_RULE §4 *independently of the
  implementation*. A real Stage-1 bug was found in passing: `analyze_tiearb.cost_block`
  reads `elapsed_secs`/`playouts` but `run_tiletie` writes `wall_secs`/`n`, so the
  committed Stage-1 READOUT carries `c_tier1 = null` from that path; the new
  `manifest_cost()` reads both spellings. **Stage 1's file is untouched.**
- **[t7] 20:08 EDT — CORPUS PIPELINE LAUNCHED** (detached, W30, `nice -n 19`).
  ETA ≈35–45 min. **Phase 1 COLLECT + VERIFY PASSED:** 850 games, plies
  min/med/max 141/144/144, round-trip **10 ok / 0 bad**, `band_ok true`,
  `n_out_of_band 0`, `n_duplicate_seeds 0`, seed span exactly
  28100000000..28100000849, `sha256_of_sorted_seeds
  c484dc259f69439a8b40b5f28485fd75c956eebcfba8cef6693ad1b50e97553a`.
  Phase 2 CENSUS running: `E4 archives by profile: {}`, one `walled` leg, all 30
  workers, task estimate 3,400 — parallelism verified by `ps` (34 procs, 96.6% CPU).
- **[t3] Six-touch, in-progress leg:** `docs/LEVER_INDEX.md` row 217 amended with the
  successor (in flight), `STATUS.md` top block replaced (the `P-PARTIAL` block moved
  to frozen history), `docs/PROGRAM_ROADMAP_2026-07-07.md` NOW block replaced.
