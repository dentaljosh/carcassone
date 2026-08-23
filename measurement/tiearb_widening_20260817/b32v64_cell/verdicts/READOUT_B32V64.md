# `B = 32` vs `B = 64` TIE-ARBITER LADDER GAME CELL — READ-OUT

> ⭐ **READING-A BANNER — READ THIS FIRST, THE READ-OUT IS NOT INTERPRETABLE WITHOUT IT.**
> The adjudicator returned **`U-UNREADABLE`**: `G-BAND` failed on its **4th conjunct**
> ("identical realized deck sets"), 12/13 gates PASS. **Owner ruling 2026-08-22
> (post-havdalah), verbatim: *"reading a"*** — the conjunct is **DISCHARGED by the confirmed
> failure set**, and the branch table applies unamended to the resolved statistics.
> ⇒ **VERDICT OF RECORD: `L-AMBIGUOUS`.**
> **The ruling, the contradiction analysis, the intent witness and the BLINDNESS DISCLOSURE are
> in [`../ADJUDICATION_GBAND_READING_A.md`](../ADJUDICATION_GBAND_READING_A.md).**
> **That document and [`READOUT_B32V64.json`](READOUT_B32V64.json) together are the verdict of
> record.** The mechanical `U-UNREADABLE` stands unedited in the JSON and in the tool's own
> rendering, [`READOUT_B32V64_TOOL_EMITTED_UUNREADABLE.md`](READOUT_B32V64_TOOL_EMITTED_UUNREADABLE.md).
>
> ⛔ **THE RULING WAS NOT BLIND.** The adjudicator printed `D`, `z_D` and `UB95(D)` beside the
> failed gate — in its console line **and in its emitted read-out** — a tool defect against the
> house §7 blindness protection. See §12 and [`../../DEVIATIONS.md`](../../DEVIATIONS.md) **D7.2**.

**generated (adjudicator):** `2026-08-23T03:06:30Z` · **blind commit:** `71b3286c` ·
**band:** `140000000000` · **read-rule:** SPENT

---

## 1. BRANCH: ⭐ `L-AMBIGUOUS`

# **UNRESOLVED — NEITHER A CONVICTED COST NOR A CONVICTED NON-INFERIORITY.**

**The deploy STAYS at `B` = 64 / `J` = 4 (the incumbent), and `B` = 128 is UNFUNDED BY DEFAULT.**
⛔ **Nothing closes and nothing is licensed.**

| | |
|---|---|
| `D` = `M_B64 − M_B32` | **+0.6460** pts/game |
| `se_D` | **0.4671** |
| `z_D` | **+1.3830** |
| ⭐ **`UB95(D)`** | **+1.4143** — **ONE-SIDED 95% UPPER BOUND ON THE COST**, against the **+0.93** pts/game tolerance |
| `EQUIV` (one_sided) | **FALSE** — `UB95(D)` = +1.414284 > 0.93 |
| `n_common` | **1,497 decks** |

**Branch selection, first-match-wins** ([READ_RULE](../READ_RULE.md) §4.1, §4.4):

| # | branch | condition | fires? |
|---|---|---|---|
| 1 | `U-UNREADABLE` | any §3 gate fails | **no** — `G-BAND` conjunct 4 DISCHARGED by owner Reading A; 13/13 |
| 2 | `L-REVERSED` | `z_D ≤ −2.0` | **no** — `z_D` = +1.3830 |
| 3 | `L-RISING` | `z_D ≥ +2.0` | **no** — the edge is `D ≥ 2·se_D = +0.9341`; realized +0.6460 |
| 4 | `L-SATURATED` | `UB95(D) ≤ +0.93` | **no** — the edge is `D̂ ≤ 0.93 − 1.645·se_D = +0.1617`; realized +0.6460, **4.0× over the edge** |
| 5 | ⭐ **`L-AMBIGUOUS`** | everything else | ⭐ **FIRES** |

⭐ **What the one-sided shape does to this branch: it is reachable ONLY FROM THE HIGH SIDE**
(`D̂ > 0.93 − 1.645·se_D`), because every `D̂` below that edge and above `L-REVERSED`'s fires
`L-SATURATED`. ⇒ **this read means the realized point estimate was too HIGH to bound the cost,
never too low.**

### 1.1 ⛔ MANDATORY SCOPE SENTENCE — quoted with the verdict, never separated from it

> *"This is an UNDER-POWERED one-sided non-inferiority test reading a high point estimate.
> [READ_RULE](../READ_RULE.md) §4.0 states before the run that `L-SATURATED` fires with EFFECTIVE
> probability 0.556 (committed dispersion) / 0.629 (realized-dispersion projection) even when the
> two rungs are exactly equal — so ~44% of the equal-rungs world lands here. **`L-AMBIGUOUS` is
> therefore NOT evidence that `B` = 32 is worse, and any read-out that presents it as such is
> over-reading it."*

### 1.2 The sign rider — `D` is POSITIVE, and what that does and does not mean

**`D` = +0.6460 > 0**, i.e. the point estimate has `CELL_B64` ahead of `CELL_B32` by 0.65
pts/game. ⛔ **That is a point estimate at `z` = +1.38 and it convicts NOTHING**: `L-RISING`
(`z_D ≥ +2.0`) did **not** fire, so *"dropping to `B` = 32 costs real game points"* is **not**
established by this cell. Symmetrically, `L-REVERSED` did not fire and no claim that `B` = 32 is
**better** is available either.

⚠️ **The `L-SATURATED` negative-`D` rider ([READ_RULE](../READ_RULE.md) §4.1 branch 4, third
rider) DOES NOT APPLY HERE** — it governs a *negative* realized `D` firing branch 4, and this
read is a positive `D` firing branch 5. It is named only so a reader can see it was checked and
found inapplicable, rather than silently omitted. `negative_D_disclosure` in the JSON is `null`
for the same reason.

### 1.3 The one citable product of this cell

⭐ **A ONE-SIDED 95% UPPER BOUND ON THE COST OF SWAPPING `B` = 64 → `B` = 32:
`UB95(D)` = +1.4143 pts/game ≈ +22.8 elo at this band's non-binding gloss.**

⚠️ **That bound is the ONLY thing this cell adds, and it is WIDER than the owner's ±15-elo
tolerance** — which is exactly why the branch is `L-AMBIGUOUS` rather than `L-SATURATED`. It
bounds the cost **above**, one-sided, at 95%; it is **not** an estimate of the cost, **not** a
statement that the cost is that large, and **not** a licence to swap or to stay on strength
grounds.

