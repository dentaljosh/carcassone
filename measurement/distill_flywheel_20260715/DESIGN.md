# Distill + Guarded Flywheel — 12-iter GEN+TRAIN design (2026-07-15)

**STATUS: DESIGN — approved-pending-Joshua-review, NOT launched. No implementation exists yet.**

Owner ask (verbatim): *"design a flywheel with our champion. no eval yet. just rounds of gen and train... local and laptop. rust orchestrator. pay attention to optimal worker counts. we want a strong distillation of our champ. and also to see if the flywheel produces stronger nets. but we will eval after 12 iters."*

This doc is the build spec for an Opus coder. It contains NO implementation; it names exact files, flags, and worker counts. Eval after iter 12 is a **separate task, not designed here**.

---

## 1. Summary — the chosen design

**Two-stage, 12-iteration GEN+TRAIN loop ("distill, then guarded flywheel"):** iters 0–3 are pure champion distillation — both boxes run the classical champion (`HeuristicPriorAgent`, clairvoyant, full production strength: sims=2750, c_puct=1.5, curve125 leaf) as a net-free CPU self-play emitter that records root-visit-distribution policy targets + outcome value targets (`tanh((p0−p1)/15)`, mover-POV). Iters 4–11 switch the local box to an AZ flywheel stage — NeuralMCTS gen with **net priors + the frozen champion heuristic leaf as the ONLY value source** (`--leaf-eval v2_5`, blend/resid 0 → policy-only net path) through **carc-orch** at W28, while the laptop keeps streaming full-strength champion games (150/iter, 25% of the mix) into every iter. Training accumulates ALL iters (`--window 12`), warm-chained from `checkpoints/warmstart_canonical.pt`. This serves both goals: goal 1 (strong distillation) gets 3,600 full-strength champion games (50% of the final window) plus a fixed frozen probe set that measures distillation fidelity every iter for free; goal 2 (does the flywheel self-improve?) gets 8 iters of genuine prior-improvement flywheel (visits→policy→priors→visits) whose value feedback loop is structurally severed — the learned value head never steers search, so the classic silent value-collapse regression is impossible by construction. Ends at iter 12 with 12 checkpoints + per-iter diagnostics; zero in-loop game evals. **ETA ≈ 28–34 h two-box wall** (stage 1 ≈ 12–15 h, stage 2 ≈ 16–18 h).

---

## 2. Key decisions

### D1 — Structure: seeded distillation → guarded flywheel (hybrid B), with a severed value loop

