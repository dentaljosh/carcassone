# LEVER-MENU EXECUTION PLAN — the six-item queue from the 2026-08-10 doc sweeps

> **Status: 📋 PLAN ONLY, 2026-08-10. NOTHING HAS BEEN LAUNCHED. NO BAND IS CLAIMED. `PRODUCTION.yaml` IS UNTOUCHED.**
> Joshua approved *planning* the full six-item menu and set the resource envelope (laptop fully
> available; local box capped at **W=14** because he is using it; default = **two-box
> `--shared-claim` work-stealing**, the pattern proven on the 2026-08-10 `b0p3` powered confirm).
> Each item's **final** pre-registration and its **band claim** land in the SAME commit, at launch
> time — per the standing rule in [`governance/BAND_REGISTRY.csv`](../governance/BAND_REGISTRY.csv).
> This document is the design, the cost model and the order. It authorizes nothing.

> **Reading order:** §1 envelope + cost model → §2 the co-tenancy ruling → §3 the DAG →
> §4 per-item mini-preregs → §5 the GO sequence → §6 what stays Joshua's → §7 out of scope →
> §8 what changed from the sweeps' sketches (read this before quoting a sweep number).

---

## 1. The envelope and the cost model

### 1.1 What is measured, and where it comes from

Every rate below is read off a file, not estimated. The basis is the 2026-08-10 morning
`curvephase_b0p3_power_fixed_v1_vs_champ_n800` cell — the same class as menu items 2 and 3
(fair PIMC k8×1376 = 11008 sims/move, `fixed_v1` + `CARCASSONNE_FIX_R9=1`, rust backend,
deck-paired, both arms at the deploy budget).

