# PIXEL TIE-ARBITER A/B — `rho_phone` is MEASURED, and the desktop bound was mildly OPTIMISTIC

> **STATUS: ⭐ CLOSED 2026-08-17 — the phone currency is solved. `rho_phone(16)` = **5.976**
> measured, against the **5.520** desktop-derived prediction (**8.3% optimistic**);
> `rho_phone(2)` = **0.742** against 0.690 (7.5% optimistic). Both routes agree to 0.3%.
> ⛔ **COST ONLY.** 0 strength games, no band, no `experiments/results.csv` row, no claim id,
> `governance/PRODUCTION.yaml` UNTOUCHED. This licenses **nothing** — it replaces one
> unmeasured number in the owner's pending flip decision.**

**Owner authorization, 2026-08-17, verbatim:**

> "in the meantime. let's also get some AB testing on pixel. 100.64.4.100:34993"

Artifacts: [results.md](results.md) · [results.json](results.json) · [manifest.json](manifest.json) ·
`runs/*.json` · `samples.csv` · `device_build.txt` · `battery_pack.txt`.
Instrument: `android/tools/battery_bench.sh` + `battery_bench_lib.py` +
`android/app/src/debug/python/carc_bench.py` (docs: [BATTERY_BENCH.md](../../android/tools/BATTERY_BENCH.md)).

## 1. The design problem, and why the identity gate did NOT have to be weakened

The battery bench's load-bearing guard is a **move-hash identity gate**: every arm must
report the same digest over the full applied-action trace, or no energy number is printed.
The tie arbiter **changes the returned action at tied plies by design**, so free-running
armed and unarmed arms diverge at the first pick-change and that gate would — correctly —
abort.

The brief offered two shapes: (a) fixed-position replay, or (b) free-running arms with the
gate downgraded to a same-workload-profile check. **Shape (a) was taken, in a form that
needed no new replay machinery and cost the gate nothing:** the rust agent already records
`last_move()["tiearb_champ_pick"]` — the champion's own `pooled_q_argmax` pick — because
that is the pick-change baseline. So every arm *applies the champion's pick* and the armed
arm still performs all the arbitration work (tie detection, the CRN world set, the
`B × arms` tier-1 playouts) at exactly the positions the champion line visits.

Consequences, all verified: the trajectory is identical across arms, so **the gate keeps its
FULL strength on the very axis whose purpose is to change picks** (PASS — all 9 runs,
`ece55328277e4af5…`); per-move energy and latency are comparable **position for position**;
and per-fired-ply cost is read off the arbiter's own instrumented clock rather than inferred.
The gate passing is also a *finding*: it proves the arbiter does not perturb the champion's
own search — it neither consumes nor advances the agent RNG (CRN-seeded off salt + state
digest + ply, dedicated `tiearb_scratch`).

⛔ **What this does NOT measure: what the arbiter's PICKS are worth.** That is the Stage-2
Phase-B game cell (`G-CONFIRMED`, already read). This bench prices the arbitration *work*.

## 2. The on-device J13 equivalent — the arbiter is LIVE on the phone

A zeroed knob measuring champion-vs-champion is the classic silent null, and the desktop
`carc_rs` in the venv **predates the arbiter**, so no desktop test could have caught a stale
phone wheel. Two on-device assertions were built instead:

* `_BenchSession._assert_tiearb` reads the **RESOLVED** arbiter block back off
  `FairAgentRs.stats()` and compares it field-by-field to the arm's request (and asserts the
  control arm resolved `enabled=False`);
* a run whose armed arbiter fired on **0** tile plies is reported `ok: false`.

**Both passed, and the arbiter demonstrably bit:** resolved `enabled=True, B=16, J=4,
mode=argmax, salt=tiearb2-deploy-v1, eps=0.0`; **39 fired plies / 81 tile plies (0.481)**;
**30 pick-changes at B=16, 27 at B=2**; **`tiearb_errors` = 0** and
**`tiearb_partial_argmax` = 0** across all six armed runs.

## 3. The table

Pixel 9 Pro, `rust_threads: 2`, k8×1376, `fixed_v1`, rust backend — production knobs, arbiter
excepted. 48 moves/run, 3 interleaved reps, seed 424242, unplugged, screen on at min
brightness, `/top-app` verified per run. Battery 30% → 23%.

| arm | J/move ± sd | s/move ± sd | net J/move | fires |
|---|---|---|---|---|
| champion as deployed | 3.177 ± 0.576 | 0.526 ± 0.032 | 2.269 | — |
| + arbiter B=2 | 3.992 ± 0.295 | 0.853 ± 0.009 | 2.536 | 39/81 |
| + arbiter B=16 (the `G-CONFIRMED` config) | 14.741 ± 3.992 | 3.045 ± 0.250 | 9.551 | 39/81 |

