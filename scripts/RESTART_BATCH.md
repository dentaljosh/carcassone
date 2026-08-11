# Flywheel RESTART BATCH — ✅ APPLIED 2026-06-08 (live in `run_residual_flywheel.sh`)

> **STATUS: APPLIED.** The flywheel ended (plateau), so the whole batch was swapped into the
> live `run_residual_flywheel.sh` and committed (`next.sh` removed). All seven D-S items below
> are now live (`bash -n` clean). Kept as the record of what changed + why. Earlier these could
> NOT be hot-applied (editing a running bash script corrupts its byte-offset execution).

| id | fix | where | status |
|---|---|---|---|
| **D-S1** | per-loop **heal cap** (`HEAL_CAP=8`, env-overridable) → a no-progress loop exits **1 loud** instead of hanging forever; + a `_share_writable` probe so a heal backs off when the share is gone instead of relaunch-storming | all 3 wait loops (gate/odo/gen) | ✅ live |
| **D-S2** | `_kill_pool` reaps the prior pool on all 3 boxes (`pkill -f eval_net_vs_heuristic` / `run_selfplay_iter`) **before** each heal relaunch → no orphan-worker accumulation (the ~56-proc pileup) | all 3 heals | ✅ live |
| **D-S3** | `_clean_stranded` in-loop age **4min → 30min** → the heal can't delete a slow-but-alive worker's claim → no duplicate-played seeds | all 3 heals | ✅ live |
| **D-S6** | `cp best.pt warm.pt` now **fails loudly** (`[ -s best.pt ]` guard + `|| exit 1`) instead of silently warming from nothing (`set -e` is off) | per-iter warm staging | ✅ live |
| **D-S7** | **plateau `break` ran BEFORE the odometer block** → the terminal iter's out-of-lineage odometer was **SKIPPED** (the 2026-06-08 iter3 miss; recovered manually via `scripts/odo_oneshot.sh`). Fixed: the `break` now happens **after** the odometer, and the odometer fires on **any terminal iter** (plateau OR last), not just the `ODO_EVERY` cadence — so the final out-of-lineage signal is never lost. | iter-loop tail | ✅ live |
| **D-S4** | ssh rc=255 box-drop now **retries** via the `_ssh_bg` wrapper (3 tries on a 255, then yields the box for that iter; the heal still re-adds it on the next stall). All 6 remote launches (gate/odo/gen × laptop/xeon) route through it. | remote launches | ✅ live |

## ✅ FIXED 2026-06-08 (the "fix all outstanding bugs" pass)
- **D-R4-1 — train/val LEAK (`warmstart.py` `split_files_train_val`)** ✅ — split now by **unique**
  path: val gets one occurrence of each held-out game, ALL occurrences (incl. oversampled dupes) of
  train-side games go to train, val-side games are fully excluded from train. **Byte-identical for
  duplicate-free input** (mix=0.0, all current training), so result-neutral; only the mix>0 leak path
  changes. Unit-verified (no leak, val de-duped).
- **D-R4-2 — `auto_chain_h2h_flywheel.sh` count()/tally()** ✅ — both now scope to the clean
  namespace (seed ≥1e9, 10+-digit) so a stray pre-1e9 / different-run file can't end `wait_h2h` early.
- **D-S5 — `eval_iter_head_to_head.py` leaf-config cache collision** ✅ — a `.leafconfig.json` stamp in
  `eval_dir` + a startup HARD-FAIL on mismatch (reusing a dir with a changed leaf now errors instead of
  silently loading the prior config's cached games). No filename/path change → all caches & the
  hardcoded `H2H_DIR` preserved.
- **D-R3-2 — `train_iter.py` corr printout** ✅ — relabelled in residual mode (value↔target, NOT the
  0.61 value-vs-outcome ruler).
- **Launcher pre-1e9 seeds** ✅ — `run_pathb_cluster_loop` (GATE_SEED), `scaling_curve`, `ladder_highsim`
  (SB), `rank_sweep`, `lever_sequencer` bumped to the 1e9 floor so a reuse no longer hangs the guard.

## ✅ FIXED 2026-06-08 (pm-3) — the v2.7 leaf is SOUND; the two real items fixed
- **D16 — `virtual_score_v2.py` `_close_prob(0)`** ✅ — a board-edge unfinished city with 0 in-bounds open
  positions now `continue`s (no bonus) instead of getting a 100% closure-anticipation bonus, at BOTH the
  city-closure and farm-growth loops. The trigger (a city chain reaching the edge of a 35×35 board in a
  ~72-tile game) is **practically unreachable**, so the leaf/ruler change is negligible — **no cap
  re-sweep needed in practice.** (My earlier "needs a re-sweep, hold for attempt #2" overstated it.)
- **D2 — phase compared by string not enum** ✅ — `state.phase == GamePhase.{TILES,MEEPLES}` in
  board_repr / features / warmstart instead of the hardcoded `"tiles"`/`"meeples"` literal. Provably
  identical today (`GamePhase.TILES.value == "tiles"`); kills the fragility vs a (frozen) engine
  enum-string change. `action_space.encode(phase: str)` left as-is — a deliberate string-param interface.
- **D3 — `bonus_cap`/`opp_bonus_cap`** — NOT a bug: `opp_bonus_cap` defaults to `bonus_cap` (equal in
  production → antisymmetry holds); the asymmetric-cap path is the intentional denial-strengthening feature.
- **D1 — TILES/MEEPLES ref-tile encoding** — NOT outstanding: already adjudicated **intentional** on
  2026-05-29 (documented in `board_repr.py:321-329`; the "always encode the placed tile" alternative was
  weighed and rejected). The stale "Deferred D1" REVIEW_LOG line predates that resolution; nothing to do.
  *(Earlier in this session I wrongly conflated this with "D2" and called it a retrain-gated bug — it isn't.)*

## Research decisions for attempt #2 (your call, not mechanical fixes)
- **S-R3-1** (the big one): residual target Δ∈[−2,2] vs tanh value head [−1,1] → high-|Δ| positions
  under-learned. Lever: clip the target to [−1,1], or a linear residual head.
- **Deck diversity:** every flywheel iter reuses seeds 0–399 → vary per iter (`--seed-start $((it*GAMES))`).
- **Leaf choice (CL-010):** the net beats heur@800-v2.7 but loses heur@800-v1, and v1 is the stronger
  standalone leaf — decide whether v2.7 should remain the production leaf.