⛔ **The elo gloss ADJUDICATES NOTHING.** `16.1247` elo per pt/game is a **one-band, one-cell
empirical conversion** between two statistics of the `b64_cell`'s run; elo is a nonlinear
function of win-rate and the mapping is not a constant of nature. **Every branch condition in
this pair is written in pts/game.** (For reference only: `D` +0.6460 → +10.42 elo;
`UB95(D)` +1.4143 → +22.80 elo; the tolerance 0.93 → +15.00 elo.)

---

## 2. ⛔ THE MANDATORY POWER PRINT — the branch is NOT READABLE without it

[READ_RULE](../READ_RULE.md) §4.1 branch 5 requires four prints. All four, from
[`READOUT_B32V64.json`](READOUT_B32V64.json):

### (i) The realized statistics against the tolerance

```
D        = +0.6459585838343354  pts/game
se_D     =  0.4670671296585714
z_D      = +1.3830101559630938
UB95(D)  = +1.4142840121226854   ONE-SIDED 95% UPPER BOUND ON THE COST   vs TOLERANCE 0.93
CI90(D)  = [-0.1224, +1.4143]    two-sided 90% interval — CONTEXT ONLY, adjudicates nothing
```

⛔ **`CI90(D)` IS NOT A "90% CI" VERDICT AND MAY NEVER BE QUOTED AS THE PRIMARY.** Since
[`RULINGS_PREBLIND.md`](../RULINGS_PREBLIND.md) RULING 1 the primary is the **one-sided 95% upper
bound**; `1.645` here is `z_{0.95}`, the one-sided 95% critical value, doing a different job with
identical arithmetic. The interval is printed because §4.3 item 2 requires it, and it adjudicates
nothing.

### (ii) ⭐ The `n` that WOULD have resolved the REALIZED point estimate as a NON-INFERIORITY

At the **realized** per-deck dispersion (sd 18.0713), solving
`D_realized + 1.645·se(n) ≤ 0.93` ⇒ `se(n) ≤ (0.93 − 0.6460)/1.645 = 0.1727`:

| | |
|---|---|
| **decks per cell** | **10,954** |
| games per cell | 21,908 |
| **games total** | **43,816** |
| **two-box wall** | **257.97 h** (≈ 10.7 days) at the measured **35.56**-worker effective pool |
| worker-hours | 9,173.5 |

⇒ **≈7.3× this cell's `n`, for ≈7.3× the spend, to certify a point estimate this high as
non-inferior.** ⚠️ `no_n_resolves_it` is **false** — the realized `D` (+0.6460) is *below* the
0.93 tolerance, so an `n` does exist; it is simply enormous. (Had `D_realized ≥ 0.93` the rule
requires the read-out to state that **NO `n` resolves it** rather than print a number. That
clause did not fire, and is named so the reader can see it was evaluated.)

### (iii) The same `n` for a 2σ **COST** verdict

At the realized dispersion, to convict `z_D ≥ +2.0`:

| | |
|---|---|
| **decks per cell** | **3,131** |
| games per cell | 6,262 |
| **games total** | **12,524** |
| **two-box wall** | **73.74 h** |
| worker-hours | 2,622.1 |

⇒ **≈2.1× this cell's `n` to convict the cost the point estimate hints at.** ⛔ **Printing this
number is not a proposal to spend it**, and no branch of this pair licenses either re-run.

### (iv) §4.0's PRE-RUN power table — stated before the run, reproduced verbatim

```
                                      COMMITTED se_D = 0.5044        REALIZED-PROJ se_D = 0.4570
                                      raw     L-REV    EFFECTIVE     raw     L-REV    EFFECTIVE
true D = 0        (the rungs equal)   0.5788  0.0228   0.5560        0.6517  0.0228   0.6290
true D = +0.0399  (bracket FLOOR)     0.5476  0.0188   0.5288        0.6189  0.0184   0.6005
true D = +0.1555  (bracket TOP)       0.4564  0.0105   0.4459        0.5198  0.0096   0.5102

n for 80% one-sided power at a true D = 0  (se_D <= 0.93/(1.645+0.8416) = 0.37400):
   committed law  =>  n >= 2,728 decks/cell (5,456 games)
   realized law   =>  n >= 2,240 decks/cell (4,480 games)
   ⚠️ RAW one-sided figures; EFFECTIVE power at that n is ~0.777, because L-REVERSED still
      takes ~2.3% of the lower tail first.
```

> ⇒ *"IF `B` = 32 IS EXACTLY AS GOOD AS `B` = 64, THIS CELL NOW HAS A ~56% CHANCE (~63% AT THE
> REALIZED DISPERSION) OF BEING ABLE TO SAY SO — up from ~16% (~30%) under the drafted two-sided
> shape, at the same tolerance, the same `n`, and no extra spend. ⚠️ It is still not a
> well-powered test: ~44% of the equal-rungs world, and ~55% of the bracket-top world, still
> reads `L-AMBIGUOUS`. **That is a declared property of the owner-funded design, not a failure of
> it.** ⛔ No read-out may present `L-AMBIGUOUS` as evidence of a difference."*

### 2.1 ⭐ The dispersion did NOT fail this cell — the point estimate did

**The realized `se_D` = 0.4671 BEAT the committed law** (0.5044) by **7.40%**
(`dispersion_model_miss_x` = 0.9260), landing 2.2% above the non-binding realized-dispersion
projection 0.4570. It also **cleared the §4.0 knife-edge**: `se_D ≤ 0.4708` was the requirement
for the offline bracket TOP to be able to fire `L-SATURATED`, and 0.4671 clears it.

⇒ ⛔ **This is NOT a read that failed for want of precision.** The instrument delivered the
dispersion the design hoped for; **the realized point estimate `D` = +0.6460 is 4.2× the offline
bracket top (+0.1555) and 4.0× the `L-SATURATED` fire edge (+0.1617)**. The `L-SATURATED` window
at the realized `se_D` was `D̂ ≤ +0.1617`, and the realized `D̂` was nowhere near it. **More `n`
at this point estimate buys the certificate only at the 10,954-deck figure of (ii).**

---

## 3. §4.3 item 1 — both cells, in full

Both cells play the **UNMODIFIED production champion** as the common opponent. Each cell's own
margin / elo / win-rate is **SECONDARY and adjudicates nothing** (Stage 2 precedent: the margin
convicts, the win-rate does not).

