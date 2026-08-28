# PREREG — C1 MICRO-GATES (zero games, banked data only)

> **Status: PRE-OUTCOME.** This file is written and committed BEFORE any gate
> statistic exists. The runner (`microgates.py`) is committed in the same
> commit. Deviations after this commit go in `DEVIATIONS.md`, never here.
>
> Owner-funded, advisor-flagged. Zero new games, zero band, **no
> `experiments/results.csv` row** (house precedent for a 0-game oracle-class
> instrument); a DECISIONS.md index line and a `docs/LEVER_INDEX.md` row are
> owed at close.

## 0. Why this instrument exists

The program has concluded that the owner's ~10–20 pt/game edge over the
production champion is **position-steering** (multi-ply construction), not a
per-move residual: `measurement/e4_ply_pricing_20260827/` found the champion
would have played the owner's own move at 74.1 % of `invasion` plies, and
`measurement/e4_continuation_20260828/` priced the divergent residual at a
PRIMARY NULL (invasion − control = −1.87 ± 1.88, z −0.99).

**C1** is a candidate mechanism for closing the steering hole: price
contested-claim plies by terminal **tier1-greedy** rollouts — the tie-arbiter's
own cost core (`carc_core::tier1`, python twin
`scripts/measurement_infra/oracle_score_pilot.py::_GreedyContinuation` =
`RuleBasedPlayer`) — on the theory that a terminal-grounded rollout *sees*
post-claim invalidation (an invasion that arrives later and zeroes a claim)
where a 1-ply leaf cannot.

An independent advisor flagged the **premise** as untested:

> the tier1-greedy rollout policy may itself never contest — never invade via
> merge, never zero an opponent farm — in which case rollouts cannot see
> post-claim invalidation and C1 dies for free.

That is a property of a POLICY, measurable on banked positions with zero new
games. This instrument measures it.

### 0.1 ⚠️ Disclosure — what was seen before this freeze

Blind means blind. Before this file was committed, three **cost/​base-rate
probes** were run (all read-only, none touching a gate statistic):

1. a single tier1-greedy playout from one banked crux ply, to size the cost
   (1.51 s, 73 plies) — a WALL-CLOCK number, not a detector output;
2. a six-point cost-vs-`ply_frac` sweep on `fixed_v1` rows (0.0124 →
   0.0290 s/ply, aggregate **0.0176 s/ply**) — again wall-clock only;
3. the **banked Stage-A base rates** in §3.1 below, computed from
   `measurement/e4_exploit_grading_20260825/rows.jsonl`. These are an input to
   the FLOORS and therefore had to be computed before the floors could be
   justified. They describe the OWNER-vs-CHAMPION archives, not the rollout
   policy, so they cannot leak a gate outcome.

