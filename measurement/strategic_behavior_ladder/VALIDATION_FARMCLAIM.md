# farm_claim validation audit — is it diagnostic/actionable, or a proxy for good positions?

**Bottom line (revised, conservative):** `farm_claim` is a *genuine* behavior that mildly
correlates with winning **in competitive games** (survives pre-move-lead controls), so it is a
valid diagnostic. **But RoD1's measured farm deficit is NOT actionable** — it is concentrated in
*low-leverage* situations (vs weak opponents you win anyway; already-ahead / late, game-decided
positions). Where farm claims actually have leverage (vs strong opponents, even score, opening),
RoD1 already matches h6400, and RoD1's *own* farm claims do not predict its wins (−2pp). The
first-pass "+17pp → actionable" was inflated by a collider (close-game conditioning) plus a
weak-opponent/leading-state confound. **Revised recommendation: do NOT run the farm probe; STOP.**

Audit script: [`scripts/strategic_ladder/audit_validation.py`](../../scripts/strategic_ladder/audit_validation.py).

---

## 1. Motif definitions (exact) + leakage check

| motif | phase | opportunity_exists | action qualifies | magnitude | excluded |
|---|---|---|---|---|---|
| **farm_claim** | MEEPLES | a legal FARMER action makes the mover **sole** owner (`_winners==[mover]`) of a farm whose **projected value = 3 × (# adjacent city components) ≥ 6** that the mover didn't already own | the farmer placements that do so | projected value (3×adj); `detail` also stores `finished_adj`, `adj_n` (all structural) | farms touching <2 cities; farms the mover already owns; ties (those are contest, not claim); roads/cities |
| **block** | TILES | opp holds majority/tie on ≥1 OPEN city, open_n≤2, opp completion-equity `Σ value·P(close) ≥ 4`, AND consequential (max−min opp-equity across legal placements ≥ 2) | strict **arg-min** opp completion-equity placement | the equity swing | roads (no open-distance in the decomposition); non-near-complete positions |
| **avoid_feeding** | TILES | a consequential feeding move exists (max−min opp-equity ≥ 2) | strict arg-min | the swing | as block |
| **contest_merge** | TILES | some placements yield a mover-favorable (tie/win by farmer count) **contested** farm (both players have farmers, projected ≥6), others don't | those placements | projected value | non-choice positions (all-or-no placements yield it) |

**farm_claim "high value" is PURELY current board structure** — `3 × |farm_root_adj_city_roots|`
from `flat_leaf.decompose(state)` (which cities the field physically touches). It does **not** use:
the final result, the game margin, any heuristic/v2.7 *score*, h6400's choice, or exact labels.
The only place outcome appears is the **downstream** outcome-sanity table — never in the label.
`P(close)={1:0.5,2:0.2}` (block/feed) is a labeled probability *model*, not the v2.7 score. **No leakage.**

- **farm_claim TRUE positive:** a corner connecting to an unowned 3-city field (`adj_n=3`, `mag=9`) you
  can sole-own — e.g. `h200:random` seed 1963002 ply 89 (4-city field, h800/h3200/h6400 claim, rod1 misses).
- **farm_claim FALSE positive:** an **opening** field with `adj_n=2, finished_adj=0` — projected value 6
  is *optimistic* (assumes both cities complete). 517/777 opps are opening with mostly `finished_adj=0` →
  a large speculative-claim class. This is the benchmaxing trap and is exactly why the outcome controls below matter.

## 2. Cell sizes (farm_claim opps with a recorded outcome = 777; took 251 / miss 526)

| split | cells (n; ⚠ = thin <20 for a take/miss arm) |
|---|---|
| **mover_spec** | random 122 · greedy 235 · h200 **34** · h800 119 · h3200 50 · h6400 72 · rod1 145 · **iter08 0** (never a game-playing agent) |
| **opp_class** | weak 235 · mid 332 · strong 210 |
| **phase** | opening 517 · midgame 142 · late_mid 57 · pre_endgame **38** · endgame **23** |
| **close-game (\|final\|≤5)** | **117 total (took 32 / miss 85)** — the original +17pp rested on this thin, outcome-conditioned cell |

Thin cells (do not over-read): h200-mover; h3200/h6400/h200 take-vs-miss strata; all late phases;
every per-agent × per-stratum cell in §3; `random:random` self-play (n=4 take).

## 3. farm_claim causality (confound controls). win% = P(mover wins this game)

> **Method note:** `score_margin_before` (smb = scores[mover]−scores[opp]) is a clean PRE-move
> covariate. `final margin` / "close game" is a POST-move OUTCOME — conditioning on it is conditioning
> on a consequence (collider). So the **unconditioned** sample is primary; close-game is secondary.

- **[A] Unconditioned:** take **65%** win (n=251) vs miss **53%** (n=526) = **+11pp** (+12.8 margin).
  (The headline +17pp came from the close-game collider; the honest effect is +11pp.)
- **[B] Leading-state confound:** takers are only slightly more ahead pre-move (smb **+6.5 vs +5.2**) —
  a small confound, not enough to explain +11pp.
- **[C] Stratified by pre-move margin:** behind **+12pp**, even **+12pp**, ahead **+3pp** (ceiling).
  → survives the lead control in non-winning positions; it is *not* purely "already ahead."
- **[D] Stratified by mover agent:** greedy +13, h800 +7, h3200 −8 (thin), **h6400 +23**, **rod1 −2**.
  → agent-dependent; crucially **RoD1's own farm claims do NOT predict RoD1's wins (−2pp)**.
- **[E] Within-agent self-play (cleanest agent control):** greedy:greedy +18, **h800:h800 −1**,
  rod1:rod1 +12, random:random +36 (n=4 ⚠). → inconsistent; ~half the agents show ≈0.
- **[F] Leverage map:** by phase opening +12 / midgame +7 / **late_mid −8** / pre_endgame +2 / endgame +2;
  by opp **weak +8 (ceiling: 99% vs 91% — you win regardless)** / mid +3 / **strong +18**; by value proj6 +10 / proj9 +9 / proj≥12 +25.
- **[G] Combined control (even pre-move margin AND non-weak opp):** **+5pp** (n=87 take / 256 miss).

**Read:** the effect is real but **modest after controls (+11pp raw → +5pp even+non-weak)**, **ceiling'd
vs weak opponents**, **agent-dependent (≈0 for rod1/h800)**, and **strongest exactly where rod1 has NO
deficit** (vs strong +18pp, opening +12pp — rod1≈h6400 there). It is **weakest where rod1's deficit lives**
(late_mid −8pp; vs-weak ceiling).

**Answer to the main question:** farm_claim is *associated* with winning even after controlling for
pre-move lead, so it is not *only* a "leading position" proxy — but the association is modest, is
ceiling-dominated by easy (vs-weak) games, and **does not hold for RoD1's own play**. It is a fair
diagnostic of *competitive* farm value; it is **not** evidence that pushing RoD1 to claim more farms would win more games.

## 4. h6400 vs RoD1 on identical positions (counterfactual, 777 farm opps)

h6400 take **60%** vs rod1 **54%** = **+6pp**. Disagreements: **h6400-take/rod1-miss = 79**; reverse 32.

- **By opponent: weak 49 / mid 19 / strong 11** — **62% of rod1's farm misses are vs WEAK opponents**
  (where the game is already won) and only 11 are vs strong (competitive).
- **By phase:** opening 35 / midgame 16 / late_mid 13 / pre_endgame 11 / endgame 4.
- **The disagreements are dominated by already-decided positions:** the top-magnitude h6400-take/rod1-miss
  cases are at pre-move margin **smb +54, +21, +33, +35** — i.e. **RoD1 declines to pad an already-won
  game; h6400 greedily banks the points.** That inflates h6400's *margin* but costs RoD1 ~0 *wins*.
- **Strategic read of an example:** `h3200:random` seed 1962002 ply 117, pre_endgame k=14, a 4-city field
  (`adj_n=4, finished_adj=1`, mag 12) with the mover at **+54** — the field is genuinely valuable in
  isolation (one city already done, three more touching), but the mover is already crushing, so claiming it
  is points-padding, not a turning point. This is the whole pattern: high structural value, low *decision* leverage.
  (Outcome caveat: `final_margin` is the actual mover's, not h6400's/rod1's — these are observational.)

## 5. Are the killed motifs truly dead?

- **`block`:** on its 203 opportunities, **random and h6400 make the same choice 82% of the time** — the
  detector cannot separate a random agent from the strongest. Examples (seed 1962000 ply 46/82/94): both
  agents miss or both take together. Genuinely non-diagnostic (the equity-proxy mostly flags
  *non-interaction* with the opp city, which most placements satisfy). **Dead — detector is crude AND the signal is weak.**
- **`avoid_feeding`:** random ≡ h6400 on **87%** of 780 opps. **Dead** for the same reason.
- **`contest_merge` outcome-negative (−11pp):** **NOT a "contesting is bad" finding and NOT a behind-signal.**
  Pre-move margin for contesters is actually slightly *ahead* (took +3.1 vs miss −3.6), so it's not that
  contesting happens when losing. The −11pp came from the thin (n=18) close-game cell and is best read as
  **noise / non-predictive**, consistent with contest_merge being a coarse "does it search at all" detector
  (random 18% → every search agent ~45–49%, no gradient among search agents).

## 6. Benchmark-overfitting safeguards (confirmed)

- ✅ **No training used these labels** — this branch produces zero training data; detectors never touch a gradient.
- ✅ **dev/test split for thresholds** — all thresholds tuned on a greedy DEV band (seeds 1930xxx), **frozen**
  before the audit; the entire suite (1940xxx+) is the held-out test set.
- ✅ **Reported metrics are held-out** — computed only on the frozen test suite.
- ✅ **Behavior score never used for promotion** — PRODUCTION.yaml + champion unchanged; no checkpoint moved.
- ✅ **h6400_v2.8 full-game winrate remains the external ruler** — the only strength arbiter.

## 7. Revised verdict

- **Which motif is actionable?** **None, for RoD1.** `farm_claim` is the only *diagnostic* motif (it
  discriminates and, in competitive games, mildly predicts winning), but RoD1's deficit on it is in
  low-leverage regimes (vs-weak ceiling, already-ahead/late, game-decided), and RoD1's own farm claims
  don't predict RoD1's wins. The other three are dead/coarse.
- **Is farm_claim strong enough to justify a late-farm-value / value-head recalibration probe?** **No.**
  After honest controls the competitive-game effect is small (+5pp even+non-weak), and it is concentrated
  exactly where RoD1 is **not** deficient. Closing RoD1's farm gap would mostly add margin to already-won
  games. The expected move in winrate vs h6400 is ≈0.
- **If one ran it anyway, the success criterion:** a recalibrated net must beat `h6400_v2.8` (or close the
  gap to it) on **full-game held-out paired winrate at n≥400** by a **≥2σ margin (≈ +24 Elo; n=400 paired
  ≈ ±12 Elo 1σ)** — not on any behavior score, not on score-margin. Given the leverage map, this is
  very unlikely to clear.
- **What would falsify the farm hypothesis?** It is **already largely falsified as a competitive lever:**
  (a) the effect does not survive as a *vs-strong, even-score* RoD1 deficit (rod1≈h6400 53/53 vs strong);
  (b) RoD1's own farm-taking is outcome-neutral (−2pp); (c) the deficit positions are dominated by
  smb≫0 already-won games. A *confirming* result would have been: RoD1 under-claims farms **vs strong
  opponents in even-score positions**, and those specific misses correlate with losses — which the data
  does **not** show.

**Net:** the strategic-behavior benchmark, after this validation, reveals **no actionable strategic lever**.
RoD1 plays heuristic-level strategy with no exploitable competitive gap; its loss to h6400 remains the
separately-characterized endgame **placement/conversion** leak, not a farm-claim deficit. **STOP** is the
honest call. Keep `farm_claim` as a *monitoring* diagnostic only; treat block/avoid_feeding/contest_merge as retired.
