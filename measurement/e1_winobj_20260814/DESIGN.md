# E1 — win-probability endgame objective (exact-K solver): DESIGN + 0-game pre-gate

> **⚠️ STATUS 2026-08-14 — PRE-REGISTERED DESIGN + FREE INSTRUMENT. 0 GAMES.**
> Committed **BEFORE the pre-gate reads a single corpus number** — git history is
> the proof. No `experiments/results.csv` row, no band claim, no claim id,
> `governance/PRODUCTION.yaml` untouched. House precedent for the format:
> [F6 pre-gate](../f6_winprob_20260814/DESIGN.md), j13, farm-war, adaptive-k.
>
> Roadmap slot: **Track E, E1** — "win-probability endgame objective +
> pre-registered exact-K winrate re-run". Scope guard: E1 is the **objective at
> the incumbent K**, NOT depth — CL-076/F13 closed deeper-than-production exact
> endgame play; nothing here re-proposes depth.

## 0. What E1 rests on (established facts, read first)

1. **The solver maximizes margin, not win** — F6 pre-gate §0 established it at
   the code level: `rust/carc/carc-core/src/endgame/mod.rs:13-20` (and the
   SHIPPED latch `rust/carc/carc-core/src/fair/solver.rs:6-7`): *leaf value =
   the REAL final score differential `flat_base_score(state, 0)`; P0 maximizes,
   P1 minimizes, at every depth, in both modes.*
2. **F6's branch-K kill does not cover this.** F6 killed score-conditioned
   *leaf* posture at close TILE decisions (0/673 binding). Its READOUT states
   explicitly that the last-2-tiles exact-solver regime is E1's question and is
   not adjudicated there.
3. **The incumbent exact-K of the fair deploy champion is `exact_max_k = 2`,
   marginalized** (`governance/PRODUCTION.yaml`; every 2026-08 deploy cell ran
   "exact-K 2 both arms"). CL-076's "K=4 incumbent" is the *clairvoyant harness*
   config of the F13 ladder, a different animal.
4. **Ties are real**: the E4 ledger just recorded a 55-55. The objective must
   define draw handling, not hand-wave it.

## 1. The objective — lattice and tie handling (the spec)

**Margin objective (incumbent, default, bit-identical):** value = expected
final score differential `E[m]`, P0 maximizes / P1 minimizes at every node;
chance nodes average over the remaining-bag multiset.

**Win objective (new, flag-gated `objective="win"`):** node value is the PAIR
`(w, m)`:

* terminal: `m = flat_base_score(state, 0)` (integral), and
  `w = outcome(m) = 1.0 if m > 0 else (0.5 if m == 0 else 0.0)` — the standard
  game-outcome lattice **win > draw > loss with a draw worth half a win**, P0's
  POV. This matches how the eval harness scores W/D/L and how match play does.
* chance node: component-wise expectation over the bag multiset (same grouping,
  same insertion-order accumulation as the margin mode) — so `w` backs up as
  exactly `E[outcome] = P(win) + ½·P(draw)`.
* decision node: P0 maximizes / P1 minimizes **lexicographically**: compare `w`
  first (with tolerance `WIN_TIE = 1e-9` against float-order noise in the
  expectations); if `|Δw| ≤ WIN_TIE`, compare `m`. Keep-first scan in legal
  action order (deterministic).
* root: `optimal_actions` = children within `WIN_TIE` of `w*` **and** within
  the existing `TIE = 1e-6` of `m*`; the agent still plays
  `min(optimal_actions)`.

**Why lexicographic and not pure {+1, 0, −1}:** a pure outcome objective
discards the margin information that currently breaks ties, making play
gratuitously indifferent among winning lines (and non-deterministic against
float noise). Win-first-margin-tiebreak is the **smallest semantic change that
flips the objective**: it maximizes `E[outcome]` exactly (the `w` component's
backup is untouched standard expectiminimax), and among outcome-equal lines it
plays precisely what the incumbent plays. Within the solved horizon it can
never score worse in win terms than margin-max.

**Where it lives / does NOT live:** the flag is **solver/search-side, never
LeafConfig** — the leaf hash must not move (same inverted-liveness convention
as surface B: liveness is read from the resolved manifest field
`exact_objective` + a positive control, never from a leaf hash). Clairvoyant
mode **rejects** `objective="win"` loudly: with a deterministic future, outcome
is a monotone function of the deterministic margin, so margin-max is already
win-optimal there and a "win mode" would be a no-op wearing a live flag.

## 2. The mechanism — and the structural theorem that bounds it

