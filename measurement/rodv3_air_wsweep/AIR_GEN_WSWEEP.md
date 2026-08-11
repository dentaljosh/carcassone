# Air (M5, ANE/CoreML) — gen-side W mini-sweep

> **STATUS: COMPLETE 2026-07-30 01:41:58 EDT.** Discharges the named gap (1) in
> `AIR_JOIN_RUNBOOK.md` §7 — *"the gen-side W has NOT been swept."* **Throwaway games**: scratch
> seed band `9902.4e9`, throwaway dir `~/rodv3_air/wsweep`, **pushed nowhere**, no `results.csv`
> row, no deck band consumed, nothing trained on them. The Air is **held out of the rodv3 turn-1
> corpus** by the pre-registered fleet decision in `RODV3_TURN1_PREREG.md`.

## Result — W\* = 4, not the inferred W6

Production knobs throughout (`--k-dets 4 --sims 688` = 2752, `--sighted`, `--batch-size 1`,
`--net-backend coreml --coreml-mlpackage cl067_iter03_policy_fp16.mlpackage`,
`--coreml-compute-units CPU_AND_NE`, curve125 leaf via `champ_env.sh`). **games-per-point = W**, so
every point is one saturated wave.

| W | games | wall | effective s/game | games/h | vs peak |
|---|---|---|---|---|---|
| **4** | 4 | 479 s | **119.8** | **30.1** | **peak — W\*** |
| 6 | 6 | 837 s | 139.5 | 25.8 | −14.3% |
| 8 | 8 | 1116 s | 139.5 | 25.8 | −14.3% |

**The engineer's suspicion is confirmed, and in the direction he predicted.** The runbook inferred
W6 from an *eval*-shaped sweep (35.0 / 37.2 / 38.5 games/h at W4/6/8 — **rising** with W), noting
that half of an eval game's moves are the cheap net-free champion, so real gen contends harder on
the one shared ANE and *"the optimum could be lower."* It is: in all-CoreML gen the curve
**inverts** — throughput is highest at W4 and drops 14% by W6, then is flat. By the house
settlement rule (smallest W within 5–10% of peak) W6 and W8 are outside the band, so **W\* = 4**.

Absolute throughput is also below plan: **30.1 games/h**, not the runbook's **~35 games/h**
planning figure (which was derived by scaling the uncontended W1 number by the eval cell's
contention factor). Anyone sizing an `AIR_GAMES` slice should use 30/h.

### ⚠️ One confound, stated rather than buried: W is confounded with temperature

The three points ran **in ascending W order on a fanless laptop**, back to back (01:01 → 01:41).
So the W6/W8 points ran on a progressively warmer box than W4, and the 14% decline is consistent
with **either** ANE contention **or** thermal drift — this sweep cannot separate them. Both
explanations point the same way for a *long* join (the box only gets warmer), so W4 stands as the
operational choice, but the *mechanism* is unresolved. **A descending-order replication (8 → 6 → 4)
would separate them** and is the cheap next step if the Air is ever funded for real gen.

Sample sizes are also small by design (4/6/8 games) — this is a scheduling number, not a strength
measurement.

## Correction to an earlier claim in this session's notes

An earlier note in
[teacher_h2h_94e9/SMOKE_AND_LAUNCH.md](../teacher_h2h_94e9/SMOKE_AND_LAUNCH.md) recorded that the
Air *"became unreachable ~02:21, most likely asleep mid-W6 despite a fresh untimed
`caffeinate -dimsu`"* and called it a **second sleep-mid-run**. **That was wrong on both counts**,
and the sweep log settles it:

- the sweep **finished cleanly at 01:41:58**, ~40 minutes *before* the box became unreachable — all
  three points `rc=0` with full npz counts (4/4, 6/6, 8/8);
- so `caffeinate -dimsu` **did its job**: it held the box awake for the entire run and released it
  when the sweep it wrapped exited, exactly as intended. The box then slept normally, which is
  correct behaviour for an idle laptop at 2 am.

The 2026-07-29 ANE-cell sleep at 377/400 remains a real, separate incident. There is **no** new
evidence that `caffeinate -dimsu` is insufficient, and the "flag it before funding a long Air run"
item raised on the strength of this is **withdrawn**. The Air was reachable again at 05:49 with the
results intact on its own disk.

## Why this was worth ~40 minutes of an idle box

The rodv3 prereg's F1 amendment leaves **gen at the corpus-teacher budget k8×1376 = 11008** as the
surviving clean test of lever 6 — priced at ~29 h local-only. If that is ever funded, every box
counts, and the Air would otherwise have joined at an inferred W that is **14% off** its measured
optimum with a games/h figure **16% optimistic**.
