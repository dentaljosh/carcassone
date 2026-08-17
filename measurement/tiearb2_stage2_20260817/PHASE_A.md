# STAGE 2 — PHASE A: SOLVE COST (rust `tier1-greedy` continuation)

> **STATUS: ⭐ CLOSED 2026-08-17 — PASS. THE COST WALL IS GONE, AND THE RUNG THAT
> CAPTURES IS THE ONE THAT IS NOW AFFORDABLE.**
>
> - **`G-BITEXACT` PASSES on its committed counts**: `n_legs` **240/240**,
>   `n_playouts` **15,360/15,360 value-bit-identical**, plies identical 15,360,
>   seed witness 240/240, **0 mismatches**, and the two sha256 digests over the
>   little-endian f64 bytes are **equal**
>   (`0c2e39fe…6b88e80`). → [BITEXACT.json](BITEXACT.json)
> - **`c_tier1_rust` = 0.178232 worker-s/playout** at the production-like `W = 30`
>   (0.093769 at `W = 1`) ⇒ **15.30× the pilot `c` 2.7274** and 12.35× the realized
>   2.2004. **§1 committed a 7.94× requirement for `B = 16` before the port existed;
>   the port delivered 15.30×.** → [COST_REMEASURE.json](COST_REMEASURE.json)
> - ⇒ **`B_affordable` = 16.** `rho_wall(16)` = **0.6224**, i.e. the capturing rung
>   runs at **52% of the 1.20 bar** — *every* rung of the ladder is now affordable,
>   and **the §5 fallback ladder does not fire.** `rho_amortized(16)` = 0.1985.
> - ⚠️ **`rho_phone` is NOT solved and is not claimed to be**: 0.345 / 0.690 / 1.380
>   / 2.760 / **5.520** at `B` = 1/2/4/8/16, so on the shipped phone currency only
>   `B ≤ 2` is under 1.20. **Reported, unadjudicated** — the N4 bar this programme is
>   graded at is `rho_wall`, and a phone deploy is a later question, not a Phase-B
>   blocker.
>
> **⇒ Phase B is UNLOCKED**: an affordable capturing `B` exists on disk. Its
> DESIGN/READ_RULE are committed blind, after this file and after
> `COST_REMEASURE.json`.
>
> ⚠️ **By-catch, and it is a real bug in the python, not in the port.** The first
> verification run read **57 mismatching legs**. Localisation: `game_wrapper.Game`'s
> per-record legal-mask memo (`_legal_cache`) is keyed on `string_representation`,
> whose rotation signature is **not injective for 180°-symmetric tiles** — so the
> banked judge occasionally served a *colliding* legal mask, and the true-legal-mask
> port diverged from it. The port reproduces the memo, collisions included
> (`legal_mask_cache = True`), which is what bit-exactness against the banked records
> *means*. The underlying non-injective key is parked as its own roadmap item
> (`05ed019c`); it is **not** fixed here, because fixing it would break exactness
> against the corpus this gate grades. A cache-off sensitivity run reads
> `c` = 0.178857 (+0.35%), so the memo is not load-bearing for the cost number.
>
> **0 strength games in Phase A.** No `experiments/results.csv` row, no band, no claim
> id, `governance/PRODUCTION.yaml` untouched.

## 0. Owner authorization

Stage 1b ([../tiearb2_20260816/READOUT.md](../tiearb2_20260816/READOUT.md)) adjudicated
**`A-COSTLY`** on 2026-08-17 by a read-rule committed before the instrument existed.
That branch **licenses (does not fund)** exactly one thing: a fresh Stage-2
pre-registration of a deck-paired GAME cell which **MUST solve cost on its own terms
and MAY NOT assume the `B*` = 2 arm**.

**Owner authorization, 2026-08-17, verbatim:**

> "funded"

— in response to the `A-COSTLY` licensed next step as stated above. The funding is
therefore for **ONE** Stage-2 deck-paired game-cell prereg, carrying `A-DEPLOYABLE`'s
conditions (a)–(d) verbatim and arm `C`'s **NO CORROBORATION** sign-check rider
verbatim, and it does **not** authorize assuming `B* = 2`.

