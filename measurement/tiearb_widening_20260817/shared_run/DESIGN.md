# TIE-ARBITER WIDENING — SHARED INSTRUMENT RUN, DESIGN (rungs 2 `B>16` + 3 `J>4`)

> **STATUS: BLIND PREREGISTRATION, DRAFT. NOT LAUNCHED. NOTHING RUN. NO OUTCOME STATISTIC
> OF ANY KIND WAS READ WHILE WRITING THIS.**
>
> ⚠️ **BLIND-ORDER REQUIREMENT — NOT YET SATISFIED.** This file and
> [`READ_RULE.md`](READ_RULE.md) were drafted and committed in an isolated **worktree**
> while the main tree is under a commit freeze. A worktree commit does **not** satisfy
> blindness. **Both files must be committed to the MAIN tree, in ONE commit, BEFORE the
> band is claimed and BEFORE one position is scored.** Until that commit exists, no leg of
> this run may start. Neither file may be edited after that commit except through a
> numbered `§0` pre-run amendment that leaves every branch condition byte-identical (the
> Stage-2 precedent).
>
> Authorities this obeys: [`CAMPAIGN.md`](../CAMPAIGN.md) rulings 1–5 (rungs 1 and 4 are
> CLOSED; this run carries **only** rungs 2+3) · [`PLAN_B_gt_16.md`](../PLAN_B_gt_16.md)
> (design core) · [`PLAN_J_gt_4.md`](../PLAN_J_gt_4.md) (rider prereg) ·
> [`census/READOUT.md`](../census/READOUT.md) · the merged W1 build
> (`scripts/tiletie/tier1_rust_leg.py`, `run_tiletie.py --arb-backend rust`).
> Where a PLAN and this DESIGN disagree, **this DESIGN governs the run** and §14 records why.
>
> `governance/PRODUCTION.yaml` is untouched by this DESIGN and by every branch of the
> READ_RULE. No claim id is minted. No `experiments/results.csv` strength row is created.

---

## 1. What this run is

One paid instrument run, one corpus, two rungs reading **disjoint statistics**, **one blind
commit, one read-out, one analyzer invocation**. It is an **offline pricing measurement of
tied tile plies** — not a strength cell, not a game cell, not a deploy.

- **Rung 2 (`B>16`)** — is the arbiter's CRN-sample ladder still rising above `B = 16`?
  Primary: `Δ(16→64)` on `arb`.
- **Rung 3 (`J>4`)** — at plies where the `J ≤ 4` cap bit, what does pricing the **full**
  deduped arm set buy? Primary: `Δ_ora` at capped plies, against two pre-registered
  multipliers (legacy **1.400**, dedupe-corrected **1.244**).

**Out of scope on every branch:** any game cell, any pts/game projection without the §7
translation rider, any on-device/phone statement, any `J`-by-condition deploy policy, any
change to `rust/`, `src/`, `engine/`, `scripts/classical_search/`.

---

## 2. Cells and their statistics

Two **root-disjoint** strata mined from ONE fresh game set. `E` = evaluation (clair-puct)
worlds; usable `B` is `M/2` because the estimator cross-fits on parity halves
(`analyze_tiletie.parity_indices`; PLAN_B §0.2).

| cell | stratum | arm set priced | worlds | statistic | owner |
|---|---|---|---|---|---|
| **B-LADDER** (primary, rung 2) | S1 | J=4 seeded subset (`subset_j4`) | `M=128` → `E=64` | `arb(B)`, `B ∈ {1,2,4,8,16,32,64}`; **PRIMARY `Δ(16→64)`** | rung 2 |
| B-LADDER-E16 | S1 | `subset_j4` | `M=128` → `E=16` sub-read | same ladder at Stage-1b's precision | rung 2 |
| **SHARED CELL** `arb(B=16, J≤4, E=16)` | S1 | `subset_j4` | `B=16`, `E=16` | ONE number, **declared shared**; printed identically in both rungs' sections; **neither rung's branch may be conditioned on it beyond the gates in READ_RULE §2** | both |
| **J-RIDER** (primary, rung 3) | S2 | full deduped set **vs** `subset_j4` | `M=32` → `E=16`, `B=16` | **PRIMARY `Δ_ora = ora_full − ora_J4`**; `R_ora = ora_full/ora_J4`; `Δ_arb`, `R_arb` as **deploy riders** | rung 3 |
| J-REPLICATION | S1 ∩ capped (≈244 plies) | full vs `subset_j4` | `M=128`, `E=64` | `Δ_ora` — independent, higher-precision, **non-adjudicating** | rider |
| B×J INTERACTION | S1 ∩ capped | **full set** | `B ∈ {16,64}`, `E=64` | `arb_full(64) − arb_full(16)` and `arb_full(16) − arb_J4(16)` — the §3 selection-noise question | rider |

