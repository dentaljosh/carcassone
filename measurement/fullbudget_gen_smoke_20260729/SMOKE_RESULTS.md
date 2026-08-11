# Full-budget flywheel gen — pre-flight throughput smoke (LOCAL 5900XT)

**Status: VERDICT — W\* = 16 (2026-07-29 night). Ladder answered; one cell crash-truncated, no
re-run owed** (reasoning under "Cells the crash truncated"). Executes
[scripts/distill_flywheel/FULLBUDGET_GEN_SMOKE_RUNBOOK.md](../../scripts/distill_flywheel/FULLBUDGET_GEN_SMOKE_RUNBOOK.md)
on the local box, Joshua-authorized. **Throwaway games** — no `results.csv` row, no deck band
consumed, no promotion, `governance/PRODUCTION.yaml` untouched. Purpose: turn the "~4–6 h/iter"
guess into a schedulable number for the lever-6 (full-budget flywheel gen) funding decision.

**Headline:** local net-prior fair gen at full budget k4×688 peaks at **W = 16**, giving
**≈87.6 s/game ⇒ 7.3 h for 300 games / 10.9 h for 450**. That is **~2× the runbook's 3–4.5 h
prior**, whose sims200 baseline is separately shown to have been wrong. **No queue collapse**
appeared at any W.

## Result — W\* = 16

Effective rate is compared on an **identical 215 s phase-matched window** for all four points
(orch axis `[60,280]s`, see Method). `s/game` is anchored on the one **complete cohort** (W12,
12/12 games, 1309.5 s wall) and carried to the other W by the measured throughput ratio.

| W | games run | mean s/game | games/h | fwd/s (examples/s) | batches/s | avg_batch | fwd_busy | GPU W (mean) | loadavg | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 12 | **12/12 complete** | **109.1 (measured)** | 33.0 | 4,307 | 229.5 | 18.8 | 34% | 49.5 | 7.3 | the anchor cohort; 19.8% below peak → out |
| **16** | 16 launched, window only | **≈87.6 (derived)** | **41.1** | **5,367** | 234.6 | 22.9 | 64% | 76.8 | 16.9 | **PEAK — W\*** ; cell truncated by the session crash |
| 20 | 20 launched, window only | ≈91.9 (derived) | 39.2 | 5,111 | 234.5 | 21.8 | 56% | 73.6 | 12.0 | 95.2% of peak |
| 28 | 28 launched, window only | ≈91.0 (derived) | 39.5 | 5,162 | 204.7 | 25.2 | 83% | 76.3 | 16.5 | 96.2% of peak; batches/s down, batch size up |

**W\* = 16.** The settle rule (smallest W within ~5–10% of peak) selects it twice over: W16 *is*
the peak, and even if the true peak were W20 or W28, W16 would still win as the smallest W inside
the tolerance band. W12 is excluded at 19.8% below peak, so the optimum is **bracketed on both
sides** — an interior knee, not a ladder endpoint.

Robustness — the ranking is invariant to the slice choice (W16 first in every case):

| slice | W12 | W16 | W20 | W28 |
|---|---|---|---|---|
| `[60,240]s` (175 s) | 4,328 | **5,382** | 5,131 | 5,107 |
| `[60,280]s` (215 s) | 4,307 | **5,367** | 5,111 | 5,162 |
| `[60,540]s` (476 s)\* | 4,154 | **5,359** | 5,043 | 5,245 |

\* at this slice W16 contributes only 225 s (all it has); W12/W20/W28 contribute the full 476 s.

### Projected gen wall at W\* = 16

| games/iter | gen wall | + ~1 h train = iter wall |
|---|---|---|
| 300 | **7.3 h** | ~8.3 h |
| 450 | **10.9 h** | ~11.9 h |

