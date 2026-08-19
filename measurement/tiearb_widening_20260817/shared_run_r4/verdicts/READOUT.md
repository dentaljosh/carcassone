# TIE-ARBITER WIDENING — READ-OUT (rungs 2 + 3)

generated: 2026-08-19T12:45:48Z

> Significance is ONE test everywhere: `lower(CI95) > 0` on the
> percentile ROOT bootstrap (2,000 reps, seed 20260819, cluster = root).
> `G-REPLICATE` z-statistics are SEALED and appear nowhere in this file.

## Gates

| gate | verdict | resolved_at |
|---|---|---|
| `G-ARMS` | PASS | `READOUT::widening.gates.arms` |
| `G-BAND` | PASS | `READOUT::widening.gates.band` |
| `G-COMPLETE` | PASS | `READOUT::widening.completion` |
| `G-CRN` | PASS | `READOUT::widening.gates.crn` |
| `G-REPLICATE` | PASS | `READOUT::widening.stage1_replication` |
| `G-SALT` | PASS | `READOUT::widening.gates.salt` |
| `G-UNCAPPED` | PASS | `READOUT::widening.gates.uncapped` |

analyzer-owned gates: **ALL PASS**

## Rung 2 — `B > 16` (S1, primary `Δ(16→64)` at E = 64)

**BRANCH: `W-RISING`** — lower(CI)>0, d>=0.04, arb_64 convicts, arb(64)>arb(16)

- `Δ(16→64)` = 0.0670 CI95 [0.0215, 0.1111] se_root 0.0228 (committed floor +0.04)
- `Δ(16→32)` = 0.0597 CI95 [0.0190, 0.0998] — reported with its CI, **never a branch input on its own**
- **realized `se` 0.0228 vs the pre-registered §3 bracket [0.0179, 0.0200] — **ABOVE****. The design's variance model under-predicted; this changes NO branch — the REALIZED CI governs and the floor is fixed — and it is printed because §3 requires the realized quantity beside its bracket. `sd_Δ` bracket [0.9000, 1.4000].

| B | arb (E=64) | CI95 | se | arb (E=16) | CI95 | se |
|---|---|---|---|---|---|---|
| 1 | 0.0282 | [-0.0499, 0.1143] | 0.0410 | 0.0921 | [-0.0236, 0.2175] | 0.0603 |
| 2 | 0.0118 | [-0.0640, 0.1010] | 0.0419 | 0.0908 | [-0.0279, 0.2196] | 0.0622 |
| 4 | 0.1010 | [0.0243, 0.1860] | 0.0405 | 0.1770 | [0.0565, 0.3085] | 0.0633 |
| 8 | 0.0954 | [0.0155, 0.1756] | 0.0405 | 0.1622 | [0.0489, 0.2815] | 0.0591 |
| 16 | 0.1345 | [0.0561, 0.2167] | 0.0410 | 0.2206 | [0.1059, 0.3402] | 0.0582 |
| 32 | 0.1942 | [0.1172, 0.2751] | 0.0405 | 0.2461 | [0.1304, 0.3586] | 0.0585 |
| 64 | 0.2015 | [0.1199, 0.2880] | 0.0413 | 0.2673 | [0.1539, 0.3819] | 0.0574 |

A null here means **"no rung above 16 is worth ≥ +0.04 pts/tied ply"**, NOT `Δ = 0`: the saturating-exp (+0.017) and √B-noise (+0.021) models are not resolved by this design.

## Rung 3 — `J > 4` (S2 capped plies, primary `Δ_ora`)

**STATUS: `VOID_S2`** — stratum voided at G-DISJOINT per PREREG_FAILURE_S2.md and ADJUDICATION_R4_GATES.md Reading A

- **bought: `true`** at `n2 = 1100` (`/home/doctor/projects/carcassone/measurement/tiearb_widening_20260817/shared_run_r4/FLOORS.json::n2`) — the J question WAS purchased and then lost to a stratum void
- **estimand_read: `false`** — the branch table was NEVER evaluated
- witness: `GATE_DISJOINT.json::digest_exclusions.S2.void` = `True` (`/home/doctor/projects/carcassone/measurement/tiearb_widening_20260817/shared_run_r4/GATE_DISJOINT.json`)
- **obligation inherited by `rung3_r5`** — I7's dedupe-partition conditional, which stays UNMEASURED — W9 / D-DRAW was skipped as moot

**THIS READING IS FORBIDDEN AS:**

- not "not bought" — the run BOUGHT rung 3 at n2 = 1100
- not "answered" — no estimand was read
- not "inconclusive" — nothing was measured to be inconclusive about
- not any rung-3 branch of the READ_RULE's branch table (they are enumerated there and are deliberately NOT named here): the table was never evaluated

### S1-side rung-3 riders — REPORTED, ADJUDICATING NOTHING

REPORTED, ADJUDICATES NOTHING. These are real S1 measurements, but with rung 3 VOID they have NO PRIMARY TO RIDE ON: no rung-3 branch may be inferred from them, in either direction. They are not a substitute estimand, not a partial read, and not evidence for or against any X-branch.

- S1 replication `Δ_ora` = 0.1993 CI95 [0.0683, 0.3327] (n_capped 230)
- interaction `arb_full(64−16)` = 0.1420 (n_capped_s1 230)


## R4 §7a — supply, composition, exclusions, predecessor

### Corpus composition — RETAINED vs FRESH

| stratum | retained (135e9) | fresh (137e9) | origin commit | copied |
|---|---|---|---|---|
| S1 | 551 | 793 | `untracked` | true |
| S2 | 103 | 961 | `untracked` | true |

**Totals:** 654 retained + 1754 fresh = 2408 (retained fraction 0.272). The retained positions were read READ-ONLY out of the SPENT R3.3 run and **COPIED** in — never symlinked, and `shared_run/` was never written to.

the retained positions are NOT pre-cleared: they entered the probe build and were gated exactly like fresh ones. 'Already gated under R3' is not a status any position holds — R3's gate FAILED, so nothing was ever passed.

### Supply and floors

- **Supply realized vs committed:** S1 1340 against floor 1283 (committed n₁ 1350); S2 capped 0 against floor 1045 (committed n₂ 1100); option `FULL`. Both counts are AFTER the §2b exclusions.

### Digest exclusions (R4 §2b — printed whether or not any fired)

| stratum | n_excluded | rate | bound | denominator | source | void |
|---|---|---|---|---|---|---|
| S1 | 1 | 0.00074 | 7 | 1350 | `RUN/FLOORS.json::n1` | false |
| S2 | 29 | 0.02636 | 6 | 1100 | `RUN/FLOORS.json::n2` | true |

`n_excluded` = `carried` (measured on the PROBE build, which is where the bound is judged) + `residual` (fresh collisions in the FINAL build, expected 0). A nonzero `residual` is additionally a **determinism defect**.

The digest is a function of the **board alone**, computed at corpus-build time **before any value exists** — the exclusion is outcome-independent by construction, which is exactly why it is legitimate here and was not in the 2026-08-14 open-city void. A stratum over the bound is **VOID, not excluded-and-continued**, and **a VOID is not curable by generating more games**.

- **Predecessor:** pair `604edc83` is SPENT-BY-GATE-FAILURE — frozen history; never amended, revived or re-read. band 135e9's 850 games are REUSABLE INPUT, not a prior result: the run stopped PRE-SCORING, so no arb, ora, delta, CI or per-position value was ever computed. R4's n is sized from rates measured on that same corpus, so it is NOT statistically independent of its STRUCTURE — a nuisance-parameter read, never an estimand dependence (PREREG_FAILURE §3.4).