| quantity | `CELL_B64` (incumbent shape) | `CELL_B32` (cheaper candidate) |
|---|---|---|
| `n` attempted (planned) | 3,000 | 3,000 |
| `n` completed (games) | **3,000** | **2,997** |
| `n_failed` | **0** | **3** |
| decks seat-balanced | 1,500 | 1,497 |
| `M` — deck-paired margin (pts/game) | **+5.2123** | **+4.5731** |
| `se` (recomputed) | 0.3421 | 0.3501 |
| `paired_z` | +15.2362 | +13.0629 |
| **elo vs the champion** *(SECONDARY)* | **+66.4644 ± 6.4597** (1σ) | **+56.8427 ± 6.4316** (1σ) |
| `wr` *(SECONDARY)* | 0.5945 | 0.5811 |
| `wr_z` | +10.3520 | +8.8775 |
| W / D / L | 1752 / 63 / 1185 | 1710 / 63 / 1224 |
| seat balance | `a_seat_0` 1500 / `a_seat_1` 1500 — **balanced** | `a_seat_0` 1498 / `a_seat_1` 1499 — **not balanced** ⚠️ |

- **`n_common` = 1,497 decks** — the denominator of `D`, and the only quantity a branch reads.
- **`M` on the common decks:** `CELL_B64` **+5.2191** · `CELL_B32` **+4.5731** ⇒ `D` = **+0.6460**.
  *(`CELL_B64`'s common-deck margin +5.2191 differs from its all-deck +5.2123 because the three
  dropped decks are excluded from the paired set; `CELL_B32`'s is unchanged, since it never had
  them.)*
- ⚠️ **The `CELL_B32` seat imbalance (1498/1499) is the direct footprint of the three failures**
  — one seating each, sibling seating successful. It is reported, and it is not a gate input.
- ⛔ **The two cells' elo figures are NOT a `B` = 32 vs `B` = 64 head-to-head.** No such contest
  was played. The elo gap (+9.62) is a **cross-cell difference of two same-band self-anchored
  numbers** and is **not** the primary; the primary is the deck-paired `D`.

---

## 4. §4.3 item 6 — ALL 13 §3 GATES, with realized values and scope markers, never short-circuited

| gate | scope | marker | result | realized |
|---|---|---|---|---|
| `G-J1` | `[PER-CELL]` | `[post-cells]` | ✅ PASS | `cand_leaf_hash` = `a36d2e15a3b3d71d` in **both** cells (resolved at `config.cand_leaf_hash`) — INVERTED gate: the arbiter moves NO leaf hash |
| `G-J4` | `[PER-CELL]` | `[post-cells]` | ✅ PASS | `CELL_B32` `{enabled:true, B:32, J:4, mode:argmax, salt:tiearb2-deploy-v1, eps:0.0}`; `CELL_B64` the same at `B:64`; singletons `tiearb_B` `[32]`/`[64]`, `tiearb_J` `[4]`, `tiearb_modes` `["argmax"]` |
| `G-J13` | `[PER-CELL]` | `[pre-run]` | ✅ PASS | 4 files (2 hosts × 2 `B`), all four **pinned** addresses present, both booleans `true`, `expected.B == j13_witness.B` — **STRICT read, no `two_sided.*` fallback**. Filenames in §4.1 |
| `G-NEST` | `[RUN]` | `[pre-run]` | ✅ PASS | `witness: true` — byte-identity + structural + tautology anchor. §4.2 |
| `G-FIRE` | `[PER-CELL]` | `[post-cells]` | ✅ PASS | `phi_effective` **17.5148** (`CELL_B32`) / **17.4717** (`CELL_B64`) vs floor **1.0** ⇒ ≈17× headroom; `error_rate_on_fired` 0.0 both |
| `G-DIVERGE` | `[RUN]` | `[post-cells]` | ✅ PASS | `1 − f₀` = **0.9880** vs floor **0.10** (≈9.8× headroom), beside the EXPECTED ≈0.98 — **not anomalous** (anomaly bar 0.95) |
| ⛔ **`G-BAND`** | `[RUN]` | `[pre-run]`+`[post-cells]` | ⛔ **FAIL** → **DISCHARGED** | conjuncts 1–3 PASS (sentinel pre-dated 2026-08-20 · sentinel = `140000000000` · both cells `band_seed_start` = `140000000000`, `same_band: true`); **conjunct 4 `same_decks: false`** — `n_decks` 1,497 vs 1,500, `decks_only_in[CELL_B64]` = `[140000001096, 140000001115, 140000001286]`, **`decks_only_in[CELL_B32]` = `[]`**. **DISCHARGED by owner Reading A 2026-08-22** — [`../ADJUDICATION_GBAND_READING_A.md`](../ADJUDICATION_GBAND_READING_A.md) |
| `G-N` | `[RUN]`+`[PER-CELL]` | `[post-cells]` | ✅ PASS | `n_common` **1,497** decks ≥ floor **1,200**; games **2,997** / **3,000** ≥ floor **2,400** — both clauses verified reachable before the run |
| `G-FAILED` | `[RUN]`+`[PER-CELL]` | `[post-cells]` | ✅ PASS | clause 1: **0.100%** (`CELL_B32`, 3/2,997) and **0.000%** (`CELL_B64`) vs the **2%** bar — 20× margin; clause 2 **did NOT fire** (`max(F)` = 3 < 5); clause 3 **HALTed and was CLEARED by the recorded owner confirmation**. §6 |
| `G-TOOL` | `[RUN]` | `[pre-run]`+`[post-cells]` | ✅ PASS | one build string across both boxes: `carc_rs-0.1.0+6542cffb2c30+rustcunpinned`. ⛔ `+rustcunpinned` is the NORMAL production value; 4 timestamped rotations excluded by name, recorded REPORT-ONLY |
| `G-PLY` | `[PER-CELL]` | `[post-cells]` | ✅ PASS | `tiearb_partial_argmax_total` = **0** in both cells (ABSENT would be unknown-not-zero and FAIL) |
| `G-STAT` | `[RUN]` | `[post-cells]` | ✅ PASS | no NaN / ±inf / absent in `D`, `se_D`, `z_D`, `UB95`, `CI90`, `z_32`, `z_64`; `se_D > 0` — evaluated **before** any branch comparison |
| `G-SMOKE` | `[RUN]` | `[post-smoke]` | ✅ PASS | `production_knobs` match `WORKERS.conf` field-for-field (`mismatched: {}`); `smoke_utc` **2026-08-21T05:55:55Z** < earliest cell record **2026-08-21T06:03:39Z**; `halt: false`; `launched_anyway: false` (**derived**, no operator flag); **0** forbidden outcome keys at any depth; emitter whitelist ok, reported beside the gate and not a gate input |

