# ARBITER COST-OPTIMIZATION — OFFLINE PRICING PACKAGE — ANALYSIS

> **READ [`PREREG.md`](PREREG.md) FIRST.** It carries the disclosure that this is
> **post-hoc pricing of already-glimpsed effects**, the corpora, the estimators, and the
> falsifiers — all fixed before any number below was computed.
>
> ⛔ **0 games played. 0 new playouts. No band claimed. `governance/PRODUCTION.yaml` untouched.
> No `experiments/results.csv` row. No claim id. Nothing here closes, kills or promotes anything.**
>
> **This is a price list, not a verdict.** Any deploy decision from it is an owner ruling on
> banked evidence (the `b64_cell` precedent) or a game cell
> ([`measurement/phasegate_prep/`](../phasegate_prep/DESIGN.md), which reads the early-fire
> question in judge-free game currency and is the instrument if the owner wants an *answer*
> rather than a *price*).

Artifacts: [`PHASE_B_CAPTURE.json`](PHASE_B_CAPTURE.json) ·
[`RACING_SIM.json`](RACING_SIM.json) · [`COST_MODEL.json`](COST_MODEL.json) ·
[`CAPTURE_PER_GAME.json`](CAPTURE_PER_GAME.json). Scripts:
`phase_b_capture.py` · `racing_sim.py` · `cost_model.py` · `capture_per_game.py`.

---

## 0. Falsifiers and gates — checked before anything was read

| PREREG §5 falsifier | result | witness |
|---|---|---|
| 1 — phase recovery agreement < 0.98 | **not fired** (census 0.9960 · corpus A 0.9978 · corpus B 0.9918; corpus C uses stored `phase_bucket`, 1.0000 self-consistent) | `PHASE_B_CAPTURE.json::phase_recovery_validation` |
| 2 — `per_world_delta != values_b - values_a` on > 1% | **not fired** (0 / 6,602) | `RACING_SIM.json::diagnostics` |
| 3 — `values_a` not CRN-identical across a rid's legs | **not fired** (0 / 1,060 rids; `world_seeds` also identical) | `RACING_SIM.json::diagnostics` |
| 4 — census `Σφ_p` > 2× from the 22.96 prior | **not fired, but at the edge: 45.26 vs 22.96 = 1.97×** — see §3.1 | `COST_MODEL.json::census`, `::phi_calibration` |
| 5 — `r_p` from plies vs seconds disagree > 15% | **FIRED (35.6%)** ⇒ PREREG's own fallback applied: the **measured-seconds** model is primary. See §3.2 — this is the single biggest correction this package makes to the advisory. | `COST_MODEL.json::playout_length` |

**Estimator self-check.** The re-implemented root bootstrap reproduces the R4 read-out's own
ladder exactly: `arb_j4_E64_B64` = **+0.2015** CI95 [+0.1199, +0.2880] here vs **0.2015**
published in `shared_run_r4/verdicts/READOUT.md`; B=32 +0.1942 vs 0.1942; B=16 +0.1345 vs
0.1345. All seven rungs match to 4 decimals.

---

## 1. COMPONENT (i) — phase × B capture

### 1.1 The table — corpus A (R4 S1, n=1,340 / 748 roots, E=64 held-out, key `arb_j4_E64_B{b}`)

pts per tied tile-ply. Percentile root bootstrap, cluster = root, 2,000 reps, seed 20260819.

