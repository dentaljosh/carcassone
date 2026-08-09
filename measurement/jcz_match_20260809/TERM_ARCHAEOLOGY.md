# Term archaeology — JCloisterZone `LegacyRanking` vs our champion leaf

> **Status: COMPLETE 2026-08-09. READ-ONLY SOURCE ARCHAEOLOGY — no code changed, no measurement run,
> no term adopted.** This is step 2 ("term archaeology") of the BACKLOG 2026-08-09 entry *"JCZ
> disagreement mining"*; step 1 (behavioural mining) has NOT been run and every steal candidate
> below is **unmeasured**. See [§4 Caveats](#4-caveats--why-reading-a-term-tells-you-nothing-about-its-value)
> before believing any row of §3.
>
> **AGPL rider (from the BACKLOG entry): ideas and measurements are fair game; JCZ code never gets
> copied into our leaf.** Nothing below is a patch; every candidate is described as a *native*
> `LeafConfig` term to be written from scratch.

**Why this exists.** The n=20 smoke ([LEVER_INDEX](../../docs/LEVER_INDEX.md) "external-AI reference
match") came back LEVEL: champion at the deploy budget (k8×1376 = 11008 sims, rust, `fixed_v1` +
`CARCASSONNE_FIX_R9=1`) vs `LegacyAiPlayer` = wr 0.525, deck-paired margin **+4.6 ± 2.2 pts (z 2.07)**,
0 voids, 0 divergences. Their agent is a **one-turn breadth-first enumeration of the acting player's
own action chain, ranked by one static evaluation of the resulting state** — no opponent reply, no
lookahead, ~38 ms/move against our ~1185 ms/move. A tie against that is either (a) our search is
buying almost nothing, or (b) their *evaluator* knows things ours does not. This memo reads their
evaluator to find out which terms could be doing the work.

**Sources.** Their side: the 4.x classes ported onto the 5.x engine in `scripts/jcz_match/java/`
(port note: *"EVERY NUMERIC CONSTANT AND EVERY FORMULA IS BYTE-IDENTICAL TO THE 4.x ORIGINAL … NO
sub-rating was dropped, weakened, or reweighted"*,
[`LegacyRanking.java:40-62`](../../scripts/jcz_match/java/com/jcloisterzone/ai/player/LegacyRanking.java)).
Our side: [`governance/PRODUCTION.yaml`](../../governance/PRODUCTION.yaml) `champion.leaf` =
`v2_9_2_Bmild_cap8_curve125`, leaf hash `a36d2e15a3b3d71d`, implemented on the production flat path
[`src/carcassonne_ai/flat_leaf.py`](../../src/carcassonne_ai/flat_leaf.py) with config schema
[`virtual_score_v2.py`](../../src/carcassonne_ai/virtual_score_v2.py). Term *values*:
[`measurement/leaf_ablation_20260730/ABL_PROGRESS.tsv`](../leaf_ablation_20260730/ABL_PROGRESS.tsv)
+ [MORNING_BRIEF](../leaf_ablation_20260730/MORNING_BRIEF_20260731.md).

---

## 1. Their evaluator, decomposed

`LegacyRanking.apply(state)` is a plain sum of seven sub-ratings
([`LegacyRanking.java:94-147`](../../scripts/jcz_match/java/com/jcloisterzone/ai/player/LegacyRanking.java)),
every one of them antisymmetrised through `ptsforPlayer(p, x) = (p == me ? x : -x)` (`:149-151`).
Units are nominally game points; no tanh, no normalisation, no cap anywhere.

Context computed once per call (`:99-106`):
`numberOfPlayers`, `lastPlaced`, `positionProbability` (see P below), and
**`remainingTurns = ceil(tilePack.totalSize() / numberOfPlayers)`** (`:103`).

| # | sub-rating | what it prices | scope | phase/deck dependence | rough formula | src |
|---|---|---|---|---|---|---|
| P | `getPositionProbability` *(not a term — the shared input)* | for each **empty legal cell**, P(that cell gets filled) | board-wide | **YES — reads the tile pack.** `state.getTilePack().getPatterns()` = the multiset of *remaining* tiles by edge pattern; counts how many still match the cell's edge pattern in any rotation | `matchingTiles = Σ{count : pattern matches any rotation}`; `p = 1 − (1 − 1/nPlayers)^matchingTiles` (0 if none) | `:153-170` |
| 1 | `ratePoints` | already-banked score | own − opp | no | `Σ_p ptsforPlayer(p, score[p])` | `:172-179` |
| 2a | `rateUnfinishedFeatures` — completables | expected points of every incomplete city/road/cloister, upweighted by P(it completes) | **all owners**, own − opp | **YES, via P** (`countCompleteProbability` = Π of `positionProbability` over the feature's open-edge cells; for cloisters over its 8 neighbours) | per feature: `pts = incomplete + prob·0.8·(complete − incomplete)`; **cloisters** `pts = incomplete + prob·0.5·(9 − incomplete)`; snap `prob > 0.85 → 1.0`; credited to every majority owner | `:181-227`, `:266-316` |
| 2b | `rateUnfinishedFeatures` — **stuck-meeple penalty** | a follower parked on a feature unlikely ever to close | own (−) and opp (+), **4:1 asymmetric** | **YES, twice** — gated on `remainingTurns > 7`, and the probability itself is deck-derived | per follower on the feature, by band: `prob < 0.0001 → −12.0 self / +3.0 opp`; `< 0.2 → −3.0 / +0.75`; `< 0.55 → −1.2 / +0.3`; else nothing | `:284-305` |
| 2c | `rateUnfinishedFeatures` — farms | end-of-game field score | own − opp | no | `0.99 × ScoreField(farm, isFinal=true).getFeaturePoints(owner)` (the engine's own final-farm reducer; **note the deliberate 0.99, not 1.0**) | `:318-337` |
| 3 | `rateOpenFeatures` | **meeple lock-up, by feature category, convex in count** | per player, own − opp | no | for each player count `roads/cities/cloisters` among *solely-owned* open completables and `farms` among occupied fields, then subtract the table entry. `OPEN_ROAD = {0,1,2.5,4.5,7.5,10.5,14.5,19,29}`, `OPEN_CITY = {0,0.5,1.5,3,5,8,12,17,27}`, `OPEN_CLOISTER = {0,0,0.4,0.8,1.2,2,4,7,11}`, **`OPEN_FARM = {0,5,10,19,28,37,47,57,67}`** | `:67-74`, `:229-264` |
| 4 | `rateMeeples` | free-meeple supply | own − opp | no | `+0.15` per free `SmallFollower`, `+0.25` per free other follower; **`−4.0` flat if supply is empty** | `:342-361` |
| 5 | `rateBoardShape` | compactness of the last placement | mover-agnostic, always **positive** | no | `0.0001 × |adjacentTiles2(lastPlaced)|` — a tiebreak, four orders of magnitude below everything else | `:377-379` |
| 6 | `rateDragon` | dragon proximity | own − opp | no | **inert in Base+Farmers** (`getDragonDeployment() == null` → 0) | `:363-375` |
| 7 | `rateConnections` | **majority-flip anticipation via a probable future merge** | all affected owners | **YES, via P** — only cells with `positionProbability ≥ 0.55` are considered | for each such cell and each of its 4 sides, take the two same-class features meeting at that corner (`Edge(pos,loc)`, `Edge(pos,loc.rotateCW(90))`); combine their meeple powers; players who *lose* majority in the merged feature are debited, players who *gain* are credited, each at `0.5 · prob · getCompletablePoints(feature)` | `:381-442` |

Ownership/tie semantics live in
[`CompletableRanking`](../../scripts/jcz_match/java/com/jcloisterzone/ai/player/CompletableRanking.java)
(`:34-48`): `powers` per player, owners = argmax, **empty owner set when max power is 0** — same
"all tied players own it" convention our engine uses after the tied-feature scoring patch.

### The high-value answer: **yes, their ranking is deck- and phase-aware — through three channels**

1. **Tile-supply-derived closure probability (P).** Their `closure_p` is not a table; it is
   `1 − (1 − 1/nPlayers)^matchingTiles` computed from the **actual remaining-tile multiset**,
   matched by **edge pattern** to the specific empty cell, then multiplied across all of a
   feature's open edges. It carries an explicit "and will it be *my* turn" factor (`1/nPlayers`).
2. **An explicit phase gate:** the stuck-meeple penalty (2b) is switched off entirely once
   `remainingTurns ≤ 7`, i.e. it stops punishing committed meeples in the last ~7 turns of the game
   (`:295`). The comment marks it as a proxy: *"TODO compare with number of available followers instead"*.
3. **Implicitly, board saturation:** P is computed over `getAvailablePlacements()`, so as the board
   fills and patterns get scarce, every downstream probability moves.

**Our leaf, by contrast, has provably no `k_remaining` dependence anywhere** — `bag_close` is OFF
(null-screened), `tile_counting_closure` and `closure_continuous_slack` are OFF, `v28_meeple_recovery_t0`
is 0, and the C7 phase slot in `leaf_v29.py` is permanently zero
([LEVER_INDEX](../../docs/LEVER_INDEX.md) "turn/phase-indexed meeple value": *"The production leaf has
NO k_remaining dependence anywhere … the shipped agent's only phase awareness is the exact-solver
handoff"*). This is the single sharpest structural difference between the two evaluators.

---

## 2. Ours, same table

Production leaf `v2_9_2_Bmild_cap8_curve125` (`a36d2e15a3b3d71d`). Assembly, in order
([`flat_leaf.py:1064-1083`](../../src/carcassonne_ai/flat_leaf.py)):

```
score = base
      + softcap(closure_bonus(self), cap=8)      # soft_cap_slope 0.0 ⇒ hard clamp
      − softcap(closure_bonus(opp),  cap=8)
      + curve[free_self] − curve[free_opp]
score = int(round(score))          # leaf_quantize:float keeps the pre-round float for priors
```

Ablation convention: **negative elo = the knocked-out component is worth that much**; n=400
deck-paired vs the intact champion, band 9.60e10, PUCT@2750
([ABL_PROGRESS.tsv](../leaf_ablation_20260730/ABL_PROGRESS.tsv)).

| term | what it prices | scope | phase/deck | formula | measured value | src |
|---|---|---|---|---|---|---|
| **base** (`flat_base_score`) | the **exact end-of-game score differential if the game stopped now** — engine `count_final_scores` semantics, not a hand-built proxy: cities `2·shield+1·tile` open / `4·shield+2·tile` closed, roads `1/tile`, cloisters `1 + n_surround`, fields `3 × #finished adjacent cities` to the majority (all tied players get full points) | own − opp | **no** | running scores + end-now award | not ablated as a whole; **`farm_base_off` = −142.1** (z −9.39) | `flat_leaf.py:440-533`, `:555-590` |
| **closure anticipation, self** (`flat_closure_bonus`) | partial→full swing our meeples would collect if their features close | own | **no** — fixed table | `Σ P(open_n) · Δ` over the player's features: cities `Δ = city_root_delta`; cloisters `Δ = 8 − n_surround`; **roads absent by design** (open and closed road points are equal ⇒ Δ = 0) | `selfanticoff` = **−88.7** (z −6.95) | `flat_leaf.py:722-820` |
| **closure anticipation, opp** | same, mirrored, subtracted | opp | no | as above for the opponent | `oppanticoff` = **−153.4** (z −8.71); **both halves off = −7.8 (z −1.81) ≈ NULL** | same |
| — its **P schedule** | | | | `{1: 0.5, 2: 0.2}` (v2.7 `DROP_THREE_OPEN`; ≥3 open ⇒ 0 exactly) | the ≥3 "lottery tickets" were dropped as noise | `virtual_score_v2.py:218-224` |
| — **farm growth** (a block *inside* the closure bonus) | incomplete cities adjacent to our fields, deduped by city component | own/opp mirrored | no | `+ P(open_n) · 3` per such city | `farmgrowthoff` = **+42.8 (z 1.87)**, confirm **+10.4 (z −0.07)** ⇒ **unconfirmed / ≈null** | `flat_leaf.py:804-818` |
| — **cap** (`bonus_cap` = `opp_bonus_cap` = 8.0) | per-side clamp on the whole anticipation bonus | both, independently | no | `min(bonus, 8)`; F6 soft-cap slopes both 0.0 | `capoff` = **−13.6 (z −1.53) ≈ NULL**; cap12/cap5/oppcap4/oppcap12 all null in the fixed_v1 re-sweep | `flat_leaf.py:825-836` |
| **meeple liquidity curve** (`v29_meeple_curve`, curve125) | value of *holding* n free meeples — convex, signed, saturating | own − opp | **no** | table by free count 0..7: `[−10, −5, −1.25, 0, 2.5, 3.75, 5, 6.25]`, differenced | **`meepleoff` = −299.6 (z −18.94)** — the dominant organ; **`meepleflat` = −177.2 (z −12.92)** ⇒ the *curve shape*, not merely the term's existence, is worth ~177 | `PRODUCTION.yaml`; `flat_leaf.py:1071-1076` |
| Term R `v29_meeple_return_k` | meeple-return liquidity (closure-P-weighted credit for returnable meeples) | — | no | OFF (0.0) | **−251.9 at dose 1.0 (CL-055)** — decisively harmful | `flat_leaf.py:868-932` |
| Term F `v29_farm_flip_k` | farm majority-flip anticipation on contested fields | — | no | OFF (0.0) | CLOSED NULL (CL-055) | `flat_leaf.py:934-978` |
| `bag_close` / `tile_counting_closure` / `closure_continuous_slack` | deck-aware closure gating | — | would be **yes** | all OFF | `bag_close` −6.1 / C5 cell null | `virtual_score_v2.py:147-160` |

Search wrapper (not leaf, but it is what plays): `HeuristicPriorAgent`, PUCT priors
`softmax(Δleaf/τ_p=5)`, value `tanh(leaf/15)`, c_puct 1.5, fair PIMC k=8 × 1376 sims, exact endgame
latch K≤2 marginalized.

---

## 3. The diff

### 3a. Terms THEY have that WE lack — the steal candidates

| # | their term | as a native `LeafConfig` term | graveyard check |
|---|---|---|---|
| **S1** | **Stuck-meeple penalty** (2b): a follower on a feature with low completion probability is debited −12 / −3 / −1.2 (self) and the opponent's is credited +3 / +0.75 / +0.3, **switched off in the last ~7 turns** | `v29_stranded_k`: for each of the player's committed meeples, `−k · w(P_close)` with a *decreasing* step function of our existing `P(open_n)` (bands: no legal completion / low / medium), antisymmetrised, and optionally phase-gated on `k_remaining`. This is a **penalty on committed meeples**, structurally the dual of our curve (which sees only the free count) | **Partial prior art, none of it this shape.** Term R (`v29_meeple_return_k`) is the *credit* form — closure-P-weighted credit for meeples that will come back — and it was **−251.9 elo, decisively harmful** (CL-055; verdict: "curve125 had already soaked the extractable headroom"). The *penalty* form on **dead** features is not the same object: R over-credits what the curve already prices, whereas S1 fires exactly where the curve is blind — a meeple that will **never** come back. Nearest other prior art: `v28_meeple_recovery_t0` (phase scaling of the flat meeple term, −75 elo, era-caveated, **already scoped for a modern retry 2026-08-09** — see `measurement/curve_shape_scope_20260809/` §1.3, owned by another agent). "Stranding" appears in the LEVER_INDEX literature row as TRIED-and-null, but that row points at Term R. |
| **S2** | **Deck-derived, edge-pattern-matched, continuous closure probability** (P + `countCompleteProbability`): `1 − (1 − 1/n)^matchingTiles` per open cell, multiplied across the feature's open edges, with a `>0.85 → 1.0` snap | replace the `{1: 0.5, 2: 0.2}` lookup with a graded supply function: per open cell, count remaining tiles whose edge pattern can fill it, map to a probability, take the product. Our `closure_continuous_slack` knob is the existing hook (currently 0.0 = off; flat path raises rather than diverging, so it needs a flat implementation) | **Prior art is real but weaker than it looks.** `tile_counting_closure` (hard gate: P=0 when the deck can no longer complete) and `bag_close` (Hall's-condition feasibility gate, `−6.1`, C5 cell null) are both **binary feasibility gates**, not graded probabilities, and neither matches by **edge pattern per cell** nor carries the `1/nPlayers` "will I get to place it" factor. `closure_continuous_slack` was specified (Option-1 Step 5) and **never play-gated**. So the *graded pattern-matched* form is closest to NEVER-TRIED. ⚠️ Counter-prior: the two feasibility gates both came back null, which is evidence the whole deck-awareness axis is thin. |
| **S3** | **`rateConnections`** (7): majority-flip anticipation through a **probable future merge** of two same-class features meeting at a likely-to-be-filled empty cell, priced at `0.5 · P · featurePoints` to the players who gain/lose the merged majority | `v29_merge_flip_k`: enumerate empty cells with high fill probability, for each pair of adjacent same-class components compute merged meeple power, credit/debit the majority swing. **Cities and roads** — the classes JCZ prices here | **Term F (`v29_farm_flip_k`) is the farms-only, no-merge cousin** — it smooths base's hard `sign(margin)·V` step on *already contested* fields; it never anticipates a **future merge creating** a contest. CLOSED NULL. The city/road merge form is **NEVER-TRIED**. Also adjacent: the LEVER_INDEX "leaf ideas from the competitive-strategy literature" row's still-never-tried *"targeted denial on near-complete large opponent cities"*. |
| **S4** | **Per-category, convex open-feature lock-up penalties** (3): `OPEN_ROAD/CITY/CLOISTER/FARM[count]`, superlinear, and enormous for farms (1 farmer = −5, 2 = −10, 3 = −19) | `v29_lockup_table`: four 9-entry tables indexed by the player's count of solely-owned open features of each class, differenced. Note this makes the meeple-economy term **category-aware**, which our single free-count curve is not | **No direct prior art.** Our entire meeple economy is one function of the *free* count. Nothing in `LEVER_INDEX` prices *which kind of feature* a committed meeple sits in. Closest relative is again the curve itself (worth −300 total / −177 in shape), which is why an axis refinement here has a high prior. |
| **S5** | **Board-shape tiebreak** (5): `0.0001 × neighbours(lastPlaced)` | a compactness tiebreak on the last placement | **Do not bother.** Weight is 1e-4 against terms of size 1–30; it is a deterministic tiebreak, not knowledge. Unrelated to our border/wall work (`grid_rule`, W1–W4), which is about the 35×35 grid bound, not placement compactness. |

Explicitly **not** candidates: `rateDragon` (inert outside expansions), the `Barn`/`ScoreFieldBarn`
branch (out of locked scope), `SmallFollower`-vs-other discrimination (we have only small followers).

### 3b. Terms WE have that THEY lack — where the +4.6/deck plausibly comes from

| # | our term | why it may matter | measured |
|---|---|---|---|
| **W1** | **The non-linear, signed, saturating free-meeple curve** `[−10,−5,−1.25,0,2.5,3.75,5,6.25]`. JCZ's supply term is **linear at 0.15/meeple with a single −4.0 cliff at zero** — i.e. their free-meeple value is ~40× smaller per meeple and has no convexity at all | our largest organ by a wide margin, and *the shape itself* is a third of it | −299.6 / shape −177.2 |
| **W2** | **Exact end-now scoring as the base**, straight out of the engine's own `count_final_scores` semantics (tied features → full points to all tied players, cathedral/inn handling, exact field majority). JCZ reassembles an approximation from `getStructurePoints` + hand-weighted completion terms and then applies discounts (×0.8 uncertain, ×0.99 farms) | any systematic bias in their reassembly is a free edge to us; theirs is an *expected*-score estimate, ours is an exact *current*-score with a bounded anticipation correction on top | `farm_base_off` −142.1 |
| **W3** | **Farm-growth anticipation** — `P(closure) × 3` for incomplete cities adjacent to our fields. JCZ's farm term is `0.99 × ScoreField(final)`, which counts **finished** cities only; they have **no farm-growth upside term at all** | this is exactly the v1 failure mode our v2 was built to fix ("v1 systematically underestimates mature farms") — and JCZ still has it | ⚠️ **but our own ablation could not confirm it**: `farmgrowthoff` +42.8 then +10.4 on confirm. Do not claim this as the edge. |
| **W4** | **Per-side caps** on the anticipation bonus (cap8 / oppcap8), which bound how far the leaf can run on speculation. JCZ's terms are unbounded (only the OPEN_* tables saturate, at index 8) | in principle prevents the over-extension failure the ablation localised | ⚠️ **measured ≈ NULL** (`capoff` −13.6, z −1.53; all four re-sweep wings null). Decorative. |
| **W5** | *(not a leaf term, but it is the elephant)* the entire search stack: PUCT with heuristic priors, k=8 PIMC determinizations × 1376 sims = 11008, tree reuse (clairvoyant only), exact endgame latch K≤2. JCZ does **one static evaluation per own-turn action chain, with no opponent reply** | this is ~31× the per-move compute, and it buys **+4.6 pts/deck** | see §5 |

### 3c. Shared concepts, priced differently

| concept | ours | theirs | the interesting delta |
|---|---|---|---|
| **P(a feature closes)** | fixed table `{1:0.5, 2:0.2}`, ≥3 open ⇒ **exactly 0** | continuous, deck- and pattern-derived, product over open edges, `>0.85 → 1.0` snap | **the deck channel** (S2). Also: ours *refuses to look past 2 open edges* (a deliberate v2.7 decision — 3-open was noise); theirs prices every horizon continuously |
| **completion upside** | `P · Δ` where Δ is the exact partial→full swing | `prob · 0.8 · (complete − incomplete)`, cloisters `prob · 0.5 · (9 − incomplete)` | theirs carries an *extra* pessimism factor (0.8 / 0.5) on top of the probability, and comments say it exists to "advantage closed features". Our P table (≤0.5) already encodes that pessimism in the probability itself. Similar magnitudes, different factorisation |
| **roads** | **no anticipation term at all** — road points are 1/tile open or closed, so the closure delta is identically 0 | same arithmetic (`complete − incomplete = 0` for a road) ⇒ their 2a road contribution is *also* 0, **but** roads carry a large `OPEN_ROAD_PENALTY` | theirs prices road meeples entirely as **lock-up cost**; ours prices them entirely as **base points**. Neither has road *upside*. This is the cleanest single illustration of S4 |
| **self/opponent symmetry** | strictly antisymmetric, with *independently tunable* per-side caps (both 8.0 today) | strictly antisymmetric via `ptsforPlayer`, **except 2b**, where self:opp magnitudes are **4:1** (−12 vs +3) | our ablation found the anticipation machinery's value is **balance, not information** (opp-half-only removal −153, both-halves −7.8). JCZ ships a deliberately *unbalanced* stuck-meeple term. Worth flagging to whoever tests S1: port the asymmetry as a knob, not as a constant |
| **fields** | base majority award + growth anticipation, no lock-up cost | `0.99 × final field score` **minus** `OPEN_FARM_PENALTY[n_farms]` = −5 for the first farmer, −10 for two, −19 for three | their net farm valuation is dramatically more pessimistic about *committing* a farmer. Given the open E4 farm question (the champion averages 11.0 farm pts/seat vs Joshua and 20.5 in its own corpus; farm-war discriminator INCONCLUSIVE), this is the most suggestive single row in the memo |
| **cloisters** | `P · (8 − n_surround)` | `prob · 0.5 · (9 − incomplete)` + `OPEN_CLOISTER_PENALTY` (tiny: 0, 0, 0.4, 0.8…) | same idea; theirs half-weighted and lock-up-taxed |
| **meeple economy** | one convex table over the **free** count | `0.15 ×` free count `− 4.0` if empty, **plus** the category-convex lock-up tables (3), **plus** the deadness penalty (2b) | **the same organ, encoded dually.** Ours reads the supply side; theirs reads the committed side, with *two* extra resolutions we do not have: **which feature class** and **how dead the feature is**. Our curve cannot distinguish a meeple on a 1-open city from one stranded on a dead field. That is the located hole |

---

## 4. Caveats — why reading a term tells you nothing about its value

**Reading a source file tells you WHAT an evaluator computes. It does not tell you WHAT MATTERS.**
Our own knockout ablation proved this on our own leaf, twice over:

- **A written term can be worth −153 elo or ≈0 and look identical in source.** Removing the
  **opponent half** of closure anticipation costs −153.4 elo; removing **both halves** costs
  −7.8 ± 17.4 — statistically nothing. The machinery's value is **balance, not information**. A
  reader of `flat_closure_bonus` cannot see that; only the nested ablation could.
- **A term can be decorative.** `capoff` −13.6 (z −1.53) and the whole caps/curve re-sweep came back
  6/6 null: the cap8 clamp that appears prominently in `PRODUCTION.yaml` is, as far as we can
  measure, doing nothing.
- **A term can be actively harmful in a shape that reads sensible.** Term R (meeple-return
  liquidity) is a perfectly reasonable-looking closure-P-weighted liquidity credit. It cost
  **−251.9 elo**.
- **A term can be unconfirmable.** `farmgrowthoff` read +42.8 (z 1.87) and then +10.4 on confirm —
  the same knockout, twice, disagreeing.

Therefore **every candidate in §3a is a hypothesis with zero evidence attached**, and the route is
fixed by the BACKLOG entry:

1. **Disagreement mining first** (BACKLOG 2026-08-09 "JCZ disagreement mining", step 1): step a
   corpus of real positions through both evaluators, collect disagreements, score both picks over
   M=32 CRN deck completions with `oracle_score_pilot.py`, **stratified by game aspect** so a win
   localises to a term rather than a vibe. Term archaeology (this memo) says *what they price*;
   only the mining says *where they win*.
2. **Then a native implementation and a play gate.** Implemented from scratch as a `LeafConfig`
   term, bracketed above and below (never a single off-baseline sample), n=400 deck-paired,
   within-band, on a fresh band. **Not a blend** — every value-blend has died at the search gate.
3. **AGPL:** ideas and measurements yes; JCZ code never enters our leaf.

Four further riders specific to this comparison:

- **The tie itself is an n=20 assumption.** +4.6 ± 2.2 pts/deck (z 2.07) is a *screen*. The BACKLOG
  entry's own sequencing puts the n=400 confirmatory match **before** this lever. A tie that is
  really a +30-elo win changes which direction we should be stealing in.
- **The match ran `fixed_v1` + `CARCASSONNE_FIX_R9=1`**, the only provably rules-identical
  configuration, which is **not** the production (`walled`, R9-off) default. These games are not
  comparable to walled elo, and R9 moves **farm** scoring — the exact axis several rows above turn on.
- **Their evaluator is inseparable from their search.** `LegacyRanking` was tuned against a
  one-turn breadth-first enumeration with no opponent reply
  ([`RankingAiPlayer.java`](../../scripts/jcz_match/java/com/jcloisterzone/ai/RankingAiPlayer.java)).
  Terms that are load-bearing there may be *redundant* under 11008 sims of PIMC search, because the
  search already discovers them — this is the standing sims-washout pattern (a policy/eval gain of
  +82.8 elo at sims=200 read +8 at sims=800). S3 (`rateConnections`) is the obvious victim: a merge
  one tile away is exactly what a deep search sees for free. S1 and S4 are the better bets precisely
  because they are *horizon-independent* valuations of commitment.
- **Bug-fix-shifts-optima applies to any adoption.** Anything touching the meeple or farm axes
  re-opens caps/curve125, which were tuned against the current term set.

---

## 5. Verdict

**Convergent evolution — with one genuinely different organ, and it is the one our ablation already
named as our biggest.** Both evaluators are the same species: an antisymmetric, hand-weighted sum of
(banked points) + (end-now feature value) + (probability-weighted completion upside) + (meeple
economy), with farms handled specially and no learned component anywhere. Where they differ is not
the ontology but the **resolution on the meeple axis and the source of the closure probability**. Our
meeple economy is one convex function of the *free* count, and our closure probability is a
two-entry constant table that is blind to the bag; JCZ's meeple economy is three separate terms on
the *committed* side — feature-class-convex lock-up, deadness-banded stranding, and a phase gate —
and its closure probability is computed from the actual remaining-tile multiset matched by edge
pattern per cell. Neither of us has what the other has, and neither of us has both. The most
economical explanation of the n=20 tie is that our +300-elo curve and our exact end-now base roughly
cancel their lock-up/stranding pricing and their deck-derived probabilities, leaving our ~31× search
advantage to produce a mere +4.6 pts/deck — which, read the other way, is the uncomfortable finding:
**11008 sims of PIMC plus an exact endgame solver bought about four and a half points per deck over a
static one-ply evaluator, and that is the number a "structurally different knowledge" story would
have to explain.** The two highest-prior steals are **S1 (stranded-meeple penalty)** and **S4
(category-convex lock-up)**, both on the meeple axis where our leaf is provably most valuable and
provably lowest-resolution; **S2 (deck-graded closure P)** is the most *structurally* novel — it
would give the leaf its first `k_remaining` dependence — but it is the one with the most existing
null evidence stacked against it. None of the three is believable until the disagreement mining
locates a category where they actually win.
