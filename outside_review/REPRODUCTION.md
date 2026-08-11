# REPRODUCTION — smallest practical reproductions

All commands run from the repo root with the venv active:

```bash
cd /home/doctor/projects/carcassone
source .venv/bin/activate          # python>=3.11, torch>=2.7
```

Where a number is given, it is the **expected range**, not an exact value (most
paths use the global RNG; seed control is partial — see caveats). Commands marked
⚠ touch the cluster / long compute — read the ETA first. Anything I could not
verify hands-on is marked **UNVERIFIED**.

---

## 0. Environment + suite sanity (≈2 min)
```bash
pip install -e . && pip install -e engine          # if not already installed
python scripts/phase0_smoke.py                      # engine smoke
python -m pytest tests/ -q                          # expect: PASS, 1 skipped
```
Expected: pytest green (332 test fns; the 1 skip is checkpoint-gated; `[bridge] ... ConnectionError` lines in `test_remote_eval_bridge` are expected teardown noise, not failures).

---

## 1. A complete game (random self-play fuzz) (≈1 min)
```bash
python -m carcassonne_ai.game_wrapper --self-play-random --n 100
```
Expected: 100 games complete, 0 rule/mask violations, mean score-sum > 10, window-overflow < 5%. (This is `tests/test_game_wrapper.py::test_self_play_random_*` as a CLI.)

---

## 2. One MCTS decision (raw policy vs searched policy) — minimal, in-process
There is no single CLI for "one decision," so use a 3-line harness:
```python
python - <<'PY'
import random; random.seed(700001)
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.mcts import NeuralMCTS
from carcassonne_ai.evaluators import make_v25_value_wrapper
import torch
from carcassonne_ai.network import load_checkpoint            # symbol name UNVERIFIED — see network.py
g = Game()
b = g.get_init_board()
# load the sims=200-plane global best
ckpt = "checkpoints/v25_retrain_optionB_iter1/iter_00.pt"
net = load_checkpoint(ckpt)                                    # adapt to actual loader if needed
ev = make_v25_value_wrapper(net, g)                            # v2.7 leaf + net priors
m = NeuralMCTS(g, ev, c_puct=3.0, sims=200)
m.search(b)
counts, actions = m.root_visit_distribution(b)
print("raw policy argmax:", )   # priors[argmax]
print("searched argmax (visits):", actions[counts.argmax()])
print("best_action (Q,N):", m.best_action(b))
PY
```
**Purpose:** compare the raw prior's top move to the searched (visit) top move and to `best_action` (which tiebreaks on Q, not visits — `mcts.py:709-713`). They can differ; that divergence is §13's "MCTS improves/worsens the raw policy" evidence.
**Status: UNVERIFIED** — the loader symbol (`load_checkpoint`) and exact API may differ; `scripts/play_vs_net.py` is the maintained reference for loading a net and stepping the game.

---

## 3. One self-play game (one .npz on disk) (≈1 min)
```bash
python scripts/run_selfplay_iter.py \
  --output-root /tmp/sp_repro --iter 0 --games 1 \
  --initial-checkpoint checkpoints/v25_retrain_optionB_iter1/iter_00.pt \
  --leaf-eval v2_5 --value-target score_diff --sims 50 --seed-start 0
ls /tmp/sp_repro/iter_00/                # expect: seed_000000.npz
python - <<'PY'
import numpy as np
d = np.load("/tmp/sp_repro/iter_00/seed_000000.npz")
print({k: d[k].shape for k in d.files})  # expect 8 arrays: boards scalars policies values valid_masks ownership aux_mask group_id
PY
```
Expected: one `seed_000000.npz` with the 8-array schema (`warmstart.py:96-106`). `boards (N,78,25,25)`, `policies (N,2511)`, `values (N,)`, etc. **Status: UNVERIFIED flag names/defaults** — confirm `--initial-checkpoint` vs `--warm` arg name in `run_selfplay_iter.py` argparse.

---

## 4. One replay sample (inspect a training row)
```bash
python - <<'PY'
import numpy as np, glob
f = sorted(glob.glob("/tmp/sp_repro/iter_00/seed_*.npz"))[0]
d = np.load(f)
i = 0
print("value target:", d["values"][i], "in [-1,1]:", -1 <= d["values"][i] <= 1)
print("policy sums to ~1:", abs(d["policies"][i].sum()-1) < 1e-3, " over", (d["policies"][i]>0).sum(), "legal actions")
print("aux_mask (full-traj row?):", d["aux_mask"][i], " group_id:", d["group_id"][i])
PY
```
Expected: value in [−1,1]; policy a valid distribution over legal actions only; `aux_mask=True` for a full-trajectory row.