4. a **5-position end-to-end smoke** (mandated by the task brief: "smoke 5
   positions end-to-end first and sanity-check the detector fires on a KNOWN
   owner-invasion ply"). This one DID produce detector output, on the first five
   `fixed_v1` `invasion` plies at world 0, and it is disclosed rather than
   discovered: those five playouts showed rollout-bucket onset counts of
   **1, 2, 3, 3, 4** and farm-control changes of 2, 2, 3, 1, 5. It also exposed
   the `C`/`R`/`F` vs `city`/`road`/`farm` spelling mismatch that G-DETECT now
   maps (§4), and it is what motivated adding **G-REPLAY** — all five archive
   replays reproduced the archive's recorded final score exactly, so that check
   was promoted from an observation to a gate.

   Those five plies are 5 of 277 in the primary pool and 5 of 4,432 playouts.
   They stay in the run (the instrument is deterministic, so they recompute
   bit-identically — the cross-stage check in §4 uses that); excluding them
   would be a post-hoc filter on a seen outcome, which is worse than declaring
   it. **The floors in §3.2 were written and committed to disk before this smoke
   ran**, and they are not moved by it.

No other detector output exists at freeze time.

## 1. What is frozen here

### 1.1 The crux ply set

The full **290 banked plies** of `measurement/e4_ply_pricing_20260827/`, read
from the share rows (`/mnt/c/carc-shared/e4_ply_pricing_20260827/rows_*.jsonl`),
which carry both the owner's `played_action` and the production champion's
banked `counterfactual_action` at every ply. No new selection is made and no
ply is dropped.

| stratum | n | | profile | n |
|---|---:|---|---|---:|
| `control` | 91 | | `fixed_v1` | 277 |
| `defense` | 86 | | `walled` | 10 |
| `invasion` | 86 | | `app_aug2` | 3 |
| `farm_capture` | 27 | | | |

263 are `tiles`-phase plies, 27 `meeples`-phase. Σ remaining plies = **20,820**
(mean 71.8). 120 / 290 are champion-divergent.

**Rules-epoch discipline (binding, inherited unchanged).** The profile is
resolved FROM EACH ARCHIVE by `analyzer.ev_loss.resolve_profile_name`; the
runner re-resolves and hard-fails on drift from the banked row's stamp. R9 is
import-latched, so one process per profile group and `prepare_env` before any
`carcassonne_ai` import; `r9_env` is stamped on every unit row. **Never
identify a build from `(start_rule, grid_rule)`.** All readouts are reported
conditioned on profile; `walled` + `app_aug2` (13 plies) are reported
separately and are never pooled into a gate statistic.

### 1.2 Pre-registered constants

```
WORLD_SEED      = 20260828     # IDENTICAL to e4_continuation_20260828 (worlds are comparable)
PLAYOUT_SALT    = 20260829
M_WORLDS        = 16           # stage 1 / stage 2
M_WORLDS_EXT    = 64           # stage 1b extension (worlds 16..63)
K_MAX           = 8            # stage 2 arms per ply
MAX_PLIES       = 400
LEGAL_MASK_CACHE = False       # the HONEST mask, see §2.4
```

### 1.3 The CRN world, reused verbatim

`world_rng(deck_seed, ply, world) = random.Random(WORLD_SEED ^ (deck_seed*1000003)
^ (ply*7919) ^ (world*104729))` — **the `e4_continuation_20260828` convention,
character for character, including its constant**, so world `j` at
`(deck_seed, ply)` is the SAME world in both instruments. There is **no arm
term**: that absence is the CRN guarantee.

The world is installed exactly as `continue_plies._run_arm` installs it (pass 1
computes the TRUE draw order and the unseen tail at the target ply; the tail is
permuted; pass 2 rebuilds from ply 0 with the permuted tail installed on the
INITIAL board and replays the archive prefix on top), with all three of its
guards kept: `deck_tail_mismatch`, `world_prefix_mutated` /
`world_not_a_permutation`, and `root_state_diverged` (the reconstructed root's
`string_representation` must equal the TRUE root's — permuting the UNSEEN tail
must not move the position). A guard trip **voids the unit** and, if it recurs
above the §5 rate, voids the instrument.

The playout policy's RNG is `RuleBasedPlayer(seed = playout_seed(deck_seed,
ply, world))`, `playout_seed = (PLAYOUT_SALT ^ (deck_seed*1000003) ^
(ply*7919) ^ (world*104729)) & 0x7FFFFFFF` — **also arm-independent**, matching
`tier1_leg`'s "a FRESH `RuleBasedPlayer(playout_seeds[j])` per pick, same seed,
stream restarted".

## 2. The measurement

### 2.1 Unit of work

One unit = one `(game, ply, world, arm)`. The arm's action is applied to the
world root; **both seats** then play to terminal under tier1-greedy
(`RuleBasedPlayer`), which is the python twin of `carc_core::tier1`'s policy.
Only the arm's action is forced; everything after it, including the meeple
follow-up belonging to the same tile, is the rollout policy's own choice.

Rust `carc_rs.tier1_leg` is **NOT** used, and the reason is recorded here
rather than discovered later: `carc_core::tier1::tier1_root` calls
`Game::from_deck` with the DEFAULT `GameConfig` (documented in its own docstring
as "the walled rules profile, whose `game_kwargs()` is `{}` by construction"),
so it cannot replay a `fixed_v1` archive — 277 of the 290 plies. Extending the
binding + rebuilding the wheel would mutate the shared venv the main tree is
editable-installed against. The python twin is used instead, at measured
0.0176 s/ply (§5). This is a stated deviation from the task brief's "use the
rust wheel", and it is the conservative direction: the python twin is the
*definition* the rust port is graded against (`G-BITEXACT`, 15,360 playouts).

### 2.2 The detectors — the Stage-A definitions, and the exact adaptation

Definitions are taken from
`measurement/e4_exploit_grading_20260825/stage_a_census.py` and are NOT
reinvented. Ported verbatim:

* `snapshot`'s positional component keys — `("C"|"R"|"F", row, col, side_name)`
  — grouped by `Decomp.city_side_root` / `road_side_root` / `farm_anypos_root`;
* the cross-ply **global union-find** over those keys, so a component keeps its
  identity `fid` through merges;
* `meeple_component_key` for mapping a placed meeple to a component;
* `flat_leaf._meeple_weight` for meeple weight;
* the **contest predicate**: a component whose meeple counts satisfy
  `counts[0] > 0 and counts[1] > 0` — first ply at which it holds is the
  **contest onset**, recorded once per `fid` (`contested_seen`);
* the **mechanism** classification at onset: `merge` (≥2 pre-ply occupied
  parts of the same `fid`, invader = the seat with FEWER tiles, `merge_equal`
  on a tie), `placement` (one occupied pre-part, meeples phase, a meeple placed
  this ply), `born_contested` (no pre-parts).

**The two adaptations, stated exactly:**

* **A1 — the census window.** Stage A censuses a whole archived game from ply 0.
  Here the census runs over ONE ROLLOUT: the state at the crux root is the
  ply-0 equivalent, its components seed the union-find and every component
  already contested there is pre-loaded into `contested_seen`, so only NEW
  onsets count. Onsets are then bucketed by position: `arm_ply` (the onset
  caused by the forced arm action itself) vs **`rollout` (ply > root ply)** —
  and **only the `rollout` bucket is a gate statistic**, because the gate is
  about what the ROLLOUT POLICY does, not about the move it was handed.
* **A2 — `n_tiles`.** Stage A reads `Decomp.city_root_coords` /
  `road_root_coords` / a farm coord set. Here `n_tiles` of a component is the
  number of distinct `(row, col)` among its positional keys, which is
  identically that set, and is what the invader/incumbent split uses.

Nothing else is adapted. The two-pass structure of Stage A (replay, then
`extract_events`) is collapsed into a single streaming pass because a rollout
is censused as it is played; the predicate and the ordering are unchanged.

**Farm-specific readouts** (root-vs-terminal, on top of the streaming census):

* **farm control** of a component = the seat with strictly greater summed
  farmer weight (`shared` if equal and > 0, `none` if no farmers), matching
  `flat_leaf._winners`. Farm meeples are mapped by `Decomp.farm_pos0_root`,
  the key the SCORING path (`_final_scores`) uses.
* **`farm_control_changed`** — a farm component that at the root had control
  ∈ {0, 1}, whose terminal control differs. Farm regions only ever merge, so
  each root component maps to exactly one terminal component via any of its
  keys; that mapping is asserted, not assumed.
* **`root_farmer_zeroed`** — a farmer meeple present at the ROOT that receives
  0 points at terminal, where the terminal farm award is
  `3 × Decomp.farm_root_finished_cities[root]` to `_winners`, i.e.
  `_final_scores`'s own arithmetic. Split into `zeroed_no_finished_cities`
  (a dead field — not an invalidation) and **`zeroed_lost_majority`** (≥ 1
  finished city AND the farmer's seat is not in the winner set) — the latter is
  the post-claim-invalidation signal C1 needs.

### 2.3 G1 — CONTEST REALIZATION (the primary gate)

For each `(game, ply)`, on the **played-action arm**, over `M_WORLDS = 16` CRN
worlds:

* **`R_contest`** (PRIMARY) = fraction of playouts with ≥ 1 contest onset at
  ply > root, ANY class, pooled over all `fixed_v1` plies;
* `R_farm`, `R_city`, `R_road` — the same, per class;
* `R_farm_control` = fraction of playouts with ≥ 1 `farm_control_changed`;
* `R_farmer_zeroed_lost_majority`;
* all of the above **split by which seat benefits** (invader seat 0 vs seat 1),
  from the onset's own `invader` field;
* per-position rates (16 worlds each) so a "some positions, never others"
  shape is visible rather than hidden in the pool.

### 2.4 G2 — DISAGREEMENT RATE (secondary)

At each crux ply, the candidate set is

```
C = {played_action, counterfactual_action}                       (forced in)
    ∪ top-(K_MAX − |C|) legal actions by the CHAMPION LEAF
