# ARBITER COST-OPTIMIZATION — OFFLINE PRICING PACKAGE — PRE-ANALYSIS PLAN

> **STATUS: PRICING PACKAGE, NOT A CONFIRMATORY INSTRUMENT** (written 2026-08-28, **before**
> any number in `ANALYSIS.md` was computed by this agent).
>
> ⛔ **0 games played. 0 new playouts. No band claimed. `governance/PRODUCTION.yaml` untouched.
> No `experiments/results.csv` row. No claim id minted. No source file outside
> `measurement/arb_costopt_prep/` created or modified.**

---

## 0. ⛔ DISCLOSURE — THIS IS POST-HOC PRICING OF ALREADY-GLIMPSED EFFECTS

**The headline point estimates this package prices were already seen.** A Fable advisory
(2026-08-28) read the same banked artifacts and reported, as quick advisor reads, that:

1. early-phase plies are ≈56% of the tie-arbiter's playout cost at ≈zero measured capture, and
2. racing / early stopping is worth ≈1.2–1.5×.

This package **re-derives those quantities to adjudication grade** — cluster-robust, with CIs,
replicated across corpora, and carried through to deployable cost multipliers. It is therefore:

- **NOT blind.** The direction and the rough magnitude of the phase effect were known to the
  analyst before the estimator was written. Selection of the phase cut was **not** free — the
  project-standard `PHASE_CUTS` were fixed long before (see §2), which removes cut-shopping but
  does **not** remove the fact that the *contrast* was chosen after it was seen to be large.
- **NOT a verdict.** Nothing here closes, kills, or promotes anything. No branch table, no
  pass/fail bar, no read rule.
- **A PRICE LIST.** Its only product is: for each proposed cost option, what it costs and what
  bound the banked evidence puts on what it loses.

**Any deploy decision taken from this package is an owner ruling on banked evidence** — the
`b64_cell` precedent (`measurement/tiearb_widening_20260817/b64_cell/OWNER_RULING_20260820.md`,
where the owner promoted B=16→64 on existing gated evidence, cited in
`governance/PRODUCTION.yaml::tiearb_authorized_by`) — **or a game cell.** The judge-free
game-currency reading of the early-fire question is already specified, unfunded, in
[`measurement/phasegate_prep/`](../phasegate_prep/DESIGN.md) (cells A1/A2 test exactly the
"stop firing early" question in game outcomes). **If the owner wants the early-gate question
answered rather than priced, that is the instrument — not this one.**

## 0.1 ⚠️ F4 RIDER — JUDGE FAMILY

Every capture level in component (i) is **in-family judge-priced**: the numerator is the
tier1-greedy arbiter's pick and the denominator/scale is the clair-puct clairvoyant judge, the
same instrument family that produced the R4 read-out. Memory `reference_evloss_grader` /
the 2026-08-26 F4 lesson: **judged headroom is family-relative** — an R1 clair-puct ceiling of
+1.49 pts/ply read −0.64 (z −3.8) under an out-of-family judge on the same CRN worlds.

⇒ **Labels this package commits to in advance:**

- **ABSOLUTE capture levels (pts/tied-ply at any B, any phase): FAMILY-RELATIVE.** They are not
  to be quoted as points of game strength, and no early-gate loss bound derived from them is
  judge-free.
- **The WITHIN-INSTRUMENT PHASE CONTRAST (early vs mid vs late at fixed B, same judge, same
  worlds, same corpus) is the robust part** and is the quantity this package leans on.
- The **cost** side (component iii) is judge-free — it is wall-clock and ply counts.

## 0.2 ⚠️ CL-068 CROSS-BAND HUMILITY

Corpus A pools deck bands `135e9` (retained) and `137e9` (fresh) —
`shared_run_r4/verdicts/READOUT.md` §7a, 551 + 793 S1 positions. Corpus B
(`tiearb_20260816`) is a different corpus again, and Corpus C (`rung3_r5`) pools `135e9`/`137e9`.
Per CL-068, contrasts that cross bands are over-dispersed 1.8–2.2×.

⇒ **Committed in advance:** every *cross-corpus* statement in `ANALYSIS.md` gets σ inflated
**2×** before any agreement/disagreement is claimed, and the corpora are **never pooled**. The
*within-corpus, same-position phase contrast* is a within-band-mixture paired contrast on
identical worlds and is **not** inflated (it is the robust class). The `early - mid/late`
difference is computed **within** corpus only.