### 0.1 The four conditions that travel (READ_RULE §4, `A-DEPLOYABLE` (a)–(d))

Quoted verbatim from `measurement/tiearb2_20260816/READ_RULE.md` §4, which
`A-COSTLY` applies verbatim:

> The prereg must (a) carry a **matched-wall-clock control arm**; (b) carry DESIGN
> §12.1 verbatim (*both judges are terminal-grounded, so this is not yet a deploy-elo
> claim*); (c) carry the §5.6 sign-check verdict verbatim if it reads **NO
> CORROBORATION**; (d) re-derive cost against a **rust** continuation rather than
> inheriting `rho_wall`'s python upper bound.

**Phase A is condition (d).** (a)–(c) are discharged in the Phase-B DESIGN/READ_RULE.

### 0.2 The carried NO-CORROBORATION rider (verbatim, READOUT §7)

> **arm `C`** — over the **1050** positions where the arbiter changes the champion's
> pick in at least one fold: 511/1033 = **+0.495** with `arb[p] > 0`, exact two-sided
> binomial **p 0.756**; aggregate sign **+1**, per-position majority -1, mean over the
> pick-change positions +0.0414 ⇒ **NO CORROBORATION -- sign agreement is not
> distinguishable from chance**

⚠️ The sign check is **MANDATORY on every branch; NEVER a branch input.**

### 0.3 DESIGN §12.1, carried verbatim (condition (b))

> ⭐ **The arbiter and the pricing judge are both terminal-grounded.** They differ in
> policy (`RuleBasedPlayer` 1-ply argmax vs 100-sim clairvoyant PUCT) and are
> independent in the leaf, but they **share the property under test**. ⇒ **a positive
> here is evidence that terminal grounding at ties is worth points *as measured by a
> terminal-grounded ruler*, which is the estimand — it is NOT yet evidence of deploy
> elo.** This is why a pass licenses only a game-cell prereg, and why that prereg must
> be graded on games.

## 1. The cost problem, stated in numbers before any rust exists

The deployable bar is the house **N4 trigger currency**, `rho_wall ≤ 1.20`.

```
rho_wall(B)   =  Ā × B × c_tier1 / t_champ          Ā = 3.0022,  t_champ = 13.7552 s/move
rho_phone(B)  =  Ā × B × c_tier1 / 1.551
```

`Ā` = `measurement/tiearb2_20260816/corpus/positions/POSITIONS_PLAN.json::mean_arms`
= **3.0022**. `t_champ` = the champion at k8×1376 sequential on this box
(`governance/PRODUCTION.yaml` clock-legality block). `t_phone` = 1.551 s/move, the
shipped phone champion at `rust_threads: 2`.

Stage 1b's python `c_tier1`: **2.7274** worker-s/playout (pilot, the `B*`-freezing
value) and **2.2004** worker-s/playout (realized, from the ARB records'
`elapsed_secs`). The Stage-1b ladder:

| B | `arb` | z | `F` | `F_fixed` | `rho_wall` (pilot c) | ≤ 1.20? |
|---|---|---|---|---|---|---|
| 1 | +0.0094 | +0.20 | +0.052 | +0.034 | 0.595 | ✅ |
| 2 | +0.0322 | +0.65 | +0.179 | +0.115 | 1.191 | ✅ (arm `C`, **does not capture**) |
| 4 | +0.0920 | +1.93 | +0.511 | +0.328 | 2.381 | ❌ |
| 8 | +0.0826 | +1.76 | +0.459 | +0.295 | 4.762 | ❌ |
| 16 | +0.1441 | **+3.01** | +0.800 | **+0.514** | 9.525 | ❌ (arm `H`, **captures**) |

**The speedup Phase A must buy, computed before it is measured** (so the read cannot
be accused of fitting the target). The affordability condition is
`c ≤ 1.20 × 13.7552 / (3.0022 × B)` = `5.4979 / B`:

