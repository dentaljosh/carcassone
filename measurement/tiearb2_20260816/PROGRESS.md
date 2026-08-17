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
- **[t8] 20:10 EDT — CORPUS BUILT, and `G-DISJOINT` FIRED. The gate did its job.**
  Phases 1–5 clean in **2m34s** (census 3,400 rows → 1,809 champ-pick candidates →
  `afterstate_dedupe.applied true`, 454 dropped as whole-set transpositions →
  **supply 1,355** over **725 roots**). `exclude_rids.n_removed_from_supply = 0`,
  which is itself the witness that the 733 spent rids could not have collided.
  Gate result:

  | layer | identity | spent | new | ∩ |
  |---|---|---|---|---|
  | a | `root_id` (the GAME) | 399 | 725 | **0** ✅ |
  | b | `rid` (the (game,ply) POSITION) | 733 | 1,355 | **0** ✅ |
  | c | `sha256(checksum)` (the BOARD) | 733 | 1,353 | **3** ⛔ |

  ⭐ **This is board TRANSPOSITION, not a band collision** — layers a and b at 0
  prove the games and positions are disjoint; 3 of 1,353 boards are reachable from
  a different game *and* a different ply, which is intrinsic to Carcassonne (the
  spent corpus measured **26.2%** whole-set transpositions *internally*, and this
  build dropped 454 of its own on the same principle). **Layer c is exactly the
  layer that exists to catch what a and b cannot**, and it earned its place on its
  first real use.
  ⚠️ **The gate's printed remedy — *"rebuild the corpus from a clean deck-seed
  band"* — is WRONG for a layer-c-only failure** and is not being followed: no band
  is clean of transposition, so regenerating would cost another 4.4 h and reproduce
  the same class of overlap. **The correct response is exclusion.**
  Also surfaced by the same report: `n_new` 1,353 distinct digests from 1,355 leg
  lines ⇒ **2 within-corpus duplicate boards**. The spent corpus has 733 rids and
  733 distinct checksums (no internal duplicates), so these are dropped too, to
  match its construction.
  ⇒ **Fix: exclude the 3 + 2 = 5 offending rids and re-run phases 5–6 through the
  same tested builder** (`build_positions.py --exclude-rids`), never by hand-editing
  a plan. Supply 1,355 < `--n` 1400 means `stratified_sample` takes ALL supply, so
  the drop is unambiguous: **expected realized n = 1,350**, still **30% above the
  1,040 floor**. Phases 1–4 are untouched.
  ⚠️ Recorded as a **corpus-assembly decision taken before any statistic exists**;
  it reads board IDENTITY only, never a value.
- **[t9] 20:16 EDT — CORPUS FINAL. `G-DISJOINT` PASSES 0/0/0.** The §0.A.2
  exclusions were applied through the same tested builder (`build_positions.py
  --exclude-rids`, 733 + 5 = 738 distinct): `n_removed_from_supply 5`,
  **n = 1,350 / 724 roots**, `mean_arms 3.0022`, `total_arm_playouts 172,992`,
  `afterstate_dedupe.applied true`. Gate re-run: `a_root_id` 0 · `b_rid` 0 ·
  `c_position_digest` 0, `n_layers_violated 0`. ⭐ Diagnostic that settles the
  cause: **all 5 offending positions are at ply 2** — textbook opening
  transposition, so no fresh deck-seed band could have avoided them and
  regeneration would have been pure waste. n=1,350 is **30% above the 1,040 floor**
  (2σ on `F_fixed` = 0.307 vs the 0.35 bar).
- **[t9] SPLIT carved:** 18 cells, `balance_ok true`, every cell ±1 root,
  **S1 690 / S2 660 positions**; `--verify` re-derives byte-identically (the
  `G-SPLIT` witness). **CHUNKS:** one committed seeded permutation (20260816) cut
  into **[337, 338, 337, 338]** = 2,703 legs / 172,992 playouts, identical rid sets
  for both judges.
