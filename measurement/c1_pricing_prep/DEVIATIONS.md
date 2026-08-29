# c1_pricing_prep — execution-layer deviations

## C1-D1 — 2026-08-29 ~05:1xZ: preflight crashed on an API guess (fixed pre-launch)

`preflight_c1.py:77` called `prof.r9_env_on()` — but `r9_env_on` is a MODULE
function in `carcassonne_ai.rules_profile`, not a `RulesProfile` method. The
design agent disclosed it could not execute the preflight pre-freeze (boxes
saturated by the A1 round); first execution was in the post-A2 window as its own
DESIGN instructed. One-line fix at the site, commented; execution-layer,
statistics-blind (an env-latch health check upstream of any statistic).

Post-fix result: **PASS, zero drops** — G-LEGAL drop_rate 0.0 in every stratum
(farm_capture 14/14 retained); the legal-mask epoch hazard the design flagged
did not materialize. VOID_TRIGGERED: [].

## C1-D2 — 2026-08-29 08:13Z: the smoke's ETA gate divided by a ONE-PROCESS rate

**Every substantive smoke gate PASSED on the first live run** — `SMOKE_RESULT.json`
carries `"fails": []`: 4/4 unit files emitted, `pair.status` `OK` on all four,
arm-map correct on all four (`played_action == c1_action`,
`counterfactual_action == champ_action`), all worlds ≥ 16 (30, 31 from the
`invasion` ply's 16–31 range; 46, 47 from the `farm_capture` ply's 16–47),
8/8 arms `OK`, `profile == fixed_v1`, and the CRN witness matched
(`dec=129/129` on the first unit — both arms took the same number of
continuation decisions).

**The one failure was the projected-ETA gate, and it is arithmetic, not the
world.** The smoke's four units are **one chunk** — `CHUNK=4` and `split -l 4`
on a four-line file produce a single chunk file, so `run_c1.sh` starts exactly
**one** `continue_plies.py`. Its own driver log prints it: `units=4 chunks=1`,
and `ps` showed one driver plus one arm child at 99% of a single core. The base
pass, by contrast, runs **W chunks concurrently**. The gate divided the whole
base block by that **single-process** rate:

```
rate  = cp / elapsed = 660 / 826 = 0.799 cont-plies/s     [ONE process]
proj  = 323360 / 0.799 / 3600    = 112.41 h              [as shipped]
```

So it answered *"how long would this take on ONE CORE"*, not *"...on THIS
BOX"* — the question its own field name
(`projected_base_block_hours_THIS_BOX_ALONE`) asks — and overstated the wall by
about a factor of `W`.

**Ground truth before the fix.** The measured quantities are not in dispute and
are **unchanged**: `cp = 660`, `elapsed = 826 s`, one-process rate 0.799. Only
the projection from them was wrong. Scaling by the box's own concurrency, de-rated
by the repo's **measured** fleet efficiency (phasegate DESIGN §6.4: 36 nominal
workers delivered 23.66 worker-s per wall-second = **0.66**; A1/A2 held it on this
box, where W30 per-worker cost ran ~17% above the laptop's W22):

| reading | value | vs the 8 h gate |
|---|---:|---|
| as shipped (one-process) | 112.41 h | FAIL |
| corrected, **local** W=30, whole block alone | **5.68 h** | PASS |
| corrected, **laptop** W=22, whole block alone | **7.74 h** | PASS |
| corrected, each box's **actual share** (`BOX_PLAN_base.json`) | local 3.28 h / laptop 3.27 h | — |

⭐ **The gate passes on its merits, not by loosening it: the 8 h bar is
untouched**, and the projection clears it on either box even under the
conservative 0.66 de-rate. The projected base-pass wall is **3.28 h** (the max of
the two boxes, balanced to 0.01 h by `plan_c1.py`'s capacity weighting) against
the design's 4.40 fleet-hour estimate — i.e. the design was conservative.

**The fix.** `smoke_c1.sh` now takes `W`, reports the one-process rate and the
box rate separately, and gates on the box rate. **It was NOT re-run to
manufacture a green:** a resumed smoke is a *vacuous* pass — the units are
already on disk, the runner skips them, `elapsed` collapses to seconds while `cp`
still sums the emitted files, and the rate goes to infinity. A second guard now
**fails** the smoke on `elapsed < 60 s` for exactly that reason. The corrected
verdict above is computed from the **already-measured** `cp` and `elapsed`, which
is the only honest way to re-read a timing.

**Statistics-blind.** The ETA gate is a launch-scheduling guard. It touches no
bar, no branch, no estimand and no emitted statistic; `READ_RULE.md`'s readouts
and `adjudicate_c1.py` never read it. ⛔ The four smoke units' outcome values are
real base-pass data and are **not read here** — they belong to the frozen read
rule, and the resumable base pass keeps them.
