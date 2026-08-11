# Value/Search Conversion Autopsy — DECISION

> **STATUS: CONCLUDED 2026-06-27 — DECISION D (value inert) + "root metrics don't convert".**
> Two findings, one of which corrects the other. (1) **At the ROOT, on decision-relevant states,** the
> learned stack underperforms bare classical search: the **neural value head is inert** and the
> **policy prior makes worse decisions** (agreement with h6400 on the full gap≥0.02 pool: classical
> 0.911 > flat-prior neural 0.867 > production neural 0.799 — monotone). (2) **But this does NOT convert
> to game strength** — head-to-head at matched 200-sim compute, classical h200 ≈ neural iter04 (WR
> 0.438, score margin −2.6, n=96, not significant), i.e. the net is **game-NEUTRAL vs classical, not
> game-harmful.** The root-level edge washes out because games are dominated by low-gap positions where
> the prior is fine. **Lesson (again): root/decision-state agreement does not predict head-to-head
> strength** (cf Path-3 prior-washout, the sims-washout). The binding constraint for game strength is
> **search depth + a value head that beats the v2.9 leaf**, not the policy. No promotion / no
> v2.9 / no PRODUCTION change.

**Date:** 2026-06-27 · **Branch:** rod_v2_flywheel · **DIAGNOSTIC ONLY.**
Plan: [VALUE_SEARCH_PLAN.md](VALUE_SEARCH_PLAN.md) · Miss set: [VALUE_SEARCH_MISS_SET.md](VALUE_SEARCH_MISS_SET.md) ·
Interventions: [VALUE_SEARCH_INTERVENTIONS.md](VALUE_SEARCH_INTERVENTIONS.md) ·
Results: [VALUE_SEARCH_RESULTS.md](VALUE_SEARCH_RESULTS.md).

## Anchor

Path-3 proved the high-gap policy signal is learnable but non-converting; this autopsy localized why.
Reproduced natively: R2 (Path-3 repair) NMCTS top1 0.775 ≤ iter04 0.799 on the full gap≥0.02 pool
(R2 better only in the endgame argmax) — policy repair is not the binding constraint under search.

## The 9 questions

1. **Where does h6400 beat NMCTS@200?** Broadly, on decision-relevant states (gap≥0.02): iter04 NMCTS@200
   agrees with h6400 only 79.9% (regret 0.0189), 30.9% of decision states are misses. The gap is not
   localized to a phase — it is global, somewhat worse in the endgame.

2. **Are misses mostly unexplored moves or undervalued explored moves?** **Undervalued/mis-ranked.**
   88% of misses are *explored* (the h6400 move is in the tree) but ranked below the chosen move; only
   12% are never-explored (and those cluster in the endgame). Mis-ranking under search, not
   under-exploration, is the dominant failure.

3. **Does more search budget fix it?** Only slowly. Neural sims 200→400→800 = top1 0.350→0.457→0.553 on
   the miss set; even 4× the budget trails classical's *200-sim* 0.815. Search budget is not the
   efficient lever.

4. **Does teacher-prior injection fix it?** Partially (64% of misses), but **less than a flat prior**
   (79%). Because `best_action` ranks by backed-up search Q (not visits), a peaked root prior
   over-commits while the deeper tree still uses the net prior + value-blind leaf, so the subtree Q
   doesn't confirm the move. A *better* prior is the wrong fix.

5. **Does flattening/degrading the prior hurt much?** The **opposite** — flattening *helps a lot*. On the
   full pool, uniform-prior neural scores 0.867 vs the trained prior's 0.799 (+6.8pp, −45% regret). The
   trained policy prior is **net-harmful** on decision-relevant states.

6. **Does neural residual/value help, hurt, or do nothing?** **Nothing.** rs0 / rs0.25 / rs0.5 are
   indistinguishable (top1 0.365 / 0.350 / 0.357 on misses), and the residual never corrupts the leaf
   ranking (I6: 107 wrong→right, 0 right→wrong). The learned value head is inert for search.

7. **Is the bottleneck global or endgame-specific?** **Global** (it holds on the full pool across
   phases), but worse in the endgame, where the static leaf is value-blind 91% of the time and the
   not-explored tail concentrates.

