# az_zero — TABULA-RASA AlphaZero mini-loop — DESIGN

**Status:** BUILT + SMOKED (not launched). Branch `rod_v2_flywheel`. 2026-07-24.
**Purpose:** the FIRST true zero-start experiment in the project — the existing
net-value + net-policy self-play machinery, but started from a **RANDOM-INIT**
network instead of the heuristic warm-start. Measures what the AlphaZero
scaffolding can bootstrap on its own, and (via the anchor screen) how far a
zero-start closes the gap to the heuristic-warm-started net.

⚠️ **MEASUREMENT / EXPLORATORY.** Touches NOTHING under
`governance/PRODUCTION.yaml`, the champion, `checkpoints/` lineage, or the live
`distill_strong_20260723` production gen. All artifacts live under
`/mnt/c/carc-shared/az_zero_20260724/`.

---

## 1. What was REUSED vs BUILT

### Reused unchanged (the core insight — no new gen script was needed)
| Component | File | Role |
|---|---|---|
| Net-value + net-policy self-play | `scripts/run_selfplay_iter.py` + `src/carcassonne_ai/selfplay.py` | The v1–v6 Phase-4 emitter. With `--teacher net --leaf-eval nn --value-blend 0 --residual-scale 0` BOTH the PUCT priors (policy head) AND the leaf value (value head) come from the net — exactly the pure-NN AZ agent. Emits the `GameDataset` npz schema `train_iter.py` reads unmodified. |
| Orch-SHM gen wrapper | `scripts/canonical_az/gen_m2_orch.sh` | Per-box sighted self-play through the carc-orch SHM GPU orchestrator (`--leaf-eval nn`), incl. TorchScript export + server lifecycle. The loop's default gen transport. |
| Trainer | `scripts/train_iter.py` | Unchanged. Reads arch/metadata from `--warm-from`, trains policy CE + value MSE (+ optional aux), writes the next ckpt in the same dict format. |
| Dataset / IO | `src/carcassonne_ai/warmstart.py` (`GameDataset`) | The npz schema (boards, scalars, policies, values, valid_masks, ownership, aux_mask, group_id). |

### Built new (`scripts/az_zero/`)
| File | What it does |
|---|---|
| `make_random_ckpt.py` | Mints the tabula-rasa `iter_-1_random.pt`: loads `warmstart_sighted.pt` ONLY to copy its arch (81ch/42-scalar 96×6 `value_global_pool`) + ckpt-dict metadata format, then constructs a fresh `CarcassonneNet` with a fixed seed (default 20260724). Weights are random; no heuristic knowledge. Saves the exact keys `train_iter.py --warm-from` reads. |
| `eval_anchor_screen.py` | The cheap anchor screen. Candidate net-agent (NeuralMCTS, pure-NN leaf) vs (a) a uniform-random legal-move player, or (b) a FIXED reference net-agent. Per-side encoders (so sighted-vs-blind never mixes reps), deck-paired seat-swap, net-on-CPU, per-game JSON resume. |
| `run_az_zero.sh` | The loop driver (config-at-top, `--dry-run`, `done/` resume markers). Per iter: gen → train → screen (every 2 iters + final). 12 iters. |

**Why a new eval instead of reusing `eval_m2_net_vs_net.py`:** that harness (1)
needs TWO orch servers running and (2) uses the **v2.9 heuristic leaf** for the
value (a policy-only health check). Both are wrong for az_zero: injecting the
heuristic leaf would measure a *different* agent than the loop trains, defeating
the tabula-rasa point; and nothing existing has a **random-move opponent**. The
new screen keeps the pure-NN leaf and adds the random floor.

---

## 2. Exact loop config

Self-play (per iter, `run_selfplay_iter.py`):
- `--teacher net` (net drives search) · `--leaf-eval nn` (leaf VALUE = net value head) · `--value-blend 0 --residual-scale 0` (no heuristic leaf, no residual)
- `--value-target score_diff` → per-position value target = **game OUTCOME** `tanh((p0−p1)/15)`, current-player POV, backfilled from the final score
- policy target = **root visit-count distribution**, normalized over the legal mask
- `--sims 128` · `--c-puct 3.0` · `--fpu 0.6`
- `--games 300` · `--workers 14` · **LOCAL ONLY** (no laptop) · `nice -n 19`
- gen transport: **carc-orch SHM** (GPU-batched, `USE_ORCH=1` default) or **net-on-CPU** fallback (`USE_ORCH=0`, `CUDA_VISIBLE_DEVICES=""`)

