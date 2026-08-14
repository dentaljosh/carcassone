# F6 (strategy-scan) — score-differential / win-probability conditioning: DESIGN + 0-game pre-gate

> **⚠️ STATUS 2026-08-14 — PRE-REGISTERED DESIGN + FREE INSTRUMENT. 0 GAMES.**
> This document is committed **BEFORE the instrument reads a single corpus
> number** — git history is the proof. No `experiments/results.csv` row, no band
> claim, no claim id, `governance/PRODUCTION.yaml` untouched. House precedent for
> the format: [j13 pre-gate](../j13_pregate_20260813/READOUT.md), farm-war,
> adaptive-k census.
>
> **Naming collision, read once:** "F6" here is **finding F6 of
> [PRO_STRATEGY_SCAN_2026-08-12](../../docs/research/PRO_STRATEGY_SCAN_2026-08-12.md)**
> ("play the score differential, not just the board"). It is NOT the roadmap's
> Track-F item "F6. Leaf residual-mining" (CL-063, closed) — an unrelated
> number-space. The directory is named `f6_winprob_*` after the scan finding.

## 0. Collision audit — is this axis actually untried? (grep evidence, read first)

The scan tagged F6 **NEW**. That is **only partly right**, and the corrections
change what is worth building. Greps run over `docs/LEVER_INDEX.md`,
`DECISIONS.md`, `experiments/results.csv` for `win.?prob / winshape / risk /
score.?diff / logistic / lambda / value_norm`:

