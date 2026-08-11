# In-loop search-value retrain — build spec (2026-06-04)

> **Status: EXECUTED (historical)** — built + validated; the lever's outcome (interior targets
> did NOT escape the value-as-leaf cliff) is recorded in [INLOOP_VALUE_FLYWHEEL_BUILD_2026-06-04.md](INLOOP_VALUE_FLYWHEEL_BUILD_2026-06-04.md)
> → succeeded by [VALUE_LOSS_ATTACK_2026-06-05.md](VALUE_LOSS_ATTACK_2026-06-05.md).

**Decision (Joshua, 2026-06-04):** build this. It's the real, properly-powered test of the
value-target-source lever, after gate-2 confirmed the mechanism (per-position targets fix the
overfitting direction) but was too underpowered to show a head beating v2.7. See
[CEILING_AND_C4C6_2026-06-04.md](CEILING_AND_C4C6_2026-06-04.md) for the full diagnosis.

## The one-line thesis

The value head fails because it **overfits**: trained on the game OUTCOME (one label per game,
shared across ~144 positions → only ~600–1200 independent labels vs a 7M net) it goes **0.79 train →
0.32 held-out**, *below* v2.7's ~0.4–0.65 → it's worse than the heuristic on the off-distribution
positions MCTS explores → blending it in HURTS. **Fix:** train the value head on the **per-position
MCTS search value (root.Q)** instead of the game outcome → ~100× more independent labels → should
generalize far better, and (at high enough sims) the target itself exceeds v2.7 → a learned leaf that
can finally beat the heuristic.

## What gate-2 showed (why this is worth building, and its caveats)

`scripts/gate2_value_head_searchvalue.py`, 24 games sims=50, held-out by game:
- search-value head **+0.166** vs outcome head **−0.04** → per-position targets generalize better ✓
- but search-value head still < **v2.7 0.401**, because: (1) **sims=50 search-value ≈ v2.7** (0.423) — a
  head can't beat its target → need **higher sims** so root.Q > v2.7; (2) **24 games underfits** → need
  production data scale. Both fixed by doing this in the production loop at sims≥200.

## AS-BUILT (2026-06-04, commits ffe823e + 5b21023 + 6f18ade) — cleaner than the plan below

The plan assumed the value target was re-derived in `train_iter.py`. It is NOT — the value target
is **baked into `ds.values` at GENERATION time** (selfplay.py), and the trainer just runs MSE on
`values`. So `search_value` shipped as a **generation-side `--value-target` mode** that writes
`root.Q` straight into `values_arr`. Nothing downstream changes — GameDataset stays a 6-array
schema, the streaming dataset / trainer / loss are untouched, and there is **no `CARC_RECORD_SEARCHVALUE`
env flag** (the `--value-target search_value` choice IS the trigger).

