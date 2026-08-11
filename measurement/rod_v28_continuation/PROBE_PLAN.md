# RoD v2.8 Continuation Probe — PROBE PLAN (Phase 2)

**Branch:** `rod_v28_continuation_probe` @ `ccc33c2` · **Date:** 2026-06-22 · **Status:** MEASUREMENT ONLY.
Small continuation probe (1–3 iterations), **not** a heroic flywheel, **not** a promotion. Binding comparison = frozen **`ITER8_V28_PARENT`** (see [`BASELINE_REGISTRY.md`](BASELINE_REGISTRY.md)).

---

## Design summary

Restart self-play from **iter8** under the **v2.8 leaf** (v2.7 + `meeple_k=2`), train 1–3 continuation checkpoints, and test whether any beats `ITER8_V28_PARENT` (iter8 net scored by the *same* v2.8 leaf) in deck-paired net-vs-net eval. Stay as close as possible to the attempt-#2 / deeper-teacher recipe; the **only** intended substrate change is the leaf (v2.7 → v2.8), realized by a single env var.

**Held constant (attempt-#2 recipe):** 96×6 ResNet arch · warm-from current champion · `residual_scale=0.25` · `value_target=residual` · `value_loss_weight=1.5` · `epochs=3` · `sims=200` (gen) · `c_puct=3.0` · `--leaf-eval v2_5` · per-iter data (no cross-iter accumulation) · deck-paired both-seats eval.

**The one substrate change:** `CARCASSONNE_V25_MEEPLE_K=2.0` exported into the self-play worker env (legacy `LeafConfig.meeple_k` → flat/Cython fast path; `_v28_active()` stays False — verified Phase 1). No code edits to `gen_flywheel.sh` / `run_selfplay_iter.py` / `train_iter.py` (they inherit the env). v2.7 stays bit-identical when the var is absent → **v2.8 is opt-in**.

**Why this is the right test (and its honest prior):** the v2.8 leaf lifts heuristic *and* neural search ~uniformly, and at equal leaf the gap `iter8+v2.8` vs `heur@3200+v2.8` is unchanged (−38.4). So the leaf swap alone is not an ML lever. The probe asks the narrower question: does *distilling v2.8-guided MCTS* (stronger visit-count policy targets) into iter8 produce a net that beats iter8 when both use v2.8? Plausible mechanism (better leaf → better policy targets → better priors); plausible null (iter8 policy already plateaued at iter5; deeper-teacher washout). Cheapest way to discriminate.

## Run topology

- **Boxes:** local 5800x-box (5900XT 16C/32T + RTX 5060 Ti) — gen (orch W28) + train; laptop (i7-14650HX + RTX 4070m) — gen (orch W8). **Rust carc-orch, high W.** Xeon NOT used (per instruction: local + laptop).
- **Run root:** local `/mnt/c/carc-shared/rod_v28_continuation/` ; remote `/mnt/carc-shared/rod_v28_continuation/` (same CIFS share, shared-claim work-stealing into one `iter${IT}_data/iter_00/` pool).
- **Checkpoints:** `rod_v28_continuation/ckpt/iter_01.pt`, `iter_02.pt`, `iter_03.pt`. iter8 parent is **never** modified/relabeled.
- **Self-play seed band:** `SP_SEED = 600_000_000 + IT*10_000` (distinct decks/iter, < 1e9 eval floor, clear of attempt-2's tiny bands).
- **Eval seed band (Phase 4/5):** fresh `1_922_000_000` (clear of spent sealed 1.7e9 + battery 1.906/1.907e9).
- All launches **detached** (`nohup … & disown` local; `setsid … </dev/null &` laptop) + `nice -n 19`. Pre-launch process census by default. Bundle-refresh the share before the laptop run (offline git-bundle sync).

## Per-iteration commands (driver: `scripts/rod_v28/rod_gen_train_iter.sh`)

Inputs: `IT` (1/2/3), `WARM` (parent ckpt, share path), `GAMES=1000`, `SIMS=200`, `SCALE=0.25`.

**(a) Local self-play gen** (5800x, orch W28, v2.8 via env):
```
SHARE=/mnt/c/carc-shared REPO=/home/doctor/projects/carcassone HOST=5800x \
  WARM=$WARM OUT=/mnt/c/carc-shared/rod_v28_continuation/iter${IT}_data \
  GAMES=$GAMES SIMS=200 SCALE=0.25 USE_ORCH=1 ORCH_WORKERS=28 SEED_START=$SP_SEED \
  CARCASSONNE_V25_MEEPLE_K=2.0 \
  nohup nice -n 19 bash scripts/gen_flywheel.sh > /tmp/rod_gen5800x_$IT.log 2>&1 & disown
```

**(b) Laptop self-play gen** (orch W8, v2.8 via env, shared-claim into the same pool):
```
ssh laptop "cd /home/<laptop>/carcassone && SHARE=/mnt/carc-shared REPO=<laptop repo> HOST=laptop \
  WARM=/mnt/carc-shared/<WARM-relpath> OUT=/mnt/carc-shared/rod_v28_continuation/iter${IT}_data \
  GAMES=$GAMES SIMS=200 SCALE=0.25 USE_ORCH=1 SEED_START=$SP_SEED CARCASSONNE_V25_MEEPLE_K=2.0 \
  setsid nice -n 19 bash /mnt/carc-shared/code_sync/gen_flywheel.sh > /tmp/rod_genlaptop_$IT.log 2>&1 </dev/null &"
```
(The laptop `gen_flywheel.sh` git-resets to the `stage-b-wiring` bundle — OK, the v2.8 `meeple_k` field is in that code; only the env var differs. Inherited `CARCASSONNE_V25_MEEPLE_K=2.0` makes its `env … python` worker use v2.8.)

**(c) Wait** until `iter${IT}_data/iter_00/*.npz` count ≥ `GAMES` (Monitor/poll), then kill both gen pools (carc-orch + run_selfplay_iter, by exact pid) and clean stranded `.claim`s.

**(d) Train** (local, 5900XT):
```
nice -n 19 env CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_CAP=12 CARCASSONNE_USE_FLAT_LEAF=1 \
  CARCASSONNE_V25_MEEPLE_K=2.0 \
  .venv/bin/python -u scripts/train_iter.py \
  --output-root /mnt/c/carc-shared/rod_v28_continuation/iter${IT}_data \
  --warmstart-root data/warmstart/heuristic_tau05 --iter 0 --window 10 --warmstart-mix-fraction 0.0 \
  --value-loss-weight 1.5 --stage-local /tmp/rod_stage_$IT \
  --warm-from $WARM --output /mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_0${IT}.pt --epochs 3 \
  --prov-value-target residual --prov-selfplay-leaf "v2_8_meeple_k2" --prov-run-tag rod_v28_continuation
```
Records loss curves + a `manifest.json`. Output ckpt sha256 logged to `CHECKPOINT_MANIFEST.json`.

**Pre-flight smoke (before iter1, at production knobs):** (i) `scripts/rod_v28/verify_iter8_v28_parent.py` (done, Phase 1); (ii) a ~2-game v2.8 self-play smoke confirming the worker's `DEFAULT_CONFIG.meeple_k==2.0` and the orch path is live; (iii) a tiny `iter8+v2.8 vs iter8+v2.7` re-eval (n≈20–30) as a free strength-reproduction side-check + orch smoke.

## Chaining / keep-best rule

- `champion_0 = iter8`. For iter k: `WARM = champion_{k-1}`.
- After iter k's pilot eval vs parent: `champion_k = argmax({champion_{k-1}, RoD_iter_k})` by paired point estimate (floor = iter8 = the parent). If RoD_iter_k does **not** beat its warm-parent, the next iter re-attempts from `champion_{k-1}` on a fresh deck band (a second independent distillation shot), not a degraded chain.

## Eval plan

- **Phase 4 (binding):** `RoD_iter_k + v2.8` vs `ITER8_V28_PARENT`, net-vs-net, both NeuralMCTS@200, c_puct=3.0, residual_scale=0.25, v2.8 leaf both sides, deck-paired both seats, fresh band 1.922e9. **Pilot n=200**, top up to **n=400** only if positive/noisy. (Exact harness: net-vs-net via two carc-orch servers — resolve the precise script at Phase 4 start; reuse `scripts/level2/eval_hybrid_handoff.py` if it accepts two distinct neural checkpoints, else a thin two-server adapter.)
- **Phase 5 (ruler, only if a ckpt survives Phase 4):** `RoD_iter_k + v2.8` vs `HEUR_800_V28` and `HEUR_3200_V28` (and optionally `HYBRID_K8_V28`). Report parent-relative gain, ruler-relative gain, and whether the equal-leaf gap (parent's −38.4 vs heur@3200_v28) shrank.

## Stop criteria

- **Training collapse** (train_iter exit 2 / entropy-floor / NaN loss) → STOP iter, mark inconclusive/negative.
- **iter1 clearly worse** (pilot n=200 vs parent: point ≤ −20 Elo **and** z ≤ −1.5) → **STOP, RoD negative** (cheapest-informative; don't spend iters 2–3).
- **Promising** (pilot point ≥ +12 Elo, ~1σ at n=200) → top up to n=400; z≥2 with point ≥ ~+24 Elo = credible margin → RoD positive; continue to next iter + Phase 5.
- **Noisy/flat** (|point| < 20, |z| < 1.5) → run one more iter (compounding chance) up to the cap.
- **Hard cap: 3 iterations.** No top-ups beyond n=400 unless strategically important.

## Expected wall-clock / cost (owned hardware, no cloud $)

| step | est. |
|---|---|
| gen 1000 games @ sims200, 5800x(W28)+laptop(W8) ≈ 17 g/min | ~60 min |
| train (5900XT) | ~12–15 min |
| pilot eval n=200 paired (net-vs-net @ sims200) | ~25–30 min |
| **per iteration (gen+train+pilot)** | **~1.7–2 h** |
| **1 iteration (likely stop point)** | **~1.7–2 h** |
| **3 iterations (worst case, all gates pass)** | **~5–6 h** |

Staged: run iter1 first, gate on its pilot — only continue if it shows signal (cost discipline: cheapest-informative-first, stop-early).

## Deliverables produced downstream

- Phase 3: `CHECKPOINT_MANIFEST.json`, `TRAINING_LOG_SUMMARY.md`
- Phase 4: `PARENT_MATCHUPS.csv` + `.md` + per-run manifests
- Phase 5: `RULER_MATCHUPS.csv` + `.md`
- Phase 6: `ROOT_AUDIT_V28*.{jsonl,csv,md}`
- Phase 7: `ROD_V28_CONTINUATION_REPORT.md`

→ Proceed to Phase 3 (process census → bundle refresh → pre-flight smoke → launch iter1).