**Adjudicating statistic (PLAN_J ask 3 — RESOLVED):** `ora` adjudicates rung 3, `arb` rides
as the deployable quantity. This adopts PLAN_J §9.3's own recommendation and keeps the read
faithful to what §4.6's ×1.40 was a claim *about*.

**Reported in full, never a branch input:** the 7-rung × 2-`E` ladder with `arb`, `z`, `F`,
`F_fixed`, `rho_wall`, contended `ms_ratio` projection · pick-churn per doubling ·
oracle-agreement per rung · `arb − rnd` per rung · the S1/S2 half-split · `R_arb`.

---

## 3. Corpus

**Generation.** Fresh champion self-play, config matched **verbatim** to
`measurement/champ_action_logs/CORPUS_MANIFEST.json` (FairHeuristicPriorAgent, k_dets=4 ×
sims=688 = 2752, exact_endgame K≤2, leaf `a36d2e15a3b3d71d`, `rules_profile=walled`), the
`measurement/tiearb2_20260816/run_gen.sh` pattern:
`scripts/distill_flywheel/gen_fair_distill.py --backend rust`, `--shared-claim` work-stealing,
both boxes, `nice -n 19`, detached. **Only the deck-seed band differs ⇒ root-level
disjointness by construction.**

**Band.** Claim **`135000000000` + 0…+849** (850 games). **Top-up range `136000000000` +
0…+199 RESERVED, not licensed** except by §3's blind corpus top-up clause. CAMPAIGN ruling 4
named `134000000000`; that is **superseded** — the JCZ re-run consumed it. **Re-read
`governance/BAND_REGISTRY.csv` at claim time regardless** and claim the row before game 1
(tier `claim`, `decision_influenced=no`, notes stating **OFFLINE CORPUS SUBSTRATE — no
strength cell, no results.csv row**). Precedent deviation recorded: the Stage-1b corpus used
an *unregistered* band (`28100000000…`); registering is the stricter choice and is what
CAMPAIGN ruling 4 asks for (owner-ask 4).

**Yield math (PLAN_B §3 / PLAN_J §4).** φ = 17.57 tied tile plies/game (candidate-side);
capped fraction 0.1807 ⇒ **3.17 capped plies/game**.

| stratum | games | mining ceiling | target | supply at target |
|---|---|---|---|---|
| **S1** — uniform tied plies (B-ladder) | 350 (band +0…+349) | `--max-per-game 4` | **n₁ = 1,350** | 1,400 |
| **S2** — capped-only plies (J rider) | 500 (band +350…+849) | `--max-per-game 3` (PLAN_J ask 4 — RESOLVED: ≤3 capped plies/game, root-bootstrap SEs) | **n₂ = 1,100 capped** | ≈1,150 expected |

**Blind corpus top-up clause (pre-licensed here, exercisable ONCE):** if the realized S2
capped yield is `< 1,100` at build time, extend generation into the reserved `136e9` range
until it reaches 1,100. **Licensed ONLY before the first scoring leg starts** — i.e. while
no statistic of this corpus exists. After any leg starts it is dead and a shortfall is read
under the §2 completion floor.

**Disjointness.** S1 ∩ S2 root-disjoint by band split. Both disjoint from
`measurement/tiletie_pricing_20260812/positions_pooled`,
`measurement/tiearb2_20260816/corpus/positions`, and
`measurement/tiearb2_20260816/corpus/EXCLUDE_RIDS_all.txt` — proved by
`scripts/tiletie/gate_disjoint.py`, not asserted (gate `G-DISJOINT`).

---

## 4. Instrument invocation

Worker counts live in **ONE** file, `shared_run/WORKERS.conf` (the tiearb2 house pattern) —
never hard-coded. Every leg `nice -n 19` and **detached** (`setsid nohup … & disown`).