| B | ALL | early (n=516) | mid (n=382) | late (n=442) |
|---:|---|---|---|---|
| 1 | +0.0282 [−0.050, +0.114] | **−0.0992** [−0.221, +0.027] | +0.1610 [+0.026, +0.305] | +0.0620 [−0.075, +0.224] |
| 2 | +0.0118 [−0.064, +0.101] | **−0.1773** [−0.296, **−0.067**] | +0.1935 [+0.039, +0.355] | +0.0757 [−0.061, +0.238] |
| 4 | +0.1010 [+0.024, +0.186] | **−0.0652** [−0.182, +0.050] | +0.2871 [+0.152, +0.430] | +0.1343 [+0.006, +0.286] |
| 8 | +0.0954 [+0.016, +0.176] | **−0.1189** [−0.243, **−0.002**] | +0.2787 [+0.150, +0.423] | +0.1872 [+0.065, +0.335] |
| 16 | +0.1345 [+0.056, +0.217] | **−0.0840** [−0.214, +0.034] | +0.3288 [+0.198, +0.480] | +0.2218 [+0.096, +0.373] |
| 32 | +0.1942 [+0.117, +0.275] | **−0.0018** [−0.121, +0.108] | +0.3800 [+0.236, +0.533] | +0.2625 [+0.139, +0.412] |
| **64** (deployed) | **+0.2015** [+0.120, +0.288] | **−0.0405** [−0.160, **+0.083**] | **+0.4341** [+0.297, +0.589] | **+0.2831** [+0.162, +0.428] |

**The early bucket does not capture at any rung on the ladder.** Every early point estimate is
<= 0; the CI covers zero at B in {1,4,16,32,64} and is *significantly negative* at B=2 and B=8.
The contrast **early − (mid ∪ late)**, computed on the same bootstrap draw:

| B | 1 | 2 | 4 | 8 | 16 | 32 | 64 |
|---|---|---|---|---|---|---|---|
| early − mid∪late | −0.207 (z −2.54) | −0.308 (z −3.72) | −0.270 (z −3.35) | −0.349 (z −4.38) | −0.355 (z −4.35) | −0.319 (z −3.95) | **−0.394 (z −5.02)** |

### 1.2 The mechanism — there is nothing to capture early, and it is not the arbiter's fault

| companion, E=64 | ALL | early | mid | late |
|---|---|---|---|---|
| `ora_full_E64` (clairvoyant oracle over the tied arms) | +0.342 (z 7.28) | **+0.048 (z 0.73)** | +0.596 (z 6.67) | +0.465 (z 6.26) |
| `rnd_E64` (random tie-break) | −0.163 (z −3.71) | **−0.261 (z −4.24)** | −0.086 (z −1.09) | −0.116 (z −1.37) |
| `arb(B64) − rnd` | +0.365 (z 9.18) | +0.221 (z 3.41) | +0.520 (z 6.61) | +0.399 (z 5.86) |

**The ORACLE captures ~nothing early** (+0.048, z 0.73; contrast early − mid∪late = −0.478,
z −5.40). So early ties are between arms that a clairvoyant judge cannot separate — the
champion's incumbent tie-break is already ~oracle-optimal there. The arbiter is not
under-performing early; **there is no headroom early.** (The arbiter still beats a *random*
pick early by +0.221 — the incumbent order carries that, not the playouts.)

### 1.3 Replication — corpus B (`tiearb_20260816`, n=733 / 399 roots, m=32 ⇒ B≈16)

⚠️ Stage-1b's read rule is SPENT and its holdout BURNED; used here only as a phase replicate.
Unscaled record means (the read-out quotes these × `scale_all` = 0.7677).

| statistic | ALL | early (n=300) | mid (n=224) | late (n=209) | early − mid∪late |
|---|---|---|---|---|---|
| `arb` | +0.284 (z 3.74) | **+0.159 (z 1.07)** | +0.485 (z 3.48) | +0.250 (z 2.44) | −0.213 (z −1.22) |
| `ora` | +0.350 (z 4.35) | **+0.122 (z 0.85)** | +0.512 (z 3.03) | +0.504 (z 4.99) | −0.387 (z −2.16) |
| `arb − rnd` | +0.265 (z 3.18) | **+0.036 (z 0.25)** | +0.426 (z 2.91) | +0.420 (z 3.06) | −0.387 (z −2.22) |

### 1.4 Cross-corpus agreement statement

⚠️ **CL-068 applied: σ inflated 2× on every cross-corpus contrast; the corpora are never pooled.**

| contrast (early − mid∪late) | corpus A | corpus B | difference |
|---|---|---|---|
| `arb` at B ≈ 16 | −0.3554 (se 0.0817 → **0.163**) | −0.2130 (se 0.1742 → **0.348**) | **z −0.37** |
| `ora` | −0.4778 (se 0.0886 → **0.177**) | −0.3866 (se 0.1787 → **0.357**) | **z −0.23** |

