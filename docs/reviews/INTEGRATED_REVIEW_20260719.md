# INTEGRATED INDEPENDENT REVIEW (verbatim, received 2026-07-19)

> Provenance: Joshua commissioned two independent external reviews of the project (blind-first protocol package `fresh_look_review_20260719.zip` + supplemental), then had them editorially combined. This file preserves the integrated document verbatim. The project's response/disposition lives in [REVIEW_ADOPTION_20260719.md](REVIEW_ADOPTION_20260719.md).

---

## Superhuman Two-Player Carcassonne Agent

**Editorial synthesis of two independent reviews**
**Date:** 19 July 2026
**Status:** Final integrated document

## Contents

- Executive verdict and decision summary
- Part I — Blind diagnosis, preserved verbatim
- Part II — Consolidated facts
- Part III — Phase-1 suspect disposition
- Part IV — The missed things and their decisive tests
- Part V — Verdict audit
- Part VI — The path
- Part VII — Stop rules
- Part VIII — Phase-3 cross-check and amendments
- Conclusion

---

## Executive verdict

The two reviews converge on the central decision.

**The team was right to retract the it16 "breakout."** The selected checkpoint did not replicate on a fresh deck band, fell from **+88.7 Elo at k2×200 to +1.7 Elo at k4×688 on the same decks**, and failed the pre-registered continuation branch. The strongest defensible wording is not "proved to be pure noise," but **"not robust and depth-local at best."** A small shallow effect may exist; it is not a production-strength result and does not justify promotion.

**There is no demonstrated self-learning flywheel.** The current loop distills policy around a permanently frozen hand evaluator, generates at one quarter of deployment depth per determinization, trains on pooled visits while deployment selects by pooled Q, and has twice produced policy gains that vanish at deeper search. Continuing that loop unchanged is not rational.

**The project nevertheless has a credible path to a superhuman agent.** The strongest evidence supports a classical-first route: make the production agent executable and auditable, exploit the proven fair-search scaling curve, test whether root-determinization PIMC is leaving public-state value on the table, correct any stage-dependent utility mismatch, and finally measure against strong humans. A learned component is optional. It should be funded only after a cheap experiment proves that its channel has production-depth headroom.

**The highest-information unresolved questions are now measurable without another long arc:**

1. Does current PIMC disagree materially with an exact public-state chance solution on genuinely hidden small-bag roots?
2. Is there any production-depth headroom left in the policy-prior channel, even with near-oracle priors?
3. Does a fixed `tanh(margin/15)` utility misprice wins by game stage?
4. Is the remaining classical residue a bundle of sub-threshold effects rather than zero?
5. How strong is the current audited agent against the human frontier?

The integrated recommendation is therefore: **do not restart the full self-learning loop; run the release audit and four bounded discriminators, buy more fair simulations, and begin the human benchmark.** Reopen learning only if a discriminator clears a pre-registered production-depth gate.

## Decision summary

| Question | Integrated answer |
|---|---|
| Was the newest growth claim valid? | No. The retraction was correct; the selected peak failed fresh replication and production-depth transfer. |
| Is the current loop a self-learning flywheel? | No. It is a stable policy-distillation loop around a frozen value basis, with no demonstrated compounding at deployment depth. |
| What has definitely improved strength? | Classical evaluator work, the PUCT search rebuild, curve125, the measured k4 PIMC setting, and additional fair simulations. |
| What is the largest untested architectural risk? | Root-determinization PIMC with conditional pooled-Q has never been compared with the correct public-state chance object on roots with genuinely hidden future draws. |
| What is the cheapest way to decide whether policy learning is worth more money? | The oracle-prior production-depth headroom probe, paired with fixed-root depth-transfer and target-alignment replay. |
| What should happen before any more headline experiment? | Make the champion manifest executable, fix the stale human harness, and pass adversarial semantic regression tests. |
| Is a learned component required for success? | No. The goal is a superhuman fair agent; learning is a means, not a requirement. |
| How is "superhuman" established? | By a fixed, audited fair agent defeating a pre-registered frontier human panel on fresh one-use decks, including an adaptation block. Internal Elo is insufficient. |

## How this synthesis was constructed

This document combines two completed reviews rather than re-running the packet analysis. The blind-first review supplies the full code-level diagnosis and the Phase-3 cross-check. The supplemental review adds especially useful quantitative power accounting and three decisive probes: the production-depth oracle-prior ceiling, stage-dependent win utility, and a powered bundle test for sub-threshold classical effects.

The editorial rules are:

- The original blind diagnosis is preserved below without hindsight edits; only heading levels are changed for document structure.
- Where the reviews agree, the evidence is stated once.
- Where they differ, the merged conclusion uses the narrower claim and makes the remaining uncertainty explicit.
- Verdict-grade evidence means a suitable paired test at roughly n≥400 or a genuine replication; n=100–200 single-band results remain screens unless the effect is overwhelming.
- Offline ranking is not treated as a proxy for in-game strength.
- Low-depth improvements are provisional until they survive production depth and equal wall-clock comparison.
- Exact source filenames and result-row identifiers are retained so the synthesis remains auditable against the packet.

## Immediate action sequence

1. **Release integrity, first.** Build one executable champion factory, update the stale human harness, and run the semantic/property suite.
2. **Run the free utility audit.** Estimate `P(win | leaf margin, tiles remaining)` from existing game logs.
3. **Run fixed-root policy diagnostics.** Measure oracle-prior headroom, depth transfer, target mismatch, and coverage bias before training another net.
4. **Run the exact small-bag public-state oracle.** Decide whether PIMC is the main untested search bottleneck before funding a new search engine.
5. **Start the human operations pilot.** Use cross-player/Latin-square deck pairing so humans do not replay a remembered hidden sequence.
6. **Exploit proven scaling.** Optimize the Python search/engine loop and measure equal-wall-clock gains from more fair simulations.
7. **Only then branch.** Public-state search if the oracle fires; corrected policy learning if prior headroom and deeper targets fire; calibrated residual value if it beats the leaf locally; otherwise classical scaling and human proof.

---

# PART I — BLIND DIAGNOSIS, PRESERVED VERBATIM

The following section is the original Step-1 diagnosis from the blind-first review. Its wording is unchanged by the experimental record; only heading levels have been demoted to fit this integrated document.

## PHASE 1 DIAGNOSIS — BLIND, PRE-RESULTS

**Review boundary.** This diagnosis was written after reading only the two top-level orientation files, `phase1/A_GOAL_AND_GAME.md`, `phase1/B_SYSTEM_DESCRIPTION.md`, and all 15 files in `phase1/code/`. No path under `phase2/` or `phase3/` had been listed, opened, searched, or otherwise inspected when this document was completed.

### Executive diagnosis

The project has built a serious and unusually well-instrumented search system, but the current "self-learning" loop is structurally boxed in. Its production agent is not an AlphaZero-like system whose evaluator can improve through outcomes. It is a hand-evaluator system in which the same fixed heuristic both (a) supplies the search value and (b) generates the action priors through one-step heuristic deltas. The neural loop is then allowed to replace only the priors; its learned value is deliberately prevented from steering search. That can compress the teacher, improve finite-budget move ordering, and occasionally discover a better way to spend a fixed search budget. It cannot reliably repair a strategic blind spot that the fixed leaf misvalues, because deeper search still terminates in that leaf and the policy targets are themselves generated by searches governed by it.

The fair-play layer introduces a second ceiling. Each determinization is searched as if its entire future deck were known, then root statistics are pooled. Fresh trees correctly prevent direct hidden-order leakage, but they do not remove **strategy fusion**: downstream play inside each world is allowed to condition on future draws the real agent will not know. The current pooled-Q rule also averages an action only over determinizations in which that action happened to receive visits. Missing adverse worlds are not counted against it. At `k=4`, this is a very low-sample, selection-biased estimate of an imperfect-information action value.

The representation has correctness risks before one even reaches learning quality. A moving 25×25 centroid crop silently omits already placed tiles and meeples, and silently removes any legal placements outside the crop unless *all* legal actions overflow. Thus the wrapper can change the legal game while presenting the network with a non-Markov partial board. The default representation also omits the publicly known remaining-tile multiset and does not encode field-component identity or even complete local farm topology. The optional "sighted" representation adds useful public information, but its three ownership planes still collapse distinct fields and omit control margins, unclaimed fields, access, and adjacent-city value.

My predicted strength ceiling is therefore the interaction of four things, in this order:

1. **A fixed, materially biased heuristic leaf used twice — as value and as prior generator.**
2. **PIMC strategy fusion plus low-K, conditionally pooled root values.**
3. **State/action information loss, especially crop loss and farm/bag structure.**
4. **Training targets and deployment rules that do not describe the same policy.**

I would not spend the next unit of compute scaling the present flywheel. I would first establish whether the interface is lossless, correct the concrete leaf-rule errors, replace root determinization with observable-state chance sampling or information-set search, and align the learned target with the actual action rule. A learned component may then become useful, but learning is not required for the immediate strongest-agent path.

---

## 1. DESIGN DECISIONS THAT ARE NON-STANDARD, RISKY, OR WRONG

The identifiers below are frozen Phase-1 suspects. They are intentionally specific so each can later be classified against evidence without rewriting the diagnosis.

### A. Goal, utility, and game-theoretic formulation

#### P1-G1 — The optimized utility is undefined at the project level, while the code commits to `tanh(score_diff / 15)`

The stated goal is "superhuman play," but the implementation optimizes a saturated score-margin transform. Those are not equivalent objectives:

- maximizing win probability;
- maximizing expected score difference;
- maximizing `E[tanh(score_diff/15)]`;
- minimizing loss probability with margin as a tiebreak;

can rank risky moves differently. The tanh transform is especially consequential under chance: it strongly compresses common large margins and imposes a nonlinear risk preference. A 30-point and a 70-point win are both nearly +1, while movement around a close result matters much more. That may be a reasonable deployment utility, but it has not been justified as the definition of superhuman strength. The exact tie epsilon (`+1e-6` for player 0 and `-1e-6` for player 1) preserves antisymmetry but introduces a needless player-index asymmetry into terminal values.

**Risk:** the system can become "better" under its shaped utility while becoming worse in match win rate, or vice versa. All evaluation and stop rules need one primary utility and explicitly secondary metrics.

#### P1-G2 — An analyzer architecture was promoted into an agent without replacing its clairvoyant game model

The deterministic MCTS descends a pre-shuffled future deck. The production fair wrapper repairs information leakage only at the root by sampling plausible complete decks. That is not the same game as the observable stochastic game. It is a collection of perfect-information games averaged after the fact.

**Risk:** plans inside each determinization exploit future draws that the deployed policy cannot condition on. This is the classic PIMC strategy-fusion/non-locality failure mode and can produce confidently wrong root values even if each world is searched perfectly.

#### P1-G3 — "Superhuman" currently has no human-anchored operational definition