```
# corpus (per stratum X ∈ {s1: max-per-game 4, s2: max-per-game 3})
run_census.py    --max-per-game <4|3> --sample-seed 20260819 --out-dir corpus/census_<X>
build_positions.py --census-rows corpus/census_<X>/rows.jsonl \
                   --cap-j inf                      # UNCAPPED: arms_full + subset_j4 recorded
                   --afterstate-map corpus/census_<X>/afterstate_map_walled.json \
                   --exclude-rids corpus/EXCLUDE_RIDS_all.txt \
                   --sample-seed 20260819 --n <1350|1100> --out-dir corpus/positions_<X>
# S2 is a TWO-PASS build: pass 1 with --allow-missing-champ-picks (free, no playouts) to
# learn `capped_at_4` per rid; select ≤3 capped rids/root; pass 2 with champ picks for the
# selected rids only. `capped_at_4` is knowable BEFORE any pricing — the selection is
# outcome-blind by construction.

# scoring — S1
run_tiletie.py --judges clair-puct tier1-greedy --arb-backend rust \
  --m 128 --positions-dir corpus/positions_s1 --only-profiles walled \
  --out-root /mnt/c/carc-shared/tiearb_widening_20260817/s1 \
  --manifest-out RUN_MANIFEST_S1.json --smoke-manifest SMOKE_MANIFEST_S1.json --yes

# scoring — S2 (identical except --m 32; B is capped at 16 there, which is all rung 3 reads)
run_tiletie.py --judges clair-puct tier1-greedy --arb-backend rust \
  --m 32  --positions-dir corpus/positions_s2 --only-profiles walled \
  --out-root /mnt/c/carc-shared/tiearb_widening_20260817/s2 \
  --manifest-out RUN_MANIFEST_S2.json --smoke-manifest SMOKE_MANIFEST_S2.json --yes
```

**Why S2 runs at `M=32`, not 128.** Rung 3 reads only `B=16`, which `M=32` fully supplies
(sel 16 / eva 16), and `E=16` is **the precision Stage-1b's `capped_only` levels — the source
of the +0.1382 / +0.0842 predictions — were measured at**. Matching it keeps the predictions
and the measurement in the same currency and costs 4× less. `ora` is an `E`-dependent
quantity (it is the value reachable by an oracle selecting on `E/2` worlds); mixing `E`
across the strata would make the pooled `Δ_ora` a mixture of two estimands, so **S1 and S2
are never pooled** — S1's capped subset is reported as an independent replication rider (§2).

**Salts, explicit (the W1 two-salt finding).** Three distinct seed streams exist and are
recorded, never conflated:

| stream | value | set by | governs |
|---|---|---|---|
| CRN world/playout salt | **`tiletie-v1`** | `run_tiletie.WORLD_SEED_SALT` (module constant, not a flag) + `tier1_rust_leg --world-seed-salt` | which determinized worlds every arm and both judges share |
| instrument cap draw | **`tiletie-cap` \| `20260812` \| rid** | `build_positions._seeded_cap` | which arms `subset_j4` contains |
| deployed cap draw | **`tiearb2-deploy-v1` \| state_digest \| ply \| `"cap"`** | `carc-core::tiearb::build_arms` (MT19937) | which arms the **shipped** arbiter would have priced |

`--m` is bounded at `M_MAX = 128`; `RUN_MANIFEST*.json::b_ceiling_from_m` records `M/2`.
`--arb-legal-mask-cache` stays **ON** (the default) — the honest recomputed mask is **not**
python-comparable (57/15,360 values moved in Phase A) and would fail `G-BITEXACT` on a
healthy run.

---

## 5. The W4 / `G-CAP` decision — **RESOLVED: instrument-draw-only scope**

**W4 is CLOSED as an emission item.** The merged W1 build already emits, per ply, the full
deduped arm list (`arms_full`), the materialised J=4 subset (`subset_j4`), its digest
(`subset_j4_id`), the draw seed (`cap_seed`), `capped_at_4`, `n_distinct_afterstates` and
`champ_outside_tieset` — PLAN_J §8 requirements (1)–(3). PLAN_B §3 still lists W4 as
outstanding; it is not.