**AGREEMENT.** Two independent corpora, different bands, different strata mixes (A is pure
`selfplay`/`walled`; B is 673 selfplay + 60 E4, three rules profiles) agree in **sign, ordering
and magnitude** on: (a) early capture is indistinguishable from zero, (b) mid is the largest
bucket, (c) the oracle ceiling itself collapses early. Corpus B alone is underpowered on the
`arb` contrast (z −1.22) but its `ora` and `arb − rnd` contrasts both clear |z| > 2, and its
point estimates sit inside A's CIs.

**Corpus C** (`rung3_r5`) banks no clairvoyant leg in-repo and therefore **cannot** replicate a
judge-priced capture. What it contributes is the arbiter's own decision-margin profile —
`PHASE_B_CAPTURE.json::corpus_C_margin_profile` — which matters for (ii):

| phase | n | mean top-2 gap | median | frac gap < 0.25 | mean paired sd | **mean gap/sd** |
|---|---:|---:|---:|---:|---:|---:|
| early | 371 | 2.450 | 1.938 | 0.057 | 24.04 | **0.104** |
| mid | 338 | 2.122 | 1.422 | 0.107 | 14.69 | **0.140** |
| late | 351 | 0.912 | 0.281 | 0.473 | 4.63 | **0.203** |

⚠️ Every corpus-C rid is `capped_at_4 = true` (n_arms >= 5) — the J-widening stratum, not the
deployment arm mix.

### 1.5 F4 label on §1

Every level in §1.1–§1.3 is **IN-FAMILY judge-priced** (clair-puct IF judge, tier1-greedy ARB
judge). Per the 2026-08-26 F4 lesson, absolute pts/tied-ply are **family-relative** and are not
game-strength points. **The robust part is the within-instrument phase CONTRAST** — same judge,
same CRN worlds, same positions, only the phase bucket differs — and that is what §1.1's
contrast row and §1.4's agreement statement rest on.

---

## 2. COMPONENT (ii) — flip-weighted racing and arm pruning

Source: `rung3_r5` tier1-greedy legs, 6,602 pairs / 1,060 positions, m = 32 CRN worlds,
star-of-pairs reconstruction into full arm × world matrices (gates in §0). Deployed arm set =
`ARMS.json::subset_j4` (4 arms). Rule: first check at t = 4 worlds, stop when the
leader-vs-runner-up **paired** margin clears z; if it never fires, all m worlds are used and the
decision is the reference by construction.

### 2.1 Racing (no pruning), deployed J=4 arms

| z | playout fraction | sign-flip rate | capture-weighted loss (arbiter currency, pts/fire) | fired before m=32 |
|---:|---|---|---|---:|
| 1.5 | 0.702 [0.680, 0.724] | 0.1264 [0.107, 0.146] | 0.2567 [0.194, 0.320] | 0.432 |
| 2.0 | 0.845 [0.826, 0.864] | 0.0547 [0.041, 0.069] | 0.1036 [0.065, 0.146] | 0.232 |
| 2.5 | 0.924 [0.910, 0.938] | 0.0226 [0.014, 0.032] | 0.0422 [0.020, 0.071] | 0.110 |
| 3.0 | 0.952 [0.940, 0.963] | 0.0142 [0.008, 0.022] | 0.0350 [0.013, 0.063] | 0.067 |

### 2.2 Racing + trailing-arm pruning at t in {8, 16}

| z | playout fraction | worlds fraction | sign-flip rate | loss (arbiter currency) |
|---:|---|---|---|---|
| 1.5 | **0.629** [0.608, 0.649] | 0.711 | 0.1189 | 0.2439 |
| 2.0 | **0.787** [0.769, 0.804] | 0.851 | 0.0538 | 0.1005 |
| 2.5 | 0.882 [0.868, 0.896] | 0.926 | 0.0226 | 0.0433 |
| 3.0 | 0.926 [0.914, 0.937] | 0.952 | 0.0142 | 0.0350 |

