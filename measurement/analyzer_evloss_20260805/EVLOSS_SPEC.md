# F12 slice 2a — offline per-move EV-loss grader: SPEC (pre-registered)

**Status: SPEC, pre-registered 2026-08-05, funded by Joshua ("EV loss grader it is"). Written
BEFORE any grading result exists.** Slice 1 (the descriptive catalog) is
[ANALYZER_REPORT.md](../analyzer_20260802/ANALYZER_REPORT.md); this is its named follow-on and
ORIGINAL_PROMPT Phase-5 task 2. Phase 5 stays downstream of the strength milestones
(2026-05-28 goal change) — **this is analysis tooling, it makes no strength claim and touches
no production config.**

CL-070 named this build as its own natural successor: it measured that the chosen move *changes*
with budget but never whether it *improved*. A grader converts "the move changed" into "the move
cost N points".

## What it does

Replay an archived game; at **every** ply of **both** seats, run the champion's search on that
position and report the loss of the action actually played against the search's best action.

## The four decisions that need pre-registering

### D1. Units — Q is NOT in points, and the old design sketch is wrong

`BACKLOG.md:591` and `ANALYZER_REPORT.md` both assert "Q values are natively in expected-margin
points (virtual-score scale)". **They are not, and that sentence is retracted here.** The leaf
handed to MCTS is `tanh(flat_virtual_score_v2_float(...) / value_norm)` with `value_norm = 15.0`
(`heuristic_prior_mcts.py:283`); MCTS backs up the squashed value, so pooled
`W` is a sum of tanh-squashed values and `Q = W/N ∈ (−1,1)` is **dimensionless**.

Pre-registered choice:

- **Primary statistic is raw `ΔQ = Q(best) − Q(played)`.** It is what the search actually
  optimizes and needs no assumption.
- **A points estimate is emitted alongside, explicitly named as an estimate:**
  `delta_points_tanh_est = 15 · (atanh(clip(Q_best)) − atanh(clip(Q_played)))`, clip at
  |Q| ≤ 0.999. It is a monotone re-scaling for human readability, **not a calibrated EV** —
  the inverse-tanh blows up near |Q|→1 and the leaf's points scale is virtual score, not final
  margin. Never quote it as "you lost N points" without this caveat.
- Both fields ship in every record; the `definitions` block states this verbatim.

### D2. Buckets are measured, not invented

CL-070 gives the self-disagreement floor as a *rate* (30.0% overall, 44.9% narrow-gap at 11008) —
that establishes "not the top move ≠ blunder", but it is not a threshold in ΔQ units. So the
thresholds are derived, not chosen:

- **Calibration pass:** re-grade every ply a second time with a different agent seed. For each
  ply, the two runs' `ΔQ` for the *same* played action is a draw from the instrument's own noise.
  The resulting distribution's quantiles define the buckets:
  `agree` (best action matches) · `within-noise` (ΔQ ≤ p95 of the null) · `inaccuracy`
  (p95 < ΔQ ≤ p99) · `blunder` (ΔQ > p99).
- The null quantiles are written into the artifact and pinned by a test. If the null is
  re-measured on a different corpus, the buckets move with it — bucket labels are never portable
  across calibrations without re-stamping.
- **The champion seat is the built-in control.** Grading both seats on the same board means the
  champion's own mean EV loss is measured in-band; the human's figure is only ever reported
  *paired against it*, never as an absolute.

### D3. The exact tail is a different, better instrument — keep it separate

When `k_remaining ≤ 2` the agent latches to the marginalized solver and the pool is empty
(`last_move()["exact"]`, `pooled == []`). Those plies are graded with
`endgame_solver.solve(...)` → `regret_of(res, action)`, which is a **true EV loss in final-score
points** (`scripts/level2/endgame_solver.py:308`). Emit them in a separate block with their own
counters; **never pool exact-tail points with tanh-scale estimates** in a mean. Forced moves
(one legal action) are excluded from every readout and counted.

### D4. Confounds stated up front, in the artifact

Rendered as a "Read this first" block (the `e4_diff.py` house pattern):