**What was left to this DESIGN is the *reconstruction* question, and the answer is: we do
NOT build it, and `G-CAP` as written in PLAN_J §6 is RETIRED as unsatisfiable.**
PLAN_J §6 asks a gate to assert that the recorded J=4 subset reproduces the *deployed* seeded
draw — but PLAN_J §2 itself records that the corpus-time draw
(`random.Random(sha256("tiletie-cap"|20260812|rid))`, python) and the runtime draw
(MT19937 seeded `sha256("tiearb2-deploy-v1"|state_digest|ply|"cap")`, rust) are **deliberately
not stream-identical**. A gate demanding their identity therefore **fails on every healthy
run** — the exact shape of the three JCZ conjuncts (`§0.F.2b`, `§0.F.2c`) that made an
adjudication unreadable, and the reason this DESIGN writes a healthy-run behaviour column for
every gate. Building the reconstruction instead would not repair it: it would import an
*unverified* cross-language identity (python's afterstate dedupe key vs rust's
`string_representation`, plus a ply-index convention) onto the critical path of a measurement
that does not need it, so a failure would be uninterpretable — an instrument defect wearing
the clothes of a finding. And it is not needed, because the estimand is
`Δ = E[v(argmax over the full deduped set)] − E[v(argmax over a uniform-without-replacement
J=4 draw from that same set)]`: **both generators realize the same uniform draw law over the
same deduped candidate list**, so the instrument draw is an unbiased, identically-paired
estimator of the deployed contrast. What is lost is only **per-ply identity** — the claim
"at *this* ply the shipped arbiter left X on the table" is not licensed; the population claim
is. That loss is carried as mandatory interpretation rider **`I7-draw-scope`** on every rung-3
branch. `G-CAP` is replaced by the satisfiable `G-DRAW` (READ_RULE §2). Recorded, not relied
on: the rust cap seed does **not** include `j` (`tiearb.rs` L300 vs its L353 doc comment), so
deployed draws are nested in `j` — a doc bug in a frozen crate, no behaviour consequence here.

**Optional, unfunded, non-adjudicating:** `D-DRAW` — replay each S2 capped ply in rust and
call `carc_rs …tiearb_probe(j=4, salt="tiearb2-deploy-v1", ply=…)` to measure how often the
two draws agree. ≈1 replay + `chain_values` per ply, **no playouts, ≈2 worker-h**. It may be
funded (owner-ask 6) and reported; **it can never move a branch**.

---

## 6. Power arithmetic (shown, not asserted)

**Rung 2.** `Δ = arb(B_hi) − arb(B_lo)` is exactly 0 at every position whose pick does not
flip, so it is far better paired than two levels (banked `se(Δ 8→16)` 0.0290 vs
`se(arb_16)` 0.0479). Measured variance law: `Var(Δ; E) = T + N/E`, `T = 0.19`, `N = 15.4`,
validated (predicted `se(Δ 8→16)` at n=1350, E=16 = 0.0297 vs published 0.0290). At
**n₁ = 1,350, E = 64**: **`se(Δ(16→64)) ≈ 0.0198–0.0203`, 2σ floor = +0.040.**

| pre-registered model (PLAN_B §1) | Δ(16→64) | resolved at 2σ? |
|---|---|---|
| log-linear in `log2 B` | +0.0640 | **yes** (z ≈ 3.2) |
| hyperbolic `L·B/(B+K)` | +0.0530 | **yes** (z ≈ 2.6) |
| power `a·B^p` | +0.1958 | **yes** (z ≈ 9.7) |
| saturating exp `L(1−e^{−B/τ})` | +0.0171 | **no** (z ≈ 0.85) |
| selection-noise `L(1−k/√B)` | +0.0209 | **no** (z ≈ 1.05) |

⇒ **a null here means "no rung above 16 is worth ≥ +0.04 pts/tied ply", NOT "Δ = 0".**
Pre-registered blind spot (PLAN_B §6 Q2); resolving a +0.02 residual needs n ≈ 5,700
(≈ +1,100 worker-h) and is **not** funded. Secondary `Δ(16→32)`, `se ≈ 0.018`, floor +0.036 —
under-powered by design, reported with its CI, **never a branch input on its own**.

**Rung 3.** `sd_Δ` is unmeasured anywhere and is **bracketed** in advance: bounded above by
the per-position level sd (1.7197) and reduced by the ~61% of capped plies where the full-set
argmax already lies inside the J=4 subset (exact zeros) ⇒ **`sd_Δ ∈ [0.9, 1.4]`**. At
**N_capped = 1,100**: `se(Δ_ora) = sd_Δ/√1100 ∈ [0.0271, 0.0422]`, **2σ bar ∈ [+0.054, +0.084]**.

