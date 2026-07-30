# TEACHER H2H — pre-flight smoke + full-cell launch record (band 94e9)

> **STATUS: SMOKE COMPLETE, FULL CELL RUNNING (launched 2026-07-30 02:08 EDT).** Prereg:
> [TEACHER_H2H_PREREG.md](../../scripts/distill_flywheel/TEACHER_H2H_PREREG.md) (`f2e11ca`,
> committed before the first game; stale-banner note `ceb49a9`). Smoke games are **throwaway**
> (scratch band 99e9, never harvested) — no `results.csv` row, no band consumed, nothing promoted.

## Pre-flight smoke — 10 games at PRODUCTION knobs, W12

Same sims / k_dets / opponent budget / leaf / exact-K / orch-or-not as the full cell; only the
game count and the seed band differ (the house pre-flight rule).

| arm | budget | measured | note |
|---|---|---|---|
| **candidate** (harness calls this side `champ`) | net-prior k4×688 = **2752** | **15.55 s/move** (14.12–16.69) | CL-067 iter_03 POLICY priors + FROZEN curve125 leaf, via carc-orch |
| **opponent** | champion k8×1376 = **11008** | **12.71 s/move** (7.96–17.71) | the champion of record, run **sequentially** per game |
| cost ratio | candidate / opponent | **1.22×** | the ¼-budget candidate costs *more* per move than the 4× classical opponent |
| per-game wall | both sides, they alternate within a game | **1973 s = 32.9 min** | mean over all 10 completed games |

⚠️ **Field-name trap, and it bites in this harness specifically:** `champ_prefix_secs` is the
**CANDIDATE's** time — the harness names the candidate side "champ" (same inversion that produced
three wrong tallies on 2026-07-18, memory `feedback_verify_numbers_before_reporting`). Reading it
as the champion's cost would invert the whole cost picture.

### What the smoke confirmed, and what it corrected

- ✅ **`parallel_workers: 8` buys nothing here — confirmed by measurement.** The opponent came in
  at 12.71 s/move against PRODUCTION.yaml's **13.7552 s/move sequential** figure for k8×1376, not
  its 2.1595 s/move 8-worker desktop figure. The eval farm is *game*-parallel, exactly as
  pre-registered. Any estimate built on 2.16 s/move is ~6× optimistic.
- ❌ **The proposal's cost line was wrong and is now replaced.** `PROPOSED_TEACHER_H2H_CELL.md`
  estimated "opponent ~2.2 s/move + candidate ~5.6 s/move → ~6–8 h two-box". Measured is
  **12.71 + 15.55 = 28.26 s/move**, i.e. ~3.6× the assumed per-move cost. The pre-flight rule
  earned its keep here: the cheap estimate would have mis-scheduled the night by ~9 h.
- ✅ Both sides curve125, `leaf_hash=a36d2e15a3b3d71d` / `frozen_config_hash=6dfffd57051690f2`,
  logged per side. TorchScript export fp-parity gated (`max|dpriors|=7.03e-06`,
  `max|dvalue|=1.14e-04` at k=37).

### Projected wall for n=400 (from the measured 32.9 min/game)

| W | local-only | with the laptop joined |
|---|---|---|
| 12 | 18.3 h | ~9.1 h |
| 16 | 13.7 h | ~6.9 h |
| **20 (chosen)** | **11.0 h** | **~5.5–6.1 h** |
| 24 | 9.1 h | ~4.6 h |

**W = 20 chosen, and the basis is stated honestly: this is a judgment from the smoke's headroom,
not a swept optimum.** At W12 with 10 games in flight the box sat at loadavg ≈ 5–7 of 32 threads,
because only the opponent half of each game is CPU-bound (12.71 s of each 28.26 s move-pair
≈ 45% duty cycle) while the candidate half blocks on the orch. So expected concurrent CPU demand
at W20 is ≈ 9 cores of 16 physical — real headroom. W24/W28 were *not* taken: that would be a
2–2.3× extrapolation off a single measured W point, which is the "bench, then extrapolate, then
commit" rule's exact failure mode, and a per-game-wall regression would erase the nominal gain.

## Full cell — LAUNCHED 2026-07-30 02:08 EDT

```
band 94e9 · n=400 deck-paired (200 decks) · OW=20 · ORCH_FWD=4 · ORCH_MAX_BATCH=20
OPP_K_DETS=8 OPP_SIMS=1376 · --exact-k 2 --k-dets 4 --sims 688
out /mnt/c/carc-shared/teacher_h2h_94e9/n400_paired_b94e9 · --shared-claim --no-results-csv
OMP/MKL/OPENBLAS=1 to the server · nice -n 19 · setsid-detached
```

- cell script (on the share, so the watchdog survives a session death):
  `teacher_h2h_94e9/cells/h2h_full.sh`