---

## 1. WHAT WILL BE COMPUTED

### (i) Phase × B capture table with CIs

For each phase bucket × each B rung: the arbiter's capture in pts per tied tile-ply, with a
cluster-robust CI, on three corpora, reported separately and never pooled.

### (ii) Flip-weighted racing + arm-pruning simulation

An exact offline replay of paired sequential stopping and trailing-arm pruning over the banked
CRN per-world margin matrices: worlds-used fraction, sign-flip rate vs the full-budget decision,
and capture-weighted loss, at z ∈ {1.5, 2.0, 2.5, 3.0}; then the same simulation restricted to
mid/late-phase positions (the phase-gate interaction).

### (iii) Cost model

Cost multipliers for phase-gate-off-early, phase-B=16-early, racing at each threshold, and the
combinations, expressed in the three deploy currencies (desktop ms/move, eval-cell worker-s/game,
phone s/fire and min/game).

---

## 2. CORPORA — FIXED BEFORE ANALYSIS

| id | path | n | clusters | what it is |
|---|---|---|---|---|
| **A** (primary) | `measurement/tiearb_widening_20260817/shared_run_r4/verdicts/per_position_s1.jsonl` | 1,340 positions | 748 roots | R4 S1. m=128 CRN worlds, E=64 held-out evaluation worlds, full B ladder {1,2,4,8,16,32,64}. Carries `phase_bucket` natively. |
| **B** (replication) | `measurement/tiearb_20260816/per_position.jsonl` | 733 positions | 399 roots | Stage-1b. m=32, cross-fit half-M ⇒ **one** effective rung (selection half = 16 worlds), i.e. comparable to A's **B=16** column only. Carries `phase_bucket` natively. SPENT read-rule / BURNED holdout — used here only as a phase-contrast replicate, never as a fresh verdict. |
| **C** (replication + racing substrate) | `measurement/tiearb_widening_20260817/rung3_r5/` legs `s2/tier1-greedy/walled/leg{1..12}/records/*.json` + `corpus/positions_s2/ARMS.json` | 6,602 pairs / 1,060 positions | 1,060 rids | Per-world CRN margin matrices, m=32. `ARMS.json` carries `phase_bucket`, `k_remaining`, `subset_j4`. ⚠️ **Every rid is `capped_at_4 = true`** (n_arms ≥ 5) — this is the J-widening stratum, **not** the deployment arm-count mix. |
| **census** | `measurement/tiearb_widening_20260817/census/tile_gap_rows.jsonl` | 31,827 TILE plies | — | Fire rate and tie size by phase; the deployment-mix weights for (iii). |
| **cost** | `measurement/tiearb2_stage2_20260817/COST_REMEASURE.json` | 240 records / 15,360 playouts | — | `c_tier1_rust` = 0.09376926 worker-s/playout at W=1, 0.17823232 at W=30. G-BITEXACT PASS. |
| **deploy shape** | `governance/PRODUCTION.yaml` | — | — | desktop `tiearb: {enabled, B: 64, J: 4, mode: argmax, threads: 8}`; **mobile arbiter OFF**. |

⚠️ **Correction to the funding brief, declared here:** the brief says "B=64 desktop / **B=32
mobile**". `governance/PRODUCTION.yaml` (lines 174–201) says **mobile is OFF** — "MOBILE: still
no arbiter at all", `rho_phone(64) ≈ 22–24` unsolved. The phone currency in (iii) is therefore
priced as a **hypothetical mobile arm at B ∈ {16, 32, 64}**, explicitly labelled as not-deployed,
not as a description of what ships.

### 2.1 Phase cuts — REUSED VERBATIM

`scripts/measurement_infra/sample_agreement_roots.py:96–102`, verbatim, **including the
strict-cut fall-through**:

```python
PHASE_CUTS = {"early": (48, 10**9), "mid": (24, 48), "late": (-1, 24)}
def phase_bucket(k_remaining):
    for name, (lo, hi) in PHASE_CUTS.items():
        if lo < k_remaining < hi:
            return name
    return "late"
```

Bounds are **strict on both sides**, so `k_remaining == 48` and `k_remaining == 24` match no
interval and fall through to `"late"`. That quirk is reproduced, not fixed.