---

## 5. One training update (≈1–3 min on CPU)
```bash
python scripts/train_iter.py \
  --output-root /tmp/sp_repro --current-iter 0 --window 1 \
  --initial-checkpoint checkpoints/v25_retrain_optionB_iter1/iter_00.pt \
  --output /tmp/train_repro.pt --epochs 1 --batch-size 64
```
Expected: prints per-epoch `pol_loss`, `val_loss`, `own_loss`, a `value_corr` readout (`train_iter.py:156-192`), and writes `/tmp/train_repro.pt` atomically + a `.metrics.json`. **Note the loss weighting:** value MSE enters at weight 1.0 while policy CE is ~5–10× larger (G-T2). **Status: UNVERIFIED arg names.**

---

## 6. One checkpoint evaluation vs the reference (≈3–6 min, n=20 screen) ⚠
```bash
CARCASSONNE_V25_CAP=12 CARCASSONNE_V25_DROP_THREE_OPEN=1 \
python scripts/eval_net_vs_heuristic.py \
  --checkpoint checkpoints/v25_retrain_optionB_iter1/iter_00.pt \
  --n 20 --sims 200 --c-puct 3.0 --paired --seed-start 700000
```
Expected (n=20 is a smoke, ±large): NeuralMCTS wins a majority; prints W/L/D, wr, elo, σ_elo and writes a `manifest.json`. **For a real screen use n≥100; verdict n≥400.** A `manifest.json` like `artifacts/example_manifest_lever.json` is written next to the results.
**⚠ Watch for A8:** the opponent HeuristicMCTS uses the **v1** leaf (`mcts.py:298-304`), not v2.7 — so this is NOT a matched-leaf comparison despite the docstring.

---

## 7. Raw-policy vs searched-policy comparison (the §13 evidence)
Use the §2 harness and report, over ~50 positions from one game, how often `argmax(prior) != argmax(visits)` and whether `best_action` (Q-tiebreak) agrees with visits. **No turnkey script exists** — `scripts/probe_decision_ranking.py` (the Kendall-τ probe) is the closest maintained tool:
```bash
python scripts/probe_decision_ranking.py --help     # harvests sibling sets + compares value/v2.7/searchQ rankings
```
Expected from prior runs: value-net τ ≈ 0.08, v2.7 τ ≈ 0.58 (STATUS.md Step A). **Status: UNVERIFIED flags.**

---

## 8. The out-of-lineage odometer (the current headline) ⚠ (multi-hour, cluster)
```bash
python scripts/ladder_asymmetric.py \
  --checkpoint /mnt/c/carc-shared/lever_seq/ckpt/residual.pt \
  --net-sims 200 --heur-rungs 200,800,3200 --n 120 --seed-start 950000 \
  --residual-scale 0.25      # arg name UNVERIFIED
```
Expected (from `results.csv: odometer_residual_*`): residual margin (s0.25 − s0) ≈ +63.6 (h200), +47.5 (h800), −17.5 (h3200); crossover heur-equiv depth ≈ 588 (residual) vs 325 (pure policy). ⚠ multi-hour; state ETA and pick a box.

---

## Caveats that affect ALL reproductions
1. **RNG/determinism is partial.** Deck shuffle uses the global `random` seeded per worker; cross-process determinism is **untested** (gap #4) and was the source of a real historical bug. Same `--seed-start` → same decks *within* a process, not guaranteed across boxes/code-revs.
2. **The residual leaf is silently disabled in `eval_iter_head_to_head.py`** (`_effective_blend` drops `residual_scale`, `:238-247`). Use `eval_net_vs_heuristic.py` / `ladder_asymmetric.py` for residual evals, or fix the gate first.
3. **Checkpoints are referenced by path, not content hash** — verify you have the file the manifest names.
4. **The CIFS share `/mnt/c/carc-shared`** holds most raw eval dirs; it may be unmounted. In-repo `checkpoints/` has the pre-Phase-0 nets; the Stage-B / lever / residual nets live on the share.
