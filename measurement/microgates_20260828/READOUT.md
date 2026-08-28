# ✅ READOUT — C1 MICRO-GATES — **BRANCH: GATE-LIVE**

> **Adjudicated 2026-08-28. `R_contest` = 0.678 ± 0.023 (floor for GATE-DEAD was
> 0.10, for GATE-LIVE 0.35); `D_champ` = 0.639 on contested plies (floor 0.15).
> Both pre-registered LIVE conditions met.** The advisor's premise-killer is
> **REFUTED**: tier1-greedy rollouts contest constantly, and they realize
> post-claim farm invalidation in the majority of playouts. Zero new games, zero
> band, **no `experiments/results.csv` row** (0-game oracle-class instrument,
> house precedent). Pre-registration: [`PREREG.md`](PREREG.md), frozen at
> `f6013f49` before any gate statistic. Departures: [`DEVIATIONS.md`](DEVIATIONS.md)
> — **read D4 before quoting any G1 number.** Machine artifact:
> [`MICROGATES.json`](MICROGATES.json).

## 1. What was asked, and what came back

An independent advisor flagged the premise of **C1** (price contested-claim plies
by terminal tier1-greedy rollouts) as untested: *the rollout policy may itself
never contest — never invade via merge, never zero an opponent farm — in which
case rollouts cannot see post-claim invalidation and C1 dies for free.*

It contests. Constantly.

| | measured | pre-registered floor | banked reference |
|---|---:|---:|---:|
| **G1 `R_contest`** — playouts realizing ≥ 1 NEW contest onset | **0.6785 ± 0.0229** | DEAD < 0.10 · LIVE ≥ 0.35 | `p_ref` = 0.739 |
| **G2 `D_champ`** — contested plies where the rollout-argmax ≠ the champion's pick | **0.6389** | LIVE ≥ 0.15 | champion-vs-owner divergence 0.259 |

`p_ref = 0.739` is what the **owner + the on-device champion** themselves realize
over a continuation of the same mean length (50 banked E4 games, 7,100 plies,
λ = 0.01873 contest onsets/ply → `1 − exp(−λ·71.8)`). The rollout policy is
therefore contesting at **92 % of the rate two deliberately-contesting real
players do**. It is not contest-blind by any reading of the word.

The SE is cluster-robust on GAME (47 games). GATE-DEAD sits ~25 SE below the
measurement. This is not a close call in either direction.

## 2. G1 — contest realization

4,432 playouts · 277 `fixed_v1` crux plies · 47 games · 16 CRN worlds each ·
mean continuation 70.4 plies · **attrition 0.0 %**.

```
R_contest                        0.6785   (SE 0.0229, clustered on game)
  R_farm                         0.4386   vs p_ref_farm 0.4658
  R_city                         0.3051
  R_road                         0.1708
mean NEW onsets per playout      0.988
R_farm_control    (a farm the root already controlled changes hands)   0.6397
R_farmer_zeroed_lost_majority    (a root-claimed farmer ends on ZERO
                                  having lost majority on a live field)  0.6022
R_farmer_zeroed_no_cities        (dead field, not an invalidation)       0.0932
by invader seat:  seat 0  0.5747   seat 1  0.1841   ambiguous  0.0463
```

**Both halves of the advisor's disjunction fail.** The rollouts invade via merge
(that is the only mechanism they use — §2.2), and they zero opponent farms: in
**60.2 %** of playouts a farmer that was already on the board at the crux root
ends the game scoring nothing *because it lost majority on a field that did have
finished cities*. That is post-claim invalidation, realized, in the majority of
rollouts. A rollout-grounded price at these plies is looking straight at it.

### 2.1 Per stratum

| stratum | playouts | `R_contest` | `R_farm` | `R_farm_control` | `R_farmer_zeroed` | onsets/playout |
|---|---:|---:|---:|---:|---:|---:|
| `defense` | 1312 | **0.937** | 0.611 | 0.677 | 0.586 | 1.46 |
| `control` | 1392 | 0.718 | 0.442 | 0.532 | 0.582 | 1.07 |
| `farm_capture` | 416 | 0.519 | 0.425 | 0.685 | 0.661 | 0.60 |
| `invasion` | 1312 | **0.429** | 0.268 | 0.702 | 0.621 | 0.56 |