| B | s/fired ply (arb clock) | s/fired ply (Δ arms) | ΔJ/fired ply | **`rho_phone` MEASURED** | predicted | added s/game | added J/game | added %batt/game | game wall-clock |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 1.151 | 1.205 | 3.01 | **0.742** | 0.690 | 20.2 | 52.9 | 0.09 | 1.181× |
| 16 | 9.269 | 9.298 | 42.70 | **5.976** | 5.520 | 162.9 | 750.4 | 1.23 | 2.459× |

**The number the owner feels:** at B=16 a tied move takes **1.55 s → 10.8 s** on the phone —
a ~7× pause on ~27% of moves. At B=2 it takes **1.55 s → 2.7 s**.

## 4. What the two clocks and the two rungs buy

* **The two routes agree to 0.3%** (9.269 vs 9.298 s/fired ply at B=16; 1.151 vs 1.205 at
  B=2). The arbiter's internal `tiearb_secs` and the arm-to-arm subtraction are independent
  measurements, so the arms did not drift and the ΔJ column inherits no doubt.
* **Cost is linear in `B` to 0.7%**: 9.269 / 1.151 = **8.056** across an 8× rung ratio.
* **The per-playout constant is stable**: `c_phone` = s/fired ply ÷ playouts/fired ply =
  **0.1883** s/playout at B=16 and **0.1870** at B=2. That is **2.01× the desktop's
  uncontended `c_tier1_rust`** (0.093769 at W=1) and **1.06× its contended W=30 figure**
  (0.178232).
* ⇒ **Why the prediction nearly worked, and why it was still optimistic.** `arbitrate_decision`
  is **single-threaded** (no rayon), so on the phone it runs on ONE core — and one Pixel core
  costs almost exactly what one *contended* desktop worker-second cost, which is the figure
  PHASE_A happened to use. The residual 8.3% miss is ~2.5% from `mean_arms` landing at
  **3.077** vs the `Ā` = 3.0022 the formula assumed, and ~6% from the phone core being
  slightly worse than that coincidence. **The cost model's shape was right; its constant was
  ~8% cheap.**

## 5. Caveats that bound the reading — the bias runs AGAINST the arbiter

* **Opening-phase sampling ⇒ these are CEILINGS.** A tier-1 arbitration playout runs to a
  terminal state, so a tied ply at move 10 is priced over ~130 remaining plies and one at
  move 130 over a handful. Benching the first 48 moves measures **the most expensive
  arbitration in the game**. The opening also ties more: measured **0.271 fires/decision**
  ⇒ an implied `phi` ≈ **19.5**, above the desktop whole-game **17.573** used in the
  projections.
* **`s/move` is not comparable to 1.551.** The session control read **0.526** s/move because
  it sampled the opening. `rho_phone` therefore divides by the **1.551 of record**, which is
  what makes it comparable to 5.520; the session-relative figure (17.6 at B=16) is reported
  in `results.md` beside it and is **not** the number to quote.
* **`baseline %batt/game` = 0.37% is a LOWER bound** for the same reason — it is referenced
  to this session's opening-phase J/move, and there is no whole-game J/move of record to
  substitute. The *added* % is on firmer ground (it is driven by fires, counted per game via
  `phi`), and its ratio to the baseline is consequently the most pessimistic framing.
* **n = 3 reps/arm.** Enough to separate arms differing by 100s of percent, not to resolve a
  few percent. The J/move sd at B=16 (±3.99 on 14.74) is the loose one; the *latency* numbers
  are tight (±0.25 on 3.045) and the arbiter-clock route is tighter still.
* **Android preview channel** — `device_build.txt` records `ro.build.fingerprint`; this phone
  rides a channel that will change under us.

## 6. What this does and does not license

**DOES:** replace `rho_phone` = 5.520 *predicted, unadjudicated* with **5.976 measured** (and
0.742 at B=2), so the owner's pending flip decision rests on a measured phone number instead
of a desktop extrapolation.

**DOES NOT:** flip `PRODUCTION.yaml`; license an on-device deploy; move any strength claim;
constitute a band, a claim id, or a `results.csv` row; or say anything about what the
arbiter's picks are worth. 0 strength games were played.

**The standing bar for reference:** `rho_phone ≤ 1.20` is the house N4 trigger currency
applied to the phone. **B=2 clears it at 0.742; B=16 does not, at 5.976** — the same
qualitative split PHASE_A predicted, now measured. B=16 is the rung that CAPTURES
(`G-CONFIRMED`); B=2 is the rung that is affordable. That tension is the owner's to resolve,
not this file's.