8. **Is any value/search intervention game-converting?** **No — and crucially, the root-level edge
   itself does not convert.** Game screen (classical HeuristicMCTS@200 vs neural iter04@200,
   head-to-head, matched compute, v2.9 leaf, paired, net-on-CPU 2-box): **classical WR 0.438 (42W/1D/53L,
   n=96, 48 paired decks), mean score margin −2.6, paired-z −1.19 — not significant, a slight lean toward
   NEURAL.** Despite classical agreeing with h6400 +11pp more *at decision roots*, the two are ~even in
   games (if anything neural edges it). So no intervention converts in classical's favor — but equally
   the net is **not** game-harmful. The decision-state errors wash out because most game positions are
   low-gap, where the net prior is fine (and more efficient than uniform UCB). This is the same
   non-conversion seen in Path-3 (held-out prior gain → no game gain) and the sims-washout.

9. **Is a new RoD-style learned loop justified?** **No.** The value head is inert and the policy prior
   degrades search; a learned loop that produces an over-confident policy makes 200-sim search worse than
   the bare heuristic. Policy distillation (any target — argmax, Q-softmax, advantage) is dead
   (hard-policy-repair + high-gap distillation + this autopsy). The lever is **not** more learned
   policy/value on this architecture.

## Outcome — D (value inert) + non-conversion; NOT F

The candidate outcomes were A (policy still matters), B (search budget), C (value corrupts), D (value
irrelevant), E (horizon/endgame), F (classical-search dust). The root-level evidence *looked* like a
strengthened **F** (classical strictly better) — but the **game screen refutes the strong reading**:
classical's root edge does **not** convert; classical h200 ≈ neural iter04 in games (slight lean to
neural). So the evidence lands on:

- **D — the neural value head is irrelevant.** Inert at every residual scale; never corrupts. SOLID,
  root + games.
- **A is real at the root but game-NEUTRAL.** The trained policy prior *is* over-confident and makes
  worse decisions on decision-relevant roots (flat/classical agree with h6400 more) — but in games this
  washes out: the net is neither better nor worse than classical at matched compute. The fix that
  "works" at the root (flatten the prior) would *not* be expected to help games (it only helps the ~20%
  high-gap positions, at the cost of efficiency on the 80% low-gap ones).
- **NOT F.** Classical search at matched budget is better *at decision roots* but **not in games** — so
  "the learned stack is strictly worse" is false at the level that matters (game outcomes).
- Search budget helps only weakly (not B); value never corrupts (not C); the leaf is 1-ply-blind but
  search recovers it given broad exploration (E is a mechanism, not the binding constraint).

**The headline correction:** root/decision-state metrics (agreement with a deeper teacher) are NOT a
proxy for head-to-head strength. The autopsy's root analysis is rigorous and the value-inert finding is
solid, but the policy "harm" is a decision-state artifact that does not move games. This is the third
independent instance (Path-3 prior-washout, sims-washout, now this) of the same trap — **gate strength
claims on games, never on root/policy metrics.**

## What this means / recommended next direction (for review — NOT actioned)

- **The binding constraint for game/superhuman strength is search depth + the value/leaf, not the
  policy.** Both classical h200 and neural iter04 are ~even with each other and both lose to h6400@6400
  (Path-3: neural WR 0.463 vs h6400). The only learned component that could raise *deep-search* strength
  is a **value head that beats the v2.9 leaf** — and this autopsy confirms the current one is inert
  (blocker #2, still open and still the gate).
- **Do NOT** run another policy-distillation flywheel, mine more policy data, temper/retrain the policy
  for game gains (the root edge doesn't convert), add heuristic terms, or promote anything.
- **Candidate directions** (each its own future experiment, none started): (a) a **value head that beats
  the leaf** — the single highest-value lever, gate it on a GAME screen vs h-deep, never on root MSE/rank;
  (b) accept the **classical/search-depth ceiling** — at matched compute the learned net adds nothing in
  games, so a *learned* superhuman agent on this architecture is blocked pending a value-representation
  breakthrough; the strongest cheap agent is bare HeuristicMCTS on the v2.9 leaf at higher sims. The
  prior-tempering idea is **deprioritized** — it fixes a root metric that does not convert.

**Answer delivered; stopping for review per governance.**