**12/13 PASS · 1 FAIL (`G-BAND`, conjunct 4 only) · 0 short-circuited.**

### 4.1 `G-J13` — RULING 4's condition discharged: the exact filenames consumed, per host

- **Doctor** · `verdicts/PREFLIGHT_Doctor_FIRST_B64.json` carried `j13_witness.B` = **64**
- **Doctor** · `verdicts/PREFLIGHT_Doctor_FIRST_B32.json` carried `j13_witness.B` = **32**
- **laptop-wsl** · `verdicts/PREFLIGHT_laptop-wsl_FIRST_B64.json` carried `j13_witness.B` = **64**
- **laptop-wsl** · `verdicts/PREFLIGHT_laptop-wsl_FIRST_B32.json` carried `j13_witness.B` = **32**

`n_files_consumed` = **4**, resolved **from the NAMED addresses** (pattern
`PREFLIGHT_{host}_FIRST_B{B}.json`), **4 superseded `_<epoch>` rotations EXCLUDED by name** and
recorded REPORT-ONLY, wired into no conjunct ([READ_RULE](../READ_RULE.md) §2.2). ⇒ **a
zero-match glob would read as ZERO, not as a silent pass.**

### 4.2 `G-NEST` — the witness, and its anchor

- **Structural** (`rust/carc/carc-core/src/tiearb.rs`, at HEAD): all four seeding sites found and
  **B-free** — `world_seed` `seed_i64(&[salt, digest, ply, js])` · `playout_seed`
  `…, js, "playout"` · `build_arms_cap` `…, "cap"` · `select_stream` `…, "select"`. Every one is
  a **pure function of `j` with no `B` term** ⇒ the world sets NEST.
- **Runtime byte-identity:** `n_compared` **32**, `worlds_byte_identical: true`,
  `world_seeds_identical` · `playout_seeds_identical` · `select_seed_identical` ·
  `cap_seed_identical` all **true**, `first_differing_j: null`,
  `n_distinct_worlds` **32** (lo) / **64** (hi).
- ⭐ **The tautology anchor REPRODUCED** ([`../GATE_NEST.json`](../GATE_NEST.json)
  `seed_i64_anchor.ok: true`): python `seed_i64` + `carc_rs.shuffle_indices` reproduced the RUST
  arbiter's own capped arm set **exactly** (4 arms of 10 candidates, `cap_seed`
  `5783025514736988432`) at a pinned position where **the cap genuinely fires**
  (`cap_actually_fired: true`; deck `28000000000`, seat 0, ply 32, digest
  `9099d17b7b4fa6da3655de5f5890f27e`, salt `tiearb2-deploy-v1`, 11 tie actions, 11 distinct
  afterstates).
- ⚠️ **Consequence, and it cuts against power, not for it:** `CELL_B64` is a **strict REFINEMENT**
  of `CELL_B32` (B=64's worlds 0..31 are byte-identical to B=32's *entire* set), so a large
  identical fraction is a **POWER LOSS** (`z_D ∝ √(1−f₀)`), **not** a power win.
- ⛔ `G-NEST` **adjudicates nothing** — it is a precondition witness that licenses the increment
  framing and moves no bar, branch or statistic.

---

## 5. §4.3 item 3 — the divergence block

| | |
|---|---|
| `f₀` (common decks with `D_i` **exactly** 0.0) | **0.012024** — 18 of 1,497 decks |
| `1 − f₀` | **0.98798** |
| `G-DIVERGE` floor | **0.10** ⇒ **headroom ≈9.8×** |
| EXPECTED (DESIGN §8.2, re-derived at this rung) | **≈0.98** |
| dilution `√(1−f₀)` | **0.99397** |
| anomaly bar (a value below this PASSES but must be reported as an ANOMALY) | 0.95 — **not triggered** |

- **The expected value was re-derived at this rung, not inherited:** the measured 32→64
  value-change fraction on this campaign's own R4 corpus is **0.4045 per fired ply**
  (`shared_run_r4/verdicts/per_position_s1.jsonl`, 1,340 plies), a deck carries ≈**34.96** fired
  plies ⇒ modelled `1 − f₀` = 1.0000, calibrated against the `b64_cell`'s realized 0.9840 at a
  31%-churnier rung ⇒ **EXPECTED ≈ 0.98**. Realized **0.98798** — the model landed.
- ⚠️ **Measurement disclosure:** `f₀` is measured as *"`D_i` exactly 0.0"*, which **OVERCOUNTS**
  identity (two different games can coincide on margin) ⇒ `1 − f₀` **UNDERCOUNTS** divergence ⇒
  **the floor is CONSERVATIVE: it can only fire early, never late.**
- ⛔ **`G-DIVERGE` is an INERTNESS DETECTOR, not a power check.** It passing says the `B` = 64
  surface is not inert relative to `B` = 32; it says nothing about whether this `n` could resolve
  the contrast.

---

## 6. §4.3 item 7 — the failed-record accounting, IN FULL

⛔ **Printed whether or not any failure occurred**, and the `failed_cells[]` dump is a **REPORT
wired into NO conjunct** ([DESIGN](../DESIGN.md) §13.2 item 2).

| | `CELL_B64` | `CELL_B32` |
|---|---|---|
| `n_failed` / `n_attempted` | **0 / 3,000** | **3 / 2,997** |
| realized rate vs the **2%** clause-1 bar | 0.00000 | **0.00100** (clears 20×) |
| `failure_rate` (emitter) | 0.0 | 0.001 |
| `failure_rate_trigger` | 0.005 | 0.005 |
| `validity_trigger_fired` | false | false |
| `tiearb_errors_total` | **0** | **0** |
| `tiearb_error_rate_on_fired` | 0.0 | 0.0 |
| `tiearb_first_error` | `null` | `null` |
| `tiearb_partial_argmax_total` | **0** | **0** |
| `resolved_failed_cells[]` | 0 — none | 0 — none |