Pruning is worth an extra ~6–7 points of playout fraction at the **same** flip rate — it removes
arms without moving the leader/runner-up race. ⚠️ Its gain is **optimistic** for deployment: the
corpus is the >=5-arm stratum (mean 7.23 arms full, capped to exactly 4), while deployed
`Ā = 3.0022`. With ~3 arms there is ~1 prunable arm, not 2–9.

### 2.3 The phase interaction — racing and the phase gate are COMPLEMENTS, not substitutes

| z | playout fraction, MID+LATE only | playout fraction, EARLY only |
|---:|---|---|
| 1.5 | **0.675** | 0.754 |
| 2.0 | **0.825** | 0.882 |
| 2.5 | 0.913 | 0.943 |
| 3.0 | 0.943 | 0.968 |

**Racing saves LEAST exactly where the phase gate saves MOST.** The naive expectation (early
gaps are big, so racing stops early) is wrong: early gaps *are* the biggest (2.45 vs 0.91 late)
but early per-world sd is 5.2× larger (24.04 vs 4.63), and racing fires on **gap / sd**, which
is worst early (0.104 vs 0.203). The two levers stack almost cleanly rather than cannibalising
each other — which is why §3.3's combined option is close to the product of the two.

### 2.4 ⚠️ The two limits on §2 — read before using any number here

1. **This prices a B=32 arbiter, not the deployed B=64 one.** The banked matrices carry m=32.
   A z-threshold on a paired mean fires at an **absolute** world index, so the *fraction* at
   B=64 is smaller. `RACING_SIM.json::b64_worlds_fraction_{lower,upper}_bound` brackets it by
   assuming non-firers stop at 32 (lower) or never (upper):

   | z | m=32 measured fraction | **B=64 bracket** |
   |---:|---:|---|
   | 1.5 | 0.702 | [0.351, 0.635] |
   | 2.0 | 0.845 | [0.423, 0.807] |
   | 2.5 | 0.924 | [0.462, 0.907] |
   | 3.0 | 0.952 | [0.476, 0.942] |

   The bracket is wide because 77% of positions never fired by world 32 at z=2.0. **Banked data
   cannot narrow it**; only a 64-world matrix can. The flip rate at B=64 is likewise not
   computable here (both the reference and the racing estimate would be better-resolved).

2. **The loss column is in the arbiter's OWN self-judged currency** (tier1-greedy terminal
   playout points, the full-m margin between the reference arm and the arm actually chosen). It
   bounds how much of the arbiter's own decision statistic racing discards. It is **not**
   judge-priced capture and is **not commensurable** with §1's numbers. Converting it would
   require the clair-puct leg on these positions, which is not banked in-repo.

---

## 3. COMPONENT (iii) — cost model

### 3.1 Fire rates and the phi calibration

Census (`tile_gap_rows.jsonl`, corpus `champ449`, 449 games, 31,827 TILE plies, eps 0.0):

| phase | tile plies/game | fired/game | fire rate | Ā (capped J=4) | Ā (uncapped) |
|---|---:|---:|---:|---:|---:|
| early | 22.90 | 15.30 | 0.668 | 3.050 | 4.12 |
| mid | 22.99 | 13.85 | 0.602 | 3.112 | 7.40 |
| late | 25.00 | 16.12 | 0.645 | 3.287 | 13.41 |
| **total** | 70.89 | **45.26** | 0.639 | **3.153** | — |

⚠️ **`Σφ_p` = 45.26 against the 22.96 of record (1.97×).** The census fire predicate is a
**leaf** top-1 exact tie (1-ply v2.9 leaf); the deployed arbiter fires on a **post-search root**
tie. The census is used for the **phase shares**; the absolute level is taken from the record via
`K_PHI = 22.96/45.26 = 0.5073`. Every ratio and multiplier below is invariant to `K_PHI`.
Ā reproduces well (3.153 vs 3.0022, +5.0%). Reconstructed `rho_amortized(B=64)` = **0.8139** vs
the identity's 0.7939 (+2.5%) — the residual is the Ā weighting.
**Residual risk, unmeasurable from banked data:** if the post-search tie rate is *not*
phase-proportional to the leaf tie rate, the shares are biased and this package cannot say by
how much.