**This roughly doubles the runbook's estimate.** The runbook's naive prior ("~10.7 s/game at
sims200 ⇒ ~37 s/game ⇒ 300–450 games ≈ 3–4.5 h local-only") is refuted on both legs:

1. **The sims200 baseline itself was wrong.** The real sims200/W20 local net-prior gen rate is
   **23.0–23.7 s/game**, not 10.7 — read off the completed production logs
   (`distill_flywheel_sighted_20260716/logs/gen_local_it19.log`: `[done] 176 games … 4055.0s`;
   `it20`: `196 games … 4651.1s`). The 10.7 figure appears to be an order-statistic artifact —
   those same logs print `48.4s/game` at the 10-game mark and converge downward to ~23, so a
   first-completions read in either direction is unsafe.
2. **Scaling to s688 is worse than the ×3.44 budget ratio suggests** at any single W, but the
   *right* W recovers part of it: 23.3 → 87.6 s/game is ×3.76, close to the ×3.44 budget ratio
   once W is re-optimised from 20 down to 16.

### Collapse: NOT observed

The hazard being hunted — July's `s200→s376 @ W32` regression where throughput fell **209 → 97
batches/s** — did **not** reproduce anywhere on this ladder. What the counters show instead is an
orderly approach to a GPU-forwarder ceiling:

- `batches/s` sits in a tight **205–239** band at every W, never collapsing.
- Throughput scales by **bigger batches, not more round-trips** (avg_batch 18.8 → 25.2 as W goes
  12 → 28 while batches/s is flat-to-declining), so ~230 batches/s is a **round-trip ceiling** on
  this box.
- `fwd_busy` rises 34% → 64% → 83%. Past W16 the forwarders are near-saturated, which is why W20
  and W28 buy nothing: added workers deepen the queue rather than the throughput.

W28 is the one point where `batches/s` dips meaningfully (204.7 vs ~234) while `avg_batch` peaks at
25.2 against the `max_batch=32` cap — the *onset* of the queueing regime that produced the July
collapse, but two steps short of it, and it costs only ~1% of throughput. Since no collapse
appeared, the runbook's optional downward W8 bracket was not triggered (W12 already brackets below).

### Cells the crash truncated — and why the data still decides

A session crash at ~23:52 killed the orch server and the live W16 cell; the session scratchpad
(shard `.npz` files, both parser scripts) was wiped with it. Surviving on disk: every
`logs/gen_w*.log`, the full `logs/orch_server.log` (532 stats lines covering **all four** cells),
and `logs/sampler.tsv`. Status per cell:

| cell | how it ended | data adequacy |
|---|---|---|
| W12 | ran to completion | **complete** — the s/game anchor, 12/12 games |
| W20 | I killed it at 643 s (bounded-window design) | 476 s window — ample |
| W28 | I killed it at 574 s (bounded-window design) | 476 s window — ample |
| W16 | **crash-truncated at ~285 s** | 225 s window — shorter, but ≥ the 215 s common slice |

**No re-run is owed.** The comparison is made on a window all four cells fully cover, W16 leads at
every slice length tested, and the settle rule reaches W16 whether or not W16 is literally the peak.
The residual caveat is confined to W16's *absolute* `s/game`: 87.6 is derived from W12's full-game
drift profile rather than a completed W16 cohort, so it inherits the assumption that the within-wave
cost curve has the same shape at W16 as at W12. The spread across the three candidate W is only
~5% (87.6–91.9 s/game), which cannot change a go/no-go on a 7–11 h iteration — so the pricing above
is safe to schedule against, and a completed W16 cohort would be a refinement, not a correction.

### Caveats worth carrying forward

- **`max_batch=32` was held fixed** across the whole ladder for comparability. W28's avg_batch of
  25.2 is close enough to that cap that the high-W end is partly *cap*-limited; raising `max_batch`
  is an untested lever that might move the ceiling. It would not change W\*=16, which sits far from
  the cap.
- **Single box, n=1 per cell.** No replicate; a ~5% difference between adjacent W is not resolved.
- Shards were written to local ext4 rather than the CIFS share (production writes to the share).
  At 144 rows/game this is one ~28 MB write per ~88 s of compute — under 1% either way.
- The laptop's net-free champion side-stream was **not** part of this smoke; these numbers price the
  **local net-prior gen stream only**.



## Provenance

| Item | Value |
|---|---|
| Net checkpoint | `/mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt` (the CL-067 net) |
| TorchScript | exported fresh, fp-parity gated vs eager (`max|dpriors|=7.0e-06`, `max|dvalue|=1.1e-04` at k=37 → OK) |
| Leaf | v2.9.2 Bmild cap8 **curve125** — values `[-10,-5,-1.25,0,2.5,3.75,5,6.25]`, `bonus_cap=8`, `opp_bonus_cap=8` |
| Leaf hash (runtime) | `6dfffd57051690f2` |
| Budget | k_dets 4 × sims 688 = **2752 sims/move**, exact endgame ON, `exact_max_k=2` |
| Representation | SIGHTED 81ch board / 42 scalars, `--batch-size 16` |
| Rows per game | **144** exactly (140 policy + 4 value-only), constant across every game |
| Code rev | `5f86c8d-dirty` (dirty = untracked measurement artifacts only; no source edits) |

### On the leaf hash — `6dfffd57051690f2` is correct, not a mismatch

The runbook names the leaf `a36d2e15`. The observed runtime hash is `6dfffd57051690f2`. These are
the **same leaf function in two hash dialects**, and the difference is registered in governance:
[`governance/PRODUCTION.yaml`](../../governance/PRODUCTION.yaml) records

- `leaf_hash: a36d2e15a3b3d71d` — PRIMARY, `c5_leaf_override._leaf_hash` (harness dialect, meeple_k=2.0)
- `frozen_config_hash_meeple_k0: 6dfffd57051690f2` — `snapshot._frozen_config_hash`, meeple_k=0.0,
  annotated **"(champ_env/distill)"** — i.e. exactly this gen path's dialect

`meeple_k` is inert under a non-null curve, so all three registered dialects describe the same leaf
(PRODUCTION.yaml: "240/240 byte-identical"). `scripts/distill_flywheel/champ_env.sh` independently
documents that sourcing it yields runtime hash `6dfffd57051690f2`. Verification was done on leaf
**VALUES** (curve125 / cap8 / opp_cap8, read out of the run manifest), which is what both the gen
script's docstring and `champion_factory.py` instruct — not on the hash string.

## Method, and the two deliberate deviations from the runbook

**Deviation 1 — games per point = W, not a flat 10.** With 10 games at W=28, 18 of 28 workers sit
idle, so the point measures single-game latency, not saturated throughput, and cannot price a
300–450-game iteration (the whole purpose). One full wave costs the same wall clock as 10 games at
that W, so this is strictly better science at no extra budget.

**Deviation 2 — W16 / W20 / W28 are bounded-window throughput points, not completed waves.** A full
saturated wave at W=28 is ~28 games × ~330k forwards ÷ throughput ≈ 30 min, which together with
W12's 22 min would blow the 90-min cap. So only W12 was run to completion (as the s/game anchor);
the other cells ran at full saturation for a bounded window and were read from the **orch server
counters**. This is sound because:

- forwards/game is **W-invariant** (the game is fixed by its seed; 144 rows every game, of which
  140 are net-driven plies), and measured constant, so the conversion carries no per-W assumption;
- **the collapse signature the smoke hunts is itself an orch-counter phenomenon** (July's
  regression was 209 → 97 batches/s), so the bounded window measures the hazard directly rather
  than through a proxy.

The runbook's own escape hatch ("if a single W point is projected >30 min ... cut it and note it")
authorizes trading game count for wall; this trades it for window length instead, which preserves
saturation. W16 was added as a refinement point after the crude ladder showed W20 ≈ W28, i.e. that
the knee lay at or below W20 (crude → refine → settle-low, per the standing W-sweep convention).

**Throughput parsing.** `carc-orch` prints cumulative `batches`/`examples` plus a window
`examples/s` every ≥5 s with **no timestamp** (`rust/carc-orch/src/batcher.rs`). The window's true
wall is recovered as `wall = Δexamples / (examples/s)`, integrated to give a per-wave time axis;
each slice is then aggregated as **total work ÷ total wall** (not a mean of rates). Windows
reporting `fwd_busy > 120%` are dropped as torn — this removes exactly one window, the one spanning
the server's death. No figure anywhere in this doc is a first-completion rate (order-statistic trap);
the one `s/game` measured directly is a 12/12 cohort mean.

**Why a phase-matched slice rather than whole waves.** Throughput falls *within* a wave (W12:
~4,470 → ~3,900 examples/s, avg_batch 19.8 → 16.7) because per-leaf cost grows as boards fill with
meeples — more farm/city util calls, the nonlinearity CLAUDE.md warns about for cheap-smoke
extrapolation. Waves of different W therefore reach different game phases at different times, and
comparing whole waves of unequal length would confound W against board-fill. Every rate in the main
table is consequently taken over the **same `[60,280]s` orch-axis window** (first 60 s dropped as
worker/torch/SHM ramp), which also happens to be the largest window the crash-truncated W16 cell
fully covers.

**Anchoring `s/game`.** W12 completed 12 games in 1309.5 s = **109.1 s/game** and consumed
3,953,178 forwards = **329,431 forwards/game**, i.e. a true whole-wave average of 3,019 examples/s.
Other W are priced as `s/game(W) = 109.1 × exs(W12) / exs(W)` on the common slice — equivalently,
scaling the W12 slice-to-whole-wave correction (0.701) onto each W. Only measured ratios enter.

## Config traps honoured

- `OMP_NUM_THREADS=1` passed to the **orch server's own env** (unpinned, its libtorch pool owns the
  box at ~2574% CPU — memory `feedback_pin_orch_omp_threads`).
