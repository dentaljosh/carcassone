# OM-M1 — REFUTATION-PRICED ARBITRATION · FIRST KILL-GATE (`G-EXPRESS`)

**Status: PREREG FROZEN 2026-08-30T16:10Z at `8b187c71`, BEFORE any statistic
was computed on any leg.** No rollout has been run. No flip rate exists yet.
Everything in §5 (the bar), §6 (the read branches) and §7 (the guards) is
written from the funding argument and the *banked* constants in §2 — none of it
was tuned against a number this instrument produced.

Funded by the owner 2026-08-30 off
[`../cl083_redteam_20260830/MECHANISM_MENU.md`](../cl083_redteam_20260830/MECHANISM_MENU.md)
menu row 2 (OM-M1, composite 5 / 4 / 4 / 4), the one non-free gate in the batch.
Its three named siblings (HP-M1, CF-M1, SA-M1) were killed by their free gates
the same day — [`../cl083_mech_censuses_20260830/`](../cl083_mech_censuses_20260830/).

⛔ **THIS IS A KILL-GATE, NOT A LEVER.** Nothing here may enter
`governance/PRODUCTION.yaml`, `CHECKPOINT_LINEAGE.csv` or the adoption chain.
The refuter is an *instrument*, and it is asymmetric by construction — the
precedent and the exact wording are
`measurement/invasion_screen_r3_prep/screen_lib.SHAPE_B_IS_AN_INSTRUMENT_NOT_A_CANDIDATE`,
which governs the very leaf this gate reuses. A "the refuter flips picks" read
is **not** a claim that the flips are good; §6.2 and §9 are explicit that
pricing is a separate, unfunded stage.

---

## §1 THE MECHANISM, AND THE ONE OBJECT IT CHANGES

The deployed tie arbiter (`carc_core::tiearb::arbitrate`, shipped, +3.0700
pts/game at n=800 deck-paired, z +4.445 —
[`../tiearb2_stage2_20260817/READOUT.md`](../tiearb2_stage2_20260817/READOUT.md))
prices tied root candidates by `B` CRN determinizations, one `tier1-greedy`
playout per `(world, arm)`, mean margin from the acting seat. **Both seats in
that playout run the same policy.** The continuation is symmetric.

CL-083's amended headline clause (red-team crack A, the policy-conditionality
scope amendment) says the champion's continuation futures price defense and
steering value at ≈ 0 *because the continuation is the champion itself*. OM-M1
relocates the asymmetry into the arbiter's rollouts: a **refuter leg** in which
the OPPONENT seat plays an exploit-expressing continuation, so a tied candidate
that is refutable by an invading opponent scores lower.

**Why this dodges the CL-082 trap (−176 elo, asymmetric leaf).** CL-082 made the
*champion's own leaf* asymmetric — it changed what the agent believes a position
is worth, in leaf units, and shipped that belief into play. OM-M1 changes the
**rollout continuation** and reads its result in **true terminal game points**
(`scores[seat] − scores[opp]` at a terminal state; `tier1_playout`). The
champion's leaf, its search, its priors and its value scale are untouched. The
asymmetry lives entirely inside a simulation whose output is a margin, not a
belief. This is also why S1 option (ii)'s backup-symmetry break does not apply:
no backup is modified.

**The lever is not in `docs/LEVER_INDEX.md`.** Grepped `refuter`, `asymmetr`,
`opponent-model`, `arbiter` (2026-08-30). The adjacent rows are: the CLOSED
symmetric arbiter-upgrade row (`tie-arbiter selection-world widening (B > 16)`,
F = 0.811), the NEVER-TRIED `learned tie-breaker net`, the GATE-LIVE `C1`
contested-claim pricing row, and the DECLINED `asymmetric opponent cap` (a leaf
knob, not a continuation). None of them replaces the rollout continuation. A
row for OM-M1 is added by the close-out of this gate whichever way it reads.

---

## §2 THE BANKED CONSTANTS THIS PREREG IS BUILT ON

Every number below is read off a banked artifact BEFORE the gate ran. They are
the inputs to §5's bar and §8's cost, and they are frozen here so a later reader
can check the bar was not reverse-engineered from a result.