The packet says there is no human or external strength anchor. Internal Elo among descendants of the same engine, hand leaf, and search family is useful for engineering but cannot establish superhuman play. A closed ecology can improve at exploiting its own ruler or regress together.

**Risk:** the project can reach a stable, impressive internal ladder without knowing whether it beats strong human play. This is a measurement-design defect, not merely a missing publicity match.

#### P1-G4 — Simulation budgets are treated as comparable strength budgets although evaluators do radically different work

A heuristic-prior node expansion evaluates the hand leaf for every legal child to construct priors. A vanilla UCT expansion evaluates one child. A network expansion incurs a forward pass and, in batched mode, virtual-loss perturbation. "2750 simulations" is therefore not a compute-normalized comparison across agents.

**Risk:** architectural conclusions can be artifacts of unequal wall-clock, leaf-call, or energy budgets. Strength claims should report both a deployment budget and compute-normalized controls.

### B. State, observation, and rules interface

#### P1-R1 — The 25×25 centroid crop can silently make the agent play a restricted, partially observed game

`encode_board` silently skips placed tiles and meeples outside the window. `get_valid_moves` silently drops legal placements outside the window whenever at least one in-window action remains; it raises only when every legal action overflows. This is more serious than a lossy neural feature: the action wrapper can remove legal moves from the game.

The crop is centered on the rounded centroid, not on the bounding box or the current frontier. A long or bifurcated board can overflow even when 25 cells sounds large. Strategic farm and city components can cross the crop boundary, so an in-window action may depend on omitted ownership and connectivity.

**Risk:** non-Markov observations, missing legal wins/blocks, incorrect training masks, and silent game-rule changes. This must be measured before any model conclusion is trusted.

#### P1-R2 — The moving centroid and coordinate-specific policy head break translation consistency

Adding one tile can round the centroid across an integer boundary and shift the entire encoded board by one cell. A convolutional trunk is approximately translation equivariant, but the policy head flattens 4×25×25 cells into a dense 2511-way layer. Its parameters are tied to absolute crop coordinates. The same geometric position translated by one crop cell is therefore not represented by the same policy computation, and there is no translation augmentation.

**Risk:** abrupt representation changes between adjacent plies, unnecessary sample complexity, and poor generalization to unusual board shapes. Rotation augmentation does not solve translation non-equivariance.

#### P1-R3 — The default 78-channel representation omits the public bag composition

Remaining tile counts are public and strategically central in Carcassonne. The blind representation includes only a scalar number of tiles remaining and the currently drawn tile. It cannot distinguish "the needed cap is still abundant" from "all compatible caps are gone." The production hand leaf also normally has bag-aware closure disabled.

**Risk:** no learned policy or value using the default representation can perform genuine tile counting. This is an information-theoretic ceiling, not a capacity issue.

#### P1-R4 — Farm structure is under-encoded at both local and component levels

The base board tensor encodes outer terrain, road-pair connectivity, city-pair connectivity, and farmer locations, but not full within-tile field connectivity. More importantly, it does not encode field-component identity, farmer-count margins, which cities border each field, whether those cities are complete, field access/frontier, or merge threats.

The optional three farm planes mark cells touched by a field currently won by self, won by opponent, or tied. They:

- exclude unmeepled fields;
- OR multiple distinct fields together on a cell;
- can mark several ownership statuses on one cell without identity;
- omit the actual farmer margin;
- omit adjacent-city identities/value;
- omit open access and possible future merges.

**Risk:** the network is asked to infer a long-range dynamic graph from a cropped raster that does not uniquely describe that graph. Farmers are a stated expert-play core, so this is likely strength-limiting.

#### P1-R5 — Several strategically different tile states can collapse to the same neural encoding

The tensor is a hand projection, not a full tile identity. It intentionally buckets non-edge terrain, combines chapel/flowers, and represents only selected road/city internal pair relations. Farm subdivisions are not fully represented. Even where the engine state distinguishes tiles or rotations, the neural input may not.

**Risk:** irreducible policy/value aliasing: two states requiring different decisions can receive the same input. A direct parity test should search the tile set for encoding collisions and then determine whether any collision changes legal meeple choices or feature connectivity.

#### P1-R6 — The scalar vector is redundant, inconsistently normalized, and partly constant under normal use

In current-player canonical evaluation, `current_player_flag` is almost always 1. `phase_tiles` and `phase_meeples` are exact complements. `score_mine`, `score_opp`, and score difference are linearly redundant; remaining tiles and progress are redundant. Scores and score differences are not clipped despite comments describing roughly bounded ranges.

This is not likely the primary ceiling, but it wastes scarce dense-head capacity and makes architecture comparisons harder. More useful public information — bag counts and feature-component summaries — is absent while redundant scalars are retained.

#### P1-R7 — The transposition/legal-cache key is not a proven injective state representation

`string_representation` claims distinct game positions yield distinct strings, but the code itself documents a collision class: rotationally symmetric tile instances can have the same key while the engine's farm list ordering yields a different representative farmer action index. The collision detector is optional. The key also omits unseen bag composition and order, total-tile metadata, and detailed farm internals beyond tile description/edge signature.

Omitting order is correct for an information-set key but not automatically correct for a deterministic perfect-information search node; omitting remaining multiset is unsafe after any discarded/unplaceable draws. More generally, legal masks are cached by a semantic state key even though action indices can depend on engine object ordering.

**Risk:** serving the wrong legal mask, merging states with different action semantics or chance dynamics, and contaminating transposition statistics. Clearing between root moves fixes only cross-ply reuse, not collisions reached within one search.

### C. Action decomposition and policy parameterization

#### P1-A1 — A player's turn is split into tile and meeple nodes, but tile priors and leaf cutoffs evaluate the pre-meeple intermediate state

The engine split is legal and the search sign handling appears correct: the same player can act in consecutive tile and meeple phases without a spurious negation. The problem is evaluation. At a tile node, each prior is based on the hand-leaf delta immediately after placing the tile, before choosing whether and where to place a meeple. A simulation that first reaches that child also uses a value for this intermediate state.

Thus a tile placement whose main merit is an excellent meeple claim can receive a poor prior and poor shallow value. Conversely, a placement that looks good before the forced/optimal meeple decision may be overvalued. The real strategic action is hierarchical/composite.

**Risk:** systematic low-depth misordering exactly where priors matter most. This is likely to make "policy gains" depth-dependent.

#### P1-A2 — The 2511-way output is mostly invalid in every position and spends most model parameters on a coordinate lookup table

For W=25, 2500 outputs are tile coordinates/rotations and 11 are phase passes/meeple slots. During meeple decisions almost all 2500 tile outputs are invalid; during tile decisions all meeple outputs are invalid. The policy projection plus dense layer is about six million parameters, the majority of the network.

**Risk:** data inefficiency, weak transfer across board locations, fixed window size, and little capacity left for the value/representation problem. Legal-action scoring should be dynamic: encode the state once and score only legal placement/rotation or meeple candidates using shared parameters.

#### P1-A3 — Symmetric rotations are represented by multiple action indices but one shared child state

The MCTS detects aliases and folds priors into a canonical child, which is sensible. But policy labels retain an arbitrary representative action index (lowest sorted action in several paths), and rotation augmentation can map that representative to another legal alias. The model can fragment probability among aliases even though the search later sums them.

**Risk:** unnecessary label noise and capacity waste. Canonicalize symmetric tile rotations in the action set or train/evaluate on equivalence-class probability.

### D. Network architecture

#### P1-N1 — The network is nominally convolutional but the policy is not spatially equivariant

A 96-channel, six-block residual trunk is reasonable at the resource level. The dense flattened policy head defeats its strongest inductive bias. Nearly every output has independent weights to every projected board cell, so learning "place this rotation adjacent to this feature" must be relearned by crop coordinate.

**Risk:** the network may imitate common board layouts yet fail on uncommon translations and shapes. More parameters do not repair the wrong symmetry.

#### P1-N2 — The value head is far too small and unstructured for the hardest task

The default value path compresses a one-channel 25×25 projection plus scalars into a 64-unit hidden layer. An optional mean/max global pool adds global statistics but still discards component identity and relational structure. Meanwhile the policy head owns most parameters and gradients.

Value in this game depends on global feature connectivity, ownership majorities, bag feasibility, meeple-return timing, and chance. A 64-unit dense bottleneck over a lossy crop is a poor fit.

**Risk:** good policy imitation with an inert or brittle value head — exactly the architecture one would expect to produce offline correlation without useful sibling ranking.

#### P1-N3 — The trunk is being asked to discover graph algorithms from raster supervision with too little independent outcome data

The receptive field can nominally span the 25×25 crop, but nominal receptive field is not equivalent to learning union-find-like feature components and counterfactual merges. The data volume is only hundreds to low thousands of games per iteration, so outcome labels have hundreds to low thousands of independent terminal results, not one independent label per position.

**Risk:** apparent train/validation fit from correlated positions without robust strategic generalization. A small graph/component module would use the rules already known and reserve learning for valuation.

### E. Hand evaluator and value currency

#### P1-L1 — The same hand model supplies both priors and values, creating a double prior and a hard discovery ceiling

The heuristic-prior evaluator computes:

- value = `tanh(leaf(state, mover)/15)`;
- prior(a) = `softmax((leaf(child_a, mover)-leaf(state,mover))/5)`.

PUCT is therefore guided toward actions the leaf already likes and stops at values from that same leaf. This is not independent policy plus value evidence; it is one heuristic injected twice. Search can correct it only by reaching states where the same heuristic's later estimate reverses the error or by reaching terminal/exact play.

**Risk:** systematic blind spots are self-protecting. The policy flywheel can learn to allocate search around the leaf, but it cannot reliably discover a strategy the leaf dislikes at every finite-horizon prefix.

#### P1-L2 — "Score the current board as if the game ended now" is a strong but structurally biased base value

The base score awards unfinished cities, roads, cloisters, and current farms under final-scoring rules. This is useful as a static evaluator, but it treats current component control and current adjacent completed cities as if no future merges, steals, closures, or access changes occurred. It is particularly brittle for farms, where value is late, discontinuous, and merger-driven.

**Risk:** horizon effects and strategic passivity. Deep search with a fixed leaf may simply push the same end-now assumption farther out.

#### P1-L3 — Closure probabilities are hand constants unrelated to the actual bag, stage, geometry, or contest

The production schedule is approximately `{1 open: .5, 2: .2, 3: .05, else 0}`, with self and opponent bonuses capped around 8. `open_n` counts distinct empty neighboring cells, not exact compatible tile patterns, draw probability, access competition, or remaining turns. The same one-hole city receives the same closure probability early or late and whether the needed tile family is plentiful or exhausted.

**Risk:** large, state-dependent value error around exactly the tactical structures search prefers. Fixed `tau_p=5` then exponentiates these errors into priors.

#### P1-L4 — Closure/farm growth is credited to players who may not score the feature

For an incomplete city, each player with at least one meeple can receive the future closure delta; the production path does not gate the bonus by current majority. A minority player can therefore receive points it would not score if the city closed without another merger.

