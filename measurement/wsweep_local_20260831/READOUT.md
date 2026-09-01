# Post-flattening W re-sweep — LOCAL half, ARB-ON-BOTH-SIDES cell shape

**STATUS: COMPLETE (2026-08-31).** Throughput-only; **no claim, no band, no elo, no
results.csv row.** Every cell played THROWAWAY seeds under a `SMOKE_` out-subdir, so
nothing here is adjudicable. Companion to
[`measurement/wsweep_laptop_20260831/READOUT.md`](../wsweep_laptop_20260831/READOUT.md)
(the laptop half, run this afternoon), whose method this copies.

## ⭐ SETTLED: **W_LOCAL = 30**

Launch every subsequent local round at `--workers 30`.

The throughput curve **rises steeply to 30 and is then flat**: W30 ≈ W36 to within
0.31% (z = 1.41, CI straddles zero). W30 is both the **smallest W on the measured
plateau** and — unlike the laptop half — the answer the settle rule's *letter* gives
too, so there is no letter-vs-intent tension to adjudicate here.

**This confirms the standing default rather than moving it.** `docs/CLUSTER_OPS.md`'s
fourth profile already carried local `W*=30 (peak W36)`; the peak has now collapsed
onto the settle, so 30 is no longer a compromise below a real peak — it *is* the
plateau's cheap end. No downstream re-sizing is needed.

> ⚠️ **The one thing this ladder does not resolve, disclosed rather than glossed.**
> The grid below the plateau is coarse: nothing was measured in the open interval
> (24, 30). W24 is **9.9% below peak**, far outside the 5% band, so it is not a legal
> settle — but an unmeasured point such as W27 could conceivably land inside the band
> and would then be a smaller legal settle. It was deliberately not bought: it could
> only shave ≤6 workers **at equal throughput** on a box that is an exclusive tenant
> for these rounds, while costing ~33 min of box time and moving W off the incumbent
> default that downstream timeouts are already sized against. **If the orchestrator
> wants the rule's smallest-W letter pushed to a finer grid, W27 is the point to buy.**

## Workload — the H2H's exact shape

Verified off the **emitted `manifest.json`**, not restated from the command line:

| | |
|---|---|
| harness | `scripts/classical_search/eval_fair_puct.py`, `--opponent fair-champion`, `--paired` |
| budget | **k16×1376 = 22016 BOTH sides** (`opp-k-dets 16`, `opp-sims 1376`) |
| tie arbiter | **ARMED BOTH SIDES**, deployed dict: B=64, J=4, argmax, salt `tiearb2-deploy-v1`, eps 0.0, phase_gate `all` (manifest `cand_tiearb` **and** `opp_tiearb`) |
| candidate-only knob | `--cand-fpu-reduction 0.2` (manifest `config.cand_search`) |
| rules | `fixed_v1` + `CARCASSONNE_FIX_R9=1` (`leaf_env.CARCASSONNE_FIX_R9: "1"`) |
| backend / endgame | rust, `rust_threads=1` per worker (FARM), `--exact-k 2` marginalized |
| leaf | `a36d2e15a3b3d71d` (curve125), both sides |
| wheel | `carc_rs-0.1.0`, binary sha **`a9bb2311ab9a635d` — byte-identical to the laptop half's** |
| src rev | `0d0cb9b6-dirty` (local main tree). The wheel's build label reads `+0d0cb9b645f5` where the laptop's read `+395b76700ab1`; the **identical binary sha** across the two labels is direct confirmation of the laptop readout's claim that rust was untouched between those revs. |
| seeds | throwaway `168999998000`–`168999998038` (39 decks × 2 seatings = 78 games) |

Seed range is disjoint from the laptop half's `167999999000` block, inside throwaway
convention, and never a claim band.

## Method — identity-gated, deck-PAIRED (copied from the laptop half)

⚠️ **The single most important design choice.** Per-game wall time varies ~40%
deck-to-deck and seat-to-seat. With **disjoint** seed ranges per W point the SEM on a
~40-game point would swamp the 5%-of-peak settle threshold. So **every W point plays
the SAME 78 games from the SAME throwaway deck set** (games are bit-identical at any W,
so this costs nothing), making the ladder a deck-paired contrast. Realized SEM:
**2.1% per point**, and the paired per-game contrast resolves a 9.5% difference at
**z = −50**.

Estimators are byte-identical to the laptop analyzer (the order-statistic trap is
handled by never reading a rate off the earliest finishers):

- **P (primary)** — `3600·W / mean(elapsed_s)` over the **steady set** = completions
  ordered by finish time, indices `[0, n−W−1]`, i.e. the **drain** (last W completions)
  dropped. The pool is saturated from t=0 because n=78 ≫ W, so there is no ramp to drop.
  Restricted to the games common to every point's steady set (**42 games**).
