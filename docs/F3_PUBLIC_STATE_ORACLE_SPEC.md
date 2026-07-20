# F3 — Exact Small-Bag Public-State Oracle — BUILD SPEC

**Status: DESIGN-ONLY / build-ready. NOT yet built, NOT run.** Written 2026-07-20.
Track-F item **F3** (roadmap [PROGRAM_ROADMAP_2026-07-07.md](PROGRAM_ROADMAP_2026-07-07.md) L78);
the review's **Candidate 1** ([reviews/INTEGRATED_REVIEW_20260719.md](reviews/INTEGRATED_REVIEW_20260719.md)
§"Candidate 1"); adoption item 5 ([reviews/REVIEW_ADOPTION_20260719.md](reviews/REVIEW_ADOPTION_20260719.md)).

**Decision this probe makes:** does root-determinization PIMC (the production `k4×688` fair agent) leave
recoverable **public-state** value on the table vs an exact chance-aware solution — i.e. is PIMC *strategy
fusion* a real, recoverable cost, or a theoretical worry? GO ⇒ build chance-node PUCT / public-tree ISMCTS.
KILL ⇒ close the search-object route; spend on throughput/utility/classical instead.

> **⚠️ Read the feasibility verdict (§2.5) before scheduling.** The review priced this at "≈1 engineering
> day + 4–12 CPU-hours" for 150–250 roots at "2–4 genuinely hidden draws." That price is **not achievable at
> the requested depth with the existing solver**: the exact *marginalized* DP already exists and is directly
> reusable, but it is deepcopy-bound and OOM-prone at K≥3, and "2–4 hidden draws" means K=4–6 where a single
> solve costs minutes-to-hours. The recommended build (§2.5, §5) runs the cheap **K=3 (1 hidden draw)** suite
> on the existing solver first (≈1 eng-day, fits the CPU budget), and treats K=4 (2 hidden draws) as a gated
> second phase requiring a **make/unmake solver rewrite (~3–5 eng-days)**.

---

## Why now — the ladder just bent downward

Fresh evidence elevates F3 above the other probes. The 2026-07-20 fair-ruler re-baseline
(`fair_ruler_rebase_*` in `experiments/results.csv`, fixed post-CL-056 champion vs `h800`, n=400 deck-matched,
one fresh band 24e9) found the fair sims-scaling curve **bends downward** at fixed `k=4`:

| total sims | config | abs elo vs h800 | deck-matched Δ vs prev rung |
|---|---|---|---|
| 2752 | k4×688 | +135.0 | — |
| 5504 | k4×1376 | +147.2 | **+2.14 pts/deck, z=+1.66** (suggestive) |
| 11008 | k4×2752 | +114.3 | **−2.85 pts/deck, z=−2.23** (significant DROP) |

Zero timeouts, clean time scaling — **not an artifact.** More per-world depth at fixed `k=4` makes fair play
*worse* past ~2× budget. This is exactly the failure the blind review predicted:

> **P1-S1** — "Root-determinization PIMC does not produce a valid observable-state policy value … optimistic
> values for plans that require mutually incompatible future responses. This can persist **or worsen with more
> search**, so high-depth strength need not validate the method."

Deeper per-world search sharpens each *clairvoyant* world's plan, which is precisely what makes strategy
fusion bite harder — the pooled root value fuses better-optimized-but-mutually-incompatible continuations.
F5 (throughput) returned its verdict on 2026-07-20: **raw sims-buying is dead past ~2× at fixed k4**; its
own note names F3 as the discriminator. This oracle is the instrument that decides whether the bend is
strategy fusion (⇒ fix the search object, F3 GO) or a budget-specific (k,sims) mis-allocation (⇒ re-solve
the width/depth split per budget, a cheaper fix).

---

## Key finding up front: the DP already exists

The review frames Candidate 1 as "solve them by dynamic programming over the remaining multiset with explicit
chance nodes." **That DP is already implemented and validated** as the marginalized mode of the L2-3 endgame
solver, `scripts/level2/endgame_solver.py`:

- `solve(game, board, mode="marginalized", budget, alphabeta=False)` → `SolveResult` with
  `value` (V*, exact expected score-diff under optimal hidden-future play), `optimal_actions` (the exact-best
  action set), **`child_values: dict[action → exact value]`** (every legal root action scored), and `nodes`.
- `_chance(nb)` (L172–186) is the explicit chance-node layer: it groups the remaining bag by tile type,
  draws each type with probability `count/total` **without replacement** (drops one instance), and returns
  the expectation — exactly the review's "future draws … prob count/total without replacement."
- Terminal = engine-exact final scoring via `flat_base_score(state, 0) = scores[0]−scores[1]` with true farm
  scoring (L151–153), **uncorrelated with the v2.9 heuristic leaf** — the whole point of a non-circular ruler.
