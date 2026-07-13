# C6 — Full-game ID-alpha-beta + TT ("clairvoyant chess-engine gambit") — PRE-REGISTERED DESIGN

> **STATUS: CLOSED 2026-07-13 (CL-053) — clair-only dead-end.** Stage-0 cost bench = GO (median depth 6). Stage-1 built (`src/carcassonne_ai/alphabeta_agent.py`, gauntlet-green vs the exact solver) + n=100 screen = αβ **+34.9 elo / paired_z 2.94 / 53W-4D-43L** vs the PUCT champion (the +206/+190 calibration smokes were small-n draws that regressed to +35). CLOSED without the n=400 confirm/escalation: αβ is CLAIRVOYANT-ONLY BY CONSTRUCTION (below), so a win can never deploy fair → strategically inert for the superhuman-fair goal. Build default-OFF, champion untouched. This design retained as the record.
> Roadmap: [docs/PROGRAM_ROADMAP_2026-07-07.md](../../docs/PROGRAM_ROADMAP_2026-07-07.md) Track C, item C6 ("the one
> family that might BEAT PUCT — attended build, **surface cost first**, ~2–4d"). Design-only; `governance/PRODUCTION.yaml`
> untouched by anything in this document. **CLAIRVOYANT-ONLY by construction** — alpha-beta cannot run in the fair
> regime (chance/deck nodes break minimax cutoffs; `scripts/level2/endgame_solver.py:105` asserts it; established by
> [A_SMALL_SPEC_2026-07-09.md](A_SMALL_SPEC_2026-07-09.md) §0). A C6 win is graded like reuse_tree (CL-044): a
> clairvoyant/dev-regime result unless a separate post-E4 fair question is opened. Roadmap rank: **below A-small/E4**
> — this doc surfaces the cost so Joshua can decide whether to fund the build at all.

## Premise

The champion of record (`governance/PRODUCTION.yaml`) is a CLAIRVOYANT classical agent: `HeuristicPriorAgent`
(PUCT + softmax heuristic-leaf priors + expand-all-children + visit-argmax), c_puct=1.5, τ_p=5, float leaf,
reuse_tree=true, ~2750 sims (= equal wall-clock to h6400, [EQUAL_TIME_BENCH_CY.md](EQUAL_TIME_BENCH_CY.md)),
exact-K≤4 endgame handoff, **v2.9.2 Bmild_cap8 curve125** leaf (CL-051). With a known deck order the game is a
deterministic, perfect-information, 2-player zero-sum game — minimax/αβ applies cleanly, and the flip (+148.2,
CL-043) proved pure-search wins over this same leaf are real. C6 asks: does exact backward induction to a
full-width horizon beat prior-guided sampling to a deeper selective horizon, at EQUAL WALL-CLOCK on the same leaf?

**Honest prior (pre-registered):** the "chess-engine territory" premise rests on a µs-scale *node*, and only the
leaf is µs-scale here (23.9 µs Cython float). The engine *step* (`get_next_state` = optimized-but-real deepcopy of
an object state) is ~100–400 µs — so αβ gets roughly the SAME node volume as PUCT, not chess's 100–1000× more.
The Stage-0 cost surface (§7) is therefore the go/no-go gate, run BEFORE the agent build. Additionally the TT —
the other half of the chess analogy — is expected to be **ordering infrastructure, not a transposition collapser**
under a fixed deck (§3). Expect a decline or a null; size the kill gates accordingly (§9).

## No-touch guarantees

- **`governance/PRODUCTION.yaml` is NOT modified** by any stage. Champion agent + config untouched; C6 is a NEW
  sibling agent class, flag-gated, default-OFF, absent = byte-identical harness behavior.
- All evidence lands as `experiments/results.csv` rows + per-cell `manifest.json` (self-describing resolved config,
  per-side leaf_hash — C5 Trap-1 mitigation carried forward).
- Champion side in every cell is the PRODUCTION.yaml champion verbatim (curve125 env exports per
  `scripts/human_anchor/env_preamble.py` conventions; manifests record both sides' resolved leaf).
- Zero cloud. Local 5900XT + laptop, `nice -n 19`, pre-launch process census, git-bundle sync before any 2-box run.

## 1. Algorithm core

**Search:** iterative-deepening depth-first minimax with αβ pruning, PVS (principal-variation search) and
aspiration windows, over the clairvoyant game tree (agents descend the true `state.deck` — same information the
champion's search uses).

- **⚠️ Mover convention — NOT naive negamax.** A Carcassonne turn is TWO plies with the SAME mover
  (TILES ply → `play_tile` sets phase=MEEPLES with `current_player` unchanged → MEEPLES ply → `next_player`,
  `engine/wingedsheep/carcassonne/utils/state_updater.py:18-28`). Per-ply sign-flipping negamax is WRONG here.
  Use the proven in-repo convention (`endgame_solver._value_ab`): **values are always P0-POV; the node is a
  max-node iff `state.current_player == 0`**. Equivalently negamax with `color` read from the child's mover,
  flipping only when the mover actually changes.
- **Depth accounting + horizon rule:** depth is counted in plies (decisions). **The horizon may only land on a
  TILES-phase node** — if the depth limit hits at phase==MEEPLES, extend one ply. Evaluating a state where a tile
  was just placed but the (free, often large) meeple option was not yet taken is the game's horizon-effect analog
  of evaluating mid-capture in chess; the extension is the 1-ply quiescence this game needs. ID schedule steps by
  **2 plies (one full turn)**: d = 2, 4, 6, … up to `max_depth` or budget.
- **Terminal nodes** inside the search return the exact final score `flat_base_score(state, 0)` (the same value
  the exact solver uses) — scale-consistent with the heuristic leaf (both in points, P0-POV), no mate-score
  machinery needed.
- **PVS:** first child at each node searched with the full (α, β) window; remaining children with a null window
  (α, α+ε), ε=1e-4 (float leaf ⇒ no integer granularity); fail-high ⇒ re-search full window. Standard.
- **Aspiration:** from ID depth ≥ 6, root window = previous-iteration root value ± `asp` (default **±3.0 points**);
  fail-low/high ⇒ widen ×4 once, then full window. Off (`asp=0`) is a sweepable ablation.
- **Root move:** best move of the deepest COMPLETED iteration (a partially-searched deeper iteration may promote
  its move only if the new PV move's full-window search completed). Tie-break: lowest action index (deterministic;
  mirrors `_ExactHandoff`'s `min(res.optimal_actions)`).
- **Budget = child-steps, not wall-clock (pre-registered choice).** The budget unit is the number of
  `get_next_state` calls (the dominant, load-invariant cost). A wall-deadline agent would be nondeterministic AND
  unfair under W-parallel load (the C4 cell logged ~6.46 s/move under load vs ~3.1 s single-thread — a wall-budget
  candidate would silently gain nodes relative to a sims-budget champion as load varies). A child-step budget is
  the exact analog of the champion's sims budget: deterministic given the deck (CRN-clean, replayable), calibrated
  once to equal wall-clock (§7), verified in-harness by the recorded `cand/champ_prefix_ms_per_move` ratio
  ∈ [0.9, 1.1] (house gate). Don't start ID iteration d+2 if > ~50% of the budget is already spent; abort
  mid-iteration when the budget hits.

**Leaf = v2.9.2 curve125, RAW float score-diff (NOT tanh) — pre-registered pick.** Call
`flat_leaf.flat_virtual_score_v2_float(state, 0, cfg, bag_close)` once per horizon node (Cython, 23.9 µs,
bit-identical to the pure-Python reference — [EQUAL_TIME_BENCH_CY.md](EQUAL_TIME_BENCH_CY.md) gates). P0-POV
always (production cap==opp_cap=8 makes the leaf antisymmetric; one call per node serves both movers).
Why raw points and not `tanh(leaf/15)`:

1. For pure minimax a strictly monotone transform is decision-neutral — tanh buys nothing.
2. Aspiration widths and futility margins live naturally in point-space; under tanh they become
   position-dependent (a ±3 window is ~0.2 tanh-units at diff 0 but ~0.001 at diff 30).
3. tanh saturates exactly where αβ needs resolution to keep bounds sharp: at |diff| ≳ 30 adjacent leaf values
   become float-indistinguishable ⇒ degraded ordering, mushy TT bounds, arbitrary tie-breaks in won/lost games.
4. Terminal exact values (`flat_base_score`) and the exact-K solver's values are in points — one consistent scale.

The champion's tanh/value_norm=15 exists to put Q in [-1,1] for PUCT prior mixing — irrelevant in αβ.

## 2. State handling — copy-state vs make/unmake (the feasibility fork)

**What the engine supports TODAY (verified in-source, not from docs):**

- `StateUpdater.apply_action` — deepcopy-then-mutate (what `Game.get_next_state` wraps). The deepcopy is the
  custom `CarcassonneGameState.__deepcopy__` (2026-05-13, cut wallclock 3.3×; "already 554×-optimized" per
  PUCT_PRIORS_RESULTS.md) but is still an object-graph copy: ~100–400 µs midgame (Stage 0 measures it exactly).
- `StateUpdater.apply_action_inplace` / `Game.apply_action_inplace` — **apply-only. There is NO undo/unmake
  anywhere in the engine or src/** (grep `unmake|undo|rollback`: only `mcts._undo_vloss`, which is virtual-loss
  bookkeeping). Confirmed independently by A_SMALL_SPEC §2 ("apply-only — there is no undo/unmake"; solver
  make/unmake = fresh 3–5 day build, BACKLOG 2026-06-21, STATUS "~week eng").
- The stepping path has already been attacked twice and declined: stepping-Cython (2026-07-06, PUCT_PRIORS_RESULTS
  — "Python-object churn on engine objects, not int math"; the de-objectify spike measured ~1.1–1.2× end-to-end,
  break-even) and compact/flat engine rewrites (multi-week, deferred).

**DECISION (v1): copy-state via `get_next_state`.** Rationale, quantified:

- Make/unmake is a 3–5 day OOM-history, silent-corruption-risk build (A_SMALL_SPEC §4: undo must bit-exactly
  restore `open_positions`, centroid sums, placed_coords, meeple lists, scores after `remove_meeples_and_update_score`,
  phase/current_player, `next_tile`/deck — and `PointsCollector` side effects on completed features). Its payoff is
  ~3–5× steps/sec (the A-small estimate for removing the deepcopy). At effective branching b_eff ≈ 4–6 (§7),
  3–5× nodes ≈ **+0.7–1.0 ply** of ID depth. That is real but NOT regime-changing — it cannot turn a 4-ply agent
  into a 7-ply agent.
- Therefore the cheap copy-state prototype fully answers the strategic question: if copy-state C6 reaches useful
  depth and lands within ~1 ply / one screen-σ of the champion, make/unmake is the identified follow-up lever;
  if copy-state C6 is clearly short (≤4 plies) or clearly loses, make/unmake's +1 ply wouldn't have saved it and
  the 3–5 day build is declined without being paid for. This is the roadmap's "surface cost first" applied to the
  fork itself.
- **Pre-registered escalation rule:** fund make/unmake ONLY if (a) Stage-0 lands in the gray zone (median
  completed depth = 5 plies, §7), or (b) the Stage-1 screen lands in [−35, +35] elo with the depth telemetry
  showing budget-truncated iterations — i.e., the one case where +1 ply plausibly flips the verdict. Joshua
  authorizes; it is A_SMALL's §4 build, shared with the solver family (one build serves both if ever funded).
- The search driver stays **pure Python** in v1: at ~100–400 µs per engine step, Python loop overhead (~1–5 µs/node)
  is noise. A Cython driver is not a v1 concern (profile-the-production-path rule — the cost is in the engine step).

Memory: copy-state αβ is depth-first — live states = O(depth × branching) boards ≈ a few hundred, trivially small.
None of the exact-solver's K≥4 RAM pathology applies at these horizons (that was millions of memoized subtrees).

## 3. Transposition table — and whether transpositions even occur

**Key:** `blake2b-128(string_representation(board))` — the proven compact-key recipe from the endgame solver
(`endgame_solver._key`, deployed 6f9dd08, ~16 B/entry key). `string_representation` (game_wrapper.py:602) already
includes placed tiles+rotations, placed meeples, scores, meeples-in-hand, current_player, **phase**, `len(deck)`,
and next_tile — under a FIXED deck (clairvoyant, per game) `len(deck)` pins the ply and the deck suffix is
implied, so nothing else is needed. It is memoized per Board (`_str_repr_cache`) so the hash input is computed at
most once per node. **The TT is valid only within one game** (a new game = a new deck ⇒ same key would mean a
different future): clear the TT at game start, PERSIST it across the game's moves (see below — this persistence is
where most of its value lives). No Zobrist build in v1: incremental hashing needs engine hooks (same class of work
as unmake); blake2b-on-memoized-sr is µs-scale and proven. Revisit only if Stage 0 shows hashing > ~15% of node cost
(then: probe/store only at remaining-depth ≥ 2, which skips the b^d frontier nodes and most of the cost).

**Do transpositions occur under a fixed deck? Mostly NO — pre-registered honest analysis.** In chess, the TT
collapses move-order permutations. Here the deck order is FORCED: at ply p every branch has drawn the same tiles
in the same order with the same mover. Cross-branch convergence to a byte-identical (board, meeples, scores,
phase) therefore requires one of:

1. **Duplicate-tile commutation** — the deck's copies of the same tile type (base game: 72 tiles over ~24 distinct
   types) drawn at plies i and j within the horizon, placed at X-then-Y in one branch and Y-then-X in another,
   both orders legal, with identical intervening meeple decisions. Real but narrow: needs a same-type pair inside
   a 4–8 ply window AND commuting legality AND matching meeple lines. Expected: low single-digit % of nodes.
2. **Meeple-line convergence** — e.g. place-meeple-then-immediately-scored vs never-placed can converge on board+
   meeple count, but `scores` (in the key) then differ. Convergence with equal scores: rare.

So the "chess-engine TT collapse" premise is **weak here and we say so plainly**. The TT is still load-bearing,
for three guaranteed (not probabilistic) reuse patterns:

- **ID re-search:** every node searched at depth d−2 is re-probed on the same lines at depth d — the stored best
  move gives near-perfect ordering (this, not transposition collapse, is most of a chess TT's value too).
- **Intra-turn reuse:** the harness asks the agent for TWO decisions per turn (tile, then meeple). The meeple-
  decision search re-enters the exact subtree the tile-decision search just explored — with a persisted TT this
  is the αβ analog of the champion's reuse_tree (+39 clair). Free, and clairvoyant-only is fine because C6 is.
- **PVS/aspiration re-searches** hit the TT's stored bounds instead of re-expanding.

**Entry:** `(value: f64, flag: EXACT|LOWER|UPPER, remaining_depth: u8, best_action: int, move_no: u8)` — the
solver's fail-soft flag scheme (`endgame_solver` `_EXACT/_LOWER/_UPPER`) reused verbatim. **Replacement:**
depth-preferred with age override (replace if `new_depth ≥ old_depth` or `old.move_no < current_move_no − 4`);
plus the solver's freeze-at-cap semantics (`_put`) as the memory valve. **Cap:** default **2,000,000 entries**
(≈0.3–0.4 GB as a Python dict; W=14 workers ≈ 5 GB, fine on 42 GB), env `CARCASSONNE_AB_TT_CAP`.

**Pre-registered Stage-0 measurement (make-or-break telemetry, not a solo kill):** at fixed depth 6 on the
20-position suite, (a) cross-parent EXACT-hit fraction (true transpositions), (b) node count TT-on vs TT-off.
Expectation on record: (a) < 10%. If confirmed, the TT stays (ordering + intra-turn reuse justify it at this
size) but the finding is written into the close-out so nobody re-sells the TT premise later.

## 4. Move ordering, pruning, and what we reject

Midgame branching (bench suite: legal 1–55/ply; tile plies ~15–40, meeple plies ~2–10 — Stage 0 measures the
distribution) is chess-like or worse, and ordering is THE lever that turns b into ~√b. Staged, cheapest-first:

1. **TT best move** — try first, NO child generation for the others yet (probe is a dict lookup).
2. **Killers** — 2 slots per ply level, tried next if legal (mask check only). Killer = an action index that
   produced a β-cutoff at the same ply elsewhere. Action indices are globally encoded (offset-anchored), so a
   killer is meaningful across siblings; legality is checked against the node's mask before use.
3. **Δleaf full ordering** — only if no cutoff yet: step ALL remaining children (`get_next_state`) and sort by
   child leaf (desc for the max-mover, asc for min). This is byte-for-byte the signal the champion's priors are
   built from (softmax(Δleaf/τ_p) — `heuristic_prior_mcts._legal_deltas`), reused as an ordering rather than a
   distribution. The stepped child boards are kept for recursion, so the step cost is shared with the search
   itself; the incremental cost of ordering is L × 23.9 µs leaf calls.
4. **History heuristic — DEFERRED (not in v1).** Δleaf is a stronger per-position signal than a global counter
   table; history only pays when eval-free ordering is needed, which stage 3 already isn't. Revisit only if
   Stage-0 telemetry shows stage-3 is reached at most cut nodes.

**LMR (late-move reductions) — flag-gated, default OFF in v1, swept in Stage 1.5.** Assessment: plausible-win —
branching is high, the Δleaf ordering is informative, and reductions on moves ranked ≥ 5 at remaining-depth ≥ 4
(reduce 1 turn = 2 plies, re-search on fail-high) is the standard recipe. But LMR changes move choice (unlike
TT/PVS/killers, which are value-preserving), so it must NOT be in the correctness gauntlet path and earns its
place via an A/B cell, not by default.

**Futility pruning — flag-gated, default OFF.** At frontier TILES-phase nodes (remaining-depth = 2, i.e. one
turn), skip children whose parent-leaf + margin ≤ α. Margin must exceed the real per-turn leaf swing — farms and
closures can move the leaf by double digits in one turn, so the default margin, if enabled, is set from the
Stage-0 measured p95 one-turn |Δleaf| (expected ~8–15 points). Mis-set futility silently weakens play; OFF until
the sweep says otherwise.

**Null-move pruning — REJECTED (pre-registered, two independent grounds; do not revisit):**

1. **A null move is ill-defined under a fixed deck.** "Skipping" the mover's placement hands the current tile —
   and every subsequent draw — to the other player: the null-moved game has a different tile→player assignment
   for the entire remaining deck. It is not a conservative relaxation of the real game (unlike chess, where a
   null move only concedes tempo); the engine's actual PassAction *discards* the tile, which changes the board
   economy instead. Either reading searches a different game.
2. **The zugzwang analog EXISTS here** (the task brief's "no zugzwang analog" is the one claim we reject):
   forced-feed positions — every legal placement of the drawn tile extends the opponent's city/farm — are
   common, i.e. "moving hurts" is a normal Carcassonne situation. Null-move is unsound precisely where zugzwang
   lives, and here it lives everywhere.

LMR + the Δleaf ordering are the sound depth-savers; nothing null-move-shaped goes in.

**Window-overflow edge:** `get_valid_moves` can raise `WindowOverflowError` deep in a hypothetical line (board
drifts to the 35×35 window edge). Catch at the node: return the static leaf for that node (same exposure and
mitigation class as the exact solver / MCTS; rare).

## 5. Endgame handoff — reuse, don't rebuild

The A/B harness already wraps BOTH sides in `_ExactHandoff` (`eval_puct_priors.py:183` — latch at the first
TILES-phase decision with `k_remaining ≤ K`, clairvoyant `endgame_solver.solve(alphabeta=True)`, BudgetExceeded →
prefix fallback). The C6 agent is a **prefix agent only** (`.move(board) -> int`), handed to `_ExactHandoff`
unchanged — the exact tail is identical on both sides and cancels out of the A/B, exactly as in every C-series
cell. **Cells run K=2 both sides** (the C2–C5 house template: solver RAM trivial, per
`reference_exact_solver_eval_infra`). No solver code is touched. Note also ID-αβ near the end of the deck
naturally reaches terminal states inside its own horizon (it IS the exact solver there), so the handoff K choice
is doubly non-load-bearing for C6.

## 6. Parameters — defaults + sweep list

| # | Knob (`AlphaBetaConfig` field / flag) | v1 default | Sweep (only if screen fires / gray) | Notes |
|---|---|---|---|---|
| 1 | `step_budget` (`--cand-ab-steps`) | **calibrated in Stage 0** (expect ~25–35k child-steps/decision) | none — it IS the equal-wall-clock normalizer | ratio gate ∈ [0.9,1.1] in-harness |
| 2 | `max_depth` | 64 plies (safety cap) | none | budget binds first |
| 3 | ID schedule | 2,4,6,… (+2 plies/iter), horizon TILES-only | none | §1 |
| 4 | `asp` aspiration half-width | 3.0 pts | {0=off, 2, 5} | fail ⇒ ×4 then full |
| 5 | `pvs` | on | 1 ablation cell off | value-preserving |
| 6 | `tt_cap` entries | 2,000,000 (`CARCASSONNE_AB_TT_CAP`) | {500k} if RAM-pressed | freeze-at-cap |
| 7 | TT replacement | depth-preferred + age(4 moves) | none | §3 |
| 8 | `killers` per ply | 2 | {0} ablation | |
| 9 | ordering | tt→killer→Δleaf staged | Δleaf-only ablation | §4 |
| 10 | `lmr` | **off** | {on: reduce 2 plies, rank≥5, rd≥4} | move-changing — swept, not defaulted |
| 11 | `futility` margin | **0 = off** | {p95 one-turn Δleaf from Stage 0} | move-changing |
| 12 | leaf | env DEFAULT_CONFIG (= production curve125 under the standard exports), raw float, P0-POV | none (leaf axes are C5's turf) | `--cand-leaf-json` plumbing reused for provenance/hash only |
| 13 | endgame K (harness) | 2 both sides | none | §5 |
| 14 | tie-break | lowest action index | none | determinism |

## 7. Stage 0 — COST SURFACE (the go/no-go gate; runs BEFORE the agent build)

**The roadmap's "surface cost first". ~0.5 day dev + <1 box-h. Nothing else is built until this passes.**

New `scripts/classical_search/bench_ab_cost.py`, single-thread, `nice -n 19`, local 5900XT, on the SAME 20 fixed
deterministic positions (plies 30–140) as `bench_equal_time_cy.py`, plus a re-measure of the champion
(PUCT float @2750, reuse off) on that suite for the budget reference (interpolated prior: **~3.1 s/move**
single-thread median — 2845 ms @2500 / 3423 ms @3000, [EQUAL_TIME_BENCH_CY.md](EQUAL_TIME_BENCH_CY.md)).

Micro-measurements (each by ply bucket early/mid/late):
- `flat_virtual_score_v2_float` µs (sanity: ≈23.9);
- `get_next_state` µs (the copy-state step — THE number this design leans on; derived prior: ~1.14 ms/sim at
  L≈8–16 children/expansion implies ~70–140 µs/child-step, but that derivation is exactly what must be replaced
  by measurement);
- `get_valid_moves` µs (mask build, tile vs meeple phase);
- `string_representation` + blake2b µs;
- branching distribution: legal-count histogram by phase.

Then a ~200-line throwaway fixed-depth αβ (Δleaf ordering only, no TT — the floor) + the TT variant:
- child-steps and wall to COMPLETE depth d ∈ {2,4,6,8} per position;
- effective branching b_eff = (N(d)/N(d−2))^(1/2);
- TT-on vs TT-off node ratio at d=6, and cross-parent EXACT-hit fraction (§3 telemetry);
- **achievable depth**: max completed d within the champion's measured single-thread budget per position.

Arithmetic this bench confirms or kills: budget ≈ 3.1 s ÷ (step+leaf ≈ 100–160 µs) ≈ **~25k child-steps/decision**
— the same order as the champion's ~2750 sims × L ≈ 22–40k child-steps. At b_eff ≈ 4–6, 25k steps ≈ **6–7 plies
(3+ turns) full-width exact**. If the step cost comes in at the pessimistic end (~400 µs) that drops to ~4–5 plies.

**Pre-registered Stage-0 verdict rules (midgame positions, plies 30–100, median over positions):**
- **GO** — completed depth ≥ 6 plies (3 full turns) within budget. Proceed to the agent build.
- **DECLINE** — ≤ 4 plies. Write the close-out: full-width exact search 2 turns deep cannot beat a 2750-sim
  prior-guided tree whose leaf already encodes 1-turn tactics; make/unmake's +0.7–1.0 ply (§2) provably cannot
  reach 6 from 4 either, so the 3–5d unmake build is declined in the same breath. C6 CLOSED on cost, ~zero
  compute spent, champion untouched.
- **GRAY (= 5 plies)** — attended decision for Joshua with the §2 escalation arithmetic on the table
  (make/unmake would put ~6 in reach; is a 3–5d build worth a coin-flip screen?).

Artifacts: `measurement/classical_search/C6_COST_SURFACE.md` + `ab_cost_raw.json`. No results.csv row (bench, not
an experiment).

## 8. Stage 1+ — build, integration, neutrality (only on Stage-0 GO)

**New module `src/carcassonne_ai/alphabeta_agent.py`** — sibling of `heuristic_prior_mcts.py`, same house shape:
- `@dataclass AlphaBetaConfig` (fields = §6 knobs; `resolved_leaf_cfg()`; `as_manifest()` — full resolved config
  incl. leaf_cfg + leaf_hash, mirroring `HeuristicPriorConfig.as_manifest`).
- `class AlphaBetaAgent`: `__init__(game, cfg, seed=None)` (seed accepted-and-unused — the agent is fully
  deterministic; kept for constructor symmetry), `.move(board) -> int`, `.clear()` (drops TT — called at game
  start by the harness prefix wrapper), and telemetry counters read by the harness into per-game results:
  `steps_used`, `nodes`, `tt_probes/tt_exact_hits/tt_cross_parent_hits`, `depth_completed` (per-move list →
  median/p10 into the manifest — this is the telemetry the §9 gates read).
- NOTHING in `mcts.py` / `heuristic_prior_mcts.py` / `fair_agent.py` is modified.

**Harness integration (`scripts/classical_search/eval_puct_priors.py`)** — the same add-a-candidate pattern the
round-robin extension used (`_parse_candidate` / `_worker_init` / `_play_one` / `_variant_sig` / `_cell_tag`):

```
--candidate ab                        # _parse_candidate: 'ab' -> ("ab", None)
--cand-ab-steps INT                   # child-step budget per decision (required with --candidate ab)
--cand-ab-max-depth INT   (64)
--cand-ab-tt-cap INT      (2000000)
--cand-ab-asp FLOAT       (3.0)       # 0 = off
--cand-ab-no-pvs                      # ablation
--cand-ab-killers INT     (2)         # 0 = off
--cand-ab-lmr                         # default off
--cand-ab-futility FLOAT  (0 = off)
--opp-reuse-tree                      # NEW: let the --opponent puct sibling run reuse_tree=True
                                      # (today _champ_puct_cfg hard-forces False — needed for the
                                      # champion-of-record confirm cell)
```

In `_play_one`: `cand_kind == "ab"` builds `_AbPrefix` (an `AlphaBetaAgent` wrapper exposing `.move`, calling
`.clear()` once at construction), wrapped in `_ExactHandoff` exactly like the puct/heur candidates. Two
`_resolve_specs` relaxations: (a) `--opponent puct` currently *requires* `--candidate puct`
(eval_puct_priors.py:333) — allow `("ab","puct")` with `opp_sims` taken from an explicit `--champ-sims`
(no cand_sims exists for ab; make `--champ-sims` mandatory in that combination); (b) `--cand-sims` not required
for `--candidate ab`. Cell tag: cand token `ab<steps>[+lmr…]` → e.g. `rr_ab28000_vs_puctchamp2750_k2`. Manifest
adds the full `AlphaBetaConfig.as_manifest()` + per-move depth telemetry; both sides' leaf_hash recorded (Trap 1).

**Default-OFF / bit-identity gate:** with `--candidate` ≠ `ab`, the patched harness must reproduce an existing
cell byte-for-byte (same seeds ⇒ same games; rerun one cached C5 mirror cell, n=20). Pytest: flag parsing, and
`--candidate ab` never constructed unless asked.

**Correctness gauntlet (blocking, before any strength cell) — `tests/test_alphabeta_agent.py`:**
1. **Solver gauntlet (the A-small AB-gauntlet pattern):** on the frozen K2/K3 endgame suites, run the agent with
   unlimited budget and depth ≥ 2K (so its horizon is terminal-only) — the root value and an optimal action must
   match `endgame_solver.solve(mode="clairvoyant", alphabeta=True)` **exactly** (same P0-POV points scale; the
   agent at terminal-horizon IS that solver). This tests minimax convention, mover handling, TT flags and PVS in
   one shot against trusted ground truth.
2. **Value-preservation:** fixed depth 4 on 10 midgame positions — TT/PVS/killers/aspiration ON vs all OFF give
   identical root value + move (LMR/futility explicitly excluded: move-changing by design).
3. **Determinism:** same board + budget twice ⇒ identical move and node count.
4. **Meeple-extension:** horizon never lands on phase==MEEPLES (assert on the search trace).

**Stage 1 — SCREEN.** `c6_ab_screen_vs_puctchamp2750_k2`: `--candidate ab --cand-ab-steps <calibrated>
--opponent puct --champ-sims 2750` (reuse OFF flag-sibling, the C2–C5 template), n=100 deck-paired, K=2, fresh
band **1.40e10** (verify unused at launch: grep scripts + results.csv, per the C5 seed-band discipline; ≥ the
clean-eval floor via `ep.assert_clean_eval_seed_range`). 1σ_paired ≈ ±25 elo. **~1.5–2 box-h** (both sides
~3.1 s/move; the C5 n=100 s2750 cells ran 2425–3002 s two-box).

**Stage 1.5 (conditional, screen fired or gray):** ≤3 knob cells at n=100 (lmr-on; asp {0,5}; futility-p95) —
pick the best single config, no factorials.

**Stage 2 — CONFIRM.** `c6_ab_confirm_vs_puctchampreuse2750_k2`: vs the **champion of record** (reuse_tree=TRUE
via `--opp-reuse-tree`, the PRODUCTION.yaml agent verbatim), n=400 paired, fresh band **1.42e10**. ≈6 box-h.
ms-ratio gate ∈ [0.9, 1.1] on the recorded prefix ms/move, both stages.

## 9. Kill-gates + risks (pre-registered)

**Decision tree:**
- **K0 (cost).** Stage-0 median completed depth ≤ 4 plies in budget → **DECLINE C6**, no agent build, no compute.
  (= 5 → attended gray-zone decision; §7.)
- **K1 (correctness).** Solver gauntlet mismatch that survives a day of debugging → stop and report; a
  minimax-convention or TT bug produces confident garbage, and no strength cell runs before gauntlet-green.
- **K2 (screen).** n=100 paired < +35 elo or paired_z < 1.5 → **C6 CLOSED (null/loses)**. No lone-spike promotion;
  a wing that contradicts the depth telemetry (e.g. +40 while median depth was 4) is re-measured at a fresh
  sub-band (1.41e10) before promotion (noise-signature rule).
- **K3 (confirm).** n=400 paired vs the reuse-ON champion: needs ≥ +25 elo AND paired_z ≥ 2.0. Fail → close as
  screen-noise.
- **TT telemetry (informational, folded into close-out, not a solo kill):** cross-parent hit rate < 10% confirms
  the fixed-deck no-transposition analysis (§3) — recorded so the "chess-engine" framing dies with data even if
  C6 wins on ordering+depth alone.
- **Any outcome:** six-touch close-out (results.csv `c6_*` → DECISIONS index line → status stamp on THIS doc →
  CLAIM_REGISTRY row → STATUS top block → roadmap C6 line), then `scripts/doc_lint.py`.

**Even a WIN is clairvoyant-only.** Pre-registered grading: a K3 pass yields a *clairvoyant/dev* champion-flip
proposal at most (self-play teacher / clair-ruler / analysis use) — the reuse_tree precedent (CL-044). αβ cannot
run fair (chance nodes have no cutoff bound — the A-small §0 assert); the only conceivable fair form is
PIMC-over-αβ-determinizations (k_dets × the full cost, and it inherits the ~120-elo midgame tax that CL-048 showed
search does not close), which is explicitly OUT of scope and gated on the post-E4 fair conversation. No production
proposal on clair evidence alone.

**Risks:**
1. **Cost surface fails (likely-ish).** Mitigated by ordering: Stage 0 runs first, ~free.
2. **Silent search bug** (mover convention, TT bound flags, aspiration fail handling). Mitigated: solver gauntlet
   + value-preservation tests before any cell.
3. **Horizon effect on farms:** farm swings resolve far beyond a 3-turn horizon; αβ leans on the leaf's farm terms
   exactly as the champion does — same leaf, so this is A/B-neutral in expectation, but it caps what "exact to
   depth 6" is worth. Noted so a null isn't over-interpreted as "search is dead".
4. **Opportunity cost is the real risk** (the A_SMALL lesson): E4 (human anchor) and A-small/C-cheap outrank C6 on
   the roadmap; the ~2–4d estimate here is Stage-0-gated precisely so the likely outcome (decline) costs half a
   day, not four.

## Budget summary

| Stage | What | Cost |
|---|---|---|
| 0 | cost-surface bench (go/no-go) | ~0.5 d dev + <1 box-h |
| 1-build | agent + harness flags + gauntlet (only on GO) | ~1–1.5 d dev |
| 1 | screen n=100 | ~2 box-h |
| 1.5 | ≤3 knob cells (conditional) | ~6 box-h |
| 2 | confirm n=400 (conditional) | ~6 box-h |
| **Total** | decline-case ≈ **0.5 day**; full-fire worst case ≈ **2–4 days** | matches roadmap "~2–4d" |

## Traps found while reading (design-relevant)

1. **Consecutive same-mover plies** (TILES→MEEPLES, `state_updater.py:26-28` vs `next_player`): naive per-ply
   negamax sign flip is wrong — use the `endgame_solver` P0-POV/current_player convention (§1).
2. **`--opponent puct` requires `--candidate puct`** today (`_resolve_specs`, eval_puct_priors.py:333) and
   **`_champ_puct_cfg` hard-forces `reuse_tree=False`** (line 256) — both need the §8 relaxations for the ab
   candidate and the reuse-ON confirm cell.
3. **Env-global leaf (C5 Trap 1 carried forward):** both harness sides resolve `DEFAULT_CONFIG` from env at
   import; a worker missing the production exports silently runs the wrong leaf (env default is cap5+3open, and
   post-CL-051 the curve is env-wired). Mitigation unchanged: per-side leaf_hash in every manifest.
4. **TT key validity is per-game only** — `string_representation` + fixed deck pins the future *within* a game;
   across games the same key means a different deck. Clear the TT per game, persist per move (§3).
5. **Wall-clock budgets are load-sensitive** (C4 cell: ~6.46 s/move under W-parallel load vs ~3.1 s single-thread)
   — hence the child-step budget, calibrated once, verified by the in-harness ms-ratio gate (§1).
6. **`get_valid_moves` can raise `WindowOverflowError`** deep in a line — catch at the node, return static leaf.
7. **Stepping path is already litigated**: stepping-Cython declined 2026-07-06 (object churn), de-objectify spike
   break-even (BACKLOG:57) — don't re-propose them as C6 accelerants; the only real step lever is make/unmake
   (§2, escalation-gated).