Pure distillation (A) can't answer goal 2 and leaves the orchestrator unused against Joshua's explicit "rust orchestrator"; pure AZ-from-net0 (C) risks 12 silently-burned iters with no eval to catch a regression. The hybrid gets 4 iters of clean distillation (net provably approaches a fixed teacher — monotone, regression-free) then 8 flywheel iters, and it de-risks the no-eval window three ways that cost nothing: **(i) value floor** — flywheel gen runs `--leaf-eval v2_5` with blend=0/resid=0, so search VALUE is always the frozen champion curve125 leaf and the net contributes priors only; the only learned feedback path is policy→priors, which search itself regularizes (a bad prior still gets 400 sims of heuristic-valued lookahead, and the recorded target is the post-search visit distribution, not the raw prior); **(ii) permanent champion anchor** — the laptop streams 150 full-strength champion games into every flywheel iter and the window accumulates everything, so champion data is ≥50% of every training set and the policy can never drift unboundedly from the teacher; **(iii) a frozen probe set** (§6) that measures distillation fidelity (policy CE vs the champion's visit distribution) every iter as a pure forward pass — no games played, so it does not violate "no eval."

### D2 — Teacher: CLAIRVOYANT champion

Clairvoyant is the champion of record (`puct_priors_v29_bmild_cap8`, PRODUCTION.yaml), is ~4× cheaper per game than the fair PIMC sibling (k_dets=4×688), and is strictly stronger — distilling the fair sibling caps the student lower for more money. The net's inputs contain **no deck-order/future-draw information** (verified: `features.py` scalars + `board_repr` are public-info only; clairvoyance lives in the search stepping the true deck, not the encoding), so the student learns the deck-*marginalized* oracle policy — the known residual risk is strategy-fusion bias in late-game meeple decisions (teacher "knows" the draws), which the iter-12 fair-mode eval will price; we accept it rather than pay 4× for a weaker teacher. Note the existing NeuralMCTS self-play path is clairvoyant-search anyway, so stage 2 is consistent with stage 1.

### D3 — Data window: accumulate-all (`--window 12`)

Champion data never goes stale (fixed teacher), so evicting it only weakens the distillation and removes the anti-drift anchor; sliding-window is the right call only when old data comes from a superseded policy, which describes at most the net-gen half of our data. Volume is affordable: ~144 policy rows/game (no interior harvesting under `score_diff` — that's a residual-mode feature) → ~1.04M rows at iter 11 → ~40 min train at 0.196 s/batch. Window 12 = accumulate everything.

### D4 — Per-iter config (sims, games, targets, net, warm-from)

- **Champion stream sims = 2750** (the full production config; C6_COST_SURFACE: 2986 ms/move median, reuse OFF — exactly our emitter's mode). "Strong distillation of our champ" means distilling *the champion*, not an h800-class shadow; at ~430 s/game it's affordable (~12–15 h for 2,400 stage-1 games two-box). Cheaper sims would trade teacher strength for game count with no evidence we're game-starved.
- **Flywheel stream sims = 400** (2× rod_v2's 200): net-gen is cheap under orch (~5.2 s/game effective at sims 200, W28 local), and the improvement-operator quality (visits vs priors) scales with sims; 450 games ≈ 80 min local — the laptop's champion quota paces the iter anyway, so the 2× is nearly free wall-clock.
- **Games = 600/iter uniform** (stage 1: 600 champ shared two-box; stage 2: 450 net local + 150 champ laptop = 25% champion mix).
- **Value target = `--value-target score_diff`** (existing: `tanh((p0−p1)/15)` backfilled, mover-POV) for BOTH streams — matches the champion's value_norm=15, gives an absolute value head (usable as future analyzer/flywheel substrate, unlike the residual-era heads), and makes `value_outcome_corr` a meaningful cross-iter diagnostic.
- **Net = existing 96×6 (7M)**. Arch isn't CLI-configurable (it's inherited from `--warm-from`), the capacity probe never produced a clean bigger-net verdict (f128b6 OOM-crashed WSL 3×; "scale weakly-dead" per DECISIONS 2026-07-05), and a bigger net taxes both orch gen throughput and the iter-12 deployment story. Don't spend a new-code + risk budget on an unevidenced axis.
- **Warm-from iter 0 = `checkpoints/warmstart_canonical.pt`; iter N>0 warm-from iter N−1.** Clean provenance for the distillation claim (no residual-era value-head semantics to unlearn — the rod/flywheel lineage heads predict residuals, not absolute values), correct arch (96×6). Smoke must verify it loads in train_iter, its scalar width matches current featurization, and `export_torchscript.py` parity passes (§7 step 5); documented fallback: `/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.pt` + `--warm-value-fresh`.
- **Train knobs:** `--epochs 3 --batch-size 256 --lr 1e-3` (defaults, rod_v2-proven), `--value-loss-weight 1.5` (flywheel precedent), `--window 12`, `--aux-weight 0.15` default, no `--augment-rotations`, `--stage-local /tmp/distill_stage_$it` (CIFS read staging, rod_v2 pattern).
- **Search knobs per stream:** champ stream `--c-puct 1.5 --dirichlet-eps 0.0 --temp-threshold 15 --batch-size 1` (teacher targets stay pure; opening diversity comes from per-seed deck shuffles + τ=1 for plies <15); net stream `--c-puct 3.0` + Dirichlet defaults (0.3/0.25) + `--temp-threshold 15 --batch-size 8` (rod_v2-proven exploration recipe).

### D5 — Boxes, workers, orchestrator placement

- **Stage 1 (champ gen, net-free CPU):** orch-OFF; **local W16, laptop W12**, both pulling one `--shared-claim` pool per iter. (These are the mapped orch-OFF optima; classical *eval* jobs have run W30-class, so the launch checklist includes a 15-min W16-vs-W24 local bench — take the free win if it's real, don't block on it.)
- **Stage 2:** **local = carc-orch SHM server + net gen at W28** (`--forwarders 4 --max-batch 16 --batch-timeout-ms 2.0 --watchdog-secs 30`, per-iter TorchScript export, rod_v2's `gen_flywheel_v29.sh` launch idiom), then train; **laptop = champion stream at W12 orch-OFF** — a full box of laptop CPU makes more champion games than laptop-orch W8 makes net games, the champion mix has to come from somewhere, and it decouples the boxes (no cross-box orch dependency). The laptop's champ driver is ckpt-independent so it free-runs ahead of the loop.
- **Train: LOCAL always** (single-process GPU-latency-bound; laptop trains ~10% slower — don't CPU-shop it). In stage 1 train overlaps the next iter's CPU gen (train is GPU + 2 dataloader workers; gen is CPU) — train is off the critical path.
- **Orch server: local only, launched/killed per iter by the gen wrapper** (pkill carc-orch + rm /dev/shm/carc_* + fresh `--model <iter.ts.pt>`), never a long-lived daemon.

---

## 3. The 12-iter schedule

Seed plan: champ stream `--seed-start 700000000 + it*100000`; net stream `+50000` on top; probe `699000000`. All streams `--iter 0` into per-iter roots (rod_v2 pattern), `--shared-claim --claim-host $HOST` everywhere (self-heal + reboot-resume idempotency).

| iter | teacher / gen agent | sims | games | orch? | box:W | train (window / warm-from) |
|---|---|---|---|---|---|---|
| 0 | champion (`--teacher heuristic_prior`, clairvoyant) | 2750 | 600 champ | OFF | local:16 + laptop:12, shared-claim | w12 / `checkpoints/warmstart_canonical.pt` |
| 1 | champion | 2750 | 600 champ | OFF | local:16 + laptop:12 | w12 / iter_00 |
| 2 | champion | 2750 | 600 champ | OFF | local:16 + laptop:12 | w12 / iter_01 |
| 3 | champion | 2750 | 600 champ | OFF | local:16 + laptop:12 | w12 / iter_02 · **GATE G1 (§6)** |
| 4 | net priors + frozen v2.9 leaf value (`--leaf-eval v2_5`, blend 0, resid 0) **+ champion side-stream** | net 400 / champ 2750 | 450 net + 150 champ | net: ON (local) | local:28 (orch) + laptop:12 (champ, orch-OFF) | w12 / iter_03 |
| 5–11 | same as iter 4, net ckpt = previous iter | 400 / 2750 | 450 + 150 | ON / OFF | local:28 + laptop:12 | w12 / iter_(N−1) |
| 12 | — loop ENDS. 12 ckpts + metrics + probe series. Eval = separate task. | | | | | |

Per-iter wall: stage 1 ≈ 3.0–3.7 h gen (600 × ~430 s/game ÷ ~28 workers @ ~0.8 eff; train overlaps); stage 2 ≈ 2.0–2.3 h (laptop champ quota ≈ 1.9–2.2 h is the critical path; local: TS export + 450 net games ≈ 80 min + train 17→40 min). Totals: **stage 1 ≈ 12–15 h, stage 2 ≈ 16–18 h, experiment ≈ 28–34 h.**

Data totals: 7,200 games (3,600 champion = 50%, 3,600 net), ~1.04M policy rows, ~11–22 GB compressed shards (MUST be re-measured at smoke — §7 step 0/8; C: had only **21 GB free** on 2026-07-16, a hard launch blocker until cleared).

---

## 4. New code (exact spec) + what's reused verbatim

### 4.1 The champion policy-recording emitter — `--teacher` in `scripts/run_selfplay_iter.py` (the ONE substantive new piece)

- Add `--teacher {net,heuristic_prior}`, default `net` (zero behavior change for existing callers).
- Add teacher knobs: `--teacher-tau-p` (float, 5.0), `--teacher-value-norm` (float, 15.0), `--teacher-leaf-quantize` (`float|int`, `float`). c_puct comes from the existing `--c-puct`.
- In `_build_evaluators()` (run_selfplay_iter.py:317–374): when `teacher == "heuristic_prior"`, skip net loading entirely and return `ev = make_heuristic_prior_evaluator(game, HeuristicPriorConfig(tau_p=…, value_norm=…, leaf_quantize=…, leaf_cfg=None))` (src/carcassonne_ai/heuristic_prior_mcts.py:225 — it already satisfies the NeuralMCTS evaluator contract `Board -> (priors[A], value)`), `bev = None`. Do NOT wrap with `make_v25_value_wrapper` (the evaluator's value is already `tanh(leaf/value_norm)`, and it's the FLOAT leaf, matching the champion, vs the wrapper's int leaf).
- Guards (assert, fail loudly): `--teacher heuristic_prior` requires `--leaf-eval nn` (default, unused), `--value-blend 0`, `--residual-scale 0`, no `--orchestrator` / `--shm-eval-server` / `--remote-eval-server` / `--anchor-checkpoint`, `--batch-size 1`. Make `--checkpoint` optional in this mode (it exists today only for net load + scalar-width peek; the recorded featurization comes from the game wrapper, not the ckpt).
- What gets recorded — **all existing behavior, zero changes**: `play_one_selfplay_game()` (src/carcassonne_ai/selfplay.py:70) already writes `policies` = root visit distribution (raw, untempered), `aux_mask=True` for trajectory rows, `values` per `--value-target score_diff` = `tanh((p0−p1)/15)` mover-POV backfilled, ownership planes, `valid_masks`, via `GameDataset.save()` atomic-rename shards. Temperature (τ=1 below `--temp-threshold`) applies to move SELECTION only. Dirichlet eps=0 disables root noise (NeuralMCTS constructor already supports it).
- `manifest.json`: include a `teacher` block = `HeuristicPriorConfig.as_manifest()` + sims + the resolved leaf env (self-describing results rule).
- **Parity test (required):** on ≥3 fixed boards, priors/value from the injected `make_heuristic_prior_evaluator` must match what `HeuristicPriorAgent` computes internally (same cfg); plus a 1-game smoke (sims=32) asserting: policies rows sum to 1 over legal mask, `aux_mask.all()`, values ∈ [−1,1] and sign-consistent with final score_diff, manifest has the teacher block. Add to `tests/`.

### 4.2 `scripts/distill_flywheel/probe_metrics.py` (small, ~80 lines — the no-eval safety net)

Loads a checkpoint + the frozen probe shards (`probe_data/iter_00/seed_*.npz`), pure forward pass (no games): reports mean **policy CE** −Σ π_champ·log p_net over legal-masked softmax (aux_mask rows only), **top-1 agreement** (argmax match rate), **value MSE + Pearson r** vs stored outcome values. Appends one JSON line `{iter, ckpt_sha, n_rows, probe_ce, top1, value_mse, value_r}` to `$OUT/probe_metrics.jsonl`. Runs on local GPU in <2 min; called by the driver after every train.

### 4.3 Driver scripts (copy-adapt, don't rewrite)

- `scripts/distill_flywheel/run_distill_flywheel.sh` — **copy `scripts/rod_v2/run_rod_v2_flywheel.sh` and edit ONLY the recipe block + stage logic**; keep its plumbing verbatim: `done/` markers, ckpt-exists skip (reboot resume), gen watchdog (npz-count poll, STALL_GEN=15 → heal, HEAL_CAP=8 → FATAL), `_clean_stranded` (delete `.claim` without `.npz`), `_ssh_bg` laptop launch (rc=124 = launched), git-bundle code sync, per-iter train → `overnight_iter_screen.py` collapse screen (rc=3 stops the chain — it's train-metrics-only, NOT a game eval) → probe_metrics.py. Recipe deltas: GAMES/SIMS/teacher per §3 table, `--value-target score_diff`, `--residual-scale 0`, WINDOW=12, iter-0 warm-from warmstart_canonical, stage split at iter 4.
- `scripts/distill_flywheel/gen_distill.sh` — copy `scripts/rod_v2/gen_flywheel_v29.sh`; two modes: `champ` (orch-less, `--teacher heuristic_prior --sims 2750 --c-puct 1.5 --dirichlet-eps 0 --batch-size 1`, W16 local / W12 laptop) and `net` (identical orch launch idiom: per-iter `export_torchscript.py` parity-gated → `run_server.sh --transport shm --workers 28 --forwarders 4 --max-batch 16 --batch-timeout-ms 2.0 --watchdog-secs 30 --n-scalar <from ckpt>` → `--shm-eval-server`, `--sims 400 --c-puct 3.0 --batch-size 8`). Keep the flat_leaf_cy `SUPPORTS_V29_CURVE` rebuild check.
- `scripts/distill_flywheel/laptop_champ_stream.sh` — laptop-side loop `for it in <list>: gen champ quota into iter<it>_data; touch done/champ<it>`; ckpt-independent, free-runs ahead; invoked via `ssh laptop 'bash -s' < script` with `cd` on line 1 (remote-ssh rule), `setsid nice -n 19 … </dev/null &`.
- `scripts/distill_flywheel/champ_env.sh` — the env block, **copied at build time from `governance/PRODUCTION.yaml`** (point-don't-copy: PRODUCTION.yaml is canonical; as of this writing: `CARCASSONNE_V29_MEEPLE_CURVE="-10,-5,-1.25,0,2.5,3.75,5,6.25"`, `CARCASSONNE_V25_CAP=8`, `CARCASSONNE_V25_OPP_CAP=8`, `CARCASSONNE_USE_FLAT_LEAF=1`, `CARCASSONNE_USE_CY_LEAF=1`, `CARCASSONNE_USE_CY_REPR=1`). Sourced by EVERY gen and train invocation on BOTH boxes (env is read at import time; spawned workers re-read it).

### 4.4 Reused verbatim (no edits)

`src/carcassonne_ai/selfplay.py` · `src/carcassonne_ai/heuristic_prior_mcts.py` · `scripts/train_iter.py` · `scripts/export_torchscript.py` · `rust/carc-orch/run_server.sh` · `src/carcassonne_ai/warmstart.py` (GameDataset) · `scripts/rod_v28/overnight_iter_screen.py` · git-bundle sync + `_ssh_bg` idioms from rod_v2.

**Explicitly NOT built:** any in-loop game eval, any arch change, any new featurization, xeon anything, fair/PIMC emitter, changes to `governance/PRODUCTION.yaml` or the champion.

---

## 5. Directory layout on the share

Local path `/mnt/c/carc-shared/…`, laptop path `/mnt/carc-shared/…` (the two-prefix rule; lint hook enforces).

```
<share>/distill_flywheel_20260715/
  ckpt/iter_00.pt … iter_11.pt          # + iter_NN.metrics.json, iter_NN.ts.pt
  iter0_data/iter_00/seed_*.npz          # 600 champ games   (seeds 700000000+)
  …
  iter4_data/iter_00/seed_*.npz          # 150 champ (7004xxxxx) + 450 net (700450000+)
  …
  iter11_data/iter_00/seed_*.npz
  probe_data/iter_00/seed_*.npz          # 24 champ games, seeds 699000000+ — FROZEN, never trained
  probe_metrics.jsonl
  done/   logs/
```

Repo-side mirror: `measurement/distill_flywheel_20260715/` (this DESIGN.md, later a STATUS/RESULTS note + manifest pointers). Nothing is pruned until the post-iter-12 eval concludes (window 12 needs all shards).

---

## 6. No-eval safety net — free per-iter diagnostics + go/no-go

Watch three signal families, all zero-game-cost:

1. **Probe fidelity** (`probe_metrics.jsonl`): policy CE vs champion visit dist, top-1 agreement, value MSE/r on the frozen 24-game probe set. This is the distillation ruler — fixed data, comparable across all 12 iters (unlike train_iter's rotating 5% val split).
2. **Train metrics** (`iter_NN.metrics.json`): `value_outcome_corr` (absolute-value semantics under score_diff — comparable to the historical ~0.6-class ruler), `policy_entropy` vs `baseline_policy_entropy` (collapse detector, already wired into the chain via overnight_iter_screen rc=3), `val_pol_loss` trend.
3. **Pipeline health**: games/h vs this doc's ETA (watchdog), shard counts, off-mask policy assertion (hard AssertionError with repro dump — any trip = halt).

Gates (decided now, so no judgment calls mid-run):

- **G0 (after iter 0):** probe CE(iter_00) < probe CE(warmstart_canonical) by ≥10%, and value_outcome_corr ≥ 0.30. Fail → halt, inspect shards (probable emitter bug), ping Joshua.
- **G1 (after iter 3, before enabling the flywheel stage):** probe CE decreased in ≥2 of the 3 steps since iter 0 AND top1(iter_03) > top1(iter_00) AND value_outcome_corr ≥ 0.40 AND no entropy-collapse rc=3. Fail → do NOT start stage 2; leave the loop paused at 4 distill ckpts and escalate.
- **G2 (each flywheel iter, drift guard):** if probe CE > 1.15 × its running minimum for 2 consecutive iters → the net is drifting from the teacher; **intervention = raise the champion mix to 300 champ + 300 net for the remaining iters** (config change only, still no eval), log it, continue. Not a halt.
- **Hard halts anytime:** value_outcome_corr < 0.25; entropy screen rc=3; HEAL_CAP exhausted; off-mask assertion.

What this net CANNOT catch (stated honestly): a flywheel net whose *play strength* regresses while still imitating the champion's distribution well — that is precisely the iter-12 eval's job, and the value-floor + 25% champion mix are the structural bounds on how bad it can silently get.

---

## 7. Ordered build → smoke → launch checklist (for the coder)

0. **Disk gate (BLOCKER):** C: had 21 GB free on 2026-07-16; projected shards ~11–22 GB. Free C: to ≥ 1.5× the *measured* (step 8) projection before stage 1. Share scan 2026-07-16: NO prunable npz remain (rod_v2 shards already pruned); the share holds only ~15 GB total — reclaimable-with-approval: ~2.6 GB stale git-sync bundles (`carc_kdets_sync.bundle`, `sync_20260704.bundle`, `carc_c6_sync.bundle`, `deeper_search_sync.bundle`, `carc_rod_batch512.bundle`) + `code_sync`/`wheels` ≈ 9 GB. The real hog is the Windows Users/WSL-vhdx → durable fix is Joshua's `wsl --shutdown` + vhdx compact. Do not launch on hope.
1. `scripts/distill_flywheel/champ_env.sh` from `governance/PRODUCTION.yaml` (copy the champion env verbatim at build time).
2. Implement `--teacher` in `run_selfplay_iter.py` per §4.1 + the parity/smoke pytest. Run the test.
3. Implement `probe_metrics.py` per §4.2; test it on the step-2 smoke shard with `warmstart_canonical.pt`.
4. Copy-adapt the three driver scripts per §4.3 (recipe-block edits only; keep rod_v2 plumbing).
5. **Warm-from verification:** `warmstart_canonical.pt` loads in train_iter (arch keys 96×6), scalar width matches the step-2 smoke shards, `export_torchscript.py` parity passes on it. Any failure → fallback `rod_v28_continuation/ckpt/iter_01.pt` + `--warm-value-fresh`, note it in the manifest and tell Joshua.
6. git bundle → laptop, `fetch + reset --hard`; verify flat_leaf_cy `SUPPORTS_V29_CURVE` on both boxes; pre-launch process census on both boxes (`ps -o pid,etime,%cpu,comm -C python --sort=-etime` + `scripts/cluster_status.py --share /mnt/c/carc-shared`).
7. **Gen the probe set:** 24 champ games @2750, local W16 (~15 min), into `probe_data/`. Record `probe_metrics.jsonl` line 0 for `warmstart_canonical.pt` (the G0 baseline).
8. **Production-knob smoke (standing rule):** champ stream 8 games @ sims 2750, W16 local — measure s/game (expect ~430 ± 30%) and MB/game; recompute the §3 ETA and the step-0 disk projection from measured numbers. Then 1-epoch train smoke on those shards + a probe_metrics run. Optional 15-min W16-vs-W24 local bench; keep whichever wins.
9. **Launch stage 1 detached** (`setsid nice -n 19 … </dev/null &` via the driver; laptop via `ssh laptop 'bash -s' <`). Immediately verify parallelism (`ps`, loadavg, both boxes) and state the ETA in chat.
10. Stage-2 entry is gated on **G1** (§6). Before iter 4's first net gen: orch smoke — export iter_03 TS, start the SHM server, run 4 games @ sims 400 W28, check games/h vs the ~5–11 s/game expectation, kill server. Then let the driver run iters 4–11.
11. At iter 12: STOP. 12 ckpts + metrics + probe series on disk. Close-out touches (results.csv row is N/A until eval; DECISIONS index line, STATUS stamp, roadmap line) then hand off to the separate eval task.

---

## OPEN QUESTIONS for Joshua (pre-launch)

1. **Disk:** C: is at 21 GB free — this design needs ~11–22 GB persistent (measured at step 8). OK to do the `wsl --shutdown` + vhdx compact first, or should I cut games/iter (600→400 saves ~⅓)?
2. **Stage split 4+8** (distill/flywheel). A 6+6 split favors goal 1 (more full-strength teacher data) at the cost of flywheel evidence. Default stands at 4+8 unless you say otherwise.
3. **Budget:** 600 games/iter ≈ 28–34 h total. 800/iter (stronger distill, ~+9 h) — want it?
4. **Flywheel sims 400** (2× rod_v2's 200, ~free wall-clock since the laptop paces stage 2) — any objection?
5. **Champ-stream Dirichlet OFF** (pure teacher targets; diversity from deck seeds + τ) — confirm, or keep noise for extra state coverage?
6. **G2 intervention** (drift → champ mix 300/300, no halt, no eval) — comfortable with that as the pre-authorized response?
