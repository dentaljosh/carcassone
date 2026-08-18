# TIE-ARBITER WIDENING — RUNG 1: `B > 16` (PLAN)

> **STATUS: PLAN ONLY, NOT A PREREGISTRATION.** No DESIGN, no READ_RULE, no band claim,
> no instrument change, no compute. This document sizes the rung and names the work
> items so the owner can fund or decline. The blind prereg (DESIGN + mechanical
> READ_RULE, committed in one commit before one position is scored) is a *separate*
> deliverable and is what §4 sketches.
>
> Paper-only under the 2026-08-17 commit freeze: nothing under `rust/`, `src/`,
> `engine/`, `scripts/classical_search/` is touched or proposed for this rung.

Evidence this extends: [tiearb2_20260816](../tiearb2_20260816/READOUT.md) (Stage 1b,
`A-COSTLY`, ladder `B ∈ {1,2,4,8,16}`) ·
[tiearb2_stage2_20260817](../tiearb2_stage2_20260817/READOUT.md) (Phase A rust port +
cost; Phase B game cell `G-CONFIRMED`).
Owner funding words: *"B > 16 — as above; ladder shape says real, measurement is cheap."*

---

## 0. Three facts established by reading the instrument (all load-bearing)

**0.1 Prefix-stability holds in `M`, and it is stronger than the DESIGN claimed.**
`oracle_score_pilot.world_seed(rid, j, salt) = sha_int("world", rid, j, salt)` and
`playout_seed` likewise — **`M` never enters**. So a run at `M = 128` reproduces
worlds `0…31` *bit-identically* to Stage 1b, and every `B ≤ 64` is a sub-read of one
paid run. The `B ≤ 16` rungs are therefore a **free replication of Stage 1b's entire
ladder on the fresh corpus** (gate `G-REPLICATE`, §4).

**0.2 ⚠️ `M = 64` does NOT buy `B = 64`. The brief's arithmetic is off by 2×.**
The estimator cross-fits on **parity halves** (`analyze_tiletie.parity_indices`):
selection uses one 16-world half of `M = 32`, pricing the other. `B` is capped by the
**selection half**, not by `M`. `B ∈ {16,32,64}` therefore needs **`M = 128`**
(sel = 64, eva = 64). This is not a cost surprise — see 0.3 — but every ETA in the
brief must be doubled.

**0.3 The ARB judge can now run rust, and that is what makes this rung cheap.**
Stage 1b scored `tier1-greedy` on the **python** backend
(`run_tiletie.JUDGE_BACKEND = {"clair-puct": "rust", "tier1-greedy": "python"}`) at
`c = 2.18–2.73` worker-s/playout. Phase A's port is **`G-BITEXACT` 15,360/15,360** at
`c_tier1_rust = 0.178232` — **12.2×** cheaper — and is already exposed as
`carc_rs.tier1_leg(...)`. Wiring it in is instrument work item **W1**. After that the
selection side is ~7% of the run and **`clair-puct` pricing is ~93% of the bill**.

**0.4 No rust change is needed for any widening rung.** `--cand-tiearb-b` (default 16),
`--cand-tiearb-j` (4) and `--cand-tiearb-eps` (0.0) are already runtime flags of
`eval_fair_puct.py`, and `tiearb::arbitrate` takes `b` as a parameter. The freeze does
not block this rung; only `scripts/tiletie/` needs edits.

---

## 1. What the ladder predicts — five saturating fits to the 5 banked rungs

Fitted to the published `arb_H` ladder (+0.0094 / +0.0322 / +0.0920 / +0.0826 /
+0.1441; `ora` = +0.1801). Bootstrap = 300 root-resamples of `per_position.jsonl`.

| model | fitted params | Δ(16→32) | **Δ(16→64)** | 90% CI on Δ(16→64) | arb(64) |
|---|---|---|---|---|---|
| log-linear in `log2 B` | slope +0.0320/doubling | +0.0320 | **+0.0640** | [+0.035, +0.100] | +0.200 |
| hyperbolic `L·B/(B+K)` | L 0.221, K 9.24 | +0.0314 | **+0.0530** | [+0.008, +0.190] | +0.193 |
| power `a·B^p` | a 0.0255, p 0.622 | +0.0771 | **+0.1958** | [+0.054, +0.980] | +0.339 |
| saturating exp `L(1−e^{−B/τ})` | L 0.156, τ 7.23 | +0.0152 | **+0.0171** | [0.000, +0.232] | +0.156 |
| selection-noise `L(1−k/√B)` | L 0.166, k 1.008 | +0.0122 | **+0.0209** | [+0.011, +0.033] | +0.145 |