```

where the champion leaf is `flat_leaf.flat_virtual_score_v2_float(state, mover,
champion_factory.production_leaf_cfg())` on the afterstate — the frozen curve125
leaf `a36d2e15a3b3d71d` of `governance/PRODUCTION.yaml`, i.e. the move ordering
C1 would actually be re-ranking. `|C| = min(K_MAX, n_legal)`.

Every arm runs the SAME 16 CRN worlds. **`rollout_argmax`** = the arm with the
greatest mean terminal `delta_pts_mover` (sign convention below), ties broken by
lowest action index (deterministic, stated in advance).

* **`D_champ`** (the G2 statistic) = fraction of plies where
  `rollout_argmax != counterfactual_action`;
* `D_owner` = fraction where `rollout_argmax != played_action` (descriptive);
* both reported pooled and per stratum, and separately on the **contested
  plies** = `invasion ∪ farm_capture`, which is the gate's cut.

**The reference is the BANKED champion search**, not a leaf-greedy stand-in:
`counterfactual_action` was produced by the full production champion
(`k_dets = 8 × sims_per_det = 1376`, fair PIMC, exact-K ≤ 2, rust) at every one
of these 290 plies by the 2026-08-27 run, and is read off disk. No champion
search is re-run here.

**Sign convention.** `margin_p0_minus_p1` is the terminal `P0 − P1`;
`delta_pts_mover` = that value for a seat-0 mover and its negation for a seat-1
mover, so higher is better FOR THE MOVER at either seat. Pinned by a hand
fixture in `test_microgates.py`.

**The legal mask.** `Game(enable_legal_moves_cache=False)`. The memo
`game_wrapper.Game._legal_cache` is keyed non-injectively and is documented in
`carc_core::tier1`'s module docs as returning a WRONG farmer-corner mask on
rotationally-symmetric tiles (it moved 57 / 15,360 banked playout values). The
banked tiearb corpus had to reproduce that bug to stay bit-exact with itself;
**this instrument is new and takes the honest mask.**

## 3. Pre-registered branches — the floors, and where they come from

### 3.1 The reference base rate (banked, computed pre-freeze — §0.1)

From `measurement/e4_exploit_grading_20260825/rows.jsonl`, the Stage-A census of
the **50 banked E4 games** (owner vs the on-device champion), 7,100 plies:

```
contest onsets            133      lambda = 0.01873 / ply     2.66 per game
  by class    farm 62 / city 48 / road 23
  by mech     merge 121 / merge_equal 12       (placement 0, born_contested 0)
  invader     seat 0 (owner) 100 / seat 1 (champion) 21 / ambiguous 12
  outcome     shared_tie 73 / invader_took_all 30 / incumbent_held 18 / ambiguous 12
