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

## ⚠️ NO RUST BACKEND — this primitive stays Python (rustport P6 Class-B, 2026-08-02)

The Class-B wiring pass converted the per-world probes (`kwidth_agreement_probe`,
`adaptive_k_census`) onto `carc_rs` via `rust_world_search.RustWorldSearcher`, and converted
`gate_b_depth_transfer`. **This module was NOT converted, and the reason is structural rather
than a matter of effort** — see `RUST_BACKEND_GAP` / `rust_backend()` below. Two independent
blockers, either one sufficient:

  1. **No Rust agent to call.** `make_heuristic_agent` builds `HeuristicMCTS` — vanilla UCT with a
     `virtual_score` leaf replacing the rollout. `carc_core::search` implements the
     PUCT-with-heuristic-priors search *only*; `MirrorState.search_single`'s own contract is
     "equivalent to `HeuristicPriorAgent(...).move(board)`". There is no Rust UCT at all.
  2. **No mid-search surface.** `snapshot_search` steps `_simulate` one simulation at a time and
     reads the root *between* sims. `search_single` is a whole search in one FFI call; there is no
     per-sim hook, no snapshot callback, and no way to resume a finished search.

⚠️ **AND THE ONLY FAITHFUL WORKAROUND DELETES THIS MODULE'S REASON TO EXIST.** Running one
`search_single` per level per world reproduces the numbers (snapshot-at-L == standalone-at-L is
exactly this module's guarantee), but it costs `sum(levels)` instead of `max(levels)` — ~2-2.7x the
sims for the usual ladders — which is precisely the Kx saving the snapshot claim is *made of*. So a
"converted" snapshot module would be a slower module with the same output and a false name. Where
that trade is still worth taking because the per-sim ratio dominates, it is taken EXPLICITLY and
labelled, in `gate_b_depth_transfer.py --backend rust`; it is not smuggled in here.

A third reason to leave this file alone even if both blockers closed: it is deliberately pinned to
the **pre-C5 frozen `7fc930b8` substrate**, and `champion_factory._hashers()` imports
`_frozen_config_hash` from it. It is a HASH SOURCE for the factory as well as a search primitive,
so it is not a place to introduce an engine switch casually.
"""
from __future__ import annotations
import os

DEFAULT_LEVELS = (200, 400, 800, 1600, 3200, 6400)
# The frozen v2.9 substrate hash. The config_hash EXCLUDES the default-off v2.10
# `bag_close` field so the value stays 7fc930b82801cb43 across the v2.10 field
# addition (commit 1f521dd added LeafConfig.bag_close, which would otherwise shift
# the full-asdict hash to f34a53bd5067ac16 with NO change to the leaf values). This
# mirrors the bag_close exclusion in tests/test_v29_flat_curve.py and
# tests/test_frozen_substrates.py, and keeps this consistent with the ~10 scripts +
# governance/LEAF_SUBSTRATES.yaml that pin 7fc930b82801cb43. `frozen_v29_cfg()`
# computes the hash the same way (drops the default-off bag_close key).
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


# The full leaf-shape env that pins the frozen v2.9 LeafConfig. Split into keys we
# SET and keys we CLEAR so the config is built from an EXPLICIT, complete override
# of every CARCASSONNE_V25_*/V28_*/V29_*/V210_* var that _config_from_env() reads —
# never from the once-cached global DEFAULT_CONFIG, which is baked from whatever env
# happened to be set at first import (sibling test modules pollute it via setdefault).
# (CARCASSONNE_V25_MEEPLE_K is set from the value_norm arg; the leaf-PATH vars
# USE_FLAT_LEAF/USE_CY_REPR don't enter LeafConfig, so they're irrelevant here.)
_FROZEN_CFG_ENV_SET = {
    "CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",   # -> 3-open closure {1:.5, 2:.2, 3:.05}
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
}
_FROZEN_CFG_ENV_CLEAR = (
    "CARCASSONNE_V25_ONE_OPEN_ONLY", "CARCASSONNE_V25_RESIDUAL_SCALE",
    "CARCASSONNE_V25_TILE_COUNTING", "CARCASSONNE_V25_CLOSURE_SLACK",
    "CARCASSONNE_V28_FARM_MAJORITY", "CARCASSONNE_V28_MEEPLE_K",
    "CARCASSONNE_V28_MEEPLE_RECOVERY_T0", "CARCASSONNE_V210_BAG_CLOSE",
)


# Default-off LeafConfig fields the frozen-cfg recipe EXCLUDES so the frozen v2.9
# substrate (7fc930b8) and the PRODUCTION champion (158f17ff) keep their historical
# hashes across additive, default-off field additions (bag_close 2026-07-04; the C7
# Term R / Term F knobs 2026-07-13). A field is dropped ONLY when it holds its
# default-off value; a SET knob (candidate leaf) still shifts the hash. Mirror this
# set in every _cfg_hash consumer (tests/test_v29_flat_curve.py, tests/
# test_frozen_substrates.py, and the ~6 provenance scripts that pin FROZEN_V29_HASH).
_FROZEN_HASH_DEFAULT_OFF = {
    "bag_close": False,
    "v29_meeple_return_k": 0.0,
    "v29_farm_flip_k": 0.0,
    # F6 soft cap (CL-063, 2026-07-23): default-off candidate-only knobs. Excluded so
    # the frozen substrate (7fc930b8) + champion (158f17ff/6dfffd57) hashes hold.
    "soft_cap_slope": 0.0,
    "opp_soft_cap_slope": 0.0,
}


def _frozen_config_hash(cfg) -> str:
    """config_hash of a LeafConfig, EXCLUDING the default-off fields in
    `_FROZEN_HASH_DEFAULT_OFF` (so the frozen v2.9 substrate keeps its historical
    hash across additive default-off field additions — see FROZEN_V29_HASH). Mirrors
    the exclusion in tests/test_v29_flat_curve.py::_cfg_hash and
    tests/test_frozen_substrates.py."""
    import dataclasses as dc, hashlib, json
    d = {k: (list(v) if isinstance(v, tuple) else v)
         for k, v in dc.asdict(cfg).items()
         if not (k in _FROZEN_HASH_DEFAULT_OFF and v == _FROZEN_HASH_DEFAULT_OFF[k])}
    return hashlib.sha256(
        json.dumps(d, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]


def frozen_v29_cfg(value_norm: float = 2.0):
    """Build the frozen v2.9 LeafConfig DETERMINISTICALLY and assert its
    config_hash == FROZEN_V29_HASH. Loud on drift.

    Built from an EXPLICIT full leaf-shape env override (not the once-cached global
    DEFAULT_CONFIG), so session env pollution from sibling test modules cannot change
    it: identical config whether run alone or in a polluted in-group session.
    `value_norm` is the flat meeple_k (2.0 for the frozen substrate)."""
    import os
    from carcassonne_ai import virtual_score_v2 as _vs

    keys = list(_FROZEN_CFG_ENV_SET) + list(_FROZEN_CFG_ENV_CLEAR) + ["CARCASSONNE_V25_MEEPLE_K"]
    saved = {k: os.environ.get(k) for k in keys}
    try:
        for k, v in _FROZEN_CFG_ENV_SET.items():
            os.environ[k] = v
        os.environ["CARCASSONNE_V25_MEEPLE_K"] = str(float(value_norm))
        for k in _FROZEN_CFG_ENV_CLEAR:
            os.environ.pop(k, None)
        cfg = _vs._config_from_env()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    h = _frozen_config_hash(cfg)
    assert h == FROZEN_V29_HASH, f"leaf is not frozen v2.9 (config_hash {h} != {FROZEN_V29_HASH})"
    return cfg


RUST_BACKEND_GAP = (
    "snapshot.py has NO carc_rs backend and cannot get one from a caller-side change. "
    "(1) AGENT: it drives HeuristicMCTS (vanilla UCT + virtual_score leaf); carc_core::search "
    "implements PUCT-with-heuristic-priors only, so there is no surface to call. "
    "(2) MECHANISM: snapshot_search reads the root BETWEEN simulations; "
    "MirrorState.search_single is one whole search per FFI call with no per-sim hook, no "
    "snapshot callback and no resume. "
    "(3) EVEN IF BOTH CLOSED, the only faithful route — one search_single per level — costs "
    "sum(levels) instead of max(levels) (~2-2.7x) and therefore DELETES the Kx snapshot claim "
    "this module exists for. Closing this needs a rust UCT search AND a stepped/snapshot API in "
    "carc_core; until then run the multi-depth ladder on the python backend, or use "
    "gate_b_depth_transfer --backend rust, which takes the sum(levels) trade EXPLICITLY and "
    "says so in its manifest.")


def rust_backend(*_args, **_kwargs):
    """FAIL CLOSED for any caller reaching for a Rust snapshot search.

    Exists so the gap is a raised error carrying its own reason, rather than something a reader
    has to infer from the absence of a `--backend` flag (rustport P6 Class-B, 2026-08-02)."""
    raise NotImplementedError(RUST_BACKEND_GAP)


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