Where a corpus carries `phase_bucket` it is used as stored. Where it does not, `k_remaining` is
recovered as `72 - ply // 2` and passed through the same function; the recovery is **validated
against the census** (which carries both) and against corpora A and B (which carry
`phase_bucket`), and the agreement rate is published in `ANALYSIS.md` before any phase number is
read. **If phase agreement is below 0.98 the recovery is abandoned and that corpus is reported
"phase not recoverable".**

---

## 3. ESTIMATORS — FIXED BEFORE ANALYSIS

### 3.1 Point estimate and interval

- **Estimator:** record mean of the per-position statistic within the cell.
- **Interval:** percentile **root** bootstrap, **cluster = root**, **2,000 reps**, **seed
  20260819** — the R4 read-out's own convention, re-implemented from
  `scripts/tiletie/analyze_widening.py::RootBoot` (rows contribute their record weight via root
  sums / root counts; CI = 2.5/97.5 percentiles of the replicate distribution; `se` = replicate
  sd; `z = value / se`). The **same shared `reps × G` root-index draw** is used for every
  statistic within a corpus so differences and their terms are coherent replicate-by-replicate.
- **Phase contrasts** (`early − mid`, `early − late`, `early − (mid ∪ late)`) are computed **on
  the same bootstrap draw**, resampling roots over the whole corpus and recomputing both phase
  means inside each replicate. Roots are **not** re-stratified by phase.
- **No significance bar is declared and no branch is taken.** CIs are printed; "significant" is
  not a word this package is entitled to use for a decision.

### 3.2 Primary capture key (corpus A)

`arb_j4_E{64}_B{b}` — **the R4 read-out's own ladder key**
(`analyze_widening.py::ladder_block`, which reads `arb_j4_*`, not `arb_full_*`). J=4 is the
deployed cap, so this is the deployed arm shape. `arb_full_E64_B{b}` is reported alongside as a
secondary. Companion keys: `ora_full_E64` (the clairvoyant oracle ceiling) and `rnd_E64` (a
random tie-break), both at E=64; `arb − rnd` is reported as the capture-over-random secondary.

E=64 (not E=16) is primary, matching the R4 read-out's own primary.

### 3.3 Corpus B keys

`arb`, `ora`, `rnd`, `arb_minus_rnd`, unscaled per-position values. The read-out's `scale_all`
(0.76768) / `scale_strict` (0.81616) scalings are carried as stored constants and applied only
where the read-out applied them; both scaled and unscaled means are printed.

### 3.4 Racing simulation (corpus C) — the exact rule, fixed in advance