The mechanism E1 was queued on: with 2 tiles left and a 3-point lead,
margin-max can prefer a line worth E[+5] with a losing branch over a guaranteed
+1 hold. The solver is exact over its enumeration, so "risk" here means risk
over the **deck marginalization**: `E[m]` averages over draws (the marginalized
mode has no alpha-beta precisely because of those chance nodes), and
`E[m₁] > E[m₂]` is compatible with `P(win₁) < P(win₂)`. The exact-K values feed
final move SELECTION directly (the latch plays `min(optimal_actions)`), so
changing the objective changes picks exactly where win-optimal ≠ margin-optimal
— the regime a fixed lead or deficit creates.

**Proposition (K ≤ 2 inertness).** *At the deployed `exact_max_k = 2`, the win
objective cannot change a single pick.* Proof: the latch fires on a TILES
decision with `k_remaining = deck + hand ≤ 2`, so at most **one** undrawn tile
exists beyond the tile in hand. Every chance node marginalizes the bag
`[next_tile] + deck` **after** a draw, at which point at most one tile remains
⇒ every bag is a **singleton** (probability 1). (The solver's own docstring
records this: "at the deployed `exact_max_k = 2` the post-draw bag never
exceeds one tile" — `fair/solver.rs` detail #3; it holds under the F9/A3
redraw chance too, since set-aside tiles never re-enter the bag.) A solve with
only degenerate chance nodes is a deterministic minimax over a fully-known
future; its values are exact integers; `outcome(m)` is monotone non-decreasing
in `m`; a monotone transform never reorders a deterministic minimax, at any
interior node or at the root. Hence the lexicographic `(w, m)` order coincides
with the `m` order, optimal sets coincide, and `min(optimal_actions)`
coincides. ∎

Corollary: **divergence requires a chance bag of ≥ 2 ⇒ `k_remaining ≥ 3`
upstream of a draw ⇒ a latch at K ≥ 3 — which is a DEPTH change, and depth is
closed (CL-076/F13; the marginalized frontier K≥5 is separately impractical,
MARG_FRONTIER 2026-08-04).** This proposition corrects F6 DESIGN §0's
"the (c) corner is real, bounded to K≤2" — the corner is real only at K ≥ 3;
at K ≤ 2 it is empty by construction, which is precisely the kind of fact the
pre-gate below exists to establish honestly before a cell is funded.

The pre-gate therefore has two jobs: (a) **verify the proposition empirically**
on the real corpora (an engine subtlety — an unexpected extra draw source —
would falsify it and instantly re-open the cell), and (b) put the pre-registered
number on the record so the kill is a measured branch, not an argument.

## 3. The build (flag-gated, default OFF = bit-identical)

* `carc_core::fair::solver` (the SHIPPED latch): `Objective::{Margin,Win}` on
  `SolverConfig` (default `Margin`); win mode adds a parallel `(w, m)`
  expectiminimax (`value_win`/`chance_win`, own TT); `SolveResult` gains
  `win_value: Option<f64>` + `child_win_values` (empty/None in margin mode).
  The margin path is **untouched code** — flag-off bit-identity is structural
  AND gated (below).
* `carc_core::endgame` (the offline/regret transcription): `Config.objective`
  reusing the same enum; `Marginalized+Win` **delegates to the fair solver**
  (one implementation of the changed semantics, per the module's own
  anti-drift philosophy — `ChanceDrop`/`TIE` are already reused this way);
  `Clairvoyant+Win` is rejected (see §1).
* `scripts/level2/endgame_solver.py` (the ORACLE): `solve(...,
  objective="win")`, marginalized-only, same lattice — stays the spec the rust
  answers are gated against.
* Plumbing: `carc-py FairAgentRs(exact_objective=...)` → resolved in `stats()`
  (the manifest surface); `rust_agent.RustFairAgent(exact_objective=...)`
  (kwarg only forwarded when ≠ "margin", so old wheels keep working and the
  default FFI call is byte-identical; a "win" request on an old wheel fails
  LOUDLY); `fair_agent.FairHeuristicPriorAgent(exact_objective=...)`;
  `champion_factory.build_fair_champion(exact_objective=...)`;
  `eval_fair_puct --cand-exact-objective` (candidate side only, rust backend).
* **Positive control** (inverted-liveness, surface-B convention): a pinned
  K=3 position where win-optimal ≠ margin-optimal, solved by BOTH objectives,
  asserting they disagree — proves the flag is live without moving any leaf
  hash. (By the §2 proposition no K≤2 control can exist; the control position
  is found by `scripts/e1_winobj/find_divergence_position.py` and pinned in
  the tests.)