| prior art | what it was | verdict | why it does NOT close F6 |
|---|---|---|---|
| **win-shaping leaf** (`v210_winshape_*`, LEVER_INDEX row "win-shaping / aggressive win-probability leaf") | Re-aim the search value from `tanh(margin/15)` to `tanh(margin/T)`, T=12 (mild, Wave-D) and T=4 (aggressive). Sharper T ⇒ the pooled search value approximates `P(win)` instead of `E[margin]`. | **KILLED 2026-07-05** — mild NULL; aggressive's +18.3/z1.05 screen **failed fresh-band replication** (−27.9; combined n=800 wr 0.493). DECISIONS 2026-07-05: "WIN-SHAPING AXIS DEAD (mild + aggressive)". Notably the n4 screen's positive lean was concentrated in the BEHIND bucket (wr 0.211 vs 0.146) — i.e. the *mechanism F6 predicts* showed up in the screen and then died in replication. | It killed the **global static squash**. It did not test *state-conditioned* posture (a transform whose shape depends on current score diff or phase), and it was a full-game A/B with ±17-elo resolution, not a mechanism instrument. But it is a strong prior AGAINST: the cheapest online form of F6 was measured and is dead. |
| **`value_norm` sweep** (ROADMAP C4, closed 2026-07-08) | The same squash's scale: vn8 / vn15 / vn30. | vn15 confirmed optimal (wings −24.4 / −36.6). | Same static-transform family. Closes the "just make the sigmoid sharper/flatter" corner from a second direction. |
| **Option B / `score_diff` value TARGETS** (`--value-target score_diff`, `wl`, `score_diff_wide`; LEVER_INDEX rows 31–33) | score-diff (or win/loss) as the **training target of a learned value head** (river-era Option B; C6 `score_diff_wide`; the AZ-canonical `wl` target was DECLINED as default). | The whole learned-value route is closed (CL-039/042/049/064/065/066/073). | **Do not conflate.** That axis is "what does a *learned net* regress on". F6 is "what does the *classical* decision rule maximize". No learner is involved in F6. The one transferable lesson is CL-073: outcome prediction ≠ move discrimination — any F6 gate must be a discrimination/decision gate, not a calibration gate. |
| **phase-aware eval weighting** | Leaf weights conditioned on **turn number**. | Bounded-null (killed list, per the scan's own scope table). | Different conditioning variable (turn ≠ score diff), but adjacent: a phase-dependent scale alone is NOT new territory. |
| **exact-K endgame objective** (ROADMAP **Track E, E1**: "win-probability endgame objective + pre-registered exact-K winrate re-run") | Switch the exact solver's objective from margin to win. | **NEVER-TRIED — named and queued since the roadmap was written, still UNSTARTED.** | This IS the (c) corner of F6, already indexed. So the axis is not *unexamined* — it is *unfunded*, with a queue entry. |

**Code-level fact (read 2026-08-14, `rust/carc/carc-core/src/endgame/mod.rs`
docstring, lines 13–20):** the exact-K solver's leaf value is *"the REAL final
score differential `flat_base_score(state, 0)`; P0 maximizes, P1 minimizes, at
every depth, in both modes"* — the shipped endgame **maximizes margin, not
win**, in clairvoyant AND marginalized mode. In clairvoyant mode the objectives
coincide in the decided worlds (a margin-max line is a win-max line when the
future is known and value is deterministic — modulo tie-vs-win preferences,
which margin-max also gets right by magnitude). In **marginalized** mode they
genuinely diverge: `E[diff]` can prefer a line that loses in half the chance
worlds over one that wins in all of them. So the (c) corner is real, bounded to
K≤2 tiles (the latch), and already has a roadmap slot (E1).

**Net position:** F6 is **not** a virgin axis. The static global transform is
dead twice over (winshape T-sweep + value_norm sweep); the endgame-objective
corner is indexed-and-unstarted (E1); what is genuinely untested is
**state-conditioned risk posture** — and before anyone funds *that*, the
question is whether the margin-vs-win distinction ever **binds** at real
decision points. That is what this pre-gate measures, for free.

## 1. Design space — what "score-differential conditioning" could concretely be

Three candidate forms, priced qualitatively. None is being built this round.

### (a) Risk-sensitive utility (variance channel), state-conditioned
The leaf prices a position by expected margin only. A trailing player should
prefer a volatile −5 (prospective-credit-heavy, wide outcome spread) over a
safe −5 (banked, narrow spread); a leader the reverse. The leaf literally
cannot see this: `virtual_score_v2 = banked_diff + prospective credits`, and
two positions with equal totals but different banked/prospective splits are
identical to it.
* **Plug-in point:** leaf post-transform in `leaf_v29.py` (the `v29_util_tanh_t`
  slot shows the shape of such a hook) or a `LeafConfig` term reweighting
  prospective vs banked credit as a function of `sign(margin)` × phase.
* **Cost:** ~free per leaf (a couple of float ops on already-computed parts).
* **Bit-identity risk:** LOW if opt-in default-OFF (house pattern: every leaf
  knob ships default-off, champion hash unchanged).
* **Prior:** the tanh squash *already* delivers a mild version of this
  automatically (Jensen: `E[tanh(m/15)]` over chance prefers spread when
  `m<0`), and sharpening it (T=4) — which strengthens exactly this effect — was
  the killed winshape cell. Prior unfavorable.

### (b) Win-prob transform of the search value, phase/score-dependent scale
`value = tanh(margin/norm(phase, diff))` instead of the fixed norm 15, so the
pooled root Q approximates `P(win)` where it matters (late, close) and
`E[margin]` where P(win) is insensitive (early, lopsided).
* **Plug-in point:** `heuristic_prior_mcts` value mapping (one line) + the rust
  search's mirror — **two implementations to keep in lockstep** (the rust/python
  parity gates make this the highest-friction option).
* **Cost:** free at runtime; expensive in parity engineering.
* **Prior:** worst of the three. Fixed-T is dead at T∈{4,12,15-vs-8,30}; a
  phase-dependent T is the killed static transform × the bounded-null
  phase-aware weighting. Would need this pre-gate to fire LOUDLY to justify.

### (c) Endgame-only: win objective in the exact-K solver (= roadmap E1)
Change the marginalized solver's backup from `max E[diff]` to
`max E[win]` (or lexicographic: win first, margin tiebreak) for the K≤2 latch.
* **Plug-in point:** `carc_core::endgame` backup + `scripts/level2/endgame_solver.py`
  mirror; the 0-mismatch reconcile gate applies (the marginalized/clairvoyant
  cross-asserts in `endgame/mod.rs` would need an objective-aware split).
* **Cost:** small, contained, and the search above the latch is untouched.
  Alpha-beta in clairvoyant mode survives (bounded utility); the marginalized
  mode has no alpha-beta to break.
