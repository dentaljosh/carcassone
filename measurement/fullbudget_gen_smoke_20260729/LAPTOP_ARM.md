# Full-budget flywheel gen — pre-flight throughput smoke (LAPTOP arm)

**Status: RESULTS — COMPLETE (2026-07-30 early hours).** Laptop arm of
[scripts/distill_flywheel/FULLBUDGET_GEN_SMOKE_RUNBOOK.md](../../scripts/distill_flywheel/FULLBUDGET_GEN_SMOKE_RUNBOOK.md),
Joshua-authorized ("get an agent doing w sweep on laptop"). Sibling arms:
[SMOKE_RESULTS.md](SMOKE_RESULTS.md) (local 5900XT) and the M5/ANE arm (`M5_ANE_ARM.md`, not yet
landed at the time of writing).
**Throwaway games** — no `experiments/results.csv` row, no deck band consumed, no promotion,
[`governance/PRODUCTION.yaml`](../../governance/PRODUCTION.yaml) untouched. Purpose: price the
laptop into a possible rodv3 gen fleet.

## Result — the W ladder (every point a COMPLETED wave, games = W)

| W | games | wall (s) | **s/game** | **games/h** | steady ex/s | steady batches/s | avg_batch | fwd_busy | GPU W (med) | GPU util | load1 | mem used |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 8 | 8/8 | 899.8 | 112.5 | 32.0 | 3,496 | 239.1 | 14.6 | 24% | 81.4 | 54% | 4.75 | 4.6 GB |
| 12 | 12/12 | 1171.7 | 97.6 | 36.9 | 4,034 | 256.9 | 15.7 | 33% | 93.8 | 62% | 8.24 | 5.8 GB |
| **16** | **16/16** | **1264.0** | **79.0** | **45.6** | 4,344 | 265.2 | 16.4 | 41% | 106.2 | 66% | 11.54 | 7.1 GB |
| 20 | 20/20 | 1524.7 | 76.2 | 47.2 | 4,576 | 267.7 | 17.1 | 48% | 118.6 | 83% | 11.96 | 8.1 GB |

Step-to-step gain in effective games/h: W8→W12 **+15.3%**, W12→W16 **+23.5%**, W16→W20 **+3.5%**.

**W\* = 16.** W20 is the measured peak (47.2 games/h) but W16 sits **3.5% below it**, inside the
5–10% settle band, so the standing rule (*smallest W within ~5–10% of peak*) selects W16. The knee
is **bracketed on both sides** — W12 is 21.8% below peak (clearly out) and W20 above it is a real
completed wave, not an extrapolation — so this is an interior knee, not a ladder endpoint. W16 also
costs **1.0 GB less RAM** than W20, which matters on an 11.9 GB WSL box that has to stay usable.

Cross-check: the local arm independently settled **W\* = 16** on completely different hardware.

## Queue collapse: NOT seen anywhere up to W20

The hazard the smoke hunts is July's `W32 s200→s376` regression, where orch throughput *fell*
209 → 97 batches/s. On the laptop, steady-state **batches/s rose monotonically** across the whole
ladder — **239.1 → 256.9 → 265.2 → 267.7** — flattening at the top (the W16→W20 step adds only
+0.9%) but never inverting. `avg_batch` also rose monotonically (14.6 → 17.1) and never pinned
against `max_batch=24`, so the batcher was not saturating its own window.

What *is* visible at W20 is the **GPU becoming the binding constraint**, not a collapse:
`fwd_busy` peaks at 61% (matched-window) / 82% (early-wave instantaneous), GPU power 118.6 W median
vs 81.4 W at W8, and util 83%. That is the honest reason the ladder flattens above W16 — the
laptop runs out of GPU, in an orderly way. Below W16 the workers are *latency*-bound, not
CPU-bound: each gen worker sits at only ~42–47% CPU (blocking on the SHM round-trip), so 16 workers
consume ~7 of 24 hardware threads.

## Method notes

**Every point is a completed wave, so `s/game` is measured, not derived.** `games = W` (one per
worker) for the reason the local arm gives: with fewer games than workers the point measures
single-game latency rather than saturated throughput. Effective `s/game` = the gen script's own
total elapsed ÷ games, i.e. it already includes ramp-up and the drain tail — never a
first-completion rate (order-statistic trap).

**Orch counters.** `carc-orch` prints cumulative `batches`/`examples` plus a window `examples/s`
every ≥5 s with no timestamp, so each window's wall is recovered as `Δexamples ÷ (examples/s)` and
`batches/s = Δbatches ÷ wall`. Reported figures are the **median over steady-state windows with 15%
trimmed off each end**. Within-wave drift is real and expected (W16 ran 5,800 → ~4,100 examples/s
as boards filled with meeples and per-leaf cost grew); the trimmed median spans the whole wave so it
includes that.

