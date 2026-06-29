"""Multi-depth snapshot search — MEASUREMENT INFRASTRUCTURE (not a strength lever).

Promoted from the post-search-residual pilot (CL-035). The key efficiency win: because MCTS is
*incremental* and deterministic given its seed, the first L simulations of an N-sim search are
bit-identical to a standalone L-sim search. So ONE HeuristicMCTS(max_level) search, snapshotted at
cumulative sim counts, yields every uniform compute level AND the deep reference — ~Kx cheaper than
running each level separately (K = number of levels). Verified bit-exact (`verify_equivalence`,
`tests/test_measurement_infra.py`).

Snapshots store, per level, the root's deduped visited children: {action -> (N, Q_rootpov)} where
Q is in the root's point-of-view (mcts.py best_action sign). `best_action_from` mirrors the agent's
actual move choice (argmax (Q, N), ties -> lowest action id).

## Frozen v2.9 leaf (the current production evaluator)

The leaf *path* env (`CARCASSONNE_USE_FLAT_LEAF` etc.) is read at engine import time, so callers that
want the frozen v2.9 leaf must set the env block BEFORE importing engine modules. Use the literal
block from `FROZEN_V29_ENV` (see README) or call `set_frozen_v29_env()` as the very first thing in
the program. `frozen_v29_cfg()` then builds the LeafConfig and asserts its config_hash.
"""
from __future__ import annotations
import os

DEFAULT_LEVELS = (200, 400, 800, 1600, 3200, 6400)
FROZEN_V29_HASH = "7fc930b82801cb43"
FROZEN_V29_ENV = {
    "CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0", "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1", "CARCASSONNE_V25_VALUE_BLEND": "0",
}


def set_frozen_v29_env() -> None:
    """Set the frozen v2.9 leaf env block. MUST run before importing engine modules to pin the
    flat-leaf path. (Idempotent; does not override an already-set value except the leaf knobs.)"""
    for k, v in FROZEN_V29_ENV.items():
        os.environ[k] = v
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")


def frozen_v29_cfg(value_norm: float = 2.0):
    """Build the frozen v2.9 LeafConfig and assert its config_hash == FROZEN_V29_HASH. Loud on drift."""
    import dataclasses as dc, hashlib, json, sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "level2"))
    import eval_hybrid_handoff as EH
    cfg = EH._heur_leaf_cfg(value_norm)
    d = {k: (list(v) if isinstance(v, tuple) else v) for k, v in dc.asdict(cfg).items()}
    h = hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    assert h == FROZEN_V29_HASH, f"leaf is not frozen v2.9 (config_hash {h} != {FROZEN_V29_HASH})"
    return cfg


def make_heuristic_agent(sims, leaf_cfg, heur_leaf: str = "v2_7", seed: int = 0):
    """A HeuristicMCTS configured for snapshotting. `leaf_cfg` from `frozen_v29_cfg()` (or any cfg)."""
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.mcts import HeuristicMCTS
    return HeuristicMCTS(
        game=Game(enable_legal_moves_cache=True, include_farm_scalars=True),
        simulations=sims, heur_leaf=heur_leaf, leaf_cfg=leaf_cfg, seed=seed,
    )


def read_children(root, root_player) -> dict:
    """Deduped visited children -> {action: (N, Q_rootpov)}. Mirrors mcts.py best_action's
    transposition dedup (lowest action id per unique Node) and root-POV Q sign."""
    seen = set()
    out = {}
    for a in sorted(root.children):
        ch = root.children[a]
        if ch.N <= 0 or id(ch) in seen:
            continue
        seen.add(id(ch))
        q = ch.Q if ch.player_to_move == root_player else -ch.Q
        out[int(a)] = (int(ch.N), float(q))
    return out


def snapshot_search(agent, board, levels=DEFAULT_LEVELS):
    """Drive `max(levels)` simulations on `agent`, snapshotting deduped child stats at each level.
    Returns (snaps, root_player) where snaps = {level: {action: (N, Q_rootpov)}}.

    The agent's tree/caches should be fresh (call agent.clear()) and its rng seeded by the caller
    for reproducibility (e.g. agent.rng = random.Random(per_root_seed)) BEFORE this call."""
    levels = sorted(int(l) for l in levels)
    root = agent._get_or_create_node(board)
    root_player = root.player_to_move
    snaps = {}
    idx = 0
    for i in range(1, levels[-1] + 1):
        agent._simulate(board, root)
        if idx < len(levels) and i == levels[idx]:
            snaps[levels[idx]] = read_children(root, root_player)
            idx += 1
    return snaps, root_player


def best_action_from(levelmap):
    """The move the agent would PLAY from a level's child stats: argmax (Q_rootpov, N) over visited
    children, ties -> lowest action id (mcts.py best_action rule). Returns (action, Q, N) or None."""
    items = [(int(a), n, q) for a, (n, q) in levelmap.items() if n > 0]
    if not items:
        return None
    items.sort(key=lambda t: t[0])                 # so max() ties resolve to lowest action id
    a = max(items, key=lambda t: (t[2], t[1]))[0]
    for aa, n, q in items:
        if aa == a:
            return a, q, n


def verify_equivalence(make_agent, board, levels, mcts_seed: int) -> dict:
    """Assert snapshot-at-L == a standalone L-sim search, at EVERY level. `make_agent(sims, seed)`
    returns a fresh agent. Returns {L: {"match": bool, "sum_n_snap": int, "sum_n_ref": int,
    "n_children_snap": int, "n_children_ref": int}}. The reconstruction of `board` must be identical
    for both runs (pass the SAME board, or rebuild it identically)."""
    import random as _random
    levels = sorted(int(l) for l in levels)
    snap_agent = make_agent(levels[-1], mcts_seed)
    snap_agent.clear(); snap_agent.rng = _random.Random(mcts_seed)
    snaps, _ = snapshot_search(snap_agent, board, levels)
    out = {}
    for L in levels:
        ref = make_agent(L, mcts_seed)
        ref.clear(); ref.rng = _random.Random(mcts_seed)
        ref.search(board)
        rroot = ref._nodes[ref.game.string_representation(board)]
        ref_children = read_children(rroot, rroot.player_to_move)
        a_snap = {a: nq[0] for a, nq in snaps[L].items()}
        a_ref = {a: nq[0] for a, nq in ref_children.items()}
        out[L] = {"match": a_snap == a_ref,
                  "sum_n_snap": sum(a_snap.values()), "sum_n_ref": sum(a_ref.values()),
                  "n_children_snap": len(a_snap), "n_children_ref": len(a_ref)}
    return out
