# STATUS — live state of in-flight work

> Update this file whenever the active branch, running task, or immediate next step changes. A new Claude thread reading [CLAUDE.md](CLAUDE.md) → here should be able to take over without missing a beat. Keep this file SHORT — current state only. Historical narrative lives in [DECISIONS.md](DECISIONS.md).

## Right now (2026-05-24, 11:25) — **Option B chain DEAD (broken from step 1). Pivoted to loop's deepsearch train+anchor (running). Next: anchor-fraction self-play for the deepsearch lever.**

**Phase 1 chain ran B2→B4 then killed.** Maximalist completed Phase 1 chain steps 2, 3, 4 (each n=2000 vs previous chain ckpt). Chain elo deltas looked OK (+11.4 / +2.4 / +1.4) so chain kept going. **But the chain-vs-prev measurements were lying.** Direct n=400 anchors against iter_01 told the real story:

### Phase 1 verdict table (the misleading chain math)
| step | result vs prev | elo Δ (chain) | direct vs iter_01 (n=400) | reading |
|---|---|---|---|---|
| B1 (iter_B1) | — | — | **+25.2** (2026-05-20) | still global best at sims=200 |
| B2 vs B1 | 1014W / 949L / 23D | +11.4 | **−6.1** (193W/200L/7D) | null vs iter_01 — chain broken from step 1 |
| B3 vs B2 | 994 / 980 / 26 | +2.4 | not measured | (no point — already drifting) |
| B4 vs B3 | 995 / 987 / 18 | +1.4 | **−19.1** (186W/208L/6D) | clear regression |
| B5 vs B4 | killed at 248/2000 | aborted | n/a | sequencer killed during this |

**Conclusion: Option B chain doesn't even gain in step 1.** B1's +25 elo cushion was already half-eroded by B2 (−6 vs iter_01); by B4 the chain was 44 elo below B1. Anchor-fraction self-play (the canonical cure for chain drift) wouldn't help an Option B chain because the recipe doesn't gain even with a perfect anchor — it can only hold the line at iter_B1's strength. **Option B as a chain lever is dead.**