For each rid, the full arm × world value matrix is reconstructed from the star of pairs:
`values_a` (arm `arms[0]`, verified CRN-identical across that rid's legs) plus `values_b` of each
pair. `per_world_delta == values_b − values_a` is asserted per record; a record failing the
assertion is dropped and counted.

- **Deployed arm set:** `ARMS.json::subset_j4` (4 arms) — the arbiter's own deterministic cap
  draw. The full ≥5-arm set is reported as a secondary.
- **Reference decision** = the arbiter's decision at full budget: `argmax_i mean_over_all_m
  worlds`, ties broken by arm order (the deployed `mode: argmax`).
- **Racing (paired sequential stopping):** worlds are consumed in their banked order
  `j = 0,1,2,…`; **the first check is at t = 4 worlds** and every world thereafter. Statistic =
  the leader's paired margin over the runner-up: `d̄_t = mean_{j<t}(v_lead,j − v_runner,j)`,
  `se_t = sd_{j<t}(v_lead,j − v_runner,j)/√t` (ddof=1). **Stop when `d̄_t / se_t ≥ z`** for
  `z ∈ {1.5, 2.0, 2.5, 3.0}`; the decision is the leader at the stop. If it never fires, all `m`
  worlds are used and the decision is by construction the reference (**never a flip**).
- **Arm pruning (variant):** at fixed checkpoints `t ∈ {8, 16}` (m=32), any arm whose paired
  margin behind the current leader satisfies `d̄_t / se_t ≥ z` is **dropped** and consumes no
  further worlds. Combined with racing, the run ends when one arm remains or `m` is exhausted.
- **Worlds-used fraction** = (playouts actually consumed) / (arms × m), i.e. the cost multiplier
  on the arbiter term.
- **Sign-flip rate** = fraction of rids where the racing decision ≠ the reference decision.
- **CAPTURE-WEIGHTED loss** = mean over rids of `|G|·1{flip}` where `G` = the reference leader's
  full-m paired mean margin over the arm actually chosen. Flips concentrate at tiny gaps, so the
  unweighted flip rate over-states the harm; this is the quantity to price.
  ⚠️ **Declared in advance: `|G|` is in the ARBITER'S OWN self-judged currency (tier1-greedy
  terminal playout points), not judge-priced capture.** It bounds how much of the arbiter's own
  decision statistic racing throws away. It is **not** a bound on lost game strength, and it is
  **not** commensurable with the (i) capture numbers.
- **Phase interaction:** the identical simulation restricted to `phase_bucket ∈ {mid, late}`.

### 3.5 Cost model (component iii) — the identities, fixed in advance

Carried **verbatim** from `scripts/tiletie/bench_tier1_rust.py::ladder` /
`analyze_tiearb2.py::rho_ladder`:

```
worker_secs_per_tied_ply(B) = Ā × B × c
rho_wall(B)                 = Ā × B × c / t_champ          t_champ = 13.7552 s/move
rho_amortized(B)            = rho_wall(B) × φ / 72         φ = 22.96 tied tile plies/game
rho_phone(B)                = Ā × B × c / t_phone          t_phone = 1.551 s/move
```

with `Ā = 3.0022`, `c = c_tier1_rust` (0.17823232 at W=30 primary; 0.09376926 at W=1 as the
uncontended sensitivity). This package **adds one factor and nothing else**: a phase-resolved
decomposition

```
worker_secs_per_game = Σ_phase  φ_p × Ā_p × B_p × c × r_p
```

where `φ_p` (fired tile plies per game in phase p) and `Ā_p` (mean `min(tie_size_exact, J)` over
fired plies in phase p) come from the **census**, and `r_p` is the **phase-relative playout-length
multiplier**, `r_p = mean_playout_plies(p) / mean_playout_plies(all)`, measured on corpus C's
`playout_plies_a`/`playout_plies_b` arrays. `r_p` is cross-checked against corpus C's measured
`elapsed_secs / (2m)` by phase; **if the two disagree by more than 15% the ply-count model is
reported as failed and the measured-seconds model is used**, with both printed either way.

The decomposition is **calibrated to the published totals**: `Σ_p φ_p` is compared to the 22.96
prior and `Σ_p φ_p Ā_p / Σ_p φ_p` to `Ā = 3.0022`, and both comparisons are printed. Multipliers
are quoted as **ratios to the current deployed shape** (B=64 everywhere, J=4), so a calibration
offset cancels in the ratio; absolute ms/move and s/fire are quoted with the calibration
explicitly stated.

Desktop `threads: 8` (measured 6.5–6.8× on the arbiter term) is applied as a stated latency
divisor on the **latency** currency only, never on the worker-seconds currency.

---

## 4. WHAT THIS PACKAGE MAY AND MAY NOT PRODUCE

**MAY:** a table of options with (cost multiplier, measured capture in the early bucket with its
CI, bound on capture-at-risk); the one-paragraph priced proposal; the observation that a
particular option is cheap.

**MAY NOT:** a verdict on whether the early gate is free; a claim id; a `results.csv` row; a
band; a `PRODUCTION.yaml` edit; a statement that early capture "is zero" (a CI containing zero is
not a zero); a pooled cross-corpus estimate; a strength claim of any kind.

**Owed at close (to be placed by the orchestrator, not by this agent):** a `DECISIONS.md` index
line and a `docs/PROGRAM_ROADMAP_2026-07-07.md` stamp. Verbatim text is listed at the end of
`ANALYSIS.md`. This agent **does not edit** `DECISIONS.md`, the roadmap, `results.csv`,
`governance/`, or any file outside `measurement/arb_costopt_prep/`.

---

## 5. FALSIFIERS / THINGS THAT WOULD MAKE ME REPORT "NO PRICE"

1. Phase recovery agreement < 0.98 on a corpus ⇒ that corpus is not phase-resolved.
2. `per_world_delta ≠ values_b − values_a` on > 1% of corpus-C records ⇒ racing simulation is
   abandoned.
3. `values_a` not CRN-identical across a rid's legs ⇒ the arm-matrix reconstruction is abandoned
   and racing is reported pairwise only.
4. Census `Σ φ_p` further than 2× from the 22.96 prior ⇒ the deployment-mix weights are reported
   as unreliable and no absolute per-game cost is quoted, only ratios.
5. `r_p` from ply counts and from elapsed seconds disagreeing > 15% ⇒ §3.5's fallback.

---

*Written before the analysis. Nothing below this line existed when this file was committed.*