**Clause 2 (candidate-correlation) did NOT fire:** `max(F) ≥ 5 AND max(F) > 3 × max(min(F), 1)`
— `max(F)` = 3 < 5. ⚠️ **`CELL_B64` carries ~2× the per-fired-ply exposure to the window-refusal
class**, so clause 2 binds **in the direction that protects the reading**; the realized split runs
the other way (3 in the *cheaper* cell).

### 6.1 The three failed games — raw surface, verbatim

| seed | `a_seat` | `attempts` | `permanent` | `exc_type` | `exc` | `window_truncation` | `window_diag` |
|---|---|---|---|---|---|---|---|
| 140000001096 | 1 | 1 | false | `PanicException` | `IndexError: board row index 35 out of range (len 35)` | **false** | `null` |
| 140000001115 | 0 | 1 | false | `PanicException` | `IndexError: board row index 35 out of range (len 35)` | **false** | `null` |
| 140000001286 | 0 | 1 | false | `PanicException` | `IndexError: board row index 35 out of range (len 35)` | **false** | `null` |

**All three in `CELL_B32`; `CELL_B64` had none. One seating each — the sibling seating of every
one of the three decks SUCCEEDED.**

### 6.2 Clause 3 — the escalation, and the owner's confirmation

`F_32 + F_64` = 3 > 0 ⇒ **clause 3 fired and the run HALTED BEFORE ADJUDICATION**
([`../ESCALATION_20260822.md`](../ESCALATION_20260822.md),
[`HALT_B32V64.json`](HALT_B32V64.json)). The class is **NOT** the known
`WindowTruncationError` (`window_truncation: false` on all three), so the narrowed clause-3 text
could not be satisfied mechanically and the pause held for the owner.

> **Owner 2026-08-22 (post-havdalah), verbatim: *"confirmed"*** — given per
> `ESCALATION_20260822.md` option 1: the 3 `PanicException` failures (the parked pre-existing
> engine board-bounds class, explicitly **NOT** `WindowTruncationError`) are ruled acceptable for
> this read-out.

⚠️ **A DELIBERATE, DISCLOSED EXCEPTION to "no owner call adjudicates any outcome":** it
adjudicates **NOTHING** — no branch, no bar, no statistic moves on it — **it decides only whether
the run pauses.** Recorded as an exception rather than hidden as a convention.

⭐ **The class, and where it goes:** the **parked rust engine board-bounds panic family**
(`carc-core/src/engine/mod.rs:411`, proven PRE-EXISTING 2026-08-17, triage unfunded), now
observed at ~0.1% in live production-knob games rather than only in fixture replay. **Not an
arbiter and not an instrument defect** (`tiearb_errors_total: 0` in both cells). **The three
reproducible seeds at production knobs are a triage lead the parked bug did not have before.**

### 6.3 The selection-effect disclosure — disclosed, not argued away

> *"window-truncation failures fire at extreme board extents, so any dropped set is **CORRELATED
> WITH BOARD GEOMETRY** — late-game, large-extent positions — and that correlation is DISCLOSED
> rather than argued away."*

Adapted to the realized class: the board-bounds panic also fires **at the grid edge**, so the
three dropped decks are **not a random subsample**. At **3/2,997 = 0.100%** with clause 2 silent
they cannot move `D`; **a 3-vs-0 split at these counts is p ≈ 0.09 under equal rates —
suggestive, not conviction**, and that too is disclosed rather than resolved.

---

## 7. §4.3 item 4 — the `phi` block

| | `CELL_B32` | `CELL_B64` |
|---|---|---|
| `phi` (fired tied tile plies / game) | **17.5148** | **17.4717** |
| `phi_effective` = `phi × (1 − error_rate_on_fired)` | **17.5148** | **17.4717** |
| `G-FIRE` floor | 1.0 | 1.0 |

- **Cross-cell `phi` difference: −0.0432** (`CELL_B64` − `CELL_B32`).
- Beside the **offline prior 22.96**, the **committed 17.481**, and the `b64_cell`'s realized
  **17.5533 / 17.4087**.
- ⚠️ **[DESIGN](../DESIGN.md) §7.2's assumption, restated rather than assumed away:** *the trigger
  predicate does not depend on `B`, so `phi` should be `B`-invariant AT THE SAME POSITION — but
  the cells diverge onto different boards, so realized `phi` can differ.* The realized difference
  is 0.25% of `phi` and is printed for that reason.
- **No fail-soft arbiter errors in either cell** ⇒ `DILUTION_STATEMENT_REQUIRED: false` (bar 0.05),
  `dilution_statement: null`. `phi_effective` is a branch input **only** through `G-FIRE`'s floor.

---

## 8. §4.3 items 5 + 8 — COST: reported on every branch, a branch input NOWHERE

⛔ **THERE IS NO AFFORDABILITY PREDICATE IN THIS PAIR, AND THE ABSENCE IS DECLARED RATHER THAN
LEFT TO BE NOTICED.** The `b64_cell`'s `A` / `W` / `OWNER_WAIVER.md` machinery is **absent by
design**: the N4 `rho_wall ≤ 1.20` bar it enforced was **WAIVED at `B` = 64** by
[`../../b64_cell/OWNER_RULING_20260820.md`](../../b64_cell/OWNER_RULING_20260820.md) ruling 1.
**Cost is reported on every branch and grades nothing.**

### 8.1 ⚠️ THE FIELD-NAME TRAP — named beside every `ms_ratio`

> ⚠️ **`champ_prefix_ms_per_move` IS THE CANDIDATE SIDE in `eval_fair_puct`** (lines
> 2361/2371/2389 — **the opposite of `eval_puct_priors`**). **A read-out that swaps them INVERTS
> the cost verdict.**

| per-move timing | `CELL_B32` | `CELL_B64` |
|---|---|---|
| `champ_prefix_ms_per_move` — ⚠️ **the CANDIDATE (arbiter) side** | **6,824.43 ms** | **11,912.54 ms** |
| `rung_ms_per_move` — the **opponent** (unmodified champion) side | 1,793.02 ms | 1,807.42 ms |
| `ms_ratio` = candidate / opponent — **realized** | **3.8061** | **6.5909** |
| `ms_ratio` — **predicted** (§9.4) | 3.74 | 6.608 |
| prediction miss | +1.8% | −0.3% |

⭐ **The §9.4 prediction-vs-realized table is printed on every branch: a wrong cost model must
stay visible even where no bar is enforced.** Here the model was right to within 2% on both cells.