| B | max affordable `c_tier1_rust` (worker-s/playout) | speedup needed vs pilot 2.7274 | vs realized 2.2004 |
|---|---|---|---|
| 1 | 5.4979 | 0.50× (already affordable) | 0.40× |
| 2 | 2.7489 | 0.99× (already affordable) | 0.80× |
| 4 | 1.3745 | **1.98×** | **1.60×** |
| 8 | 0.6872 | **3.97×** | **3.20×** |
| 16 | 0.3436 | **7.94×** | **6.40×** |

Precedents for the port factor (never a promise): `carc_core::endgame` ran **20.8×**
the python solver; the general engine port ran **~9.4×**. The python `tier1-greedy`
continuation is the *slowest* path in the codebase — a `copy.deepcopy` of the whole
`CarcassonneGameState` **per candidate action**, then `PointsCollector.count_final_scores`
over the object graph — so the expected factor is at the high end. **It is not
automatic and it is not assumed.**

## 2. What is being built

The rust port of the **arbiter's cost core** and nothing else: the `tier1-greedy`
continuation playout — `RuleBasedPlayer` 1-ply argmax over the **v1 OBJECT** leaf
`virtual_score_inplace`, played to terminal. Nothing else in the arbiter moves the
cost.

Deliverables, in order, each committed before the next depends on it:

1. **The crate/module + tests** — additive only in `rust/carc/carc-core` and
   `rust/carc/carc-py`. No existing rust behaviour changes; the `scripts/rustport/`
   reconcile gates stay green.
2. **`BITEXACT.json`** — the gate. Count-only reporting, committed expected counts,
   mirroring the `G-REPRO` pattern.
3. **`COST_REMEASURE.json`** — `c_tier1_rust`, the recomputed `rho_wall` /
   `rho_phone` ladder, and the max affordable `B`.

## 3. `G-BITEXACT` — the gate, and it is a hard abort

The rust playout must reproduce the python judge's per-leg values **BIT-IDENTICALLY**
— same seeds, same picks, same values — on the adjudicated Stage-1b corpus before any
cost number is quoted.

- **Reference corpus**: `/mnt/c/carc-shared/tiearb2_20260816/main/chunk{1..4}/tier1-greedy/walled/leg{1..4}/records/*.json`
  — 2,703 adjudicated position-records, each carrying `world_seeds`, `playout_seeds`,
  `values_a`, `values_b`, `playout_plies_a/b`, `afterstate_deck_hash_a/b` and
  `crn_verified`, all under `G-CRN` (0 cross-judge mismatches over 2,703 legs).
  Root replay inputs (`deck_seed`, `actions`, `ply`, `pick_a`, `pick_b`,
  `root_player`, `rules_profile`) come from the matching
  `measurement/tiearb2_20260816/positions_chunk*/positions_walled_leg*.jsonl` line.
- **Sample**: **committed before it is drawn** — a seeded uniform sample stratified
  across all 4 chunks and all 4 legs, `n_legs = 240` position-records
  (**> the ≥200 floor**), = `240 × 32 worlds × 2 picks` = **15,360 playouts**.
  The seed and the resulting rid list are written to `BITEXACT.json` and the expected
  counts are the **committed constants**, never `len(new)`.
- **Reported**: counts only — `n_legs`, `n_playouts`, `n_value_bit_identical`,
  `n_mismatch`, `n_plies_identical`, `n_deck_hash_identical`, plus a sha256 over the
  reproduced `(values_a, values_b)` compared to a sha256 over the recorded ones. **A
  digest is not a value and is not invertible.**
- **Bit equality means `f64` bit patterns**, compared with the same `_f64_bits`
  discipline `run_tiletie.check_crn_cross_leg` uses. The values are integral margins,
  but the comparison is on the raw bits, not on `==` after a cast.
- ⛔ **If exact float equality is unreachable across the FFI boundary, PHASE A STOPS
  AND REPORTS. "Close" is not accepted and no cost number is quoted.**

## 4. Cost re-measurement, and what it is allowed to conclude

`c_tier1_rust` is measured in the **same currency** as the python `c_tier1`:
**worker-seconds per playout**, i.e. `Σ(per-record wall) / (n_records × 2 × m)`
summed inside `W`-parallel workers — the definition
`analyze_tiearb2.cost_block::c_from_elapsed_secs` uses.