- **A** — same but over each point's own steady set (unpaired).
- **satur** — wall-clock rate from launch to the last steady completion.
- **gross** — `n / point_wall_s`, drain included; context only.

### Adaptation record (the merged laptop driver was NOT edited)

`wsweep_driver_local.sh` is a copy of `measurement/wsweep_laptop_20260831/wsweep_driver.sh`
with four changes, all recorded in its header; the workload knobs, census gate, sampler
and estimators are byte-identical.

1. `SHARE` `/mnt/carc-shared` → `/mnt/c/carc-shared` (local mount path).
2. `LOGDIR` → `$SHARE/wsweep_local_20260831`.
3. Cell name `SMOKE_WSWEEP_W$W` → **`SMOKE_WSWEEPLOC_W$W`**.
4. Seed base → `168999998000`.

> ⚠️ **Change 3 was mandatory, not cosmetic — it is a caught near-miss.** Both boxes
> mount the **same** share, the laptop half had already written
> `SMOKE_WSWEEP_W{18,22,26,28,30}` there, and this driver `rm -rf`s its own out-dir at
> the top of every point. Running the local ladder under the laptop's names would have
> **silently deleted the laptop half's raw per-game records at the shared W=30 point**,
> destroying evidence behind an already-merged readout.

## Points

| W | paired g/h | SEM | steady g/h | satur g/h | gross g/h | s/game | % of peak | loadavg | procs in R | min free MB |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 24 | 146.4 | 2.14% | 144.5 | 111.8 | 125.4 | 24.6 | 90.1% | 24.01 | 24 / 24 | 38085 |
| **30** | **162.0** | 2.13% | 160.9 | 125.5 | 143.3 | **22.2** | **99.7%** | 30.03 | 30 / 30 | 37975 |
| 36 | 162.5 | 2.16% | 162.5 | 100.5 | 137.4 | 22.2 | 100.0% | 36.05 | 36 / 36 | 37453 |

All three points `rc=0`, 78/78 games each. Wall per point 2240 / 1960 / 2043 s. Memory
was never remotely a constraint (≥37.4 GB free of 42.1 GB at every W) — the laptop's
RAM-floor concerns have no analogue on this box.

> ⚠️ **Do not read the settle off the `gross` column — it is context-only, and it lies
> here in a specific, reproducible way.** At fixed n=78 the W36 point looks *4% slower
> than W30* in gross terms (137.4 vs 143.3 g/h; 2043 s vs 1960 s), which invites the
> conclusion that the W36 edge **reversed**. It did not. Gross includes the **drain**,
> and the drain is 36 of 78 games at W36 versus 30 of 78 at W30 — the wider pool spends
> proportionally more of a *short* run under-loaded. The deck-paired estimator, which is
> the entire reason this ladder is identity-gated, puts W30 vs W36 at **−0.31%
> (z = −1.41)**: flat. The honest verdict is that the edge **compressed to zero**, not
> that it inverted. The gross artifact scales away as n grows and must not be carried
> into a long-run projection — though it is one more reason nothing is *gained* by
> taking W36 over W30.

### Paired per-game contrasts (log-ratio, 95% CI)

```
W24 vs W30:  −9.48%  [−9.84, −9.13]   z=−49.90   n=48
W24 vs W36:  −9.87%  [−10.40, −9.34]  z=−34.47   n=42
W30 vs W36:  −0.31%  [−0.74, +0.12]   z= −1.41   n=42   ← plateau
```

The peak is **bracketed**: rising hard 24 → 30, flat 30 → 36. The extension trigger
(*extend past 36 only if still rising >2% point-to-point*) **did not fire** — 0.31% is
both under the bar and statistically indistinguishable from zero — so the ladder stops
at 36 and W36 is not an unbracketed endpoint being mistaken for a peak.

## Prior check — did local's pre-flattening W36 edge survive?

**No. It is gone.**

The prior is recomputed here **with this sweep's own paired estimator** rather than
quoted from a gross-wall number, so the two eras are compared like with like. Prior
evidence: `/mnt/c/carc-shared/wgap_profile/pt_A_w{8,14,22,30b,36}`, 2026-08-30,
**pre-flattening**, budget **11008** (k8×1376), arbiter effectively **off** (phase_gate
`none`, 0 fired plies), n=W single wave:

```
  W   n   wall_s   gross g/h   perGameRate g/h   mean_el_s   conc_running_mean
  8   8    214.9       134.0             176.9       162.8         5.98 / 8
 14  14    246.1       204.8             265.7       189.7        10.61 / 14
 22  22    290.6       272.5             358.8       220.8        16.45 / 22
 30  30    340.5       317.2             414.3       260.7        22.56 / 30
 36  36    380.1       341.0             424.9       305.0        28.63 / 36
```