- watchdog: `teacher_h2h_94e9/cells/h2h_watchdog.sh`, armed 02:09 (pid 62225). **Eval-shaped:**
  keys orphan-clearing on `.json`, refuses to call DONE below n=400, and **parks a short
  `summary.json` as `summary_nNNN_PARTIAL.json`** so a relaunch is not silently a no-op — the eval
  path fails OPEN (a stranded claim yields a plausible summary at the wrong `n`).
- **ETA ~11 h local-only ⇒ ~13:10 EDT.** With the laptop moved onto this cell: ~6 h ⇒ **~08:15**.

## LAPTOP JOINED the same cell — 02:27 EDT (approved swap)

Coordinator GO on the recommendation: gen is premise-gated by Joshua's own 01:25 logic, so a 13:10
premise answer would have inverted the priority he set. The laptop moved off gen and onto this cell
via `--shared-claim`.

**Laptop gen stopped cleanly first:** its gen watchdog disarmed FIRST (pid 106774) so it could not
relaunch behind the kill, then gen main 106724 + all 17 spawn children by exact pid, then its orch
+ SHM segment, then **16 stranded laptop claims cleared → 65 npz = 65 claims at parity.** The rodv3
gen pool is parked losslessly at **65/300** (it had advanced 33 → 65 while the laptop ran, i.e. the
laptop contributed 32 games in ~43 min ≈ 81 s/game effective — confirming its sweep's "peer of the
local box" finding).

**Laptop W = 12, and it is sized from a MEASUREMENT, not a guess.** The live local arm was sampled
first: **537 MB RSS per eval worker** (20 workers + main + orch = 11.3 GB). Against the laptop's
~10 GB available:

| W | workers | + orch | total | verdict |
|---|---|---|---|---|
| 12 | 6.4 GB | ~1.5 GB | **~7.9 GB** | ~2 GB headroom — chosen |
| 16 | 8.6 GB | ~1.5 GB | ~10.1 GB | the entire budget, zero headroom |

The laptop has a documented **WSL-VM-teardown-under-memory-pressure** failure mode (a Windows-side
OOM, invisible in `dmesg`), so the arm additionally runs inside
`systemd-run --user --scope -p MemoryHigh=8G -p MemoryMax=9G`: a breach now fails **CLOSED** (the
cell dies and `--shared-claim` resumes it) instead of taking the VM down with it.

Verified after launch: 12 workers busy at 45–50% CPU, **549 MB RSS each** (matching local's 537 MB
— the extrapolation held), orch 1.27 GB, 6 GB still available, own watchdog armed
(`h2h_watchdog_laptop.sh`, host-scoped orphan-clearing so it can never touch local's live claims;
summary-parking is deliberately left to the local watchdog alone — two boxes racing one file is
worse than the problem).

**Revised ETA: ~09:15–09:45 EDT** (32 workers nominal; the laptop's 8P+8E topology makes its 12
workers ≈ 10 local-equivalents, and it joined 19 min after local). This is **later than the ~08:15**
quoted when recommending the swap, and the reason is a deliberate trade: that figure assumed laptop
W16, which the RSS measurement showed has no memory headroom on this box.

### ⚠️ Verify before reading any number

`n` in the final `summary.json` **must equal 400**. A short cell is indistinguishable from a real
one downstream except by its `n`.

## Smoke outcome — deliberately NOT interpreted

The 10 scratch games came back candidate 8/10, mean diff +6.0. **This is not evidence and is not
being treated as any.** n=10 is ±110 elo, it is a non-harvested scratch band, and the whole reason
this cell exists is that two ±1σ derivations disagree in sign. It is recorded only so nobody later
finds the scratch directory and mistakes it for a result.

## Cross-references

- Turn-1 gen is **parked losslessly at 65/300** (claims at parity on both hosts). It resumes on
  whichever box frees first *after* this cell's verdict and Joshua's morning read. The turn-1
  **gate remains NOT funded**.
- **Air incident (non-critical):** its gen-side W sweep completed W4 — 4 games / 479 s wall =
  **119.75 s/game effective, 30.1 games/h** (vs the runbook's ~35 games/h planning figure inferred
  from eval-shaped data) — started W6 at 01:09, and the box became **unreachable from ~02:21**
  (`ssh: connect … port 22: Connection timed out`), most likely asleep despite the fresh untimed
  `caffeinate -dimsu` wrapping the sweep. Its results are on its own disk and lose nothing by
  waiting. Not chased: the Air is held out of the corpus and contributes nothing to the critical
  path. **Open question for the morning:** the Air slept mid-run *again* (it also slept at 377/400
  during the 2026-07-29 ANE cell) — `caffeinate -dimsu` is evidently not sufficient on this box,
  and that is worth understanding before any long Air run is funded.
- The stale `PROD_KNOBS` banner defect (`eval_fair_puct.py` pinned at the pre-promotion k4×688) is
  documented in the prereg and is **not** fixed yet — main-tree source, live cell.