Two live worlds: **still-rising** (log-linear / hyperbolic / power, Δ(16→64) ≈ +0.05
to +0.20) and **saturated** (sat-exp / √B-noise, Δ(16→64) ≈ +0.02). ⭐ **The rung's job
is to separate those two, not to estimate Δ to three digits.**

⭐ **Mechanistic corroborant, free and already banked:** the *pick-churn* per doubling
is **flat** — 0.303 / 0.309 / 0.290 / **0.287** at 1→2 / 2→4 / 4→8 / 8→16. A selector
that had converged would churn less each doubling. Oracle-agreement also still climbs
monotonically (0.4270 → 0.4285 → 0.4326 → 0.4359 → 0.4430 vs a 0.3704 random floor).
Both say *still rising*, independently of the noisy value read.

---

## 2. Power — and a measured variance law that changes the design

⚠️ Sizing on the **increment**, not the level: `Δ = arb(B_hi) − arb(B_lo)` is **exactly
0** at every position whose pick does not flip, so it is far better paired than two
independent levels. Banked, `se(Δ 8→16)` = **0.0290** vs `se(arb_16)` = 0.0479 (0.61×).

**New measurement (this analysis, 900 banked positions re-priced from the per-world
records; a nuisance-parameter read off a spent corpus, adjudicates nothing):**

```
Var(Δ ; E)  =  T + N/E          E = number of EVALUATION (clair-puct) worlds
Δ(8→16):  T = 0.19  (boot 90% CI [−0.10, +0.48])   N = 15.4
Δ(4→8) :  T = 0.15                                  N = 16.8
observed:  var@E=2 7.54 · E=4 4.42 · E=8 2.12 · E=16 1.16   (a clean 1/E law)
validation: predicted se(Δ 8→16) at n=1350,E=16 = 0.0297 vs published 0.0290 ✓
```

**≈84% of the increment's variance is clair-puct pricing noise, not position
heterogeneity.** That inverts the obvious plan. Minimising total cost subject to a
target `se`, with corpus generation priced in (≈623 worker-s per usable position — the
fresh champion self-play, §3), gives:

| E (eva worlds) | M_if | n needed for se(Δ 16→64)=0.020 | relative total cost |
|---|---|---|---|
| 8 | 16 | 5,500 | 2.26 |
| 16 | 32 | 3,400 | 1.44 |
| 32 | 64 | 2,100 | 1.08 |
| **64** | **128** | **1,350** | **1.00** ← optimum |
| 128 | 256 | 970 | 1.16 |

⇒ **Buy worlds, not positions.** `E = 64` pairs exactly with the `M = 128` that `B = 64`
already forces (0.2), so the design collapses to **`M = 128`, Stage 1b's estimator
verbatim, `n` unchanged at 1,350.**

**Sized read at `n = 1,350`, `M = 128`:** `se(Δ 16→64) ≈ 0.0198–0.0203`; **2σ floor
= +0.040**. That **resolves** log-linear (+0.064), hyperbolic (+0.053) and power
(+0.196); it **cannot** resolve sat-exp (+0.017) or √B-noise (+0.021) — those read as a
2σ null, which *is* the "saturated" answer. Pre-register that limitation: a null here
means "no rung above 16 is worth ≥ +0.04 pts/tied ply", **not** "Δ = 0".
(Resolving a +0.02 residual at 2σ needs n ≈ 5,700 — ≈ +1,100 worker-h, mostly corpus.
Not recommended; see §6 Q4.)

Secondary: Δ(16→32), `se ≈ 0.018`, 2σ floor +0.036 — under-powered by design, reported
with its CI, **never a branch input on its own**.

---

## 3. The instrument extension, and what one paid run costs

**Design:** fresh root-disjoint corpus, `n = 1,350`, **`M = 128`** for both judges,
`clair-puct` (rust) pricing / `tier1-greedy` (**rust**, W1) selection, salt
`tiletie-v1`, parity-base 1, symmetrised over both folds — **every knob Stage 1b's, only
`M` moves**. Arm sets recorded **UNCAPPED** (§5). Sub-reads from the one run:
`B ∈ {1,2,4,8,16,32,64}` × `E ∈ {16, 64}`; the `(B ≤ 16, E = 16)` corner is
bit-identical to Stage 1b's estimator on fresh positions.

Playout accounting is the instrument's own (`POSITIONS_PLAN.formula`):
`playouts_per_judge = n × 2 × (Ā − 1) × M`, with uncapped `Ā ≈ 3.581`
(banked capped `Ā` = 3.0022; post-dedup uncapped/capped arm ratio 3.349/2.807).

