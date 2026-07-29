# CL-067 EQTIME/ANE CELL — read-out skeleton

**STATUS: RUNNING (launched 2026-07-29 14:31 UTC on the Apple M5 Air). PLACEHOLDERS
BELOW ARE UNFILLED — no result exists yet.** Every `<<...>>` is a slot; fill from
`summary.json` and delete this banner when the verdict lands.

This file is the pre-registration + the close-out template in one, written BEFORE the
result so the morning is mechanical. The pre-registration half (§1–§3) is fixed and must
not be edited after the fact.

---

## 1. The question

The equal-wall-clock gate
([NETPRIOR_EQTIME_GATE_20260728.md](NETPRIOR_EQTIME_GATE_20260728.md)) fired branch C
(WASH) on the desktop CUDA batch-1 forward and fixed a reopen condition in §6:

> REOPEN the distilled-net line for deploy when the target device's measured
> `r = forward_ms / search_ms_per_sim` is <= ~1.5.

This cell is the single direct test §6 caveat 1 called for: the netprior agent on the M5
at its own **measured** equal-time budget, with the policy forward on the **Apple Neural
Engine**, vs the deploy champion.

## 2. Configuration (fixed before launch)

| | |
|---|---|
| candidate | fair-netprior, distilled `iter_03` (sha256 `6e2679908d79a76c`), NET policy priors + FROZEN curve125 leaf (value severed), **forward on the ANE** |
| CoreML artifact | `cl067_iter03_policy_fp16.mlpackage`, sha256(tree) `5883aa7f44e59c09`, policy-only, fp16, `CPU_AND_NE`, fixed batch-1 |
| candidate budget | **k4×438** (1752 total sims) |
| opponent | DEPLOY champion, `FairHeuristicPriorAgent`, k4×688 (2752 total) |
| both sides | exact-K 2 marginalized endgame, curve125 leaf `a36d2e15a3b3d71d`, c_puct 1.5, tau_p 5.0 |
| n | 400 deck-paired (200 decks × 2 seats) |
| band | **92e9** (verified unburned vs ledger + 612 share manifests; claimed before launch) |
| box / W | Apple M5 Air (darwin-arm64, 10-core), **W6** |
| code rev | `347566e` (worktree `agent-ae16172e9e13c3dfa`) |