- **[t10] 20:24 EDT — COST PILOT PASSED, `B* = 2` FROZEN FROM COST ALONE.**
  43/43 on every witness, abort **not** triggered: `n_failed 0`, `crn_verified 43`,
  `checksum_ok 43`, seed/arm identity 43/43/43, **`G-REPRO` 43/43 bit-identical** to
  the adjudicated 2026-08-14 OOF records. ⭐ **Cross-judge witness: 43/43 world AND
  playout seeds bit-identical to the `clair-puct` pricing records** — `world_seed`
  is keyed on rid+salt and never on the judge, so this is the check the `G-CRN`
  cross-judge join actually rests on, and a same-judge reproduction cannot show it.
  Cost: `A_bar 3.0022`, **`c_tier1 = 2.7274`** worker-s/playout ⇒
  `rho_wall`: B=1 **0.5953** ✅ · B=2 **1.1906** ✅ · B=4 2.3811 ❌ · B=8 4.7623 ❌ ·
  B=16 9.5246 ❌ ⇒ **`B* = 2`, `DEPLOY` true** — **exactly what DESIGN §7.2 predicted
  in advance**, so the cheap arm was not fitted to anything.
  ⚠️ **TWO CAVEATS THE READ-OUT MUST CARRY.** (i) **B\*=2 clears the bar by 0.8%**:
  `rho_wall(2) ≤ 1.20` needs `c_tier1 ≤ 2.7489` and we measured 2.7274 — a slightly
  slower pilot would have forced `B*=1`. The `DEPLOY` conjunct is on a knife edge and
  must never be quoted as comfortable. (ii) `c_tier1` is **28% above Stage 1's
  2.1236**, measured under **W30** contention vs Stage 1's W20; a *deployed* arbiter
  fires on one move with the box to itself, so this **overstates** deployable cost —
  the conservative direction, consistent with §7.1's declared python-vs-cython bias.
  At Stage 1's `c` the same B=2 reads `rho_wall 0.927`. It is +9.1% vs
  `ALLOCATION.conf`'s 2.5 assumption, **inside** the ±25% revisit band ⇒ the static
  chunk allocation stands.
- **[t11] ⚠️ BOTH BOXES ABORTED AT FIRST LAUNCH — and the abort was CORRECT.**
  `run_main.sh`'s pre-launch check called `stage_plans.py main --verify`, which
  re-derives the permutation from the **source corpus**. It failed on both boxes for
  two different reasons: the **laptop** has no `corpus/positions` (65 MB,
  deliberately not synced — only the chunk plans are), and **locally** the call used
  stage_plans' *relative* default paths and resolved them against the wrong cwd.
  **Nothing was scored on a bad plan**; the gate did its job.
  **Fix:** a self-contained check over synced artefacts only — each chunk dir's
  `ARMS.json` key set must equal `POSITION_ORDER`'s slice for that chunk, leg files
  must exist, and the recorded `sha256_order` must reproduce. That is precisely the
  property the cross-judge CRN join depends on, and it needs no source corpus. The
  full byte-identity re-derivation still runs locally in `run_analysis.sh`.
  (The digest formula was **verified against the recorded value, not assumed** —
  `stage_plans.py` hashes one rid per line *with* a trailing newline.)
  Verified before relaunch: **all four chunks match exactly, 0 missing / 0 extra.**