| symbol | value | source |
|---|---|---|
| `Ā` — mean arms per fired ply | **3.0022** | `../tiearb2_20260816/corpus/positions/POSITIONS_PLAN.json::mean_arms` |
| `G_arb` — deployed ARB−RND transfer | **+3.0700 pts/game** (z +4.445, n=800 deck-paired) | [`../tiearb2_stage2_20260817/READOUT.md`](../tiearb2_stage2_20260817/READOUT.md) |
| `c_tier1_rust` @ W=30 | **0.17823232 worker-s/playout** | [`../arb_costopt_prep/PREREG.md`](../arb_costopt_prep/PREREG.md) (`COST_REMEASURE.json`, 240 records / 15,360 playouts, G-BITEXACT PASS) |
| `c_tier1_rust` @ W=1 | **0.09376926 worker-s/playout** | same |
| CL-083 falsifier bar | **≥ 2 pts/game** vs a validated exploit-expressing opponent | `governance/CLAIM_REGISTRY.csv` CL-083 |

⚠️ **`F` — the fired-plies-per-game rate — is deliberately NOT in that table,
and the correction matters.** The `22.96 fired tile plies/game` figure carried
by the tiearb plans is the **E4 stratum**: 597 tied plies over 26 phone games
(`tiletie_pricing_20260812/DESIGN.md:792`, quoted verbatim in
[`../tiearb_widening_20260817/PLAN_eps_near_ties.md`](../tiearb_widening_20260817/PLAN_eps_near_ties.md) §1).
It is **not** this gate's population. The banked per-ply census for `champ449`
itself reads **45.26 exact-tied tile plies/game** (20,322 tie_exact / 31,827
TILE rows over 449 games,
`../tiearb_widening_20260817/census/tile_gap_rows.jsonl`), and this
instrument's own replay of the DEPLOYED trigger reads **37.0 fired plies/game**
(the difference being the tie sets that dedupe to a single arm). Carrying 22.96
into the bar would have been off by ~2×. See §5 for why it does not matter.

Derived once, here, and never re-derived downstream:

**The surface's own exchange rate.** `RND` draws uniformly among the `Ā` arms,
`ARB` takes the argmax, so they differ at

> **`P` = 1 − 1/Ā = 1 − 1/3.0022 = 0.6669** of fired plies,