* **Bit-identity gate**: F-c-style — golden fingerprints over real production
  searches and full games at the incumbent config, computed on the pre-change
  tree, asserted unchanged post-change; champion fingerprint tests untouched
  and green; skipif-loudly when `carc_rs` predates the knob. ⚠️ Per-box
  footgun: `carc_rs` is a built wheel — every box (local/laptop) must rebuild
  it before any run that passes `exact_objective`; a stale wheel fails loudly
  at construction, never silently.

## 4. The 0-game pre-gate (this directory)

Instrument: `scripts/e1_winobj/e1_pregate.py`. Corpora (all banked, nothing
played): the champion self-play bank
`measurement/champ_action_logs/champ_games.jsonl` (449 games, `walled`,
lossless replay, final-score integrity assert) and the E4 archives
`measurement/e4_games/*.json` (rules profile resolved FROM each archive,
`ev_loss.py` convention; absent stamp ⇒ pre-fixed_v1 ⇒ `walled`).

At **every exact-K-solved ply** (simulated latch: first TILES ply with
`k_remaining ≤ 2`, then every subsequent ply of the game — exactly the plies
the deployed champion hands to the solver), solve BOTH objectives with the
oracle python solver and record: the two picks (`min(optimal_actions)`), the
two optimal SETS, solve wall-time each, `k_remaining`, and the game's realized
outcome.

Reported:
* `divergence_rate` = share of solved plies where win-pick ≠ margin-pick
  (primary), plus the weaker `set_divergence_rate` (optimal sets differ at
  all).
* On divergent plies (if any): realized-outcome consistency — in the archived
  game, what did the margin-pick cost in wins? ⚠️ **Selection-effect label**:
  archived continuations followed the margin policy, so realized outcomes
  condition on it; this is descriptive, not causal.
* Cost: per-ply solve-time ratio win/margin (median, p90) — the bench the
  build owes (rust ratio to be confirmed at wheel-rebuild time; the
  aggregation change is identical in both implementations and the marginalized
  mode has no alpha-beta to break in either).

### Read-rule — committed NOW, before any number is read

Primary statistic: `divergence_rate` over all solved plies, both corpora
pooled (per-corpus rows reported).

* **Branch K (dies free — cell NOT owed):** `divergence_rate < 1%`. The
  objective almost never (per §2: provably never, absent an engine surprise)
  changes a pick at the plies the champion actually solves ⇒ bounded-tiny;
  honest kill; LEVER_INDEX row MEASURED-AND-KILLED-FREE; the win mode stays
  merged flag-gated default-off as infrastructure.
* **Branch F (fund the cell):** `1% ≤ divergence_rate ≤ 10%`. Fund the
  pre-registered deploy cell (DEPLOY_PREREG draft in this directory).
* **Branch F+ (fund + flag):** `divergence_rate > 10%` — surprisingly large;
  fund AND flag that §2's proposition failed, i.e. an unmodeled draw source
  exists — investigate before the cell runs.

The §2 proposition predicts branch K at exactly 0. **If the empirical rate is
nonzero at all, the proposition is falsified and the discrepancy must be
root-caused before any branch is read** — a nonzero rate with the proposition
intact would mean the instrument or the implementation is wrong, and no branch
adjudicates on a broken instrument.

### If funded: the cell (pre-registered shape, drafted blind)

n=800 deck-paired, fair PIMC k8×1376=11008 BOTH arms (identical search;
**only** the candidate's endgame objective differs), `fixed_v1`+R9, rust
backend, exact-K 2 both arms, `ms_ratio` 1.20 trigger, band
CLAIMED-BY-ORCHESTRATOR, laptop W22 / local W30. ⚠️ **The irony, handled**:
the program's primary statistic is the deck-paired MARGIN, but this lever
*optimizes WIN at margin's expense* — a margin-only read would be structurally
biased against it. The prereg therefore names the **paired win-rate z as
co-primary** with a decision matrix committed before any game (see
DEPLOY_PREREG). Not drafted further here unless a branch funds it.

## 5. Integrity

Replay: per-game final scores must equal recorded (`champ_games` 449/449;
E4 archives all-of-corpus) — any mismatch aborts loudly. E4 rules profile
resolved from the archive, never from a flag; profile-latch conflicts fail
closed. Both-objective solves run in the same process on the same replayed
position object. Tests: `tests/test_e1_win_objective.py` + rust in-crate
tests + the golden bit-identity gate. Cost stated at launch; 0 games.