**Why k4×438, and why not the r-model.** Measured at W6 on the day: champion search
**1.0036 ms/sim** (the gate's 0.5741 projection was single-stream and 1.75× optimistic),
ANE forward **0.427 ms** single-stream. Naive r = 0.436 would license k4×479, but that
divides an *uncontended* forward by a *contended* search while six workers serialise on
the one shared ANE. The budget was therefore set from the **direct paired cost ratio**,
which contains every contention effect: k4×395 → 0.9014, **k4×438 → 0.9893**. Per-sim cost
multiple candidate/opponent **1.554×** (desktop CUDA batch-1 was 4.2–5.5×).

**Fidelity precondition (PASSED before launch).** `verify_coreml_evaluator.py`, 60 real
champion-reached positions: policy max-abs **1.113e-03**, legal-argmax agreement
**60/60**, top-5 overlap **1.0000**, ANE batch-1 **0.427 ms** vs torch-CPU 2.537 ms. The
ANE agent is the same player, so this cell measures a **cost intervention**, not a
different agent.

## 3. Pre-registered branches (inherited verbatim from the gate, so the two are comparable)

| branch | condition | meaning |
|---|---|---|
| **A** | both statistics ≥ +2σ | the forward WAS the binding constraint; reopen the line, unpark G3 as "get the forward onto a cheap accelerator" |
| **B** | positive but < 2σ | directionally right, underpowered; a bigger n is justified |
| **C** | both statistics inside 2σ | WASH — the ANE r ≈ 0.44 is not enough either |
| **D** | negative past 2σ | §7 kill: the equal-sims edge survives no realistic cost model; the distilled policy becomes a Phase-5 analyzer asset |

⚠️ The cost guard is part of the verdict. If the measured in-flight ratio falls outside
**[0.90, 1.10]** the cell is NOT equal-time and the elo must not be read as an
equal-clock number.

---

## 4. RESULT — fill from `summary.json`

```
records            <<n>>/400
winrate            <<W>>W-<<D>>D-<<L>>L  = <<wr>>   z <<z>>
elo                <<elo>> +/- <<sigma>>
deck-paired margin <<margin>> pts/deck  se <<se>>  paired_z <<pz>>
cost ratio         candidate <<c_ms>> vs opponent <<o_ms>> prefix ms/move = <<ratio>>
                   -> [0.90,1.10]? <<PASS|FAIL>>
measured r         <<r>>   (forward 0.427 ms / search <<o_ms>>/2752 ms per sim)
integrity          deck_hash mismatches <<x>>/200, timeouts <<x>>/<<x>>,
                   latches <<x>>/400 both sides, leaf a36d2e15a3b3d71d both sides
BRANCH FIRED       <<A|B|C|D>>
```

## 5. results.csv row template (paste, fill, done)

```
distill_strong_iter03_netprior_EQTIME_ANE_k4x438_vs_champ_deploy_b92e9_n400_paired,2026-07-30,base,347566e,400,distill_strong_20260723/ckpt/iter_03.pt,1.5,8,fair-netprior_k4x438_EQTIME_ANE,1752,fair_champion_curve125,1.5,8,heuristic-prior_k4x688_DEPLOY,2752,<<W>>,<<L>>,<<D>>,<<elo>>,<<sigma>>,<<avg_diff>>,/mnt/c/carc-shared/eqtime_ane_netprior_k4x438_b92e9,verdict,"CL-067 EQUAL-WALL-CLOCK REOPEN TEST ON THE APPLE NEURAL ENGINE. Same agent pair as the 82e9 gate arm A, ONE variable changed: the candidate's policy forward runs on the ANE via CoreML (cl067_iter03_policy_fp16.mlpackage sha256 5883aa7f44e59c09, CPU_AND_NE, batch-1) instead of desktop CUDA batch-1. This tests the gate's own pre-registered reopen condition (r <= ~1.5). Budget k4x438 set by a MEASURED direct paired cost probe at W6 (k4x395 -> 0.9014, k4x438 -> 0.9893), NOT by the r-model: r computed from a single-stream forward over a W6-contended search is optimistic because six workers serialise on the one shared ANE. Measured at W6: champion search 1.0036 ms/sim (the gate's 0.5741 was single-stream, 1.75x optimistic), ANE forward 0.427 ms, per-sim cost multiple 1.554x vs 4.2-5.5x on CUDA. Fidelity gate PASSED before launch (60 real positions: policy max-abs 1.113e-03, legal-argmax 60/60, top-5 1.0000) so this is a COST intervention, not a different agent. In-flight cost guard: candidate <<c_ms>> vs opponent <<o_ms>> prefix ms/move = <<ratio>>, <<INSIDE|OUTSIDE>> [0.90,1.10]. Band 92e9 (fresh), 200 decks, <<x>> deck_hash mismatches, <<x>> timeouts, <<x>>/400 latches both sides, both sides leaf a36d2e15. winrate <<wr>> z <<z>>; deck-paired margin <<margin>> pts/deck se <<se>> paired_z <<pz>>. PRE-REGISTERED BRANCH <<X>> FIRED. Readout measurement/classical_search/EQTIME_ANE_CELL_20260729_READOUT.md. PRODUCTION.yaml <<untouched|updated>>."
```

## 6. Six-touch close-out checklist

- [ ] `experiments/results.csv` row (§5)
- [ ] `DECISIONS.md` index line
- [ ] status banner on THIS doc (delete the RUNNING banner, stamp the verdict)
- [ ] `governance/CLAIM_REGISTRY.csv` — CL-067 row flip
- [ ] `STATUS.md` top block
- [ ] `docs/PROGRAM_ROADMAP_2026-07-07.md` line + `docs/LEVER_INDEX.md` ANE row
      (currently reads "BUILT 2026-07-29, NOT RUN")
- [ ] `python3 scripts/doc_lint.py`

## 7. Operational record

| | |
|---|---|
| launched | 2026-07-29 14:31 UTC |
| verified | 6 workers busy, 485.6% aggregate CPU, `0 cached, 400 to play` |
| watchdog | `~/carc-eqtime-ane/cell_watchdog.sh` PID 54741, bounded 12 relaunches, terminates on 400 records |
| ETA | 7.37 h → ~21:53 UTC 2026-07-29 |
| artifacts | `/mnt/c/carc-shared/m5_ane_prep_20260729/` (verify JSON, export sidecar, both cost probes) |

⚠️ **Success is RECORD COUNT, never an exit code** — the gate's ops note 7 found a sibling
harness exiting `rc=1` on a fully successful run. Count `*.json` in the out-dir.