| item | worker-s | worker-h |
|---|---|---|
| fresh champion self-play (≈850 games × 990 s; the disjointness supply) | 841,500 | 233.8 |
| champion picks (1,350 × 13.7552) | 18,570 | 5.2 |
| **ARB** `tier1-greedy` rust — 891,993 playouts × 0.178232 | 158,977 | **44.2** |
| **IF** `clair-puct` rust — 891,993 playouts × 2.35 *(measured off banked `elapsed_secs`)* | 2,096,183 | **582.3** |
| **TOTAL** | 3,115,230 | **865.5** |

**ETA.** W30 local + W22 laptop = 52 workers → **16.6 h** at parity; with a 25%
laptop-slowness + contention allowance, **≈ 20–22 h wall** (corpus ≈ 5 h, scoring
≈ 15 h). Both boxes are busy — this queues behind the live measurement.
⚠️ Same-box, uncontended `c` values; the §0.G currency lesson applies to the *deploy*
figures below, not to this table, which is already in worker-seconds.

**Instrument work items (all under `scripts/tiletie/`, none in the freeze set):**
W1 wire `tier1-greedy` → `carc_rs.tier1_leg` + re-verify the identity gate at HEAD ·
W2 confirm no hard-coded 32 downstream of `--m` · W3 `analyze_tiearb2.py`:
`m_expected` 128, `b_ladder` {1,2,4,8,16,32,64}, `E` sub-read, `J ≤ 4` sub-arm-set
reconstruction from the committed seeded draw · W4 `build_positions.py`: emit uncapped
arm sets + the draw index · W5 `gate_disjoint.py` against
`EXCLUDE_RIDS_all.txt ∪ {the Stage-1b 1,350}`.

---

## 4. Gates and branches — skeleton for the mechanical READ_RULE

**Preconditions (any failure ⇒ `W-UNREADABLE`, a harness report, nothing licensed):**
`G-DISJOINT` (no shared game / position / board with either spent corpus) ·
`G-CRN` (world+playout seeds bit-identical across judges) · `G-BITEXACT@HEAD`
(re-run Phase A's gate on the rust ARB backend) · `G-PREFIX` (worlds 0…31 of this run
byte-equal to `world_seed(rid, j, "tiletie-v1")`) · completion ≥ the committed floor.

⭐ **`G-REPLICATE` (free, and it is the strongest new check this rung buys):** the
`(B ≤ 16, E = 16)` sub-read must land within 2σ of Stage 1b's ladder, with
`arb(16) z ≥ +2.0`. Fail ⇒ **UNINTERPRETABLE, never FAIL** — the fresh corpus is not
the same population and no widening statement can be made from it.

**Branches, on the primary `Δ(16→64)` with its cluster-robust (root) paired se:**

| branch | condition | meaning / what it licenses |
|---|---|---|
| `W-RISING` | `Δ(16→64) ≥ +2σ` ∧ `z(arb_64) ≥ +2.0` ∧ `arb(64) > arb(16)` | the ladder is still rising at the instrument's new ceiling. **Licenses (does not fund) ONE** prereg: a deck-paired game cell at the best-reading rung, plus a mandatory cost re-measure in the contended currency (§5). |
| `W-SATURATED` | `\|Δ(16→64)\| < 2σ` ∧ `z(arb_64) ≥ +2.0` | `B = 16` is on the plateau to within +0.04 pts/tied ply. **CLOSES the `B` axis at 16.** The deploy question stays where Phase B left it. Licenses nothing. |
| `W-REVERSAL` | `Δ(16→64) ≤ −2σ` | a strictly larger CRN sample cannot be worse in expectation for a consistent selector ⇒ a **mechanism anomaly**, not a finding. Report, diagnose (arm-order side channel? argmax tie-break? world-draw pathology?), license nothing. |
| `W-NOISY` | `z(arb_64) < +2.0` | the level itself does not convict on the fresh corpus; the increment is uninterpretable regardless of sign. Nothing licensed. |

**Reported in full, never branch inputs:** the 7-rung × 2-`E` ladder with `arb`, `z`,
`F`, `F_fixed`, `rho_wall`, contended-`ms_ratio` projection · pick-churn per doubling ·
oracle-agreement per rung · `arb − rnd` per rung · the S1/S2 half-split.

---

## 5. The deploy question, in both currencies — and the other three rungs

**Do NOT size a game cell now. Gate it on the offline increment.** Reasons, with numbers:

| rung | `rho_wall` (sequential; N4 bar 1.20) | contended in-cell `ms_ratio` (projected) | `rho_phone` |
|---|---|---|---|
| B = 16 | **0.6224** ✅ | **2.42 realized** (Phase B) | 5.976 |
| B = 32 | **1.2449** ❌ (fails by 3.7%) | ≈ **3.75** | 11.95 |
| B = 64 | **2.4897** ❌ (2.07× the bar) | ≈ **6.50** | 23.90 |