and the measured +3.0700 pts/game buys exactly that many changed picks. So
points per changed tied-arm pick is `R_x = G_arb / (F × P)`. `R_x` is measured
**on this exact surface, in-family, judge-free** (game outcomes, not an EV-loss
judge — F4's family-relativity lesson does not bite). At the walled corpora's
own `F = 45.26` it is **0.1017 pts/changed pick**; at the E4 stratum's 22.96 it
is 0.2005. **§5 shows the choice cannot affect the bar.**

---

## §3 THE POPULATION — WHICH BANKED FIRED-PLY SOURCE, AND WHY

**Chosen: the 1,299-game `walled` champion-selfplay root-replay corpora,
POOLED.**

| label | file | games | tracked? |
|---|---|---:|---|
| `champ449` | `measurement/champ_action_logs/champ_games.jsonl` | 449 | yes |
| `tiearb2_850` | `measurement/tiearb2_20260816/corpus/champ_games_tiearb2.jsonl` | 850 | **no — on disk in the main tree, untracked** |

Each record carries `(game_id, deck_seed, actions, n_plies)`, which is the
**lossless** replay key: `tier1_root(deck_seed, actions[:ply])` reconstructs any
ply of any game bit-exactly. That is the whole requirement — the instrument
re-derives the deployed trigger and the deployed arm set from the *position*
(§4.1), so the corpus need only supply positions.

Alternatives considered and rejected:

- **`/mnt/c/carc-shared/phasegate_a1/{ARB_FULL,ARB_EARLY_*,ARB_FULL_EXT_*}`**
  (803 files/cell, the A1/A2 phase-gate archives). **Rejected: no per-ply
  record.** Each file is one *game-level* summary — `cand_tiearb`, `moves`,
  `score_p0/1`, timings. The arbiter's fires are counted, not located; there is
  no `actions` list and no fired-ply index, so nothing can be replayed without
  re-running the games. Verified by reading the record schema, not assumed.
- **`/mnt/c/carc-shared/tiearb_widening_20260817_b64_cell`** (the B=64 widening
  cell) — same shape, same defect, and additionally a band that has already
  influenced a decision.
- **`../tiearb_widening_20260817/census/tile_gap_rows.jsonl`** (31,827 TILE rows
  over the same 1,299 games). Has `deck_seed`, `ply`, `seat`, `tie_exact`,
  `tie_size_exact`, `gap` — the richest *fire index* in the tree — but **no
  action prefix**, so it cannot be replayed standalone. It is used here as a
  **cross-check** (§7 `G-FIRE`), not as the source.
- **`../tiearb2_20260816/positions_chunk*/`** (2,703 position records, WITH
  `actions`). Rejected as the *primary*: they are the Stage-1 **pairs**
  instrument — `ARMS.json` carries exactly `[pick_a, pick_b]` per rid, a
   2-arm capped/deduped draw over a different population than the deployed
  `J ≤ 4` arm set, and the set is strata-sampled and partly BURNED
  (`EXCLUDE_RIDS_*`). Re-using a spent selection corpus as a fresh population is
  the exact CL-084 hazard this gate is supposed to respect.
- **`measurement/e4_games/`** (E4 phone archives). Rejected: n ≈ 50, `fixed_v1`
  rules epoch, and an owner opponent — a different position distribution, and
  the anchor is nonstationary (memory `reference_android_app`).

**Stated limitation, on the record.** Both corpora are `walled`-profile
champion self-play generated with the arbiter itself OFF (they are the corpora
the arbiter round *mined*), and `champ449` is `k4×688`, shallower than today's
champion. The gate therefore measures expression on the champion's own
**position distribution**, not on the distribution the deployed arbiter induces.
This is accepted: the question is whether a refuter continuation re-ranks
leaf-tied arms *at all*, which is a property of the position and the arbiter, and
the alternative (generating fresh arbiter-on games) costs games this gate is
defined to spend zero of. The corpus axis is reported split (`champ449` vs
`tiearb2_850`) and never silently pooled — **adjudication is on the POOLED row**,
the split is diagnostic only (the widening census's house rule for this exact
pair).

**Clustering.** At most **ONE fired ply per game** enters the sample, drawn by a
seeded uniform choice among that game's fired plies
(`sha256("omm1-sample-v1"|deck_seed)`). Fired plies within a game share a board
and are strongly dependent; one-per-game makes the `n` clusters independent and
lets the flip rate carry an honest binomial `se`. Target **n = 1200** of the
≤ 1,299 available (games with zero fired tile plies are skipped and counted).

---

## §4 THE INSTRUMENT

### 4.1 The trigger and the arm set are the DEPLOYED ones, re-derived

At each candidate ply the harness calls the shipped
`carc_core::tiearb::arbitrate_decision` path, not a re-implementation: phase ==
TILES, acting seat, `n_legal ≥ 2`, `chain_values` + `detect_tie(eps = 0.0)`
(exact f64 equality), `build_arms(J = 4, champ_pick)` with
`salt = TIEARB_SALT_OF_RECORD = "tiearb2-deploy-v1"`, and the "fewer than 2 arms
after dedupe ⇒ NOT fired" rule. `champ_pick` is the corpus's own
`actions[ply]` — the action the champion actually played, which is by
construction its `pooled_q_argmax` pick at that ply.

### 4.2 The three (four) legs, on ONE set of CRN worlds

`world_seed(j) = seed_i64(salt | state_digest | ply | j)` — **independent of
`B`**, which is load-bearing twice over: (a) all legs share the identical `B`
determinizations, so every contrast below is fully CRN-paired at world level,
and (b) the deployed **`B = 16`** arbitration is exactly the first 16 worlds of
this `B = 64` run, recoverable for free and bit-exactly.

| leg | opponent-seat policy in the playout | `playout_seed(j)` |
|---|---|---|
| **S** — symmetric | `tier1-greedy` (unchanged) | `seed_i64(salt\|digest\|ply\|j\|"playout")` — **the deployed seed** |
| **P** — placebo | `tier1-greedy` (unchanged) | `seed_i64(salt\|digest\|ply\|j\|"playout"\|"omm1-leg2")` |
| **R_ref** — refuter, of record | shape-B invader leaf, `invasion_alpha = 0.09`, `invasion_alpha_cap = 11.0` | same as **P** |
| **R_max** — refuter, ceiling | `invasion_alpha = 1.0`, `invasion_alpha_cap = 11.0`, `invasion_beta = 1.0` | same as **P** |

**Why the placebo leg exists, and why it is the null of record.** A two-leg
score computed from 32 symmetric + 32 refuter worlds differs from the pure
64-world symmetric score for TWO reasons: the refuter changed the continuations,
and half the worlds were re-run under a different RNG stream. The second reason
alone flips picks — arm means over 64 worlds on exact-leaf-tied arms are close,
and the banked per-world spread is large (`within_se` 0.5–6.0 points/world on
the tiletie records). **P** is the same policy class, the same cost, the same
CRN worlds, differing from **S** by nothing but the tie-break stream, so
`p_flip(P)` is exactly the flip rate attributable to rollout stochasticity at
this world count. **R** shares P's `playout_seed`, so `R − P` isolates the
policy change alone. Reporting `p_flip(R)` without `p_flip(P)` would be a
mis-read, and this prereg forbids it.

### 4.3 The refuter's provenance — a BUILT invader, not a new one

`R_ref` is **the shape-B invader opponent of record**: `invasion_alpha = 0.09`
at `invasion_alpha_cap = 11.0`, the exact opponent
[`../invasion_screen_r3_prep/DESIGN.md`](../invasion_screen_r3_prep/DESIGN.md)
§ (lines 197–226) runs as the C-arm ENV opponent
(`CARCASSONNE_INVASION_ALPHA=0.09`, `CARCASSONNE_INVASION_ALPHA_CAP=11.0`,
resolved leaf `42adadc988784b44`). Round 2 demoted shape B as a *candidate* and
round 3 kept it as an *instrument* — `SHAPE_B_IS_AN_INSTRUMENT_NOT_A_CANDIDATE`
— which is precisely the status this gate needs. The rust term is
`carc_core::leaf::invasion::shape_b_term`, spec
[`../invasion_term_build/SHAPES.md`](../invasion_term_build/SHAPES.md): the
non-negative stub-merge potential over ordered pairs `(S, L)` of same-family
components where `S` is a player-held stub of `≤ 2` tiles and `L` is an
opponent-held majority component it can join. That is the literal
SETUP → FOOTHOLD → MERGE plan the Stage-A census defines as a deliberate
invasion (`../e4_exploit_grading_20260825/stage_a_census.py` §H2), i.e. the
owner's own measured farm-steal mechanism.

**Why `R_max` too.** A kill-gate must be run at maximum expression: if a
maximally-invasive opponent does not re-rank the tied arms, the mechanism is
dead regardless of dose. `R_max` adds shape A at `invasion_beta = 1.0`, whose
principled meaning is exactly *"a contestable component is worth nothing in the
differential"* (`invasion::shape_a_term` docs), and lifts alpha to 1.0 so the
stub-merge potential reaches the cap in points rather than in hundredths of a
point. **`R_max` adjudicates the kill; `R_ref` adjudicates deployability**
(§6.4). Neither is proposed for production, ever.

⚠️ **The rollout policy is NOT the champion leaf.** `tier1::RuleBasedPlayer`
ranks candidates by `candidate_leaf` = the int64 **base** terminal-score
differential (`flat_base_score`), not by the v2.9 `LeafConfig` leaf. The refuter
scorer therefore adds `alpha·T_B (+ beta·T_A)` to that int64 base **in f64**,
and argmaxes in f64 with the identical exact-`==` tie set + `rng.randbelow`
draw. Rounding the invasion bonus to an integer would silently swallow the whole
`R_ref` dose (`alpha·T_B ≤ 0.99` at cap 11.0), which would make a kill
uninterpretable. The f64 path is instrument-only and is reached **only** on the
refuter seat of an armed leg; §7 `G-INERT` pins that.

### 4.4 The statistics, defined before any leg ran

Per fired ply `i`, per leg `L ∈ {S, P, R_ref, R_max}`, the instrument stores the
raw `B × arms` margin matrix `M_L[j][a]` (worlds × arms) and nothing else. All
arithmetic below is Python-side, in `analyze_gate.py`, from those matrices.

- `mean_L[a] = (1/64) Σ_j M_L[j][a]`; `argmax_L` = strict-`>` argmax over the
  arm order (ties keep the earliest arm — the incumbent leaf tie-break, exactly
  `arbitrate_core`'s rule).
- **The symmetric pick** `A_sym = argmax_S` over all 64 worlds.
- **The two-leg pick** for refuter `R`:
  `mean_2R[a] = ½·(1/32)Σ_{j<32} M_S[j][a] + ½·(1/32)Σ_{j≥32} M_R[j][a]`,
  `A_2R = argmax(mean_2R)`. This is the **iso-cost deployable object** the menu
  contract names ("split B=64 into a symmetric leg + a refuter leg").
- **The two-leg placebo pick** `A_2P`, identically with `P` in place of `R`.
- `FLIP_R(i) = 1[A_2R ≠ A_sym]`, `FLIP_P(i) = 1[A_2P ≠ A_sym]`.
- **`p_flip(L) = (1/n) Σ_i FLIP_L(i)`.**
- ⭐ **`Δ_flip(R) = p_flip(R) − p_flip(P)`**, paired per ply.
  `se(Δ) = sqrt(b + c)/n` where `b` = #{FLIP_R ∧ ¬FLIP_P}, `c` = #{¬FLIP_R ∧ FLIP_P}
  (McNemar's paired-discordance se).
- **Swap replication** `ρ`: recompute with the leg halves exchanged
  (`worlds ≥ 32` symmetric, `worlds < 32` refuter) — free, same matrices — and
  let `ρ = ` the fraction of primary-flipped plies that flip again under the
  swap AND to the SAME arm.

Reported alongside, never as a branch input: `p_flip` at `B = 16` (worlds 0–15
symmetric vs 8+8 split), the pure-`R` 64-world flip rate (`argmax_R ≠ argmax_S`,
the expression ceiling), the arm-count and `phase_bucket` cuts, and the
per-corpus split.

---

## §5 ⭐ THE BAR — SET AT THE EFFECT SIZE THE DECISION CARES ABOUT

**Adopted 2026-08-30 house rule: a bar is written from "what effect would change
the decision", NEVER at 2σ̂ of the instrument.** The derivation:

1. Stage 2 (pricing) and, beyond it, CL-083's registered falsifier cell cost
   games. A survivor must eventually clear **≥ 2 pts/game** against a validated
   exploit-expressing opponent.
2. Set the stage-1 target at **1.0 pts/game** — HALF the falsifier bar. A
   mechanism whose optimistic self-play ceiling is below 1.0 cannot plausibly
   reach 2.0 in the falsifier cell, and 1.0 is already generous by 2×.
3. Convert pts/game to a flip rate at the surface's own measured exchange rate
   (§2): `pts/game = F × Δ_flip × R_x`.
4. ⭐ **`F` cancels.** `R_x` is itself `G_arb / (F × P)`, so
   `F × R_x = G_arb / P` and the fire rate leaves the expression entirely:

   > **`Δ_flip ≥ target × P / G_arb = 1.0 × 0.6669 / 3.0700 = 0.21723`.**

   This is why the `22.96`-vs-`45.26` correction in §2 does not move the bar: a
   ~2× error in `F` would have propagated into `R_x` in the opposite direction
   and cancelled itself. Pinned by
   `tests/test_omm1_refuter_gate.py::test_the_bar_does_not_depend_on_the_fire_rate`,
   which asserts the equality at `F ∈ {22.96, 37.0, 45.26, 100.0}`.

   ⚠️ **What does NOT cancel** — and is stated rather than hidden: the flip
   rate is measured on the walled champion-selfplay corpora (§3), while `G_arb`
   was measured on the Phase-B game cell's population. The conversion assumes
   the flip RATE transfers between them. It is the same trigger and the same
   arbiter, but it is an assumption, and a stage-2 pricing (§9) measures the
   value directly rather than converting.

> ### 🔒 **BAR: `Δ_flip(R_max) ≥ 0.22` on the POOLED row.**
> ### 🔒 **CONJUNCT: `ρ ≥ 0.50`.**

**The bar is deliberately conservative in the mechanism's favour.** `R_x` was
measured on ARB-vs-**RND** picks, i.e. on swaps between the argmax arm and a
uniformly-drawn arm. A refuter flip moves between two arms that are BOTH already
near the symmetric top, so its per-flip value is very likely **smaller** than
0.2005 — using `R_x` therefore *overstates* what a given flip rate can buy, which
means the bar is easier to clear than the truth warrants. If it still fails, the
kill is strong.

**Compliance statement (house rule, explicit).** At n = 1200 with a plausible
discordance `b + c ≈ 300`, `se(Δ) ≈ 0.017`, so `2σ̂ ≈ 0.035`. **The bar 0.22 is
6.3× the instrument's 2σ̂ and was derived without reference to it.** The null's
read distribution is therefore stated up front: under a true `Δ = 0`, `DEAD`
fires with probability > 0.999 and the `UNRESOLVED` band is unreachable — this
round discharges something whichever way it lands, which is the exact failure
(phasegate A1, the FPU `BAR_M`) the house rule was written to stop.

**Power at the bar.** `n = 1200` was chosen so the bar is *decidable*, not so it
is *2σ*: at `Δ_true = 0.22` the read is `EXPRESSES` ≈ 50 % of the time by
construction (`Δ̂ ≥ bar` is a point-estimate test), and `DEAD` essentially never
(it needs `Δ̂ < 0.185`). The asymmetry is intended — this is a kill-gate, and its
job is to make DEAD trustworthy, not to make EXPRESSES certain.

---

## §6 THE READ RULE — BRANCHES, FROZEN

Adjudicate in this order on the **POOLED** row, `R_max` first. `Δ̂` and `se`
always mean `Δ_flip` and its McNemar se from §4.4.

### 6.1 `OM-DEAD` — `Δ̂(R_max) + 2·se < 0.22`
The mechanism is **dead**. A maximally-invasive refuter continuation, run on the
same CRN worlds at the deployable split, does not re-rank leaf-tied root arms
beyond what re-seeding the tie-break RNG does. **Zero games spent.** Close-out:
`LEVER_INDEX` row (refuter-leg arbitration → MEASURED AND CLOSED), roadmap row,
DECISIONS line, `CLAIM_REGISTRY` note against CL-083's mechanism menu. **No
`results.csv` row is owed** — this is a 0-game oracle-class gate, the
`microgates_20260828` precedent.

### 6.2 `OM-EXPRESSES` — `Δ̂(R_max) ≥ 0.22` **and** `ρ ≥ 0.50`
The refuter leg re-ranks, reproducibly. **This is not a value claim.** It
activates §9's stage-2 prereg, which is **unfunded** and must be adjudicated by
the owner before one game is bought. Nothing is adopted, nothing is measured
against a band, no `results.csv` row.

### 6.3 `OM-UNRESOLVED` — `Δ̂(R_max) < 0.22 ≤ Δ̂(R_max) + 2·se`
The narrow band (`Δ̂ ∈ [0.185, 0.22)` at the anticipated se). **Not a licence to
fund.** ONE extension is pre-authorised: raise the sample to two fired plies per
game (`n ≈ 2400`, seeded second draw, same corpora, same legs), which halves
`se`, and re-read §6.1/§6.2 unchanged. If it is still `UNRESOLVED` after the
extension, the read is **DEAD by default** and §6.1's close-out runs.

### 6.4 `OM-DOSE-ONLY` — a MODIFIER on 6.2, not a branch
If `OM-EXPRESSES` fires on `R_max` but `Δ̂(R_ref) + 2·se < 0.22`, the expression
exists only ABOVE the built instrument's dose. Stage 2 is **not** funded on that
reading without a separate, pre-registered dose argument: `R_max` is a ceiling
construct (`beta = 1.0` = "a contestable component is worth nothing"), and a
mechanism that needs it is not the shape-B invader of record. Record the pair
`(Δ̂(R_max), Δ̂(R_ref))` in the readout either way.

### 6.5 `OM-VOID`
Any guard in §7 fails. No branch is read; fix and re-run. A voided run's numbers
are quarantined in `VOID_*.json` and never enter a readout table.

---

## §7 GUARDS — every one is a pre-launch or in-run ABORT

| id | statement | why |
|---|---|---|
| **`G-BITEXACT`** ⭐ | For every ply in the sample, leg **S**'s 64-world `means` vector is **bit-identical** (`f64::to_bits`) to the shipped `carc_core::tiearb::arbitrate(...)` at `B = 64`, and its `argmax_arm` is identical. Enforced in-run per ply, and pinned by a rust unit test. | The FPU precedent. If the instrument's own symmetric leg is not the deployed arbiter to the bit, the flip rate is measuring the harness, not the mechanism. |
| **`G-INERT`** ⭐ | With every invasion weight set to `0.0`, leg **R**'s margin matrix is **bit-identical** to leg **P**'s, and a `tier1_playout` with `refuter = None` is bit-identical to the pre-change `tier1_playout`. Rust unit tests. | The disarmed path must be the old code byte for byte, not merely equal — the early-branch discipline `leaf::leaf_terms_with` already uses for every optional term. |
| **`G-CRN`** | The `world_seed(j)` list is identical across all four legs at every ply (asserted, not assumed), and `R` and `P` share `playout_seed(j)`. | `R − P` is only the policy delta if nothing else differs. |
| **`G-COMPLETE`** | `worlds_completed == B` on every leg at every ply. A `tier1_playout` error voids the WHOLE ply (all four legs), which is recorded and excluded, never averaged over survivors. | `arbitrate_core`'s own whole-ply-revert contract; a partial world set breaks the CRN pairing that the entire comparison rests on. |
| **`G-FIRE`** ⭐ | TWO halves, both must hold. **(a) EXACT, decisive:** every `(deck_seed, ply)` the replay marks FIRED must carry `tie_exact` in `../tiearb_widening_20260817/census/tile_gap_rows.jsonl`, at **≥ 0.99 agreement** over the joined keys. **(b) RATE, advisory:** `fired/game ÷ 45.26` (the same census's banked exact-tied rate) lands in **[0.60, 1.00]** — the deployed trigger is a strict subset of the exact-tie plies because some tie sets dedupe to one arm. | Proves the replay reproduces the DEPLOYED trigger. ⚠️ Half (a) replaced an earlier rate-bracket around 22.96, which was the E4 stratum's constant and would have failed a correct replay by ~2× (§2). A join is exact; a rate bracket cannot be. **Measured on a 120-game slice 2026-08-30: fraction 0.818, join agreement 0.9955 (20/4,443) — PASS, with the residual recorded in [`DEVIATIONS.md`](DEVIATIONS.md) `OM-D1`.** |
| **`G-LEAF`** | The resolved champion leaf hashes to **`a36d2e15a3b3d71d`** (`champion_factory.verify_leaf` + `resolved_manifest`), and the refuter leaf differs from it in exactly the invasion fields §4.2 names. | The house R1/R7 provenance guard. |
| **`G-SALT`** | `salt == "tiearb2-deploy-v1"`, `J == 4`, `eps == 0.0`, `max_plies == 400`. Stamped in `manifest.json`. | Any other value is a different experiment (`TIEARB_SALT_OF_RECORD`'s own doc). |
| **`G-TENANCY`** | A full-args process census (`ps -eo args`, never `-C python`) before launch and a per-process sampler during. | Memory `feedback_no_agent_compute_beside_eval` — a single niced DRAM-churner inflated a saturated eval ~1.8×. Wall-clock here is only a cost figure, not a result, so a co-tenant voids the COST line and nothing else; it is still recorded. |

---

## §8 COMPUTE COST

Per fired ply: `4 legs × 64 worlds × Ā(3.0022) arms = 768.6` `tier1-greedy`
playouts. (`n` is the SAMPLE, one ply per game — the corpus's total fire rate
does not enter the cost.)

| | worker-s / ply | n = 1200 | wall |
|---|---:|---:|---|
| @ `c` = 0.17823 (W = 30) | 137.0 | **45.7 worker-h** | **≈ 1.52 h** at W = 30 |
| @ `c` = 0.09377 (W = 1) | 72.1 | 24.0 worker-h | — |
| at W = 14 (a shared box) | 137.0 | 45.7 worker-h | ≈ 3.26 h |

Plus the corpus build (§3): leaf-only replay of 1,299 games, no playouts — the
widening census did the same 1,299 games in **52.2 s at W = 30**, so **≈ 1
minute**.

The `OM-UNRESOLVED` extension (§6.3) doubles the rollout figure once: `+45.7`
worker-h. Nothing else in this prereg buys compute, and **no games are played on
any branch**.

⚠️ **Not launchable while the S1 G3 round holds both boxes.** This gate is a
DRAM-bound tier1 rollout campaign and the memory
`feedback_no_agent_compute_beside_eval` is unambiguous about co-tenancy on a
saturated eval box. The instrument is frozen and tested; the run waits for a
quiet window and an owner box assignment.

### 8.1 MEASURED cost (post-freeze addendum, 2026-08-30 20:35 EDT)

⚠️ **The table above is ~5.4× PESSIMISTIC.** It was built from
`c_tier1_rust = 0.17823232` worker-s/playout, which
[`../arb_costopt_prep/`](../arb_costopt_prep/PREREG.md) measured on the
**pre-swap** playout engine. The `flat_base_score` tier1 swap has since merged
(roadmap 2026-08-29: "playouts realized 10.9× cheaper post-swap"), so the
projection was against an engine that no longer exists.

Measured on this instrument, 16 fired plies at `B = 64`, four legs, release
wheel `f9e8813b`, W=16 (`LEGS`'s sibling `BENCH/`):

| | measured |
|---|---:|
| worker-s per playout | **0.0175** |
| playouts per ply (4 legs, `Ā` 3.25 here) | 832 (+208 when the `G-BITEXACT` re-derivation runs) |
| worker-s per ply | **14.59** (mean over records, not the wall clock — the order-statistic trap) |
| ⇒ n = 1,299 at W=30 | **≈ 20 min**, not 1.5 h |

Two consequences, both taken: the run uses the FULL frame (`n = 1,299`, every
game contributes its one sampled ply — no game had zero fires), and
`G-BITEXACT` runs at **stride 1, i.e. on every ply**, rather than the sampled
subset the cost table would have forced. The `--bitexact-stride` knob remains
for a future tighter window; a skipped check reports `null` and is excluded
from the guard's denominator, never counted as a pass.

**This changes no statistic and no bar.** Cost is not an input to §5 or §6.

---

## §9 STAGE 2 — PREREG SKELETON (⛔ UNFUNDED, DESIGN ONLY)

Activated only by `OM-EXPRESSES` (§6.2), and only by an owner funding decision.
Written now so the stage-1 read cannot be followed by an improvised stage 2.

**The estimand.** Not "do the flips happen" (stage 1) but "are the flipped picks
WORTH anything", in true game points, without the winner's curse.

**S2.1 — CL-084 independent-world selection/pricing split (mandatory).**
Partition the CRN worlds into disjoint halves fixed before any read:
`SELECT = {j < 32}`, `PRICE = {j ≥ 32}`.
- SELECTION uses `SELECT` only: `A_sym^sel = argmax` of leg S over `SELECT`;
  `A_ref^sel = argmax` of the two-leg score over `SELECT` (16 S-worlds +
  16 R-worlds, so selection never touches a pricing world).
- PRICING uses `PRICE` only, and is run at a **fresh, larger** world budget
  drawn from the same seed family (`j ∈ [64, 64 + B_price)`) so the pricing
  estimate is not a re-read of a selection world at all: the statistic is
  `δ_i = mean_{PRICE} M_S[·][A_ref^sel] − mean_{PRICE} M_S[·][A_sym^sel]`,
  i.e. the value of the refuter's re-ranking measured under the **symmetric**
  continuation — the champion's own futures, which is what the deployed agent
  will actually experience.
- Per-game aggregate: `pts/game = F × p_flip × mean_i δ_i`, with `se` from the
  per-ply `δ_i` clustered one-per-game.
- **Bar: `pts/game ≥ +1.0` with the 2σ LOWER bound above 0.** Same 1.0 as §5,
  now measured rather than converted through `R_x`. A negative point estimate
  kills OM-M1 outright (the refuter systematically picks worse arms).

**S2.2 — CL-085 out-of-family corroboration, BEFORE any game cell.**
S2.1 selects with tier1-greedy margins and prices with tier1-greedy margins —
ONE family. F4's lesson (a +1.49 pts/ply ceiling that read −0.64, z −3.8, under
an out-of-family judge on the same CRN worlds) forbids funding on that. Repeat
S2.1's pricing under a second continuation family on the identical selected
plies and identical `PRICE` worlds: the **rust exact endgame solver**
(`carc_core::endgame`) on the late bucket where it is affordable, and
`clair-puct` elsewhere. Both must agree in SIGN with S2.1. Cheap (~laptop-hours)
and it runs first.

**S2.3 — only then, the game cell.** CL-083's own registered falsifier: ≥ 2
pts/game against a validated exploit-expressing opponent WITHOUT regressing
versus champion + Carcasum. Within-band deck-paired, band claimed in
`governance/BAND_REGISTRY.csv`, `n` sized to the effect S2.1 measured — not to
2σ̂ of the instrument.

**What stage 2 may NOT do:** argmax over refuter doses (post-hoc dose search on
the same plies is the CL-084 hazard in its purest form — the dose ladder must be
pre-registered and priced on independent worlds), pool across bands, or promote
any invasion weight into a leaf. The refuter stays an instrument.

---

## §10 ARTIFACTS

| file | what |
|---|---|
| `PREREG.md` | this document — frozen before any statistic |
| `scripts/omm1/build_fired_plies.py` | corpus replay → `FIRED_PLIES.jsonl` (+ `G-FIRE`) |
| `scripts/omm1/run_gate.py` | the four legs per ply → `LEGS/*.jsonl` raw margin matrices (+ `G-BITEXACT`, `G-CRN`, `G-COMPLETE`) |
| `scripts/omm1/analyze_gate.py` | §4.4 arithmetic → `READOUT.json` / `READOUT.md`, branch per §6 |
| `rust/carc/carc-core/src/tiearb.rs` | `arbitrate_legs` — the multi-leg arbiter |
| `rust/carc/carc-core/src/tier1.rs` | `RefuterConfig` + `tier1_playout_with` — the seat-gated refuter scorer |
| `rust/carc/carc-py/src/lib.rs` | `tiearb_arbitrate_legs` binding |
| `tests/test_omm1_refuter_gate.py` | python-side contract tests |
| rust `#[cfg(test)]` in `tiearb.rs` / `tier1.rs` | `G-BITEXACT` and `G-INERT` golden gates |
