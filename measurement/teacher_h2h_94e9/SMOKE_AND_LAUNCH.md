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

### ⚠️ Verify before reading any number

`n` in the final `summary.json` **must equal 400**. A short cell is indistinguishable from a real
one downstream except by its `n`.

## Smoke outcome — deliberately NOT interpreted

The 10 scratch games came back candidate 8/10, mean diff +6.0. **This is not evidence and is not
being treated as any.** n=10 is ±110 elo, it is a non-harvested scratch band, and the whole reason
this cell exists is that two ±1σ derivations disagree in sign. It is recorded only so nobody later
finds the scratch directory and mistakes it for a result.

## Cross-references

- Turn-1 gen is **stopped at 33 banked games** and continues on the **laptop** (W\*=16, joined
  01:38, `33 cached, 267 to play`); the turn-1 **gate remains NOT funded**.
- The stale `PROD_KNOBS` banner defect (`eval_fair_puct.py` pinned at the pre-promotion k4×688) is
  documented in the prereg and is **not** fixed yet — main-tree source, live cell.
