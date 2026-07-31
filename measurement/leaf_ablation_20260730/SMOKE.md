# Leaf-ablation SMOKE — measured s/game and the ETA arithmetic

> Written from disk 2026-07-30 23:2x, BEFORE the real launch. Numbers below are measured,
> not extrapolated from the C5/C7 reference cells.

## What was smoked

House rule: smoke at **PRODUCTION knobs, only the game count differs.** So the smoke ran the
real launcher, the real cell (`meepleoff`), the real harness, the real search config — and
changed exactly two things: `--n 16` instead of 400, and a throwaway seed band `9.69e10`
instead of the claimed `9.60e10`.

```
bash scripts/classical_search/leaf_ablation_launcher.sh 16 local \
     --cells meepleoff --n 16 --band 96900000000 --out-sub-prefix ablsmoke_
```

Local 5900XT box only, W16, `nice -n 19`, detached. Confirmed at launch: 16 worker processes
at ~99% CPU each, loadavg 16.6. Harness banner confirmed the candidate leaf was live —
`rr_puct2750_vs_puctchamp2750_k2-leaf15477283` (`15477283…` = the `meepleoff` leaf hash).

## Measured

| quantity | value |
|---|---|
| games | 16 / 16 completed |
| **mean s/game (local, W16)** | **570 s** |
| wave duration (max, = the 16th game) | 683 s |
| spread of the 16 completions | 485 s … 683 s |
| candidate/champion cost ratio | **0.99** — the knockout is compute-neutral, as designed |

**The mean is taken over all 16 completed records, not the first few.** All 16 workers start
together, so the first completions (485 s, 489 s) are an order statistic — the minimum of 16
draws — and using them would have been ~17% optimistic. This is the ETA trap the memory note
names; 570 s is the mean, 485 s is the trap.

## ETA arithmetic

Local throughput: `16 workers / 570 s` = **101.1 games/h**.

Laptop throughput is *assumed*, not measured tonight: the CL-067 equal-wall-clock gate measured
the laptop at a **~1.39× clock ratio** vs local (`governance/BAND_REGISTRY.csv` rows 82e9/84e9),
so `570 × 1.39 ≈ 792 s/game` → `16 / 792 s` = **72.7 games/h**.

```
combined      ≈ 101.1 + 72.7          = 173.8 games/h
per cell      = 400 games / 173.8     = 2.30 h/cell
6 cells       = 6 × 2.30              = 13.8 h   ← overflows the window
window        ≈ 10.5 h (23:30 → ~10:00)
cells landing = 10.5 / 2.30           = 4.6      ← 4 complete + a 5th partial
```

**Expected morning state: cells 1–4 complete (`meepleoff`, `oppanticoff`, `anticoff`,
`selfanticoff`), cell 5 (`meepleflat`) partial, cell 6 (`capoff`) not started.** That is the
reason for the priority order — `n=400` completes per cell rather than spreading thin, so the
morning read is whole verdicts, and the `--shared-claim` queue resumes the remainder with zero
replay.

The laptop ratio is the soft number here. If the laptop is faster than 1.39×, a 5th cell lands.
The real combined rate will be visible from the first cell's record count within ~30 min.

## CONFIRMED live rate (measured on the real run, cell 1, 2026-07-30 23:44)

The prediction held. Measured on `abl_meepleoff` after a full two-box wave:

```
32 records in 703 s  =  163.9 games/h   (predicted 173.8 — 6% optimistic)
projected per cell   =  400 / 163.9     =  2.44 h/cell   (predicted 2.30)
window from launch 23:32 to ~10:00      =  10.47 h
cells landing        =  10.47 / 2.44    =  4.3
```

Both boxes are genuinely contributing — live claim census **32 local / 24 laptop** (the laptop
runs slightly behind, so the CL-067 1.39× ratio was pessimistic but directionally right).

**Morning expectation, unchanged from the prereg: cells 1–4 complete (`meepleoff`,
`oppanticoff`, `anticoff`, `selfanticoff`), cell 5 (`meepleflat`) partial, cell 6 (`capoff`)
not started.** Cells 5–6 resume from the `--shared-claim` queue with zero replay.

## Note on W16

W16 is the authorized setting (Joshua: *"both boxes, work stealing, w16"*) and is what was
smoked. For the record, it is **below** the C7 net-free classical convention of W~30 local /
W~22 laptop (`scripts/classical_search/c7_s1_launcher.sh` header) — the local box is 16C/32T, so
W16 leaves hyperthreads idle. If W30 local scaled linearly it would buy roughly `+88 games/h`
→ ~1.5 h/cell → all six cells inside the window. **Not changed unilaterally** — flagged for
Joshua as a knob worth re-benching, not applied.

## Smoke hygiene

The smoke's aggregate step wrote a `results.csv` row under the REAL `exp_id`
(`abl_meepleoff_vs_puctchamp2750_k2`) carrying `n=16` from the throwaway band — the launcher's
primary role aggregates without `--no-results-csv`. **That row was deleted before the real
launch**, `ABL_PROGRESS.tsv` was reset to its header, and the smoke output dir was renamed to
`_SMOKE_THROWAWAY_ablsmoke_meepleoff` so it can never be mistaken for a cell.

⚠️ The smoke's own numbers (4W–12L, elo −190.8 ± 100.3 at n=16) are **NOT a result** and are
recorded here only as smoke telemetry. n=16 is far below any reporting threshold, and the band
is a throwaway. The pre-registered cell is n=400 on band 9.60e10; nothing about the direction
seen here may be cited until that lands.