For farms, the production path similarly credits future adjacent-city growth to a player with a farmer even when the opponent has strict majority. A majority-aware experimental option exists but is off in the described production configuration.

**Risk:** contested-feature values can be wrong in sign, not merely noisy. Because both sides' bonuses are subtracted, equal false credits can erase the strategic value of control margins.

#### P1-L5 — The evaluator appears to contain a rule-level farm scoring error: one city is globally deduplicated across distinct farms

`counted_growth_cities` is shared across all of a player's farms, with the comment that the same city adjacent to two farms "shouldn't be paid for twice." Under Carcassonne farm scoring, each separately controlled field scores each adjacent completed city. The same city can legitimately score for two distinct fields controlled by the same player.

Deduplicating repeated farmers on the *same* field is correct. Deduplicating one city across *different* fields is not.

**Risk:** systematic undervaluation of multi-field city geometry and of plays that preserve or capture multiple separate fields around a city. This should first be confirmed with a tiny engine-rule fixture; if confirmed, it is a correctness bug, not a tunable heuristic choice.

#### P1-L6 — Meeple return, timing, and road completion are mostly handled only after the fact

Road completion has no anticipation bonus in the production leaf because point value often does not change, but completion returns a scarce meeple. City/chapel closure also returns meeples; the default anticipation term prices score delta but not return timing. A free-meeple lookup curve gives a static liquidity value after a return occurs, not an estimate of the probability and timing of that return.

**Risk:** search undervalues setup moves whose payoff is recovering a meeple beyond the current horizon. This can be decisive in midgame tempo and denial.

#### P1-L7 — Caps, lookup curves, quantization, and fixed temperatures introduce discontinuities and arbitrary scale coupling

Important constants include:

- `value_norm=15`;
- prior `tau_p=5` raw points;
- closure caps around 8 per side;
- a free-meeple curve `[-10,-5,-1.25,0,2.5,3.75,5,6.25]`;
- optional integer rounding versus float leaf;
- pooled minimum visits = 2.

The marginal value of one meeple in that curve is non-smooth and even changes pattern around four free meeples. Caps make additional real stakes invisible. A fixed prior temperature has different sharpness at different phases and score scales. Tanh then compresses values differently from priors.

**Risk:** brittle local optima and parameter "peaks" that are really noise or compensation among arbitrary scales. Constants need either derivation/calibration or robust plateau evidence.

#### P1-L8 — The optional bag-aware closure logic is too permissive to be an oracle and is not active in the default champion

The bag-aware path counts broad city-bearing supply and uses feasibility/Hall-style checks, but it does not fully model all terrain matches, placement competition, draw timing, opponent consumption, or whether a compatible tile can legally reach the feature. It is useful as a necessary-condition gate, not a closure probability.

**Risk:** enabling it could remove impossible bonuses but should not be interpreted as solving tile counting. Leaving it off preserves a known information blind spot.

### F. Search mechanics and imperfect information

#### P1-S1 — Root-determinization PIMC does not produce a valid observable-state policy value

Each sampled deck is searched with full knowledge of its future order. Even though a fresh tree is used per deck, future decisions in that tree can adapt to hidden future draws. Pooling only the root does not force one common contingent policy across worlds.

**Risk:** optimistic values for plans that require mutually incompatible future responses. This can persist or worsen with more search, so high-depth strength need not validate the method.

#### P1-S2 — `k=4` is extremely small for a high-variance without-replacement bag

Four full-deck samples per move cannot characterize tail risks, rare required tiles, or action values whose sign depends on several future draws. Spending 688 searches inside each world may be inferior to more observable chance samples with shallower continuation, especially with a strong prior/leaf.

**Risk:** large move-to-move Monte Carlo error and seed sensitivity masquerading as strategic signal. The fixed `k×sims` split should be measured rather than inherited.

#### P1-S3 — Pooled-Q is a selection-biased conditional mean because unvisited worlds contribute nothing

For action `a`, the wrapper sums `W` and `N` only in determinizations where that action was visited. An action omitted in a world is "neither signal nor noise." But omission is not random: PUCT is less likely to visit an action where that world's priors or early values are bad. The resulting Q estimates `E[value | action got search attention]`, not `E[value]`.

The minimum pooled-visit floor of 2 can be satisfied by two visits in one favorable world. There is no per-determinization coverage requirement or uncertainty penalty.

**Risk:** brittle, underexplored actions can look best precisely because adverse determinizations are missing. This is a likely source of isolated apparent gains.

#### P1-S4 — The final action rule is inconsistent and high-variance

The single-search champion can select by visit count. Generic `best_action` selects Q then N. The fair wrapper ignores `cfg.final_select` and selects pooled Q. Training records pooled visits. These are three different policies.

Q-first selection with only a two-visit eligibility floor is vulnerable to leaf noise and winner's curse. Visit selection is more robust but has different semantics. There is no principled reason the deployed action, distillation target, and evaluation policy should disagree.

#### P1-S5 — Transposition statistics are stored on nodes, but PUCT needs edge-local visits and values

If a state is reachable through multiple parent actions, the child node's `N/W` is shared. PUCT then uses those node visits as if they were visits on each incoming edge. One parent's exploration can suppress or inflate another parent's edge. The object also retains only limited parent metadata despite being a DAG.

True state-value sharing can be valid, but action-selection counts must remain edge-local. The risk is worse when key collisions or hidden-state abstraction merge states that are not truly equivalent.

#### P1-S6 — The legal-cache/transposition abstraction has already shown action-semantic collisions

The code comments describe a stale-mask bug where symmetric rotations share a string key but the engine chooses a different farmer-corner representative. Clearing before a new root fixed one observed path, but the same abstraction is still used within search and for transposition merging. The collision checker is diagnostic-only and off by default.

**Risk:** a search can assign a prior/visit/value to an action index whose meaning differs on another engine instance of the "same" keyed state.

#### P1-S7 — Candidate and champion searches use different batching algorithms

The net-prior candidate uses within-search batches and virtual loss for latency, while the heuristic champion remains serial to preserve byte identity. Virtual loss changes which leaves are selected; it is not just faster transport. Thus a head-to-head can confound policy source with a different search approximation.

**Risk:** a real network gain can be hidden by batching loss, or a batching diversification gain can be misattributed to learning. At least one equal-algorithm control is required.

#### P1-S8 — Tree reuse is mostly disabled, discarding useful computation and hiding whether values are stable

The agent usually clears the tree each move. Stochastic draws require care, but the observed child after a tile/meeple action is a valid subtree/information-set state. A correct chance-aware tree can retain compatible statistics and spend the saved budget on uncertainty.

This is not the main correctness issue, but at the stated compute budget it is an avoidable strength cost.

### G. Distillation and self-learning loop

#### P1-D1 — The policy target does not match the teacher's action policy

The fair teacher **plays by pooled Q** but records **pooled visit counts** as the policy target. The code explicitly notes that `argmax(policy)` need not equal the played move. In standard AlphaZero, visits are a sensible improved policy because the search and action-selection rule are built around them. Here visits are an allocation trace from four separate clairvoyant trees, while the deployed decision is another statistic.

**Risk:** the student is trained to imitate where the teacher searched, not what it chose or what has highest estimated fair value. Iterative replacement can therefore drift even with perfect policy loss.

#### P1-D2 — The learned value is trained but deliberately barred from search, so the loop is only weak policy iteration around a fixed evaluator

Stage 2 uses net policy priors and the frozen hand leaf as value. This avoids a bad learned value destroying play, but it also removes the main route by which outcomes could correct the hand evaluator. The value loss still updates the shared trunk, so the loop is not perfectly severed: outcome gradients can indirectly alter policy features. That indirect, uncontrolled path is not a substitute for a validated value blend.

**Risk:** the loop converges to a policy that best allocates a finite fixed-leaf search, then plateaus. Any apparent "self-learning" is expected to be budget-specific and may vanish when the search is deep enough for the heuristic-prior teacher to recover.

#### P1-D3 — The outcome target is heavily saturated and has far fewer independent labels than rows

Every position in one game receives the same final `tanh(score_diff/15)` up to sign. A 100-ply game creates roughly 100 rows but one independent stochastic outcome. With hundreds or low thousands of games and a seven-million-parameter net, ordinary row-level validation can look much stronger than true generalization. The `/15` target also pushes many ordinary outcomes close to ±1, discarding margin resolution.

**Risk:** overfit value/trunk representations and misleadingly low MSE/correlation. Holdouts must be by complete game seed and evaluated on fresh search strength, not random rows.

#### P1-D4 — Fair distillation/self-play has essentially no deliberate policy exploration

The fair emitter uses deterministic pooled-Q play; no root Dirichlet noise and no visit-temperature sampling are present. Diversity comes from actual deck seeds and sampled determinizations, not from exploring plausible alternative actions. Once the learned prior narrows, the loop can stop generating corrective examples for actions it suppresses.

**Risk:** self-confirming policy collapse without necessarily low entropy, and inability to recover discarded strategies. Exploration should exist in data generation while deployment remains deterministic.

#### P1-D5 — There is no promotion gate; an entropy floor is not a strength gate

Each new iteration can become the next generator without first beating the frozen champion or last promoted model at deployment depth. The entropy guard detects one failure mode only. A weak broad policy passes; a genuinely strong sharp policy might fail.

The replay window eventually ages out early teacher data. Without a fixed anchor fraction or promotion arena, errors can compound.

**Risk:** closed-loop drift, cyclic play, and loss of absolute strength while chain-relative or offline metrics improve.

#### P1-D6 — Exact endgame actions are thrown away as policy supervision

When the marginalized solver takes over, `last_pooled_visits` is set to `{}` and the row becomes value-only. These are the highest-confidence action labels in the system. At minimum, the optimal-action set or chosen optimal action could train the policy head, with separate weighting if deterministic one-hot labels are undesirable.

**Risk:** wasting scarce ground truth and making the policy weakest exactly near the only solved region.

#### P1-D7 — Forced moves and dummy auxiliary labels can distort the dataset

Forced moves are kept as one-hot policy examples, potentially a large fraction of meeple/pass decisions that teach little. The fair emitter writes zero ownership tensors and relies on `--aux-weight 0`; a configuration mismatch would train false labels. Even with the weight off, these rows occupy IO and batching.

**Risk:** diluted informative policy signal and brittle dependence on launch flags.

#### P1-D8 — Replay mixing and validation are file-count based, not position-count based, and can leak duplicates

Warmstart files are sampled with replacement to approximate a target fraction by **file count**, although game shards have different numbers and kinds of positions. The resulting duplicate paths are then split into train and validation lists; the same source file can plausibly occur in both sets if the splitter does not deduplicate first.

**Risk:** inaccurate mixture weights and optimistic validation. Validation should use unique held-out game seeds and never duplicate an underlying shard across splits.

#### P1-D9 — Several "trustworthy" offline diagnostics are self-referential