Train (`train_iter.py`):
- `--warm-from` prev iter (`iter_-1_random.pt` at iter 0) · `--window 4` · `--epochs 3` · `--batch-size 256`
- `--value-loss-weight 1.0` · `--aux-weight 0` (ownership head OFF) · `--entropy-floor-frac 0` (**disabled**, see §4)
- trains on GPU (`CUDA_VISIBLE_DEVICES=0`)

Anchor screen (`eval_anchor_screen.py`, every 2 iters + final):
- n=50, sims=128, c_puct 3.0, fpu 0.6, net-on-CPU, `nice -n 19`
- vs `random` AND vs `net` (`--anchor-ckpt`, default `checkpoints/warmstart_canonical.pt`)

Lineage: `iter_-1_random.pt → iter_00 → … → iter_11` (12 iters). Each trained
ckpt carries the sighted arch/metadata forward, so the whole chain stays 81ch/42.

---

## 3. What exploration the machinery supports

The reused `selfplay.py` provides (documented, not newly built):
- **Root Dirichlet noise**: `dirichlet_alpha=0.3`, `dirichlet_eps=0.25` (defaults in `run_selfplay_iter.py`), mixed into the root prior each move.
- **Temperature schedule**: τ=1 (sample ∝ visits) for plies `< temp_threshold` (default 15), then τ=0 (argmax visits). Gated by the GAME CLOCK (opening exploration), AZ-canonical.
- **PUCT `c_puct`** (3.0) and **FPU reduction** (0.6) shape selection-time exploration.

No new exploration machinery was added — these are the standard AZ knobs already
in the emitter. (The `--anchor-fraction` / learner-vs-anchor mixing path exists in
`run_selfplay_iter.py` but is OFF for az_zero: pure self-play from the random net.)

---

## 4. Known purity caveats (READ before interpreting results)

1. **The self-play search is CLAIRVOYANT.** `selfplay.py` builds `NeuralMCTS`
   with `fair_chance=False` (the default) — the engine's deck is pre-shuffled in
   its TRUE future order, so every simulation descends along the ACTUAL upcoming
   tiles. The search **sees the next tiles**; it is perfect-info
   single-determinization, **NOT** blind PIMC and **NOT** an expectation over
   draws. There is no determinization (`k_dets`) in this path. The RoD-v2 /
   `fair_agent` machinery is the non-clairvoyant (blind-PIMC) family; the classic
   Phase-4 `selfplay.py` reused here is the clairvoyant one. **Consequence:** the
   learned net is trained against clairvoyant search targets, and the anchor-screen
   strength numbers are clairvoyant-search numbers — they do NOT directly predict
   blind-PIMC deployment strength. This is the single most important caveat.

2. **The anchor screen is also clairvoyant** (`eval_anchor_screen.py` uses the
   same `fair_chance=False`). Both agents get the same info, so the head-to-head is
   fair, but the absolute winrate is a clairvoyant number.

3. **`warmstart_canonical.pt` anchor confounds rep with scaffolding.** It is a
   BLIND 78ch/10-scalar net; the az_zero candidate is SIGHTED 81ch/42. The screen
   handles the cross-rep matchup (each side its own encoder), but a difference could
   be rep OR scaffolding. For a CLEAN "what scaffolding buys" comparison use the
   same-arch sighted warm-start:
   `ANCHOR_CKPT=/mnt/c/carc-shared/m2_sighted/warmstart_sighted.pt`. One knob;
   documented in the driver.

4. **`--value-loss-weight 1.0` may under-train the value head.** Policy CE (over
   ~2511 actions) out-magnitudes value MSE ~5–10× in the unweighted sum — and here
   the value head IS the self-play leaf. 1.0 is the AZ-canonical / least-surprising
   default; the distill flywheel used 1.5 for outcome targets. If the per-iter
   `value↔outcome corr` (train_iter prints it) stalls low, bump `VLW` to 1.5–3.