- `--max-batch 32 ≥ W_max 28`, `--workers 28` SHM slots ≥ every W tested → one server served all
  four points with no reconfigure (deliberately held fixed for comparability).
- 4 forwarders, each on its own CUDA stream; `--n-ch 81 --n-scalar 42` (server defaults 78/12 would
  be silently wrong for the sighted net).
- `nice -n 19`, every cell `setsid`-detached, gen workers CUDA-hidden by `champ_env.sh` so only the
  server touches the GPU.
- Peak worker RSS ~534 MB (cap was 10 GB) — no memory risk.

## Commands

Export the TorchScript (clean shell, CUDA visible — NOT under `champ_env.sh`):

```bash
.venv/bin/python scripts/export_torchscript.py \
  --checkpoint /mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt \
  --out $SP/iter_03.ts.pt --device cuda
```

Start the one orch SHM server (OMP pinned, max_batch ≥ W_max):

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 setsid nice -n 19 rust/carc-orch/run_server.sh \
  --model $SP/iter_03.ts.pt --transport shm --shm-name fbsmoke \
  --workers 28 --forwarders 4 --max-batch 32 \
  --batch-timeout-ms 2.0 --watchdog-secs 30 \
  --n-ch 81 --n-scalar 42 --device cuda </dev/null > logs/orch_server.log 2>&1 &
