# Farm-war discriminator — PRE-REGISTRATION

**Status: PRE-REGISTERED 2026-08-05 late night, FUNDED by Joshua ("go"). Written and committed
BEFORE any cell runs.** Design rationale + costing: [FARMWAR_DISCRIMINATOR_SCOPE.md](FARMWAR_DISCRIMINATOR_SCOPE.md).
Motivating evidence: readout §6c (grade-vs-outcome inversion) and the E4 farm ledger
(Joshua 6-for-6; champion 11.0 farm pts/seat vs him against 20.5 in its own corpus).

## The question

When Joshua's contested-farm moves grade as blunders under the champion's own leaf, **are they
actually worse, or does the leaf mis-price farm wars?** The EV-loss grader cannot answer this:
it prices moves with the leaf under suspicion. This scores the same moves against an
**independent** reference.

## Method

For each selected ply: replay the position (each game under **its own** rules profile via the
corrected resolver), take the action Joshua **played** and the action the champion's search
**preferred** (`action_played` / `action_best`, already in the EV-loss artifacts), and score
both continuations over **M = 32 CRN-paired deck completions** (identical world seeds for both
arms — `oracle_score_pilot.world_seeds` / `position_delta`). Statistic per ply:

**Δ = V(played) − V(best), in FINAL-SCORE POINTS, Joshua's seat.** Positive ⇒ his move earned
more than the champion's preferred move.

## Stratification — FIXED NOW, before any result

**Primary stratifier `farm_driven`** (pre-registered, in priority order — use the first that
is cleanly computable; record which fired in the manifest):

1. **Leaf-term rule.** Decompose the leaf value of both successor states into farm and
   non-farm contributions (the knockout machinery already separates farm terms —
   `F7B_GATE_WIRING_farmbaseoff/farmgrowthoff`). A ply is `farm_driven` iff the **farm-term
   difference accounts for ≥50% of the total leaf-value difference** between the two
   successors. This targets exactly the plies where the champion's preference *is* a farm
   judgment.
2. **Fallback (only if terms are not cleanly separable — say so in the manifest).** A ply is
   `farm_driven` iff either action places a **farmer**, or either action is a tile placement
   that merges/extends a field region already carrying a farmer of either player.

**Strata:**
- **FARM** — all `farm_driven` human plies with bucket ∈ {inaccuracy, blunder} across the six
  graded games (expected ~20–25: g5's 12 blunders, g6 ply 44, g3's 9, plus g1/g2).
- **CONTROL** — non-`farm_driven` human plies of the same buckets, **matched on ΔQ magnitude**
  (nearest-neighbour on ΔQ, no replacement; expected ~15). The control is what separates
  "the leaf mis-prices FARM WARS" from "the leaf mis-prices HIS STYLE generally".

If either stratum comes in under **n = 10**, the run is **INCONCLUSIVE by construction** —
report and stop, do not reinterpret.

## Judges

- **Primary: in-family** (clair-PUCT continuation over the champion's own leaf), the
  `oracle_score_pilot` default. ⚠️ It shares the leaf under test, so it is biased **toward the
  champion's picks**: a POSITIVE result through it is therefore **conservative**; a null
  through it is **uninformative** about H1.
- **Secondary: out-of-family sign check** — Tier-1 greedy (`--oracle-policy tier1-greedy`),
  the 2026-07-28 discriminator precedent. ⚠️ **1.83× noisier, no curve125 — SIGN ONLY, never
  compare its magnitude to the primary's.**

## Decision map (branch precedence 1 → 2 → 3 → 4; first match wins)

1. **FARM mean Δ > 0 with |z| ≥ 2, AND CONTROL CI covers 0 or CONTROL mean < ½ FARM mean**
   ⇒ **H1 FIRES: the leaf mis-prices contested farm wars.** A localized, human-found defect in
   the champion's evaluation. Consequences: his g5 "12 blunders" are re-labelled; the farm
   terms become a C5/C7 re-sweep candidate; a claim id is minted. **Does NOT license "the
   champion is weak"** — it is one term, and the during-play ledger says the rest is intact.
2. **FARM mean ≤ 0 with |z| ≥ 2** ⇒ **H2: the champion's picks really are better.** His moves
   are genuinely worse; the wins were deck-assisted; the ΔQ readouts stand as written.
3. **BOTH strata positive with |z| ≥ 2** ⇒ **H3: general same-family self-preference in the
   grader**, larger than the oracle pilot's +0.74. A statement about the instrument; gates
   every future grader claim, including tonight's.
4. **Otherwise** ⇒ **INCONCLUSIVE.** Report the estimate and its CI; do not promote. Default
   next step is *more E4 games*, not more compute on n=6.

**Two-sided z throughout** (a negative result is informative here — it vindicates the leaf).
Cluster-robust on **root position** if any game contributes multiple plies from the same root
(the pilot's design effect lesson: 628 records spanned only 385 roots).

## Pre-stated threats

1. **Same-family judge** — handled by the conservative-direction argument + the Tier-1 sign
   check. Not eliminated.
2. **Weak continuation** — the judge's continuation is shallower than real play; it is the
   pilot's untouched secondary threat and remains untouched here. It biases toward whichever
   move looks better under shallow play, direction unknown.
3. **n = 6 games, one human.** Every ply comes from one player's games; this measures the leaf
   on *positions his play produces*, not on farm wars in general.
4. **Selection on ΔQ.** Both strata are selected as high-ΔQ plies, i.e. conditioned on the
   champion disagreeing strongly. Regression to the mean pushes Δ toward 0 on re-scoring; this
   makes a positive result harder, not easier.
5. **Mixed rules epochs** (g1/g2 `walled`, g3 `app_aug2`, g4–g6 `fixed_v1`) — each ply is
   replayed under its own profile, but the strata pool across epochs. Report the per-epoch
   split; do not pool if the epochs disagree in sign.

## Cost / ETA

~40 positions × M=32, both judges ⇒ **~1–1.5 h at W16 on the local box** (from the pilot's
measured 100 positions × M=32 in ~81 min). No cloud, no other box. ⚠️ The local box
dirty-crashed 3× on 2026-08-04 — checkpoint per position and support `--resume`.

## Governance

Measurement only. `governance/PRODUCTION.yaml` untouched, no champion change, no promotion on
any branch. A claim id is minted only on branch 1 or 3. Every number ships in a manifest with
the resolved stratifier rule, per-ply records, and the judge configs.
