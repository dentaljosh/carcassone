# Path B — turning the value-bootstrap back on (KataGo-style)

> **Durable handoff doc.** Written 2026-05-29 right before a context compaction.
> A post-compaction Claude (or fresh thread) should be able to execute this
> step-by-step. Read [CLAUDE.md](../CLAUDE.md) → [STATUS.md](../STATUS.md) →
> this file. Live progress tracker mirrors these steps in the TodoWrite list.

## Why this exists (one paragraph)

Goal changed 2026-05-28: **genuinely superhuman play** (beat the world champ).
The blocker is structural: our strength is PUCT search over a **hand-crafted**
leaf (`virtual_score`/v2.7), which caps learned play near strong-human by
construction. Real AlphaZero's S-curve comes from a **value↔policy bootstrap**
fueled by a *learned* value trained on real outcomes — we disabled half of it
(Option 2, the NN-value leaf, was *worse* than the heuristic and got closed
2026-05-18, because the value head was data-starved). **KataGo's contribution
was making a learned value viable at far less compute** via richer inputs +
richer learned targets. Path B re-runs the Option-2 test, but this time with the
KataGo machinery that was missing. See [DECISIONS.md](../DECISIONS.md) 2026-05-28.

## The one question this answers (go/no-go)

> **Can a learned value head — given KataGo-style help (aux heads + domain input
> planes) — beat the v2.7 heuristic leaf head-to-head?**

If **GO** → the bootstrap can turn; commit to scaling (more iters, reference
ladder, Optuna-over-recipe). If **NO-GO** → architecture isn't enough at our
scale; superhuman is likely out of reach on this hardware (honest stop, or seek
more compute).

**The decisive test is cheap because the harness already exists.** Option 2
wired the "use NN value as the leaf" path (`LeafConfig.value_blend`, the
eval-server `compute_value` path). So the go/no-go is a leaf-swap A/B we can
already run:

> Same policy net both sides, sims=200, **n=400**: `(NN-value-as-leaf)` vs
> `(v2.7-heuristic-leaf)`. **GO if NN-value-leaf wins by > +15 elo** (n=400,
> 1σ≈±9, so +15 ≈ 1.7σ). NO-GO if ≤ 0 or within noise.

We don't build the test — we build a value head *worth* testing.

## Diagnostic gate — so a NO-GO is credible, not a tuning artifact

A bare negative A/B is ambiguous: did the architecture fail, or did we freeze a
bad knob? We resolve this by measuring the value head's quality **independent of
the head-to-head**, which turns "negative" into "negative *with a mechanism*."

**The orthogonal signal: value↔outcome correlation.** The Option-2 post-mortem
(2026-05-18) measured the old NN value head at **corr +0.18** with the game
outcome vs the heuristic's **+0.61** (STATUS.md / DECISIONS.md). That **+0.61 is
the baseline to beat.** After Path B training — and BEFORE trusting the A/B elo —
measure the learned value's correlation (and held-out value MSE vs the
heuristic's) on a sample of self-play games:

| value-corr vs 0.61 | A/B elo | reading |
|---|---|---|
| still ~0.2–0.3 | loses | **real NO-GO** — a value head that can't predict outcomes can't be rescued by any eval-side knob. Architecture/data is the wall. Credible stop. |
| ~0.55–0.65 | loses | failure is **integration/eval-side** (leaf-swap blend, search `c`), NOT the value head — a fixable, knob-shaped result. Look there before declaring NO-GO. |
| aux losses flat in training | — | labels are garbage (the Step 1 farm-ownership linchpin), not a tuning problem. |

**Confound insurance on the one genuinely-new knob (aux-weight).** The frozen
knobs split two ways: *inherited + validated* (sims / c_puct / dirichlet / temp /
value_target / epochs / games — the exact iter_01/B1 recipe, so NOT suspects if
the probe fails) and *genuinely-new* (aux-weight, domain planes, head arch). Only
aux-weight is a free scalar worth pre-checking, and it's cheap at warmstart (no
self-play loop): train warmstart at aux-weight **{0.0, 0.15, 0.5}** and confirm
(a) the policy/value mains don't degrade as the weight rises and (b) the aux heads
actually learn. If 0.15 looks clean there, freezing it for the loop is
*justified*, not assumed. Folded into Step 6.

