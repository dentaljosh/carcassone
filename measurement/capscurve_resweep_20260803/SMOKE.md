# CAPS/CURVE RE-SWEEP — PRE-FLIGHT SMOKE (2026-08-03)

> **Throwaway bands, no `results.csv` row, no band claimed, distinct out-subdir prefixes.
> None of this is a result.** Prereg: [PREREG.md](PREREG.md).

Two passes, both through the real launcher at **production knobs** (only `--n` and the band
differ), local box, worktree code (`CC_REPO`), `--backend rust`, **W30**:

| pass | purpose | cells | n | band | prefix |
|---|---|---|---|---|---|
| **A** | wiring — every cell runs end to end and its manifest proves the rules | all 6 | 4 | `1.03999e11` | `ccsmoke_` |
| **B** | **throughput** — a SATURATED wave (n = W), the number the cost projection needs | `curve100` | 30 | `1.03998e11` | `ccthr_` |

Pass A alone cannot price the run: at n=4 only 4 of 30 workers ever run, so it measures
game *latency* plus process startup, not throughput. Hence pass B.

## Pass A — wiring: 6/6 cells PASS

Per-cell manifest evidence, read off `<SHARE>/capscurve_resweep/ccsmoke_<cell>/manifest.json`:

| cell | profile | `r9_env_ok` | candidate leaf hash | champion leaf hash | cand engine | opp engine | W | sims | K | OpenBLAS |
|---|---|---|---|---|---|---|---|---|---|---|
| `curve100` | `fixed_v1` | **true** | `42af12fce22e1a0f` | `a36d2e15a3b3d71d` | rust | rust | 30 | 2750 | 2 | 1 |
| `curve150` | `fixed_v1` | **true** | `165f45134582c7b4` | `a36d2e15a3b3d71d` | rust | rust | 30 | 2750 | 2 | 1 |
| `cap5` | `fixed_v1` | **true** | `0a7b068d229e6f25` | `a36d2e15a3b3d71d` | rust | rust | 30 | 2750 | 2 | 1 |
| `cap12` | `fixed_v1` | **true** | `771fc59803f86ea2` | `a36d2e15a3b3d71d` | rust | rust | 30 | 2750 | 2 | 1 |
| `oppcap4` | `fixed_v1` | **true** | `f3ca4b52db5a69c3` | `a36d2e15a3b3d71d` | rust | rust | 30 | 2750 | 2 | 1 |
| `oppcap12` | `fixed_v1` | **true** | `a68ab5ebc78d7bf5` | `a36d2e15a3b3d71d` | rust | rust | 30 | 2750 | 2 | 1 |

Every candidate hash matches the PREREG cell table and every one differs from the champion's,
so **each cell demonstrably varied the leaf it claims to vary** — and all six ran with the
profile applied and R9 latched. `SWEEP_PROGRESS_SMOKE.tsv` carries the same two columns
(`profile`, `r9_ok`) for the operator.

**The `rules_profile` block is the load-bearing artifact**, because it is what the pre-fix code
could NOT have produced honestly: before the 2026-08-03 `rust_agent` fix a `--backend rust`
leg stamped `fixed_v1` in the manifest while its mirrors played the engine of record (PREREG
§"the build found a live bug"). `r9_env_ok: true` is the separate D0 check — R9 is env-latched
at import, so the profile can only *observe* it.

Compute neutrality (recorded, not a gate — the design is equal-sims): candidate/champion
`ms_per_move` ratio ranged **0.91–1.06** across the six cells. No cell's knob makes its side
materially cheaper or dearer.

## Pass B — throughput, measured

**30 games, W30, one saturated wave, 241 s end to end.**

| quantity | value |
|---|---|
| mean per-game wall | **110.9 s** |
| median / min / max | 101.4 / 79.0 / **240.2** s (long right tail) |
| mean moves per game | 142.0 |
| mean prefix secs (cand / champ) | 41.7 / 41.1 |
| mean exact-tail secs (cand / champ) | 14.1 / 13.9 |

Three rates, and they differ for real reasons — quote the right one:

- **Steady-state ceiling `W / mean` = 974 games/h.** The harness is claim-driven, so within an
  invocation a worker pulls the next seed the moment it finishes; there is no wave barrier.
- **This wave, end to end: 30 / 241 s = 448 games/h.** Pessimistic by construction — a 30-game
  wave on 30 workers pays the *entire* 240 s straggler once, plus spawn startup and the
  aggregate pass, with nothing to amortise them against.
- **Planning figure: ~800 games/h local.** At n=200/cell the run is ~6.7 waves deep, so the
  straggler and startup taxes dilute ~6.7×: `200 / (200/30 × 110.9 + ~240 straggler + ~25
  startup) ≈ 0.22 games/s`.

### ⚠️ `fixed_v1` + R9 cells are ~1.5× more expensive than F7b's walled cells

On the **identical** wave metric — a saturated wave, games ÷ wall — F7b measured
**670 games/h** (32 games / 172 s at W32) and this run measures **448** (30 / 241 at W30).
Do not carry F7b's cost figures over to a fixed-rules cell. The mechanism is visible in the
per-game record: 142 moves/game under the redraw rule, and a ~14 s/side exact-K tail (F7b
reported 20.3 s/game shared).

### Cost projection (6 cells × n=200 = 1200 games)

| configuration | rate | per cell | whole run |
|---|---|---|---|
| local only (plan) | ~800 g/h | ~15 min | **~1.5 h** |
| local only (floor, wave-limited) | 448 g/h | ~27 min | ~2.7 h |
| two boxes — laptop W26, CL-067 clock ratio 1.39 | ~800 + ~500 = ~1300 g/h | **~9 min** | **~0.9 h** |

The laptop leg is **projected, not measured** — treat the two-box figure as the optimistic
bound and **plan against the local-only ~1.5 h**. Either way this is a sitting, not a night.

### ⚠️ The throughput pass peeked at an effect, and the prereg is not tuned to it

Pass B's `curve100` cell returned **−34.9 ± 63.8 (paired z −1.32)**, 13W/1D/16L, at **n=30 on a
throwaway band**. Reported because operational honesty requires the peek be on the record.

Read it as a **wiring diagnostic, not an estimate**: it is ~2.6× under-powered against this
document's own thresholds, on decks that are not the claim band. What it *does* discharge is
the PREREG's positive-control alarm — the sign is negative and the magnitude is in the right
neighbourhood of the walled prior (**−66.8 ± 17.7, n=400**), which is what you would see if the
rules are reaching the engine and the ×1.25 optimum survives. A `curve100` reading near **zero**
here would have been the stop-and-check signal. Every threshold in PREREG §Power and §Decision
map was written before pass B ran and **none was adjusted after**.

## Conditions

- Local box, `nice -n 19`, `CUDA_VISIBLE_DEVICES=""`, `OMP/MKL/OPENBLAS_NUM_THREADS=1`,
  net-free (no carc-orch).
- ⚠️ A **sibling agent's CUDA net bench** (`carc-net/bench_r`, ~1.2 cores) was live on this box
  throughout both passes. At ~1.2 of 32 threads the effect on a CPU-bound W30 run is small, but
  it is not zero and it is recorded rather than assumed away — the quoted rates are, if
  anything, mild under-estimates.
- Code: worktree at base `06fa067`, `code_rev` stamped `06fa067-dirty` in every manifest (the
  `rust_agent` fix + this run's launcher/cells are the diff).