* **Prior:** the only corner with a *positive* prior: exact-endgame margin
  gains land in close games (+0.57 pts, z 5.95 into close games — DECISIONS
  2026-07-05), and lexicographic win-first can never score worse in win terms
  than margin-max *within the solved horizon*. But the horizon is K≤2 — the
  binding question is how often a margin/win disagreement can even occur in the
  last 2 tiles.

## 2. The free pre-gate instrument (0 games)

**Question:** at real champion decision points where the top moves are
**near-tied in margin**, how often do they differ **materially in win
probability** — and when they do, does the champion take the lower-P(win) arm
while trailing?

**Key design point — why this is measurable at all:** under any *deterministic*
map `P(win) = f(margin, phase)`, margin-near-tied siblings are mechanically
P(win)-near-tied, and the instrument would be circular. The measurable channel
is the **banked/prospective decomposition**: two arms with equal leaf margin
can split differently between `banked = scores[p]−scores[opp]` (realized,
variance-free) and `prospective = leaf − banked` (anticipated, convertible or
not). If realized outcomes show prospective points convert to wins at a
discount (or premium) relative to banked points, then margin-tied arms with
different splits have genuinely different win probabilities — and that
difference is exactly the "safe −5 vs volatile −5" distinction of form (a).

### Corpora (all banked, nothing new is played)
* **Calibration:** `measurement/champ_action_logs/champ_games.jsonl` — 449
  champion self-play games (fair PIMC k4×688, exact K≤2, champion leaf,
  `walled` rules), deck-seed + action-sequence lossless replay, realized final
  scores. Replay is verified against recorded `score_p0/p1` per game.
* **Near-tie decision points:** the tile-tie bank,
  `measurement/tiletie_pricing_20260812/positions/positions_walled_leg*.jsonl`
  (selfplay stratum, 673 positions in `ARMS.json`, `walled`, checksums carried)
  joined with `ARMS.json` (the deduped arm sets, ≤4 arms/position) and
  `champ_picks/champ_picks.jsonl` (the full-champion 8×1376 pick where scored).
* **Epoch discipline:** primary stratum is selfplay/`walled` **only** — the
  calibration corpus and the near-tie bank are the same rules epoch and the
  same agent. The E4 stratum is NOT graded this round: no `fixed_v1`
  self-play calibration corpus exists, 23 games cannot fit a stable logistic,
  and grading `fixed_v1` positions under a `walled`-fitted outcome model would
  manufacture a cross-epoch number (R9 touches farm scoring, hence the leaf).

### Measurements
1. **Stage 1 — calibration scan.** Replay all 449 games; at every TILES-phase
   ply record, for each POV p∈{0,1}: `k_left` (tiles remaining,
   `fair_agent.k_remaining`), `banked_p`, `leaf_p` (champion leaf of record,
   `chain_census.build_leaf`, hash-asserted), `prosp_p = leaf_p − banked_p`,
   and the realized outcome `y_p` (1 win / 0.5 draw / 0 loss).
2. **Stage 2 — outcome models,** fit per phase bucket (`late: k_left ≤ 12`,
   `mid: 13–36`, `early: ≥ 37`; buckets fixed here, before any fit):
   * **M1 (margin-only):** `logit P(win) = α + β·leaf`
   * **M2 (decomposed):** `logit P(win) = α + β₁·banked + β₂·prosp`
   The mechanism statistic is **β₂/β₁** — the win-conversion rate of a
   prospective point relative to a banked point. CIs by game-clustered
   bootstrap (B=500, resample games).
3. **Stage 3 — binding census on the near-tie bank.** For each of the 673
   positions: replay to the root (checksum-verified), compute each arm's
   **chained** afterstate (tile + best meeple by leaf — `chain_values`
   semantics, the bank's own convention) and its `(leaf, banked, prosp)` from
   the mover's POV; score `P(win)` per arm under M2 (root's bucket).
   * **Near-tie pair:** two arms with `|leaf_i − leaf_j| ≤ 0.25` pts
     (primary; 1.0 pts sensitivity).
   * **ΔP of a position:** max pairwise `|P_i − P_j|` over its near-tie pairs.
   * **Binding:** ΔP ≥ 0.02 (primary; 0.05 sensitivity).
   * Honesty row: the same ΔP under M1 (must be ≈0 by construction; shows the
     binding, if any, comes from the decomposition channel, not the map).