⚠️ **The smoke's `ms_ratio` and the cells' `ms_ratio` are both printed and NEITHER grades the
other** — a bar written after a smoke number exists is not a bar, and no such bar was
pre-registered.

### 8.2 The cost facts of record

| | value |
|---|---|
| `rho_wall` at `B` = 16 / 32 / 64 / 128 | 0.6224 / **1.2449** / **2.4897** / 4.9794 |
| the house **N4 bar 1.20** | ⛔ **WAIVED AND RETIRED at `B` = 64** — printed as **HISTORY**, never as a test |
| total per-move wall vs the champion baseline | **2.2449×** at `B` = 32 · **3.4897×** at `B` = 64 |
| **the swap-down prize** | **≈2.24 s/move saved at the 1.8 s/move baseline = −35.7% of the per-move wall** |
| `rho_phone` at `B` = 32 / 64 | [11.04, 11.95] / [22.08, 23.90] — ⛔ **NOT SOLVED — a THIRD CURRENCY.** The mobile profile plays the **unmodified champion** and no branch here changes that |

⚠️ **The prize is real and this branch does NOT license buying it.** `L-AMBIGUOUS` licenses no
swap-down decision; the −35.7% figure is printed because §4.3 item 8 requires it, and it is the
reason the question will keep asking to be re-opened.

### 8.3 The realized bill — and one mandatory print the adjudicator did NOT emit