### 3.2 ⚠️ THE ADVISORY'S "EARLY ≈ 56% OF COST" IS THE PLY MODEL, AND TWO MEASUREMENTS REFUTE IT

| phase-cost factor `r_p` | early | mid | late |
|---|---:|---:|---:|
| `r_from_plies` — playout LENGTH (the advisory's model) | 1.677 | 0.984 | 0.340 |
| **`r_from_secs` — measured worker-seconds, PREREG primary** (rung3_r5, n=6,602) | **1.271** | **1.209** | **0.527** |
| `r_from_profile` — independent exclusive-tenant bench (PROFILE_TIER1.md §3, n=480, identity-gated 480/480) | 1.273 | 1.122 | 0.636 |

resulting **early share of total arbiter cost**:

| model | early | mid | late |
|---|---:|---:|---:|
| ply-length (advisory) | **0.564** | 0.306 | 0.130 |
| **measured seconds (PRIMARY)** | **0.4256** | 0.374 | 0.200 |
| measured profile (corroboration) | **0.4200** | 0.342 | 0.238 |
| fires only, no `r_p` | 0.327 | 0.302 | 0.371 |

**The early share shrinks from 56.4% to 42.0–42.6% — down ~14 percentage points, a factor 0.75.**
Mechanism (PROFILE_TIER1.md §3): early playouts are ~1.68× **longer** but each ply runs on a
**smaller, cheaper board** — per-candidate `count_final_scores` rises 10.5× from a near-empty
board to 65–77 placed tiles, so cost is roughly *flat* from root ply 6 to 60 despite a 40% drop
in remaining plies. A `cost ∝ plies` model anchored early **under-charges late fires by 1.67×**.
The two independent measured models agree on the early share to within **0.6 percentage points**;
the ply model is the outlier.

**Declared deviation:** PREREG §3.5 named two `r_p` models. The third (profile) arrived
mid-analysis from a sibling instrument. It is reported as **corroboration only** and is **not**
substituted for the PREREG-mandated primary — legitimate precisely because the two agree. No
estimator was shopped: falsifier 5 fired on the pre-registered 15% rule before the profile
existed. ⚠️ Profile caveat: its LATE bucket has one grid point (root ply 100, k=22, the shallow
edge of late), so its `r_late` is an upper bound and its early share a lower bound.

### 3.3 The option price list

Baseline = the deployed shape (B=64 all phases, J=4). Multipliers are **ratios**, so they compose
multiplicatively with any constant-factor engine change — e.g. the separately-gated 7.90×
bit-identical `count_final_scores` swap (PROFILE_TIER1.md §4). ⚠️ That swap's factor is itself
occupancy-dependent (4.7× near-empty to 8.2× at 65–77 tiles), so it does **not** cancel out of
the phase shares: it would shift them **further toward early**, strengthening the gate case.

| option | cost mult (secs / plies / profile) | speed-up | eval worker-s/game (W=30) | desktop s/move | phone min/game (hypothetical) |
|---|---|---:|---:|---:|---:|
| **current** B=64 all phases | 1.000 / 1.000 / 1.000 | 1.00× | 806.0 | 6.00 (arb 4.20) | 7.07 |
| **gate OFF early** | **0.574** / 0.436 / 0.580 | **1.74×** | 463.0 | 4.21 (arb 2.41) | **4.06** |
| B=16 early | 0.681 / 0.577 / 0.685 | 1.47× | 548.8 | 4.66 (arb 2.86) | 4.81 |
| B=16 early + B=32 mid | 0.494 / 0.424 / 0.514 | 2.03× | 398.0 | 3.87 (arb 2.07) | 3.49 |
| racing z=2.0 (m=32 measured) | 0.850 / 0.858 / 0.849 | 1.18× | 684.7 | 5.37 | 6.00 |
| racing z=1.5 (m=32 measured) | 0.708 / 0.719 / 0.708 | 1.41× | 570.9 | 4.77 | 5.01 |
| racing+prune z=2.0 | 0.790 / 0.797 / 0.790 | 1.27× | 637.0 | 5.12 | 5.59 |
| racing+prune z=1.5 | 0.633 / 0.642 / 0.633 | 1.58× | 510.4 | 4.46 | 4.48 |
| **gate OFF early + racing z=2.0** | **0.474** / 0.359 / 0.479 | **2.11×** | 382.1 | 3.79 (arb 1.99) | **3.35** |
| gate OFF early + racing z=1.5 | 0.388 / 0.294 / 0.391 | 2.58× | 312.4 | 3.43 (arb 1.63) | 2.74 |

**At the deployed B=64 the racing rows are brackets, not points** (§2.4):

| z | racing alone | gate-off-early + racing |
|---:|---|---|
| 1.5 | mult [0.354, 0.642] → **1.56–2.82×** | mult [0.194, 0.346] → **2.89–5.16×** |
| 2.0 | mult [0.425, 0.812] → **1.23–2.35×** | mult [0.237, 0.448] → **2.23–4.22×** |
| 2.5 | mult [0.463, 0.910] → 1.10–2.16× | mult [0.262, 0.513] → 1.95–3.81× |
| 3.0 | mult [0.477, 0.945] → 1.06–2.10× | mult [0.271, 0.535] → 1.87–3.69× |

**Currency notes.** (a) *Desktop s/move* uses `PRODUCTION.yaml`'s own stated calibration
(≈6 s/move armed vs ≈1.8 s/move champion baseline), scaling only the ≈4.2 s arbiter component;
`threads: 8` (6.5–6.8× measured on the arbiter term) is already inside the stated 6 s figure.
(b) *Eval worker-s/game* is `Σ_p φ_p Ā_p B_p c r_p` at `c_w30 = 0.178232`. (c) ⚠️ **The phone
column is hypothetical.** `PRODUCTION.yaml` says *"MOBILE: still no arbiter at all"* — the
funding brief's "B=32 mobile" does not exist. The column prices a hypothetical mobile arm at
`c_w1 = 0.093769` assuming a phone core ≈ a desktop core (**kappa = 1, UNMEASURED**); the
`rho_phone` equivalent falls from **22.6 → 13.0** (gate) → **10.7** (gate + racing z=2.0), still
far above any affordability bar the desktop ever used.

### 3.4 Capture at risk, in pts/GAME

Aggregating §1.1 with the calibrated fire rates (early 7.76, mid 7.02, late 8.18 fired
plies/game), bootstrap CI computed inside the replicate — `CAPTURE_PER_GAME.json`:

| B | total pts/game | mid+late only | early contribution |
|---:|---|---|---:|
| 16 | +3.471 [+1.685, +5.419] | +4.123 [+2.668, +5.824] | −0.652 |
| 32 | +4.801 [+2.995, +6.732] | +4.815 [+3.343, +6.553] | −0.014 |
| **64** | **+5.050 [+3.186, +7.099]** | **+5.364 [+3.902, +7.087]** | **−0.314** |

*Sanity, not a claim:* the offline B=64 total (+5.05 pts/game) is the same order as the banked
**game-level** readings of the arbiter vs the unmodified champion (+3.07 pts/game band 132e9;
+3.66 band 139e9 — cited in `measurement/phasegate_prep/DESIGN.md` §1, never pooled, different
bands). The offline instrument does not systematically under- or over-state the mechanism.

**The early-gate loss bound** — what the banked evidence allows the early bucket to be worth:

| option | forgone capture, pts/game | **95% upper bound = the loss bound** |
|---|---|---:|
| gate OFF early (B=64 → 0) | −0.314 [−1.243, **+0.641**] (z −0.68) | **+0.64 pts/game** |
| gate OFF early at the B=32 rung | −0.014 [−0.935, +0.839] | +0.84 pts/game |
| B=16 early (forgo B64−B16, paired) | +0.338 [−0.360, **+1.013**] (z +0.94) | +1.01 pts/game |

⚠️ Three honest riders. **(1)** The point estimates are *negative* — firing early looks like a
small *loss* — but a CI containing zero **is not a zero**, and this package does not claim early
capture is zero. The decision-relevant number is the **upper** limit. **(2)** These are
**in-family judge-priced** (§1.5). A 0.64 pts/game bound is a bound in the
clair-puct/tier1-greedy family, not in game-outcome currency. **(3)** Note the ordering:
`B=16 early` costs *more* (mult 0.681 vs 0.574) **and** carries a *wider* risk bound (1.01 vs
0.64). On this evidence **`B=16 early` is dominated by `gate off early`** — the incoherence of
the two bounds (an increment bounded above the whole) is a noise signature at these n, and is
reported rather than smoothed.

---

## 4. ⛔ WHAT THIS PACKAGE DOES NOT ESTABLISH

- That early capture **is** zero. It establishes that the banked, in-family evidence bounds it at
  **<= +0.64 pts/game** and cannot distinguish it from zero at any rung.
- Anything in **game-outcome** currency. The only judge-free reading of the early-fire question
  is the (unfunded, unbuilt) cell in [`measurement/phasegate_prep/`](../phasegate_prep/DESIGN.md).
- The racing numbers **at the deployed B=64**. §2.4's bracket is as far as banked data goes.
- That the census's leaf-tie phase shares transfer to post-search root ties (§3.1).
- Any strength claim, any band, any `results.csv` row, any `PRODUCTION.yaml` change.

---

## 5. THE PRICED PROPOSAL

**A phase-gated arbiter — no arbiter fire while `k_remaining > 48` — runs at ≈0.57× current cost
(1.74× cheaper; 0.574 measured-seconds / 0.580 profile-corroborated / 0.436 under the refuted
ply model), at a measured early capture-loss bound of <= +0.64 pts/game (point estimate −0.31,
CI [−1.24, +0.64], z −0.68, in-family judge-priced), against a whole-game arbiter capture of
+5.05 pts/game [+3.19, +7.10] of which mid+late carry +5.36 [+3.90, +7.09]; the phase contrast
that licenses it — early − mid∪late = −0.394 pts/tied-ply, z −5.02 at B=64 — replicates on an
independent corpus (−0.213; cross-corpus difference z −0.37 after CL-068's 2× sigma inflation)
and is mechanistically explained by the clairvoyant ORACLE itself capturing nothing early
(+0.048, z 0.73). Optional racing at z=2.0 multiplies that by a further 0.85× as measured at
m=32 (→ 0.474×, 2.11× total) for a 5.5% sign-flip rate costing 0.104 pts/fire in the arbiter's
own currency — and by an un-narrowable [0.425, 0.812] at the deployed B=64, so gate + racing
lands somewhere in 2.23–4.22× cheaper; trailing-arm pruning adds ~6 points of saving at the same
flip rate but is optimistic on a >=5-arm corpus. Desktop goes 6.00 → 4.21 s/move (gate) or →
3.79 (gate + racing z=2.0); an eval cell goes 806 → 463 → 382 worker-s/game; a hypothetical
phone arm (not deployed — `PRODUCTION.yaml` ships no mobile arbiter) goes 7.07 → 4.06 → 3.35
min/game, `rho_phone` 22.6 → 13.0 → 10.7. Every multiplier is a ratio and composes with the
separately gated 7.90× `count_final_scores` swap — which, being occupancy-dependent, would push
the early cost share higher still. ⚠️ This is post-hoc pricing of already-glimpsed effects on
banked evidence; it is an owner ruling or a game cell, not a verdict — and the advisory's
"early ≈ 56% of cost" is the ply-length model, which two independent cost measurements refute:
the measured early share is 42.0–42.6%.**

---

## 6. OWED INDEX LINES

A `DECISIONS.md` index line and a `docs/PROGRAM_ROADMAP_2026-07-07.md` roadmap stamp are owed at
close. ⛔ **This agent deliberately edited neither file** (nor `results.csv`, nor `governance/`,
nor anything outside `measurement/arb_costopt_prep/`). The verbatim text for both lines is in the
agent's final report to the orchestrator, which places them.