- Measured **uncontended** (`W = 1`) and **production-like** (`W = 30`, the standing
  local figure in `measurement/tiearb2_20260816/WORKERS.conf`). The `W`-parallel
  worker-second figure is the branch-relevant one, because that is how the python `c`
  was measured and how a deployed arbiter would run.
- The box is censused before and after; a co-tenant voids the timing (memory
  `feedback_no_agent_compute_beside_eval`: a timing bench is an **exclusive tenant**).
- `rho_wall` and `rho_phone` are recomputed at `B ∈ {1,2,4,8,16}` with `Ā = 3.0022`
  unchanged, and `B_affordable = max{B : rho_wall_rust(B) ≤ 1.20}` is reported.
- ⚠️ **The capture column of the ladder is NOT re-measured and NOT re-adjudicated.**
  Stage 1b's read-rule is **SPENT** and its corpus is **BURNED**. The `arb`/`z`/`F` /
  `F_fixed` numbers are carried across as *published, already-adjudicated* values,
  used only to say which rungs capture. Phase A computes **no** strength statistic.

## 5. Pre-registered fallback ladder, in order — committed before `c_tier1_rust` exists

If the rust port lands short of the 7.94× that `B = 16` needs:

1. **Highest affordable `B` with `F_fixed ≥ 0.35` published evidence.** On the
   Stage-1b ladder only `B = 16` (`F_fixed` 0.514) clears 0.35; `B = 4` reads
   `F_fixed` 0.328 at z +1.93 and `B = 8` reads 0.295 at z +1.76 — **both below the
   read-rule's own `RBAR` bar and below its `C_z` bar.** So a Stage-2 cell at `B = 4`
   or `B = 8` would be carrying a *rung that did not clear the mechanism bar*, and the
   game cell must then carry that risk explicitly in its DESIGN and READ_RULE — it may
   not present `B = 4` as if it were the honest arm. ⚠️ Also note the ladder is
   **non-monotone** (`B = 8` reads *below* `B = 4`), which is itself a noise signature
   at these `n`s and is a reason not to treat any single sub-16 rung as a point
   estimate.
2. **A truncated-but-terminal-scored playout — ONLY if terminal grounding survives.**
   The Stage-1b designer **rejected** truncation, on the ground that it reintroduces
   the frontier blindness the whole axis exists to remove: a playout cut at ply `k`
   and scored by *any* non-terminal function is a static afterstate evaluation again,
   and DESIGN §12.1's estimand ("terminal grounding at ties is worth points") is no
   longer the thing being measured. That argument is **accepted as binding for any
   truncation scored by a heuristic**. The only truncation this ladder would admit is
   one whose scoring function is *itself* the exact terminal score of the truncated
   line — which, absent a solver, does not exist. ⇒ **In practice rung 2 is closed
   unless a specific construction defeats the frontier-blindness argument, and that
   construction must be written down and argued in this file before it is built.**
3. **STOP.** If no affordable `B` captures, Phase A terminates the programme: the
   verdict "cost wall stands: `X×` at best affordable `B`" is written here and into
   `docs/LEVER_INDEX.md` row 217, the six-touch close-out runs, and **the game cell is
   not fundable under the license and MUST NOT be launched.**

## 6. Governance

- Measurement + engineering only. **0 strength games in Phase A on every outcome.**
- No `experiments/results.csv` row, no band claim, no claim id, and
  `governance/PRODUCTION.yaml` **untouched** — in Phase A unconditionally, and in
  Phase B on every branch (an `A-DEPLOYABLE`-shaped pass licenses a production-flip
  **decision for the owner**, never an automatic flip).
- The champion config is untouched by construction: the Phase-B candidate's leaf hash
  must **equal** the champion's `a36d2e15a3b3d71d` (inverted liveness gate), with a
  positive-control liveness assert on the arbitration surface.
- `docs/LEVER_INDEX.md` row 217 is amended at start as in-progress and flipped at
  close.
- `python3 scripts/doc_lint.py` clean at every commit.