| | committed | realized |
|---|---|---|
| worker-s/game, `CELL_B64` | **928.025** (MEASURED on the `b64_cell`'s WIDE) | ⚠️ **NOT EMITTED** — `cost_facts.worker_s_realized.CELL_B64` is `null` |
| worker-s/game, `CELL_B32` | **579.389** (PROJECTED — [DESIGN](../DESIGN.md) §7.2, **graded NOWHERE**) | ⚠️ **NOT EMITTED** — `null` |
| two-box wall | **35.33 h** (§7.5) | ≈**24.5 h** — ⚠️ **sentinel-derived, not adjudicator-emitted** (see below) |
| worker-hours | 1,256.2 | not emitted |
| effective pool | **35.560** workers (measured, §7.5); occupancy derate 1.4623 | — |

⚠️ **DISCLOSED RATHER THAN PAPERED OVER: [READ_RULE](../READ_RULE.md) §4.3 item 8 requires *"the
realized worker-s/game for both cells against §7.2's committed 579.389 / 928.025"*, and the
adjudicator emitted `null` for both.** The figure is not recoverable from
[`READOUT_B32V64.json`](READOUT_B32V64.json), so it is reported as **absent**, not invented.
**The only MEASURED cost of record for this run is the smoke's** — see §8.4.

⚠️ **The ≈24.5 h wall is an OBSERVATION off the run sentinels, NOT an adjudicator emission and
NOT a graded quantity:** earliest cell record `2026-08-21T06:03:39Z` → last cell sentinel
`DONE_cells_B64` at `2026-08-22T06:33:56Z` = **24 h 30 m** (with `DONE_cells_B32` at
`2026-08-21T15:30:24Z` = 9 h 27 m). It came in **under** the committed 35.33 h. It is labelled as
an observation because a wall-clock figure derived from file mtimes is not the currency
[DESIGN](../DESIGN.md) §9.3 costs in — *"the house forbids costing from wall clock"*.

### 8.4 The §9.3 HALT record — one-sided, and it did not fire

| | |
|---|---|
| bar | **1,392.038** worker-s/game = **1.50 ×** 928.025 |
| realized (**smoke**, `CELL_B64`) | **843.323** worker-s/game |
| `halt` | **false** — an overrun HALTS, an **underrun proceeds** |
| graded cell | ⭐ **`CELL_B64` ONLY** — the one cell whose cost is MEASURED rather than projected. **`CELL_B32`'s realized cost is printed against its projection and graded NOWHERE (§9.4); grading a 1.50× bar against a projection would be grading a model against itself.** |

- **Cost definition, the pair's own:** `worker_secs_per_game = SUM(seed*.json::elapsed_s) / n`.
  ⛔ **NEVER `wall × W / n`** — §9.3 names that very substitution as the currency error behind
  Stage 2's cost miss.
- ⛔ **There is NO override flag.** A HALT would have held until the owner ruled (stop, or re-fund
  at the realized cost); `run_cells.sh` refuses a real-cell launch on `halt == true`, and
  `launched_anyway` is **derived** (`halt ∧ cells_ran`), not supplied by an operator.

### 8.5 The cost immunity, stated in the half that is true

> *The two cells are **NOT** cost-matched — `CELL_B64` spends ~**1.60×** the worker-seconds per
> game of `CELL_B32` — **but NEITHER CANDIDATE'S SEARCH BUDGET MOVES**: both run the identical
> champion at k8×1376 with identical sims, and the arbiter fires **AFTER** the search, at the
> root, on an already-resolved tie ⇒ **the extra cost buys NO extra search.** It is a **WALL-CLOCK
> ASYMMETRY** and is disclosed as one on every branch, never claimed away.*

---

## 9. §4.3 items 9 + 10 — the offline ladder (DESCRIPTION) and the translation caveat (VERBATIM)

### 9.1 The offline ladder — a DESCRIPTION, explicitly NOT a projection

`arb(32)` = **0.1942** · `arb(64)` = **0.2015** · `Δ(32→64)` = **+0.0073** pts/tied ply · ratio
**1.038** · the §5.2 bracket **[+0.0399, +0.1555]** pts/game.

⛔ **MUST NOT be presented as a projection of the game effect.** The offline ratio 1.038 is a
**description of the offline ladder**; the bracket is a **WIDTH**, and **NEITHER ENDPOINT IS A
PROJECTION.**

⚠️ **The realized `D` = +0.6460 is 4.2× the bracket top.** That is a fact about the bracket and
about this cell's realized draw at `z` = +1.38; it is **not** a third data point in the
offline→game map, because it convicts nothing.

### 9.2 Carried VERBATIM — the 3.9× translation caveat, BOTH directions

> **translation caveat:** *"⚠️ The offline→game translation factor is not established. Stage 1b's
> +0.1441 pts/tied ply predicts +0.79 pts/game (× phi 17.57 / non_additivity 3.2); Phase B
> realized +3.07 — a 3.9× under-prediction."*

> **both ways:** *"CAMPAIGN ruling 5 binds in BOTH directions: Stage 1b's offline read
> under-predicted the Phase B game cell 3.9× … so the offline→game map is unestablished and
> +0.0670 × 3.9 is not a projection either."*

> **the second datum:** *"the `b64_cell`'s §5.2 bracket for Δ(16→64) was [+0.368, +1.435] and it
> realized +1.7167 — **the map missed LOW TWICE, at n = 2, in the SAME direction.** ⛔ Still not a
> licence to multiply."*

> **`b64_cell` scope fence:** *"⛔ No branch re-adjudicates the `b64_cell`. Its verdict of record
> is `B-COSTKILL`, its read-rule is SPENT and its band 139e9 is RETIRED. **No comparison against
> its numbers is a branch input anywhere.**"*

---

## 10. §4.3 item 11 — ⛔⛔ CROSS-BAND HUMILITY — mandatory, not optional prose

| rung | band | elo vs the unmodified champion | status |
|---|---|---|---|
| `B` = 16 | 139000000000 | +36.2644 | **RETIRED band** |
| `B` = 64 | 139000000000 | +63.9457 | **RETIRED band** |
| `B` = 32 | **140000000000** | **+56.8427** | this cell |
| `B` = 64 | **140000000000** | **+66.4644** | this cell |

- **Over-dispersion: 1.8–2.2× in BOTH statistics** (CLAUDE.md cross-band humility).
- ⛔⛔ **The 139e9 numbers MUST NOT be pooled with the 140e9 numbers, plotted as one curve without
  the band labels, or differenced to produce any estimate.** Band 139e9 is **RETIRED from
  confirmatory use and cannot support a new verdict at all.** **THE ONLY ROBUST CONTRAST IN THIS
  RUN IS THE WITHIN-BAND DECK-PAIRED `D`, and it is the only branch input.** The table may be
  **SHOWN, with its band column, as a DESCRIPTION** — never fitted, differenced across bands, or
  called a curve measurement.
- ⛔ **No branch resolves the ladder's SHAPE, and no branch may name `B` = 32, 64 or 128 an
  optimum.** Two points in game points cannot separate "log-linear", "saturating-exp" and
  "√B-noise".

---

## 11. §4.3 items 12 + 13 — the band, and this rule's own blind commit

- **Band `140000000000`**, decks **`140000000000..140000001499`** (`deck_seed_min` 140000000000,
  `deck_seed_max` 140000001499). Claim sentinel
  [`../BAND_CLAIM.json`](../BAND_CLAIM.json), `claimed_before_game_1: true`, dated **2026-08-20**;
  registry row in [`../../../../governance/BAND_REGISTRY.csv`](../../../../governance/BAND_REGISTRY.csv).
- ⛔ **The band is ONE-USE and RETIRES from confirmatory use at close-out on EVERY branch** —
  including this one. Flipped to `status=retired`, `decision_influenced=yes` at close-out.
- **Blind commit `71b3286c`** — [`../DESIGN.md`](../DESIGN.md) and
  [`../READ_RULE.md`](../READ_RULE.md) landed in the **SAME commit before game 1** (stamped by
  `7fd9c8de`), and **the band claim (2026-08-20) PREDATES that commit (2026-08-21)** — that
  ordering is itself printed here, as [DESIGN](../DESIGN.md) §12.2 requires.
- **`RULINGS_PREBLIND.md` RULING 1 (owner, 2026-08-21):** `EQUIV_SHAPE` = **`one_sided`**,
  `TOLERANCE_PTS` = **0.93** — both READ fail-closed from
  [`../WORKERS.conf`](../WORKERS.conf), changeable with no code edit, with no coerced default.

---

## 12. ⛔ BLINDNESS DISCLOSURE — MANDATORY, and it is about THIS read-out's own tooling

# **THE ADJUDICATOR PRINTED `D`, `z_D` AND `UB95(D)` BESIDE THE FAILED GATE. THE OWNER'S READING-A RULING WAS THEREFORE NOT BLIND TO THE OUTCOME IT COULD AFFECT.**

**The rule breached**, verbatim ([`../../shared_run/READ_RULE.md`](../../shared_run/READ_RULE.md)
§7, the campaign's standing blindness protection):

> *"**On `W-UNREADABLE` (any gate FAIL): the harness report prints GATE INPUTS ONLY — no `arb`,
> no `ora`, no `Δ`, no CI, no per-position statistic.** This is a hard requirement: on 2026-08-17
> a mandatory companion table printed alongside a gate failure made the orchestrating session
> non-blind and forced the fixes to be written by a separate blind session."*

…and this pair's own restatement, [READ_RULE](../READ_RULE.md) §4.1 row 1: *"⛔ The read-out may
**not** print `D`, `z_D` or a branch label as if adjudicated."*

⚠️ **The leak surface is WIDER than a console line, and the correction is recorded rather than
softened.** It is in the **emitted artifact** as well:
[`READOUT_B32V64_TOOL_EMITTED_UUNREADABLE.md`](READOUT_B32V64_TOOL_EMITTED_UUNREADABLE.md),
preserved byte-identical, prints the full §4.3 item-2 `D` block (`D`, `se_D`, `z_D`, `UB95(D)`,
`CI90`, `EQUIV = False`, both resolving-`n` figures) **under a `U-UNREADABLE` heading**, and its
gate table leaks `UB95` again in the `G-STAT` row. **The `U-UNREADABLE` suppression clause was
enforced by nothing but the read-out author's discipline, and it leaked on the first gate failure
this campaign's game cells ever had.**

**Why the ruling is nonetheless defensible — the argument, made in advance:**

1. ⭐ **Reading A lands on `L-AMBIGUOUS`, the one branch of five that LICENSES NOTHING AND FAVORS
   NO ONE.** Under Reading B the run is void and also licenses nothing ⇒ **the two readings
   differ in what is RECORDED, not in what is AUTHORIZED.**
2. ⭐ **The orchestrator's written recommendation stated IN ADVANCE that a non-blind ruling toward
   any REWARDING branch would instead have drawn a "stand + fresh-band re-run" recommendation** —
   i.e. had the statistics selected `L-SATURATED` (which licenses the one-word swap-down and
   kills `B` = 128) or `L-RISING` (which licenses a `B` = 128 prereg), the recommendation would
   have been to let `U-UNREADABLE` stand and re-run on a fresh band under a fixed successor pair.
   **The asymmetry was declared before the ruling, not discovered after it.**

⛔ **This does not make the ruling blind, does not retroactively satisfy §7, and sets NO
precedent.** ⛔ **And the defect is NOT patched into this adjudicator** — it is a **spent** tool
for a **SPENT** read-rule, and editing it now would change the instrument that produced the
artifact of record after the fact. **The fix is owed to any successor adjudicator**
([`../../DEVIATIONS.md`](../../DEVIATIONS.md) **D7.2**).

---

## 13. ⚠️ SPEC-vs-BUILDABLE — REPORTED, never resolved by the adjudicator

Seven mismatches were found by the draft and carried; none was resolved at read time.

| where | status | one line |
|---|---|---|
| `G-FAILED` clause 3 / DESIGN §8.1 | **REPORTED — carried as drafted** | `eval_fair_puct` emits no `diagnostic_class`; the per-failure surface that DOES exist is printed and wired into **no** conjunct. ⛔ **NOT PROMOTED HERE** — wiring a new address into a conjunct after sign-off is how the three unsatisfiable gates shipped |
| `G-J13` / DESIGN §3 | ⭐ **CLOSED — strict read** | all four addresses read STRICTLY at the pinned paths, **no `two_sided.*` fallback**; `preflight.sh` asserts them on the emitting host before that host's game 1 |
| `G-SMOKE` / DESIGN §9.2 | **CARRIED — RULING 1 implemented** | two surfaces: the EMITTER whitelist (write, fail-closed) vs the GATE row (fires only on forbidden **outcome** keys). Structural keys never fire the row |
| DESIGN §13.2 item 7 | ⭐ **CLOSED — moved, not re-derived** | `nest_witness` COPIED into this cell's module; `analyze_b64_cell.py` (a SPENT run's tooling) UNTOUCHED |
| DESIGN §9.3 HALT bar (R1 finding B6) | ⭐ **CLOSED — three links, all enforced** | ⛔ the bar had been **UNENFORCED END-TO-END** and the gate conjunct hung on an operator `store_true` flag whose **default was the PASSING value** — a pass-always gate. Flag **DELETED**; `launched_anyway` now derived |
| READ_RULE §2.2 / `G-TOOL` (R1 finding B7) | ⭐ **CLOSED — one resolution path** | rotation-exclusion now on the REAL adjudication path, not just `knowngood`; an operator glob can no longer fail a healthy run |
| READ_RULE §4 `EQUIV` / `WORKERS.conf` | ⭐ **RULED — parameterized** | the bar is owner-ruled and changeable with **no code edit**; committed value `one_sided` (RULING 1, 2026-08-21) |

⚠️ **Note the pattern this cell kept catching and one it did not:** three of the seven are
**pass-always / fail-always** defects found *before* the run. The **fourth** — `G-BAND` conjunct 4
vs `G-FAILED` — was found **after** it, because it is a **pairwise** contradiction that no
single-gate audit and no zero-failure known-good fixture can surface
([`../../DEVIATIONS.md`](../../DEVIATIONS.md) **D7.1**).

---

## 14. ⛔ WHAT THIS CELL LICENSES: NOTHING

- ⛔ **`governance/PRODUCTION.yaml` is UNTOUCHED.** The deployed shape stays **`B` = 64 / `J` = 4**
  (desktop; the phone plays the **unmodified champion**, arbiter OFF).
- ⛔ **No swap-down decision is put to the owner.** That is `L-SATURATED`'s licence and it was not
  earned. The ≈2.24 s/move prize stands **unbought**.
- ⛔ **`B` = 128 is UNFUNDED BY DEFAULT** — neither licensed (that is `L-RISING`'s) nor killed
  (that is `L-SATURATED`'s). Re-opening it needs a **fresh prereg and fresh owner funding**.
  `rho_wall(128)` = **4.9794** travels with any mention of the rung.
- ⛔ **No claim is minted** in `governance/CLAIM_REGISTRY.csv` — the campaign's instrument
  precedent (rung 2's `W-RISING`, rung 3's `X-INCONCLUSIVE` and the `b64_cell`'s `B-COSTKILL`
  minted none either). The citation is the `results.csv` row, with the usual **self-anchored
  caveat**: elo vs *our own* champion within band 140e9, **not absolute strength**.
- ⛔ **No on-device / phone deploy.** `rho_phone` ∈ [11.0, 11.95] at `B` = 32 and [22.08, 23.90]
  at `B` = 64 — a **third currency**, never solved.
- ⛔ **`J` stays 4** (`rung3_r5` read `X-INCONCLUSIVE`); no change to `eps`, the salt, the trigger
  predicate, the playout, or the champion; **no ruler or eval baseline is re-anchored**.
- ⛔ **No branch re-reads or re-adjudicates** Stage 1, Stage 1b, Phase A, Stage 2 Phase B, the R4
  widening run, `rung3_r5`, or the `b64_cell`. They stand as adjudicated.

---

## 15. Numbers of record, and the SPENT footer

**Verdict of record = [`../ADJUDICATION_GBAND_READING_A.md`](../ADJUDICATION_GBAND_READING_A.md)
+ [`READOUT_B32V64.json`](READOUT_B32V64.json) ⇒ `L-AMBIGUOUS`.**
Mechanical record (unedited): `READOUT_B32V64.json::branch` = `U-UNREADABLE`, rendered in
[`READOUT_B32V64_TOOL_EMITTED_UUNREADABLE.md`](READOUT_B32V64_TOOL_EMITTED_UUNREADABLE.md).
Escalation: [`../ESCALATION_20260822.md`](../ESCALATION_20260822.md) +
[`HALT_B32V64.json`](HALT_B32V64.json).
Deviations: [`../../DEVIATIONS.md`](../../DEVIATIONS.md) **D7.1**, **D7.2**.
Governing pair: [`../DESIGN.md`](../DESIGN.md) + [`../READ_RULE.md`](../READ_RULE.md), blind
commit `71b3286c`.
`results.csv` row:
`tiearb_widening_b32v64_gamecell_B64_minus_B32_n1497decks_b140e9` · DECISIONS 2026-08-22.

> ⛔ **THIS READ-RULE IS SPENT.** It is spent on **every** branch, and band `140000000000`
> **RETIRES from confirmatory use**. Any successor — a `B` = 128 cell, a head-to-head cell behind
> an opponent-side knob, or an extension of `n` — needs a **FRESH PAIR AND A FRESH BAND**. ⛔ No
> branch licenses a second game cell, and this one licensed nothing at all.