1. **`src/carcassonne_ai/mcts.py`** — added `NeuralMCTS.root_value(board)`: returns `root.Q` (W/N from the
   root's current-player POV) from the most recent search; re-searches if root absent. Mirrors
   `root_visit_distribution`. `select_for_training` reads but never clears `_nodes`, so the root persists.
2. **`src/carcassonne_ai/selfplay.py`** — `value_target="search_value"` records `float(mcts.root_value(board))`
   per learner ply (in the same `is_learner_move` guard → index-aligned with `players_arr`), then sets
   `values_arr = np.array(search_values_arr)`. **No per-ply z-flip** (root.Q is already POV-signed, unlike the
   outcome targets). Length-mismatch guard raises loudly.
3. **`scripts/run_selfplay_iter.py`** — added `search_value` to `--value-target` choices; `cfg["value_target"]`
   already threads through to selfplay (no other change).
4. **Cluster loop** — already passes `--value-target ${VALUE_TARGET:-score_diff}` into the per-host self-play
   command (expanded locally, shipped to each box). **No loop edit.** Run it with `VALUE_TARGET=search_value`.
5. **Tests** — `tests/test_selfplay.py` (search_value mode: matches root.Q, varies per position, deterministic,
   differs from outcome) + `tests/test_neural_mcts_selfplay_extensions.py` (root_value accessor). 23 pass.

### Gate harness (as-built)
- **Gate A** = `scripts/probe_heldout_value_corr.py` — STREAMS held-out OUTCOME-target data (one .npz at a time
  via `make_streaming_dataset` + DataLoader) and accumulates Pearson sufficient stats. ⚠️ The first cut
  load-all-into-RAM **OOM'd the 31 GB 5800x at ~1200 games** — never load all; `--max-games` bounds it.
  `--checkpoint A B …` evaluates multiple ckpts on the SAME batches → side-by-side table. **iter_01 baseline
  measured first-hand: +0.289** on `stage_b/iter_05` (600 games), vs v2.7 ~0.4–0.65 → the overfitting signature.
- **Gate B** = `scripts/eval_net_vs_heuristic.py` with `CARCASSONNE_V25_VALUE_BLEND=0.5` (+ `..._DROP_THREE_OPEN=1
  ..._CAP=12`), `--sims 200 --heur-sims 200 --c-puct 3.0 --paired` (mirror the scaling-curve cell). iter_01
  craters to **−123** at λ0.5; a head that stops cratering means the learned leaf is usable in search.

### Run config used (the actual launch)
`RUN=searchval_s200 WARM_SRC=stage_b/ckpt/iter_01.pt START=0 ITERS=1 GAMES=400 SIMS=200 VALUE_TARGET=search_value
ANCHOR_FRACTION=0 STAGE_B_BLEND=0 HOSTS="5800x xeon laptop"` (value-loss-weight left at 1.0 to keep the A/B vs
iter_01 clean — only the target source changes). Output ckpt → `searchval_s200/ckpt/iter_00.pt`.

**Decide (step 7):** new head held-out corr ≥ ~0.40 (beats +0.289, reaches v2.7's floor) AND value-blend stops
hurting → iterate/scale (more games, higher-sims root.Q). Flat/worse → lever bounded → measurement / Phase 5.

---

## Original plan (superseded by AS-BUILT above; kept for rationale)

1. **Record root.Q in self-play.** In `src/carcassonne_ai/selfplay.py` (the per-ply record block ~L186–272,
   after `mcts.search(board)` ~L222): get the root node and append its Q (search value, current-player POV)
   to a new `search_values_arr`, gated on `is_learner_move` like the other arrays. Access pattern (verified):
   ```python
   root = mcts._nodes[game.string_representation(board)]   # after search
   sv = float(root.Q)                                       # Node.Q property, mcts.py:60, POV current player
   ```
   Save `search_values=np.array(...)` in the npz (`run_selfplay_iter.py` `np.savez`, ~L196 path / save site).
   Gate it behind a flag (e.g. `CARC_RECORD_SEARCHVALUE=1`) so default behavior is unchanged.
   ⚠️ Confirm `select_for_training` (what the loop actually calls) leaves the root in `mcts._nodes` after its
   search; if it clears, capture root.Q right after the search call inside the same ply.
2. **Add the value target to `train_iter.py`.** New `--value-target search_value`: value label = the recorded
   per-position `search_values` array (POV-signed, already tanh-ranged since root.Q∈[-1,1]) instead of the
   outcome z. Optionally `search_value_blend` = α·outcome + (1−α)·search_value (start α=0 = pure search-value).
   (train_iter already has --value-target score_diff|score_diff_wide|wl; mirror that.)
3. **Wire the loop.** `run_pathb_cluster_loop.sh`: pass `CARC_RECORD_SEARCHVALUE=1` to self-play and
   `VALUE_TARGET=search_value` to train_iter (the loop already has a `VALUE_TARGET` knob, commit ea36499).
4. **Smoke** (1 iter, ~6 games, sims=50): confirm `search_values` is in the npz and train consumes it.
   ⚠️ **Verify production self-play is FAST** here — the ad-hoc gate-2 generator was stuck single-process
   (multi-worker single-board GPU eval thrashes the CUDA context, ~37s/game W=1). The production loop
   historically runs W=14–20 at 12–20 pos/s; if it ALSO thrashes, the orchestrator (batched GPU eval) or a
   different eval path is needed before scaling. Check throughput in the smoke.
5. **Run ONE iteration** at production knobs: warm from **iter_01** (`stage_b/ckpt/iter_01.pt`, the +87 net),
   `STAGE_B_BLEND=0` (λ=0, policy clean), `VALUE_TARGET=search_value`, sims=200, ~300–600 games, on the cluster.
6. **Evaluate the new value head (two gates):**
   - (a) **Held-out value-head corr** (cheap, reuse today's measurement): run the new head's value on
     held-out self-play (a later iter's games) and corr with the true margin. iter_01 was **0.32**; if the
     new head jumps toward v2.7's level (~0.4–0.65), overfitting is fixed.
   - (b) **Value-blend-at-play vs HeuristicMCTS** (`eval_net_vs_heuristic.py` + `CARCASSONNE_V25_VALUE_BLEND`):
     iter_01's head craters at λ=0.5 (−123). If the new head's blend stops hurting / helps, the leaf beats v2.7.
7. **Decide:** new head beats v2.7 (held-out corr up AND value-blend helps) → iterate/scale (this is the
   strength push). Flat/worse → the lever is bounded → measurement / Phase 5.

## Caveats / risks
- **The payoff is capped by root.Q's quality.** At sims=200 root.Q should exceed v2.7 (deeper than the
  sims=50 gate where it was ≈v2.7); confirm the target itself beats v2.7 before expecting the head to.
- Even a value head that beats v2.7 yields uncertain *elo* gain (v2.7 is already good), and **superhuman
  remains unprovable without an above-amateur reference** (measurement wall, deferred).
- POV/sign: root.Q is current-player POV; the existing value pipeline is too — keep them aligned.

## Useful artifacts from 2026-06-04 (reusable)
- `scripts/probe_heldout_value_corr.py` — the streaming held-out-corr gate (Gate A); multi-checkpoint table.
- `scripts/gate2_value_head_searchvalue.py` — generates search-value data + trains/compares heads (the
  spawn + W=1 pattern; the orchestrator would make it fast).
- `scripts/probe_value_head_c4.py`, `probe_value_target_c6.py` — the C4a/C6 kill-tests (both refuted).