Search-Q, interior-node Q, sibling rank, and policy cross-entropy can all improve relative to labels generated by the same search/leaf while online strength worsens. `_value_outcome_corr` is only literally outcome correlation when stored targets are outcomes; with search-value or residual data it measures target imitation. The code partly documents this for residuals but not all modes.

**Risk:** optimizing a ruler rather than the game. Offline metrics are useful for debugging representation and fit, but no offline-to-online inference should be accepted without a paired production-depth game test.

#### P1-D10 — Learned and hand components are changed together through a shared trunk and changing data distribution

Even in "policy-only" search, the trainer applies value loss to the same trunk used by policy. Replay composition changes by iteration, and the generator changes when the prior changes. Consequently, a checkpoint difference is not a clean policy-distillation intervention; it combines policy imitation, outcome representation pressure, and distribution shift.

**Risk:** causal ambiguity. Small ablations must freeze the trunk or value loss when asking whether policy distillation itself improves strength.

### H. Evaluation design implied by the code

#### P1-E1 — Fixed-depth, internal head-to-heads are necessary but not sufficient

Deck-paired games are the right variance reduction. However, same-lineage agents share the same engine abstractions, crop, leaf, and PIMC error. Cross-play against out-of-lineage agents, exact bands, and humans is required to detect common-mode weakness.

#### P1-E2 — Parameter sweeps are vulnerable to winner's curse at the stated sample sizes

At n=100–400, a lone setting beating neighbors by 1–2 standard errors is expected noise, especially after searching many constants, leaf variants, and iterations. Pre-registration, neighbor consistency, and fresh-seed replication are essential.

#### P1-E3 — Low-depth policy gains are not evidence of a stronger deployed agent

The architecture makes a specific prediction: a better prior can matter greatly when search is shallow and vanish when the fixed-leaf teacher has enough visits. Every learned-policy claim must therefore include a production-depth transfer test using the same fair wrapper and batching algorithm.

---

## 2. PREDICTION OF THE SYSTEM'S STRENGTH CEILING

### 2.1 What it should be good at

I expect the production classical agent to be genuinely strong at:

- immediate scoring and closure tactics;
- common meeple-economy patterns captured by the hand curve;
- shallow denial visible in the leaf;
- exact last-two-tile play;
- common board shapes represented inside the crop;
- spending a large fixed budget efficiently on moves already favored by the heuristic.

The heuristic-prior design is a credible way to turn a competent evaluator into a strong tactical searcher. Its engineering quality should not be confused with the validity of the self-learning claim.

### 2.2 Where the ceiling comes from

#### Ceiling 1: the evaluator's systematic errors are reinforced twice

Because the same leaf generates both Q cutoffs and priors, a line the leaf dislikes receives fewer visits and, when visited, terminates in a value that still dislikes it. This creates a basin of attraction. More simulations improve tactical consistency within the heuristic's worldview but do not guarantee escape.

The most damaging likely slices are:

- contested city/farm majority;
- multi-field adjacency to the same city;
- long-horizon farm mergers;
- meeple recovery timing;
- bag-dependent closures;
- moves whose value is realized only after the subsequent meeple decision.

#### Ceiling 2: fair search is not solving the fair game

PIMC can prefer a root action because each sampled world contains a different clairvoyant continuation that makes it work. The real agent must choose one policy contingent only on observed draws. This creates a ceiling that more per-world depth can fail to remove.

At `k=4`, sampling and conditional pooling add a second, noisier ceiling: the chosen move may be the winner of four biased, sparsely covered estimates.

#### Ceiling 3: the neural model cannot represent all public strategic facts

The default model never sees the remaining tile multiset. Both default and sighted variants have weak field-component identity. The crop can omit state and legal actions. No amount of training can recover facts that are absent or aliased.

#### Ceiling 4: the flywheel has no reliable mechanism for improving the value basis

A learned prior can outperform the hand prior at one budget by allocating visits better. As the hand-prior search deepens, that advantage should shrink unless the learned policy encodes genuinely useful long-range patterns. Because the value remains frozen and training targets come from the same fixed-leaf searches, robust iteration-over-iteration growth should plateau, oscillate, or overfit to generation depth.

### 2.3 Concrete prediction

Before seeing results, my expectation is:

1. Distillation will produce attractive offline policy metrics and may beat the teacher at low or medium search budgets.
2. The gain will be fragile across depth, batching mode, and fresh seeds.
3. At the full production budget, most apparent iteration peaks will collapse toward noise unless a representation change accidentally captures a real missing heuristic.
4. Learned value-only replacements will be much weaker than the hand leaf unless given bag/component features and substantially more independent targets.
5. Correct classical fixes — chance handling, farm-majority scoring, composite tile/meeple evaluation, and bag-aware features — are more likely to yield the next durable strength gain than simply extending the present policy-only loop.
6. The current system cannot support a superhuman claim even if it wins its internal ladder, because there is no human anchor and the fair-game approximation is unvalidated.

---

## 3. WHAT I WOULD BUILD INSTEAD, OR CHANGE FIRST AT THE STATED RESOURCES

I would run two tracks, with the strongest-agent track allowed to remain mostly classical and the learning track required to earn its way into deployment.

### 3.1 First: freeze scaling and repair the game interface

1. **Use the full legal board, not a lossy crop.** The engine grid is only 35×35. A full-board tensor is feasible on consumer hardware if the policy head is made dynamic. At minimum, use a bounding box with guaranteed margin and fail on *any* dropped legal action, never silently remove moves.
2. **Make the observation Markov for public information.** Include the exact remaining count of every tile type in production, not under an experimental "sighted" switch.
3. **Canonicalize action equivalence classes.** Symmetric tile rotations leading to the same state should be one policy action or one explicitly summed class.
4. **Replace semantic-state legal caching until injectivity is proven.** Key the cache by a collision-free canonical serialization that includes all fields affecting legality and chance, or by immutable engine-state identity within a search. Keep edge action semantics separate from transposed state values.
5. **Add rule fixtures for every leaf component.** In particular, contested majority and one city bordering multiple separately controlled farms.

These changes are cheap compared with another training campaign and protect every later measurement.

### 3.2 Second: search the stochastic observable game

The clean design is an explicit chance-aware tree:

- Decision nodes are keyed by the **observable state**: board, scores, meeples, phase, current revealed tile, and remaining bag multiset.
- After the turn completes, a chance node draws the next tile type with probability `remaining_count / remaining_total` and removes it without replacement.
- At high branching, sample one chance outcome per simulation rather than expanding all 32 types; accumulate edge-local statistics.
- Downstream decisions see only draws revealed along that simulation. They do not know the rest of a pre-sampled future deck.
- Use information-set/node values shared only when the complete observable state matches; keep `N/W` on parent-action edges.
- Retain the exact marginalized solver in the tractable endgame band.

A pragmatic intermediate version is **re-determinizing ISMCTS/chance sampling per simulation**, not four complete decks per root. It should be validated against the exact K≤2 solver before deployment.

This directly addresses strategy fusion and uses each simulation to sample uncertainty, rather than spending most of the budget refining four clairvoyant worlds.

### 3.3 Third: make tile and meeple policy hierarchical but value-consistent

Keep separate heads if convenient, but do not evaluate a tile action as though the meeple decision did not exist.

Options, from cheapest to best:

1. For hand priors, score a tile placement by a shallow backup over legal meeple responses — e.g. max or search-weighted value after the meeple action — rather than the pre-meeple afterstate.
2. Train a tile head to predict the value/visits of the complete turn and a meeple head conditional on the selected tile.
3. Represent each legal complete-turn option `(tile placement, rotation, meeple/pass)` and use a factorized scorer so the combinatorics remain manageable.

The search can still expose intermediate nodes internally; the prior/value target should correspond to the player's actual decision opportunity.

### 3.4 Fourth: use a component-aware, dynamic-action model under roughly the same parameter budget

I would not simply enlarge the present ResNet. A feasible ~7M model is:

- a full 35×35 tile CNN or sparse tile encoder;
- explicit city, road, and field component nodes built by the rules engine;
- component features: owner counts/margins, open boundary types, tile/shield count, adjacent completed/incomplete city IDs, frontier cells, compatible remaining tile counts, and expected meeple return;
- two or three rounds of message passing between tile cells and feature components;
- a global/bag embedding;
- a **shared legal-action MLP** that scores each legal tile placement from the target cell embedding, rotation/tile embedding, affected component embeddings, and global state;
- a small meeple-slot scorer for the last tile;
- value heads for win/draw/loss and score difference, optionally distributional, plus component ownership/completion auxiliaries.

This architecture uses known game structure rather than asking six conv blocks to rediscover union-find. It is translation-compatible, variable-board compatible, and spends parameters on valuation instead of a 6M coordinate table.

### 3.5 Fifth: retain the hand leaf as a bootstrap, not an untouchable authority

1. Correct rule errors and add bag/component features to the hand evaluator.
2. Train the learned value on **fresh game outcomes** and exact endgame values, with game-level holdouts.
3. Initially use the net as a residual or blend: `v = hand + alpha * residual`, clipped only at the final search interface.
4. Increase `alpha` only after production-depth online gates show improvement in several strategic slices and against out-of-lineage opponents.
5. Keep the corrected hand leaf as an anchor and fallback, not as the permanent value that defines every future target.

The primary value utility should be stated. My preference for match play is win/draw/loss probability as primary, with expected score margin as an auxiliary/tiebreak head rather than a saturated single target.

### 3.6 Sixth: turn the loop into gated policy iteration

- Data generation may use root noise and visit-temperature sampling; deployment does not.
- Train targets must match the intended policy. If deployment chooses by visits, train visits. If deployment chooses by expected Q, train a calibrated advantage/value-improvement target, not raw search allocation.
- Include exact-solver optimal actions as policy labels.
- Keep a fixed fraction of teacher, exact, and diverse historical data indefinitely.
- Promote a checkpoint only after it passes:
  1. fresh-seed production-depth paired games versus the last promoted agent;
  2. a fixed frozen champion;
  3. at least one out-of-lineage search agent;
  4. exact-endgame regret and targeted farm/bag slices.
- Use sequential confidence bounds to stop weak candidates early.

A self-learning flywheel is plausible only after the learned value is allowed to correct the evaluator and survives those gates. The present prior-only/frozen-value loop is better described as iterative search-policy distillation.

### 3.7 Establish a human anchor now, not after the agent is "done"

At low cost, assemble:

- a fixed set of annotated positions from strong human games;
- blinded move-choice comparisons by strong players;
- a small set of full paired games against the strongest available human opposition, using the same public-information rules and clocks;
- an external/open-source or independently implemented baseline if available.

Human move agreement is not strength, but human head-to-head is necessary for the final claim. Internal Elo remains an engineering metric.

---

## 4. THE FIVE CHEAPEST MEASUREMENTS I WOULD RUN FIRST

### M1 — State/action integrity replay: crop loss plus key/cache collisions