```
PRE-FLATTENING  paired W36 vs W30:  +4.80%  [+4.01, +5.59]  z=+12.24  n_paired=30
POST-FLATTENING paired W36 vs W30:  +0.31%  [−0.12, +0.74]  z= +1.41  n_paired=42
```

**The post-flattening CI excludes the prior point estimate outright.** The edge
compressed from **+4.80% → +0.31%**.

⚠️ **"Compressed", not "reversed."** The gross-wall column tempts the stronger claim
that W36 is now ~4% *worse* than W30 — see the warning under the points table; that is
a drain artifact of n=78, not a sign change. Nothing in this sweep says oversubscription
became *harmful* on local. It says it became **free and worthless**, which is exactly
what the laptop half found.

**What moved — the mechanism, measured, and it is the laptop's mechanism exactly:**

- **Pre-flattening the pool was never fully runnable**: 16.45/22, 22.56/30, 28.63/36
  processes in `R` at any instant — between 5.5 and 7.4 workers' worth of the pool
  stalled. That stall is precisely the slack oversubscription exists to hide.
- **Post-flattening the pool is fully runnable at every W tested**: median processes in
  `R` = 24/24, 30/30, 36/36 — exactly W, at every point. The DRAM stall is **gone**.
- **And with it, the oversubscription edge.** Past ~the thread count the curve is flat:
  30 → 36 buys +0.31% (|z| = 1.4, CI ±0.4%).

**⇒ The laptop half's prediction generalizes to local.** Both boxes now show the same
shape: **throughput rises with W up to roughly the box's thread count and is flat
thereafter; oversubscription buys nothing.** Laptop: 24 threads, plateau from W26
(1.08× threads). Local: 32 threads, plateau from W30 (0.94× threads). The two settles
differ in absolute W only because the boxes differ in width.

⚠️ **What is NOT comparable across the two eras: absolute rates.** The prior ran at
11008 with the arbiter off; this sweep runs at 22016 with the arbiter armed on both
sides. Only the **W-shape** transfers. (Per `docs/CLUSTER_OPS.md`'s cost-model rule, the
prior's absolute ms/move figures are era-stale and are not carried here at all.)

**Cross-box planning number** (same binary, same cell shape, same estimator, both
throughput-only): local at W30 = **162.0 g/h** vs laptop at W26 = **135.4 g/h**, i.e.
local ≈ **1.20×** the laptop for the 22016 arb-on-both-sides workload.

## Census honesty

- **Local was an exclusive tenant for all three points.** Census by **FULL ARGS**
  (`ps -eo pid,etime,pcpu,args`), never `-C python`/comm, before each point; zero busy
  compute processes found, loadavg 0.05–0.25 immediately pre-launch. The driver's own
  gate (abort the point if any `python|carc` process exceeds 50% CPU) was armed
  throughout and never fired. Median loadavg during each point equalled W to within
  0.05, and processes in `R` equalled W exactly — i.e. the box was running this and
  nothing else.
- **The laptop was busy with the pinned H2H round — stated even though it is irrelevant
  to local timings, because they are different machines.** ⚠️ Two corrections to the
  brief's premise, both established **read-only from the share** (the laptop was never
  sshed to): the H2H round **finished during this sweep** — `fpu_h2h/CELL_H2H_FPU02/`
  carries a `DONE` marker, a `summary.json` and 800 game records, last written
  **01:47:35Z**, which is **23 minutes into the W24 point**. So the laptop was busy for
  only the opening stretch of point 1 and **idle for the whole of W30 and W36**.
- **The one conceivable coupling was tested, not asserted away.** The share is hosted on
  the local box's `C:`, so laptop record-writes land as SMB traffic on local. Splitting
  W24's paired steady games by whether they completed before or after the laptop went
  idle: overlap subset `−9.58% [−9.94, −9.21]`, clean subset `−8.08%` (**n=3 only** — the
  clean subset is too small to carry weight, and its games are fast decks, mean elapsed
  473 s vs 601 s). Both are an order of magnitude from zero; the W24 < W30 conclusion is
  unaffected. **Decisively: the settle-deciding contrast, W30 vs W36, ran entirely after
  the laptop went idle and carries no overlap at all.**

## Artifacts

- `points.jsonl` — per-point wall clock, rc, game count, timestamps
- `POINTS.json` — the estimator table above, machine-readable
- `PAIRED_DELTAS.txt` — all three pairwise paired contrasts
- `wsweep_driver_local.sh` / `analyze_wsweep_local.py` / `paired_delta_local.py` — the instrument
- raw per-game records: `/mnt/c/carc-shared/fpu_ladder/SMOKE_WSWEEPLOC_W{24,30,36}/`
  (throwaway; the `SMOKE_` prefix keeps them out of every adjudication)
- driver logs + resource samplers: `/mnt/c/carc-shared/wsweep_local_20260831/`