```

One W point (`W` and `--seed-start` vary; `$SP` = session scratchpad, throwaway shard dir):

```bash
source scripts/distill_flywheel/champ_env.sh
setsid nice -n 19 .venv/bin/python -u scripts/distill_flywheel/gen_fair_distill.py \
    --games <W> --k-dets 4 --sims 688 --c-puct 1.5 --tau-p 5.0 --value-norm 15.0 \
    --sighted --net-ckpt /mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt \
    --shm-eval-server fbsmoke --workers <W> --batch-size 16 \
    --seed-start <seed> --out $SP/smoke_out/w<W> </dev/null > logs/gen_w<W>.log 2>&1 &
```

Seed bands used (throwaway, deliberately far from every production band): W12 `990120000`,
W16 `990160000`, W20 `990200000`, W28 `990280000`.

Cells were run sequentially against **one** server, each killed by exact process group
(`kill -9 -$PGID`; `setsid` makes PGID == PID) with the spawn-worker count verified to zero after
each — a killed mp main does not reap its spawn workers.

Raw logs for every cell are in [`logs/`](logs/):

| file | contents |
|---|---|
| `orch_server.log` | 532 stats lines spanning **all four** cells; wave boundaries are stats-line indices W12 `0–222`, W20 `222–355`, W28 `355–469`, W16 `473–532` |
| `gen_w12.log` | the complete cohort, ends `[done] 12 games … 1309.5s` |
| `gen_w16/20/28.log` | header + orch attach line; these cells were killed/crashed before any progress print, so **all** their numbers come from `orch_server.log` |
| `sampler.tsv` | 5 s samples of `epoch · GPU power.draw · loadavg · matched-proc count` |
| `w*.t0`, `w*.orchline*` | per-cell wall-clock and orch stats-line boundary markers |

Wave boundaries are recorded as line indices rather than timestamps because the orch stats lines are
untimestamped; `w*.orchline*` were written at each cell transition so the attribution is exact.