**Design.** Replay at least 1,000 fixed-seed games from the current champion/self-play distribution with the already implemented window audit and legal-cache collision checker enabled. Record per decision:

- any placed tile or meeple outside the crop;
- number and fraction of legal actions dropped;
- whether the dropped action is the champion's choice under a larger/full window;
- state-key collisions with differing legal masks;
- invalid-visit/action-alias incidents;
- stage, board span, and farm stakes when each occurs.

For a cheap counterfactual, run the same recorded states with W=35 or a no-crop legal encoder and compare legal sets and chosen moves without retraining.

**Decides.** Whether the current wrapper is a valid representation of the game at all. Any non-negligible dropped-action rate, or any collision that changes a legal mask/action meaning, is a stop-the-line correctness issue. Zero events over a large, adversarial state set would substantially lower P1-R1/R7/S6.

**Rough cost.** CPU replay only; hours, not a training run.

### M2 — Leaf differential oracle suite, targeted at rule and horizon errors

**Design.** Build small hand fixtures and harvest several hundred K≤2 or otherwise solver-tractable positions in these strata:

1. contested cities with self majority, tie, and minority;
2. contested farms with different farmer margins;
3. one completed/incomplete city adjacent to two distinct fields controlled by the same player;
4. one-hole features where compatible tiles are exhausted versus abundant;
5. road/city closures whose main value is meeple return;
6. farm-merge threats.

For every legal action, compare current leaf delta/rank with marginalized exact value where available. Report top-action regret, Kendall rank, and sign error by slice. First include direct engine-rule assertions for the multi-field-city case.

**Decides.** Whether P1-L4/L5/L6 are real and material, and whether the hand leaf is the dominant ceiling. A confirmed rule mismatch should be fixed regardless of aggregate Elo; large exact regret in one common slice justifies component-aware evaluation before more distillation.

**Rough cost.** Mostly unit fixtures plus existing exact solver; a few CPU-hours.

### M3 — Composite-turn prior audit

**Design.** On a stratified sample of tile-phase roots, compute for every legal tile placement:

- current prior score: leaf immediately after tile placement;
- composite score: best or search-weighted leaf after all legal subsequent meeple/pass choices;
- exact/deeper continuation value where cheap.

Measure rank correlation, top-1 disagreement, and regret, especially when a farmer or scarce last meeple is available. Then run a small paired n≈100 game test replacing only tile priors with the composite score, keeping value, chance wrapper, and total leaf-call/wall-clock budget controlled.

**Decides.** Whether the phase split is merely representational or actively poisoning low-depth search. A large offline mismatch plus online gain from the one-change ablation would confirm P1-A1.

**Rough cost.** One extra legal-meeple sweep per sampled tile action; modest CPU.

### M4 — Determinization action-value matrix and independent-world regret

**Design.** For 100–200 representative roots, sample at least 32 independent determinizations. Run a small fixed search per world and save the full matrix:

- action visited/not visited;
- visits and root-POV Q;
- action rank per world.

Compare:

1. current conditional pooled-Q;
2. pooled-Q requiring minimum coverage in several worlds;
3. mean with an explicit pessimistic/neutral estimate for unvisited worlds;
4. a robust lower-confidence rule;
5. observable chance-sampling/ISMCTS prototype;
6. exact marginalized values in K≤2 positions.

Finally evaluate each selected action on a **fresh, independent** set of determinizations or rollouts not used for selection. Report selection regret, coverage, variance, and K-sensitivity.

**Decides.** Whether P1-S1/S2/S3 are theoretical concerns or current move errors. If current picks have high fresh-world regret, low cross-world coverage, or worsen with deeper per-world search, the PIMC wrapper must be replaced before any superhuman claim.

**Rough cost.** Offline root analysis; comparable to a few hundred games but highly parallel.

### M5 — Flywheel causal test: target alignment and depth transfer under identical search mechanics

**Design.** Freeze several checkpoints, including the teacher and latest iterations. For each:

- measure how often pooled-visit argmax disagrees with pooled-Q played action and the Q regret of the visit argmax;
- evaluate net priors versus hand priors at generation depth, an intermediate depth, and full production depth;
- force the same batching/virtual-loss mode and same wall-clock budget on both sides in one control;
- use fresh deck pairs and at least n=200 for the production-depth comparison;
- include a fixed out-of-lineage opponent, not only parent/child chain play.

Success requires a replicated gain that remains positive at production depth and against the frozen/out-of-lineage anchors. An isolated low-depth or one-checkpoint win is not success.

**Decides.** Whether the current loop is learning transferable strategy or only a budget-specific search-allocation surrogate; whether pooled visits are a valid target for pooled-Q behavior; and whether batching is a hidden confound.

**Rough cost.** No new training, only targeted arena games. It is the most expensive of the five but far cheaper than another multi-iteration campaign.

---

## Bottom line before seeing any experiments

The system may already be a strong game-playing program, but its present architecture gives me no reason to expect open-ended self-learning. The most likely next durable gains are not "more iterations." They are:

1. prove the wrapper is lossless and collision-free;
2. correct contested-feature and multi-field farm valuation;
3. evaluate complete tile-plus-meeple decisions;
4. replace four-world PIMC with observable chance search;
5. give any learned value the public bag and component graph, then admit it only through production-depth gates;
6. establish a human anchor.

If those changes still leave a learned value unable to improve a corrected chance-aware search, I would pursue the superhuman-agent goal primarily through classical search and engineered component evaluation. Learning is a means, not the objective.

---

# PART II — CONSOLIDATED FACTS

## Evidence standard

The record supports three distinct levels of statement:

1. **Established:** directly measured with an appropriate ruler and adequate replication for the stated scope.
2. **Suggested:** moves belief but does not identify the mechanism or support a broad closure claim.
3. **Not established:** never tested, tested under the wrong information regime, or tested only through an offline, shallow, stale, or underpowered proxy.

A fair kill of an implementation is not automatically a kill of the idea. Conversely, a clean positive result can confirm a design flaw rather than validate the larger program.

## F1 — The current production agent is a classical-search champion with learned components optional

The declared champion is `HeuristicPriorAgent`: PUCT with `c=1.5`, heuristic priors formed from `softmax(Δleaf/τ=5)`, the float curve125 leaf, and about 2,750 simulations. Fair deployment is root-determinization PIMC at k4×688 with pooled-Q selection and exact marginalized K≤2 handoff (`PRODUCTION.yaml`).

The major search flips are real. The PUCT-prior rebuild beat the h6400 configuration by **+148.2 Elo, z=10.17, n=400** at verified equal wall-clock (`puct_c1.5_tau5_float_visits_s2750_vs_h6400_k2`), and a round-robin rejected a simple rock-paper-scissors explanation. Tree reuse added **+39.3 Elo, z=2.81, n=400** at equal wall-clock, but it is scoped to the clairvoyant/development regime because fair PIMC does not retain one fixed future. Curve125 was confirmed in both regimes: clairvoyant **+66.8 Elo** on a fresh n=400 band; the fair confirm `c5_confirm_curve125_fair_vs_h800_k2` reports **+120.8±11.6 versus h800**, compared with the D0 reference at +81.4, with the paired direct contrast reported elsewhere as roughly +49 Elo.

The important conclusion is architectural: the strongest agent is already primarily a hand-designed evaluator plus search. The learned policy is not required for the current champion and has not yet produced a deep, replicated promotion over it.

## F2 — The trust base improved, but several early results were contaminated or circular

The project has a strong correction culture, and it has needed it.

- A May farm-connectivity defect made farm regions start-dependent in about 2.2% of games.
- The June 2 audit found a terminal/leaf farm-scoring overcount in about 17% of scored farms and rotational-transposition visit duplication in about 20% of decision nodes. Both were fixed and specifically verified (`foundational_audit_2026-06-02.md`; `CORRECTION_PLAN_2026-06-02.md`).
- The `won_by_champ` field had inverted semantics; the team caught it through margin-sign contradictions and verified 0/312 disagreement after correction.
- The old h6400 offline ruler correlated **0.995** with the hand leaf. Pre-1 July claims that a model approached or beat that ruler were partly circular. The exact marginalized K≤2 solver over 1,119 roots is the first clean local ruler.
- The fair wrapper leaked hidden-order information until 14 July: reshuffling began from the true hidden deck order, and 19% of audit trials changed move. Canonical sorting fixed the leak. Pre-fix fair rows are therefore mildly clairvoyance-tinted and not exact baselines for the corrected agent.

These corrections increase confidence in the clean-era measurements, but they also make a release-grade semantic suite and executable manifest mandatory before the human benchmark.

## F3 — Fair strength scales strongly with simulations and is not saturated

Against a fixed h800 rung, the fair ladder rises coherently:

- 800 total simulations: **+27.9 Elo**
- 1,600: **+61.4 Elo**
- 2,752: **+81.4 Elo**
- 5,504: **+149.3 Elo**

Rows: `fair_ladder_s{800,1600,2752,5504}_vs_h800_k2`.

This is the cleanest open strength lever in the record. It does not prove that an implementation port will automatically produce +40–90 Elo at equal wall-clock, because throughput, latency, cache behavior, and search quality must be measured. It does show that additional fair search has substantial headroom and should receive more engineering attention than another unqualified model sweep.

At fixed total budget 2,752, the determinization-width bracket is also coherent: k4×688 is the measured optimum; k2 is second; k16≈k8; k32 is clearly worse. That fairly kills "just use more determinizations" for the current PIMC and budget. It does not validate PIMC against the correct public-state game.

## F4 — The clairvoyance tax is real, large, and agent-dependent

For iter8@s200, the measured fair-versus-clair gap was about 26.6 Elo and statistically weak. Generalizing that as a universal discount was wrong. For the PUCT champion, screens around `fair_puct2752_kd8_*` showed clairvoyant roughly +205 versus fair roughly +49, implying a tax around 156 Elo for that configuration.

Some of this is intrinsic value of information. Some may be approximation error from PIMC, shallow per-world search, action coverage, or strategy fusion. The record does not separate them. Clairvoyant ladders are therefore useful screens only; the fair corrected agent is the ruler of record.

## F5 — The classical line has produced multiple large, depth-robust gains

The strongest counterexample to premature closure is the v2.8 meeple-economy term. It had been discarded after an n=20 screen, then later measured at about **+179.5 Elo at s200** and **+94.9 at s800**. v2.9's nonlinear meeple-liquidity curve added **+55.2 at s200** and **+64.3 at h6400** against the actual v2.8 production configuration (`v291_THRONE_bmild_cap8_vs_v28prod_*`).

The PUCT rebuild, curve125, k4 fair configuration, and fair depth scaling then added further real strength. Together they show that search and hand-evaluator work were not exhausted when earlier reviews said they were. The lesson is not that every remaining heuristic will work; it is that architecture and bundles deserve tests proportionate to the effect size being claimed.

## F6 — Learned value is inert or harmful at the tested scale, but the scope guard matters

