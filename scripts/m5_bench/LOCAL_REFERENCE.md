# Local reference run — 2026-07-28, 5900XT box

Same bundle, same 60 positions, same code as the M5 will run. Recorded so the M5
numbers have a rung-for-rung comparison instead of a vibe.

**⚠️ The box was LOADED.** The CL-067 equal-wall-clock gate was live throughout
(16 spawn workers, `loadavg` 13.9 / 12.8 / 11.6 on 32 threads). These numbers are
therefore **pessimistic** for the 5900XT and must not be quoted as its clean
single-stream figure. They are a *code-works* reference and an *order-of-magnitude*
anchor, nothing more. A clean 5900XT rerun at a quiet window is owed before any
M5-vs-5900XT claim.

## Measured

Command (run with `nice -n 19`, `PYTHONPATH` cleared):

```
.venv/bin/python bench_champion.py --budgets k1x32
```

| budget | sims/move | leaf path | mean s/move | p50 | p90 | n |
|---|---|---|---|---|---|---|
| k1×32 | 32 | Cython | **0.0403** | 0.0372 | 0.0634 | 58 |

Repeated four times over ~15 min on the same loaded box (all `exact_latches: 0`,
all Cython):

| run | mean | p50 | p90 |
|---|---|---|---|
| 224133 | 0.0403 | 0.0372 | 0.0634 |
| 224904 | 0.0406 | 0.0363 | 0.0623 |
| 225202 | 0.0359 | 0.0330 | 0.0514 |
| 225439 | 0.0374 | 0.0391 | 0.0529 |

Grand mean **0.0386 s/move**, run-to-run spread ±6% — which under a fluctuating
16-worker load is about as tight as this measurement gets, and is the reproducibility
the M5 numbers should be judged against.

By phase (same run):

| phase | mean s/move | p50 | p90 | n |
|---|---|---|---|---|
| meeples | 0.0443 | 0.0389 | 0.0594 | 29 |
| tiles | 0.0364 | 0.0313 | 0.0634 | 29 |

The meeple half costing **more** than the tile half — despite choosing among 2–5
actions instead of 16–30 — independently reproduces
`measurement/ANDROID_WALLCLOCK_MEMO_20260728.md` §2 on a different box at a different
budget. Good sign that the harness is measuring the thing the memo measured.

`exact_latches: 0` — no position reached the endgame solver, as designed.

## Cython vs pure Python

Same 6 positions, same budget, same loaded box, `CARCASSONNE_USE_CY_LEAF=0` for the
second row:

| leaf path | mean s/move |
|---|---|
| Cython | 0.036 |
| pure Python | 0.164 |

**4.5×.** This is the number that matters for interpreting an M5 run: a
compiler-less M5 (pure Python) is not comparable to a Cython 5900XT, and the
`cython.leaf_active` flag in the output JSON is what tells the two apart.

## Provenance (from the run's own JSON)

* champion `puct_priors_v29_bmild_cap8`, agent `FairHeuristicPriorAgent`
* leaf hashes — all three dialects match `governance/PRODUCTION.yaml`:
  `a36d2e15a3b3d71d` / `6dfffd57051690f2` / `158f17ff76adaa02`
* search `c_puct 1.5`, `tau_p 5.0`, `value_norm 15.0`, `leaf_quantize float`,
  `final_select visits`
* `fair_deploy` k_dets 4 × sims_per_det 688 = 2752, `exact_max_k` 2
* env: curve `-10,-5,-1.25,0,2.5,3.75,5,6.25`, `USE_FLAT_LEAF=1`, `OMP_NUM_THREADS=1`
* python 3.13.12, AMD Ryzen 9 5900XT, 44.2 GB

## Runtime estimate for the full ladder

Extrapolated from the k1×32 rung, **not measured** — the larger budgets were
deliberately not run locally while the gate owned the box.

Per-decision cost is close to linear in total sims once the fixed per-determinization
overhead (a board deepcopy + tree setup) is paid, so scaling 0.040 s at 32 sims:

| budget | sims/move | est. s/move | est. for 60 positions |
|---|---|---|---|
| k1×32 | 32 | 0.04 | ~3 s |
| k4×172 | 688 | ~0.9 | ~55 s |
| k4×344 | 1376 | ~1.7 | ~1.7 min |
| k4×688 | 2752 | ~3.4 | ~3.4 min |
| **total** | | | **~6 min** |

Two independent cross-checks on the k4×688 figure: the Android memo measures
**1.7 s/move** on a Pixel 9 Pro at exactly this budget and puts the phone at ≈0.5× a
contended desktop, i.e. a contended desktop at ≈3.4 s/move — the same number the
extrapolation gives.

**So the full ladder is ~6 minutes, not the 20–60 the task sketch assumed.** That is
good news and it changes the recommendation: run it with `--repeat 3` (~18 min) so the
p90 is built from 180 samples per rung instead of 60. On an unloaded M5 expect
somewhere between 2 and 8 minutes for a single pass; budget 30 min of wall clock for
setup + smoke + a `--repeat 3` ladder + the ANE probe.
