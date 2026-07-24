# az_zero — off-distribution value probe (2026-07-24, mid-run)

**Status: RESULT, decisive.** Offline forward-pass probe run mid-loop (after iter 6) to test
Joshua's hypothesis: *"it can copy the moves of the teacher, but there's not enough of a
distribution of different moves to match unseen situations."* Answer: **confirmed, and sharper
than the hypothesis** — the az_zero value head's apparent skill does not survive leaving the
policy generations it trained on. MEASUREMENT ONLY; nothing promoted, both live runs untouched.

## Method
`scripts/distill_flywheel/probe_metrics.py` (the flywheel's fidelity probe), 40-shard subsets
(~5,750 positions each), `--device cuda`, candidate `az_zero/ckpt/iter_06.pt`.
**Control net:** `m2_sighted/warmstart_sighted.pt` — same arch/rep (81ch/42), trained on NONE of
these games, so it measures each probe set's *intrinsic* predictability.
(40-shard cap deliberate: boards load as float32 ≈0.2 MB/row, so a full 300-game dir would be
~9 GB and risk the documented WSL-teardown failure.)

## Result — value↔outcome correlation

| probe set | in iter_06's training window? | **az_zero iter_06** | warmstart (control) |
|---|---|---|---|
| az iter_03 games | YES (deep in window) | **0.906** | 0.646 |
| az iter_06 games | YES (newest in window) | **0.891** | 0.731 |
| az iter_07 games | **NO** — played by iter_06 itself, never trained on | **0.530** | 0.717 |
| distill teacher games (k8×1376 fair PIMC) | **NO** — foreign + strong | **0.437** | 0.620 |

value_mse tells the same story: 0.062 / 0.092 in-window → 0.259 / 0.472 out.

**The control is the point.** warmstart scores ~0.62–0.73 on *all four* sets, so they are not
intrinsically different in difficulty. az_zero swings 0.91 → 0.53 across the same span. The
collapse is about the net's relationship to the data, not the data.

**Consequences:**
1. **The per-iter "value↔outcome corr" printed by `train_iter.py` overstates general skill.** It is
   computed on a game-level-held-out split *of the training window* (`split_files_train_val`), i.e.
   games from the same policy generations. It is NOT leaky in the position sense, but it does not
   measure transfer. The iter-6 headline **0.834 → 0.530** on the very next generation's games.
2. **The "we crossed the heuristic's 0.61!" reading from earlier today is withdrawn.** True
   held-out value correlation (0.530) is *below* the 0.61 reference and *below* the warmstart
   control (0.717) — on az_zero's own distribution.
3. **Policy vs value dissociate.** Policy top-1 agreement stays high out-of-window (0.656 in-window
   → 0.671 on iter_07) because those are literally its own search's moves; only the VALUE head
   collapses. On teacher games policy top-1 is 0.283 — *worse than the warmstart's 0.380*, i.e. the
   zero-start net's move preferences are further from strong play than the old v2.7-distilled net's.

## Mechanism (the precise form of "not enough distribution")
The value head's **effective sample size is the number of GAMES, not positions**: each game
contributes ~144 positions that all share ONE outcome label. Window-4 × 300 games = **~1,200
independent labels** for a 7M-parameter value head — memorizing "which game am I in" is the path of
least resistance, and that is what the numbers show. This is the classic AZ value-overfitting
regime; AGZ escaped it with millions of games, not a better recipe.

This also explains the stalled anchor curve (margin −47 → −33 → −27.5 → −34.6): in the states a
*foreign* opponent steers into, az_zero's leaf value is worse than the warmstart's, so extra
self-play sharpens a policy on top of an evaluator that doesn't transfer.

## What it implies
- **A flatline at iter 11 would be a DATA-STARVATION null, not a recipe null** — exactly the
  PREREG's "compute-bounded, weakly informative" clause, now with a measured mechanism.
- The lever ranking for any scale-up is **games ≫ iterations**: more independent value labels
  (bigger gen/iter), longer τ=1 exploration and/or opponent diversity (past checkpoints) to widen
  the state distribution — not more passes over the same narrow slice.
- **It retroactively defends the heuristic warmstart.** At this compute scale a heuristic-taught
  value head generalizes better (0.717 held-out) than a self-play-learned one (0.530). The "chains"
  are a crutch that works when you cannot afford AGZ's data.

## Reproduce
Probe dirs were 40-shard symlink subsets built in the session scratchpad; rebuild with any 40
`seed_*.npz` from the named dirs and run `probe_metrics.py --ckpt <net> --probe-dir <dir> --out <d>`.