The strongest value evidence is non-circular and pre-registered.

- A pure neural leaf was catastrophic, around −800 Elo; a later fair local sibling lost 0–100.
- In the canonical-AZ M2 cell — sighted representation, global-pooled value, widened target, FPU=0.6, value fully driving the leaf — exact K≤2 sibling rank remained **τ 0.018→0.023** over five iterations, versus **0.615** for the hand leaf. The conversion sweep had 0/6 cells clear 2σ and became harmful at weight (`m2_*`).
- C-cheap v1, which replaced the leaf, lost **0–100**. C-cheap v2, a residual that passed an offline gate, produced only **+9.2 Elo** online against a +35 gate.
- The Gate-B crater was partly a search-integration bug: FPU=0.6 restored the value-driven agent from 0.265 to **0.496**, parity, never superiority (`m3_confirm_*`).

This fairly kills the tested recipe at roughly 7M parameters, five iterations, and ≤200 simulations. It does not prove that all learned value is impossible. Capacity was not cleanly tested, public-state expected value was not trained, and no model targeted determinization disagreement or residual regret. Any final value attempt must first beat the hand leaf on local public-state sibling regret and calibration.

## F7 — Offline ranking and online strength have dissociated in both directions

The packet repeatedly demonstrates that offline improvement cannot be promoted by inference.

- Explicit bag/farm features reduced held-out regret by 20.5% with a shuffled-input control collapsing to zero, yet later fair online conversion was null.
- CL-034 reduced held-out regret by 41% and washed out under s200.
- v2.10 cap6 improved the exact solver-screen rank from τ 0.615 to 0.648, replicated, then produced **+4.3 Elo, z=0.45, n=800** in games.
- Bag-close was **−6.1 Elo** online.
- The strongest clean tempo ranker remained about four times weaker than the hand leaf on the exact ruler.
- High-gap distillation learned offline and lost about 64 Elo in games.

The reverse direction also occurs: search changes and evaluator terms can win games without looking impressive on the chosen offline ruler. Every future route must therefore have a production-depth, equal-wall-clock game gate after any local screen.

## F8 — Low-depth policy gains have vanished at high depth twice

The deepteacher lineage showed **+82.8 Elo, z=3.48 at s200**, then **+8.0, z=0.34 at s800** on the same networks and decks (`deepteacher_WASHOUT_*`; `_SEALED_*`). The newest flywheel showed **+88.7 at k2×200**, then **+1.7, z=0.07 at k4×688** on the same 100 decks (`eval_iter16_vs_rodv2iter02_PROD_DEPTH`).

This is now a governance rule: a shallow policy gain is provisional until it survives deployment depth. The leading mechanism is search acceleration without asymptotic value improvement, possibly amplified by budget-specific visit targets and pooled-Q coverage bias. The mechanism remains testable with root replay; the production verdict does not depend on identifying it.

## F9 — The newest flywheel was operationally stable and did not demonstrate compounding

Stage 1 increased top-1 agreement from about 0.32 to **0.60**, with a teacher-versus-teacher ceiling around 0.75. At production simulation count, distilled priors versus champion priors — a single-variable swap — finished **100–100–0**, margin +1.87 (`distill_s1_confirm_n200`). That is a point estimate of parity at equal simulations, not equivalence and not equal compute.

Stage 2 ran 17 unattended iterations over about 25 hours with zero crashes. Against the fixed out-of-lineage anchor at k2×200, the eight measured checkpoints were:

**+17.4, +8.7, +10.4, +49.0, +26.1, +88.7, +15.6, +17.4 Elo.**

The curve is non-monotone. Every adjacent deck-matched step was below 2σ. Stable operation and non-collapse are real engineering achievements; they are not evidence of autonomous improvement.

## F10 — The it16 breakout was correctly refuted

Three independent facts support the retraction.

1. **Pre-registered continuation rule.** The rule set before it20 landed required it16→it20 ≥ +1.5 points/deck to continue. The observed change was **−3.43±1.87**, so the team correctly took Plan B.
2. **Production-depth washout.** On the same decks, it16 changed from +88.7 at k2×200 to **+1.7 at k4×688**.
3. **Fresh-band failure with a contemporaneous control.** On band 13.2e9, it16 was **−3.5 Elo, z=−0.14**; the cross-band discrepancy was z=2.60. it20 reproduced its tie-level result (+17.4→+26.1; pooled +21.7, z=1.25), and the deck-matched it16−it20 contrast reversed sign across bands.

Pooling the selected original half with the fresh half to report +41.9/z2.40 would assume a stable estimand that the replication test rejects. The `REFUTED` stamp is appropriate.

One nuance remains. Under a rough independent-look approximation, a 3.65σ maximum among eight points is still unusual, so "pure random noise" is not the only plausible mechanism. A small, band-sensitive shallow effect plus winner's-curse selection is credible. That nuance does not reopen the result: no robust gain survived the only depth that matters.

## F11 — Several "classical closures" were only closures above a large effect threshold

At n=400, 1σ is about ±17.5 Elo, so a clean two-sided 2σ confirmation naturally favors effects around 35 Elo or larger. That is suitable for finding large levers, but it can mislabel smaller composable effects as "nothing."

- Term F's best cell was **+20.9 Elo, z=1.50 at n=100** against a pre-registered ≥+35 and z≥1.5 gate. It failed the large-effect gate; it was not shown to be exactly zero.
- Closure schedule was tested only as a global ±20% scalar in n=100 screens, with +10.4 and +34.9 point estimates.
- Win-shaping used stage-independent `tanh(margin/T)` transforms. The aggressive +18.3 screen failed fresh replication at −27.9. That fairly kills that transform, not stage-dependent win probability.
- Rotation augmentation was tested once, unpaired, n=400 per arm versus a common opponent; the difference was roughly −8.9±24.
- Term R was strongly and monotonically harmful and is fairly killed.
- Exact endgame depth increased score margin but not win rate at any tested depth.

The record therefore supports a powered bundle test and a stage-dependent utility audit, not indiscriminate reopening of every leaf term.

## F12 — The external endpoint has never been measured, and the intended harness is stale

No public bot in the packet is a credible frontier anchor. The human benchmark infrastructure exists, but `PRODUCTION.yaml` marks the human-play path as stale: it still wires the pre-flip agent and old leaf. A human result obtained without fixing this would be uninterpretable.

Internal Elo orders internal agents only. It cannot establish "superhuman." The current classical champion may already beat the strongest accessible humans, or it may not. That uncertainty is now more important than another unanchored self-play arc.

## What the record suggests but does not establish

- PIMC may be leaving recoverable public-state value on the table; the existing exact "fairness probe" had `deck_len==1` at every K=2 root, so no genuinely hidden future tile remained.
- Better priors may have little production-depth headroom, or the current recipe may simply fail to capture existing headroom. No oracle-prior upper-bound probe exists.
- A fixed `tanh(margin/15)` utility may misprice late conversion and risk-seeking, but the stage-dependent hypothesis has never been directly tested.
- Several sub-threshold classical effects may compose into a useful bundle, but no adequately powered bundle exists.
- Strong-teacher policy distillation as a class is not fully dead because the pre-registered k4×344 generation escalation was never run. The quarter-budget recipe and unchanged continuation are dead.
- The current champion's absolute human strength is unknown.

# PART III — PHASE-1 SUSPECT DISPOSITION

## Fairly killed for the stated scope

- Learned value driving search under the canonical M2 recipe at roughly 7M parameters, ≤5 iterations, and ≤200 simulations.
- Pure learned leaf replacement and the tested C-cheap residual route.
- Deepteacher as a source of compounding, depth-portable policy growth.
- The it16 breakout and any production-depth promotion claim.
- More determinizations than k4 at fixed 2,752 total simulations in current PIMC.
- Gumbel root as a strength lever in the tested setup.
- Full-game clairvoyant alpha-beta as strategically relevant to the fair goal.
- Term R.
- v2.10 cap6 and the implemented bag-close switch as full-game strength levers.
- The tested typed-GNN post-search residual and high-gap distillation recipes.
- The seven-knob T3 family as a source of free fair strength.

## Tested inadequately

- Stage-dependent win-probability utility; only stage-independent temperature changes were tested.
- Closure schedule; only a global scalar was screened.
- Term F and the broader farm-contest axis; the best cell was screen-grade against a large-effect gate.
- Rotation augmentation; one unpaired old-era A/B is not a closure.
- Capacity and scale; the direct probe crashed, so "unfunded" is more accurate than "killed."
- Bag and relational information as online bottlenecks; signal exists offline, conversion failed under current search/targets.
- Learned value as a universal class; only the current scale and recipes are closed.
- Strong-teacher policy distillation at half or full generation depth; k4×344 was not executed.
- Small positive classical levers; the standard n=400 design is not a tight equivalence test around zero.

## Never tested

- Exact public-state chance search versus PIMC on roots with genuinely hidden future draws.
- Production-depth oracle-prior headroom.
- Direct expected-Q, probability-of-optimality, or pairwise-regret policy targets with complete action-by-world coverage.
- A dynamic legal-action or per-cell convolutional policy head replacing the 2,511-way dense coordinate head.
- A side-to-move/tempo term in the hand leaf.
- Cross-determinization variance reduction with common random numbers/shared afterstates.
- Sampled or exact fair endgame widening beyond K≤2.
- A systematic search-core throughput program measured at equal wall-clock.
- The human anchor.
- An adaptive-exploitability benchmark and a sealed one-use final claim band.

# PART IV — THE MISSED THINGS AND THEIR DECISIVE TESTS

## Candidate 1 — Public-state chance search may dominate root-determinization PIMC

### Claim

Current fair search solves sampled complete future orders as if each order were known, then fuses incompatible strategies at the root through conditional pooled-Q. The correct object is a public-state contingent policy with explicit chance: future actions may condition on tiles when they are revealed, but never on hidden order. The project optimized k, selectors, and leaves inside PIMC without testing that game-theoretic object.

### Why the record is consistent with it

The champion pays a large agent-dependent fair tax; the k-width curve has the inverted-U expected from a bias/variance and depth tradeoff; bag/farm signal exists offline but fails to convert; learned prior gains disappear as both agents converge toward the same frozen leaf and aggregation rule; and the largest late gain came from changing search rather than adding another feature.

The prior exact fairness probe does not close this: every K=2 root had only one unseen deck tile, so hidden identity was inferable and reshuffling was effectively the identity permutation.

### Cheapest decisive experiment

Build an exact small-bag public-state oracle suite:

1. Mine 150–250 late roots with the current tile known and 2–4 genuinely hidden future draws.
2. Solve them by dynamic programming over the remaining multiset with explicit chance nodes and exact terminal scoring.
3. Compare current pooled-Q, pooled-N, coverage-corrected expected Q, and the exact public-state optimum at matched root budget.
4. Log expected-points regret, action agreement, coverage, and strategy-fusion cases.
5. Implement production chance-node PUCT or public-tree ISMCTS only if the local gate fires.

