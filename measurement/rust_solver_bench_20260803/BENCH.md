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

Host `Doctor`, `carc_rs` 0.1.0. Artifacts: `BENCH_pyx4.json`, `BENCH_pyx4_rows.jsonl`, `BENCH_rest.json`, `BENCH_rest_rows.jsonl`, `BENCH_rust_rows.jsonl`.

| cell | n ok / n | wall median | wall p90 | wall max | nodes median | nodes max | TT entries max | peak RSS max | timeouts |
|---|---|---|---|---|---|---|---|---|---|
| `rust_clairvoyant_ab_k4` | 20/20 | 14.48 s | 52.87 s | 179.73 s | 84,589 | 506,304 | 506,122 | 87.7 MB | 0 |
| `rust_clairvoyant_ab_k5` | 2/4 | 13.71 s | 16.52 s | 16.52 s | 193,999 | 259,668 | 259,668 | 62.9 MB | 2 |
| `rust_clairvoyant_ab_k6` | 2/6 | 129.64 s | 193.79 s | 193.79 s | 1,293,756 | 2,228,339 | 2,228,339 | 239.2 MB | 4 |
| `rust_marginalized_k3` | 6/6 | 94.36 s | 205.92 s | 288.90 s | 307,986 | 1,005,104 | 1,005,104 | 115.1 MB | 0 |
| `rust_marginalized_k4` | 1/6 | 102.31 s | 102.31 s | 102.31 s | 496,046 | 496,046 | 496,046 | 77.6 MB | 5 |
| `rust_marginalized_k5_probe` | 0/1 | — | — | — | — | — | — | — MB | 1 |
| `py_clairvoyant_ab_k4` | 5/6 | 254.54 s | 337.41 s | 337.41 s | 60,560 | 137,574 | — | 1669.7 MB | 1 |

### Rust vs Python, position-paired

| K | paired n | median × | min × | max × | aggregate × | node-count agreement | value agreement |
|---|---|---|---|---|---|---|---|
| k4 | 5 | 20.77× | 19.63× | 28.71× | 22.11× | 5/5 | 5/5 |

### What the numbers say

* **K=4 clairvoyant is comfortably tractable in Rust** — 20/20 complete, median
  14.5 s, and the whole cell cost about as much wall clock as *five* Python
  solves of the same kind.
* **The cost wall is the mode, not the depth.** Clairvoyant has alpha-beta;
  marginalized cannot (chance nodes have no minimax cutoff). So marginalized
  K=4 finishes 1/6 under a 300 s cap while clairvoyant K=6 — two tiles deeper —
  finishes 2/6. Marginalized K=5 does not finish at all: the probe was killed at
  the cap, so the honest statement is **> 300 s**, not a measured time.
* **A 300 s cap is the wrong budget for K=5/K=6 clairvoyant**, and the timeout
  counts say so: 2/4 and 4/6 respectively exceeded it. The completed solves
  bound the *easy* tail only, so read those rows as "at least this fast on the
  easier positions", never as a cell median.
* **Memory is a Rust win as large as the speed one.** At K=4 the peak child RSS
  is 88 MB against the Python oracle's 1 670 MB on the same positions — ~19×,
  from the 16-byte digest key and the absence of a per-node `deepcopy`. The
  Python solver's ~1–2 GB/worker (which is what forces `CARCASSONNE_TT_CAP`
  and low W) is not a property of the search; it is a property of the
  implementation.
* **Peak table size** on completed solves: 506 K entries at K=4, 260 K at K=5,
  **2.23 M entries / 239 MB at K=6**. Extrapolating the RSS is safe here in a
  way the wall clock is not — the table grows with distinct positions, and the
  ~107 B/entry constant held across every cell measured.

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