**Maximalist + watchdog + health_log KILLED 2026-05-24 ~07:55** (Joshua's call). B5 self-play / B5 vs B4 eval discarded mid-flight (would have wasted ~55h more compute on the dead chain).

**Current global best (unchanged):**
- sims=200 plane: `checkpoints/v25_retrain_optionB_iter1/iter_00.pt` (iter_B1, +25.2 over iter_01)
- sims=800 plane: `checkpoints/v25_retrain_deepsearch/iter_00.pt` (+35.8 over iter_01)

**Currently running: loop's orphaned deepsearch train+anchor** (PID 5369, `/home/doctor/loop_deepsearch_train_anchor.sh`, `nice -n 19`, logs `/tmp/loop_deepsearch_run.log`, sentinel `/tmp/loop_deepsearch_run.DONE`). Uses the 2026-05-18→21 work-stealing deepsearch data (`/mnt/c/carc-shared/deepsearch/iter_00/`, 1200 games sims=800 warm-from iter_01) to train a new ckpt at `checkpoints/v25_retrain_deepsearch_v2/iter_00.pt`, then anchor-gate n=100 sims=200 vs iter_01. Started 11:23, ETA ~35 min. **This was orphaned by the maximalist (Phase 3 used a different warm-from path); finally getting its verdict.**

### Next pivot (after deepsearch_v2 verdict)
1. **Implement anchor-fraction self-play** (~5h, ~190 LoC). Design fully scoped (see DECISIONS.md 2026-05-24). Static anchor = iter_B1 OR deepsearch (depending on which plane we're improving), fraction=0.3, alternating sides. Scope it to the **deepsearch lever** — sims=800 chain is where the actual strength gains live (confirmed +35 elo at sims=800 plane). Option B chain doesn't need it (the recipe itself is dead).
2. **Parallel: run Phase 2 + Phase 4 + Phase 5-smoke** (~37h total, GPU-parallel'able). All unaffected by chain drift; tune hyperparameters/leaf-evals against iter_B1.
3. **Then: anchor-fraction'd deepsearch chain** (Phase 3 equivalent, ~32h per step).

### Lessons memorialized
- [feedback_no_sigstop_mp_queue](../.claude/projects/-home-doctor-projects-carcassone/memory/feedback_no_sigstop_mp_queue.md) — SIGSTOP on mp.Queue processes breaks them
- [feedback_xeon_ssh_quoting](../.claude/projects/-home-doctor-projects-carcassone/memory/feedback_xeon_ssh_quoting.md) — don't wrap wsl invocation in outer quotes when ssh'ing Xeon
- [feedback_anchor_before_scaling](../.claude/projects/-home-doctor-projects-carcassone/memory/feedback_anchor_before_scaling.md) — already existed; this week's failure was the textbook case (maximalist Phase 1 had only chain anchors, no global anchor — direct anchor would have caught the drift at B2 instead of B4)
- **Next lever after B2 verdict:** likely Phase 3 (deepsearch DS_02) or the orphaned loop deepsearch train+anchor (data already collected at `/mnt/c/carc-shared/deepsearch/iter_00/`).

### Lessons memorialized today
- [feedback_no_sigstop_mp_queue](../.claude/projects/.../memory/feedback_no_sigstop_mp_queue.md) — SIGSTOP on mp.Queue processes breaks them
- [feedback_xeon_ssh_quoting](../.claude/projects/.../memory/feedback_xeon_ssh_quoting.md) — don't wrap wsl invocation in outer quotes when ssh'ing Xeon

**Zenbook called dead-end for now** (2026-05-21 — Joshua's call). Bridge infrastructure stays in tree as committed code (see "Bridge code" below) for future deploy. Sequencer v3 (`/home/doctor/maximalist_sequencer_v3.sh`) sits ready but is NOT in use.

**Loop's deepsearch train+anchor — STILL ORPHANED.** Data ready at `/mnt/c/carc-shared/deepsearch/iter_00/` (1200 games sims=800, warm-from iter_01). Now that the maximalist is killed and 5800X GPU will be free after the B2 anchor, this is a candidate for the next experiment. ~5 min train + ~30 min anchor n=100 sims=200.

**Bridge code (committed, unchanged):** `src/carcassonne_ai/remote_eval_bridge.py` (TCP listener + bridge thread, length-prefixed `np.save(allow_pickle=False)` wire format) + `src/carcassonne_ai/remote_socket_handles.py` (drop-in socket-backed ServerHandles) + `scripts/run_selfplay_iter.py` `--serve-on`/`--remote-eval-server`/`--serve-slots` flags + 9 unit tests (pass on 5800X **and** Zenbook). Loopback smoke: 12932 evals, 0 failures. The earlier "W=10 production" recommendation came from a STUB-eval bench — the only real-GPU bench attempt (today) was junk; no validated production W yet.

---

## Recent (2026-05-20, 16:10) — **retroactive-validation pipeline COMPLETE; 2 of 4 false-negatives recovered.**

Final verdicts (all jobs n=400 at the named sims; full table + decision context in [DECISIONS.md](DECISIONS.md) 2026-05-20 (results)):

| job | n | result | elo Δ | σ vs 50% | verdict |
|---|---|---|---|---|---|
| deepsearch vs iter_01 @ sims=800 | 380 | 208W/169L/3D | **+35.8** | 2.0σ | **recovered FN** (suspected → confirmed) |
| iter_02 vs iter_01 @ sims=200 | 400 | 193W/198L/9D | **−4.3** | 0.25σ below 0 | genuine null |
| iter_B1 vs iter_01 @ sims=200 | 400 | 213W/184L/3D | **+25.2** | 1.5σ | **🎯 NEW recovered FN** |
| iter_01 c=2.0 NEW vs c=1.5 OLD @ sims=200 | 400 | 200W/194L/6D | **+5.2** | 0.3σ | genuine null |

**Global-best updated:**
- **sims=200-plane play** → `checkpoints/v25_retrain_optionB_iter1/iter_00.pt` (iter_B1) replaces iter_01. +25.2 elo, 1.5σ at n=400.
- **sims=800-plane play** → `checkpoints/v25_retrain_deepsearch/iter_00.pt` (deepsearch) replaces iter_01 at that plane. +35.8 elo, 2.0σ at n=380. Pair with the +200 elo sims=200→800 play-time win (sims-ladder, 2026-05-18) for the strongest play config.

**Plateau retraction:** the 2026-05-19 entry's "plain v2.7 plateau across all three strategies" overreached. Only iter_02 (the plain W/L-target recipe) really plateaued. Option B (`score_diff` value targets) gave +25 elo — it is **not** plateaued; chaining Option B forward (iter_B2, iter_B3, ...) is the highest-EV next move.

**Next (queued, multi-day autonomous pipeline while Joshua is away — to be wired):** chain Option B → iter_B2/B3/B4 (each ~9h: self-play + train + n=400 anchor-gate vs iter_B(n-1)); wider c_puct sweep at sims=200 (c=0.5, c=3.0, c=5.0 each n=400 vs iter_B1); cap=20 and cap=∞ smokes. Plan + sequencer to be wired before Joshua's away days.

**Code-review loop — DONE 2026-05-19:** a 4-iteration multi-agent review of all living code applied **14 safe fixes** and logged **16 deferred findings** with rationale → [REVIEW_LOG.md](REVIEW_LOG.md). Action-needed deferrals are parked in [BACKLOG.md](BACKLOG.md): D1/D13 (encoding — next retrain), D16 (leaf-eval — next cap re-sweep), D9 (claim cleanup — before next multi-iter run), D15 (stale-recovery race — accept+document). The running self-play workers are unaffected — edits apply on next launch.

**deepsearch iter — RUNNING on work-stealing (migrated 2026-05-18 from the fixed split):**
- The strength-lever call: deeper-search self-play — retrain with sims=800 self-play (stronger teacher; may un-stick the policy plateau the sims-ladder reframed as a *training*-recipe saturation, not a net+leaf ceiling).
- 1200 games, sims=800, leaf v2_5, orchestrator, batch_size=8, value-target score_diff, warm-from `checkpoints/v25_retrain_iter01/iter_00.pt`.
- **Work-stealing, not a fixed split:** both boxes run the SAME command (`--shared-claim --seed-start 0 --games 1200`) against ONE shared folder; each worker atomically claims (`O_CREAT|O_EXCL` on a `seed_NNNNNN.claim` sidecar) the next unplayed seed. Auto load-balances (faster box does more, no idle-at-end) and every `.npz` lands in one durable place the instant it's produced. 5800X W=14, Xeon W=10.
- **Shared folder** = an SMB share on the 5800X's Windows side (`C:\carc-shared`). 5800X reaches it via drvfs `/mnt/c/carc-shared/deepsearch` (WSL2 NAT can't loopback-mount its own host's share). Xeon reaches the SAME folder via CIFS `/mnt/carc-shared/deepsearch` (`//192.168.0.195/carc-shared`, vers=3.1.1, nobrl, creds `/home/doctor/.carc-smb.creds`).
- **sims=800 per-game cost = 4.81× sims=200** (pre-flight smoke: first game 1478s vs sims=200's 307s) — superlinear; the bigger MCTS tree adds ~20% over a naive 4×.
- **Migration (2026-05-18):** the run started as a fixed seed-split (5800X 0-759, Xeon 760-1199); after work-stealing was built + verified, the in-flight run was migrated — 336 done games consolidated into the shared folder, both boxes relaunched with `--shared-claim`. No recomputation (`path.exists()` fast-path skips done seeds). Verified live: 24 claim files on disk, 14 `5800X` + 10 `xeon`.
- **Xeon launch + detachment:** `/home/doctor/launch_xeon_ws.sh` (on the Xeon) remounts the CIFS share (WSL drops non-fstab mounts on distro teardown) then execs the run — invoked by path over `nohup ssh xeon 'wsl … bash launch_xeon_ws.sh'` on the 5800X (held-open ssh keeps the Xeon's WSL session alive for the run; survives Mac sleep). Relaunch = re-run that ssh; the launcher self-heals the mount, cached seeds skip.
- Logs (both local to the 5800X): 5800X `/tmp/deepsearch_ws_5800x.log`, Xeon `/tmp/deepsearch_ws_xeon.log`. Persistent monitor armed.
- **At completion:** all 1200 `seed_*.npz` are already in `/mnt/c/carc-shared/deepsearch/iter_00/` (no rsync) → `train_iter.py` (warm-from iter_01, warmstart-mix 0.0, 3 epochs — mirrors iter_01/iter_B1) → anchor-gate n=100 @ sims=200 vs iter_01 (`eval_iter_head_to_head.py`). Verdict: did the deeper-search teacher beat iter_01 at equal production search depth.
- **Work-stealing code (committed `1895b02`, branch `gpu-orchestrator`):** `run_selfplay_iter.py` (`--shared-claim`/`--claim-stale-secs`/`--claim-host` + `--seed-start` + claim primitive + gate), `warmstart.py` (per-writer-unique temp filename), new `tests/test_selfplay_claim.py` (8 tests, pass) + `scripts/verify_shared_claim.py` (two-box O_EXCL deploy-gate). Code-reviewed — 3 fixes applied (CIFS-`os.close()`-EIO crash guard, staged-file unlink log, cross-machine temp filename). O_EXCL deploy-gate PASSED on the real drvfs+CIFS mount (701/299 split, all 1000 seeds won exactly once).

**iter_B1 — Option 2 Phase B stage 1 — DONE 2026-05-18 00:29 (533.9 min):**
- 1200-game v2.7 self-play from iter_01 + train + anchor-gate. Checkpoint: `checkpoints/v25_retrain_optionB_iter1/iter_00.pt`. Self-play value targets are `score_diff` (`tanh(margin/15)`), not W/L — the deliverable for the iter_B2 blend.
- **Anchor-gate vs iter_01: 14W/0D/6L, wr=0.70, avg diff +12.6 — PASS.** STATUS expected iter_B1 ≈ iter_02 (flat); it *gained* over iter_01 instead. But n=20 is noisy — treat as "promising, wants n=100 to confirm" before calling it a new global best.
- log `/tmp/optionB_iter1.log`.

**Overnight chain — RESULT (2026-05-18 00:53):** orchestrator ran iter_B1 → n=50 re-smoke → **POORLY**, stopped. **No iter_B2 launched.**
- Re-smoke (iter_B1 blended-leaf λ=0.5 vs plain leaf, n=50): **−15.5 avg diff, 31% wr (15W/1D/34L)** — worse than Phase A's W/L blend (−11.3/46%). **Option 2 (NN value-head blend) is dead** — the score-diff currency fix did not rescue it; the currency hypothesis is refuted.
- Residual diagnostic (`/tmp/residual_structure.log`): NN value head corr **+0.18** with the outcome vs the heuristic's **+0.61**, beaten by the heuristic in every game phase; best static blend cuts prediction MSE only 4% (in-sample-optimised → inflated). The script auto-verdict said "headroom" but that threshold is miscalibrated — honest read: **value-head injection (blend AND residual) is exhausted.** Don't spend 10h on residual.
- **iter_B1 strength — n=20 anchor (70%/+12.6) was a fluke.** n=100 confirm: **49W/0D/51L, +4.6 avg diff, elo −6.9** — iter_B1 ≈ iter_01, no new global best. The plain v2.7 recipe is **plateaued** (iter_00→01 +13.3, 01→02 +0.2, 01→B1 +4.6/49%).
- **Pivot (Branch B) — sims-depth A/B DONE 2026-05-18 ~10:30.** iter_01 @ sims=800 vs iter_01 @ sims=200, same checkpoint both sides (only search depth varies), n=50, plain v2.7 leaf: **38W/0D/12L = 76% wr, +24.9 avg diff, +200 elo.** Decisive (3.7σ) — **the policy is significantly under-searched at the production sims=200; deeper search is a large, under-exploited lever.** Reframes the "plateau": the v2.7 leaf is *not* a hard wall — iter_01→02→B1 flattening was the *training* recipe saturating, not the ceiling of what net+leaf can do with more search at play time. Log `/tmp/sims_ab_800v200.log`. Code: `eval_iter_head_to_head.py` gained an `--old-sims` flag, committed d613e13.
- **Sims ladder — COMPLETE 2026-05-18.** 3 rungs, all n=50, iter_01 both sides: 800 v 200 = **76%**; 800 v 400 = **62%/+10.8/+85 elo**; 1600 v 800 = **52%/+3.1/+14 elo**. **Knee at 800, confirmed both sides** — 400 is not enough (800 wins 62%), 1600 buys nothing over 800. 200→800 ≈ +200 elo. Logs `/tmp/sims_ab_{800v200,800v400,1600v800}.log`.
- **Free win available:** set production/play inference sims 200→800 (~+200 elo, no retrain, ~4× per-move latency — fine for human-paced play). Search is now a closed lever.
- **Next strength lever — Joshua's call (nothing auto-started):** (a) deeper-search self-play — retrain with sims=800 self-play (stronger teacher, may un-stick the policy plateau). Cost confirmed ~4× per-iter compute — 400 was tested, not enough, no 2× shortcut. ~1.5-2 day local on the 5800X; the Xeon (Quadro RTX 4000, WSL CUDA OK) could add ~1.4-1.6× throughput via a seed-range split once deployed. (b) leaf-eval redesign — the v2.7 heuristic is the other ceiling; bigger project.
- **Still open:** human benchmark (the documented superhuman blocker) — deferred until Joshua can play. Other harder levers: heuristic-leaf redesign, net capacity — see EXPERIMENTS.md.
- Artefacts (one-off, in `/tmp`): `optionB_overnight.sh`, `optionB_iter1_resmoke*.sh`, `residual_structure.py`, logs. Not committed.

**Option 2 (NN value-head blend) — why a 2-stage Phase B:** Phase A wired the leaf↔value-head blend — `LeafConfig.value_blend`, the evaluators, the eval_server `compute_value` path, `--value-target score_diff` (committed eb42c25). The λ=0.5 fixed-checkpoint smoke blended iter_01's *W/L*-trained value head and was mildly harmful (46% wr, −11.3 avg diff) — a currency mismatch with the graded score-diff leaf. So Phase B splits: iter_B1 mints a score-diff value head; iter_B2 is the real blended co-improvement test.

**Self-play perf optimization — parked (full rationale: DECISIONS.md 2026-05-17):**
- **Shipped** (`gpu-orchestrator`, 080fea7): hash-cache the engine value objects + precompute `FarmerSide.get_side` → ~20-24% faster leaf eval (cProfile). Live in iter_B1.
- **Option A** (memoize the find_* flood-fills) and **Option B** (incremental union-find) both **parked**. `find_farm` — the #1 hot path, ~58% of leaf cost — is start-dependent in the vendored engine and can't be safely cached or union-found. The find_city+find_road half (Option A) is verified-correct on branch `leaf-memoization` (3db30f1, unmerged) but only ~6% — not worth merge-risk attention.

**Production config:** v2.7 leaf (`CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12`) + c_puct=1.5 + sims=200, W=14 on the 5800X.

## Active branch

`gpu-orchestrator` — ahead of `origin/gpu-orchestrator` by 8. The v2.7-leaf retrain line + GPU orchestrator + Option-2 blend wiring live here. Single worktree (`carcassone`) — side worktrees removed 2026-05-18. Two unmerged side branches (no worktrees, reachable from the main repo): `leaf-memoization` (3db30f1 — parked find_city/road memo, ~6%, not worth merge-risk) and `play-vs-mcts` (04e4330 — stale human-vs-AI play UI, 93 commits behind, needs a forward-port before it runs). No merge to `phase-4-selfplay`/`main` pending.

## Second machine (Xeon) — deployed 2026-05-18

Xeon W-2135 (192.168.0.110, `ssh xeon` → WSL Ubuntu-24.04). Repo rsync'd, venv built (torch 2.11.0+cu128, CUDA OK on the Quadro RTX 4000). **Deployed + benched 2026-05-18 — ready to take a self-play shard.** Worker bench: engine-sim peak W≈10. Self-play smoke DONE — path validated end-to-end (orchestrator + Quadro eval-server + v2.7 leaf, 28 games across both boxes, 0 failures). Self-play throughput **~0.6× the 5800X** (single sims=200 game: 5800X ~307s, Xeon ~375s; optimal W=10 vs 14) → **combined ~1.6×**. GPU not the bottleneck on either box (eval-server 70%+ idle). **WSL gotcha:** detached processes die when the ssh/wsl session closes — hold the ssh session open for the run, or use `systemd-run` for a multi-day run. Full Xeon details in CLAUDE.md.

## Cloud note

vast.ai's docker-pull infra failed across 7 boxes on 2026-05-15 (all images, all regions, "Verifying Checksum" stalls) — iter_01/iter_02 ran locally instead ($0). If cloud is needed again, evaluate **RunPod Secure Cloud** (pre-cached templates sidestep the cold-pull stall). cloud helper scripts: `scripts/cloud_bootstrap.sh`, `cloud_pull_destroy.sh`, `cloud_retrain_watchdog.sh`.

## Recent history (full detail in DECISIONS.md)

- **2026-05-14** — diagnosed v1-v6 failure: the NN value head was the broken leaf eval. Pivoted to hand-crafted `virtual_score` leaf (v1 → v2 → v2.5).
- **2026-05-15** — v2.5 dedup bug fix + cap/P re-sweep → v2.7 (`cap=12`, drop-3-open); cloud-retrained iter_00 (+21pp over warmstart). v3 leaf cap tuning = n=20 noise (v2.7 holds). PUCT c sweep: low c catastrophic, c=1.5 default holds. W-bench: W=14 optimum for v2.7 recipe.
- **2026-05-16** — iter_01 retrain confirmed (+13.3, new global best). Strategy lit-review parked in BACKLOG. Docs hygiene + checkpoint cleanup (v1-v6 checkpoints removed, 2.7G→563M; `iter_12.pt` kept as `checkpoints/v6_iter12.pt`).
- **2026-05-17** — iter_02 flattened (+0.2 — policy saturated against the fixed leaf). Closure-P leaf refinement = null (pooled 47.5%, n=200) → pivot to Option 2 (NN value-head blend). Phase A wired (eb42c25); W/L-blend smoke mildly harmful → 2-stage Phase B, iter_B1 launched. Self-play hot path profiled + optimized (hash-cache + get_side, ~20-24%, 080fea7); deeper memoization (Options A/B) parked — find_farm is start-dependent.
- **2026-05-19 → 2026-05-20 (overnight)** — 4-iter multi-agent review → 14 fixes (F1–F14) + 16 deferred; see [REVIEW_LOG.md](REVIEW_LOG.md) / [BACKLOG.md](BACKLOG.md). **Deepsearch retrain anchor-gate**: sims=200 plane FAILED (45W/0D/55L, −34.9 elo), sims=800 matched plane AMBIGUOUS (52W/1D/47L, +17.4 elo, 0.5σ — clean sign flip from the sims=200 reading). Triggered a meta-audit: realized matched-strength comparisons at n=100 have ~50-60% power against +30 elo edges → project has been systematically false-negative-prone. **Wired up 4-job autonomous re-test sequencer** (deepsearch n=400 sims=800, iter_02 n=400 sims=200, iter_B1 n=400 sims=200, PUCT c=2.0-vs-c=1.5 n=400 sims=200), running overnight. **Infra extracted in the process:** new `src/carcassonne_ai/claim.py` shared module (refactored out of `run_selfplay_iter.py`); `eval_iter_head_to_head.py` gained `--shared-claim`/`--claim-stale-secs`/`--claim-host` (work-stealing + crash-tolerance for evals) and `--new-c-puct`/`--old-c-puct` (per-side PUCT for A/B testing exploration constants with the same checkpoint both sides). 12 tests green; backwards-compat preserved for all existing call sites.
- **2026-05-20 (results)** — pipeline COMPLETE. **2 of 4 false-negatives recovered:** deepsearch confirmed at +35.8 elo / 2σ (sims=800 plane); iter_B1 newly recovered at +25.2 elo / 1.5σ (sims=200 plane). iter_02 (−4.3 elo) and PUCT c=2.0 (+5.2 elo) confirmed genuine nulls. **iter_B1 is the new sims=200-plane global-best**, replacing iter_01. The "plain v2.7 plateau across all strategies" claim is retracted — only the W/L-target recipe (iter_02) plateaued; the score-diff-target recipe (Option B) is a +25 elo lever not yet chained. Highest-EV next move: chain Option B → B2/B3/B4. Full table + audit of remaining false-negative reservoirs in [DECISIONS.md](DECISIONS.md) 2026-05-20 (results).

## Key contact files for a fresh thread

1. [CLAUDE.md](CLAUDE.md) — project goal, scope, operating norms
2. [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md) — verbatim spec
3. [DECISIONS.md](DECISIONS.md) — every non-trivial decision + why; supersedes the original prompt
4. [EXPERIMENTS.md](EXPERIMENTS.md) — open ablation roadmap + findings ledger
5. [BACKLOG.md](BACKLOG.md) — deferred ideas (don't action without Joshua's OK)
6. This file (STATUS.md) — what's running, what's next

## Hooks active in this environment

- `~/.claude/hooks/idle_check_with_bg_tasks.sh` — Stop hook. Detects active bg tasks; if elapsed >5min, instructs Claude to actively check status (`ps`, tail output) rather than idle. Registered in `~/.claude/settings.json`.