**The inversion is the interesting part and it is not an artifact.** `invasion`
plies show the LOWEST new-contest rate precisely because at an invasion ply the
contest has usually *already happened* — either it stands at the root or the
forced arm action itself creates it, and both are excluded from the rollout
bucket by construction (PREREG §2.2 adaptation A1: only onsets at ply > root
count, because the gate is about what the ROLLOUT POLICY does, not about the
move it was handed). `defense` plies sit two plies BEFORE the owner's invasion,
so the contest is still in the future there — and 93.7 % of the time the rollout
policy goes and creates one. Read together, the two rows say the rollouts are
not merely stumbling into contests left standing; they generate them.

### 2.2 Mechanism — and an unplanned corroboration

```
merge        4168        merge_equal   211
placement       0        born_contested  0
```

**Every single contest the rollout policy creates is a MERGE**, in exactly the
proportion the banked Stage-A census found for the real games (121 merge +
12 merge_equal, 0 placement, 0 born_contested, from an independently written
two-pass implementation on different data). Nobody designed that agreement; it
fell out. It is the strongest evidence available here that the ported detector
is measuring the same thing Stage A measures.

### 2.3 Per-position shape

277 positions, 16 worlds each. **33 positions (11.9 %) never realize a contest
in any of their 16 worlds; 110 (39.7 %) realize one in all 16.**

```
0.00 |################################# 33      0.75 |############## 14
0.06 |############# 13                         0.81 |############ 12
0.12 |########## 10                            0.88 |############### 15
0.19..0.50 | 28 across five bins                0.94 |###################### 22
0.56..0.69 | 20 across three bins               1.00 |###...################ 110
```

The distribution is strongly bimodal, not a uniform 68 %. That matters for C1:
the mechanism is available at most positions and absent at a minority, so a C1
price would be informative where it fires and silent where it does not — which
is the shape a *selective* lever wants, not a defect.

### 2.4 The aside profiles (reported apart, never pooled — PREREG §1.1)

| profile | plies | playouts | `R_contest` | `R_farm` | `R_farm_control` | `R_farmer_zeroed` |
|---|---:|---:|---:|---:|---:|---:|
| `walled` | 10 | 160 | 0.631 | 0.506 | 0.706 | 0.637 |
| `app_aug2` | 3 | 48 | 0.333 | 0.021 | 0.021 | 0.979 |

`walled` tracks the primary pool. **`app_aug2` does not, and the reason is the
rules epoch, not the policy**: it is the pre-`fixed_v1` phone build, which runs
with **R9 OFF** — different farm adjacency — so its farm components decompose
differently and its farmers almost never share a field (`R_farm` 0.021) while
almost all of them end on a dead field (`R_farmer_zeroed` 0.979, and that number
is the `no_cities` kind). n = 3 plies. It is stated here because the
rules-epoch discipline demands it, and it is evidence for that discipline, not
against the gate.

## 3. G2 — disagreement

4,640 units · 277 `fixed_v1` plies · mean 7.7 arms/ply · 16 shared CRN worlds ·
**attrition 0.0 %**. The reference is the **banked full production-champion
search** (k8 × 1376, fair PIMC, exact-K ≤ 2, rust) from the 2026-08-27 run, read
off disk — no champion search was re-run, and no leaf-greedy stand-in was used.

| cut | plies | `D_champ` | `D_owner` | mean arm spread |
|---|---:|---:|---:|---:|
| **contested** (`invasion` ∪ `farm_capture`) — THE GATE CUT | 108 | **0.639** | 0.546 | 11.17 pts |
| all crux plies | 277 | 0.679 | 0.675 | 11.14 pts |
| `defense` | 82 | 0.744 | 0.744 | — |
| `invasion` | 82 | 0.671 | 0.659 | — |
| `control` | 87 | 0.667 | 0.770 | — |
| `farm_capture` | 26 | 0.538 | **0.192** | — |

The terminal-grounded pick differs from the champion's at **64 %** of contested
plies — 2.5× the floor, and 2.5× the rate at which a strong human (the owner)
differs from the champion at those same plies. There is real re-ranking
information here, not a rubber stamp.

**One row deserves naming: `farm_capture`.** There the rollout-argmax agrees
with the OWNER 81 % of the time (`D_owner` 0.192) while disagreeing with the
champion 54 % of the time — the only stratum where the rollouts side decisively
with the human against the production champion. n = 26 plies, so this is a
pointer, not a verdict. But it is a pointer at precisely the mechanism the
2026-08-25 Stage A named (farm-steal, "one missing leaf term") and the one thread
the continuation run left unpromoted (`farm_capture` +2.53, z 1.68, n = 12).
**Three instruments now point at farm capture.**