| prediction | `Δ_ora` pts/capped ply | z at sd 0.9 / 1.4 | resolved? |
|---|---|---|---|
| legacy ×1.400 | +0.1382 | 5.1 / 3.3 | **yes** |
| corrected ×1.244 | +0.0842 | 3.1 / 2.0 | **yes** (marginal at sd 1.4) |
| cap-was-free ×1.00 | 0 | — | separable from both |
| **1.400 vs 1.244** (Δ = 0.054) | — | 2.0 / 1.28 | **NO — pre-registered blind spot** |

SEs are **root-bootstrap** (resample `root_id`, 2,000 reps, seed `20260819`), never naive
per-ply. The ≤3 capped-plies/root ceiling exists to hold the within-root clustering near
Stage-1b's 1.10 capped/root. The S1 replication rider (≈244 capped plies at E=64) has
`se ∈ [0.058, 0.090]` and adjudicates nothing.

---

## 7. Cost and ETA — **two currencies, never converted**

**Currency A: offline worker-seconds** (what this run spends). `c_ARB = 0.178232`
worker-s/playout (rust, measured at W30 contended), `c_IF = 2.35` (measured off banked
`elapsed_secs`). Playouts per judge = `n × 2 × (Ā − 1) × M`; `Ā_full` = 3.581 all plies /
7.12 at capped plies.

| item | worker-h |
|---|---|
| generation, 850 games @ 990 worker-s | 233.8 |
| champ picks, 2,450 positions @ 13.755 worker-s | 9.4 |
| S1 ARB (rust) — 891,993 playouts | 44.2 |
| S1 IF (clair-puct) — 891,993 playouts | 582.3 |
| S2 ARB — 430,848 playouts | 21.3 |
| S2 IF — 430,848 playouts | 281.2 |
| **TOTAL** | **≈ 1,172** |

**ETA.** Generation at the F7d **GEN** worker counts (local **W48** / laptop **W24** =
72) ≈ 3.2 h parity; scoring at the F7d **eval** counts (local **W30** / laptop **W22** = 52)
≈ 17.9 h parity; with PLAN_B's 25% laptop-slowness + contention allowance,
**≈ 26–29 h two-box wall**. This is **+35% worker-h and +6 h wall over CAMPAIGN sequencing
item 2's 865 wh / 20–22 h** — the delta is entirely rung 3's power (owner-ask 1).

**⚠️ `c`-REMEASURE OBLIGATION (binding, before the long leg).** Both `c` figures are
inherited and one (generation, 990 worker-s/game) is contradicted by the F7d GEN row
(~590 games/h two-box ⇒ ~440 worker-s/game). Before the S1 IF leg starts:
**on an IDLE box (a timing bench is an exclusive tenant — no agent compute beside it),** run
the `run_tiletie --smoke` at production knobs (`--m 128`, `--arb-backend rust`, walled,
≥20 positions) and read `SMOKE_MANIFEST_S1.json::worker_secs_per_playout` for both judges.
If any realized `c` differs from the committed value by **> 25%**, **HALT** and re-price via
`build_positions.full_run_eta_secs`; a re-priced run above **1,500 worker-h** requires a fresh
owner authorization. Record realized vs committed in `RUN_MANIFEST_S1.json`.

**Currency B: deploy wall (NOT convertible — Stage-2 §0.G; these are quoted, never derived
from currency A).** `rho_wall` (sequential, N4 bar 1.20): B=16 **0.6224** ✅ · B=32
**1.2449** ❌ · B=64 **2.4897** ❌. Realized contended in-cell `ms_ratio`: **2.42 at B=16**,
projected ≈3.75 / ≈6.50. `rho_phone`: 5.976 / 11.95 / 23.90. Rung 3: `Ā` 3.0022→3.5044 =
+16.7% per fired ply, `rho_wall` → ≈0.727, `ms_ratio` ≈2.42 → **≈2.66** (+9.7% per-move wall).
**Every one of these must be re-measured before any flip decision, never inferred.**

---

## 8. Instrument work items

