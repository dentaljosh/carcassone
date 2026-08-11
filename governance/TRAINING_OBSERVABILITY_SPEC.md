# TRAINING OBSERVABILITY SPEC (Phase B)

Minimum persisted telemetry for future training runs. **Prioritized, not exhaustive** — the proposal's
rule applies: implement the cheap high-value metrics + the provenance stamp first; do not implement
expensive observability blindly. This spec sits in the governance INTERPRETATION layer
(`governance/README.md`) and is the precondition the `PROJECT_CHARTER.md` Track-B work gates on.

Two of the charter's load-bearing claims are currently **Provisional because they were never measured**:
CL-007 ("MSE cannot rank siblings") and CL-008 ("the value head is gradient-starved"). The telemetry
that would *test* them (sibling Kendall-τ; per-component shared-trunk gradient norms) is in the
"needs engineering" tier below — building it is how those claims get resolved instead of asserted.

---

## Tier 0 — DONE (this Phase-B commit)

**Checkpoint-provenance stamp** (`src/carcassonne_ai/train_provenance.py`, wired into
`scripts/train_iter.py` + `scripts/train_warmstart.py`). Every saved `.pt` now carries a `provenance`
block (also mirrored into `.metrics.json`), schema `carcassonne-training-provenance/v1`, with the fields
that were previously **`unknown@train` and unrecoverable** (the headline finding of
`governance/CHECKPOINT_LINEAGE.csv`):

| field | source | closes lineage gap |
|---|---|---|
| `code_commit`, `dirty` | `git_commit_and_dirty()` | ✅ (was universal gap) |
| `parent_ckpt.{path,sha256}` | `--warm-from` + `sha256_file` | ✅ |
| `train_command` | `sys.argv` | ✅ |
| `dataset.{fingerprint,n_files,total_bytes,replay_iters,files}` | `dataset_fingerprint(file_list)` | ✅ (was universal gap) |
| `arch`, `loss_weights`, `aux_heads` | trainer args | ✅ |
| `value_target`, `selfplay_leaf`, `selfplay_seed_range` | `--prov-*` pass-through (cluster loop) | ✅ if passed, else `unknown@train` |

Design: trainer-visible facts are always captured; the few self-play-only facts fall back to
`unknown@train` unless the cluster loop passes `--prov-value-target/--prov-selfplay-leaf/--prov-seed-range/
--prov-run-tag` (behavior-free flags). The block mirrors the `CHECKPOINT_LINEAGE.csv` columns, so a future
`scripts/update_lineage.py` can auto-append a row from any checkpoint. **`dataset.replay_iters` also gives
the replay-source-iteration histogram for free** (one of the cheap metrics below).

**Follow-up wiring (cheap, before the next training run):** pass the `--prov-*` flags from
`run_pathb_cluster_loop.sh` (it already knows `VALUE_TARGET`, the leaf, and the self-play seed range) so
the self-play-side fields stop being `unknown@train`. ~5 lines in the launcher; not done here (no training
this task).

---

## What's persisted TODAY (pre-existing, in `<ckpt>.metrics.json`)

Per-epoch: `train_pol_loss, train_val_loss, train_own_loss, train_rank_loss, train_center_loss,
val_pol_loss, val_val_loss, val_own_loss, val_rank_loss, n_batches, wallclock_sec, nan_skipped`.
Per-iter: `iter, warm_from, warmstart_mix_fraction, buffer_files, n_train_positions, n_val_positions,
policy_entropy, baseline_policy_entropy, value_outcome_corr` (+ now `provenance`). Gate elo/n/σ →
`experiments/results.csv`. (Source: `scripts/train_iter.py`.)

---

## Tier 1 — CHEAP adds (data already computed in the loop; persist it)

| metric | why it matters | how cheap |
|---|---|---|
| **total loss** (sum of the 5 components) | one-line trend; currently only components logged | trivial (sum existing) |
| **replay-source-iteration histogram** | detect stale/over-narrow buffers | **already captured** via `provenance.dataset.replay_iters` |
| **raw-vs-searched policy divergence** (net argmax vs MCTS-visit target, per batch) | the policy-improvement signal; flatlines when self-play stops teaching | both tensors already in the train step; add a KL/top-1-agreement accumulator |
| **game-length / score / win / seat distributions** (from the self-play `.npz`) | detect degenerate self-play, seat bias | aggregate at gen time or in a one-pass `.npz` scan |
| **value output distribution + calibration** (predicted vs realized, bucketed) | is the value head saturating/miscalibrated | reuse the held-out batch already scored for `value_outcome_corr` |

Recommendation: implement these into `metrics.json` when wiring the next training run (they touch the
loop but are read-only on existing tensors — low risk). Persist as a per-iter `telemetry` sub-dict.

---

## Tier 2 — NEEDS ENGINEERING (build deliberately; these resolve the open claims)

| metric | resolves | cost |
|---|---|---|
| **per-component shared-trunk gradient norms** (‖∇policy‖, ‖∇value‖, ‖∇aux‖ at the trunk) | **CL-008** (value gradient-starved?) — directly | moderate: separate `backward(retain_graph)` per loss term, or grad capture hooks; a few × cost on instrumented steps only (sample, don't run every step) |
| **policy/value gradient cosine (interference)** | CL-008 mechanism (do the objectives fight?) | same instrumented pass |
| **sibling Kendall-τ / sibling regret** on a held-out probe set | **CL-007** (MSE can't rank siblings?) | moderate: reuse `scripts/probe_decision_ranking.py` as a per-iter probe on a fixed held-out node set |
| **top-action agreement drift** (net argmax before/after each iter) | policy churn / instability (the iter1 −50 flywheel regression) | cheap-moderate: cache argmax on a fixed probe set |
| MCTS depth / branching / visit-distribution entropy | search-quality drift | moderate: instrument `NeuralMCTS` (per-path bookkeeping) |
| inference latency / throughput (moves/s, ms/board) | perf regressions | cheap wrapper; `CARC_BENCH_TP` already emits throughput to stdout |

**Priority for the next training cycle (Track-B is primary):** the gradient-norm/cosine probe and the
sibling-τ probe are the two highest-value Tier-2 items — they convert CL-007/CL-008 from *Provisional*
(asserted) to measured, and a gradient-starved value head is a leading candidate *mechanism* for the
CL-011 flywheel null (the primary objective's blocker). Build them sampled (e.g. every Kth step / once per
epoch on a fixed probe set), not every step.

---

## Persistence contract (proposed)

- One `<ckpt>.metrics.json` per iter (exists) extended with a `telemetry` sub-dict (Tier 1) and an optional
  `probes` sub-dict (Tier 2, when sampled). Append-only per iter; never overwrite a prior iter's metrics.
- The `provenance` block (Tier 0) lives in BOTH the `.pt` and the `.metrics.json` so lineage survives even
  if one is lost.
- Keep it lightweight (principle 10): JSON next to the checkpoint, no new service/DB. A future
  `scripts/plot_training_curves.py` can read the per-iter JSONs.

*Governance spine: [`governance/README.md`](README.md). Lineage: [`CHECKPOINT_LINEAGE.csv`](CHECKPOINT_LINEAGE.csv).
Open claims this spec would resolve: CL-007, CL-008 in [`CLAIM_REGISTRY.csv`](CLAIM_REGISTRY.csv).*
