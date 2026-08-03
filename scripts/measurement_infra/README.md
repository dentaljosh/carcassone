# measurement_infra — reusable measurement infrastructure

**This is MEASUREMENT tooling, NOT a strength lever.** It was promoted from the Post-Search Residual /
Adaptive-Compute pilot (DECISIONS 2026-06-28, **CL-035 / Decision C**), which **CLOSED adaptive compute
as a strength lever** (predictable, but a one-line heuristic captures it and the magnitude is too small
to convert — see [BACKLOG.md](../../BACKLOG.md)). What survived is the *plumbing*: a cheap, exact way to
build and target measurement datasets. Use these primitives to measure; do **not** revive adaptive
compute as a strength play on their basis.

## What's here

| module | what it gives you |
|---|---|
| `root_replay.py` | **Lossless position reconstruction** from `(deck_seed, action_sequence, ply)` — works for ANY policy's games (not just greedy). `RootRef`, `GameRecord`, `replay_actions`, `load_games`. |
| `snapshot.py` | **Multi-depth snapshot search** — ONE `HeuristicMCTS(max_level)` search snapshotted at many sim levels, bit-exact to standalone `h_L`. `snapshot_search`, `best_action_from`, `verify_equivalence`, `frozen_v29_cfg`. |
| `tagging.py` | **h200 top-2 Q-gap** (+ entropy / top-share / n_visited) on every root — the cheap "is this hard for shallow search?" triage signal. `tag_from_snaps`, `tag_root`. |
| `labeling_queue.py` | **Adaptive 4-strata labeling queue** — `ordinary` / `low_top2gap` / `opening_heavy` / `close_score`. `AdaptiveLabelingQueue`. |
| `verify_h12800.py` | certifies snapshot==standalone up to **h12800** on a random sample. |
| `adaptive_k_census.py` | **PIMC world-ensemble census** — replays archived champion games and reports, per decision and by phase, the across-world value spread / per-world pick disagreement / whether worlds 3–4 change the **pooled** pick, plus the exact duplicate-world (and next-N-tile near-duplicate) rate. Built as the adaptive-k pre-gate (verdict: [ADAPTIVE_K_CENSUS_20260728](../../measurement/classical_search/ADAPTIVE_K_CENSUS_20260728.md) — FLAT, lever died free); reusable for any "is the determinization ensemble earning its width **here**?" question. `--noise-control` proves the per-world searches are deterministic (no noise floor to subtract). Tests: `tests/test_adaptive_k_census.py`. |
| `kparallel_latency_bench.py` | **Single-GAME latency bench for the k-parallel split** (G6 stage 1) — mean + p90 s/move for the fair champion, sequential vs `parallel_workers ∈ {2,4,8}`, at k4×688 and the CL-068 k8×1376 shape, over ≥30 replayed REAL mid-game roots (`root_replay`). Writes `manifest.json` + `rows.csv`. Re-verifies on every run that each parallel row chose the SAME action as its sequential sibling (the split is behavior-identical — `tests/test_kparallel.py`), so a latency number can never come from a row that played differently. ⚠️ Run it ALONE: it measures a DRAM-latency-bound workload, so a contended box reports contention, not the lever. `--smoke` is a harness check, not a verdict. |
| `clock_skew_guard.sh` | **Cluster CLOCK-SKEW GUARD for every `--shared-claim` run** (sourced shell lib, roadmap F7c). A box whose clock is fast by more than `--claim-stale-secs` sees every sibling box's **live** claim as stale and steals it — `claim.py:is_stale()` compares the share's **SERVER** mtime to the **CLIENT**'s `time.time()` — so the cluster silently collapses to one box's throughput with no crash and no warning. `carc_clock_skew_guard` / `carc_clock_skew_check` / `carc_clock_skew_seconds`. See [wiring](#wiring-the-clock-skew-guard-into-a-launcher) below. Tests: `tests/test_clock_skew_guard.py`. |
| `demo_labeling_queue.py` | runnable example of the queue. |
| `tests/test_measurement_infra.py` | contracts (A) replay lossless (B) snapshot==standalone (C) tagging (D) frozen cfg. |

## The two load-bearing guarantees

**1. Replay is lossless for any policy.** The engine consumes the global `random` stream in exactly one
place — the deck shuffle in `get_init_board()`. During play it consumes none; MCTS agents use their own
RNG. So `(deck_seed, actions)` fully determines a game, and `replay_actions(seed, actions, ply)`
reconstructs the exact board at any ply. (Supersedes `gen_endgame_positions.replay_to`, which only
replays the deterministic *greedy* line.)

**2. Snapshot == standalone, bit-exact, at every depth.** MCTS is incremental and deterministic given
its seed, so the first `L` sims of an `N`-sim search are identical to a standalone `L`-sim search. One
`HeuristicMCTS(max_level)` run snapshotted at `{200,…,max}` therefore yields every uniform level **and**
the deep reference for ~the cost of the deepest level alone (Kx cheaper than running each separately).
**Verified to h12800: `verify_h12800.py` → 12/12 roots match at {200,1600,6400,12800}** (see
`../../measurement/post_search_residual/h12800_verify.json`). `verify_equivalence()` re-checks on demand.

## Frozen v2.9 leaf (the current production evaluator)

The leaf-path env (`CARCASSONNE_USE_FLAT_LEAF`, …) is read at engine import, so set the block at the very
top of your script **before importing engine/infra modules**, then build the config with the hash guard:

```python
import os
os.environ.update({                      # or copy snapshot.FROZEN_V29_ENV
    "CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0", "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1", "CARCASSONNE_V25_VALUE_BLEND": "0",
})
import sys; sys.path.insert(0, "scripts/measurement_infra")
import snapshot as SNAP
cfg = SNAP.frozen_v29_cfg()               # asserts config_hash == 7fc930b82801cb43
```

## Usage

**Build a snapshot dataset for a set of roots:**
```python
import random
from root_replay import replay_actions
agent = SNAP.make_heuristic_agent(6400, cfg)         # the deepest level you want
for (deck_seed, actions, ply) in roots:
    agent.clear(); agent.rng = random.Random((deck_seed*1_000_003 + ply) & 0x7fffffff)
    _, board = replay_actions(deck_seed, actions, ply)
    snaps, root_player = SNAP.snapshot_search(agent, board, [200,400,800,1600,3200,6400])
    # snaps[L] = {action: (N, Q_rootpov)};  SNAP.best_action_from(snaps[L]) = the move h_L plays
```

**Build an adaptive labeling queue (targets WHERE to spend deep labeling):**
```python
from labeling_queue import AdaptiveLabelingQueue
q = AdaptiveLabelingQueue.from_games("games.jsonl", cfg, sims=200, candidates_per_game=25, workers=16)
strata = {s: q.sample(s, 2000) for s in ("ordinary","low_top2gap","opening_heavy","close_score")}
q.emit("queue.jsonl", strata)            # one row per unique root, with tags + which strata it hit
```

`low_top2gap` selects the roots where `HeuristicMCTS(200)`'s top-2 backed-up Q are nearly tied — the
signal the pilot found best predicts where shallow search is wrong. **It targets MEASUREMENT, not play.**

## Wiring the clock-skew guard into a launcher

Every launcher that passes `--shared-claim` must carry this — enforced by
`tests/test_clock_skew_guard.py::test_every_shared_claim_launcher_carries_the_guard`, which
enumerates the `scripts/**/*.sh` that actually invoke a shared-claim run and fails on any that
doesn't. Paste the stanza near the top (after `set -...`, before any real work):

```bash
# ---- CLOCK-SKEW GUARD (shared) — scripts/measurement_infra/clock_skew_guard.sh ----------
_CSG="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
while [ ! -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] && [ "$_CSG" != / ]; do _CSG=$(dirname "$_CSG"); done
[ -f "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" ] || _CSG="${REPO:-/home/doctor/projects/carcassone}"
. "$_CSG/scripts/measurement_infra/clock_skew_guard.sh" || { echo "FATAL: clock_skew_guard.sh not found from $0"; exit 3; }
carc_clock_skew_guard
# ----------------------------------------------------------------------------------------
```

The upward search resolves the repo root from the script's own location, so it works unchanged
in a `git worktree`; `$REPO` (then the canonical checkout path) is the last-resort fallback for a
script piped in over ssh, where `BASH_SOURCE` is not a path.

- `carc_clock_skew_guard [dir]` — probes `dir`, else `$OUT_ROOT` if the caller already set one,
  else the auto-detected share mount (`/mnt/c/carc-shared` locally, `/mnt/carc-shared` on a remote
  box). It **aborts with `exit 3`** above 60 s of \|skew\| in **either** direction: ahead steals the
  siblings' live claims, behind makes this box's own claims read as instantly stale.
- `carc_clock_skew_check [dir]` — same logic but **returns** 3 instead of exiting, for a caller
  that wants to handle it.
- It **fails open with a loud `WARNING … UNCHECKED`** when the skew can't be measured (local-only
  run, no share mounted) — a run that never touches the share must not be bricked by this.
- `CARC_CLOCK_SKEW_MAX` retunes the threshold; `CARC_CLOCK_SKEW_DISABLE=1` skips it and says so
  loudly (it exists so nobody deletes the guard line instead — don't set it for a multi-box run).

The two launchers that pioneered the guard — `scripts/classical_search/leaf_ablation_launcher.sh`
and `capscurve_resweep_launcher.sh` — deliberately keep their **inline** copies (they were live when
this lib was hoisted); the coverage test accepts those and pins that they still abort.

## Provenance / origin

Logic verified bit-identical to the pilot scripts in `scripts/post_search_residual/` (the origin), which
remain as the historical record. The games/roots/queue `.jsonl` outputs live under
`measurement/*/data/` (gitignored). Net-free, pure CPU.
