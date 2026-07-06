"""Diagnostics for the self-play "invalid visit clip" event (Phase 0.3).

`play_one_selfplay_game` builds its policy target from the NeuralMCTS root
visit distribution, then intersects it with the snapshot legality mask
(`get_valid_moves(board)` taken at the top of the ply). Any visit landing on a
masked-off action is dropped ("clipped"). The drop was a silent defensive
patch with a "not yet root-caused" comment; this module root-causes it.

`capture_clip_repro` records a full, self-describing repro for every clip so an
offline reader can decide WHICH mechanism produced the illegal visit:

  * cache staleness  — the snapshot mask was served from a stale legal-moves
    cache entry keyed by `string_representation` (a wrong-board hit); a fresh
    (cache-cleared) recompute would include the action.
  * offset drift     — the incremental centroid tracker (`board.sum_row/col/
    tile_count`) diverged from the true placed-tile centroid, so `board.offset`
    (which indexes the action space) means different cells than a full re-scan.
  * transposition alias — the root's `children` holds an action key that is NOT
    in `root.valid_actions` (a mis-attributed aliased/colliding child).

The discriminators are computed live at the clip site (below) and written to
`{CARCASSONNE_CLIP_TRACE_DIR}/clip_<pid>.jsonl` (one JSON object per line, one
file per worker process so parallel Pool workers never interleave). The module
also keeps a process-local counter of (moves seen, clips seen) so a run can
BOUND the clip frequency even when it is zero.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

import numpy as np

# Process-local counters. Bumped by play_one_selfplay_game; read by the caller
# (or dumped at process exit) to bound the clip frequency.
CLIP_COUNT = 0          # number of (action, count) visits dropped
CLIP_MOVE_COUNT = 0     # number of learner moves that had >=1 clip
LEARNER_MOVE_COUNT = 0  # total learner moves seen (denominator for frequency)


def trace_dir() -> str | None:
    """Directory to write clip repros to, or None (default) to disable file
    capture. Counters are always maintained regardless."""
    d = os.environ.get("CARCASSONNE_CLIP_TRACE_DIR")
    return d or None


def _mask_hash(mask: np.ndarray) -> str:
    return hashlib.blake2b(np.ascontiguousarray(mask).tobytes(), digest_size=8).hexdigest()


def _off_tuple(off) -> tuple[int, int, int]:
    return (int(off.origin_row), int(off.origin_col), int(off.size))


def capture_clip_repro(
    *,
    game,
    board,
    mcts,
    mask: np.ndarray,
    offending: list[tuple[int, float]],
    ply: int,
    cur_player: int,
) -> dict:
    """Build (and, if enabled, persist) a full repro dict for a clip event.

    `offending` is the list of (action_index, visit_count) pairs that landed on
    a masked-off action for THIS move. `mask` is the snapshot mask the outer
    loop used. All the expensive diagnostics run only here — i.e. only when a
    clip actually fired — so the healthy path pays nothing.
    """
    from .board_repr import centroid_sums, compute_window_offset

    snap_key = game.string_representation(board)

    # --- OFFSET DRIFT probe: incremental tracker vs a full re-scan -----------
    true_sr, true_sc, true_tc = centroid_sums(board.state)
    true_off = compute_window_offset(board.state)
    board_off = board.offset
    offset_drift = _off_tuple(board_off) != _off_tuple(true_off)
    sums_drift = (
        int(board.sum_row), int(board.sum_col), int(board.tile_count)
    ) != (int(true_sr), int(true_sc), int(true_tc))

    # --- CACHE / NONDETERMINISM probe: recompute the mask from scratch -------
    # Clear the legal cache so this is a genuine fresh enumeration (not a hit on
    # whatever the snapshot wrote), then diff it against the snapshot mask.
    hits0 = game._legal_cache_hits if game._legal_cache is not None else None
    misses0 = game._legal_cache_misses if game._legal_cache is not None else None
    game.clear_caches()
    fresh_mask = game.get_valid_moves(board)
    mask_matches_fresh = bool(np.array_equal(mask, fresh_mask))

    # --- MCTS / transposition state at the root ------------------------------
    root = mcts._nodes.get(snap_key)
    root_valid = set(int(a) for a in root.valid_actions) if root is not None else None
    root_children = sorted(int(a) for a in root.children) if root is not None else None
    root_aliases = sorted(int(a) for a in root.child_aliases) if root is not None else None

    per_action = []
    for ai, c in offending:
        ai = int(ai)
        try:
            decoded = repr(
                game._decode_for(board.state, board_off, ai)
            )
        except Exception as e:  # decode can raise WindowOverflow etc.
            decoded = f"<decode-error: {type(e).__name__}: {e}>"
        per_action.append({
            "action": ai,
            "visits": float(c),
            "in_snapshot_mask": bool(mask[ai]),
            "in_fresh_mask": bool(fresh_mask[ai]),
            "in_root_valid_actions": (ai in root_valid) if root_valid is not None else None,
            "is_root_alias": (ai in root.child_aliases) if root is not None else None,
            "decoded_under_board_offset": decoded,
        })

    k_remaining = int(board.total_tiles - board.tile_count)
    rec = {
        "ts": time.time(),
        "pid": os.getpid(),
        "ply": int(ply),
        "cur_player": int(cur_player),
        "k_remaining": k_remaining,
        "snapshot_key": snap_key,
        "snapshot_mask_hash": _mask_hash(mask),
        "snapshot_n_legal": int(mask.sum()),
        "fresh_mask_hash": _mask_hash(fresh_mask),
        "fresh_n_legal": int(fresh_mask.sum()),
        "snapshot_mask_matches_fresh": mask_matches_fresh,
        # OFFSET DRIFT verdict
        "board_offset": _off_tuple(board_off),
        "true_offset_full_scan": _off_tuple(true_off),
        "offset_drift": offset_drift,
        "incremental_sums": [int(board.sum_row), int(board.sum_col), int(board.tile_count)],
        "true_sums_full_scan": [int(true_sr), int(true_sc), int(true_tc)],
        "sums_drift": sums_drift,
        # cache stats at clip time (before the diagnostic clear above)
        "legal_cache_hits": hits0,
        "legal_cache_misses": misses0,
        # MCTS state
        "n_tree_nodes": len(mcts._nodes),
        "root_present": root is not None,
        "root_N": int(root.N) if root is not None else None,
        "root_n_children": len(root.children) if root is not None else None,
        "root_n_valid_actions": len(root.valid_actions) if root is not None else None,
        "root_children": root_children,
        "root_aliases": root_aliases,
        "root_key_matches_snapshot": (root is not None and root.state_key == snap_key),
        "offending_actions": per_action,
    }

    d = trace_dir()
    if d is not None:
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"clip_{os.getpid()}.jsonl")
        with open(path, "a") as fh:
            fh.write(json.dumps(rec) + "\n")
    return rec
