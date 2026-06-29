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

## Provenance / origin

Logic verified bit-identical to the pilot scripts in `scripts/post_search_residual/` (the origin), which
remain as the historical record. The games/roots/queue `.jsonl` outputs live under
`measurement/*/data/` (gitignored). Net-free, pure CPU.