- Decision nodes are keyed by the **observable state** + the **sorted bag multiset** (`_key`, L130–149): the
  "V5 no-leak key" where states differing only in unrevealed order collide. This is already a public-state
  object, not a clairvoyant one.
- `regret_of(res, action)` (L282–289) gives per-action regret in raw points, mover-oriented, ≥0.

**Therefore F3 is not a "new search engine."** The new work is: (1) **root mining** that actually contains
hidden future draws (the old probe's fatal gap), (2) the **comparison harness** (PIMC selectors vs the exact
optimum + strategy-fusion detection), and (3) a **feasibility decision** about how deep the exact solve can
go before the deepcopy wall makes it infeasible. Sections 1–3 spec these; §2.5 is the feasibility call.

---

## 1. Root mining — genuinely-hidden late roots

### 1.1 Why the old probe tested nothing (do not repeat it)

The prior probe `scripts/canonical_az/fairness_decision_probe.py` capped at **K≤2** (`k_remaining ≤ 2`),
because that is the only band where the marginalized solve is both tractable *and* fair-legit (marginalized ==
clairvoyant there). But `k_remaining = len(deck) + 1(in-hand)`, so **K=2 ⇒ `len(deck)==1`**: exactly one
unseen tile, whose identity is fully inferable from the public bag multiset. The FAIR arm's only
differentiator, `rng.shuffle(deck)`, is the **identity permutation on a 1-element list**. The committed run
proves it: `measurement/fairness_probe/fairness_decision_s1600_k8_n300.log` shows `deck_len_dist={1: 300}` —
all 300 roots had zero hidden information. The two arms differed only by search RNG. **Verified on the L2-3
suite** (`measurement/level2/l23_positions.jsonl`, 750 greedy roots): at K=2, **0%** of roots have ≥2 distinct
tile types in the bag; at K=3, **96%**; at K≥4, **100%**.

### 1.2 Definition of "genuinely hidden"

A future draw is *genuinely hidden* iff, at the moment it is drawn, the remaining bag has **≥2 distinct tile
types** (Shannon entropy > 0 over `tile.description`). The **number of genuinely hidden draws** at a root =
the number of chance nodes on the principal variation whose bag has entropy > 0. In these late greedy roots
the bag is ~1 tile per type (near-uniform), so:

| K (`k_remaining`) | `len(deck)` | median distinct types | ≈ genuinely hidden draws |
|---|---|---|---|
| 2 | 1 | 1 | **0** (dead — the old probe) |
| 3 | 2 | 2 | **1** |
| 4 | 3 | 3 | **2** |
| 5 | 4 | 4 | **3** |
| 6 | 5 | 5 | **4** |

The review's "2–4 genuinely hidden draws" therefore maps to **K=4, 5, 6**. Note **1 hidden draw (K=3) already
admits strategy fusion**: two possible worlds ⇒ the pooled value can fuse two incompatible continuations. K=3
is the cheapest band that tests the mechanism at all, and (per §2.5) the only exact band reachable without a
solver rewrite.

### 1.3 Root source — champion distribution, not greedy

The old suite (`gen_endgame_positions.py`) is **greedy self-play** (`RuleBasedPlayer`) — a neutral generator,
but the wrong distribution for this probe: we are testing whether the **champion's** pooled-Q pick is wrong at
positions the **champion actually reaches** under fair PIMC. Mine roots from **champion fair-PIMC self-play**:

- **Primary path:** use `scripts/measurement_infra/root_replay.py` — lossless `(deck_seed, action_sequence,
  ply)` reconstruction that works for **any** policy's games (not just greedy). Generate (or reuse existing)
  fair `k4×688` champion self-play game logs, then `replay_actions(seed, actions, ply)` to reconstruct the
  exact `Board` at each candidate late-game ply. The engine consumes the global RNG only at the deck shuffle,
  so `(seed, actions)` fully determines the game — replay is bit-exact (README "load-bearing guarantee #1").
- **Provenance schema** (reuse `gen_endgame_positions._provenance`, L63–85): persist per root `seed`, `ply`
  (or `actions`), `k_remaining`, `to_move`, `scores`, `meeples{free,placed}`, `in_hand_tile`,
  **`bag_multiset`** (the hidden type-multiset), **`bag_size`** (= `len(deck)` = "deck_len"), `known_order`
  (real future order, for a clairvoyant cross-check only), `legal_n`, and `checksum =
  string_representation(board)` (replay-determinism guard, §5.4).