⚠️ **Arm spread ≈ 11 points is large and is NOT a claim of 11 points of edge.**
It is the max-minus-min of arm means over 16 worlds; with M = 16 the per-arm SE
is several points, so a good part of that spread is sampling noise and an argmax
over ~8 noisy arms carries a winner's-curse bias. `D_champ` is a *disagreement
rate*, which is what the gate asked for; it is not a price, and nothing here
prices a ply.

## 4. Instrument gates — all PASS

| gate | result |
|---|---|
| **G-DETECT** — the census must reproduce a KNOWN banked invasion | **82 / 82 = 1.000** (needed ≥ 0.95) |
| **G-REPLAY** — the archive's own continuation must reproduce its recorded final score | **82 / 82 = 1.000** |
| **G-REPEAT** — same unit, twice, same process | **5 / 5 identical** |
| **cross-stage determinism** — g1 vs g2, independent passes, different chunkings | **4,640 / 4,640 identical** on every playout-determined field |
| attrition (G1 and G2) | **0 / 9,280 units** — no ERROR, TIME_SKIPPED or OOM_SKIPPED |
| world guards | no `root_state_diverged`, `world_not_a_permutation`, `deck_tail_mismatch` or `world_prefix_mutated` on any unit |

Stage 1b (the 64-world extension) did **not** run: PREREG §5 gates it on
`0.005 ≤ R < 0.20` and `R = 0.678` is far outside. That is the pre-registered
branch executing, not a cost cut.

## 5. ⚠️ Read this before quoting a G1 number

**A bug in this instrument's own census was found and fixed AFTER the first full
pass had been run and aggregated** (`DEVIATIONS.md` D4). Streaming the Stage-A
union-find is not sound: `UF.union` re-roots onto the group's minimum positional
key, so a component that grows a smaller key acquires a new root and every
`fid` already recorded for it goes stale — the already-contested component is
then re-reported as a fresh onset. Stage A is immune only because it is
two-pass (its `fid()` is evaluated against the final union-find).

**The buggy pass read `R_contest` = 0.866. The corrected value is 0.678.**
Component identity is now carried by permanent key membership (adaptation A3),
G1 was re-run in full, and the `unknown` mechanism bucket — 6,547 onsets, which
is what exposed the bug — went to **zero**. G2 was not re-run and does not need
to be: `D_champ` uses terminal margins only, the playouts are byte-identical, and
the g2 units' census fields are read by nothing.

The branch is unchanged by the correction (0.678 and 0.866 are both far above
0.35), but the sub-statistics moved a lot and the honest number is 0.678.

## 6. What this means for C1 — the one paragraph

**C1's premise survives, and the gate that could have killed it for free did not
fire.** The tier1-greedy rollout policy is not contest-blind: it creates new
contests in 68 % of playouts, exclusively by merge, at 92 % of the rate the
owner and the champion themselves do; it flips control of an already-claimed
farm in 64 % of playouts; and in 60 % of playouts a farmer that was on the board
at the crux root ends up scoring zero because it lost a majority it held — the
post-claim invalidation C1 was supposed to be able to see, realized, routinely.
The terminal-grounded pick is also genuinely opinionated: it differs from the
production champion's full-search move at 64 % of contested plies, 2.5× the
floor and 2.5× the rate a strong human does. **What this does NOT establish is
that C1 would be worth anything** — this instrument prices nothing, and the
program's standing lesson is that a mechanism being visible to an estimator is
not the same as that estimator being right (CL-073: outcome prediction is not
move discrimination; the F4 lesson: judged headroom is family-relative). A
disagreement rate of 0.64 says the re-ranker moves a lot of plies; it says
nothing about whether it moves them in the right direction, and an argmax over
~8 noisy arms at M = 16 has a winner's curse that a real C1 would have to be
sized against. **The correct next step is not to fund C1 — it is to price a
small, judge-free sample of C1's own re-rankings against realized game outcomes,
the way `e4_continuation_20260828` priced the champion's**, with `farm_capture`
first: it is the one stratum where these rollouts side with the owner against
the champion, and it is now the third independent instrument to point there.