| quantity | value | source |
|---|---|---|
| deploy-class two-box wall, n=800 | **4462 s = 1.24 h** | [`PREREG_POWER03.md`](../measurement/curve_shape_scope_20260809/PREREG_POWER03.md) deviation line; `results.csv` `curvephase_b0p3_power_fixed_v1_vs_champ_n800` |
| ⇒ two-box rate at **local W30 + laptop W22** | **645.5 games/h** | 800 / 4462 s |
| per-box completion split | **local 57.0% / laptop 43.0%** | counted directly from the last claim-owner of each of the 795 recoverable `seed*.claim` files in `/mnt/c/carc-shared/curvephase_ladder/cp3_b0p3/` (453 / 342) |
| ⇒ local **W30** | 368.0 games/h | 0.570 × 645.5 |
| ⇒ laptop **W22** | 277.5 games/h | 0.430 × 645.5 |
| local **W14**, same class | **14.2 s/game = 253.5 games/h** | [`PREREG_POWER03.md`](../measurement/curve_shape_scope_20260809/PREREG_POWER03.md) §cost, "the measured ~14.2 s/game" |
| independent check on the W14 figure | 96 games in 21.2 min at W14 = 13.25 s/game | F14 E4 deck baseline, `measurement/e4_deck_baseline_20260807/READOUT.md` (same rules, same 11008 budget, rust) |
| second independent check | JCZ n=400 in ~47 min at W14 = 511 games/h — but only **one** arm pays 11008 (JCZ's evaluator is 38 ms/move), so ≈2× the two-champion-arm rate | [`CONFIRM_READOUT.md`](../measurement/jcz_match_20260809/CONFIRM_READOUT.md) |

**Local W14 is ≈69% of local W30, not ≈47%.** The naive "half the workers ⇒ half the throughput"
read is wrong on this workload: the two figures above imply only **1.45× throughput for 2.14×
workers** (14→30), i.e. the curve is already *concave* well before W30 — consistent with the
2026-08-02 flagship fair-eval sweep, which found a **plateau from W≈32** (17.0–18.0 moves/s
across W=32–64). The two independent W14 measurements (14.2 and 13.25 s/game) both land near
253–272 games/h. We plan on the **conservative 253.5**.

⚠️ **What is not measured.** There is **no clean W-sweep for this exact config** (fair PIMC
k8×1376, `fixed_v1`+R9, rust) on either box — F7d's `local W*=30 / laptop W*=22` came from the
*`eval_puct_priors`* workload and was flagged stale twice (a 2026-08-03 re-sweep moved the laptop
to W*=26). `W30/W22` is therefore "what was actually run and manifest-confirmed", not a settled
optimum, and the laptop leg has never been swept on this class at all. The 253.5 and 277.5
figures above are anchored to *measured throughput at the W we plan to use*, which is the reason
to prefer them over any W* recommendation.

### 1.2 The new envelope

| class | local W14 | laptop W22 | **two-box** | vs this morning |
|---|---|---|---|---|
| **deploy** (k8×1376 = 11008, both arms) | 253.5 g/h | 277.5 g/h | **531 g/h** (6.78 s/game) | 82% |
| **ablation / screen** (2750 sims both arms) | ~710 g/h | ~777 g/h | **~1490 g/h** | — |
| **net-arm (carc-orch)** — item 5 only | ~22.5 g/h | ~19.2 g/h | **~42 g/h** | — |

**Self-check:** the model reproduces the prereg's own independent figure. It predicts
n=800 local-only at W14 = 800 / 253.5 = **3.16 h**; [`PREREG_POWER03.md`](../measurement/curve_shape_scope_20260809/PREREG_POWER03.md)
wrote "~3.2 h at W=14". That agreement is why the model is trusted below.

**The ablation multiplier is ~2.8×, and it is a wall-clock fact, not the sims ratio.** The sims
ratio is 11008/2750 = **4.00×**; the *measured* throughput ratio is **2.7–3.2×**, centre ~2.8×
(the four rust-era cells in `measurement/leaf_ablation_20260730/ABL_PROGRESS*.tsv` ran n=400 in
826 / 779 / 768 / 688 s two-box = 1743 / 1848 / 1875 / 2093 games/h, on local W32 + laptop W24,
against the deploy class's 646 g/h at W30+W22; DECISIONS 2026-08-02 rounds this to *"~1800
games/h two-box"*). Normalizing per worker gives 3.01×. **We plan on the conservative 2.8×** — a
plan that runs late is better than one that runs over. Never substitute the 4× sims ratio.

**The net-arm rate is 12× worse than the deploy class and is not a CPU story.** The CL-072 n=400
cell took **7 h 47 min for 400 games at local OW=20 + laptop OW=12 = 51.3 games/h**
([`READOUT.md`](../measurement/teacher_h2h_94e9/READOUT.md); logs under
`/mnt/c/carc-shared/teacher_h2h_94e9/`). Its workers are blocked on GPU forwards through
`carc-orch`, so worker count is a GPU-service parameter, not a core count. Scaling the local leg
20→14 orch workers gives the ~42 g/h above; that is an **extrapolation**, flagged as such.

### 1.3 Per-item cost at the new envelope

| # | item | games | class | **two-box wall** | local-only W14 |
|---|---|---|---|---|---|
| 1 | farm-norm replay | 0 | replay (no games) | **≤0.5 h**, one box | ≤0.5 h |
| 2 | `farm_growth_off` n=1600 confirm | 1600 (+~32 gate) | deploy | **3.0 h** (+0.06 h) | 6.3 h |
| 3 | CL-060 width residual H2H n=800 | 800 | deploy | **1.5 h** | 3.2 h |
| 3′ | …conditional top-up to n=1600 | +800 | deploy | **+1.5 h** | +3.2 h |
| 4 | capscurve 4 cells × n=800 | 3200 | ablation | **2.2 h** | 4.5 h |
| 5 | CL-072 n→800 extension | +400 | net-arm | **9.6 h** | **17.8 h** |
| 6 | JCZ S3 cut | 0 | oracle replay | **~1.4 h**, one box (W16) | ~1.4 h |

Item 6's basis: `oracle_score_pilot.py` measured **100 positions × M=32 in ~81 min at W16**
(≈48.6 s/position; the script's own header banner). 2 strata × 50 positions = 100 positions
⇒ ~1.4 h. The laptop has 24 threads, so W16 there is comfortable; **that box has never been
timed on this instrument** — the W16-equivalence is the one assumption in item 6's price.

---

## 2. Co-tenancy: is anything here timing-sensitive?

**Asked and answered explicitly, because it decides the schedule.**

**No item's primary statistic is time-budgeted.** Items 2, 3 and 4 are *sim-budgeted* deck-paired
margin evals: both arms play a fixed number of simulations per move, so the deck-paired margin —
the primary statistic in every case — is invariant to how fast the box happens to be. **Co-tenancy
is therefore a throughput cost, not a validity cost.** This is the opposite of the 2026-08-03
timing-bench lesson (`feedback_no_agent_compute_beside_eval`), where the instrument *was* a clock
and a co-tenant contaminated it.

Three qualifications, and then the ruling:

1. **`ms_ratio` survives co-tenancy; absolute ms/move does not.** Item 2 carries an `ms_ratio`
   rider (~0.96 — deletion is cheaper) and item 3's deployability framing wants ms/move. A
   *ratio* of two arms sharing one process pool is first-order insensitive to contention; an
   *absolute* ms/move is not. So: quote `ms_ratio` freely, and **never quote an absolute
   ms/move from a shared-tenancy run**.
2. **Serializing costs nothing.** With both boxes saturated by one work-stealing cell, running
   two evals concurrently and running them back-to-back consume the same total wall clock. Serial
   is strictly better: cleaner attribution, one `--shared-claim` output dir per box at a time
   (the design the launchers assume), and no repeat of the crash-cycle stretching seen when a
   second workload sat beside a live eval.
3. **Item 5 is the exception worth naming.** Its arms are asymmetric (a net at 2752 vs a
   classical champion at 11008), the cost ratio 1.15× is *recorded in the claim*, and the GPU is
   a shared, saturable resource. Nothing else may touch the GPU while item 5 runs.

**RULING.** Items 2, 3, 4, 5 run **one at a time** across the two boxes. Items 1 and 6 are
replay/oracle instruments that play no games and are free to slot into gaps — but they are
CPU-heavy, so they go in **gaps, not beside a game eval**, purely to protect throughput and the
ms riders. Item 1 (local) and item 6 (laptop) may run **concurrently with each other**, since
neither quotes a clock.

---

## 3. Dependency / decision DAG

```
                 ┌───────────────────────────────────────────────┐
   T0  ─────────►│ 1. FARM-NORM REPLAY   (local, ≤0.5 h, 0 games)│──┐
                 │ 6. JCZ S3 CUT         (laptop, ~1.4 h, 0 games)│  │  (concurrent — neither
                 └───────────────────────────────────────────────┘  │   quotes a clock)
                                                                    │
   1 REFEREES future farm spending. It does NOT gate item 2. ───────┤
   6 CLOSES the JCZ steal file whichever way it reads. ─────────────┤
                                                                    ▼
                 ┌───────────────────────────────────────────────────────────┐
                 │ 2a. WIRING GATE (~32 games, deploy class, ~4 min)         │
                 │     MUST PASS before 2b. HARD BLOCKER.                    │
                 └──────────────────────────┬────────────────────────────────┘
                                            ▼
                 ┌───────────────────────────────────────────────────────────┐
                 │ 2b. farm_growth_off n=1600 deploy confirm   (3.0 h)       │  ← the top buy
                 └──────────────────────────┬────────────────────────────────┘
                       z ≥ +2 ──► caps/curve RE-SWEEP owed (bug-fix-shifts-optima)
                                  ──► then a PRODUCTION.yaml proposal ⇒ JOSHUA
                       |z| < 2 ──► row CLOSES bounded-null (4th sub-2σ read)
                                            ▼
                 ┌───────────────────────────────────────────────────────────┐
                 │ 4. capscurve 4 cells + the ×1.75 rung  (2.0 h, ablation)  │
                 └──────────────────────────┬────────────────────────────────┘
                       any |z| ≥ 2 ──► optimum moved, re-tune ⇒ JOSHUA
                       all |z| < 2 ──► retires the "≤20 elo not excluded"
                                        caveat in PRODUCTION.yaml (±17.5 elo bound)
                                            ▼
                 ┌───────────────────────────────────────────────────────────┐
                 │ 3. CL-060 width residual H2H n=800  (1.5 h)               │
                 │     └─ 1.5 ≤ |z| < 2 ──► pre-registered top-up n=1600 (+1.5 h)
                 └──────────────────────────┬────────────────────────────────┘
                       information only — a k4 win is NOT deployable (§4.3)
                                            ▼
                 ┌───────────────────────────────────────────────────────────┐
                 │ 5. CL-072 n→800 extension  (9.6 h, GPU, exclusive)        │
                 └───────────────────────────────────────────────────────────┘
                       settles the rodv3 premise ⇒ park/kill call is JOSHUA's
```

**Edges that exist:**
- `2a → 2b` is a **hard blocker**: the knob has never been exercised through the fair harness.
- `2b(z≥2) → caps/curve re-sweep → PRODUCTION proposal` — the standing
  bug-fix-shifts-optima rule; a leaf change re-opens the tunables it was tuned against.
- `4 → PRODUCTION.yaml caveat text` — item 4's whole product is a caveat retirement.

**Edges that do NOT exist (stated so nobody invents them):**
- **1 does not gate 2.** Item 1 referees *future* farm-cluster spending (more E4 games, a
  farm-war follow-up). Item 2 is a leaf-deletion measurement whose case rests on three elo cells,
  not on the farm-norm story. Running 1 first is a scheduling choice (it is free and it is
  quick), not a dependency.
- **4 does not gate 2.** They touch different leaf terms. But if 2 fires, 4's cells must be
  re-read against the *new* leaf before adoption — which is exactly the re-sweep the `2b(z≥2)`
  edge already mandates.
- **3 gates nothing.** It resolves a decomposition, not a deployment.
- **6 gates nothing.** It closes a file.

---

## 4. Per-item mini-preregs (skeletons — the launch-time prereg is the authority)

Common to every game-playing item: `fixed_v1` + `CARCASSONNE_FIX_R9=1`, rust backend, both arms;
`OPENBLAS_NUM_THREADS=1`; `nice -n 19`; detached (`nohup … & disown`);
[`clock_skew_guard.sh`](../scripts/measurement_infra/clock_skew_guard.sh) at launch;
`--shared-claim` with stale-claim cleanup before start; a `manifest.json` with the full resolved
config; **≥90% completion or the cell is VOID**; wiring gates verified from the manifest **before
any number is read**. Band is claimed in the prereg commit, before game 1, and flipped to
`retired` at close-out.

---

### 4.1 — Item 1. Farm-norm replay (FREE, runs first)

**⚠️ The sweep's premise is wrong and the item is redesigned. Read [§8.1](#81-item-1--the-premise-was-wrong) first.**

**Design.** Replay the banked JCZ n=400 corpus
`measurement/jcz_match_20260809/confirm.jsonl` (400 games, `fixed_v1`+R9 stamped, champion at
k8×1376=11008, fully losslessly replayable — each record carries `deck_seed` + the full `actions`
list and self-verifies via `replay_ok`) through
[`scripts/analyzer/corpus_stats.py`](../scripts/analyzer/corpus_stats.py), which already emits the
per-seat decomposition `final_score / during_play / incomplete_pts / farm_pts /
farm_pts_per_farmer / first_farm_turn`. Report per-seat means with CI, **champion seat and JCZ
seat separately**.

**Build rider (small, real).** `confirm.jsonl` lacks the `game_id` key that
`root_replay.load_games` requires and stores finals as `scores`, not `score_p0`/`score_p1`. A
~20-line adapter (emit `game_id`, split `scores`) is needed. **Acceptance gate: the replay must
reproduce the archived finals 400/400 before any decomposition number is quoted** — the same bar
the match itself cleared over 56,777 plies.

**Primary statistic.** Champion-seat `farm_pts` mean ± 95% CI over 400 seats, against the two
existing reference points: **20.49** (self-play, walled, 2752 —
[`CORPUS_STATS_champ449.md`](../measurement/analyzer_20260802/CORPUS_STATS_champ449.md), 898 seats,
sd 10.7) and **20.81** (self-play, `fixed_v1`, 11008 —
[`PHASE_C_DESCRIPTIVES.md`](../measurement/f9_phase_c/PHASE_C_DESCRIPTIVES.md) §3, 800 seats).
The number nobody has is the **vs-a-non-self-opponent** value, which is what the 11.0-vs-Joshua
figure should actually be compared against.

**Branches.**
- **A — vs-JCZ farm pts/seat lands near 11–14** (i.e. near the vs-Joshua figure): the "collapse"
  is a **generic vs-opponent effect**, not human-specific — self-play farm points are inflated
  because both seats are the same farmer-timing policy. ⇒ **de-prioritize farm-cluster spending**;
  the farm-war story loses its headline.
- **B — it lands near 20** (within ~1 sd of the self-play norms): the collapse **is** specific to
  Joshua's play. ⇒ strengthens item 2's mechanism story and is a real argument for **funding more
  E4 games** (Joshua's call, §6).
- **C — anywhere in between, CI straddling both**: report as inconclusive at n=400 seats and say
  so; do not pick a side.

**Riders.** (i) One opponent, one band, one rules epoch — a single external opponent is not "all
opponents"; write it bounded. (ii) `farm_pts` sd ≈ 10.7 ⇒ 95% CI at 400 seats ≈ ±1.05 pts, which
*is* enough to separate 11 from 20 but not to resolve 14 from 17. (iii) Band `1.08e11` is
**retired**; this reuse is licensed because it is an exploratory decomposition of an existing
archive that mints no strength claim — the same licence the JCZ mining reuse was granted.

**Cost.** ≤0.5 h, one box, **0 games, no band claimed**.

---

### 4.2 — Item 2. `farm_growth_off` n=1600 deploy confirm (the top buy)

**Prior evidence — all three cells, exactly as recorded** ([`results.csv`](../experiments/results.csv), rows `abl_farmgrowthoff*`):

| cell | n | band | elo ± σ | **paired margin z** |
|---|---|---|---|---|
| gate | 400 | 1.00e11 | +42.8 ± 17.5 | **+1.866** |
| confirm | 400 | 1.01e11 | +10.4 ± 17.4 | **−0.075** |
| `fixed_v1` remeasure | 400 | 1.05e11 | +25.2 ± 17.4 | **+1.855** |

The recorded 2-cell pool is **+26.6 ± 12.3 elo (z +2.16), but margin-pooled z ≈ +1.27, and the
two statistics disagree** — disposition **PARKED suggestive-unpromoted** (DECISIONS 2026-08-03
early). Pooling the third cell is explicitly **not licensed** (the standing no-third-cell ruling,
[`LEVER_INDEX.md`](LEVER_INDEX.md)). All three ran at the **2750** ablation instrument through
[`eval_puct_priors.py`](../scripts/classical_search/eval_puct_priors.py) — **never at the deploy
budget, never through the fair PIMC harness**.

**2a — WIRING GATE (hard blocker, ~32 games, ~4 min).** The plumbing exists end-to-end
(`LeafConfig.farm_growth_off` → `flat_leaf` / `carc-core` leaf → `rust_agent.leaf_config_rs`
→ `search_config_rs` → `RustFairAgent`/`FairAgentRs` → `eval_fair_puct.py --cand-leaf-json`) but
has **never been exercised through [`eval_fair_puct.py`](../scripts/classical_search/eval_fair_puct.py)**:
zero `farm_growth_off` manifests exist anywhere on the share. Precedent for why this is a
blocker and not a formality: the caps/curve build found the **clairvoyant rust mirrors ignoring
`--rules-profile` entirely**. The gate is three assertions, all read from the manifest:
1. the candidate's resolved leaf hash **differs** from the champion's `a36d2e15a3b3d71d`
   (proves the knob was applied, not silently dropped) — this requires
   `--allow-cand-curve-drift`, which `eval_fair_puct.py` permits **only** under
   `--info fair --opponent fair-champion`, and which in turn requires the candidate JSON to
   carry an explicit 8-entry curve, so the cell JSON is
   `{"farm_growth_off": true, "v29_meeple_curve": [<curve125 verbatim>]}`;
2. the opponent arm resolves **exactly** `a36d2e15a3b3d71d`;
3. `r9_env_ok: true`, `rules_profile: fixed_v1`, `k_dets 8 / sims 1376`, both arms.
Plus a sign sanity check against a `farm_base_off` micro-cell, which must read strongly negative
(the recorded −132.9…−142.1) — a knob that reads ~0 where the reference reads −140 is broken
wiring, not a null.
**If the gate fails, item 2 stops and becomes a build task. Do not "fix it and keep the games."**

**2b — the cell.** ONE cell, **n=1600 deck-paired (800 decks × 2 seats)**, ONE **fresh** band
(next free ≥1.18e11, subject to a launch-time registry + share census). Candidate = the champion
leaf with `farm_growth_off=true`; opponent = the intact champion. Fair PIMC **k8×1376 = 11008**,
`fixed_v1`+R9, rust, exact-K per production.

**Primary statistic: the cell's own deck-paired margin z.** No pooling with any prior cell
(different bands, different budget, different harness — cross-band pooling is forbidden).

**Power, stated honestly.** From the b0p3 n=800 cell (400 decks, se 0.634 pts/deck), 800 decks
gives **se ≈ 0.45 pts/deck ⇒ 2σ ≈ ±0.90 pts/deck ≈ ±15.7 elo**.
- The **face-value** lean (+26.6 elo ≈ 1.52 pts/deck) would read **z ≈ +3.4** — decisively.
- The **winner's-curse-calibrated** expectation (0.3–0.4× on a lean that has been sub-2σ three
  times) is **+8 to +11 elo ≈ 0.46–0.61 pts/deck ⇒ z ≈ +1.0 to +1.4** — which this cell
  **cannot** resolve. Reaching z=2 on the curse-adjusted effect would need ~2100 decks (n≈4300,
  ~8 h). That is not proposed.
⇒ **n=1600 is a decisive test of the lean at face value and a bounded null otherwise.** Say so in
the readout; do not let a null be written as "the deletion does nothing".

**Branches (precedence: INSTRUMENT-BROKEN → KILL → CONFIRM → BOUNDED-NULL).**
- **z ≥ +2.0** → CONFIRMED. Deletion is better. ⇒ triggers the **caps/curve re-sweep** (a leaf
  change invalidates the tunables tuned against the old leaf) and only then a `PRODUCTION.yaml`
  proposal. **Both are Joshua's calls** (§6). Nothing is adopted inside this plan.
- **|z| < 2.0** → does **not** confirm. This is the **fourth** sub-2σ read on this lever; per the
  no-third-cell ruling the row **CLOSES** as a bounded null with the ±15.7-elo bound recorded in
  `results.csv`, `CLAIM_REGISTRY` (CL-074 farm row) and [`LEVER_INDEX.md`](LEVER_INDEX.md).
- **z ≤ −2.0** → the deletion is harmful; close negative and record that the farm-growth block
  earns its place.

**Riders.** (i) `ms_ratio` expected ≈0.96 — deletion is *cheaper*, so an equal-**sims** win is
also an equal-wall-clock win *a fortiori*; record the ratio, do not quote absolute ms/move from a
shared-tenancy run. (ii) The knockout reaches the **leaf only** — the exact-K endgame tail keeps
full farm scoring on both sides, per [`F7B_PREREG.md`](../measurement/leaf_ablation_20260730/F7B_PREREG.md).
(iii) A win here changes a leaf that three prior cells measured at 2750; the 2750 evidence does
**not** transfer to 11008 by assumption, which is the whole reason this cell exists.

**Cost.** 0.06 h gate + **3.0 h** two-box. Band: one fresh.

---

### 4.3 — Item 3. CL-060 width residual, direct H2H

**⚠️ The sweep's "adapt the existing launcher" instruction does not survive contact. Read [§8.3](#83-item-3--the-named-launcher-is-the-wrong-instrument).**

**The question.** CL-060 ([`CLAIM_REGISTRY.csv`](../governance/CLAIM_REGISTRY.csv), status
**Reopened**) decomposes its +49.85-elo budget promotion into budget and width **by quadrature
across two different bands**: budget alone = +27.85 ± 12.43 (z 2.24, band 44e9); ⇒ **width
residual at fixed 11008 = +21.99 ± 18.96, z 1.16, NOT RESOLVED**. CL-060's own "sharp next test
#1" names the fix: *a k8×1376 vs k4×2752 head-to-head at fixed 11008 on ONE band, n≥400 paired*.
It also names the tension: **CL-054** has k4 > k8 at fixed total 2752 (+5.18 ± 1.24 pts/deck,
z 4.17, Promoted, and it is what the phone still runs).

**Design.** ONE cell, direct H2H, **both sides fixed 11008**, ONE **fresh** band (propose
≥1.19e11), n=800 deck-paired first. The harness already documents this exact shape — it is the
CL-060 re-open command with the two budget knobs swapped:

```
--info fair --opponent fair-champion --exact-k 2 \
--k-dets 4 --sims 2752  --opp-k-dets 8 --opp-sims 1376 \
--n 800 --paired --seed-start <fresh band> --shared-claim --no-results-csv
```
(candidate = k4×2752, opponent = the k8×1376 champion; both asymmetry flags are required —
`--opp-sims` alone would silently give a k8×2752 opponent).

**Primary statistic: deck-paired margin z.** **Pre-registered top-up:** if
**1.5 ≤ |z| < 2.0**, extend to n=1600 on fresh decks of the **same** band, then verdict.

**Power.** n=800 = 400 decks ⇒ se ≈ 0.634 pts/deck ⇒ 2σ ≈ ±1.27 pts/deck ≈ **±22 elo** — which is
the *same size* as the residual being chased. **n=800 is therefore a screen, and the top-up
should be expected, not treated as a surprise;** budget **3.0 h**, not 1.5 h. At n=1600,
2σ ≈ ±15.7 elo, which does resolve a +22-elo residual.

**Branches.**
- **|z| ≥ 2.0** → width residual RESOLVED with a sign. If **k8 wins**, CL-060's decomposition is
  vindicated and CL-054 is re-scoped as *budget-specific* ("optimal width grows with budget").
  If **k4 wins**, CL-054 generalizes and CL-060's quadrature difference was noise.
- **1.5 ≤ |z| < 2.0** → top up to n=1600, then re-read on the same map.
- **|z| < 1.5** → bounded null; the width axis at 11008 closes as **unresolvable at affordable n**
  with the ±22-elo (or ±15.7 after top-up) bound recorded, and CL-060's falsifier (1) is
  discharged rather than left open.

**Honest framing — a k4 win is information, not a deployment.** The two configurations cost
**the same sequentially**: k4×2752 = 15315 ms/move (band 44e9) vs k8×1376 = 14779 ms/move
(band 32e9), i.e. k4 is ~3.6% *slower*, not faster. The ~2× is a **parallel-deploy** claim, and
it is an extrapolation, not a measurement: production runs `parallel_workers = k_dets`, so k4 can
occupy only 4 workers against k8's 8. At the measured efficiencies in
[`EFFJENSEN_BENCH_BATCH_20260729.md`](../measurement/EFFJENSEN_BENCH_BATCH_20260729.md) (k8×1376:
13.755 s/move sequential → 2.160 at W=8, 6.37×, 80% efficiency; k4×688: 3.16× at W=4, 79%),
k4×2752 at W=4 projects to ≈15.3/(4×0.79) ≈ **4.8 s/move vs the champion's measured 2.16** —
≈2.2×, and it would push the tournament-clock share from the recorded ~20.6% toward a
majority of the 900 s. **k4×2752 has never been benched k-parallel.** ⇒ Whatever this cell
reads, **nothing is proposed for `PRODUCTION.yaml`**; the deliverable is a resolved
decomposition and a discharged falsifier.

**Cost.** 1.5 h, expected 3.0 h with the top-up. Band: one fresh.

---

### 4.4 — Item 4. capscurve unresolved cells + the ×1.75 rung

**What it buys.** [`PRODUCTION.yaml`](../governance/PRODUCTION.yaml) currently carries, verbatim:
*"Power caveat: the screen resolves ~50 elo unpaired / ~35 paired at 2-sigma; a <=20-elo optimum
shift is NOT excluded."* The 2026-08-03 re-sweep closed **all six cells null** at n=200 on band
1.03e11, but its own pre-registered power section says it had **no power at all for `curve150`,
`cap5` or `cap12`** and that *"a null on those three is uninformative about ±20 elo and must not
be written up as flat"* ([`PREREG.md`](../measurement/capscurve_resweep_20260803/PREREG.md)).

**Design.** 4 cells — **cap5, cap12, curve150, curve175** — each **n=800 deck-paired**, ONE
**shared fresh** band (propose ≥1.20e11) with CRN across all four cells, at the **2750 ablation
instrument** that produced the originals: [`eval_puct_priors.py`](../scripts/classical_search/eval_puct_priors.py)
via [`capscurve_resweep_launcher.sh`](../scripts/classical_search/capscurve_resweep_launcher.sh)
(reuse, do not rewrite — it already carries `--paired`, `--shared-claim`, the
`OPENBLAS_NUM_THREADS=1` pin and the two-box primary/helper roles), `--cand-sims 2750` both
sides, `fixed_v1`+R9, rust, incumbent = cap8 / oppcap8 / curve125.

**Why n=800 is exactly the right size.** The re-sweep's own stated resolution is **paired 2σ ≈ 35
elo at n=200**; 4× the sample halves the se twice over ⇒ **2σ ≈ ±17.5 elo at n=800**. That is
precisely the bound needed to retire a "≤20 elo not excluded" caveat, and no more. Going further
buys nothing the caveat asks for.

**Primary statistic: each cell's own deck-paired margin z** vs the incumbent, on the shared band.

**Branches (per cell).**
- **|z| ≥ 2.0** → the optimum **moved** under `fixed_v1`; a re-tune of that axis is owed.
  ⇒ **Joshua's call** (§6). Do not adopt inside this plan.
- **|z| < 2.0** → for cap5 / cap12 / curve150: the caveat is **RETIRED** for that knob, and
  `PRODUCTION.yaml`'s caveat text is replaced with the measured **±17.5-elo** bound. That text
  edit is the item's product and is a governance touch, not a config change.

**The ×1.75 rung is a different animal — frame it correctly.** It has **already been measured
cleanly, under `walled`**: `c5_s2_curve175_n400` = **+77.7 ± 17.7, paired z 4.19** (2026-07-13,
after the OpenBLAS-oversubscription hang was root-caused and fixed), against curve125's +66.8 on
the same axis — a **+10.9-elo gap, well under 1σ**, which is exactly why curve125 and not
curve175 was adopted (CL-051). So this cell is a **`fixed_v1` re-measure of a known rung**, not a
virgin rung. Curse-calibrated expectation vs the curve125 champion: 0.3–0.4× of ~+11 ⇒
**+3 to +4 elo**, well inside the ±17.5-elo 2σ floor. **Expect a null.** A ≥2σ read would re-open
the curve-*scale* axis that C5 closed as a noisy plateau — a Joshua call, not an adoption.
⚠️ Keep `OPENBLAS_NUM_THREADS=1` pinned: the ×1.75 hang lived on this exact axis.

**Overall framing.** This is **caveat retirement plus first-ever `fixed_v1` coverage above
×1.25**, at a curse-adjusted expectation of **+0 to +8 elo**. It is not an elo hunt.

**Cost.** 3200 games at the ablation class (~1490 g/h) = **2.2 h** two-box. Band: one fresh, shared.

---

### 4.5 — Item 5. CL-072 n→800 extension

**Status.** [CL-072](../governance/CLAIM_REGISTRY.csv) is **Provisional / low confidence**:
**−20.87 ± 17.40 elo (z −1.20), deck-paired margin −2.0025 pts/deck, margin z −1.90**, n=400
deck-paired, band 94e9. Its prereg
([`TEACHER_H2H_PREREG.md`](../scripts/distill_flywheel/TEACHER_H2H_PREREG.md)) pre-commits:
*"if |elo| ∈ [5, 25], extend the SAME cell to n=800 on fresh decks of the same band, then
verdict."* **|elo| = 20.9 ⇒ the trigger FIRED, and the extension has never been run**
([`READOUT.md`](../measurement/teacher_h2h_94e9/READOUT.md)).

**Band policy — the one licensed exception to fresh-band.** [`BAND_REGISTRY.csv`](../governance/BAND_REGISTRY.csv)
row `94000000000` is still **`claimed`, not retired**, with the note: *"Status stays 'claimed'
because the pre-registered n=800 extension draws FRESH decks of THIS band — flip to retired only
when that extension closes or is abandoned."* No new band is claimed; the existing row is flipped
to `retired` at close-out.

**Arms — stated precisely.** Candidate = CL-067's distilled net used as **policy priors** with the
**frozen curve125 leaf** (value severed), `k4×688 = 2752`. Opponent = the **production champion**
`FairHeuristicPriorAgent` at the promoted `fair_deploy` **k8×1376 = 11008** — i.e. a classical
agent at the same tier/budget as the corpus teacher, **not** a teacher checkpoint. Harness
[`fair_net_vs_net_orch.sh`](../scripts/classical_search/fair_net_vs_net_orch.sh) over
[`eval_fair_puct.py`](../scripts/classical_search/eval_fair_puct.py)
(`--info fair-netprior --opponent fair-champion --shared-claim --no-results-csv`), two `carc-orch`
SHM servers.

**Box topology, honestly.** The laptop **can** contribute to a net-arm eval and has already done
so **on this exact cell**: it ran its own laptop-side `carc-orch` server at OW=12 against its own
GPU while local ran OW=20 (`/mnt/c/carc-shared/teacher_h2h_94e9/logs/full_laptop.log`). It does
**not** need the local GPU. `scripts/az_zero/laptop_joiner.sh` is **not** the mechanism — that is
a self-play **generation** joiner (its measured ~16% contribution, and its `--shared-claim` +
`_clean_stranded` residue, belong to the az_zero gen loop); the eval-side two-box pattern is the
one already proven here.
- **Two-box at the new cap (local OW14 + laptop OW12):** ≈42 g/h ⇒ **~9.6 h** for the +400 games.
- **Local-only at W14:** ≈22.5 g/h ⇒ **~17.8 h** — ~1.9×, as expected.
⚠️ Both are extrapolations from the one measured configuration (OW20/OW12 = 51.3 g/h). Also note
the local "W=14" cap is a *responsiveness* cap on cores, while orch workers are mostly blocked on
GPU — OW14 is the conservative reading and is what is priced.

**Mandatory orchestrator hygiene** (else the server owns the box): `OMP_NUM_THREADS=1` **to the
carc-orch server process**, and `max_batch ≥ W` on each server.

**Primary statistic: the deck-paired margin z on the full n=800.** se scales 1.054 → **≈0.745
pts/deck** at 400 decks ⇒ 2σ ≈ ±1.49 pts/deck.
- Face-value effect (−2.00 pts/deck) ⇒ **z ≈ −2.7**: decisive.
- Curse-calibrated (0.3–0.4× toward zero, applied to a *lean* regardless of sign) ⇒ −0.6 to
  −0.8 pts/deck ⇒ **z ≈ −0.8 to −1.1**: not resolvable. Same honest shape as item 2.

**Branches.**
- **z ≤ −2.0** → the student does **not** beat its own corpus teacher. The **rodv3 premise is
  refuted**; the parked 65/300 gen retires. ⇒ formal kill is **Joshua's call** (§6).
- **|z| < 2.0** → bounded null; CL-072 closes Provisional → **bounded-null** with the ±1.49
  pts/deck bound recorded; gen stays parked; **no more n at this design** (a re-open needs a new
  mechanism or a finer instrument).
- **z ≥ +2.0** → the premise holds and rodv3 becomes a live, fundable proposal — Joshua's call.

**Riders.** Cost ratio candidate/opponent **1.15×** (16100 vs 14047 ms/move) is recorded in the
claim and must be re-reported; the `champ_ms` field prints as *candidate* — **read the emitter
before trusting the field name.** GPU is exclusive to this item while it runs.

**Cost.** **9.6 h** two-box / 17.8 h local-only. Band: 94e9 (already claimed for this).

---

### 4.6 — Item 6. JCZ S3 cut

**What exists.** The mining extraction is banked:
`measurement/jcz_mining_20260809/mining/CANDIDATES.jsonl` = **6,800 disagreement rows** over
400/400 games, of which **1,650 carry `merge_exposure_differs: true`** (emitted at
`scripts/jcz_mining/mine_disagreements.py:938`). The 2026-08-09 run closed on branch **G3, NO
CONVICTION**, and S3 was deliberately excluded — [`MINING_PREREG.md`](../measurement/jcz_mining_20260809/MINING_PREREG.md) §3.4, verbatim:

> `merge_exposure_differs` — a boolean covariate for **S3** (`rateConnections`, city/road
> merge-flip anticipation). **S3 is explicitly NOT tested by this design.** Its territory is a
> tile-placement property that needs its own stratum and its own n… The covariate is recorded so
> a future cut is a **query, not a re-run**.

**Design.** Query `CANDIDATES.jsonl` for `merge_exposure_differs == true`; build an **S3
stratum** and a **matched control** using the prereg's own §3.3–3.4 matching discipline —
matched **exactly on `ply_class`** (TILE/MEEPLE) and on the ΔQ/phase covariates the A/B/C strata
matched on — sampled by the prereg's deterministic-hash ordering so the selection is not
discretionary. Score both with
[`oracle_score_pilot.py`](../scripts/measurement_infra/oracle_score_pilot.py) **unmodified at
M=32**, through its `--positions-jsonl` adapter (required per-line fields: `rid`, `deck_seed`,
`ply`, `pick_a`, `pick_b`, `root_player`, plus `actions` or `archive_path`; sign contract
`delta = V(pick_b) − V(pick_a)`).

**Sizing.** 50 positions per stratum (100 total). The prereg's gate is **n ≥ 25 scored per
stratum or the stratum is INCONCLUSIVE BY CONSTRUCTION**; its own re-open bar was n=74 for 80%
power at +1.4 pts/ply. **n=50 sits between the gate and the powered bar — say so.** Yield is not
the constraint (1,650 candidate rows).

**Primary statistic: mean ΔQ in pts/ply per stratum, cluster-robust z**, exactly as the mining
analyzer computes it, with the matched control read alongside.

**Branches (mirroring the mining decision map).**
- **S3 z ≥ +2.0 AND the matched control null** → a **localized conviction**: their evaluator
  out-earns ours specifically on merge-exposure. ⇒ any downstream play gate **must** use a
  **fresh band** (the mining prereg says so explicitly) and its funding is **Joshua's call**.
- **S3 and control move together** → background, not S3-specific — the same shape that killed
  stratum B (−0.904 vs its control −0.903).
- **|z| < 2.0** → **NO CONVICTION**; the JCZ steal file **closes** and the native-term build stays
  unfunded.

**Riders.** (i) Exploratory by construction — no strength claim, **no band claimed**; band
1.08e11 stays retired and this reuse does not un-retire it. (ii) `oracle_score_pilot.py` lives
under `scripts/measurement_infra/`, **not** `scripts/analyzer/`. (iii) The oracle prices with a
reference that is not the leaf under suspicion — that is the point; do not substitute the leaf.

**Cost.** ~1.4 h at W16, **one box (laptop), 0 games, no band**.

---

## 5. Recommended GO sequence

Parameterized from **T0** = the moment the first launcher fires. Two-box, `--shared-claim`,
evals strictly serial per §2.

| block | window | what runs | boxes |
|---|---|---|---|
| **A** | T0 → **T0+1.4 h** | **Item 1** (≤0.5 h) on local ‖ **Item 6** (~1.4 h) on laptop; **Item 2a wiring gate** on local after item 1 (~0.1 h) | both, non-game |
| **B** | T0+1.4 → **T0+4.4 h** | **Item 2b** — `farm_growth_off` n=1600 deploy | both, exclusive |
| **C** | T0+4.4 → **T0+6.6 h** | **Item 4** — 4 cells × n=800, ablation class | both, exclusive |
| **D** | T0+6.6 → **T0+8.1 h** | **Item 3** — width H2H n=800 | both, exclusive |
| **D′** | T0+8.1 → **T0+9.6 h** | *conditional* item-3 top-up to n=1600 (fires at 1.5 ≤ \|z\| < 2) | both, exclusive |
| **E** | T0+8.1 (or T0+9.6) → **T0+17.7 h** (or **T0+19.2 h**) | **Item 5** — CL-072 n→800 | both + **GPU exclusive** |

**Cumulative: ≈17.7 h without the item-3 top-up, ≈19.2 h with it** — about **0.8 box-days** of
two-box wall clock. Item 5 alone is **54%** of the total; blocks A–D together are **8.1 h**.

**Why this order.**
1. **Free things first.** Items 1 and 6 cost no games and no band, and item 1's answer changes
   how much future farm work is worth funding — cheap information that reprices later spending is
   always first.
2. **The top buy second.** Item 2 is the only item on the menu with a live path to a
   `PRODUCTION.yaml` change, and its gate is a 4-minute smoke.
3. **Cheapest-per-verdict third.** Item 4 retires a caveat that is currently written into
   `PRODUCTION.yaml` at ⅓ the per-game cost of a deploy cell.
4. **Item 3 fourth** — it resolves a decomposition and discharges a named falsifier, but changes
   no deployment either way.
5. **Item 5 last** — it is the single most expensive item (9.6 h), it monopolizes the GPU, and it
   settles a **parked** lever rather than a live one. If the window closes, this is the item to
   drop, and dropping it costs nothing that is currently in flight.

**Natural stopping points**, if Joshua wants a shorter commitment: after **block B** (T0+4.4 h)
the top buy is answered; after **block D** (T0+8.1 h) everything except the parked rodv3 premise
is answered.

**Operational.** Local box has a dirty-reboot history (3 in 28 h on 2026-08-04, suspect =
self-inflicted memory pressure) — `--shared-claim` gives per-game checkpointing, and a resume
must clean claims-without-records first. Laptop `systemd-run --user` linger is enabled
(2026-08-09), so a detached run survives ssh exit. Bundle-sync the laptop before block A: local
has unpushed commits and stale remote code is a contamination class, not an inconvenience.

---

## 6. Decision points that stay Joshua's

Nothing below is decided by this plan or by any run it schedules.

1. **Launching anything at all.** This document authorizes nothing; each item's launch is its own
   go/no-go, and each launch commits a band.
2. **Any `PRODUCTION.yaml` adoption.** Item 2 at z ≥ +2 does **not** produce a champion change —
   it produces (a) an owed caps/curve re-sweep, then (b) a proposal. Item 4 at any |z| ≥ 2
   produces an owed re-tune, not an adoption.
3. **Funding more E4 games** — the natural consequence of item 1 branch **B** (and the standing
   cheapest way to grow every analyzer result).
4. **The rodv3 park/kill** — item 5's product. A confirmed negative retires the parked 65/300 gen;
   that retirement is a decision, not an automatic consequence.
5. **Funding a JCZ native-term build** if item 6 convicts — plus the fresh-band C5 play gate that
   any conviction would require.
6. **Whether to spend the item-3 top-up** (+1.5 h) when the pre-registered trigger fires.
7. **Whether item 5 runs at all**, given it is 55% of the menu's cost for a parked lever.
8. **Whether any of this is worth the local box's cycles while he is using it** — the W=14 cap is
   his, and everything above is priced at it.

---

## 7. Explicitly NOT in scope

- **No promotions and no `PRODUCTION.yaml` config changes** from any item here. The only
  `PRODUCTION.yaml` edit contemplated is item 4 replacing a *power-caveat sentence* with a
  measured bound — a governance touch, not a config change.
- **The phase axis stays CLOSED.** CL-077 stands and its falsifier was discharged-negative on
  2026-08-10 (n=800, margin z −0.78). No more n at that design; a re-open needs a new mechanism
  argument or a finer instrument.
- **No curve-SHAPE sweep.** Part A read `A4_UNRESOLVABLE`; the 3.9-box-day Optuna sweep is not
  funded and this plan does not smuggle it back in. Item 4's ×1.75 is a *scale* rung on a
  previously-measured axis, not a shape search.
- **No reservoir re-sweeps.** The false-negative sweep closed 2026-07-30 with 31 candidates
  checked and **0** resurrect-candidates.
- **No learned-track reopen, no new training arcs.** CL-039/042/064/065/066/073 stand.
- **No cross-band pooling anywhere**, and **no third/fourth pooling of the `farm_growth_off`
  cells** — the no-third-cell ruling holds.
- **No cloud/vast spend.** Two boxes, zero dollars.
- **No rules-scope expansion.** 2-player Base+Farmers, `fixed_v1`; R9-on where a cell says so.
- **No `engine/` or `src/` edits in the main tree while a cell is live** — build in a worktree.

---

## 8. What changed from the sweeps' sketches

Read this before quoting a number from either doc sweep. Every correction below was checked
against the file it cites.

### 8.1 Item 1 — the premise was wrong
The sweep said the 20.5 norm is *"cited in five files and derived in none."* **It is derived**, in
[`CORPUS_STATS_champ449.md`](../measurement/analyzer_20260802/CORPUS_STATS_champ449.md) (449 games
/ 898 seats, `farm_pts` mean **20.49**, sd 10.72), generated by `corpus_stats.py` against
`measurement/champ_action_logs/champ_games.jsonl`. It is also **not stale**: the same instrument
reads **20.81** on the `fixed_v1` / 11008 corpus
([`PHASE_C_DESCRIPTIVES.md`](../measurement/f9_phase_c/PHASE_C_DESCRIPTIVES.md) §3). So the
"stale-era norm" hypothesis is already largely excluded, and **reading A as the sweep framed it
(≈14 from an era correction) is not available.** The item is redesigned around the number that
genuinely does not exist: the champion's farm points **against a non-self opponent**, at the same
rules and budget as the E4 games. That is a better referee for the 11.0-vs-Joshua figure than
either self-play norm, because self-play farm points are inflated by both seats sharing one
farmer-timing policy. A ~20-line archive adapter is also needed (`confirm.jsonl` has no
`game_id`, and stores finals as `scores`).

### 8.2 Item 2 — the pooled number is wrong, and the wiring claim is PARTIAL
- **"+17.8 ± 12.3" does not exist anywhere in the repo.** The recorded 2-cell inverse-variance
  pool is **+26.6 ± 12.3 (z +2.16)** with **margin-pooled z ≈ +1.27**, and the two statistics
  disagree — disposition **PARKED suggestive-unpromoted** (DECISIONS 2026-08-03 early). The
  design is unchanged; the *expectation* it is sized against is not.
- **"Only run through `eval_puct_priors`" is TRUE as an operational fact but FALSE as a
  capability claim.** The code path to the fair harness exists end-to-end and would honor the
  knob; it has simply never been exercised (zero `farm_growth_off` manifests on the share). ⇒ the
  wiring gate is a **~4-minute smoke, not a build task** — but it stays a hard blocker, because
  the caps/curve build caught the clairvoyant rust mirrors ignoring `--rules-profile` entirely.
  The gate's exact shape (curve-drift stamping, the required explicit curve in the candidate
  JSON, the `farm_base_off` sign control) is spelled out in §4.2.
- **Added:** the honest power statement — n=1600 resolves the lean at face value but **not** its
  winner's-curse-calibrated size. The sweep did not say this and it changes how a null is written.

### 8.3 Item 3 — the named launcher is the wrong instrument
[`blind_curve_width11008.sh`](../scripts/classical_search/blind_curve_width11008.sh) exists, but
it grades k4×2752 **against the sighted RoD-v2 anchor** on band **70e9**, at n=200 — it is not a
head-to-head, and the anchor carries the **CL-070 ceiling: it cannot price budgets above 2752 and
mis-orders a +50-elo contrast by ~71 elo *including the sign*.** Adapting it would reproduce
exactly the quadrature-of-two-anchored-deltas design CL-060 is stuck in. Replaced with the
**direct H2H** that `eval_fair_puct.py` already documents in its own usage block (§4.3) — no new
script, a launcher wrapper on the proven two-box pattern.
Also corrected: **"k4 halves parallel width ⇒ ~2× latency" is not measured.** Sequential ms/move
is *equal* (15315 vs 14779). The ~2.2× is a projection from the measured k-parallel efficiency
curve; k4×2752 has never been benched k-parallel. The conclusion (not deployable) survives — the
*evidence* is a projection and must be written as one.

### 8.4 Item 4 — the ×1.75 rung is not virgin
`c5_s2_curve175_n400` = **+77.7 ± 17.7, paired z 4.19** (2026-07-13, clean, post-OpenBLAS-fix)
already measured it under `walled`, statistically tied with curve125's +66.8 (+10.9, <1σ) — which
is *why* curve125 was adopted. So the cell is a `fixed_v1` re-measure with a curse-adjusted
expectation of **+3 to +4 elo**, inside the ±17.5-elo floor. "First-ever `fixed_v1` measurement
above ×1.25" is correct; "never measured" would not be. Also: **n=800/cell is derived, not
chosen** — the re-sweep's own paired 2σ ≈ 35 elo at n=200 scales to **±17.5 elo at n=800**, which
is exactly what retires a "≤20 elo" caveat.
Minor: the phrase "s2750 ablation instrument" does not appear in the repo; the instrument is
`eval_puct_priors.py` at `--cand-sims 2750`, both sides, rust, net-free.

### 8.5 Item 5 — the arms and the joiner were both mis-stated
The opponent is **not** "its 11008 corpus teacher" as a checkpoint — it is the **production
classical champion** at the promoted k8×1376 budget (same tier as the corpus teacher). And the
laptop question is already answered by the n=400 run itself: the laptop served **its own** net
from **its own** GPU at OW=12 alongside local's OW=20.
[`laptop_joiner.sh`](../scripts/az_zero/laptop_joiner.sh) is a **generation** joiner for az_zero
(the ~16% figure and the `_clean_stranded` residue belong to that loop) and is **not** the
mechanism here. Both topologies priced: **9.6 h** two-box vs **17.8 h** local-only.

### 8.6 Item 6 — path correction, and S3 needs building not querying
`oracle_score_pilot.py` is at **`scripts/measurement_infra/`**, not `scripts/analyzer/`. And the
mining run recorded the covariate but built **no S3 stratum and no matched control** — the cut is
a query *into the candidates file* followed by a fresh stratum construction, which is a small
build, not a re-analysis of existing strata.

### 8.7 The cost model
- **Local W14 is 253.5 games/h (14.2 s/game), not half of W30.** The linear-in-W read would give
  171.7; the measured figure is ~48% higher because the W-throughput curve is concave (F7d: W*=30
  with the peak still climbing at W32). Two independent measurements (14.2 s/game in the b0p3
  prereg; 13.25 s/game in the F14 deck baseline) agree.
- **The 57/43 split is confirmed exactly** — 453 local / 342 laptop of 795 recoverable claim
  files from the b0p3 run. ⇒ laptop W22 = 277.5 g/h.
- **"~3× cheaper" for the ablation class is right on wall clock (measured 2.7–3.2×, centre ~2.8×;
  3.01× normalized per worker) even though the sims ratio is 4.00×.** Planned at the conservative
  2.8×. Do not substitute the sims ratio for the throughput ratio.
- **A stale figure is still on the record, and this plan does not fix it.** `STATUS.md` and the
  roadmap's NOW block still describe the b0p3 run as *"~3.1 h wall"*; the corrected value is
  **1.24 h / 4462 s** (`DECISIONS.md`, `PREREG_POWER03.md`, `results.csv` — commit `71007f7`
  fixed three files but not those two). Flagged here, not edited, because this plan is read-only
  outside its own file and its two pointers. **Worth a one-line fix on the next close-out touch.**
- **The net-arm class is ~12× slower than the deploy class** and is GPU-bound, so it does not
  scale with the CPU cost model at all — item 5 is priced from its own measured run.

---

*Companion documents: [`STATUS.md`](../STATUS.md) (live state) ·
[`PROGRAM_ROADMAP_2026-07-07.md`](PROGRAM_ROADMAP_2026-07-07.md) (the queue) ·
[`LEVER_INDEX.md`](LEVER_INDEX.md) (check before proposing any lever) ·
[`BAND_REGISTRY.csv`](../governance/BAND_REGISTRY.csv) (claim a band in the prereg commit).*