```

Every contest in the banked archives is a **merge**. Over a continuation of the
target set's mean length `L = 71.8` plies, a policy pair contesting at the
banked rate realizes ≥ 1 onset with probability

```
p_ref      = 1 − exp(−0.01873 × 71.8) = 0.739      (any class)
p_ref_farm = 1 − exp(−0.00873 × 71.8) = 0.466      (farm only)
```

`p_ref` is the rate of a strong human plus a production champion, both of which
contest deliberately. It is the ceiling this gate measures against, not a null.

### 3.2 The branches

Let `R = R_contest` (§2.3, `fixed_v1` pool, rollout bucket only) and
`D = D_champ` on contested plies (`invasion ∪ farm_capture`, §2.4).

* **GATE-DEAD — C1's premise is REFUTED.**
  `R < 0.10`.
  Justification, two ways, both must be true at that number and are:
  (a) 0.10 is **< 1/7 of `p_ref` = 0.739** — a policy that contests at under a
  seventh of the rate the two real players do is contest-blind in the sense the
  advisor meant; (b) at `R < 0.10` a `B = 16` world set yields **fewer than 1.6
  contested worlds per ply**, so a contest-conditional value difference is below
  the CRN noise of the very estimator C1 would use — C1 cannot price what its
  own rollouts almost never produce. **If GATE-DEAD fires at stage 1, stage 2
  (G2) is NOT RUN** and the run closes; a re-ranker built on contest-blind
  rollouts is moot regardless of how often it disagrees.
* **GATE-LIVE — the premise holds AND there is re-ranking leverage.**
  `R ≥ 0.35` **AND** `D ≥ 0.15`.
  `0.35` is ≈ half of `p_ref`: the rollout policy contests within a factor of
  two of the real players. `0.15` is ≈ 60 % of the banked **champion-vs-owner
  divergence rate at invasion plies (25.9 %,** the 2026-08-27 run's own
  headline complement of 74.1 % agreement**)** — the two policies whose
  10–20 pt/game gap C1 exists to explain differ at 25.9 % of these plies, so a
  candidate re-ranker that differs from the champion at less than ~60 % of that
  rate cannot supply the disagreement budget the gap requires.
* **GATE-MIXED — everything else**, i.e. `0.10 ≤ R < 0.35` (the policy contests,
  but well below the human/champion rate), or `R ≥ 0.35` with `D < 0.15` (the
  premise survives but the terminal-grounded pick almost never differs from the
  champion's, so C1 buys nothing). MIXED is reported with which half failed, and
  is **not** an authorization to fund C1.
* **VOID — instrument failure.** Any of: > 5 % of units ending `ERROR` /
  `TIME_SKIPPED` / `OOM_SKIPPED`; any `root_state_diverged`,
  `world_not_a_permutation`, `deck_tail_mismatch` or `world_prefix_mutated`
  recurring on > 1 % of units; the determinism gate (§4 G-REPEAT) failing; the
  detector gate (§4 G-DETECT) failing; or the replay gate (§4 G-REPLAY) failing.
  A VOID reports no gate branch.

Farm-specific sub-readouts (`R_farm` vs `p_ref_farm = 0.466`,
`R_farm_control`, `R_farmer_zeroed_lost_majority`) are reported against their
own reference and **inform the written implication, but do not move the
branch** — the branch is decided by `R_contest` and `D_champ` alone, fixed here
so the reading cannot be shopped across sub-statistics after the fact.

### 3.3 Power, stated before the outcome

`R` is a pooled Bernoulli over 277 `fixed_v1` plies × 16 worlds = 4,432
playouts, but the worlds within a ply are NOT independent (they share a root).
The SE quoted is therefore **clustered on GAME** (the 290 plies live in ~50
archives), computed from per-game influence contributions. At 50 clusters and
`R` near the 0.10 floor, the cluster-robust SE is ≈ 0.03–0.05, so the DEAD
branch is decided by a wide margin or not at all. `D_champ` on ~113 contested
plies has a binomial SE ≈ 0.035 at `D = 0.15`. **This instrument is powered to
separate "essentially never" from "at the human rate", not to resolve 5-point
differences.** A near-floor reading is reported as near-floor.

## 4. Instrument gates (run BEFORE the pass; a failure blocks the pass)

* **G-DETECT — the detector must reproduce a KNOWN invasion.** For every
  `invasion` ply, replay the ARCHIVE's own continuation from the crux root
  (world = −1, the TRUE deck, the archive's own actions) and require the
  streaming census to fire a contest onset at the arm ply whose `cls` equals
  the banked row's `notes.cls`. **Required pass rate: ≥ 95 % of the 86 invasion
  plies** (the residual allows for the handful of banked rows whose tagged event
  is a multi-event ply — `notes.n_events > 1` — where the FIRST onset need not
  be the tagged class; those are listed by name in the readout). Anything below
  that is a detector bug and the pass does not launch.
  This census keys components `("C"|"R"|"F", …)` and the banked rows spell the
  same classes `city`/`road`/`farm`; `CLS_LONG` is the one-line map between the
  two spellings, and it is a spelling map, not a definition.
* **G-REPLAY — the replay must reproduce the archive.** The same archive-continuation
  replays that feed G-DETECT also produce a FINAL SCORE. It must equal the
  archive's own `recorded_scores`, on **100 %** of the invasion plies that carry
  one. This is the end-to-end check on the whole chain — profile resolution, R9
  latch, world installation, prefix replay, terminal scoring — and it is free
  (the same replays). Any mismatch VOIDs before a gate statistic is read.
* **G-REPEAT — determinism.** 5 pre-named units (first unit of the first 5
  `fixed_v1` plies in target order) are run twice in separate processes; the
  full row must be identical. Any difference VOIDs.
* **G-PROFILE — rules epoch.** Every unit re-resolves its profile from the
  archive and stamps `r9_env` expected-vs-observed; a mismatch hard-fails that
  process.

## 5. Compute — the arithmetic, before the launch

Measured (§0.1 probe 2): **0.0176 s per continuation ply**, aggregate over 420
plies spanning `ply_frac` 0.08 → 0.94, plus ~2.5 % census overhead.

```
Sigma remaining plies over the 290 crux plies              20,820
STAGE 1  (G1): 1 arm  x 16 worlds  -> 333k plies    ->  ~5,900 s core  ->  ~13 min @ W8
STAGE 1b (ext): 1 arm x 48 worlds  -> 999k plies    -> ~17,600 s core  ->  ~37 min @ W8
STAGE 2  (G2): <=8 arms x 16 worlds -> 2.66M plies  -> ~47,000 s core  ->  ~1.7 h  @ W8
```

Run on the local box only, `nice -n 19`, **W = 8** (agent cap; the box is
otherwise idle — census taken, load 0.46). Units are written one JSON file each,
atomically (`.tmp` + rename), so the pass is resumable and no wall-clock chunk
boundary can lose more than one unit.

**Sequencing, pre-registered:** stage 1 → evaluate the DEAD branch → stage 1b
runs **iff** `0.005 ≤ R < 0.20` (the zone where 16 worlds resolve `R` poorly)
→ stage 2 runs **iff** GATE-DEAD did not fire. This ordering is cost discipline,
not outcome shopping: the branch thresholds are fixed above and stage 2 can only
move a reading from LIVE to MIXED, never from DEAD to LIVE.

## 6. Reproduce

```bash
WT=/home/doctor/projects/carcassone/.claude/worktrees/agent-a7e4274d1451a32d9
export PYTHONPATH=$WT/src:$WT/engine:$WT/scripts
D=$WT/measurement/microgates_20260828

python3 $D/microgates.py --stage gates   --out $D/out        # G-DETECT + G-REPEAT
python3 $D/microgates.py --stage g1      --out $D/out --workers 8 --budget-s 420
python3 $D/microgates.py --stage g2      --out $D/out --workers 8 --budget-s 420
python3 $D/microgates.py --stage aggregate --out $D/out --json $D/MICROGATES.json
```

Every stage is resumable: re-running skips units whose output file exists.
`--budget-s` stops launching new units after that many seconds so a run fits an
interactive call; it changes nothing about the result (units are deterministic
given `(deck_seed, ply, world, arm)`).