## Frozen hyperparameters (decide once, HOLD — do not tweak mid-run)

The discipline (CLAUDE.md "Results discipline"): pick these up front, freeze them,
read the result. Most are NEW (not in results.csv — that's eval-side knobs only).

| knob | value | source / rationale |
|---|---|---|
| trunk | **6×96 ResNet (unchanged)** | bigger net only helps if signal uses it; the aux heads + domain planes ARE the signal change. Widen later only if GO. |
| aux-loss weight | **0.15 each** | KataGo-style: small enough to regularize, not dominate the policy/value mains. |
| self-play sims | **200** | this probe is about the value head, not search depth. Fast. (sims=800 is a separate lever.) |
| self-play c_puct | **1.5** | long-standing default; Dirichlet+temp drive early exploration so c matters little here. **If tonight's hygiene run resurrects c=3, optionally use 3.0 — not critical.** |
| dirichlet α / eps | **0.3 / 0.25** | match current production. |
| temp_threshold | **15** | match current. |
| value_target | **score_diff** | already default; aligns with the score-margin aux head. |
| train epochs / warmstart-mix | **3 / 0.0** | mirror iter_01/B1 (warmstart-mix 0 after the initial warmstart). |
| self-play games/iter | **1200** | matches the v25 retrain line. |

## Deterministic gates (baked into the loop — NOT human check-ins)

The self-play loop runs unattended; these are guardrails that halt+report.
**Implementation status audited 2026-05-29** (before any Step-8 launch):
- **NaN/inf loss** in any epoch → abort iter. **✅ IMPLEMENTED** —
  `train_iter.py:275` + `train_warmstart.py:246` (`if not torch.isfinite(loss)`).
- **Policy-entropy floor** (if mean policy entropy drops below ~0.5× the warmstart
  net's initial entropy → collapse, abort+report). **❌ NOT IMPLEMENTED** — no
  entropy check exists in train_iter / selfplay / run_phase4_smoke. **Step-8
  prerequisite:** either (a) build it (measure warmstart baseline entropy once;
  train_iter computes val-set mean policy entropy/iter; halt if <0.5× baseline;
  ~40 LoC), or (b) consciously rely on the anchor-gate (n=100/iter) + stop-after-2
  to catch collapse a bit later. Decide before launching the multi-day loop.
- **Anchor-gate per iter** (`eval_iter_head_to_head.py`): auto-play iter_N vs
  previous-best at **n=100, sims=200**; promote only if elo_delta > 0. **Stop after
  2 consecutive non-positive iters.** **✅ IMPLEMENTED** via run_phase4_smoke
  `--anchor-gate --anchor-max-fails 2`; set `--anchor-min-winrate 0.5` so "fail" ==
  "non-positive" (wr≤0.5 ≈ elo_delta≤0), matching the spec.
- Human re-engages ONLY on a gate trip or at the final go/no-go A/B.

## Build steps — the TODO (ordered; aux-targets first = correctness linchpin)

> Per-step **dev** estimates are aggressive (Joshua's bet: the dev is hours, not
> a week — the multi-day part is detached *compute*, not attention). Verify each
> file's current signature when implementing — do not trust line numbers from
> memory.

### Step 1 — Aux-target generation + validation  (THE LINCHPIN, ~2-4h dev)
- Compute, at each self-play game's terminal state, the labels the aux heads will
  learn: **(a) feature ownership** (who controls each city/road/farm at game-end),
  **(b) final score-margin** (have via score_diff — extend/confirm), **(c)
  closure-timing** (tiles-remaining when each open feature closed).
- The engine already computes final scores → ownership is derivable. **Farm
  ownership is the risky part** (long-range, the engine's most-likely-buggy area).
- **VALIDATE before training**: on a sample of games, assert the ownership labels
  reconcile with the engine's final scorer. A wrong label teaches the aux head
  garbage. This validation gate is non-negotiable. **✅ PASSED 2026-05-29:
  `validate_aux_targets.py --n 2000` → 0 reconciliation fails / 26,317 feature
  records / 12,086 farm records / 649 contested fields. Linchpin cleared; the
  smoke's "aux losses fall" check is now meaningful.**
- Add the new label arrays to the `.npz` schema (alongside boards/scalars/
  policies/players/valid_masks). Touch: `selfplay.py` (emit), `warmstart.py`
  (`GameDataset` load), the warmstart label generator.

### Step 2 — Domain input planes  (REVISED 2026-05-29 — mostly redundant; net-new part gated on a find_farm speedup)
- **Finding (2026-05-29):** 4 of the 6 originally-proposed inputs ALREADY exist as
  scalars in `features.py` — `meeples_remaining` mine/opp, `tiles_remaining`,
  `game_progress` (≈ is_endgame), plus `score_diff`. Don't re-add them.
- The only net-new signals are **`contested_features` + `my/opp_dominant_farms`**
  (farm-reasoning). These are FARM-derived → computing them runs farm enumeration
  (`find_farm`), and network INPUTS are encoded at **every MCTS leaf** (~200/move),
  so naively adding them hammers the #1 hot path. **They are deferred behind a
  `find_farm` speedup** (the engine fix made `find_farm` start-independent →
  cacheable/union-findable; see below).
- **✅ Leaf flood-fill speedup DONE 2026-05-29 (farm + city)** (dev complete, gated,
  benched; commit pending). Implemented as **lazy per-leaf memos** (`_farm_cache` farm
  regions, `_city_cache` city components), NOT the incremental union-find imagined here:
  the production leaf path (NeuralMCTS) uses functional `get_next_state` (deepcopy per
  step, no rollback — `apply_action_inplace` is only the vanilla-MCTS *random rollout*
  path, which the v2.7 leaf never runs), so per-leaf-state is correct, not
  incremental-across-tree. Profiling reset the priors: post-fix `find_farm` ~41% of the
  leaf (not 58%), `find_cities`/`find_city` ~31%, **>50% of those calls redundant within
  one eval**, deepcopy negligible. A/B picked lazy over eager whole-board decomposition
  (farm-only 1.27× vs 1.11×); **combined farm + city = 1.70× leaf / 1.48× end-to-end
  search** → ~33% faster ALL self-play + eval. City memo returns a fresh City per call
  (caches flood-fill data only) to preserve count_farm_points' identity-dedup →
  value-invariant. **Gate (non-negotiable, mirrors aux n=2000):**
  `scripts/reconcile_farm_index.py` region + value equivalence, **n=400, 921,953 nodes,
  0/0 mismatches**; `tests/test_farm_index.py`. `find_all_farms` (eager decomposition)
  kept in `farm_util` for the farm INPUT features below + as oracle. See DECISIONS
  2026-05-29 "Leaf flood-fill speedup IMPLEMENTED" / BACKLOG 2026-05-29.
- **Step E (farm INPUT features) — ✅ BUILT (2 scalars, opt-in, OFF by default).**
  `features.farm_control_scalars` adds 2 RAW structural scalars: `contested_field_count`
  (# fields both players farm) + `farm_control_balance` (# fields I lead − # opp leads),
  normalized by 4.0, appended after the base 10. Deliberately raw counts, NOT
  value-weighted by adjacent cities (value-weighting would re-encode the v2.7 heuristic's
  evaluation → contaminate the probe). Scalars not planes: an ownership *plane* would
  duplicate the Step-3 ownership aux *target* (feeding the answer we want learned). Gated
  by `Game(include_farm_scalars=True)` (→ `get_scalar_feature_size()` 10→12); the choice
  is saved in the checkpoint as `n_scalar_features` and propagates to `train_iter`
  automatically. Tests: `tests/test_farm_scalars.py` (29; index tally == independent
  find_meeples recompute, symmetry, net accepts 12). **Cost: ~FREE (+0.035 ms/leaf, 2.2%).**
  `make_v25_value_wrapper` (single + batch) shares one `_farm_cache`/`_city_cache` across the
  policy-encode (where the farm scalars flood farmer fields) and the v2.7 leaf-value pass — the
  leaf value floods the same fields anyway, so the scalar floods are reused. (Standalone it was
  +0.49 ms/encode; sharing cut it to +0.035 ms.) Value-invariant: gate n=400 0/0 + a
  wrapper-value==standalone-leaf test. **Flip-on is WIRED end-to-end** — every consumer derives
  the 12-scalar shape from the checkpoint's `n_scalar_features`: eval-server net + warmup,
  `run_selfplay_iter` worker/anchor nets + worker Games (main-process checkpoint peek →
  `cfg["include_farm_scalars"]`), `eval_iter_head_to_head` per-side Games, `train_iter`. The
  ONLY manual flag is at the start: `generate_warmstart_smoke --include-farm-scalars` +
  `train_warmstart --include-farm-scalars`. **Still lower-EV than the Step-3 aux heads**, but
  now free to include.

## LAUNCH RECIPE (2026-05-29 — 3-box work-stealing, nice -19, farm scalars IN — HOLD until Joshua says go)

Decided config: work-stealing across 5800X + Xeon + laptop, all workers `nice -n 19`, farm
scalars ON. Frozen knobs per the table above.

**Step 0 (pre-launch) — PROPAGATE to Xeon + laptop. ✅ DONE 2026-05-29.** Both clones now run the
fixed engine + full Path B code (`engine/ src/ scripts/ tests/`). Mechanism used:
- **Xeon** (`/home/doctor/projects/carcassone`): staged the 4 dirs to the 5800X `code_sync` share
  (`/mnt/c/carc-shared/code_sync/`), then ran `sync_pathb.sh` on the Xeon over `ssh xeon`→WSL
  (rsync from `/mnt/carc-shared/code_sync/` into the repo). **`sync_pathb.sh` lives on the share**
  for re-use. NOTE: pass the wsl invocation with NO shell operators on the cmd line (cmd.exe mangles
  `| && ;`) — that's why the chaining lives inside the script file. `pytest test_farm_index.py` 20/20.
- **Laptop** (`/home/pop/carcassone`, user `pop`): direct `rsync -a engine src scripts tests
  laptop:/home/pop/carcassone/` (Linux→Linux, no share hop). `pytest test_farm_index.py` 20/20.

Original note (kept for context): the launchers auto-sync only `scripts/`, but this work changed
`engine/` (`farm_util.py`, `city_util.py`) and `src/` (features, game_wrapper, virtual_score(_v2),
evaluators, eval_server, warmstart, aux_targets). The branch is ahead of `origin/gpu-orchestrator`
by >10, so the clones can't `git pull` without a push (ask Joshua) — hence the rsync/share route.
**Re-run before launch if any of those files change again** (re-stage + re-run `sync_pathb.sh` on
Xeon; re-rsync to laptop).

1. **Step 6 smoke (do FIRST, ~30 min):** tiny end-to-end at toy scale with farm scalars on —
   `generate_warmstart_smoke --label-strategy heuristic --include-farm-scalars --n <small>` →
   `train_warmstart --include-farm-scalars` (small) → 1 short `run_selfplay_iter` (e.g. 25 games,
   sims=25) → `train_iter` → anchor-gate via `eval_iter_head_to_head`. Assert: no NaN, aux losses
   fall, 12-scalar shape flows through, the value-leaf swap works. Also run the aux-weight
   sweep {0.0, 0.15, 0.5} at warmstart (confound insurance). **This catches a bug before days of compute.**
   - **1a. PROFILE the per-game hot path (`cProfile`, in-process, ~5 min).** The 1.48× leaf
     speedup shifted the bottleneck; the tree-ops side hasn't been re-profiled. ⚠️ **Do NOT
     `cProfile run_selfplay_iter.py` directly** — it always spawns a `spawn` `Pool`
     (`run_selfplay_iter.py:732`), so the parent profile captures only the main/orchestrator
     process and MISSES the per-game worker hot path (tree ops, `get_next_state` deepcopy, leaf
     eval) entirely. **Profile IN-PROCESS instead:** a tiny single-process harness that calls
     `selfplay.play_one_selfplay_game(...)` directly (no Pool) at **sims=200, batch_size=8, the
     v2.7 leaf wrapper** (`evaluators.make_v25_value_wrapper` / `make_v25_batch_value_wrapper`)
     on the warm net, for ~3 games, under `python -m cProfile -o /tmp/sp.prof`; then
     `pstats … sort_stats('cumulative')`. Expect the new hot path = per-tree-step `deepcopy` in
     `get_next_state`, `string_representation`, or `get_valid_moves` — NOT the leaf. **If any
     single fn is a >2× surprise vs its components, stop and fix before the multi-day run** (the
     "profile before long jobs" rule — saved ~3h in Phase 2). Else proceed.
   - **1b. RE-BENCH worker count (W) per box (~5 min each).** Current W (5800X=14, Xeon=10,
     laptop=24) were tuned against the OLD, slower leaf; a 1.48× faster leaf shifts the CPU/GPU
     balance (eval-server was ~70% idle → likely MORE workers now optimal, or the GPU becomes the
     ceiling). ⚠️ **`scripts/bench_workers.py` is the WRONG tool** — it times RAW-engine random
     games (no MCTS / no NN / no orchestrator), unrepresentative of self-play. Instead **time the
     REAL `run_selfplay_iter`** (orchestrator path, `--orchestrator --batch-size 8 --leaf-eval
     v2_5 --sims 200`, fixed `--games ~20`) at W ∈ {10,12,14,16,18}, read its own wall-clock /
     games-per-min, pick the per-box peak. Don't extrapolate — measure (bench-then-commit).
     **✅ RESULT 2026-05-29 (8 games/W, sims=200): curves FLAT** (post-speedup self-play is
     eval/GPU-bound — W barely matters ≥10). Peaks: **5800X W=14 (2.87 g/min), Xeon W=18 (1.90),
     laptop W=24 (4.34)**; cluster ≈546 g/h → ~2.2h self-play per 1200-game iter. Use these W for
     Step 8. Drivers: `/home/doctor/run_pathb_1b_wsweep.sh` (+ `xeon_1b_fg.sh` for the Xeon
     foreground-over-held-ssh, since WSL2 teardown kills nohup'd bg jobs).
2. **Step 7 — warmstart:** full `generate_warmstart_smoke ... --include-farm-scalars` corpus →
   `train_warmstart --include-farm-scalars --aux-weight 0.15` (6×96 trunk). Detached (nohup), nice -19.
   Produces the 12-scalar warm net (checkpoint records `n_scalar_features=12`).
3. **Step 8 — self-play loop:** `run_selfplay_iter` → `train_iter` → anchor-gate, looped,
   work-stealing `--shared-claim` across all 3 boxes, knobs frozen, deterministic gates baked in
   (NaN guard, entropy floor, stop-after-2-flat). Launch once, walk away. (include_farm auto-derives
   from the warm checkpoint — no extra flag needed downstream.)
4. **Step 9 — go/no-go A/B:** `(NN-value-leaf)` vs `(v2.7-heuristic-leaf)`, same policy net both
   sides, sims=200, n=400, via the `value_blend` leaf-swap. GO if > +15 elo. **Report value↔outcome
   correlation alongside the elo** (baseline to beat: heuristic's +0.61; the diagnostic gate).
   Append to `experiments/results.csv` + write a manifest.

### Step 3 — Auxiliary heads + losses  (~2-3h dev)
- In `network.py` (`CarcassonneNet`): add output heads for ownership / score /
  closure-timing predictions. Add their losses to the training objective at
  weight 0.15 each (mains: policy CE + value MSE unchanged).
- Touch `train_iter.py` (loss assembly) + `train_warmstart.py`.

### Step 4 — Bundle deferred feature fixes D1/D13  (~30min dev)
- From REVIEW_LOG.md: D13 (`features.py` `tiles_remaining` off-by-one), D1
  (`board_repr.py` ref-tile TILES-vs-MEEPLES encoding inconsistency). Free riders
  on the fresh-warmstart boundary. Decide D1: unify or keep+document.

### Step 5 — Warmstart pipeline update  (~1h dev)
- Regenerate the warmstart targets to include the new aux labels + new input
  shape. The existing heuristic-labeled warmstart corpus is the base.

### Step 6 — TINY-SCALE SMOKE (de-risks the whole run; ~30min + short compute)
- Run the FULL pipeline at toy scale: new-arch warmstart (small) → 1 short
  self-play iter (e.g. 25 games, sims=25) → train → anchor-gate. Assert: no NaN,
  aux losses decrease, anchor-gate runs, the value-leaf swap works. **This catches
  a bug before it eats days of compute.** Do not skip.
- **Aux-weight sensitivity (confound insurance — see "Diagnostic gate"):** run the
  small warmstart at aux-weight **{0.0, 0.15, 0.5}**; confirm the mains don't
  degrade as weight rises and the aux losses fall. Justifies freezing 0.15 for the
  loop instead of assuming it. Cheap here (warmstart only, no self-play).

### Step 7 — Launch warmstart  (compute: ~hours, detached, ask which box)
- Full warmstart of the new arch from heuristic-labeled data. nice -19, detached.

### Step 8 — Launch the self-play loop  (compute: ~days, detached, gates baked in)
- `run_selfplay_iter.py` → `train_iter.py` → anchor-gate, looped, **knobs frozen
  per the table above**, deterministic gates per the section above. Work-stealing
  across the cluster (5800X+Xeon+laptop). Launch once; walk away.

### Step 9 — The decisive go/no-go A/B  (compute: ~hours)
- `(NN-value-leaf)` vs `(v2.7-heuristic-leaf)`, same policy net both sides,
  sims=200, n=400, via the existing `value_blend` leaf-swap. GO if > +15 elo.
- **Report value↔outcome correlation alongside the elo (see "Diagnostic gate").**
  The elo is the headline; the corr is the *attribution*. A NO-GO is only credible
  paired with its mechanism — corr < 0.61 → real architecture wall; corr ≥ 0.61
  but elo loses → the failure is eval-side, look there before stopping.
- Append the result to `experiments/results.csv` (and write a manifest — see
  "results discipline" / the deferred manifest root-cause fix).

## What's already built (reuse — don't rebuild)
- Warmstart pipeline (`warmstart.py`, `train_warmstart.py`).
- Self-play loop + anchor-gate (`run_selfplay_iter.py`, `train_iter.py`,
  `eval_iter_head_to_head.py`) incl. work-stealing (`--shared-claim`).
- **The NN-value-as-leaf swap** (`LeafConfig.value_blend`, eval-server
  `compute_value`) — the go/no-go harness.
- `score_diff` value targets (the baby score-margin aux head).

## Risks
- **Aux-target correctness for farms** (Step 1) — the linchpin. Validate labels
  vs the engine scorer before training, or the aux head learns garbage.
- **Warmstart bias**: warm-starting the value head from heuristic labels biases
  it toward the heuristic. Mitigate by weighting self-play *outcomes* over
  heuristic labels for the value target during the loop.
- **Bigger/slower net** from new heads+planes — bench inference cost; if it
  meaningfully slows self-play, that's a cost input, not a blocker.

## Measurement note
The go/no-go A/B (Step 9) is self-contained — it does NOT need the strong
reference ladder. But measuring ABSOLUTE progress toward superhuman (after a GO)
DOES require the ladder (Tier-1 is saturated; self-anchored elo can lie). So:
reference ladder is the parallel/next workstream once Step 9 returns GO.