- **Supplement / fallback:** the existing greedy `l23_positions.jsonl` K=3/4 roots (already 96–100% hidden)
  can seed the fixtures and a distribution-robustness cross-check, but the headline suite must be
  champion-distribution so the measured regret is on-policy.

### 1.4 Band, stratification, exclusions

- **Band:** `k_remaining ∈ {3, 4}` for the buildable suite (§2.5); `{5, 6}` only as opportunistic exact +
  sampled-marginalization reference (§2.5, §4). Only **TILES-phase** roots (the current tile is revealed and
  known; the hidden part is the deck) — this matches `k_remaining`'s definition and the fair agent's latch
  condition.
- **Target n:** 150–250 roots **with ≥1 genuinely hidden draw** after filtering, split across K bands and
  strata. (At K=3, ~96% of greedy roots qualify; champion roots should be similar — filter, don't assume.)
- **Stratification** (so the go/kill signal is not dominated by one board type — mirror review M2/M4 strata):
  1. **contested farms** — ≥1 field with farmers of both players, or a farmer-margin ≤1 (the leaf's known
     weak slice; use `flat_leaf` decomposition to detect);
  2. **open cities** — ≥1 incomplete city with ≤2 open edges and ≥1 meeple committed (closure contestable by
     the hidden draw);
  3. **live meeple decision** — ≥1 player has ≥1 free meeple (~⅓ of endgame roots; the rest are pass-only —
     keep some but don't over-weight, they have trivial meeple branching);
  4. **top-2 shallow-Q gap** — tag each root with `scripts/measurement_infra/tagging.py` h200 top-2 Q-gap;
     over-sample the **low-gap** stratum (shallow search nearly indifferent ⇒ where the hidden future is most
     likely to flip the right move). This is the cheap "is this hard?" triage the infra was built for.
- **Exclusions:** drop roots that are (a) **forced** (`legal_n == 1` — the fair agent skips the k searches,
  nothing to test); (b) **effectively decided** (|score margin| large enough that `child_values` spread <
  0.5 pt — no decision to get wrong); (c) **zero-entropy** bag after filtering (`bag_size < 2` or 1 distinct
  type); (d) reconstruction-mismatch (`string_representation(replay) != checksum` — §5.4).

---

## 2. The exact public-state DP

### 2.1 Node semantics (map to existing code)

| node | definition | code |
|---|---|---|
| **decision** | observable state = (board layout, scores, meeples, phase, **revealed in-hand tile**, remaining **sorted multiset**). Mover maximizes (P0) / minimizes (P1) the P0-perspective value. | `_value` L151–170; TT key `_key` L130–149 (`string_representation` ⊕ `tuple(sorted(descs))`) |
| **chance** | entered after a turn completes (a draw happens); marginalize the just-drawn tile over the remaining multiset, `P(type)=count/total`, without replacement. | `_chance` L172–186 |
| **terminal** | `next_tile is None`; value = `flat_base_score(state,0)` (engine-exact final farm scoring). | `_terminal` L69–71; leaf L152–153 |

The chance node conditions downstream decisions **only on the tile once revealed** — it never sees the rest
of the (sorted, hidden) multiset order. That is precisely the "public-state contingent policy" object the
review says PIMC fails to compute. **No alpha-beta** in marginalized mode (chance/expectation nodes have no
minimax cutoff — asserted L105–106); the TT + multiset symmetry are the only tractability levers.

### 2.2 What is reused verbatim vs new

| component | reuse? |
|---|---|
| the expectiminimax DP, chance marginalization, exact terminal, regret | **verbatim** — `endgame_solver.solve(mode="marginalized")`, `_chance`, `flat_base_score`, `regret_of` |
| move generation / successor / legality | **verbatim** — `game.get_valid_moves` + `game.get_next_state` (the engine, no custom move-gen) |
| no-leak TT key (sorted multiset) + 128-bit blake2b digest + freeze-at-cap (`CARCASSONNE_TT_CAP`) | **verbatim** — `_key` L130–149, `_put` L121–123 |
| solve-once-score-many harness pattern (score any ranker's per-child regret vs one `SolveResult`) | **reuse the pattern** from `scripts/canonical_az/solver_score.py` (`score_root`, L410–477) |
| root reconstruction + provenance | **verbatim** — `measurement_infra/root_replay.py`, `gen_endgame_positions._provenance` |
| **the PIMC-vs-oracle comparison harness (§3)** | **NEW** — this is the deliverable script |
| **make/unmake successor (kill the deepcopy)** | **NEW, conditional** — only if K=4 is required (§2.5) |
| **strategy-fusion detector** (§3.3) | **NEW** |

### 2.3 State-space / branching — real numbers

From the L2-3 suite (`legal_n` = TILES-phase legal action count = placements × rotations):

- **tile-decision branching** `b_t` ≈ **43 median**, up to **124** (across all K bands).
- **meeple-decision branching** `b_m`: **1 (pass-only) in ~⅔ of endgame roots** (median free meeples = 0);
  else `1 + claimable features on the placed tile` ≈ 2–6 (bounded by ≤~4 farm regions + city + road + chapel).
- **chance branching** `b_c` = distinct types remaining = `len(deck)` in these near-uniform late bags: K=3→2,
  K=4→3, K=5→4.

A K-tile marginalized solve alternates `decision(b_t) → decision(b_m) → chance(b_c)` for K tiles. The naive
tree is `∏(b_t·b_m·b_c)` ≈ `(43·~1.5·b_c)^K`, but the TT collapses order/board transpositions massively.
**Empirical node counts** (clairvoyant + AB, which is a *lower bound* on marginalized nodes — marginalized
adds chance fan-out and loses AB pruning):

| K | clairvoyant+AB node_med | clairvoyant+AB sec_med | source |
|---|---|---|---|
| 2 | 1,654 | 4.5 s | `solver_bench_by_k.json` (marginalized ≈ 7.5 s; but K=2 = 0 hidden) |
| 3 | 25,764 | **80 s** (max 119 s) | `solver_bench_by_k.json` → tagged **"MICRO-ONLY"** |
| 4 | ~108k–210k (max ~970k) | **~21 min median (max ~7.4 h)** | `LEVEL2_K4_PROBE_VERDICT.md` |

Per-node cost is **~4.5 ms/node, deepcopy-dominated** (`_clone_with_tile` L77–87 deepcopies `board.state` per
chance child; `get_next_state` copies per successor). **Practical exact-marginalized depth cap with the
current solver: K=3 (borderline, attended, OOM-prone at W>4).** K≥4 marginalized is documented infeasible
(`eval_fair_puct.py` L82–83: "K≥3 marginalized … RAM/OOM regime → ATTENDED ONLY"; roadmap A-small declined
the make/unmake build).

### 2.4 Cost model (per root, marginalized)

Direct measurement anchor (this spec, 2026-07-20): one K=3 marginalized solve on the first L2-3 K=3 root
**did not complete in 35 s** even with a 300k-node budget cap (single process, `nice -n 19`) — consistent
with marginalized ≈ 3–10× the clairvoyant+AB node count. Estimates:

| K | current deepcopy solver | with make/unmake (~5–15× faster, deepcopy is the dominant cost) |
|---|---|---|
| 3 | ~1–3 min/root (OOM-prone W>4) | ~5–20 s/root |
| 4 | ~30 min–hours/root (**infeasible at scale**) | ~3–20 min/root (attended, partial coverage) |
| 5–6 | infeasible | infeasible exact (⇒ sampled marginalization only) |

**Suite totals:**
- K=3 × 200 roots, current solver: **~3–10 CPU-hours** single-thread (parallelizable to ~1–3 wall-hours at
  W≤4 on the laptop, RAM-permitting). **Borderline within the review's 12-CPU-hour line.**
- K=4 × 150 roots, current solver: **hundreds of CPU-hours + OOM** — **NOT feasible.**
- K=4 × 150 roots, make/unmake solver: **~10–50 CPU-hours** (partial coverage, attended).

### 2.5 ⚠️ Feasibility verdict (the blocker)

**The review's cost line (≈1 eng-day + 4–12 CPU-hours for 150–250 roots at 2–4 hidden draws = K=4–6) is not
achievable with the existing code.** The exact marginalized DP exists, but it is deepcopy-bound; "2–4 hidden
draws" is exactly the K=4–6 band where a single solve is minutes-to-hours and OOMs above W=4. The old probe
capped at K=2 for this reason, and K=2 has zero hidden information.

**Recommended staged build (cheap-first):**

1. **Phase 1 — K=3-only exact oracle on the existing solver (≈1 eng-day build + ~4–10 CPU-hours run).**
   150–250 champion-distribution K=3 roots (1 genuinely hidden draw), `CARCASSONNE_TT_CAP` + node budget +
   **report coverage** (fraction of roots fully solved vs budget-hit), attended, W≤4 on the laptop.
   **1 hidden draw already exhibits strategy fusion**, so this is decisive for the GO/KILL gate. This matches
   the review's cost envelope *if the depth is read as "≥1 genuinely hidden draw" rather than literally 2–4*.
2. **Phase 2 — make/unmake solver rewrite → K=4 (only if Phase 1 fires or is borderline, ~3–5 eng-days).**
   Replace `_clone_with_tile` deepcopy + `get_next_state` copy with incremental apply/undo (candidate:
   reuse `flat_leaf`'s int union-find decomposition for O(Δ) apply/undo, no `Farm`/`City` objects). This is
   the "3–5 day OOM-prone build" the roadmap declined (A-small) — now justified only *after* the cheap K=3
   signal. Unlocks K=4 (2 hidden draws) at ~10–50 CPU-hours partial coverage.
3. **Never exact at K=5–6.** For the deep end, use **sampled marginalization** (Monte-Carlo the chance
   fan-out, exact continuation) as a *secondary, lower-confidence* reference only — this is the review's
   Priority-5 "sampled-marginalization solver," not the exact oracle. The exact GO/KILL gate lives at K=3–4.

**Bottom line for scheduling:** F3 is *cheap and decisive at K=3* (Phase 1) and *expensive at K=4* (Phase 2,
gated). Do not attempt exact K=5–6.

---

## 3. Comparison protocol

For each mined root, at **matched production root budget** (`k4×688`, the champion's fair config —
`PRODUCTION.yaml` `fair_deploy`: `k_dets=4`, `sims_per_det=688`), compute four picks and score every one
against the exact `child_values`.

### 3.1 The four agents (all at the same k=4 root determinizations/seeds — common random numbers)

Instrument the production agent `FairHeuristicPriorAgent._pimc_move` (`fair_agent.py` L496–529; per-world
search is `NeuralMCTS` with the heuristic-prior evaluator) to run the k=4 determinizations once per root and
capture the **full per-world action-value matrix** `M[world w][action a] = (N_{w,a}, Q_{w,a})` from each
per-world tree (via `pool_root_stats` L116–132, which already dedups rotation aliases by child identity and
signs W to the root player). Then:

1. **(a) Production pooled-Q pick** — `pooled_q_argmax(agg_n, agg_w, min_visits=2)` (`fair_agent.py`
   L135–146): eligible = actions with pooled `N ≥ 2` (fallback to all visited); argmax `(W/N, N, −a)`.
   **This is the current selector** and the primary thing on trial. Note it is a *conditional* mean — an
   action gets zero contribution from a world where it was never visited (the P1-S3 selection bias).
2. **(b) Pooled-N pick** — `argmax_a agg_n[a]` (visit-count selection; the old probe's primary, more robust
   to leaf noise). Tests whether the visit target the trainer records would pick differently.
3. **(c) Coverage-corrected expected-Q pick** — for action `a`, coverage `c(a)` = # of the k=4 worlds where
   `N_{w,a} ≥ 1`. Compute `Q̄(a) = mean over ALL k worlds` of `Q_{w,a}` where visited, and an **imputed value
   for unvisited worlds** (spec two variants, report both): (i) *neutral* = that world's root value; (ii)
   *pessimistic* = that world's min-child Q (counts adverse missing worlds against `a`). Pick
   `argmax_a Q̄(a)`. This is review M4 arm 3 — it directly tests whether the selection bias is the mechanism.
4. **(d) Exact public-state optimum** — `min(res.optimal_actions)` from `solve(mode="marginalized")`, plus
   the full exact `child_values` vector = the ground-truth ruler.

### 3.2 Metrics (per root, then aggregated paired)

- **Expected-points regret per root** for each of (a),(b),(c): `regret_of(res, pick)` = `V* − V(pick)` in raw
  points, mover-oriented, ≥0. **Primary endpoint** = paired mean regret of (a) vs the exact optimum, and the
  **regret reduction** of (c)/(b) relative to (a).
- **Top-action agreement**: fraction of roots where each PIMC pick ∈ `res.optimal_actions` (exact-best set).
- **Per-world coverage stats**: distribution of `c(a*)` where `a*` is the pooled-Q pick — how many of the 4
  worlds actually visited the chosen action (low coverage ⇒ the pick rides on a selection-biased few worlds).
  Also report the coverage of the *exact-best* action (is the right move being systematically under-covered?).
- **K-sensitivity**: report all metrics split by K band (3 vs 4) — the ladder bend predicts regret grows with
  the number of hidden draws.
- **Strategy-fusion flag** (§3.3) rate, and the fusion-attributable share of pooled-Q regret.

### 3.3 Strategy-fusion detection (mechanical, from the per-world trees)

Strategy fusion = a root action `a` ranks well under pooled-Q **because different worlds reward incompatible
downstream continuations** that a single observable-state policy cannot jointly realize. Detect it per action:

1. For each world `w`, record the **greedy continuation line** after playing `a` (the child's principal
   variation inside world `w`'s clairvoyant tree).
2. **Cross-world replay:** take world `w1`'s continuation policy and evaluate it in world `w2` (replay the
   move sequence where legal; where illegal, fall back to that world's search move). Let
   `Q_fused(a)` = pooled-Q as computed = each world scoring `a` with **its own** clairvoyant continuation, and
   `Q_single(a)` = the best value achievable by **one** continuation policy fixed across all k worlds
   (max over the k candidate policies of the min/mean cross-world value).
3. **Fusion premium** `Φ(a) = Q_fused(a) − Q_single(a) ≥ 0`. Flag `a` as fusion-inflated if `Φ(a)` exceeds a
   threshold (spec: ≥0.5 pt) **and** `a` is the pooled-Q pick **and** `a ∉ res.optimal_actions`.
4. The exact public-state optimum inherently uses one contingent policy conditioning only on revealed draws,
   so **regret(pooled-Q pick vs exact)** already captures the *aggregate* fusion cost; `Φ(a)` **localizes**
   which picks are inflated by fusion vs by simple sampling noise / coverage bias. Report: fraction of
   nonzero-regret roots where the pooled-Q pick is fusion-flagged (⇒ fusion is the mechanism) vs
   coverage-flagged (`c(pick) ≤ 1`, ⇒ selection bias is the mechanism) vs neither (⇒ sampling noise).

### 3.4 Pre-registered gates — VERBATIM from the review

From [INTEGRATED_REVIEW_20260719.md](reviews/INTEGRATED_REVIEW_20260719.md) §"Candidate 1 → Cheapest decisive
experiment":

> **Go:** at least 0.5 points/root or 25% lower regret with a paired 95% interval above zero, followed by at
> least +35 Elo/z≥2 at equal wall-clock in fresh fair games.
> **Kill:** at least 95% action agreement, upper bound below 0.2 points/root, and online upper bound below
> +20 Elo.

Operationalized for the **local** (offline) stage — the online +35 Elo / +20 Elo bounds are the *second*
stage, run only after a local GO:

- **Local GO** if (paired mean pooled-Q regret vs exact ≥ **0.5 pts/root**) **OR** (coverage-corrected /
  chance-aware pick reduces pooled-Q regret by ≥ **25%**), with the **paired 95% CI above zero**.
- **Local KILL** if (pooled-Q top-action agreement ≥ **95%**) **AND** (paired 95% upper bound on pooled-Q
  regret < **0.2 pts/root**).
- On local GO, the review's second gate is a *production* chance-node PUCT / public-tree ISMCTS prototype
  measured at **equal wall-clock** vs `k4×688` PIMC on a fresh fair band — GO needs **≥ +35 Elo, z ≥ 2**;
  KILL if the online 95% upper bound < **+20 Elo**. (Out of F3 scope; F3 delivers the local verdict + the
  labeled data that a prototype would be built from.)

---

## 4. Cheap adjacent win — Candidate-4 residual-value data

The same mined roots + exact DP labels are exactly the training targets the review's **Candidate 4**
(learned value as a calibrated **residual/uncertainty model**) needs — "Construct exact/public-state
action-Q labels from Candidate 1 roots." Candidate 4 is the only value-channel route left open (roadmap:
C-cheap DEAD, but a residual/uncertainty model with a local sibling-regret gate is the reshaped Stage-3).
**Persist the full label set once**, so the data build is not repeated:

Per root, write one self-describing JSON record (`manifest.json`-style, per results-discipline):
- **identity/provenance:** `seed`, `ply`/`actions`, `checksum`, `k_remaining`, `to_move`, `bag_multiset`,
  `bag_size`, `in_hand_tile`, `known_order`, source-agent + config hash, solver `budget`, `completed`
  (coverage flag), `nodes`.
- **exact labels:** `vstar`, `optimal_actions`, and the **full `child_values` vector** (every legal root
  action → exact expected score-diff) — the residual target is `child_values[a] − leaf_value(child_a)`.
- **PIMC observables (for the uncertainty model):** the per-world matrix `M[w][a] = (N,Q)`, pooled `agg_n`/
  `agg_w`, coverage `c(a)`, top-2 Q-gap tag, and the fusion premium `Φ(a)` — determinization disagreement is
  the natural uncertainty feature the review names.
- **features:** the sighted board representation + the 32-type bag histogram at the root (so a
  residual/uncertainty net can be trained without re-deriving state). Use the production encoder
  (`flat_repr_cy`) + `sighted_planes.bag_histogram` (L176–194). The fair policy target (pooled-N) is already
  emitted per move as `FairHeuristicPriorAgent.last_pooled_visits` (L482–486) — persist it alongside.

This makes F3's output double as the Candidate-4 dataset at ~zero marginal cost. Local Candidate-4 gate
(≥25% lower sibling regret than the leaf, two seeds, no bad tails) can then run **offline** against these
labels before any games — the correct cheap-first ordering.

---

## 5. Execution plan

### 5.1 Build order (fixtures first)

1. **Hand-verified fixtures.** Construct a **2-tile toy** where the correct move depends on the hidden draw:
   a K=3 position (1 in-hand + 1 hidden draw over exactly 2 known types) where placing tile T scores well iff
   the hidden draw is type X but poorly iff type Y, so the exact expectation is hand-computable
   (`E = p_X·v_X + p_Y·v_Y`). Assert `solve(mode="marginalized").value` and `child_values` match the by-hand
   number **exactly**. Add a K=2 degenerate fixture (single determined draw) asserting marginalized ==
   clairvoyant (already true — a regression guard). Add a **strategy-fusion fixture**: a position with two
   worlds where a root action `a` looks best only because each world uses a different continuation — assert
   `Φ(a) > 0` and that `a ∉ optimal_actions` while pooled-Q would pick it.
2. **Mining script** (`scripts/f3_public_state_oracle/mine_roots.py`): champion self-play → `root_replay` →
   filter (§1.4) → stratify (§1.4) → write provenance JSONL. Verify every record's `checksum` on replay.
3. **Oracle + comparison harness** (`scripts/f3_public_state_oracle/run_oracle.py`): for each root, run the
   k4×688 PIMC capturing the per-world matrix, run `solve(mode="marginalized")`, compute the four picks +
   metrics + fusion flags, persist the Candidate-4 record (§4). Solve-once-score-many (reuse
   `solver_score.py`'s pattern). Fork `multiprocessing.Pool`, `CARCASSONNE_TT_CAP` set, `nice -n 19`.
4. **Analysis** (`scripts/f3_public_state_oracle/analyze.py`): paired CIs (bootstrap over roots), the gate
   evaluation (§3.4), by-K and by-stratum breakdowns, coverage/fusion attribution. Emits the verdict block.
5. **(Phase 2, gated) make/unmake solver** — only after a Phase-1 GO/borderline; separate spec.

### 5.2 pytest contracts (`tests/test_f3_public_state_oracle.py`)

- **A. DP correctness:** the 2-tile toy — `solve(marginalized).value` == hand-computed expectation (exact);
  `child_values` per action == hand-computed.
- **B. Chance semantics:** `_chance` weights sum to 1; without-replacement (bag shrinks by exactly one
  instance of the drawn type); grouping by `tile.description` collapses interchangeable tiles.
- **C. No-leak invariance:** `solve(marginalized)` value is invariant to a permutation of `state.deck`
  (already a property of the sorted-multiset key — assert it as a regression).
- **D. Marginalized == clairvoyant at K=2** (single determined draw).
- **E. Regret non-negativity + optimal-set consistency:** `regret_of(res, a) ≥ 0 ∀a`; `== 0 ⟺ a ∈
  optimal_actions`.
- **F. Selector parity:** the harness's pooled-Q reproduces `fair_agent.pooled_q_argmax` byte-for-byte on a
  captured matrix; pooled-N == `argmax agg_n`.
- **G. Fusion detector:** on the fusion fixture `Φ(a) > 0` and the pick is flagged; on a no-hidden-info
  fixture (K=2) `Φ ≡ 0`.
- **H. Coverage accounting:** `c(a)` ∈ [0, k]; coverage-corrected pick == pooled-Q pick when all actions have
  full coverage.
- **I. Replay determinism:** `string_representation(replay_actions(seed, actions, ply)) == checksum` for
  every mined root (guards §5.4 failure mode).

### 5.3 Box / worker / RAM profile

- **Pure CPU, net-free** — no GPU, no orchestrator. The solver is single-threaded per root; parallelize
  across roots with a fork pool.
- **Box:** the **laptop** (5900XT is the local box; both are running evals per the task). Capacity/solver
  jobs are banned on the local box during evals anyway. `nice -n 19`.
- **RAM is the binding constraint, not CPU.** The marginalized TT reaches ~1M entries on hard roots; a single
  hard K=4 worker ballooned to **~12 GB** (`LEVEL2_K4_PROBE_VERDICT.md`). **Size W ≤ RAM / ~2 GB**, use
  `CARCASSONNE_TT_CAP` to bound it (freeze-at-cap is correctness-neutral — a miss just recomputes). For
  Phase-1 K=3: **W ≤ 4** on the laptop, watch for the OOM-killer (a vanished `setsid` job = OOM, per the
  exact-solver infra memory).
- **Wall-clock (Phase 1, K=3, 200 roots):** ~3–10 CPU-hours ⇒ **~1–3 wall-hours at W=4**. Set a per-root
  wall/node budget (e.g. 2M nodes / 300 s) and **report the budget-hit fraction as coverage** — do not let
  one pathological root hang the suite.

### 5.4 Two failure modes to guard

1. **Multiset-memo blowup (RAM/OOM).** The TT is the whole ballgame at K≥3. Guard: `CARCASSONNE_TT_CAP` set
   from the start (freeze-at-cap, correctness-neutral); per-root node budget with `BudgetExceeded` caught and
   the root marked `completed=False`; **report coverage** (fully-solved fraction) as a first-class metric —
   a KILL verdict is invalid if coverage is low (budget-hit roots are silently the hard ones). Cap W to
   RAM/~2 GB; monitor for OOM-killer (vanished worker).
2. **Engine state-reconstruction drift.** The whole probe rests on `replay_actions` reproducing the exact
   board the champion faced. Guard: assert `string_representation(replay) == checksum` (stored
   `deck_hash`/checksum) for **every** root at mine time **and** at solve time (test I); refuse to solve any
   root that fails. The replay guarantee is bit-exact by construction (RNG only touched at deck shuffle), but
   an action-sequence off-by-one or a code-era drift would corrupt every downstream number silently.

---

## 6. Cost summary

| item | eng-hours | CPU-hours | notes |
|---|---|---|---|
| **Phase 1** — K=3 oracle on existing solver (mine + harness + analysis + fixtures + tests) | **~8–10 h (≈1 eng-day)** | **~4–10** | fits the review's envelope *at 1 hidden draw*; decisive for GO/KILL |
| **Phase 2** (gated on Phase-1 GO/borderline) — make/unmake solver → K=4 | **~24–40 h (~3–5 eng-days)** | **~10–50** | the roadmap's declined A-small build, now justified by a local signal |
| deep end (K=5–6) | — | — | **not exact** — sampled-marginalization reference only (review Priority 5) |

**Total to a defensible local verdict: ~1 eng-day + ~4–10 CPU-hours (Phase 1).** The review's headline price
holds *only* if "2–4 genuinely hidden draws" is relaxed to "≥1 genuinely hidden draw" (K=3). Reaching the
literal 2-hidden-draw depth (K=4) needs the ~3–5 eng-day solver rewrite.

---

## Appendix — key code references

- **DP / oracle:** `scripts/level2/endgame_solver.py` — `solve` L247–279, `_chance` L172–186, `_value`
  L151–170, `_key` L130–149, `SolveResult` L53–61, `regret_of` L282–289, `_clone_with_tile` (deepcopy wall)
  L77–87. Terminal leaf `flat_base_score` in `src/carcassonne_ai/flat_leaf.py` L577.
- **Production PIMC agent:** `src/carcassonne_ai/fair_agent.py` — the deployed champion is
  `FairHeuristicPriorAgent` (L305–569; per-world search = `NeuralMCTS` + heuristic-prior evaluator), PIMC loop
  `_pimc_move` L496–529. Shared module helpers: `pool_root_stats` L116–132, `pooled_q_argmax` (+ floor
  `DEFAULT_MIN_POOLED_VISITS=2` L95) L135–146, `reshuffled_determinization` (CL-056 canonical-sort leak fix)
  L206–228. (`FairHeuristicMCTSAgent` L149–302 is the older `HeuristicMCTS`-based sibling using the same
  helpers.) `final_select: visits` in PRODUCTION.yaml is **inert in fair mode** — the ensemble always picks by
  pooled-Q. There is **no** pooled-N *selector* and **no** per-world coverage counter in production (both are
  NEW comparison arms in §3). Production config: `governance/PRODUCTION.yaml` `fair_deploy` (`k_dets=4`,
  `sims_per_det=688`, `min_pooled_visits=2`).
- **Mining / replay:** `scripts/measurement_infra/root_replay.py` (`replay_actions`, `load_games`);
  `scripts/level2/gen_endgame_positions.py` (`_provenance` L63–85, `k_remaining` L45–47, `replay_to`);
  `scripts/measurement_infra/tagging.py` (top-2 Q-gap).
- **Solve-once-score-many pattern:** `scripts/canonical_az/solver_score.py` `score_root` L410–477.
- **The dead old probe:** `scripts/canonical_az/fairness_decision_probe.py` (K≤2 cap, `deck_len==1`);
  evidence `measurement/fairness_probe/fairness_decision_s1600_k8_n300.log` (`deck_len_dist={1:300}`).
- **Cost evidence:** `measurement/exact_endgame_hybrid/solver_bench_by_k.json` (K2 4.5s / K3 80s
  clairvoyant+AB); `measurement/level2/LEVEL2_K4_PROBE_VERDICT.md` (K4 ~21min median);
  `scripts/exact_hybrid/bench_solver_by_k.py`.
- **Ladder-bend evidence:** `experiments/results.csv` rows `fair_ruler_rebase_{2752,5504,11008}`.
