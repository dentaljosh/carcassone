# In-loop value flywheel — build spec (2026-06-04)

**Decision (Joshua, 2026-06-04 evening):** build a KataGo-style **in-loop learned value flywheel**.
This is the one lever that can produce a *climbing* curve (and the only path that can break the
v2.7-leaf ceiling). Superhuman stays the **north star** — we are NOT re-scoping down to the analyzer.
Playbook (Joshua's framing, AlphaGo-style): **build the flywheel → put a non-lying odometer on it →
let it climb → challenge a human LAST.**

## PROGRESS (live)
- ✅ **Step 1 BUILT** (commit `67fd90e`): `value_target="search_value_tree"` — `NeuralMCTS(record_boards=True)` + `interior_value_targets()` harvest interior (board→Q); selfplay emits value-only rows; new `GameDataset.aux_mask` (None→all-True back-compat) through save/load/rotate/augment/streaming-7-tuple; shared `masked_policy_ownership_loss` (policy+own on full rows, value on all). Full pytest green + plumbing smoke (6 games → 864 traj + 5746 interior rows; train_warmstart 1 epoch finite losses).
- ✅ **Step 1 VALIDATION FINISHED — verdict NEGATIVE** (`RUN=searchval_tree`): interior training did NOT escape the value-as-leaf cliff (λ=1.0 still ≈ −576-class). Steps 1+2 (interior targets, global pooling) both failed to make the learned value a usable leaf → the lever moved to the value LOSS/objective: [VALUE_LOSS_ATTACK_2026-06-05.md](VALUE_LOSS_ATTACK_2026-06-05.md) (whose Lever 1 → residual → attempt-2 → production iter8). *(Original ⏳ live-run text removed 2026-06-12.)*
- ✅ **Odometer rung 1 BUILT** (commit `07ebda8`): `scripts/ladder_asymmetric.py` — asymmetric-compute v2.7 ladder → net's heuristic-equivalent search depth (out-of-lineage, non-saturating). 6 crossover-math tests pass. Not yet run.
- ⏭ **Next:** read the λ=1.0 verdict → if it escapes the cliff, proceed to step 3 (value-into-leaf in-loop); regardless, run the ladder on iter_01 to anchor absolute strength. Remaining odometer: non-v2.7 opponents, deck-paired cross-play, oracle-regret. Then step 2 (global pooling).

## Why (the regroup that produced this)

We spent the day characterizing and mostly closing the value-head-in-search lever, then got **four
independent outside opinions** (3 blind subagents + 1 external reviewer). They converged hard, and they
**corrected the team's earlier "0.47 information ceiling / value exhausted" call.** The corrected read:

- **0.47 is NOT an information ceiling.** It's the corr of the value with the *final realized margin*,
  which is heavily set by future tile draws (high variance) — a noisy *outcome-prediction* target.
  What matters for play is **decision ranking** (does the value pick the right move) / **expected
  value**, not Pearson-r with one noisy game result. We measured the wrong quantity.
- **The −576 pure-NN-leaf catastrophe is a DISTRIBUTION MISMATCH, not a ceiling.** Our value trained
  on self-play *trajectory* positions and got queried on *tree-interior* positions it never saw.
  KataGo fixes exactly this by training the value **in-the-loop on its own search-visited positions**.
- **The curve erodes because the value flywheel is OFF.** Only the policy learns; the leaf is the
  frozen v2.7 heuristic. A half-flywheel settles (→ `policy_scale` +87→+38 erosion). AlphaGo's climb
  came from the *value+policy* flywheel turning together. To get a climb, turn the value engine on.
- **Even the +87 may be ecosystem-overfit.** It's measured vs the *same* v2.7 evaluator we train/play
  with. The "+39 over prior that was a dead tie on an independent ladder" is the magnetized-instrument
  failure in our own data. → a *light, out-of-lineage* odometer is required so the climb is real.
- **Honest risk (recorded, not a blocker):** 3 home GPUs are ~3–4 orders of magnitude under any known
  superhuman recipe, and 2p Carcassonne is high-variance (tile draws compress the measurable skill
  gap). Genuine world-champion-superhuman may be out of reach here; the *climb* is what tells us how
  far we can get. We pursue it clear-eyed.

Full results + the 4 opinions are in DECISIONS 2026-06-04 (pm-3/pm-4/pm-5). Today's measured curve:
held-out value corr **0.289 (outcome head) → 0.464 (search-value head)**, **flat at sims 200→400**
(0.4644→0.4675); value-blend@play **λ0=+96, λ0.5=−37, λ1.0(pure NN leaf)=−576**.

## What's already built + reusable

- `search_value` generation-side value target (commit ffe823e): `NeuralMCTS.root_value()` (root.Q,
  current-player POV) + `selfplay.py value_target="search_value"` writes per-ply root.Q into
  `values_arr`. **This is the seed of step 1** — but it currently records only the PLAYED root, not the
  tree interior.
- `scripts/probe_heldout_value_corr.py` (streaming, multi-ckpt table; `--max-games` bounds memory —
  the load-all cut OOM'd the 31 GB 5800x). The held-out-corr gate. ⚠️ but see "metric" caveat below —
  outcome-corr is the wrong gauge; add a **decision-ranking** metric.
- Cluster loop `run_pathb_cluster_loop.sh` (3-box, `VALUE_TARGET`/`STAGE_B_BLEND`/`value-blend` knobs),
  git-bundle sync to xeon+laptop, per-box W (5800x 14 / xeon 10 / laptop 20).
- `--value-blend λ` already blends NN value into the v2.7 leaf in BOTH self-play and eval
  (`CARCASSONNE_V25_VALUE_BLEND`). Step 3 reuses this.

## Build steps (the flywheel) — cheapest-foundational first

1. **Value sees the SEARCH distribution (the −576 fix, foundational — do first).**
   Record value targets at MCTS *interior* nodes (the visited tree), not just the played root. After a
   move's `search()`, walk `mcts._nodes` (or the top-visited subtree) and emit `(node_board, node.Q)`
   for nodes with `N ≥ min_visits`. Board reconstruction: root children are reachable via
   `get_next_state(root_board, a)`; deeper nodes need either storing the board on the node or replaying
   the action path — decide the cheapest adequate coverage (depth-1 + PV is a reasonable start).
   ⚠️ **Schema/loss work:** interior positions have NO policy/ownership target (we don't play them out),
   so they need value-ONLY rows → GameDataset gains a per-row mask + `train_iter` masks policy/ownership
   loss for them. This is the main plumbing cost.
2. **Global pooling in the net** (`network.py`). Add global-pooling layers (mean/max over the board,
   concatenated back) so the value/policy can reason about board-WIDE quantities (farm control, tiles
   remaining, meeple supply) that a 6×96 conv stack with small receptive field can't integrate. New
   trunk → retrain a warmstart. Likely the single biggest quality lever per the reviewers.
3. **Value into the leaf, IN the loop (turn the flywheel).** Train value (steps 1–2) → blend it into
   the leaf at a ramping λ in self-play (`--value-blend`) → its self-play now generates the interior
   targets it trains on next iter → repeat. Success = a blended (eventually higher-λ) leaf that **beats
   the pure-v2.7 leaf at matched compute** (i.e. exceeds +96 / clears the ceiling), AND a curve that
   CLIMBS across iters instead of eroding.
4. **Light, out-of-lineage ODOMETER (in parallel, cheap, idle-CPU).** So "it's climbing" is trustworthy:
   - **Asymmetric-compute v2.7 ladder:** HeuristicMCTS at 50/200/800/3200/12800 sims — "what heuristic
     sim-budget does our 200-sim agent equal?" (absolute-ish, non-saturating, un-overfittable).
   - **Diverse NON-v2.7 opponents** (different heuristic weights, random-rollout MCTS, greedy/feature,
     ablations) — detects ecosystem-overfitting (does the edge generalize beyond v2.7, or only beat it?).
   - **Frozen cross-lineage "graveyard league"** cross-play table; **deck-paired both seats**, report CIs.
   - **Oracle-regret metric:** move-match / regret vs very deep search on a fixed position set —
     a strength signal with NO opponent and NO lineage.
5. **Diagnose why iteration erodes** (exploration/temperature collapse? training on the capped/stale
   value signal? narrow opponent ecology?). A loop that decays can't climb regardless of architecture —
   fix before scaling. (May partly resolve once the value flywheel is on.)

## Open technical questions (resolve during the build)
- **Chance-node / tile-draw handling.** Vanilla AZ assumes determinism; Carcassonne draws are stochastic
  (the engine pre-shuffles; `fair_chance` re-shuffles unseen deck per move). Collapsing draw uncertainty
  into point-estimate value targets may be a quiet root cause of both the 0.47 and the off-distribution
  failure. Audit how targets treat the draw distribution; consider expectation over draws.
- **Value target form.** Move from scalar `tanh(margin/15)` toward a **win-probability + score-
  distribution** head (KataGo-style; categorical/HL-Gauss). Richer, denser signal; better calibrated.
- **Metric.** Add a **decision-ranking** gauge (does value+search pick the oracle move) alongside the
  outcome-corr probe — outcome-corr is the wrong gauge (it's why we mis-read 0.47 as a ceiling).

## First action (post-compaction)
Start **step 1** (value records the search distribution) — it's the foundation; the value must SEE the
off-distribution positions before global pooling / in-loop blending matter. Stand up the **step-4
odometer** (asymmetric ladder + one non-v2.7 opponent + deck-paired cross-play) in parallel on idle CPU.
Keep superhuman as the north star; let the curve tell us how far it goes.