| item | state |
|---|---|
| **W1** wire rust ARB judge | ✅ **MERGED** (`tier1_rust_leg.py`, `run_tiletie --arb-backend rust`) |
| **W4** uncapped arms + draw index | ✅ **CLOSED** (§5) — already emitted by `build_positions` |
| **W2** no hard-coded 32 downstream of `--m` | TODO before launch |
| **W3** analyzer: `m_expected` 128/32, `b_ladder {1,2,4,8,16,32,64}`, `E` sub-read, S1/S2 strata, the `widening.*` verdict block the READ_RULE addresses | TODO before launch |
| **W5** `gate_disjoint.py` vs `EXCLUDE_RIDS_all.txt ∪ Stage-1b's 1,350`, **plus** an S1∩S2 root-overlap key | TODO before launch |
| **W6** corpus driver `build_widening_corpus.sh` (the `build_tiearb2_corpus.sh` pattern, parameterised by band / `--max-per-game` / two strata / two-pass S2 selection) | TODO before launch |
| PLAN_J §8(4) runtime `tiearb_capped_total` counter | **NOT built, NOT a gate** — it is a *deploy-side rust* counter and `rust/` is frozen. The offline requirement is already met by `ARMS.json::capped_at_4` and `POSITIONS_PLAN.json::n_positions_capped_at_4`. |

---

## 9. Manifests the run MUST write (self-describing, house rule)

`corpus/GEN_MANIFEST.json` (band, seeds used, generator config, sha256 of the games file) ·
`corpus/positions_{s1,s2}/{POSITIONS_PLAN.json,ARMS.json}` ·
`GATE_DISJOINT.json` · `GATE_BITEXACT_HEAD.json` · `GATE_DRAW.json` ·
`RUN_MANIFEST_{S1,S2}.json` · `SMOKE_MANIFEST_{S1,S2}.json` ·
`verdicts/READOUT.{json,md}` + `verdicts/per_position_{s1,s2}.jsonl` · `logs/`.
Every one carries the fully resolved config — no result may require dirname archaeology.

---

## 10. PLAN_J ask 6 — draft `I6` amendment text (**for owner approval; NOT enacted here**)

> **`I6-fullset-extrapolation-scope` — PROPOSED AMENDMENT.** Takes effect **only** if branch
> `X-PARTIAL` or `X-FREE` fires in `shared_run/READ_RULE.md`, and only on the owner's
> approval recorded in DECISIONS.
>
> *In force since 2026-08-12, on every tiletie/tiearb VERDICT:* the full-set ceiling is
> ≈1.40× the measured `J=4` headroom, an extrapolation through the S1a spread estimate,
> never a measurement.
>
> *Proposed replacement text:* "The ×1.40 multiplier is an order-statistic extrapolation over
> **raw** tied-set sizes (mean 8.55) applied **globally**. The arbiter prices **deduped** arm
> sets (mean 3.348 over all plies; 7.12 full-set at capped plies) and the cap binds on 18.07%
> of plies. Re-running §4.6's own machinery on the deduped population gives **≈1.244× at
> capped plies** and **≈1.087× globally**. Every VERDICT quoting ×1.40 is to be read with this
> correction. **The multiplier cancels out of `F`, so no prior verdict's branch, bound or
> claim moves** — this changes a quoted headroom figure and nothing else. The measured
> multiplier of record is `R_ora` = ⟨value, CI⟩ from
> `measurement/tiearb_widening_20260817/shared_run/verdicts/READOUT.json`."
>
> *Scope:* text-only, on the VERDICT riders + the `governance/CLAIM_REGISTRY.csv` notes
> column. No claim id minted, retired or moved. `governance/PRODUCTION.yaml` untouched.

---

## 11. Owner-ask list (only Joshua can decide these)

1. **Fund ≈1,172 worker-h / ≈26–29 h two-box wall** (vs the 865 wh / 20–22 h in CAMPAIGN
   sequencing item 2). Cheaper alternatives, both pre-priced: **J-FLOOR** N_capped = 700 ⇒
   ≈1,043 wh / ≈24–26 h (loses the corrected-1.244 resolution at `sd_Δ` 1.4); **J-BUNDLED**
   no S2 at all ⇒ ≈+141 wh over PLAN_B, N_capped ≈ 244, and rung 3 becomes a **screen that
   cannot resolve either prediction at 2σ**.
2. **PLAN_B §6 Q3 — does the N4 `rho_wall ≤ 1.20` waiver extend above B = 16?** B=32 misses
   by 3.7%, B=64 by 2.07×. If it does not, rung 2 is **informational only** and no deploy
   branch can ever fire from it. **Settle before the run, not after.**