5. **Entropy-floor disabled.** The iter-0 warm-from is the RANDOM net, whose
   near-uniform policy has HIGH entropy. Legitimate AZ policy sharpening drops
   entropy well below the default 0.5× floor → a FALSE collapse halt. `ENTROPY_FLOOR=0`
   for the zero-start lineage. (Watch the printed value↔outcome corr + winrate-vs-random
   as the real health signals instead.)

6. **Ownership labels exist but are unused.** Unlike the fair distill emitter
   (dummy zeros), `selfplay.py` DOES reconstruct real terminal ownership. az_zero
   trains `--aux-weight 0` per spec (pure policy+value AZ), so they're just carried,
   not trained on. Bump `AUX_WEIGHT` if the ownership aux is wanted later.

---

## 5. Smoke results

Verified off-disk 2026-07-24 09:15 (the engineer agent was cut off before writing this section;
smoke artifacts under `/mnt/c/carc-shared/az_zero_20260724/smoke/`):
- 4 smoke games (W2, sims 32) completed; npz well-formed: **144 rows/game, policy rows sum to
  exactly 1.0, values in [−1, 1], boards 81ch (sighted)**.
- `train_iter.py` accepted the shards from the random warm-from and wrote `smoke/ckpt/iter_00.pt`
  + metrics (finite losses: val_pol 1.83, val_val 0.065; no NaN).
- Both anchor screens (`vs_random`, `vs_warmstart`) ran and wrote per-game JSON.
- Zero Tracebacks/FATALs across all smoke logs.

## 6. Cost forecast

To be filled from live iter_00 timing (smoke W2/sims-32 numbers are not honestly scalable to
W14/sims-128 under SMT contention with the live distill gen; the loop was launched 2026-07-24
09:18 alongside the beast per Joshua's 50%-contention tolerance — see PREREG.md §5).

---

## 7. Exact launch command (full loop)

Run `make_random_ckpt.py` first (already done — `iter_-1_random.pt` is in place),
then launch the driver **detached** (Mac→Windows→WSL SIGHUP + WSL teardown both
kill tty-attached jobs):

```bash
cd /home/doctor/projects/carcassone
# (optional) dry-run to print every per-iter command:
bash scripts/az_zero/run_az_zero.sh --dry-run

# real launch — detached, nice-19, log to /tmp:
nohup nice -n 19 bash scripts/az_zero/run_az_zero.sh \
  > /mnt/c/carc-shared/az_zero_20260724/logs/loop.log 2>&1 & disown
```

Per-box logs: gen `…/logs/gen_itNN.log`, train `…/logs/train_itNN.log`, screens
`…/logs/screen_{random,warm}_itNN.log`. Resume is automatic (`done/iter$it`,
`done/gen$it` markers). Checkpoints: `…/ckpt/iter_NN.pt` (+ `.metrics.json` with
the per-iter `value↔outcome corr`).

**net-on-CPU fallback** (if the GPU/orch is unavailable or contended):
prepend `USE_ORCH=0` to the launch. **Clean-scaffolding anchor** (recommended):
prepend `ANCHOR_CKPT=/mnt/c/carc-shared/m2_sighted/warmstart_sighted.pt`.
**Worker widths (Joshua's final call 2026-07-24 ~10:00):** relaunches carry `W_GEN=20
SCREEN_W=32`, applied via driver bounce at the iter-0 train boundary. Context: the half-box
heuristic (RoD2-era sweeps: gen ~28 / eval ~48 full-box) first suggested 14/24, then a live
measurement showed az gen workers at ~32% CPU each (GPU round-trip latency-bound, GPU at 41W)
— the W optima are conservative here because the binding resource (CPU↔GPU trips) is NOT
under contention from the CPU-only distill gen. Joshua set 20/32 as the operating point.

⚠️ The full loop's gen (W14) will contend with any live production CPU gen. Launch
after the `distill_strong_20260723` run is done, or accept the contention.