**Go:** at least 0.5 points/root or 25% lower regret with a paired 95% interval above zero, followed by at least +35 Elo/z≥2 at equal wall-clock in fresh fair games.
**Kill:** at least 95% action agreement, upper bound below 0.2 points/root, and online upper bound below +20 Elo.
**Cost:** roughly one engineering day plus 4–12 CPU-hours for the local suite; several engineering days only after a positive gate.

## Candidate 2 — The policy channel's ceiling, target, and generation depth are all unmeasured at deployment

### Claim

The stage-2 question was framed as "can a trained net improve the champion's priors?" but the project never measured the upper bound of that channel. It also trains on pooled visits while the teacher plays pooled-Q, and it generates at k4×200 while deployment uses k4×688. A net can therefore learn search allocation or early action discovery without changing the deep decision.

### Why the record is consistent with it

Stage 1 tied the champion at equal simulations; both policy lineages washed out at depth; PUCT prior influence decays with visits; and the k4×344 null-resolution branch was never run. Two incompatible worlds remain possible:

- production-depth prior headroom is near zero, making every prior-only flywheel futile; or
- headroom is +30 to +60 Elo, but pooled-N labels and shallow generation fail to capture it.

### Cheapest decisive experiment

Run three nested gates, stopping as soon as one kills the route.

**Gate A — oracle-prior headroom.** At each root, run a 2–4× budget champion pre-search and feed its root distribution as priors to a production-budget search. Screen clairvoyantly at n=200; if the point estimate is at least +30, confirm fairly at k4×688, n=400–800.

- **Go:** at least +35 Elo/z≥2 fair.
- **Kill:** point estimate below +15 Elo with a sufficiently tight interval; the prior channel is capped at deployment depth.

**Gate B — fixed-root depth transfer.** On 300–500 fresh roots, use identical determinizations, seeds, leaf, and candidate actions at k4×200, k4×344, and k4×688. Record action-by-world N/Q, selected action, time to discover the deep action, and regret versus k4×1376 or the public-state oracle.

- **Go:** k4×344 reduces held-out expected action regret by at least 25% relative to k4×200 and survives scoring by k4×688/public-state oracle.
- **Kill:** upper bound below 10% regret reduction or essentially identical Q ordering.

**Gate C — target alignment.** Only if A and B show headroom, train matched dynamic legal-action scorers on pooled-N, coverage-corrected mean Q, probability of optimality, and pairwise regret. Canonicalize rotation aliases and force minimum root coverage.

- **Go:** at least 25% lower held-out public-state action regret and +35 Elo/z≥2 at production depth and equal wall-clock.
- **Kill:** no target beats pooled-N locally, or the online 95% upper bound is below +20 Elo.

A full restart is justified only after these gates. The allowed restart is a short paired k4×200/k4×344 fork of two to three iterations per arm, not another blind 17-iteration arc.

## Candidate 3 — Stage-independent margin utility may be optimizing the wrong game objective

### Claim

Terminal values, the hand leaf, and training targets all use a constant `tanh(margin/15)` mapping. The stated objective is win rate. `P(win | margin, state)` depends strongly on tiles remaining, uncertainty, meeples, and board structure. A +10 margin early and a +10 margin with two tiles left are not the same utility, and saturation around ±30 can remove gradient for conversion or comeback variance.

The tested `tanh(margin/T)` and constant norm sweeps changed scale but remained stage-independent. They did not test the actual hypothesis.

### Why the record is consistent with it

Exact endgame depth increases margin without increasing win rate; the points-to-wins analysis finds gains in close games but at sub-point scale; aggressive win shaping briefly pointed positive before failing replication; and the current utility treats a strong midgame lead and a locked endgame similarly once saturated.

### Cheapest decisive experiment

**Step 1 — free calibration audit.** From existing game JSONs, estimate empirical `P(win | leaf-margin bucket, tiles-remaining bucket)` with player/agent and deck controls. Overlay the current `tanh(m/15)` surface and assess out-of-sample calibration.

**Step 2 — one-knob online test, only if Step 1 fires.** Fit a monotone stage-dependent norm or calibrated WDL transform, freeze it, and run n=800 fair paired at production depth.

**Go:** materially better calibration and at least +25 Elo/z≥2 online.
**Kill:** little stage interaction, or online point estimate below +10 with an upper bound too small to matter.
**Cost:** an afternoon for the audit; one standard powered evaluation if warranted.

## Candidate 4 — A learned value may still help only as a calibrated residual or uncertainty model

### Claim

The failed value heads tried to replace or blend with a strong hand leaf using noisy outcome supervision. The still-open object is narrower: predict the residual between the hand leaf and exact/public-state action Q, or predict uncertainty/regret from determinization disagreement and use it for Q shrinkage or adaptive allocation.

### Why the record is consistent with it

The hand leaf is excellent on exact K≤2 siblings; the neural heads are not. FPU calibration can prevent catastrophe but has not created superiority. Bag/farm information exists, yet the current target/search may not reward it. A residual target concentrates capacity on the hand leaf's known errors rather than relearning everything.

### Cheapest decisive experiment

1. Construct exact/public-state action-Q labels from Candidate 1 roots and deeper common-determinization matrices.
2. Train game-grouped residual and uncertainty models with distributional or WDL-plus-margin outputs.
3. Require at least 25% lower sibling regret than the hand leaf, no material worst-decile degradation, and stable calibration by phase/bag size.
4. Replay identical roots with identical priors/chance samples, changing only value.
5. Admit the model to n≥400 fresh production-depth games only after the local gate; replicate before self-play use.

**Go:** +35 Elo/z≥2 on the first band and a positive replication.
**Kill:** failure to beat the leaf locally, catastrophic tails, or online upper bound below +20 Elo.
**Cost:** one focused data build and small training study, not a full autonomous loop.

## Candidate 5 — "No single ≥35-Elo lever" may hide a useful classical bundle

### Claim

The standard n=400 methodology is designed to certify large individual effects. It does not tightly distinguish zero from +10 to +20 Elo. Term F, closure scaling, and other small positive cells could all be noise, or several could compose into +25 to +60 Elo. The record cannot currently distinguish those worlds.

### Cheapest decisive experiment

After the stage-dependent calibration audit, form one pre-registered bundle: best-dose Term F (`k=0.25`), a fitted closure schedule, and the best defensible pclose adjustment, all in one `LeafConfig`. Run n=1600 fair paired at production depth.

**Go:** at least +25 Elo/z≥2; reopen classical work in powered bundles.
**Kill:** absolute effect below 10 Elo with a tight interval; call the adjacent classical residue dust.
**Cost:** about four box-days unattended at the project's reported cadence.

This is a one-shot power correction, not permission for endless recombination.

# PART V — VERDICT AUDIT

## The flywheel retraction

### Correct conclusions

- The pre-registered continuation rule bound the team and correctly stopped unchanged continuation.
- The fresh-band extension was a legitimate anti-winner's-curse test, strengthened by the it20 control.
- The deck-matched it16−it20 contrast flipped sign across bands.
- The same-deck production-depth test erased the practical effect.
- Pooling inconsistent selected and replication halves would have been misleading.

### Necessary nuance

The record does not identify "pure noise" as the unique mechanism. A small, transient, or deck-sensitive shallow effect plus selection is plausible. The operative sentence should be:

> **it16 did not replicate, did not survive production depth, and cannot support a growth or promotion claim. Any remaining shallow effect is too unstable and too small to matter for the stated goal.**

### Final audit judgment

The retraction was correctly drawn under the team's own rules. The team should retain the narrower mechanism wording above and should not reopen it16 itself.

## Fair kills

| Verdict | Integrated audit |
|---|---|
| Canonical-AZ value cell | Fairly killed at the explicit 7M/≤5-iteration/≤200-simulation scope. |
| Pure learned value / C-cheap routes | Fairly killed for the tested implementations. |
| Deepteacher compounding | Fairly killed by fresh-band and depth-transfer evidence. |
| it16 breakout | Fairly killed as robust growth and production improvement. |
| More determinizations at fixed 2,752 sims | Fairly killed; k4 is the measured optimum inside current PIMC. |
| v2.10 cap6 and bag-close | Fairly killed as online strength levers in the tested forms. |
| Gumbel root, Term R, T3 family | Fairly killed for the tested families. |
| Typed-GNN residual and high-gap distillation | Fairly killed for those targets/models. |
| Public bots as frontier anchors | Fairly killed for the surveyed implementations. |

## Premature or over-broad closures

- **"Clairvoyance is a fixed small tax."** False; the tax is agent-dependent and the old fair wrapper leaked.
- **"Value can rank but can never drive search."** Over-broad; calibrated FPU restored parity. The fair surviving claim is that tested values do not add strength.
- **"The AZ-value route is universally exhausted."** Only true with the M2 scope guard.
- **"Bag adds nothing."** False as an information claim; it has not converted under current online recipes.
- **"Relational structure is inert."** The tested GNN failed; dynamic legal-action scoring remains open.
- **"Leaf and search are tapped out."** Adjacent knobs are tired, but public-state chance search and throughput remain open.
- **"Strong-teacher fair distillation is dead."** Too broad. The k4×200 recipe and unchanged continuation are dead; one bounded k4×344/full-depth hypothesis remains open after the root gate.
- **"Win shaping was tested."** Only stage-independent transforms were tested.
- **"Term F and closure are zero."** The experiments failed large-effect gates; they did not establish equivalence to zero.
- **"No robust growth at any iteration, any depth."** Directionally right but logically broader than the measurements. The defensible statement is that no checkpoint has a replicated positive advantage and the selected peak has no production-depth advantage.

# PART VI — THE PATH

## Strategic choice

A self-learning flywheel is **probably unavailable at the current scale**, but the policy channel has not yet been closed by an upper-bound measurement and the one preregistered half-depth generation cell was never run. The program should therefore execute a bounded decision tree, not either extreme of faith-based continuation or blanket abandonment.

The reliable route to superhuman play is currently:

**audited classical agent → more fair simulations → public-state/search correction where justified → calibrated utility → strong-human proof.**

Learning remains a conditional branch.

## Priority 0 — Make the measured agent unambiguous

Before any new claim:

1. Replace documentary configuration with a versioned immutable executable manifest containing agent class, leaf hash/config, reshuffle semantics, k/sims, selector, exact handoff, checkpoint, and latency budget.
2. Make evaluation and human harnesses instantiate the same factory and emit resolved hashes at startup.
3. Fix the stale human path to the current PUCT-prior curve125 k4×688 champion.
4. Add golden traces and adversarial property tests for dual-farm/same-city scoring, crop boundaries, key equivalence, rotation aliases, deck canonicalization, current-tile/bag invariants, and result-sign semantics.
5. Replay at least 100,000 random/adversarial states with hard assertions.

**Gate:** zero semantic/configuration divergences. Any failure supersedes downstream strength work.

## Priority 1 — Run the decision probes in parallel

These are cheap relative to another training arc:

