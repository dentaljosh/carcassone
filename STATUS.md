# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A new Claude thread reading [CLAUDE.md](CLAUDE.md) → here should be able to take over without missing a beat.

## Right now (2026-05-15 ~18:05 EDT) — iter_01 retrain RUNNING LOCALLY. ETA ~Sat 06:20 EDT. Joshua away until Sun 11am.

**iter_01 retrain (in flight):**
- Launched 2026-05-15 18:04 EDT, detached (`nohup`, PID 46248). Log: `/tmp/iter01_local.log`.
- 1200-game v2.7 self-play, W=14, sims=200, initialized from iter_00, anchor-gate vs iter_00 (20 games sims=200, pass ≥50%).
- **Pure self-play training** (`--warmstart-mix-schedule 0,0,0,0`) — replicates iter_00's exact recipe (iter_00 trained with `warmstart_in_list=0` because the cloud box never had the warmstart .npz; for a clean "more data" A/B, iter_01 matches).
- Output: `checkpoints/v25_retrain_iter01/`, `data/selfplay/v25_retrain_iter01/`.
- **Why local, not cloud:** vast.ai's docker-pull infra was broken 2026-05-15 PM — 7 boxes across CA/JP/MY, 2 registries (ghcr.io + Docker Hub), all stalled at "Verifying Checksum". Abandoned cloud; ~$0.66 sunk (incl. one orphaned box — see memory `vastai-success-false-still-creates`). Local machine is free (Joshua away) so $0 cost + no unattended-spend risk.
- **Acceptance:** iter_01 wins ≥50% (≥10/20) of anchor-gate vs iter_00 → iter_01 is the new global best, data-scarcity hypothesis holds. If <50% → recipe ceiling, not data scarcity.

**W-bench (2026-05-15):** for the v2.7 self-play recipe, W=14 is the throughput optimum (1.66 games/min vs 1.47 at W=12, 1.58 at W=16). Old W=16 optimum was for the NN-value recipe; the heavier v2.7 leaf needs 2 threads of headroom for the orchestrator server + main.

**PUCT c sweep (earlier today, closed):**
- c≤1.0 catastrophic (iter_00 52.5% vs Tier-1 at c=1.0). c=1.5/2.0/3.0 within noise; c=1.5 stays default.
- Warning comment at `src/carcassonne_ai/mcts.py:298`.

**Day summary (closed):** hygiene cleanup; v3 leaf cap tuning (fitting noise, v2.7 holds); PUCT sweep (low-c boundary found).

**iter_00 (`checkpoints/v25_retrain/iter_00.pt`) is the global best until iter_01 lands.** Production: v2.7 leaf + c_puct=1.5 + sims=200.

**After iter_01 (pick when ready):**
1. If iter_01 PASSES: consider iter_02 (does it keep compounding?) or human-play test.
2. If iter_01 FAILS: recipe ceiling confirmed → bigger net (10×128) or human-play test.
3. **Human play vs iter_00/iter_01** — Tier-1 is saturated as a reference; only real measure of superhuman progress.

**Full sweep (rule_player+v1 vs iter_00+v3 leaf, env vars affect NN side only):**

| opp_cap | n=20 iter_00 wr | n=50 iter_00 wr | n=50 score diff (rule POV) |
|---|---|---|---|
| 5 | 95% ← lucky | **80%** | -26.3 |
| 8 | 75% ← unlucky | — | — |
| 12 (v2.7 implicit) | 90% | — | -37 (n=20) |
| 20 | 80% | 80% | -27.3 |
| 30 | 80% | — | — |

**Conclusion.** All opp_cap values land at 80% ± 5pp at n=50. The "90% baseline" anchor for v2.7 was n=20 too, so its true mean is likely also ~80%. **opp_cap in {5..30} doesn't materially change iter_00's strength vs Tier-1.** Score-diff signals likewise converged within ~1pt at n=50.

The v3 cap-tuning direction is exhausted. v2.7 cap=12 is the local optimum (or indistinguishable from one). The score-diff "regression" framing in commit `862ec37` was also over-reading n=20 noise — needs correction.

**What's next (real options, in priority order):**
1. **iter_01 retrain on v2.7** (~$2.40 cloud, ~6h). Tests whether more training data at the working leaf produces a stronger NN. Data scarcity is the most plausible remaining ceiling.
2. **Human-play vs iter_00.** Tier-1 is saturated as a reference — same 80% wr regardless of leaf cap. Need direct evidence vs a strong human.
3. **Different leaf STRUCTURE** (not cap tuning). E.g., learned leaf eval (small MLP trained on game outcomes), or hand-designed terms beyond closure anticipation (territory control, road completion forecasting, etc.).
4. **PUCT c sweep** (~30 min local, cheap). Hyperparameter on the search side, not the leaf.

Recommendation: #4 first (cheap closure on the search-side knob), then #1 if it shows headroom, #2 always.

**v3 result (commits `e55f622` infra + `862ec37` doc correction):**
- Tested two leaf additions: meeple_K × Δmeeples (failure-mode 4) and asymmetric `_OPP_BONUS_CAP` (failure-mode 3 — denial)
- meeple_K ∈ {0.5, 1.0, 2.0}: all null at n=20 (90% iter_00 wr unchanged)
- opp_cap ∈ {20, 30}: **regression** — iter_00 wr drops to 80% (n=50 confirms 80%, score-diff regresses from -37 → -27.3 from Tier-1 POV)
- Hypothesis "denial invisible" falsified at high opp_cap. v2.7's symmetric cap=12 is load-bearing
- Now testing opposite direction: opp_cap ∈ {5, 8} → does the NN currently over-defend at cap=12?

**Production unchanged (pre-v3):**
- v2.7 leaf: `_BONUS_CAP=12` + `_CLOSURE_P={1:0.5, 2:0.2}` (env vars: `CARCASSONNE_V25_CAP=12 CARCASSONNE_V25_DROP_THREE_OPEN=1`)
- iter_00 checkpoint at `checkpoints/v25_retrain/iter_00.pt` is global best. Beats warmstart_canonical 61.7%, iter_12 82.5%, Tier-1 90%.

**Next decision (gated on v3-down sweep result):**
- If opp_cap=5/8 also regresses: v2.7 cap=12 is the optimum. Pivot to: (a) iter_01 retrain on v2.7 (more data), or (b) human-play test, or (c) different leaf structure entirely (not just cap tuning).
- If opp_cap=5 or 8 *improves*: NN was over-defending. Re-sweep at fine grain, then promote.

## Earlier (2026-05-15 morning) — v2.5 retrain DONE: iter_00 +21pp over warmstart at v2.7 leaf. Total cost ~$2.40, box destroyed. Local artifacts pulled.

**Headline:**
- Production v2.5 leaf eval is now `_BONUS_CAP=12` + `_CLOSURE_P={1:0.5, 2:0.2}` (env vars: `CARCASSONNE_V25_CAP=12 CARCASSONNE_V25_DROP_THREE_OPEN=1`).
- New iter_00 checkpoint at `checkpoints/v25_retrain/iter_00.pt` (30 MB, ungitted).
- Anchor: iter_00 vs warmstart_canonical (both at v2.7 leaf, sims=200) = 18W/1D/11L = 61.7% wr, avg +14.3 pts/game.
- See DECISIONS.md 2026-05-15 for the full bug-find-and-fix narrative + cap/P sweep results.

