# SIZING — C1 OUTCOME PRICING: power and cost, before the launch

> **⚠️ Status: DESIGN ONLY — FROZEN, PRE-OUTCOME.** Every number below is
> derived from artifacts already on disk. Pre-registration:
> [`DESIGN.md`](DESIGN.md). Reading rule: [`READ_RULE.md`](READ_RULE.md).

## 1. The variance model — measured, not assumed

`e4_continuation_20260828` ran the identical machinery (same runner, same CRN
world construction, same champion, same strata, M = 8) and its
`CONTINUATION.json` carries `world_deltas` per ply. Decomposing those gives the
only real measurement of this estimator's variance that exists:

| stratum (e4_continuation, M = 8) | n plies | sd **within** ply (per world) | sd **between** plies |
|---|---:|---:|---:|
| `farm_capture` | 12 | 12.62 | 2.71 |
| `invasion` | 21 | 23.09 | 3.20 |
| `defense` | 28 | 20.20 | 2.77 |
| `control` | 30 | 22.99 | 0.00 |

**The within-ply world variance dominates by 4–8×.** That is the single most
consequential fact for sizing this run: the SE is very nearly pure `1/√M` in this
regime, so **worlds are the cheap axis and the ply count is not the binding
constraint** — the opposite of the usual "buy more n" reflex. It is why
`farm_capture` gets M = 32 while `defense`/`control` get M = 8 (§3).

Model: `sd_ply(M) = √(sd_between² + sd_within²/M)`, `SE = sd_ply/√n × 1.05`.
The 1.05 is a cluster inflation factor; measured cluster-robust/naive ratios in
`e4_continuation` were 1.00 / 1.03 / 1.07 / 0.74 (mean 0.96), so 1.05 is mildly
conservative. Caveat, stated: those variances come from **owner-vs-champion**
arms. C1's two arms are both machine picks and may sit closer together, which
would make the true within-ply variance somewhat *smaller* — i.e. these MDEs are
more likely pessimistic than optimistic. They are not re-derived from C1 data,
because none exists.

## 2. Achieved power — the honest statement

| pool | n plies | M | sd_ply | SE | **2σ MDE (pts / divergent ply)** |
|---|---:|---:|---:|---:|---:|
| **P1 `farm_capture`** (PRIMARY) | 14 | 32 | 3.51 | 0.99 | **1.97** |
| **P2 contested** (CO-PRIMARY) | 69 | 32/16 | 6.10 | 0.77 | **1.54** |
| `invasion` (secondary) | 55 | 16 | 6.60 | 0.93 | 1.87 |
| `defense` (secondary) | 61 | 8 | 7.66 | 1.03 | 2.06 |
| `control` (secondary) | 58 | 8 | 8.13 | 1.12 | 2.24 |
| all 188 divergent (secondary) | 188 | mixed | 7.29 | 0.56 | 1.12 |

**After every elasticity block (`E1`+`E2`+`E3`, 8.8 fleet-hours):**

| pool | M | SE | 2σ MDE |
|---|---:|---:|---:|
| P1 `farm_capture` | 64 | 0.88 | **1.76** |
| P2 contested | 64/32 | 0.61 | **1.22** |
| all 188 | mixed | 0.42 | 0.83 |

### 2.1 What that buys, said plainly

* **Against the in-sample gap (+6.208 pts pooled, +6.000 on `farm_capture`) this
  instrument is overwhelming** — that hypothesis is rejected at z ≈ 6 on P1 and
  z ≈ 8 on P2 if the true out-of-sample price is ≈ 0. **The winner's-curse
  readout ([`READ_RULE.md`](READ_RULE.md) §5) is therefore the one output that is
  essentially guaranteed to land**, whatever the branch.
* **Against a genuinely useful C1 (+2 pts per divergent ply — i.e. ~+1.1 pts per
  ply of deployed play at `D_champ` = 0.538) P1 sits right at 2σ.** It is a
  coin-flip whether a real +2 effect clears the bar on the primary alone. **This
  is stated before the outcome and is the honest limitation of n = 14 divergent
  plies in 12 games.** P2 clears the same effect comfortably (z ≈ 2.6), which is
  the entire reason it is a co-primary rather than a secondary.
* **Against a subtle C1 (+1 pt per divergent ply) nothing here is powered**, and
  the pre-registered outcome in that world is `C1-NULL-BOUNDED` with the bound
  quoted — which is a real result (it caps the lever at < ±2 pts) and is
  explicitly not "C1 is worth zero".
* **Reference scale.** The 2026-08-28 continuation read `farm_capture` at +2.53
  ± 1.51 (z 1.68, n = 12) for the *owner's* move. This instrument's primary sits
  at a comparable n with a ~35 % smaller SE, on a different treatment.

### 2.2 Why `farm_capture` and not "just run more plies"

There are exactly 14 divergent `farm_capture` plies in the entire banked corpus
(26 crux plies × `D_champ` 0.538). **n cannot be increased without new E4 games
and a new microgates pass.** The only axis available is M, the within-ply
variance is 4.7× the between-ply variance there, and 32 worlds on 14 short
late-game plies costs 0.36 fleet-hours. That is why the allocation is shaped the
way it is; a uniform M would have spent the same money for a worse primary.

## 3. Cost — the arithmetic, from realized rates

### 3.1 The measured fleet rate