1. **Same-family self-preference.** The grading agent *is* the agent that played the game — same
   leaf, same search family. It structurally prefers its own moves. This is why D2's paired
   champion-seat control is mandatory and the human's absolute number is not reportable alone.
2. **Grading epoch.** The two archived games are pre-2026-08-01 (k4×688, walled grid, random
   start tile). A `fixed_v1` archive (`centered18` + `retail`) must be graded under its own
   rules profile — and `root_replay.replay_actions` has **no rules-profile seam** today
   (it builds a bare walled `Game`); the grader must construct `Game(**profile.game_kwargs())`
   itself. Grading an archive under the wrong profile is a silent wrong answer, so the tool
   fails closed when the archive's `start_rule`/`grid_rule` disagree with the profile in use.
3. **n = 2 human games.** Everything about Joshua's play is a description of two games.
4. **Budget.** Grading budget is stamped per record; grading at a budget the game was not played
   at is legal but must be read as "a stronger reader's opinion", not the opponent's own.

## Build notes (non-negotiable, from the API survey)

- **Env before import.** `env_preamble.PROD_ENV` (curve125 — note `eval_puct_priors._CANON_ENV`
  and the move-agreement probe export *curve100* and inject the leaf via cfg instead; do not copy
  those). `CARCASSONNE_FIX_R9=1` and `OPENBLAS_NUM_THREADS=1` must precede process start /
  `import numpy`; R9 is OnceLock-latched with no per-Game seam.
- **Agent construction** via `champion_factory.make_production_champion("fair", ...)` +
  `mirror_protocol.resolve_execution(...)`; rust backend is the default (`auto` → `rust`).
- **Mirror protocol is mandatory** with the rust agent: `mirror_protocol.reseat(agent,
  deck_seed=..., actions=prefix, move_idx=ply)` is the correct per-ply entry — it seats on the
  deck seed, replays the prefix, and sets `move_idx` so per-determinization seeds match what the
  live game would have drawn. `MirrorDesync` must propagate, never be caught.
- **Pooled stats:** rust `RustFairAgent.last_move()["pooled"]` gives `(action, N_bits, W_bits)`
  as raw IEEE-754 f64 bits — decode with `fair_common.ubits`. **W is a raw float sum; Q = W/N.**
  (The Python agent does not expose `agg_w` at all; `fair_common.PoolSpy` is the only sanctioned
  capture there.)
- **Cost:** ~144 plies/game at rust threads=8 ≈ 0.305 s/move ⇒ **~45 s per archive per pass**,
  ~90 s including the D2 calibration replicate. Trivial; no box booking needed.

## Deliverables

1. `scripts/analyzer/ev_loss.py` — sibling of `corpus_stats.py`/`e4_diff.py`: same CLI style,
   dual JSON+markdown output, `SCHEMA = "carcassonne-analyzer-ev-loss/v1"`, a module-level
   `DEFINITIONS` block copied verbatim into the artifact, an `integrity` block
   (`replay_scores_match`, `n_plies_graded`, `n_latched_exact`, `n_forced_skipped`,
   `mirror_desync_events == 0`, leaf hash `a36d2e15a3b3d71d`, budget stamp), and a `confounds`
   list.
2. Tests in `tests/test_analyzer_evloss.py` following the house pinning style: bucket thresholds
   pinned as constants with boundary behaviour asserted; `Q_played == pooled[a].W/N` for the
   played action; `ΔQ ≥ 0` always; forced and latched plies excluded from the primary readout;
   an end-to-end run over one archived game.
3. Graded artifacts for both E4 archives + the calibration null.
4. A short `EVLOSS_READOUT.md` reporting the paired human-vs-champion EV loss, the bucket
   census, the exact-tail regret block, and the top-3 worst moves per game.

## What would make this wrong

If the champion seat's own mean EV loss is NOT near the calibration null — i.e. the instrument
scores the agent that generated the moves as materially lossy — the grader is mis-wired (wrong
profile, wrong seeding, mirror drift) and no human number from it is reportable. That check is
the acceptance gate, and it runs before any headline.