**Day's narrative (chronological):**
1. Rented vast.ai 5090 + 48-core EPYC (instance 36800338, Japan, $0.37/hr).
2. First instance 36799296 had vast-side broken reverse-tunnel. Destroyed + retried per CLAUDE.md.
3. Bootstrapped (clone gpu-orchestrator + `pip install -e .` + `pip install -e engine/`) — captured in `scripts/cloud_bootstrap.sh`.
4. Launched 2K-game retrain with buggy v2.5; ETA was 6× pre-launch estimate.
5. Investigated v2.5 leaf cost; found over-counting bug (multiple meeples on same farm/city each got the bonus). Fixed via canonical-content dedup.
6. Killed cloud retrain (~$0.30 sunk on 192 contaminated games), pushed fix.
7. Re-bench: fixed v2.5 + cap=5 was 70% (down from buggy 80%) — cap was load-bearing on the buggy bonus magnitudes.
8. Cap re-sweep: cap=12 + 3-tier P = 85%. Then v2.7 (drop 3-open) + cap=12 = 90%. **Joshua's intuition** that 3-open features were lottery-ticket noise was right.
9. Launched 1200-game retrain with v2.7 + cap=12. ~6h10min wallclock.
10. Detached watchdog auto-pulled artifacts and destroyed box on completion.

**Production config (NEW):**
- **iter_00.pt is the new global best.** Beats warmstart_canonical 61.7% and iter_12 (prior v6 best) 82.5% at v2.7 leaf, sims=200, both sides.
- Leaf: `_hybrid_v2_evaluator` with v2.7 numerics (env vars above).
- Sims=200, W=12 + `--orchestrator` for local; W=48 for cloud.