- `P(win | margin, stage)` calibration from existing logs.
- Oracle-prior production-depth headroom.
- Fixed-root k4×200/344/688 depth transfer and selector/coverage replay.
- Exact small-bag public-state oracle.

Together they determine whether the next dollar belongs to utility, policy learning, chance search, or neither.

## Priority 2 — Begin the human benchmark now

After Priority 0, run a small operations/variance pilot against the strongest accessible two-player experts.

Use **cross-player or Latin-square deck pairing**, not same-human replay of the same hidden sequence. A human can remember rare-tile timing and gain unintended future-order information in the second leg. Treat player and deck as crossed effects. Use unique one-use claim decks generated only after the binary and analysis plan are frozen.

Report two endpoints:

- **first-contact performance**, and
- **informed/adaptation performance** after opponents receive a familiarization block.

Publish the result even if the agent loses. The benchmark calibrates the goal; it is not a reward for a particular architecture.

## Priority 3 — Buy fair simulations

The fair ladder is the only clean, unsaturated dose-response curve. Profile the Python PUCT tree, engine stepping, and batching; port or vectorize only the measured bottlenecks; then compare equal wall-clock strength and latency. Preserve semantic regression tests across the port.

A 2–4× throughput improvement could be valuable because the existing ladder prices additional simulations strongly, but the Elo gain must be measured rather than assumed.

## Priority 4 — Follow the probe results

### If the public-state oracle fires

Implement explicit chance-node PUCT or public-tree ISMCTS with edge-local N/W/Q, public-tree reuse, progressive chance sampling, canonical action classes, and exact late-game handoff. Compare equal wall-clock against k4×688 PIMC before changing the leaf.

### If oracle-prior headroom and depth transfer fire

Run the direct Q/regret target study with a dynamic legal-action scorer. Only then run the short paired k4×200/k4×344 fork. Keep-best promotion, fresh one-use bands, two seeds, deliberate exploration, and production-depth/equal-wall-clock gates are mandatory.

### If stage-dependent utility fires

Deploy the simplest calibrated monotone transform first; confirm at n=800 before touching training targets broadly.

### If only the bundle fires

Reopen classical work as powered bundles, not n=100 individual knob screens.

### If all policy probes fail

Close the prior-only flywheel. One residual/uncertainty value route remains, subject to the local gate. If it fails, direct strength work moves to classical search and deployment.

## Priority 5 — Widen exact late-game treatment cautiously

A sampled-marginalization solver for K≤4–8 is worth a gated study because the tile multiset is small late. Gate on **win rate**, not margin; the existing exact-endgame results show that margin improvements can be strategically inert.

## Priority 6 — Use sealed evaluation governance

Maintain three deck tiers:

1. reusable development bands;
2. sealed one-use promotion bands assigned after model/manifest hashes are frozen; and
3. an independently generated final claim band never recycled into design decisions.

Once a band influences a decision, retire it from confirmatory status.

# PART VII — STOP RULES

## A. Declare self-learning operationally dead at the current resource scale when all conditions hold

### Policy channel closure

1. Oracle-prior headroom at production depth is below +15 Elo with a sufficiently tight paired interval (prefer n≥800 for the final kill).
2. Fixed-root k4×344 generation reduces expected action regret by less than 10%, or reproduces the k4×200 ordering.
3. If the root gate fires and the short deeper-generation fork is run, no arm achieves a replicated +35 Elo/z≥2 production-depth equal-wall-clock gain and the best pooled upper bound is below +20 Elo.

### Value channel closure

4. One structurally distinct residual/uncertainty value route, with calibrated FPU and public-state local labels, fails to reduce sibling regret by 25% in two seeds or exhibits unacceptable tails.
5. Any locally successful value fails fresh production-depth online gates, with the best 95% upper bound below +20 Elo.

### Scale closure

6. A roughly 4× data/model probe shows no positive capacity slope, and the project has no decision or funding to increase capacity/games by about 10×. If larger-scale funding later appears, the honest epitaph remains "dead at the tested scale," not a universal theorem.

When all six hold, stop funding autonomous self-learning for strength. Retain neural models only for latency, compression, analysis, or interface purposes. Do not reopen the program because of another shallow/offline spike without a new improvement channel.

## B. Declare superhuman reached only through an audited human claim

### Required protocol

1. One immutable fair agent manifest, corrected hidden-order handling, current harness, fixed time control, logged hashes/latency, and no mid-match changes.
2. A pre-registered panel representing the strongest accessible two-player human frontier. If the panel is weaker, narrow the claim to that panel.
3. Cross-player/Latin-square deck and seat balancing, fresh one-use decks, independent adjudication, and no training or tuning on claim decks.
4. Both first-contact and adaptation blocks.
5. Public or independently auditable game logs.

### Primary statistical criterion

Use a pre-registered fixed or group-sequential design. Declare formal superiority when the one-sided 95% lower confidence bound on paired match score exceeds **55% overall** against the top panel, the lower bound exceeds **50% against each of the top three players or equivalently strong strata**, and the result replicates on a second sealed band.

### Stronger "decisively superhuman" capstone

A more demanding public claim may additionally require a sequential test supporting at least **65% overall** and at least **60% over 30+ games** against a national-champion-caliber player. This is a useful capstone, not a necessary logical definition of superhumanity.

Anything based only on internal Elo is "plausibly strong," not "superhuman." If frontier access never materializes, the maximal honest claim is: **"decisively beats every expert who agreed to play, under public audited conditions."**

# PART VIII — PHASE-3 CROSS-CHECK AND AMENDMENTS

## 1. Doubt-by-doubt verdict

| Team doubt | Verdict | Integrated reason |
|---|---|---|
| n=200 may miss durable +10 to +20 Elo effects | Qualify | True about resolution, irrelevant as a rescue of +88.7 or production growth. Use pooled slope/equivalence methods for small effects. |
| The held anchor is mid-tier and in-ecosystem | Endorse | "Held tier" is only relative to `rodv2_iter02` at shallow depth; it is not champion or human evidence. |
| The k4×344 null-resolution cell was never run | Endorse narrowly | It narrows the kill. Run one fixed-root discriminator and, only if positive, a short paired fork. |
| Warm start and regularization may explain non-collapse | Endorse | Stable retention is a platform result, not autonomous improvement. |
| Frozen learned value may prevent both collapse and depth-robust growth | Endorse with gate | It explains the structural ceiling but does not justify naive unfreezing. Local regret/calibration must come first. |
| Equal simulations are not equal compute | Endorse | The stage-1 tie is mechanism-level. Deployment decisions require equal wall-clock under the real batching regime. |
| The human anchor is overdue | Endorse strongly | It is the only measurement that grounds the stated endpoint. |

## 2. Open decision questions

### What is the lesson of a loop that held tier but did not grow?

It validated operational stability, fair self-play plumbing, a strong warm start, and a usable policy-compression route. It did not demonstrate policy improvement. The frozen leaf, anchor data, and nearby teacher made collapse unlikely. The loop becomes strategically useful only if attached to a deeper/public-state policy target or a locally superior residual value.

### Should training resume from `iter_20.pt`?

Not unchanged. Run the oracle-prior, root depth-transfer, and target-alignment gates. A short k4×200/k4×344 fork is allowed only after the root gate fires. Otherwise close the route.

### Should the stage-3 value unlock run?

Not as a direct unfreeze, convex blend, or leaf replacement. Run one residual/uncertainty model through local public-state sibling-regret, tail, calibration, and identical-root counterfactual gates. Only a locally superior value enters games.

### Which ablations are worth running?

Only two can change strategy: generation-depth/target alignment, and a small fixed-data 2×2 stability-anchor study (champion side stream on/off; anchored versus aging replay). Do not spend seven self-play branches explaining a null.

### What most likely causes depth washout?

Search acceleration without asymptotic value improvement is the leading explanation. Budget-specific visit targets and pooled-Q coverage bias are second. Root replay across 50, 100, 200, 344, 688, and 1,376 simulations per determinization can separate early discovery, Q convergence, selector effects, and downstream game coupling.

### What external measurement belongs next?

The strong-human benchmark, immediately after the release audit. Use one-use decks, cross-player pairing, and adaptation blocks.

## 3. Neither list

### Human deck pairing can leak future order through memory

Same-human seat swapping on the same hidden deck is unsafe. Use cross-player/Latin-square pairing, or a delayed recall-audited design whose second leg is excluded if recall is material.

### Static strength can hide adaptive exploitability

A deterministic style may beat its ecosystem yet become exploitable after opponents learn its thresholds and tie-breaking. Report first-contact and informed/adaptation results, and maintain a style-diverse out-of-lineage adversarial panel.

### Reused evaluation bands become development data

Researcher checkpoint and narrative selection over a repeatedly viewed band is governance-level overfitting even without model leakage. Retire exposed bands from confirmatory use.

### Equal-wall-clock can hide resource-shape mismatch

Single-game latency, total throughput, batching, concurrency, and memory pressure are different constraints. Report all of them. A model that is equal at one throughput regime may be unusable in the human interface or vice versa.

## 4. Amendments

**AMENDED — Scope of policy-distillation closure.** The quarter-budget k4×200 recipe, the it16 breakout, and unchanged continuation are killed. Strong-teacher fair distillation as a class is not fully closed because the preregistered k4×344 escalation was never run. It earns one bounded root discriminator and, only if positive, a short paired fork.

**AMENDED — Human deck-pairing protocol.** Replace same-player replay of the same hidden sequence with cross-player/Latin-square pairing or a rigorously delayed recall-audited design.

**AMENDED — Superhuman threshold reconciliation.** The statistically principled formal declaration uses a replicated lower confidence bound above 55% against a frontier panel and above 50% against its top strata. The supplemental review's 65%/national-champion criterion is retained as a stronger "decisively superhuman" capstone rather than the sole definition.

No other central conclusion changes: the breakout retraction is correct; no flywheel has been demonstrated; the current loop should not resume unchanged; public-state search, policy-channel headroom, calibrated utility, and a local residual value are the decisive technical tests; the human anchor is overdue; and learning is not required for the agent goal.

# CONCLUSION

The project is not at "nothing worked." It has built a substantially stronger classical search agent, a stable fair self-play pipeline, a culture of correction and preregistration, and several exact/local tools. What failed is a more specific claim: **the current shallow-teacher, visit-distillation, frozen-value loop has not produced self-sustaining growth at the deployed operating point.**

The right response is neither to keep iterating the same loop nor to declare all learning impossible. It is to measure the remaining channels directly:

- exact public-state regret for PIMC,
- oracle production-depth headroom for priors,
- stage-conditioned calibration for utility,
- local public-state regret for residual value,
- powered composition for small classical terms,
- and actual strength against the human frontier.

Those measurements can turn the fork into a sequence of finite decisions. If they all close, the team should pursue superhuman play through classical fair search and engineering without apology. If one opens, it will identify a real improvement channel rather than another attractive but ambiguous curve.