**Forwards/game is W-invariant, as the local arm assumed.** Measured per cell from the cumulative
counters at the cell boundaries: **335,166** (W8) · 341,812 (W12) · 333,132 (W16) · 328,528 (W20)
— mean ≈ 334.7k, spread ±2%. Rows/game was **143.9 constant** at every W (1151/8, 1727/12,
2303/16, 2878/20), matching the local arm's 144.

### Cross-arm calibration: the window-derivation method looks ~10% CONSERVATIVE

The local arm derived its W16/W20/W28 `s/game` by scaling its *measured* W12 number by the ratio of
window throughputs (its cells were truncated by the same session crash that hit this arm). The
laptop arm has **both** the window reading and the completed wave at the same W, so it can check
that method:

- laptop W12 measured 97.6 s/game, matched-window (<600 s) 4,462 ex/s; W16 matched-window 4,951 ex/s
- derivation predicts `97.6 × 4462/4951` = **87.9 s/game** at W16
- the completed W16 wave actually ran **79.0 s/game** — the derivation is **10.1% pessimistic**

Cause: the early-window throughput ratio (1.110) understates the **full-wave** ratio (1.204),
because higher W holds up better late in a wave. So derived numbers on any arm are likely a floor,
not a ceiling. This is a one-point calibration on different hardware — flagged for the local arm to
use or discard, **not** applied to their table here.

## The read — the laptop is a peer of the local box, not a junior partner

At the W\* both arms settled on independently (**W16**), the laptop turns in **79.0 s/game =
45.6 games/h from a completed 16-game wave**, against the local 5900XT's **≈87.6 s/game =
41.1 games/h** (derived from a window). The laptop is therefore **~1.11× the local box's gen rate**,
and its number is the better-evidenced of the two. This refutes the going-in assumption behind this
arm's brief — that the laptop's GPU-net ratio is "~4.5× worse than local", which would have priced
it near-worthless for gen. That ratio is a **batch-1 single-move latency** property; under the
batched SHM orchestrator the RTX 4070 Laptop is fully competitive, and at W20 the laptop is pushing
118 W through its GPU at 83% util. It also refutes the runbook's naive **~37–40 s/game** linear
prior for *either* box: the real full-budget cost is ~2× that.

Fleet arithmetic for one rodv3 turn (300–450 games), both boxes at W16:

| fleet | games/h | 300 games | 450 games | laptop share |
|---|---|---|---|---|
| laptop alone | 45.6 | 6.6 h | 9.9 h | 100% |
| local alone | 41.1 | 7.3 h | 11.0 h | — |
| **laptop + local** | **86.7** | **3.5 h** | **5.2 h** | **53%** |

So the laptop is worth **just over half** of a two-box rodv3 gen fleet, and adding it roughly halves
the gen wall. With ~1 h of training on top, a full-budget turn lands at **~4.5 h (300 games) to
~6.2 h (450 games)** on the two boxes together — i.e. the runbook's "~4–6 h/iter" guess survives,
but only *because* the laptop is in the fleet; local alone would be ~8–12 h. Practical caveat for
whoever runs it: at W16 the laptop holds ~7.1 GB of an 11.9 GB WSL budget, so a long gen shard there
wants `--shared-claim` work-stealing plus the on-disk watchdog, and should not share the box with
another memory-hungry job.

## Exact commands

Laptop repo rev **`fb5097e5a`** (synced from local before the run — see Provenance). All cells
`nice -n 19` and `setsid`-detached; gen workers are CUDA-hidden by `champ_env.sh` so only the orch
server touches the GPU. Every remote invocation was piped as `ssh laptop-wsl 'bash -s' < script.sh`
with `cd` on line 1 (the inline `cd &&` form gets stripped in transit).

Export the TorchScript (clean shell, CUDA visible — NOT under `champ_env.sh`):

```bash
cd /home/doctor/projects/carcassone
nice -n 19 .venv/bin/python scripts/export_torchscript.py \
  --checkpoint /mnt/carc-shared/distill_strong_20260723/ckpt/iter_03.pt \
  --out /home/doctor/rodv3_smoke_laptop/iter_03.ts.pt --device cuda
```

Orch SHM server — `OMP_NUM_THREADS=1` in the **server's own** env, `max_batch=24 ≥ W`:

```bash
cd /home/doctor/projects/carcassone
SP=/home/doctor/rodv3_smoke_laptop
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 setsid nice -n 19 rust/carc-orch/run_server.sh \
  --model $SP/iter_03.ts.pt --transport shm --shm-name lapsmoke \
  --workers 16 --forwarders 4 --max-batch 24 \
  --batch-timeout-ms 2.0 --watchdog-secs 30 \
  --n-ch 81 --n-scalar 42 --device cuda </dev/null > $SP/logs/orch_server.log 2>&1 &
```

One W point (`W` and `--seed-start` vary):