**Strength ordering at v2.7 leaf (sims=200):**
1. iter_00 (new) — beats everything tested
2. warmstart_canonical (yesterday's baseline) — beats iter_12
3. iter_12 (v6 cloud best) — degraded by NN-value-driven self-play
4. Tier-1 — saturated reference (iter_00 wins 90% with avg +35 pts/game)

One iteration of v2.7-leaf-driven self-play (1200 games, single train pass) beat 13 iterations of v6-recipe NN-value-driven self-play. The leaf eval matters way more than iteration count.

**Still NOT superhuman.** Joshua still beats Tier-1 2-of-3. But the policy + leaf are both meaningfully stronger than yesterday. Phase 5 still gated. Next ablations:
- Bench iter_00 + v2.7 vs Tier-1 (in flight at write time, ~9 min local).
- iter_00 vs iter_12 head-to-head (which is the real "best so far"?).
- Another retrain iter from iter_00 (would be iter_01, recipe v2 = v2.7 leaf throughout).



**Sequence today:**
1. Rented vast.ai 36800338 (5090, Japan, $0.37/hr). First instance (36799296) had broken vast reverse-tunnel — destroyed + retried per CLAUDE.md.
2. Bootstrapped (clone + `pip install -e .` + `pip install -e engine/`), smoke-tested, launched 2K-game retrain at sims=200 W=48 batch=8 v2_5+orchestrator.
3. ETA realized as 5.8h instead of expected 1.6h — 6× off because my pre-launch local smoke was sims=50 (1/4 the CPU work) and v2.5 leaf eval is intrinsically expensive (engine farm/city utils per leaf).
4. Investigated: found a real over-counting bug in `_closure_anticipation_bonus` — multiple meeples on the same farm/city each got the bonus added separately, but the engine itself only scores each farm/city once per player. Fixed via dedup keyed on `frozenset(farm.farmer_connections_with_coordinate)` and `frozenset(city.city_positions)`. Commit `08dfead`.
5. Killed cloud retrain (~$0.30 sunk on 192 generated games — discarded; they used the buggy bonus magnitudes). Pushed fix to GitHub.
6. **Now:** running n=20 sims=200 bench on cloud with FIXED v2.5 to confirm wr ≥ 70% before re-launching retrain.

**Pending decision:** if fixed v2.5 wr ≥ 70%, re-launch the cloud retrain with `08dfead`. If wr < 70%, the cap=5 was load-bearing on the buggy bonus magnitudes — would need to retune cap (probably cap=8 or cap=12) and re-bench.

**(Update 06:00 UTC):** fixed v2.5 + cap=5 = 70% (matched threshold but suspected weaker than buggy 80%). Ran cap re-sweep:

| config (n=20 sims=200 each) | wr | avg diff |
|---|---|---|
| fixed + cap=5 | 70% | n/a |
| fixed + cap=8 | 60% | -17.8 |
| fixed + cap=12 (3-tier P) | 85% | -22.4 |
| fixed + cap=20 (3-tier P) | 85% | -34.7 |
| fixed + cap=12 + 1-open-only (v2.6) | 77.5% | -18.4 |
| **fixed + cap=12 + drop-3-open (v2.7)** | **90%** | **-30.6** |

v2.7 winning config: `_CLOSURE_P = {1: 0.5, 2: 0.2}` + cap=12 (env vars `CARCASSONNE_V25_DROP_THREE_OPEN=1` + `CARCASSONNE_V25_CAP=12`). +10pp over the buggy v2.5. Joshua's intuition that 3-open was just lottery-ticket noise was right.

**Cloud retrain v2 launched** (commit `f89b5f3`, 1200 games, sims=200, batch=8 vloss=1.0 orchestrator + v2_5 leaf + v2.7 P + cap=12). ETA ~5h, finishes ~10:55 UTC. Watchdog running detached on local WSL (PID 54199), will auto-pull artifacts + `vastai destroy 36800338` when retrain completes. Watchdog log at `/tmp/retrain_watchdog.log`.





**Cloud command launched:**
```
nohup python -u scripts/run_phase4_smoke.py \
  --iters 1 --games 2000 --sims 200 \
  --eval-sims 200 --eval-games 50 \
  --workers 48 --eval-workers 48 \
  --batch-size 8 --virtual-loss 1.0 \
  --window 30 \
  --warmstart-mix-schedule "0.0,0.0,0.0,0.0" \
  --anchor-gate \
  --anchor-checkpoint /workspace/carcassone/checkpoints/warmstart_canonical.pt \
  --anchor-games 30 --anchor-sims 200 \
  --anchor-min-winrate 0.5 --anchor-max-fails 1 \
  --initial-checkpoint /workspace/carcassone/checkpoints/warmstart_canonical.pt \
  --orchestrator --leaf-eval v2_5 \
  --checkpoint-root /workspace/carcassone/checkpoints/v25_retrain \
  --output-root /workspace/carcassone/data/selfplay/v25_retrain \
  > /tmp/v25_retrain.log 2>&1 & disown
```

Self-play 2K games at sims=200 with v2.5 leaf + W=48 workers + batching + orchestrator. ETA ~90 min self-play + 5 min train + 3 min anchor = ~100 min. Cost ~$0.65.

**Cloud-prep recipe captured** in `scripts/cloud_bootstrap.sh` (commit pending) — clones gpu-orchestrator branch, installs both `carcassonne-ai` and vendored `wingedsheep` packages editable. The first cloud attempt today hit `ModuleNotFoundError` twice because the `ghcr.io/dentaljosh/carcassone-cloud:latest` image has torch+cuda but neither project package preinstalled.

**Lessons from today's bootstrap:**
1. First instance (id 36799296, mach 79955) failed with vast-side broken reverse-tunnel ("Error: remote port forwarding failed for listen port 39296"). Status flipped to `running` but SSH was unreachable. Destroyed + retried per CLAUDE.md rule.
2. Active polling Monitor now also includes an SSH probe gate: only emits `READY` when `actual_status=running` AND `ssh root@... 'echo OK'` succeeds. Avoids the "running-but-unreachable" failure mode.
3. The cloud image needs `pip install -e .` and `pip install -e engine/` before running anything — captured in `scripts/cloud_bootstrap.sh`.

**Still NOT superhuman** — Joshua still beats Tier-1 2-of-3. Phase 5 still gated. Cloud retrain is the test of whether v2.5-driven self-play data improves the policy head enough to get us closer.



### v2 → v2.5 progression

| Eval | Tier-1 wr | hybrid wr | avg diff (Tier-1 view) | n |
|---|---|---|---|---|
| hybrid_v1 sims=400 | 23.3% | 76.7% | +15.5 | 30 |
| hybrid_v2 sims=400 | 70.0% | 30.0% | +10.6 | 30 |
| **hybrid_v2.5 sims=400** | **16.7%** | **83.3%** | **-30.7 (Tier-1 LOSES by avg 31)** | 30 |

v2 failed (47pp regression) because the closure-anticipation + farm-growth bonuses were 4-7× larger than the base virtual_score, saturating the tanh leaf squash and killing the search gradient. v2-diagnostic confirmed root cause was scale, not bugs (cathedral branch never fired).

v2.5 = halved P heuristic ({1: 0.5, 2: 0.2, 3: 0.05}) + hard cap on per-player bonus at ±5. The cap hits 75% of self-moves in diagnostic (the bonus *wants* to be much larger, the cap rate-limits it). Bench result: +6.6pp over v1, +53pp over v2.

**Module:** `src/carcassonne_ai/virtual_score_v2.py` (kept the v2 name for git continuity; the constants are v2.5).

**Production config (NEW):** `warmstart_canonical.pt` + `_hybrid_v2_evaluator` (v2.5 numerics) + **sims=200** (sweet spot per sweep below) + W=12 + `--orchestrator`.

### v2.5 sims sweep result (2026-05-14)

| sims | v2.5 wr | v1 wr (same scale) | v2.5 advantage |
|---|---|---|---|
| 50  | 50.0% | 63.3% | -13.3pp |
| 100 | 71.7% | 58.3% | +13.4pp |
| **200** | **80.0%** | 70.0% | **+10.0pp** |
| 400 | 83.3% | 76.7% | +6.6pp |

v2.5 ramps with depth more steeply than v1. Bonuses are noise at sims=50, signal at sims≥100. **sims=200 is the new production sweet spot** (80% wr at half compute of 400). Orchestrator at W=12 saves ~25% local wallclock vs W=6 baseline.

### v2.5 cap sweep result (2026-05-14)

| cap | v2.5 wr | Δ vs cap=5 |
|---|---|---|
| 2  | 60.0% | -20.0pp |
| **5 (production)** | **80.0%** | — |
| 8  | 73.3% | -6.7pp |
| 15 | 76.7% | -3.3pp |

Clean inverted-U around cap=5. Hand-picked initial value happens to land on the knee. Plumbed `CARCASSONNE_V25_CAP` env var for future sweeps without source edits.

### Cloud-prep complete (2026-05-14 evening)

Plumbed `--leaf-eval {nn, v2_5}` through the full self-play stack so a future cloud retrain can use v2.5 leaf-eval for game generation (commit `1d3a0cb`):

- `src/carcassonne_ai/evaluators.py` — new `make_v25_value_wrapper` / `make_v25_batch_value_wrapper` helpers that take any (priors, value) evaluator and replace the value with `tanh(virtual_score_v2/15)`.
- `scripts/run_selfplay_iter.py` — `--leaf-eval` flag, applied after evaluator construction.
- `scripts/eval_iter_head_to_head.py` — `--leaf-eval` flag, applied to BOTH sides for apples-to-apples eval.
- `scripts/run_phase4_smoke.py` — propagates `--leaf-eval` to all 3 substages (self-play, anchor-gate, chain h2h).

Defaults stay `nn` for back-compat. Cloud command would be: add `--leaf-eval v2_5 --batch-size 8 --virtual-loss 1.0 --orchestrator` to the v6 recipe baseline.

`train_iter.py` is **unaffected** by leaf-eval choice — it loads stored datasets where the value labels are game outcomes (z = W/D/L), not leaf evaluations.

**End-to-end smoke** (W=4 sims=50 batch_size=8 vloss=1.0 orch v2_5, 4 games):
- avg_batch=7.2 (vs 2.4 we measured at W=6 without batching today — ~3× batch fill from MCTS virtual-loss alone)
- Stage breakdown 74% dequeue / 26% forward — GPU is now waiting for workers (the inverse of yesterday's bottleneck). At cloud W=48 this will scale beautifully.
- 4 self-play games in 78s, 663 positions. Smoke-passed.

Caveat to watch on the actual cloud run: at h2h sims=50 n=4 self-vs-self, smoke gave 4W/0D/0L (instead of expected 50/50). Probably MCTS-seed asymmetry magnified by tiny N — verify with n=20+ games on the actual cloud before trusting results.

### Cloud cost estimate (revised)

For a policy-head retrain on v2.5 self-play data:
- Self-play 10K games at sims=200, W=48, orchestrator+v2.5: ~30 min total → ~$0.20
- Training pass (1 iter ~ 5 min): ~$0.04
- Anchor eval: ~$0.10
- Box bootstrap + slack: $0.50

**Total ~$1, not yesterday's $5 estimate.** Most of the savings come from sims=400→200 (per the sims sweep) and the orchestrator+batching plumbing landed today.

**Still NOT superhuman** — Joshua still beats Tier-1 2-of-3. Phase 5 still gated. Next: either trigger the policy-head retrain (cloud) or human-vs-bot test (cheap, no compute).

### Day 2 prior findings ledger (still current)

| Discovery | Source experiment |
|---|---|
| NN value head was actively harmful | hybrid (NN policy + virtual_score leaf) at sims=100 → Tier-1 40%; NN-only at same → Tier-1 75% |
| v1-v6 self-play degraded the policy head | hybrid iter_12 → Tier-1 40%; hybrid warmstart_canonical → Tier-1 23-42% range |
| NN policy head is worth ~18pp | puct_uniform sims=100 → Tier-1 60%; hybrid_warmstart sims=100 → Tier-1 42% |
| sims=400 is the scaling ceiling | sims=200 → 70% hybrid; sims=400 → 77% hybrid; sims=800 → 77% hybrid (no gain) |

### Production config

`warmstart_canonical.pt` + `_hybrid_evaluator` (NN policy priors + tanh(virtual_score/15) leaf) + sims=400 + ≥4 workers. Beats Tier-1 76.7% by avg 15 pts/game.

The bench harness is at [scripts/eval_rule_player.py](scripts/eval_rule_player.py) with three new opponent types: `heuristic_mcts` (no NN), `hybrid` (NN priors + virtual_score), `puct_uniform` (uniform priors + virtual_score, diagnostic).

### Open ablation queue

See [EXPERIMENTS.md](EXPERIMENTS.md). Top priority: **diagnose virtual_score's blind spots** from games where hybrid lost (no compute, ~1 day analysis). Output: catalog of failure modes ranked by frequency, ready to inform virtual_score_v2 design.

**Day 1 (2026-05-13, committed `64f7a74`):** Tier-1 rule-based player. 1-ply argmax of virtual_score. Beat warmstart_canonical 77% (n=50 sims=100), beat iter_12 75% (n=50 sims=100). Recipe-ceiling confirmed empirically.

**Day 2 (2026-05-14, in progress):** Diagnosis-by-substitution experiments to isolate which component of NeuralMCTS is broken. Both heads are broken in *different* ways:

| Setup | Tier-1 winrate | Avg score diff |
|---|---|---|
| iter_12 NN-only sims=100 (yesterday's bench, n=50) | **75%** (Tier-1 dominant) | — |
| HeuristicMCTS (no-NN, UCT+virtual_score leaf) sims=200 (n=20) | 60% | -1.1 |
| Hybrid iter_12 sims=100 (n=20) | 40% | -6.8 |
| Hybrid iter_12 sims=200 (n=20) | 40% | -5.2 |
| **Hybrid warmstart_canonical sims=100 (n=20)** | **20%** | **-16.2** |
| Hybrid warmstart_canonical sims=200 (n=20) | _in flight_ | _in flight_ |

**Two damning conclusions:**

1. **The NN's value head was actively harmful** (proven by hybrid iter_12 sims=100). Same network, same MCTS, same sims — only swapped the value output for `virtual_score(state)`. Win rate vs Tier-1 jumped from 25% to 60% (a 35-pp swing). The value head IS trained on `tanh(virtual_score/15)` targets — it's an *approximation* of what we now just compute exactly, and it's WORSE than the exact answer.

2. **v1-v6 self-play *degraded* the policy head** (proven by hybrid warmstart_canonical vs hybrid iter_12). The day-0 heuristic-warmstart policy is *substantially stronger* than iter_12's policy after 12 iterations of self-play training. Hybrid_warmstart sims=100 wins 80% vs Tier-1 by avg 16 points; hybrid_iter_12 at the same sims wins only 60% by avg 7 points. Doubling sims on iter_12 didn't close the gap.

**Net effect of all of Phase 4 (v1-v6) on the model: NEGATIVE on both heads.** Weeks of cloud compute made the model strictly worse than what we had at end-of-Phase-3.

**Why this matters:** the value head IS trained on `tanh(virtual_score/15)` targets. The network is supposed to *approximate* what we now just compute directly. It's approximating it *worse* than the exact answer. Hypotheses (not yet diagnosed): (a) MCTS-induced distribution shift — training labels from completed-game states, but search evaluates partial-game leaves outside that distribution; (b) capacity starved by the policy head's `Linear(2500, 2511)` ~6M params dominating the trunk; (c) subtle perspective/sign bug.

**Code shipped (uncommitted):**
- [src/carcassonne_ai/mcts.py](src/carcassonne_ai/mcts.py) — added `HeuristicMCTS` class (vanilla UCT + virtual_score leaf, no NN).
- [tests/test_mcts.py](tests/test_mcts.py) — 5 new tests (all 11 pass).
- [scripts/eval_rule_player.py](scripts/eval_rule_player.py) — `--opponent heuristic_mcts` (fork pool) and `--opponent hybrid` (spawn pool, NN priors + virtual_score leaf via `_hybrid_evaluator`).

**Bench chain in flight:** (1) Hybrid `warmstart_canonical` sims=100 n=20 vs Tier-1 — tests whether v1-v6 self-play actually improved the policy head (vs already-strong heuristic-warmstart). (2) Hybrid `iter_12` sims=200 n=20 vs Tier-1 — tests how high hybrid's win rate scales with sims. ETA ~27 min total.

**Path to superhuman is now concrete:** production MCTS with NN policy + virtual_score leaf. No more value-head call at search time. Architectural follow-ups: delete the value head entirely (it's harmful AND it's slow), simplifying the net and freeing trunk capacity for the policy head.

**Backlog item logged 2026-05-14:** action-space dedup for redundant meeple-placement slots (10-25% inflation on meeple-phase actions, wastes policy-head capacity). See [BACKLOG.md](BACKLOG.md).

---

## Previously (2026-05-13) — v6 DONE. iter_12 = 70% wr new global best. **MCTS perf: 5 patches → ~7.6× game-wallclock speedup at production sims=200.**

**Five engine + wrapper patches landed on `gpu-orchestrator` (commits `5afb6b5`, `b9431de`).** Started by cProfile-ing one self-play game; the actual hot path was `copy.deepcopy` (75% of wallclock for per-tree-step state copy), not the PUCT loop or GPU forward as predicted. Iterated four more times, profile-driven:

| Loop | Patch | s/game @ sims=50 | Cumulative |
|---|---|---|---|
| 0 | baseline (default deepcopy) | 84.7 | 1.00× |
| 1 | engine state `__deepcopy__` (shares immutable Tile/TileAction/Coord refs) | 25.5 | 3.32× |
| 2 | tile `_type_cache` (precompute `(side → TerrainType)` once per Tile) | 16.9 | 5.01× |
| 3 | rot_sig + str_repr caches on Tile / Board | ~15.7 | ~5.4× |
| 4 | `placed_coords: set[Coordinate]` on engine state (replaces 1225-cell board walk) | 14.5 | 5.84× |
| 5 | `tile.turn(N)` cache per Tile | _(sims=200: 80→44.5, 1.79×)_ | **~7.6× at sims=200** |

At production sims=200 batch=8 (the v6 config), local wallclock dropped from ~80s/game (post-loop-4) to **44.5s/game** post-loop-5. Estimated pre-patch baseline at sims=200 was ~339s/game (4× the sims=50 baseline of 84.7s), so cumulative speedup at production scale is **~7.6×**.

**169/169 tests pass.** 5 new regression tests added (`tests/test_state_deepcopy.py` for equivalence + cache-invalidation, `tests/test_engine_adjacency.py` for placed_coords).

**Cloud-iter implication (corrected):** v6 was ~9h / $3.40 for 20 iters. Self-play phase was ~13 min of ~26 min/iter; post-patch ~1.7 min/iter on self-play. Train is unchanged at ~5 min/iter and is now the next bottleneck. **Total iter ~26 min → ~10 min ≈ 2.6× per-iter speedup**; 20 iters ~9h → ~3.4h / $1.30. Not the 5-6× the bare self-play speedup might suggest — train + h2h + anchor are all in the path.

**Next concrete action — Phase A cloud bench (~$0.15, ~20 min):** rent a 5090 + 48-core EPYC, run iter-0 self-play twice (orchestrator off vs on) at production knobs, compare wallclock + GPU util. Validates the patches survive at scale, confirms orchestrator still cracks W=48 OOM, and produces a real prod-hardware bottleneck breakdown.



**v6 cloud result** (20 iters, 490 min wallclock, ~$3.40 cloud + $0.06 sunk on a destroyed pre-launch box):
- **Best: iter_12 at 70% wr** — first checkpoint ever to beat warmstart_canonical at ≥70% wr (+5pp over v5's 65% peak).
- **Pass rate: 15/20 (75%)** vs v5's 5/10 (50%). v6 strictly Pareto-dominates v5 on every metric.
- Trajectory shape: 65 65 35F 60 50 40 50 35F 50 60 35F 45 **70** 65 45 55 30F 45 25F 65.
- All 4 launch-time bugs fixed on `gpu-orchestrator` (Dockerfile sshd, bootstrap warmstart data, orchestrator-flag passthrough, see DECISIONS.md). Artifacts at `checkpoints/selfplay_v6/iter_00..19.pt` + `data/selfplay/v6_cloud/`. Cloud box destroyed.

**Three null results that shape v7:**
- 192×14 warmstart locally trained — 2.1× the params, ~zero val-loss improvement. **Capacity is not the bottleneck at our 10k data scale.**
- RuleBasedPlayer (meeple-only rules) vs random: 44% wr. **Tile-placement dominates the value question;** meeple-side rules can't compete.
- Multi-process orchestrator pool (built + cloud-swept 2026-05-13, ~$0.56): N=1 optimal; N=2/4/8 strictly slower (+4/+7/+7%). The orchestrator GIL was never the bottleneck — workers (CPU-bound MCTS tree work) are. Code stays in repo (correct + back-compat at n_shards=1); v7 launches `--orch-shards 1`. See DECISIONS.md "2026-05-13 — Orchestrator multi-process pool: NULL RESULT".

**fp16 is DEAD for our workload** (DECISIONS.md, two independent benches): local 5060 Ti 0.82× single / 0.92× batch=8; cloud 5090 same shape. Autocast + cast-back overhead exceeds compute savings on 7M-param net + small batch. Revisit only if (a) net >30M params or (b) batch >32. Not a v7 perf lever.

**Real v7 perf levers (in order, after eliminating fp16):**
1. **MCTS Python hot-path optimization.** ~50% of worker time is pure-Python MCTS tree work (selection, expansion, backup). Profile first to find the actual hotspot, then numpy-vectorize or Cython-rewrite the inner loop. This is the binding constraint now that orchestrator is ruled out.
2. **Symmetry rotation augmentation** (recipe-side, not perf): free ~4× training data — addresses the data-scarcity ceiling independently.
3. Right-size box: at games=80 we cap workers at 80 regardless of cores; a 32-core box at $0.30/hr would be a better $/throughput than the 48-core EPYC.

**v7 direction (next plan-mode session):** the data-scarcity hypothesis. Recipe ceiling at ~70% + capacity null → bottleneck is "not enough diverse training data". Cheap leverage:
1. Symmetry rotation augmentation (free 4× data)
2. Start from `iter_12.pt` (70% wr — new global best)
3. Apply v6's recipe with orchestrator pool at N=1 (the swept optimum)
4. If symmetry alone doesn't break ceiling, layer in KataGo-style aux loss heads next.

**Next concrete action:** profile MCTS locally (cProfile a 200-sim self-play game on the current warmstart_canonical or iter_12, ~30 min) to find the actual hot lines before deciding optimization scope.

---

## (Archive) 2026-05-12 night — Phase A bench: orchestrator validated, W=96 throughput optimum

**Phase A results (~$1.40 spend):**
- Orchestrator W=48 chain h2h: 2 MiB final VRAM (vs baseline 58 GB → OOM). Smoking-gun pass.
- Baseline self-play at W=48 OOM'd 36/80 games on torch 2.11 (larger allocator pool than torch 2.7).
- Worker sweep (W=44-96): non-monotonic, **W=96 best at 992.9s/80 games** (15% faster than W=48). W=64 is the perf VALLEY.

**Cloud image** (`ghcr.io/dentaljosh/carcassone-cloud:latest`) built via GH Action. Public.

---

## (Archive) 2026-05-12 evening — v5 cloud peaked above warmstart (iter_06 = 65% wr!) but halted at iter 9; GPU orchestrator landed on `gpu-orchestrator` branch

**Branch:** `gpu-orchestrator` (off `phase-4-selfplay`), pushed to `https://github.com/dentaljosh/carcassone` — public GH repo created today; cloud bootstrap can now `git clone` instead of rsync-over-proxy.

**v5 cloud result (~$5 total spend):**
- Recipe: mix-floor 0.5 + K=30 + best-so-far rachet + anchor-gate n=20 + sims=200 on rented 5090 + 48-core EPYC.
- Harness halted at iter 9 (3 consecutive FAILs, max-fails=3).
- Anchor trajectory: 40 PASS → 20 FAIL → 50 PASS → **60 PASS** → 30 FAIL → 50 PASS → **65 PASS** → 35 FAIL → 35 FAIL → 25 FAIL.
- **iter 3 and iter 6 are the first checkpoints that beat warmstart_canonical by a meaningful margin** (+20-25 pp). Recipe peaks above baseline but drifts back down. Rachet couldn't recover after iter 6.

**v5 artifacts persisted** to `checkpoints/selfplay_v5/iter_00..09.pt` + `data/selfplay/v5_cloud/` (gitignored, total 380 MB). Cloud box destroyed. `iter_06.pt` is the local peak (65% wr vs warmstart_canonical).

**GPU orchestrator landed today (commit `2191a61` on `gpu-orchestrator`):**
- `src/carcassonne_ai/eval_server.py` + `remote_evaluators.py` + `tests/test_eval_server.py` (4/4 pass in 24 s).
- `--orchestrator` flag on `run_selfplay_iter.py` (1 server) + `eval_iter_head_to_head.py` (2 servers).
- Numerical agreement < 1e-5 vs `make_batch_evaluator`. Local 5060 Ti bench: 0.91× (selfplay) / 0.88× (eval) — IPC overhead dominates on small GPU. Cloud W=48 vs current OOM-cap-W=20 is the actual proof-point.

**Recipe ceiling chronology:**
- v1: -330 ELO at iter 24 (chain-ELO discredited)
- v2: -200 ELO at iter 4
- v3: -107 to -123 ELO at iter 3/4
- v4: ceiling at ~50% wr, no above-baseline iter
- v5: **peaked at +25 pp (iter 6, 65%)** but couldn't sustain — first real partial-success

**Next-decision (plan-mode session needed):** "Phase 4 v6 + orchestrator-on" cloud run. Forks worth considering:
1. Use v5 `iter_06.pt` (the +25 pp peak) as the new warmstart and re-run v5 recipe
2. Bigger net (10×128 or 14×192) — orchestrator unlocks the VRAM headroom
3. Async training (train continuously while self-play runs)
4. Cheapest single experiment first: orchestrator cloud bench at W=48 chain h2h (~$1-2, ~1 h, proves the OOM fix)

**Vast.ai balance**: check before next launch.

---

## (Archive) 2026-05-12 morning — v3/v4 recipe both regressed; cloud bench validated W=48 + fp32

**Branch:** `phase-4-selfplay`. Latest commits `20aa166` (v3 recipe), `de8abd4` (fp16 batch bench), `503d004` (v2 fail docs).

**v3 result (2026-05-11)**: 5-iter sanity with mix=0.5 floor + best-so-far rachet + anchor-gate ran 4h on local 5800X+5060Ti. Anchor curve oscillated 40-60% (n=10 noisy); definitive 50-game anchors revealed **iter_3 at 34% wr, iter_4 at 32% wr → ELO -107 to -123 vs warmstart_canonical**. Improvement over v2's -200 ELO but still failed the ≥40% acceptance bar. Rachet kept rolling back to iter_0 (best at 55-80% n=10, true ~50%); chain never advanced. Quarantined.

**v4 attempt (2026-05-11 → -12)**: Same v3 recipe but **n=20 anchor gate** (tighter signal). Ran 5 iters on local W=16: iter 0=55%, iter 1=40%, iter 2=20% FAIL, iter 3=40%, iter 4=40%, iter 5=35% FAIL. Killed after 5 iters — pattern crystal clear: **iter_0 (55%) remains best-so-far indefinitely, rachet keeps rolling back, no iter ever exceeds warmstart**. Local recipe ceiling confirmed at ~50% wr vs warmstart.

**Cloud bench (2026-05-12 05:00-07:00 UTC, ~$0.40 spent)**:
- Rented RTX 5090 + 48-core EPYC 9J14 at $0.387/hr (Japan)
- Worker scaling sweep at sims=100/games=64: W=8→W=48 near-linear (~7× speedup), W=64 OOM at 32 GB VRAM
- **W=48 is the safe max** without MPS
- fp16 bench on Blackwell: single 0.82×, batch=8 0.92× (SLOWER both ways) — autocast overhead exceeds GPU compute savings for our 7M-param net + small batch
- Conclusion: **stay fp32, use W=48 for prod**

**MPS attempt #1 (2026-05-12, ~$0.40 wasted)**: Second 5090 rental had flaky network; rsync deadlocked twice for 30+ min. Destroyed without bench.

**MPS attempt #2 (2026-05-12, ~$0.40 wasted)**: Killed `uv pip install` mid-way to save time after it took 6+ min on torch>=2.7 upgrade. Bench ran but VRAM samples showed 0 processes — selfplay python failed silently at runtime (likely missing dep). Auto-destroy fired before I could cancel. No usable data.

**MPS test landed 2026-05-12 (~13:00 UTC, instance 36616189)**: per-worker VRAM is 662 MB no_mps / ~600 MB MPS (only ~10% savings — bottleneck is PyTorch allocator pool, not CUDA context). W=52 + MPS fits VRAM (31977/32607 = 98% used) but is *slower* than W=48 due to cgroup CPU oversubscription (5.3s/game wallclock vs 3.4s at W=48). **W=48 + fp32 + no-MPS is the locked optimum.** Real fix for scaling past 48 is inference-server pattern (1-2 days eng) or rent an 80 GB GPU (~$2/hr).

**Lesson learned**: `torch>=2.7` pin in requirements.txt is load-bearing for Blackwell (sm_120). Two wasted MPS rental attempts ($0.80) because we tried to skip the torch upgrade and use the pre-installed 2.4.0. Never skip uv pip install on a fresh box.

**Prod run plan (waiting on MPS data):**
- Recipe: same v3/v4 (mix=0.5, best-so-far, anchor-gate n=20) at sims=200, games=80
- Box: 5090 + 48-core EPYC, host 384353 has been reliable
- Workers: W=48 (or higher if MPS validates)
- 30 iters ≈ 25h × $0.387 ≈ $10 ($5 if MPS works)

**Vast.ai balance**: $2.07 → top up to ~$15 before prod.

**Open items deferred:**
- Bigger network (10×128 or 14×192) for if even cloud sims=200 plateaus
- Inference-server pattern (single network on GPU, workers query via queue) — addresses VRAM bottleneck structurally vs MPS

---

## (Archive) 2026-05-11 — Phase 4 v2 also regressed (-200 ELO); v3 recipe TBD

**Branch:** `phase-4-selfplay`. Latest commit `a1f29ec` (v2 recipe fixes).

**Headline:** v2 recipe (mix-floor 0.3, K=30, anchor-gate, eval-games 50) ran 5 iters in 4h. Chain ELO drift -98 (vs v1's misleading +612). Definitive iter_4 vs warmstart_canonical at n=50: **24% wr, ELO -200** (95% CI [13%, 37%], upper bound below the 40% acceptance threshold). Real regression, not noise. Recipe fix wasn't strong enough at this floor value. See DECISIONS.md "2026-05-11 — Phase 4 v2 recipe FAILED acceptance".

**Quarantined v2 artifacts (alongside v1; do NOT use as warmstart):**
- `checkpoints/selfplay_v2/iter_*.pt` (iters 0-4)
- `data/selfplay/v2_sanity/`
- Both kept on disk for Phase 6 emergence analysis.

**v3 recipe candidates (needs plan-mode session before implementing — don't piecemeal):**
1. Higher warmstart-mix floor (0.5 or 0.7) — most direct fix
2. Best-so-far reference instead of warmstart_canonical
3. Higher sims for self-play (200 vs 100) — addresses noisy policy targets
4. Reject-iter on anchor FAIL — restart from prev good iter instead of advancing

Select 1-2 for v3 (don't try all four — confounds the diagnosis if v3 also fails).

**Vast.ai rental still gated.** Balance unchanged at $2.07. Don't rent until v3 passes the anchor-bar acceptance.

**Open items deferred:**
- Bench fp16 with the BATCH evaluator on a meaningful checkpoint (single-evaluator was 0.83× = SLOWER on local 5060Ti). Wait until v3+ produces a non-quarantined checkpoint.
- Root-cause snapshot-mask vs MCTS-mask divergence (defensive clip handles symptom).

---

## (Archive) 2026-05-10 — Phase 4 RE-OPENED; 30-iter v1 recipe regressed; cloud rental aborted

**Branch:** `phase-4-selfplay`. Latest commit `2af55be`.

**Headline:** chain-vs-prev ELO climbed +612 over 24 iters, but anchor eval (`iter_24 vs warmstart_canonical`) showed iter_24 = **6W/1D/43L = -330 ELO** in absolute terms. The recipe drove an absolute-strength regression while the chained metric reported steady improvement. Full write-up in DECISIONS.md "2026-05-10 — Chain-vs-prev ELO discredited as standalone metric". 30-iter run was killed at iter 26; cloud rental aborted.

**Active background task (launched 2026-05-10 21:57):**
- Diagnostic anchors: `iter_5/10/15/20 vs warmstart_canonical`, 30 games each at sims=100, 16 workers. Serial loop in `/tmp/diag_anchor_loop.sh`, output `/tmp/diag_anchors.log`.
- iter_5 done: **9W/1D/20L vs warmstart, ELO -134** (regression already in place by iter 5). iter_10/15/20 still running (~45 min remaining).
- Confirms the recipe broke very early (likely as soon as warmstart-mix dropped to 0 at iter 3), not as a late-stage drift.

**Quarantined artifacts (do NOT use as warmstart for any subsequent run):**
- `checkpoints/selfplay/iter_*.pt` (iters 0-25, plus partial iter_26 self-play data)
- `data/selfplay/sanity_30iter/`
- Kept on disk only for the Phase 6 emergence-analysis archive. The 2026-05-03 "Phase 4 PASS" smoke artifacts (`data/selfplay/smoke_v1/`) are similarly quarantined.

**Recipe-fix shortlist (will be sequenced in a future plan-mode session before re-launching Phase 4):**
- Floor warmstart-mix at ≥0.3 throughout (do NOT drop to 0)
- K=10 → K=30 replay-buffer window
- Anchor-gate accept/reject for each iter's checkpoint vs warmstart_canonical (~3 min cost per iter)
- Bump eval games per chained head-to-head 20 → 50

**Production-readiness landed in this session (commits `fe8ede3` + `2af55be`):**
- skip-on-error in `run_selfplay_iter._play_one_pool`: failed games log+drop, no whole-iter abort (engine `farm_util.IndexError` rate ~1/1500 games)
- `--fp16` plumbed through `run_selfplay_iter.py`, `eval_iter_head_to_head.py`, `run_phase4_smoke.py` (default off; expects 1.5-2× forward speedup on Blackwell — fp16 is the right precision; fp4/fp8 require calibration not worth it for our 7M-param net)
- `--no-elo-log` flag for ad-hoc anchor evals (the lifesaver — caught the regression at $0)
- New `scripts/bench_fp16_vs_fp32.py` (numerical agreement + wallclock delta on N mid-game positions; not yet run)
- Updated `scripts/vastai_phase4_runbook.sh` with current 5090 pricing ($0.295/hr min) — held in reserve until Phase 4 recipe fixes land
- **Vast.ai balance: $2.07** — no top-up needed yet; cloud rental gated on Phase 4 v2 sanity passing

**Next steps (after diagnostic completes):**
1. Read iter_10/15/20 anchor curve, confirm regression slope
2. Plan-mode session for Phase 4 v2 recipe (the four fixes above; sequence + verification plan)
3. Re-run 5-iter smoke v2 with fixed recipe, anchor-eval gating from iter 0
4. If smoke v2 anchors POSITIVE vs warmstart, only then consider 200-iter cloud

**Open items deferred:**
- Root-cause the snapshot-mask vs MCTS-mask divergence (defensive clip handles symptom; benign at our scale).
- Larger eval game count per head-to-head (20 → 50+ — folded into recipe-fix shortlist).
- fp16 numerical+wallclock bench (`scripts/bench_fp16_vs_fp32.py`) — run once Phase 4 v2 has a meaningful checkpoint to bench against; meaningless on the quarantined ones.

## Phase 4 archive (2026-04-29 → 2026-05-03)

(See DECISIONS.md "2026-05-03 — Phase 4 smoke PASS" for the full closure entry.)

## Phase 3 archive (2026-04-28 → 2026-04-29)

## Phase 3 attempt history

### v1 (tau=10.0) — 2026-04-28 evening

| Test | Result | Threshold | Pass? |
|---|---|---|---|
| T1 net argmax vs random, n=100 | 84/100 (+19.0) | ≥90% | NO |
| T2 smoke n=2 at s=20/s=20 | 0/2 (-6.5) | smoke | NO |

Diagnosis: policy head couldn't fit near-uniform heuristic targets at tau=10. Train pol CE 1.86 → 1.86 (flat).

### v2 (tau=0.5) — 2026-04-28 night

| Test | Result | Threshold | Pass? |
|---|---|---|---|
| T1 net argmax vs random, n=100 | 88/100 (+32.1) | ≥90% | NO (within statistical noise) |
| T2 partial n=16 at s=50/s=100 | 5/16 (31%, -18.2) | >55% | NO (~97% confidence per Bayesian P(true≥55%)=3.0%) |

Diagnosis: policy now learning (train pol CE 1.79 → 1.26, val 1.79 → 1.66) but the policy is the wrong policy — losing decisively on low-roll-rule games. Either c_puct miscalibration (Plan B step 1) or labels still too noisy (Plan B step 2 = 2-ply).

T2 was killed twice by Mac sleep before nohup workflow rule landed. Per-game checkpoints saved 16/100 for v2 partial — not resumed because n=16 already gives >97% confidence T2 fails.

## v1 acceptance — Phase 3 misses (2026-04-28)

| Test | Result | Threshold | Pass? |
|---|---|---|---|
| T1 net argmax vs random, n=100 | **84/100** (84%, +19.0 avg diff) | ≥90% | NO |
| T2 smoke NeuralMCTS s=20 vs vanilla s=20, n=2 | **0/2** (avg diff -6.5) | (smoke only) | likely NO at scale |

**v1 training metrics (100K positions, tau=10.0):**
- Train value MSE: 0.165 → 0.030 (5.5× reduction — strong)
- Val value MSE: 0.137 → 0.081, best at epoch 14
- Train pol CE: 1.860 → 1.855 (FLAT)
- Val pol CE: 1.879 → 1.879 (FLAT)
- Diagnosis: value head learned, policy head couldn't fit near-uniform targets.

**T2 production cost estimate** that drove the pause: NeuralMCTS s=50 vs vanilla MCTS s=100 = ~28 min/game × 100 games / 2 spawn workers ≈ 24h wallclock. Bottleneck is vanilla side at s=100 (random rollouts, ~300ms each).

### Smoke comparison — COMPLETE (2026-04-28)

| Step | Status | Result |
|---|---|---|
| Heuristic gen (5K positions) | DONE | ~2 min wallclock |
| Heuristic train (4×64, 20 ep) | DONE | val MSE 0.21→0.10; pol CE flat at 1.93 |
| Heuristic tournament (50 games vs random) | DONE | **35/50 (70%)** wins, +3.0 avg diff |
| MCTS s=50 gen (5K positions) | DONE | ~55 min wallclock (Pool x16) |
| MCTS train (4×64, 20 ep) | DONE | val MSE 0.21→0.21; pol CE 1.85→1.90 |
| MCTS tournament (50 games vs random) | DONE | **39/50 (78%)** wins, +7.6 avg diff |
| `compare_warmstart_smoke.py` decision | DONE | **HEURISTIC wins by 24.7x in wins-per-hour-of-gen** |

**DECISION:** Production warm-start uses Option D (heuristic-only, scale to 500K). Logged in DECISIONS.md.

**GATED on 3 prerequisite fixes** before kicking off the 500K production gen:
1. Board encoding richness (meeple side/corner + tile internal topology)
2. Scalar feature normalization
3. Streaming/IterableDataset trainer

These are in BACKLOG and must land before the production warmstart commits compute.

### Active background tasks

- **MCTS s=50 generation:** 500 games × 10 positions/game = 5K labeled positions. 16-worker Pool. **Revised ETA ~2.5 hours total** (steady-state 5 min/game/worker; my earlier 55-min estimate from the 2-game smoke was too low — that test had low SMT contention).
   - Output dir: `data/warmstart/mcts/seed_*.npz`
   - Script: `scripts/generate_warmstart_smoke.py --label-strategy mcts --n 5000`
   - Resumable: skips cached seeds. To wipe: `--reset`.
   - Job died once at 125/500 (cause unknown — possibly SSH disconnect propagating SIGHUP). Resumed cleanly at 148/500. Currently 250-260/500 done (~50% through). ETA ~30 min from now.

### NeuralMCTS + Tournament 2 script (added during the gen wait)

- `src/carcassonne_ai/mcts.py` now has `NeuralMCTS` (PUCT selection, network leaf evaluator). 5 tests pass.
- `scripts/eval_neural_mcts_vs_vanilla.py` runs Phase 3 acceptance Tournament 2 (NeuralMCTS(s=50) vs vanilla MCTS(s=100)). Pattern matches `play_mcts_vs_random.py` checkpointing.

### External review 2026-04-28

Two bugs found and fixed:
- `Game.get_canonical_form` was double-swapping mine/opp when player != current_player. Fixed; new regression test in `tests/test_invariants.py`.
- `warmstart.generate_one_game_dataset` didn't seed the global `random` module before `get_init_board()`. Engine deck shuffle uses global random, so seeds weren't reproducible. Fixed.

Three production-prerequisites flagged for BACKLOG (must land before scaling smoke up):
- Board encoding richness (meeple side/corner; tile internal topology)
- Scalar feature normalization
- Streaming/IterableDataset trainer

Smoke comparison is unaffected — both label strategies share these limitations.

### When both background tasks finish

1. Train MCTS-net on the just-generated 5K MCTS dataset: same params (4×64, 20 epochs). ~5 min.
2. Eval both nets vs random, 50 games each (no MCTS at inference, network argmax-policy):
   - `python -u scripts/eval_warmstart_smoke.py --checkpoint checkpoints/warmstart_heuristic_smoke.best.pt --n 50`
   - `python -u scripts/eval_warmstart_smoke.py --checkpoint checkpoints/warmstart_mcts_smoke.best.pt --n 50`
3. Decision rule: pick winner by **wins per hour of generation cost**. Heuristic gen ≈ 1 min for 5K, MCTS gen ≈ 55 min. So heuristic must produce non-zero useful signal to win; if it lands at 30+/50 wins, it's the right answer (10x cheaper for similar quality).
4. Commit smoke results + decision in DECISIONS.md.
5. Run the full chosen-strategy generation: 500K positions for D (~1.5h) or 50K for C (~9h post-fix from the plan's 26h estimate).

### Files added this session (Phase 3 prep, uncommitted)

- `src/carcassonne_ai/virtual_score.py` — engine-`count_final_scores`-based labeler. 8 tests pass.
- `src/carcassonne_ai/network.py` — 6×96 ResNet with 1×1 conv heads (~7.4M params). 7 tests pass.
- `src/carcassonne_ai/warmstart.py` — dataset IO + heuristic/MCTS labeling.
- `scripts/generate_warmstart_smoke.py` — Pool-parallel labeled-position generation, --reset / --summary-only.
- `scripts/train_warmstart_smoke.py` — supervised training, train/val split by game.
- `scripts/eval_warmstart_smoke.py` — N-game tournament vs random.
- `tests/test_virtual_score.py`, `tests/test_network.py` — coverage.
- DECISIONS.md updated with Phase 3 network-capacity rationale.

All 63 tests pass.

## (Archive) Phase 2 status (now historical)

**Branch:** `phase-2-mcts` (all Phase 0 + 1 + 2 commits stacked here; not yet merged to `main`)

**Latest commits:**
1. `508c1c1` mcts: best_action picks by Q, not N (fixes near-random play at low s)
2. `dd88386` add per-game checkpointing + resume to play_mcts_vs_random
3. `d236477` docs: handoff scaffolding (CLAUDE.md, STATUS.md, ORIGINAL_PROMPT.md)
4. `534043a` phase 2: vanilla MCTS with state-mutation rollout optimization
5. `9c05fd3` chore: disable noisy markdownlint rules in this repo
6. `bfab407` patch engine: open_positions adjacency tracking for fast legal-move queries
7. `d1e80fd` phase 1: AlphaZero-style game wrapper

**Known issue caught and fixed:** Initial `best_action` picked the most-visited child. At s=10 with ~50 root actions, most children have N=1, so the choice was effectively arbitrary — empirically MCTS won only ~47% vs random. Fixed by picking by Q-value (mean rollout reward); falls back to N for ties. Tournament re-running with `--reset` to confirm.

**Active background task:** MCTS(s=10) vs random tournament, 100 games, 16 parallel Pool workers (restarted ~09:55 with `python -u` + per-game checkpointing).
- Launched: 2026-04-28 ~09:55 local (after a non-checkpointed run was killed at 32 min for opacity)
- Expected wall-clock: ~30 min total
- Acceptance criterion: MCTS wins ≥95/100 games
- **Resumable:** results stream to `data/tournament/s0010_seed*_p*.json` as each game completes. If killed mid-run for any reason (laptop sleep, manual stop, optimization swap), rerun the SAME command to pick up where it stopped:

  ```bash
  python -u scripts/play_mcts_vs_random.py --n 100 --sims 10
  ```

  To inspect progress without running:
  ```bash
  ls data/tournament/ | wc -l                # files = games done
  python scripts/play_mcts_vs_random.py --summary-only --n 100 --sims 10
  ```

  To restart from scratch, add `--reset`.

## When the tournament finishes (Joshua away ~60 min from 2026-04-28 ~10:30)

Joshua left during the run. I will:

1. Read the final result, write a summary at the bottom of this file under "Tournament outcome".
2. **Wait for Joshua's decision** on whether to accept the result or rerun at higher s. Won't autonomously launch a rerun.
3. Idle until Joshua returns or instructs further. The harness's hooks will keep firing during my idle but I'll have genuinely nothing actionable to do until you're back.

When you return, the decisions waiting for you are:

- **If MCTS wins ≥95/100:** Phase 2 acceptance met. Commit the tournament results, update DECISIONS.md, and decide whether to start Phase 3 plan-mode or pause for review.
- **If MCTS wins 80-94/100:** strong but below target. Either (a) accept (MCTS is verifiably real; the 95% target was based on Ameneyro's s=100, not s=10), or (b) rerun at `--sims 20` (~50 min wallclock) for a more decisive number. My weak preference is (a) — the bot's job in Phase 2 is to be a sparring partner, not optimal play. Phase 3+ replaces it.
- **If MCTS wins <80/100:** something else is wrong (not just budget). Investigate before proceeding to Phase 3.

In any case: the per-game results in `data/tournament/` are durable; subsequent runs (different `--sims` values) write to non-conflicting filenames, so there's no need to wipe.

**Phase 3** is the next big chunk: network architecture (10-15 ResNet blocks, 128 filters), warm-start labeled-position generation (~500K positions), supervised pre-training. Acceptance: warm-started network beats random 90%+ standalone, network+MCTS(s=50) beats vanilla MCTS(s=100) at >55%. Plan-mode session recommended before any code.

## Tournament outcome

**Phase 2 PASS** — MCTS(s=20) vs random, 100 games, 16 parallel workers:

| Metric | Value |
|---|---|
| MCTS wins | **96 / 100 (96.0%)** |
| Draws | 0 |
| MCTS losses | 4 |
| Avg score diff (MCTS − random) | +30.9 |
| Avg moves/game | 166 |
| Avg wall-clock/game | 11m16s |

Acceptance criterion (≥95%) met. Per-game JSON results in `data/tournament/s0020_seed*_p*.json`.

Phase 2 finalization commit: `508c1c1` (Q-tiebreak fix is the load-bearing change). Tournament data not committed (gitignored under `data/`); reproducible via `python scripts/play_mcts_vs_random.py --n 100 --sims 20`.

Next: Phase 3 (network + warm start) — see plan file `~/.claude/plans/new-project-in-this-spicy-finch.md`.

## Pending non-blocking items

- BACKLOG entry: in-place state mutation for MCTS rollouts (DONE — applied during Phase 2; remove from BACKLOG)
- BACKLOG entry: GPU forward batching for Phase 4 — virtual-loss MCTS pattern. Mandatory for Phase 4 wallclock budget.
- BACKLOG entry: Phase 3 prerequisite: implement `virtual_score_estimate` (currently a NotImplementedError stub in mcts.py)
- BACKLOG entry: cloud rental ($30-200) for Phase 4 long runs once local smoke-test confirms loop is healthy

## Hooks active in this environment

- `~/.claude/hooks/idle_check_with_bg_tasks.sh` — Stop hook. Detects active bg tasks via fuser; if elapsed >5min, instructs Claude to actively check status (`ps`, tail output) instead of just "find adjacent work". Settings registered in `~/.claude/settings.json`.

## Key contact files for a fresh thread

1. [CLAUDE.md](CLAUDE.md) — project goal, scope, operating norms
2. [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md) — verbatim spec
3. [DECISIONS.md](DECISIONS.md) — what we decided and why; supersedes any specific number in the original prompt
4. This file (STATUS.md) — what's running, what's next

## Outstanding questions for Joshua

- Whether to merge `phase-2-mcts` → `main` once acceptance is met, or keep all phase branches separate. Default per Joshua's earlier instruction: keep branches separate.
- Whether to start Phase 3 immediately after Phase 2 commit, or pause for review. Default: pause for review.