4. **Stage 4 — champion posture (mechanism check).** Among binding positions
   where the mover is **trailing at the root** (mover-POV root leaf < 0) and
   the full-champion pick is recorded and is itself margin-near-tied with the
   P(win)-argmax arm: rate at which the champion's arm has
   `P(win) ≤ P_max − 0.02` (i.e. the champion leaves win-probability on the
   table exactly where F6 predicts), plus the mean sacrifice.

### Read-rule — committed now, before any number is read

Primary statistics: `binding_rate` = share of scoreable near-tie positions
(≥1 near-tie pair at ε=0.25) with ΔP ≥ 0.02 under M2; `beta_ratio` = pooled
β₂/β₁ over mid+late buckets (inverse-bootstrap-variance weights) with
game-clustered 95% CI; `champ_lower_rate` (Stage 4) with its n.

* **Branch K (dies free — KILL):** `binding_rate < 5%`. The margin-vs-win
  distinction almost never binds where decisions are actually close ⇒ every
  form of F6 except (c) is bounded tiny; recommendation = kill (a)/(b) without
  a game, leave (c) to E1's own queue slot, add the LEVER_INDEX row as
  MEASURED-AND-KILLED-FREE.
* **Branch F (funded with mechanism):** `binding_rate ≥ 5%` AND the
  `beta_ratio` 95% CI excludes 1 AND (`champ_lower_rate ≥ 0.5` with n ≥ 20).
  Recommendation = build the cheapest online form of (a) as an **offline
  discrimination gate first** (CL-073 discipline: sibling move-ordering against
  the `h6400_v2.9` / solver ruler), NOT a game cell.
* **Branch T (bounded-tiny / parked):** anything else. Recommendation = park
  with numbers; state exactly which sub-statistic failed and what would
  re-open (e.g. binding real but champion already picks the right arm ⇒ no
  exploitable gap; or β-ratio ≈ 1 ⇒ prospective points convert at par and the
  variance channel is empty in this corpus).

Multiple-look note: the ε/ΔP sensitivity cells are reported but the branch is
adjudicated on the primary (ε=0.25, ΔP=0.02) cell alone, fixed here.

### What this pre-gate CANNOT tell you (read before quoting it)
1. **P(win) is "under champion self-play continuation"** — both seats are the
   champion. A human opponent's conversion rates differ; the E4 corpus is the
   place to check that, and this round deliberately does not.
2. **No search in the loop.** Arms are priced by the leaf at chained depth 1;
   the champion's 11008-sim search may already recover part of any binding gap
   (exactly as the tile-tie Stage-A found for margin ties: σ²_arm real, but
   search recovers most of it). A binding rate here is an UPPER BOUND on what
   conditioning the leaf could add over the deployed agent.
3. **The late bucket overlaps the exact-K≤2 latch** where play is
   solver-exact: binding there is evidence about the *solver objective* (form
   (c)/E1), not about the leaf.
4. **M2 is a 2-feature logistic** — it prices the banked/prospective split, not
   full outcome variance. If the variance channel lives in features M2 cannot
   see (e.g. contested-feature structure), the pre-gate under-detects; a null
   here kills the *cheap measurable* forms, not every conceivable one.
5. **No causation, no elo.** 0 games; nothing here prices an online change.

### Cost & integrity
* Whole instrument is local CPU, ~minutes (≈65K leaf evals Stage 1 at W8;
  673 replays + ≤4 chained arms each Stage 3). ETA stated at launch.
* Integrity gates: per-game replayed final scores == recorded (449/449
  required); per-position `checksum` == bank's recorded checksum (673/673
  required); leaf hash == `LEAF_HASH_OF_RECORD` (asserted by
  `chain_census.build_leaf`); any failure aborts loudly.
* Instrument: `scripts/analyzer/f6_winprob_pregate.py` ·
  tests: `tests/test_f6_winprob_pregate.py`.
* Output: `READOUT.md` + `VERDICT.json` + `raw/` in this directory.