- **[t12] 20:29 EDT — MAIN SCORING LAUNCHED, both boxes, detached (`setsid nohup`).**
  Per `ALLOCATION.conf`, with the ETA recomputed at the pilot's realized
  `c_tier1 = 2.7274` (clair-puct at the assumed 1.60, unmeasured this run):

  | box | W | legs | worker-h | ETA |
  |---|---|---|---|---|
  | **local** | 30 | `clair-puct` chunks 1–4 | 76.9 | ≈2.6 h |
  | **local** (chained) | 30 | `tier1-greedy` chunk 4 | 32.8 | ≈1.1 h |
  | **laptop** | 22 | `tier1-greedy` chunks 1–3 | 98.3 | ≈4.5 h |
  | | | **total 208 worker-h** | | **makespan ≈ 4.5 h** |

  Local runs as ONE detached process (`run_local_chain.sh`), chained with `;` not
  `&&` so a partial clair-puct failure cannot silently cancel the tier1 leg.
  **DONE-MARKER CONVENTION** (all in this run dir, detectable from the share-adjacent
  repo): `DONE_<judge>_CHUNK<k>` per completed chunk · `DONE_<judge>_<box>` per
  completed box-leg · `DONE_LOCAL_SHIFT` when the local chain finishes ·
  `DONE_ANALYSIS` at the end. Records accumulate under
  `<share>/tiearb2_20260816/main/chunk<k>/<judge>/…/records/` and are merged by file
  copy into `main/merged/<judge>/` with a duplicate guard.
  ⚠️ **Every completed-chunk prefix is a uniform random subsample** of the committed
  permutation, so a partial run is still an unbiased read at its realized `n` —
  subject to `G-N` (≥1,040 pooled, ≥400 per slice).
- **[t13] ⚠️ SECOND LAUNCH ABORT — `run_main.sh` never `cd`'d to the repo root.**
  The 20:29 launch died on BOTH boxes at run_tiletie's own preflight
  (`[preflight] positions: FAIL — missing positions file for leg walled/leg1`)
  even though every leg file is present. Cause: `POSITIONS_PLAN.json` stores leg
  paths **repo-relative**, and the preflight resolves them against the **current
  working directory**. `run_pilot.sh` has always carried `cd "$REPO"` — which is
  precisely why the pilot ran clean and the main run did not.
  **Fixed** by `cd "$REPO"` before any leg launches; verified `positions: PASS`.
  ✅ **NOTHING WAS CONTAMINATED:** the preflight is a hard abort, so **0 records**
  were written on either box (verified on the share) and **0 DONE stamps** laid
  down. Cost was wall-clock only (~8 min).
  ⚠️ **Two standing traps both fired during the stop, and both are worth re-reading:**
  (i) `pkill -f <pattern>` **self-killed**, because the invoking command contained
  the literal pattern — every subsequent kill was done by **exact pid**;
  (ii) killing the launcher shells did **NOT** reap the mp spawn workers (9 orphans
  survived on local), so they were TERM'd then KILL'd by exact pid. **Both boxes
  were verified at 0 python processes before relaunch.**
- **[t14] 20:37 EDT — MAIN SCORING RUNNING, BOTH BOXES, PARALLELISM VERIFIED.**

  | box | W | leg | `positions:` | scorers seen | loadavg |
  |---|---|---|---|---|---|
  | local | 30 | `clair-puct` chunk 1 → 4, then `tier1-greedy` chunk 4 | **PASS** | **36** | 7.86 |
  | laptop | 22 | `tier1-greedy` chunks 1 → 3 | **PASS** | **26** | 8.56 |

  Both detached with `setsid nohup … & disown`. ETA (at the pilot's realized
  `c_tier1 = 2.7274`; clair-puct at the assumed 1.60, unmeasured this run):
  **local ≈ 3.6 h · laptop ≈ 4.5 h ⇒ makespan ≈ 4.5 h**, i.e. finishing ≈ 01:05 EDT.
  **DONE-MARKER CONVENTION** (all in this run dir): `DONE_<judge>_CHUNK<k>` per
  chunk · `DONE_<judge>_<box>` per box-leg · `DONE_LOCAL_SHIFT` when the local
  chain ends · `DONE_ANALYSIS` last. Records land under
  `<share>/tiearb2_20260816/main/chunk<k>/<judge>/…/records/` and merge by file copy
  into `main/merged/<judge>/` with a duplicate guard.
- **[t3] Six-touch, in-progress leg:** `docs/LEVER_INDEX.md` row 217 amended with the
  successor (in flight), `STATUS.md` top block replaced (the `P-PARTIAL` block moved
  to frozen history), `docs/PROGRAM_ROADMAP_2026-07-07.md` NOW block replaced.
