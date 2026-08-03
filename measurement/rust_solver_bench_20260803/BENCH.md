# Rust exact-K endgame solver — cost bench (2026-08-03)

**Status: BENCH ONLY.** No production wiring, no `PRODUCTION.yaml` change, no
strength claim. This measures what a solve costs; it says nothing about whether
anything should be deployed at any K.

Subject: `carc_core::endgame` (`rust/carc/carc-core/src/endgame/mod.rs`), the
Rust port of `scripts/level2/endgame_solver.py`, driven through
`carc_rs.MirrorState.solve_endgame`. Correctness is established separately by
the G7 gate (`measurement/rustport_exact_solver/`), not here.

Harness: `scripts/rustport/bench_exact_solver.py`. Raw rows:
`BENCH_rust_cheap.json`, `BENCH_expensive.json`.

## Method

* **One solve per forked child.** Each measurement forks, seats the position,
  solves once, reports through a pipe and exits. The parent never accumulates a
  solved transposition table, so the RSS figure is the solver's own footprint.
* **Peak RSS** is `ru_maxrss` read inside the child after the solve, minus the
  same reading taken immediately before it (`rss_delta_mb`); `rss_peak_mb` is
  the absolute child peak, which includes the ~45 MB Python/engine baseline.
* **Single-threaded per solve.** The solver is serial. `--workers` runs several
  *positions* side by side and was held at or below 3 throughout — a GPU
  training run (G2) owned the box and had to stay undisturbed.
* **The wall cap is enforced by the parent** (`select` with a deadline, then
  `SIGKILL`). An in-child `SIGALRM` cannot stop a Rust solve: it runs under
  `allow_threads` with the GIL dropped, so the Python handler does not fire
  until the call has already returned.
* **Replay is timed separately and excluded.** Seating a greedy-suite position
  replays ~140 plies of `RuleBasedPlayer` (~1.3 s); that is harness cost, not
  solver cost. Action-carrying corpora seat in ~6 ms.
* **`RLIMIT_AS` per child** (6 GB) so an uncapped table fails its own child
  instead of the box. No child hit it.
* **Positions are real corpus endgames**, checksum-verified against the record's
  own `string_representation` before being solved, and cross-checked against the
  Rust mirror. Sources by K:
  * K=3 — `measurement/f3_public_state_oracle/roots_k3_champion.jsonl`
  * K=4, K=5 — `measurement/level2/l23_k4_multisource.jsonl`
  * K=6 — `measurement/level2/l23_positions.jsonl`
* **The Python leg runs the same positions in the same harness**, so the speedup
  is a like-for-like paired ratio, not two benches divided.

`tt_cap = 0` (unlimited) throughout: the freeze-at-cap policy trades memory for
node count, so a capped run would not measure the solver's natural footprint.

## Results

<!--RESULTS-->

## Caveats

* **Per-position variance is large and is the headline risk**, not the median.
  Endgame difficulty at a fixed K spans orders of magnitude (measured during
  calibration: two K=3 positions at 434 and 74 101 nodes). Read p90 and max, not
  the median, when sizing anything.
* **The node counts are the port's, and they are identical to the Python
  oracle's** on every gated position — so a cost quoted here is a cost the
  Python solver would have paid on the same search tree, only slower.
* Marginalized mode has **no alpha-beta** (chance nodes have no minimax cutoff),
  which is why its cost curve is so much steeper than the clairvoyant one.