`e4_continuation_20260828`, both boxes, `LOCAL W = 30` + `LAPTOP W = 22`,
`rust_threads = 1`, `nice -19`, exclusive tenants:

```
local   START 2026-08-28T00:25:46  DONE 01:51:17   = 5 131 s   392 units
laptop  START 2026-08-28T00:26:16  DONE 01:46:29   = 4 813 s   304 units
                                                     728 units, 0/1456 arm attrition
continuation-plies executed  =  7 534 remaining-plies x 2 arms x 8 worlds = 120 544
FLEET RATE                   =  120 544 / 5 131 s   =  23.49 continuation-plies / s
```

Per arm-slot that is 0.452 plies/s, i.e. **2.21 s per continuation ply under
W30+W22 contention** against the 1.16 s/ply measured solo — a 1.9× contention
factor, consistent with the DRAM-bound profile this repo measures everywhere.
The fleet rate is the right unit here because it is **end-to-end**: it already
contains chunk launch overhead, import cost and the tail.

### 3.2 This run's work

`continuation-plies = Σ(remaining plies) × 2 arms × M`, per stratum:

| block | strata | worlds | Σ rem | cont-plies | fleet-h @ 23.49/s | **+15 % margin** |
|---|---|---|---:|---:|---:|---:|
| **base** | `farm_capture` | 16–47 (M 32) | 436 | 27 904 | 0.33 | 0.38 |
| | `invasion` | 16–31 (M 16) | 4 416 | 141 312 | 1.67 | 1.92 |
| | `defense` | 16–23 (M 8) | 4 852 | 77 632 | 0.92 | 1.06 |
| | `control` | 16–23 (M 8) | 4 782 | 76 512 | 0.90 | 1.04 |
| | **base total** | | 14 486 | **323 360** | **3.82** | **4.40** |
| `E1` | `farm_capture` | 48–79 | | 27 904 | 0.33 | 0.38 |
| `E2` | `invasion` | 32–47 | | 141 312 | 1.67 | 1.92 |
| `E3` | `defense`+`control` | 24–31 | | 154 144 | 1.82 | 2.10 |
| | **everything** | | | 646 720 | 7.65 | **8.80** |

**Base pass ≈ 4.4 fleet-hours** (2 280 units, 4 560 arms) — inside the requested
4–6 h band. Everything ≈ 8.8 h.

The 15 % margin is genuine headroom on top of an already end-to-end rate. **It
does not cover a non-exclusive box**: the 2026-08-26 quantification is that one
niced 1-core DRAM churner inflated a saturated W = 22 eval ~1.8×/move. If the
G-HOST gate is overridden, this ETA is void. That is why `run_c1.sh` refuses
rather than warns.

### 3.3 The arm cap

`ARM_CAP_S = 1800` s of **CPU** per arm, carried from `e4_continuation`'s D-1
deviation (its PREREG said 600; 1800 is what actually ran, with 0/1456
attrition). Worst arm here is `control`/`invasion` at ~82 continuation decisions
× 1.16 s solo ≈ **95 s CPU** — ~19× under the cap. The primary stratum's arms are
31 decisions ≈ 36 s. Contention is charged to wall, not CPU, so the cap is not
the binding constraint at any W. Carried unchanged; no reason to revise.

### 3.4 The exact-solver bonus leg

4 plies, one marginalized solve each, `k_marginalized_max = 4` and
`per_solve_cpu_cap_s = 1800` inherited verbatim from
`../e4_ply_pricing_20260827/MODE_CUT.json`. Measured rust ladder there: ~290 s at
K = 4 with a heavy tail. **Worst case ≈ 4 × 1800 s = 2 core-hours, typical
≈ 20 minutes on one core.** Runs beside nothing (it is a single-core job; run it
*after* the continuation blocks, not during — the exclusive-tenancy rule applies
to this instrument's own legs too).

## 4. The pre-flight and smoke budget

| step | cost |
|---|---|
| `selftest_c1.py` (static; AST only, no engine) | ~1 s |
| `preflight_c1.py` (G-LEGAL: 188 prefix replays, no search) | ~1–2 min, 1 core |
| `plan_c1.py` | < 1 s |
| `smoke_c1.sh` (4 real units = 8 arms through the real driver) | ~5–10 min at W30 |

Total pre-launch ≈ **15 minutes**, and it gates a 4.4-hour run. The
projected-ETA gate inside the smoke (**> 8 h ⇒ do not launch**) is the last
chance to catch a mis-sized fleet before spending the window.

## 5. What would change these numbers

* **A G-LEGAL drop** shrinks n. At the 20 % void bar, `farm_capture` losing 3 of
  14 plies would push P1's 2σ MDE from 1.97 to ~2.2; losing more is a VOID, not
  a degraded estimate.
* **Small-K duplication**: two `farm_capture` plies (K = 4, K = 6) have fewer
  distinct completions than M = 32, so their per-ply SE floors early. With 2 of
  14 plies affected the effect on P1's SE is a few percent, not a
  qualitative change; `achieved_m_worlds` and `world_deck_len` make it auditable.
* **A slower fleet** (non-exclusive box, laptop thermal, a different W) scales
  every fleet-hour linearly. The elasticity rule (`DESIGN.md` §6) is written
  against *measured* remaining wall-clock for exactly this reason, not against
  this table.
