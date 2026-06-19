# Level-2 L2-3 — endgame regret suite (PROTOCOL, pre-registered 2026-06-19)

> **Measurement gate only (Joshua's standing guardrail + explicit instruction 2026-06-19).**
> NO train / promote / redesign / modify-iter8 follows. Executes the §6 *solver-grounded*
> component of [docs/MEASUREMENT_FIRST_SPEC_2026-06-18.md](../../docs/MEASUREMENT_FIRST_SPEC_2026-06-18.md)
> (V9/V10) — an EXACT endgame solver gives ground-truth best-move labels, killing the
> clairvoyant-label circularity of the deep-search "reference move" (which would only measure
> agreement-with-deep-search, not correctness).

## Why this experiment
L2-1/L2-2 placed iter8 above the heuristic rungs on full-game Elo, but every label there is
*in-ecosystem* (the ruler is the heuristic itself). In the deep endgame (≤~6–8 tiles) the game
is small enough to **solve exactly** → ground-truth optimal moves independent of any heuristic.
We then measure each agent's **regret** (points lost vs optimal) and **top-1 agreement**. This is
the first label in the whole program that is NOT circular.

**⚠️ This is a DIFFERENT question from full-game Elo and its conclusions are kept SEPARATE**
(Joshua #7): endgame-move-optimality ≠ full-game strength. A strong full-game agent can have
endgame regret (and vice-versa). Do not merge the two verdicts.

## Ground truth — two modes (Joshua #4), explicit per position
Both computed by an exact solver over the final ≤K tiles; leaf = the REAL final score-diff
(`flat_leaf.flat_base_score`, exact `count_final_scores` equivalent — NOT a heuristic leaf).

1. **PREFERRED — bag-expectation (marginalized).** Expectiminimax: at each draw a CHANCE node
   marginalizes the unknown remaining deck (uniform over the remaining-bag multiset; each player
   decides knowing only tiles drawn so far). This is the honest game value under hidden future.
   The drawn tile is revealed before placement (real Carcassonne), so expectiminimax = the exact
   value (no info-set subtlety: the only hidden state is the future order, which the chance nodes
   integrate out). Tractable to smaller K than mode 2.
2. **FALLBACK — perfect-information (clairvoyant).** Minimax with the KNOWN real future deck order
   (`[next_tile]+state.deck`), alpha-beta. **Clearly labeled `clairvoyant`.** This matches how the
   production agents actually plan (clairvoyance gap measured small, CL-022), so it is the
   apples-to-apples optimum for clairvoyant agents; tractable to larger K.

Per position we record WHICH mode produced the label. Where both are computed (small K), V10
cross-checks they agree on the optimal-set; divergence bounds the clairvoyance advantage in the
endgame. Agent regret is reported under **both** measures (each agent's move is evaluated by the
same solver mode as the ground truth: regret = V*(best) − V*(agent move), in raw points, ≥0).

## Position suite + PROVENANCE (Joshua #2) — `measurement/level2/l23_positions.jsonl`
Positions are sampled by replaying fresh-band games and snapshotting when exactly K tiles remain.
Each record is fully reconstructable + self-describing:

| field | meaning |
|---|---|
| `gen_id`, `source_agent` | which generator game (e.g. `heur_v2_7@800` self-play) |
| `seed`, `ply` | **source game deck seed + move index** → replay to reconstruct the exact Board |
| `k_remaining` | tiles left to draw (incl. the in-hand `next_tile`) |
| `to_move` | player to move (0/1) |
| `scores` | `[s0, s1]` accumulated mid-game score |
| `meeples` | per-player free-meeple counts + placed-meeple summary |
| `bag_multiset` | the remaining-bag tile-type multiset (the hidden info) |
| `known_order` | the real remaining order (for the clairvoyant mode; marked `marginalized` when the GT mode integrates it out) |
| `legal_n` | number of legal moves at the position |

Bands: **3.2e9** (per the ladder protocol's L2-3 allocation; disjoint from L2-1/L2-2). Suite is
FIXED once generated (committed) so every agent + re-run sees identical positions.

## K buckets (Joshua #3)
Target **K ∈ {1,2,3,4,5,6}**, extending to 7–8 only if the solver stays tractable. Feasibility is
bounded empirically: expectiminimax (mode 1) is tractable to a smaller K_max than clairvoyant
(mode 2) — the actual K_max per mode is measured in the smoke and recorded. Positions whose solve
exceeds a node/time budget are SKIPPED and logged (no silent truncation). Bucketed reporting by K.

## Agents under test (Joshua #5)
iter8 (production NeuralMCTS@200, c=3.0), heur@800, heur@1600, **heur@3200**, + greedy (1-ply) and
heur_v1@200 (optional, cheap). Each agent's move at a position = `agent.best_action(board)`. Agents
play at their normal settings (incl. clairvoyant production search) — we are measuring THEIR move,
scored by the solver.

## Metrics (Joshua #6), per agent × {GT mode} × {K bucket}
- **top-1 agreement**: fraction where the agent's move ∈ the solver's optimal-set.
- **mean / median regret** (points lost vs optimal).
- **blunder rate**: fraction with regret > 2, > 5, > 10 points.
- **by remaining-tile bucket** (K).
- **examples**: the largest iter8 regret losses AND its largest wins-over-the-field (lowest-regret
  positions where heuristics blunder) — concrete annotated positions.

## Validation tests (pre-registered)
- **V9 (solver self-consistency):** the solver's own best move, played out under solver-optimal
  continuation, realizes V* exactly (by construction; tests the solver). 100% required.
- **V2 (degenerate / last tile):** at K=1 (no hidden future) mode-1 == mode-2 exactly.
- **V-brute:** on tiny K (≤2) the alpha-beta/expectiminimax value matches a naive full-enumeration
  brute-force solver (separate reference impl).
- **V-mono:** solver value is monotone under perfect info ≥ marginalized for the to-move player's
  best (clairvoyance can't hurt) — a sanity bound, not a hard gate.
- **Provenance smoke:** every position reconstructs bit-identically from `(seed, ply)`; the recorded
  `bag_multiset` / `scores` match the reconstructed Board.

## Deliverables (in `measurement/level2/`)
`LEVEL2_L23_PROTOCOL.md` (this) · `l23_positions.jsonl` (fixed suite) · `scripts/level2/endgame_solver.py`
+ `gen_endgame_positions.py` + `endgame_regret.py` + `tests/test_endgame_solver.py` ·
`L23_REGRET_RESULTS.json` · `LEVEL2_L23_VERDICT.md` (separate from the Elo verdicts) · results.csv
rows (regret/agreement, NOT elo) · a CL-registry entry for the endgame-regret finding.

## Follow-up (Joshua #8)
After L2-3: run the missing **same-band iter8 vs heur@3200** full-game comparison (orch eval) — the
one rung of the validated ladder iter8 was not yet measured against. Reported under the **Elo**
verdict, kept separate from the endgame-regret verdict.