⚠️ **The two currencies are NOT the same number** (Stage 2 §0.G — that equation is
withdrawn). The projection above scales only the *arbiter* term of Phase B's realized
split (candidate 4383.6 ms/move, opponent 1808.2 ⇒ arbiter ≈ 2575 ms/move at B=16) and
**must be re-measured, never inferred.** `rho_phone` is a third currency again; the
phone is out of scope for this rung and B>16 is dead there regardless.

⚠️ **The offline→game translation factor is not established.** Stage 1b's +0.1441
pts/tied ply predicts +0.79 pts/game (`× phi 17.57 / non_additivity 3.2`); Phase B
realized **+3.07** — a **3.9× under-prediction**. So Δ(16→64) = +0.064 maps to anywhere
from +0.35 (naive) to +1.4 (realized-ratio) pts/game. A deck-paired `B=64` vs `B=16`
cell resolves +1.4 pts/game at n ≈ 800/cell but needs n ≈ 12,500 for +0.35. **Sizing it
before the offline read would be guessing at the top of a 4× uncertainty.**

**Interaction with the other three rungs.**

- ⭐ **`J > 4` — YES, one paid run serves both.** Post-dedup arm counts are
  1/2/3/4/5/6/7/8/9/10/11/12 = 454/676/265/169/58/90/21/18/22/15/6/15 (max **12**);
  **13.5%** of qualifying positions exceed `J = 4`. Recording arm sets **uncapped**
  raises `Ā` 3.0022 → 3.581 = **+19.3% playouts ≈ +141 worker-h (+22%)** — already in
  §3's total. The `J ≤ 4` sub-arm-set is *exactly* recoverable (the cap is a seeded
  draw from the committed salt, `tiearb.rs::build_arms`), so the `B` prereg reads the
  `J ≤ 4` arms and the `J` prereg reads the full set, off one run.
  **Blindness condition (mandatory):** both READ_RULEs committed in the **same commit**
  before scoring, adjudicated in **one** read-out from **one** analyzer invocation, no
  interim numbers to either author. The shared cell `arb(B=16, J≤4)` must be **declared
  as shared** in both; neither branch may be conditioned on the other's outcome.
- **`eps > 0` — separate scoring run, shared game generation.** The census
  (`corpus/census/rows.jsonl`, 3,400 rows) already carries `by_eps`: tied-row count
  0.644 → 0.647 / 0.670 / 0.711 / 0.784 and mean tie size 8.76 → 8.86 / 9.03 / 9.67 /
  14.17 at eps 0 / 0.05 / 0.2 / 0.5 / 1.0. Most of the effect is **new positions**, not
  wider arms at existing ones, so it needs its own scored set — but it can be mined from
  the **same fresh champion self-play games** (the 234 worker-h line in §3), which is
  where the sharing actually pays.
- **Meeple plies — separate scoring run, shared game generation.** The trigger is
  `Phase == TILES` by construction; a meeple rung needs a new `chain_census` predicate
  over meeple decisions. Same verdict: share the games, not the legs.

⇒ **Recommendation: bundle `B > 16` + `J > 4` into this one run (+22%), and generate
the fresh game set large enough that the `eps` and meeple rungs can mine it later.**

---

## 6. Open questions for the owner

1. **Fund ≈ 865 worker-h / ≈ 20–22 h wall on two busy boxes?** Both are on the live
   measurement; this queues behind it. No cheaper design exists that still separates
   the two ladder hypotheses (§2's cost table is a measured optimum, not a guess).
2. **Accept the pre-registered blind spot?** `n = 1,350` resolves "still rising"
   (+0.05…+0.20) from "saturated" but reads a +0.02 residual as a null. Resolving +0.02
   costs ≈ +1,100 worker-h (corpus-dominated). Recommend accepting the blind spot.
3. **Does the N4 `rho_wall ≤ 1.20` waiver (READ_RULE §0.D, *"dont let that be the
   constraint right now"*) extend above `B = 16`?** `B = 32` misses by 3.7%, `B = 64`
   by 2.07×. If it does not, this rung is informational only and no deploy branch can
   fire — worth settling **before** the prereg, not after.
4. **Is the phone ever the deploy target?** `rho_phone(64) = 23.9`. If yes, `B > 16` is
   desktop-only value and should be graded that way from the start.
5. **Approve the `J > 4` bundling** (+22%, one read-out, two preregs, one declared
   shared cell) — or keep the two rungs on separate runs at ~1.8× the combined cost?
6. **Pre-register the `B = 64` game-cell trigger now (blind), or after the offline
   read?** House discipline says now; the 3.9× translation uncertainty (§5) says the
   *sizing* cannot be fixed until the offline number exists. Proposed split: prereg the
   **trigger and the design** now, size `n` from a committed formula in the offline
   read-out.