```bash
cd /home/doctor/projects/carcassone
source scripts/distill_flywheel/champ_env.sh
SP=/home/doctor/rodv3_smoke_laptop
setsid nice -n 19 .venv/bin/python -u scripts/distill_flywheel/gen_fair_distill.py \
    --games <W> --k-dets 4 --sims 688 --c-puct 1.5 --tau-p 5.0 --value-norm 15.0 \
    --sighted --net-ckpt /mnt/carc-shared/distill_strong_20260723/ckpt/iter_03.pt \
    --shm-eval-server lapsmoke --workers <W> --batch-size 16 \
    --seed-start <seed> --out $SP/out/w<W> </dev/null > $SP/logs/gen_w<W>.log 2>&1 &
```

Throwaway seed bands, deliberately far from every production band: W8 `991080000`,
W12 `9911120000`, W16 `9911160000`, W20 `9911200000`.

## Provenance

| Item | Value |
|---|---|
| Box | laptop (`ssh laptop-wsl`), i7-14650HX 8P+8E / 24 threads, RTX 4070 Laptop 8188 MiB, WSL2 11.9 GB RAM + 8 GB swap |
| Laptop repo rev | **`fb5097e5a`** (= local `android-app` HEAD at launch) |
| Net checkpoint | `/mnt/carc-shared/distill_strong_20260723/ckpt/iter_03.pt` (the CL-067 net), 30,083,965 B |
| TorchScript | traced (`torch.jit.script` unavailable); fp-parity gate PASS at k=37: `max|dpriors|=7.53e-06`, `max|dvalue|=1.19e-04` |
| **Leaf hash (runtime)** | **`6dfffd57051690f2`** — identical to the local arm; the `champ_env.sh` curve125 dialect of the champion leaf (`governance/PRODUCTION.yaml` registers it as `frozen_config_hash_meeple_k0`, annotated "(champ_env/distill)") |
| Leaf | v2.9.2 Bmild cap8 **curve125** — `[-10,-5,-1.25,0,2.5,3.75,5,6.25]`, `bonus_cap=8`, `opp_bonus_cap=8` |
| Budget | k_dets 4 × sims 688 = **2752 sims/move**, exact endgame ON, `exact_max_k=2` |
| Representation | SIGHTED 81ch board / 42 scalars, `--batch-size 16` |
| torch | 2.11.0+cu128, CUDA available |
| Laptop-side logs | `/home/doctor/rodv3_smoke_laptop/logs/` — `orch_server_w8_w12_w16.log`, `orch_server_w20.log`, `gen_w{8,12,16,20}.log`, `sampler.tsv`, `boundary_after_w{8,12,16}.txt`; shards in `out/w{8,12,16,20}/` (throwaway) |

**Rev sync.** The laptop was 3 source commits behind at `c6f0f9676`. `gen_fair_distill.py` and the
`carc-orch` binary were already byte-identical to local, but `champion_factory.py` and
`fair_agent.py` were not (including `54b31ac` PROMOTION), so the box was synced to local HEAD via an
incremental git bundle on the share — `git bundle create /mnt/c/carc-shared/rodv3_inc_20260729.bundle
c6f0f9676..android-app`, then `git fetch` from `/mnt/carc-shared/...` + `reset --hard` on the laptop
(never github; the remotes can't reach it). Post-sync md5s match local exactly. No source was edited
on either box.

## Two deviations, and one interruption

1. **W20 was added beyond the briefed `{8,12,16}` grid.** With only W8/W12/W16 the peak sat at the
   top of the ladder, which the standing bracket rule forbids settling on. W20 was run as a full
   wave to bracket the knee — it required restarting the orch server with 20 SHM slots (`--workers
   20`, `--shm-name lapsmoke20`), keeping `max_batch=24` and all other knobs fixed. Cells W8/W12/W16
   shared one 16-slot server; only the slot count changed for W20.
2. **`max_batch=24`, vs the local arm's 32.** Kept uniform across the whole laptop ladder so the
   sweep is internally comparable. Not a binding constraint at any point: `avg_batch` topped out at
   17.1 (a single worker's 16-board request), never approaching 24.

**Interruption.** A Claude session death killed the driving agent mid-ladder. Because every cell was
`setsid`-detached, W8 and W12 ran to completion unattended and were recovered from disk; W16 and W20
were launched afterwards by the resumed agent against the same server/ckpt/rev. No cell was
partially counted — all four rows are complete waves with matching shard counts. The only casualty
was the 5 s sampler's process-count and RSS columns, which were mis-specified (`ps -C python3` never
matches the venv's `python`) and read 0 throughout; GPU power, util, loadavg and total memory are
valid, and per-cell attribution was recovered from the unambiguous memory signature rather than
wall-clock guesses.

**Cleanup.** Orch server and sampler killed by exact PID, verified gone; `/dev/shm/carc_lapsmoke*`
removed; box left idle (load 0.24, 1.1 GB used of 11.9 GB). One pre-existing orphan from a prior
agent, `/dev/shm/carc_fairnvnClaptop-wsl` (2026-07-28, no owning process), was **left alone** as it
is not this arm's to reap.