3. **PLAN_B §6 Q4 — is the phone ever the deploy target?** `rho_phone(64) = 23.9`. If yes,
   `B > 16` is desktop-only value and must be graded that way from the start.
4. **Band `135000000000` + `136000000000` top-up reservation** (CAMPAIGN ruling 4's `134e9`
   is superseded), and: is a BAND_REGISTRY row the right home for an **offline corpus
   substrate** band at all? (Stage-1b's corpus band was never registered.)
5. **Approve the §10 `I6` amendment text in advance** (PLAN_J ask 6), so an `X-PARTIAL`
   landing does not stall on a governance decision.
6. **Approve the §5 W4/`G-CAP` resolution** — instrument-draw-only scope + rider
   `I7-draw-scope`, `G-CAP` retired as unsatisfiable — and say whether to fund the optional
   `D-DRAW` diagnostic (≈2 worker-h, non-adjudicating).
7. **Accept the two pre-registered blind spots:** a +0.02 residual on rung 2 reads as a null
   (+1,100 wh to fix, not recommended); 1.400 vs 1.244 is not separable on rung 3 at any
   affordable size.
8. **PLAN_B §6 Q6** — prereg the `B=64` game-cell *trigger and design* now and size `n` from
   a committed formula after the offline read? (This DESIGN sizes **no** game cell, per
   CAMPAIGN ruling 5.)
9. **Queue and boxes** — this queues behind the JCZ re-run; confirm the two-box split and
   that the `c`-remeasure smoke gets an **idle** box.

---

## 12. Contradictions found between the authorities, and how this DESIGN resolves them

1. **n vs N_capped (material).** PLAN_B sizes n = 1,350 tied plies; at the 18.07% cap rate
   that yields ≈244 capped plies, but PLAN_J §4 needs **1,100** (floor 700). PLAN_J §8's own
   shared-run table meanwhile assumes **7,900** tied plies, 5.9× PLAN_B's n. **Resolved:**
   two root-disjoint strata off one game set — S1 (n=1,350, M=128) serves rung 2 exactly as
   PLAN_B specified; S2 (1,100 capped-only plies, M=32) serves rung 3 at its own
   pre-registered power. Neither plan's n is silently rescaled.
2. **PLAN_J §8's cost is a ~6× under-estimate.** Its "≈165 worker-h ≈ 3.2 h wall" counts only
   the tier1/ARB playouts; PLAN_B §0.3 establishes that **clair-puct pricing is ~93% of the
   bill**. **Resolved:** both judges are priced on both strata (§7); PLAN_J §8's total is
   superseded.
3. **`G-CAP` is unsatisfiable as written** (PLAN_J §6 vs PLAN_J §2). **Resolved in §5** —
   instrument-draw-only scope, `G-DRAW` replaces it, rider `I7-draw-scope`.
4. **PLAN_J §6's branch table mis-reads a result ABOVE 1.400.** As written, an `R_ora` CI
   entirely above 1.400 satisfies `X-PARTIAL` ("1.400 outside CI, 1.244 inside or below it")
   and would be reported as *below* the legacy prediction — the opposite of the truth.
   **Resolved:** `X-PARTIAL` gains the conjunct `upper(CI) < 1.400`, and a new branch
   **`X-ABOVE`** is added (READ_RULE §5). Fixed before any data exists.
5. **Band.** CAMPAIGN ruling 4 says `134e9`; the DESIGN-time instruction says `135e9`.
   **Resolved:** `135e9` + `136e9` reserved, re-read the registry at claim time (§3).
6. **`champ_picks` cost.** PLAN_B 13.7552 worker-s/position vs PLAN_J 1.409 (the *realized*
   figure from the Stage-1b pipeline). **Resolved:** budget the conservative 13.7552; the
   difference is < 1% of the bill and it is a `c`-remeasure line.
7. **Generation cost.** PLAN_B 990 worker-s/game vs roadmap F7d's GEN row (~590 games/h
   two-box at W48/W24 ⇒ ~440 worker-s/game). **Resolved:** budget 990 (conservative), name
   it in the `c`-remeasure obligation (§7).
8. **W4 already built** (PLAN_B §3 lists it as outstanding). **Resolved:** closed as an
   emission item; only the reconstruction question remained (§5).
9. **PLAN_J §8(4)'s `tiearb_capped_total`** is a runtime rust counter behind the freeze.
   **Resolved:** not built, not a gate; the offline witnesses already exist (§8).
