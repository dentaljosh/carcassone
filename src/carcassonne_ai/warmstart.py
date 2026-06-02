"""Warm-start dataset utilities — labeled-position generation, IO, and a
torch Dataset that wraps the saved .npz files.

Two label strategies (Phase 3 smoke-compares them before committing to the
full run):
  - "mcts":      policy = MCTS(s=N).visit_distribution; value = virtual_score
  - "heuristic": policy = softmax(virtual_score after each legal action);
                 value = virtual_score

Storage: one .npz per game under data/warmstart/<strategy>/seed_<NNNNN>.npz.
Each file holds N sampled positions from that game, all four arrays:
  boards:      (N, n_channels, W, W) float32
  scalars:     (N, n_scalar_features) float32
  policies:    (N, action_size) float32     - rows sum to 1 over valid moves
  values:      (N,) float32                  - tanh(diff/15)
  valid_masks: (N, action_size) bool

Resume by skipping seeds whose .npz already exists.
"""
from __future__ import annotations

import math
import os
import random
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

from .action_space import action_size as compute_action_size
from .aux_targets import OWNERSHIP_PLANES, extract_terminal_ownership, ownership_planes
from .game_wrapper import Game
from .virtual_score import virtual_score, virtual_score_inplace


SCORE_NORM_SCALE_FOR_LABELS = 15.0  # matches game_wrapper's reward normalization


def normalized_value_target(state, player: int) -> float:
    diff = virtual_score(state, player)
    return math.tanh(diff / SCORE_NORM_SCALE_FOR_LABELS)


@dataclass
class GameDataset:
    boards: np.ndarray       # (N, C, W, W) float32
    scalars: np.ndarray      # (N, S) float32
    policies: np.ndarray     # (N, A) float32
    values: np.ndarray       # (N,) float32
    valid_masks: np.ndarray  # (N, A) bool
    # Path B aux target: per-cell final feature ownership, current-player POV,
    # (N, OWNERSHIP_PLANES, W, W) float32 in {-1, 0, +1} (city/road/farm planes).
    ownership: np.ndarray

    def save(self, path: Path) -> None:
        """Save to a private temp file then atomically rename onto `path`.
        The rename is atomic; readers see only fully-written files.

        The temp name is `.<stem>.<host>.<pid>.partial.npz`:
        - leading dot — never matched by the `seed_*.npz` globs every consumer
          uses, so a straggler left by a worker killed in the narrow
          savez->rename window cannot be picked up as a training file;
        - `<host>.<pid>` — unique per writer across machines, not just within
          one box: under work-stealing two workers on different boxes can
          (re)play the same seed, and bare PIDs collide cross-box. With the
          host included they write separate temp files; only the final atomic
          rename contends (last writer wins, both datasets valid)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        # Explicit .npz extension on the temp file: np.savez_compressed would
        # otherwise append one.
        partial = path.with_name(
            f".{path.stem}.{socket.gethostname()}.{os.getpid()}.partial.npz"
        )
        np.savez_compressed(
            partial,
            boards=self.boards,
            scalars=self.scalars,
            policies=self.policies,
            values=self.values,
            valid_masks=self.valid_masks,
            ownership=self.ownership,
        )
        partial.replace(path)

    @classmethod
    def load(cls, path: Path) -> "GameDataset":
        # Any failure reading the .npz means the file is unusable; re-raise
        # with the path so a corrupt/truncated file is identifiable instead
        # of surfacing as a bare BadZipFile with no filename attached.
        try:
            with np.load(path) as data:
                return cls(
                    boards=data["boards"],
                    scalars=data["scalars"],
                    policies=data["policies"],
                    values=data["values"],
                    valid_masks=data["valid_masks"],
                    ownership=data["ownership"],
                )
        except Exception as e:
            raise RuntimeError(
                f"failed to load .npz (corrupt or truncated?): {path}"
            ) from e

    def __len__(self) -> int:
        return self.boards.shape[0]


def rotate_dataset_90(ds: "GameDataset") -> "GameDataset":
    """Rotate every example in a GameDataset 90° CCW (C5 symmetry augmentation).

    boards -> rotate_board_repr_90 (spatial + directional channel perm);
    policies / valid_masks -> scattered through the action-rotation permutation;
    ownership -> spatial rotation only (per-cell planes, no directional channels);
    scalars + values -> unchanged (orientation-invariant). Applying 4× is identity.
    """
    from .action_space import action_rotation_perm
    from .action_space import action_size as _asize
    from .board_repr import rotate_board_repr_90_batch

    W = ds.boards.shape[-1]
    A = ds.policies.shape[-1]
    if A != _asize(W):
        raise ValueError(
            f"policy width {A} != action_size({W})={_asize(W)} — window/action mismatch"
        )
    P = action_rotation_perm(W)
    pol = np.zeros_like(ds.policies)
    pol[:, P] = ds.policies
    msk = np.zeros_like(ds.valid_masks)
    msk[:, P] = ds.valid_masks
    return GameDataset(
        boards=rotate_board_repr_90_batch(ds.boards),
        scalars=ds.scalars.copy(),
        policies=pol,
        values=ds.values.copy(),
        valid_masks=msk,
        ownership=np.ascontiguousarray(np.rot90(ds.ownership, k=1, axes=(2, 3))),
    )


def augment_with_rotations(ds: "GameDataset") -> "GameDataset":
    """Return a GameDataset with each example + its 3 rotations (4× rows).

    Free data: Carcassonne is invariant under the 4 square rotations (reflection
    is NOT — curved roads / directed art break it). Use in the training data
    loader; no scratch retrain needed (operates on existing tensors)."""
    rots = [ds]
    cur = ds
    for _ in range(3):
        cur = rotate_dataset_90(cur)
        rots.append(cur)
    return GameDataset(
        boards=np.concatenate([r.boards for r in rots], axis=0),
        scalars=np.concatenate([r.scalars for r in rots], axis=0),
        policies=np.concatenate([r.policies for r in rots], axis=0),
        values=np.concatenate([r.values for r in rots], axis=0),
        valid_masks=np.concatenate([r.valid_masks for r in rots], axis=0),
        ownership=np.concatenate([r.ownership for r in rots], axis=0),
    )


DEFAULT_HEURISTIC_TAU = 10.0


def _heuristic_policy(
    game: Game, board, valid_mask: np.ndarray, *, tau: float = DEFAULT_HEURISTIC_TAU
) -> np.ndarray:
    """Policy target via 1-ply virtual_score lookahead. For each legal action,
    apply it, score the resulting state, softmax across legal actions with
    temperature `tau`.

    Returns a length-action_size float32 array, zeros on invalid actions.

    Tau choice (measured empirically — virtual_score gaps between candidate
    actions are typically just 1-5 points so the softmax flattens quickly):
      - 10.0 (current default): top-1 mass ~45% on mid-game prod data.
        Very soft — preserves near-tie information but gives the policy
        head a weak signal to fit.
      - 1.0: top-1 mass ~47%, top-3 cumulative ~62%.
      - 0.5: top-1 mass ~56%, top-3 cumulative ~75%. Recommended next
        try if the policy head is undertrained at tau=10.
      - 0.1: nearly one-hot (top-1 ~62%, top-3 ~87%). Risks amplifying
        heuristic noise on actions with virtual_score within 1 point.
    """
    legal = np.flatnonzero(valid_mask)
    if legal.size == 0:
        return np.zeros_like(valid_mask, dtype=np.float32)
    scores = np.empty(legal.size, dtype=np.float32)
    player = board.state.current_player
    # Single-deepcopy-per-action: clone the engine state once, apply the
    # action in place, run virtual_score_inplace on the mutated state.
    # Replaces the previous double-deepcopy path (get_next_state copied via
    # apply_action, then virtual_score copied again). Skips Board.from_state
    # entirely — virtual_score doesn't need the window offset, only state.
    # Reviewer flag, 2026-04-28 round 2.
    import copy as _copy
    from .action_space import decode
    from wingedsheep.carcassonne.utils.state_updater import StateUpdater
    for i, action_idx in enumerate(legal):
        action = decode(
            int(action_idx),
            off=board.offset,
            phase=board.state.phase.value,
            next_tile=board.state.next_tile,
            last_tile_coord=(
                board.state.last_tile_action.coordinate
                if board.state.last_tile_action is not None
                else None
            ),
        )
        scratch_state = _copy.deepcopy(board.state)
        StateUpdater.apply_action_inplace(game_state=scratch_state, action=action)
        # virtual_score from CURRENT player's perspective; positive = good for us
        scores[i] = virtual_score_inplace(scratch_state, player)
    z = scores / tau
    z -= z.max()
    e = np.exp(z)
    p = e / e.sum()
    out = np.zeros(valid_mask.shape[0], dtype=np.float32)
    out[legal] = p
    return out


def _heuristic_policy_2ply(
    game: Game, board, valid_mask: np.ndarray, *, tau: float = DEFAULT_HEURISTIC_TAU
) -> np.ndarray:
    """Policy target via 2-ply lookahead for tile-phase actions.

    For each legal tile-phase action: apply the tile, enumerate the meeple/
    pass follow-ups, score each via virtual_score, take the BEST follow-up
    score as this tile action's value. Captures the joint 'tile + best
    meeple' decision that the 1-ply variant misses. (Reviewer pass-2,
    BACKLOG, 2026-04-28.)

    For MEEPLES-phase positions falls through to 1-ply: after a meeple
    decision the turn is over and the next ply is the opponent's, which
    we don't score from our perspective.

    Cost: ~7x deepcopy work vs 1-ply for tile-phase positions (1 outer +
    ~6 meeple candidates per tile action). Halved for the project's
    half-tile/half-meeple position split: ~3-4x slower overall than 1-ply
    for the same dataset size.
    """
    is_tile_phase = board.state.phase.value == "tiles"
    if not is_tile_phase:
        return _heuristic_policy(game, board, valid_mask, tau=tau)

    legal = np.flatnonzero(valid_mask)
    if legal.size == 0:
        return np.zeros_like(valid_mask, dtype=np.float32)

    import copy as _copy
    from .action_space import decode
    from wingedsheep.carcassonne.utils.state_updater import StateUpdater
    from wingedsheep.carcassonne.utils.action_util import ActionUtil

    scores = np.empty(legal.size, dtype=np.float32)
    player = board.state.current_player

    for i, action_idx in enumerate(legal):
        tile_action = decode(
            int(action_idx),
            off=board.offset,
            phase="tiles",
            next_tile=board.state.next_tile,
        )
        post_tile = _copy.deepcopy(board.state)
        StateUpdater.apply_action_inplace(game_state=post_tile, action=tile_action)

        # If applying terminated the game or didn't transition to MEEPLES
        # (e.g., tile-phase pass), score directly.
        if post_tile.is_terminated() or post_tile.phase.value != "meeples":
            scores[i] = virtual_score_inplace(post_tile, player)
            continue

        followups = ActionUtil.get_possible_actions(post_tile)
        if not followups:
            scores[i] = virtual_score_inplace(post_tile, player)
            continue

        best = -float("inf")
        for follow in followups:
            scratch = _copy.deepcopy(post_tile)
            StateUpdater.apply_action_inplace(game_state=scratch, action=follow)
            s = virtual_score_inplace(scratch, player)
            if s > best:
                best = s
        scores[i] = best

    z = scores / tau
    z -= z.max()
    e = np.exp(z)
    p = e / e.sum()
    out = np.zeros(valid_mask.shape[0], dtype=np.float32)
    out[legal] = p
    return out


def _mcts_policy(mcts_visits: dict, action_size_: int) -> np.ndarray:
    """Policy target = MCTS visit count distribution, normalized."""
    out = np.zeros(action_size_, dtype=np.float32)
    if not mcts_visits:
        return out
    total = sum(mcts_visits.values())
    for action, n in mcts_visits.items():
        out[action] = n / total
    return out


def generate_one_game_dataset(
    seed: int,
    label_strategy: str,
    *,
    n_positions_per_game: int = 10,
    mcts_sims: int = 50,
    skip_early: int = 10,
    skip_late: int = 10,
    heuristic_tau: float = DEFAULT_HEURISTIC_TAU,
    heuristic_lookahead: str = "1ply",
    include_farm_scalars: bool = False,
) -> GameDataset:
    """Play a random game; sample N mid-game positions; label each.

    label_strategy: "mcts" or "heuristic".
    heuristic_lookahead: "1ply" (default; tile-phase scored at tile-only) or
                        "2ply" (tile-phase scored as tile + best meeple
                        follow-up; ~3-4x slower gen).
    include_farm_scalars: Path B Step E — emit the 12-scalar feature vector (10
                        base + 2 farm-control) in the recorded dataset. Must match
                        the net trained on this corpus (train_warmstart
                        --include-farm-scalars). Default off → legacy 10-scalar.
    """
    if label_strategy not in ("mcts", "heuristic"):
        raise ValueError(f"label_strategy must be 'mcts' or 'heuristic', got {label_strategy!r}")
    if heuristic_lookahead not in ("1ply", "2ply"):
        raise ValueError(f"heuristic_lookahead must be '1ply' or '2ply', got {heuristic_lookahead!r}")

    # Seed the GLOBAL random module — the engine shuffles its deck via
    # random.shuffle(global), so without this, runs are not seed-reproducible.
    # (Caught by external review 2026-04-28.) The local rng below is for our
    # own action choices.
    random.seed(seed)
    rng = random.Random(seed + 1)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=include_farm_scalars)
    board = game.get_init_board()

    # Walk the game, recording at each step the data we'd need to label
    # later, then sample positions to actually label.
    snapshots: list[tuple] = []  # (board_snapshot, valid_mask, current_player)
    while game.get_game_ended(board, 0) == 0.0:
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        # Snapshot BEFORE we apply the action.
        snapshots.append((board, mask, board.state.current_player))
        board, _ = game.get_next_state(board, int(rng.choice(legal)))

    n_total = len(snapshots)
    eligible_lo = skip_early
    eligible_hi = max(skip_early + 1, n_total - skip_late)
    if eligible_hi <= eligible_lo:
        eligible_indices = list(range(n_total))
    else:
        eligible_indices = list(range(eligible_lo, eligible_hi))

    # Sample n_positions_per_game positions from eligible mid-game.
    if len(eligible_indices) <= n_positions_per_game:
        chosen = eligible_indices
    else:
        chosen = sorted(rng.sample(eligible_indices, n_positions_per_game))

    # Label each chosen position.
    A = compute_action_size(game.window_size)
    boards_arr = []
    scalars_arr = []
    policies_arr = []
    values_arr = []
    masks_arr = []
    ownership_arr = []

    # Defer MCTS imports so heuristic-only runs don't pay the cost.
    # Share one MCTS-side Game across all positions in this run; the legal-moves
    # cache is reusable across positions (same engine state-key semantics) and
    # we save N×Game-construction overhead.
    if label_strategy == "mcts":
        from .mcts import MCTS
        mcts_game = Game(enable_legal_moves_cache=True, include_farm_scalars=include_farm_scalars)

    for idx in chosen:
        snap_board, mask, player = snapshots[idx]
        obs, scalars = game.get_canonical_form(snap_board, player)
        if label_strategy == "heuristic":
            if heuristic_lookahead == "2ply":
                policy = _heuristic_policy_2ply(game, snap_board, mask, tau=heuristic_tau)
            else:
                policy = _heuristic_policy(game, snap_board, mask, tau=heuristic_tau)
        else:
            mcts = MCTS(game=mcts_game, simulations=mcts_sims, seed=seed * 1000 + idx)
            visits = mcts.search(snap_board)
            policy = _mcts_policy(visits, A)
            mcts_game.clear_caches()  # bound per-search memory; cache is per-MCTS anyway
            del mcts
        value = float(normalized_value_target(snap_board.state, player))
        # Ownership aux label: "who owns each feature if scored now" — the same
        # virtual_score semantics as the value target above, so value + ownership
        # are consistent. Projected onto this position's window + POV.
        records = extract_terminal_ownership(snap_board.state)
        owners = ownership_planes(records, snap_board.offset, player, game.window_size)
        boards_arr.append(obs.astype(np.float32))
        scalars_arr.append(scalars.astype(np.float32))
        policies_arr.append(policy)
        values_arr.append(value)
        masks_arr.append(mask.astype(bool))
        ownership_arr.append(owners)

    return GameDataset(
        boards=np.stack(boards_arr) if boards_arr else np.empty((0, 0, 0, 0), dtype=np.float32),
        scalars=np.stack(scalars_arr) if scalars_arr else np.empty((0, 0), dtype=np.float32),
        policies=np.stack(policies_arr) if policies_arr else np.empty((0, A), dtype=np.float32),
        values=np.array(values_arr, dtype=np.float32),
        valid_masks=np.stack(masks_arr) if masks_arr else np.empty((0, A), dtype=bool),
        ownership=(
            np.stack(ownership_arr)
            if ownership_arr
            else np.empty((0, OWNERSHIP_PLANES, game.window_size, game.window_size), dtype=np.float32)
        ),
    )


def iter_game_dataset_files(root: Path) -> Iterator[Path]:
    """Yield all .npz files in the warmstart root, sorted by name."""
    yield from sorted(root.glob("seed_*.npz"))


# ---------------------------------------------------------------------------
# Streaming dataset
# ---------------------------------------------------------------------------
#
# A torch IterableDataset that lazy-loads one .npz at a time. Designed for
# the production warmstart at 500K-position scale, where loading everything
# into RAM (~60 GB raw, ~10x compressed) is infeasible. The smoke trainer
# still uses the in-memory TensorDataset path; this is the production path.

# Imports are deferred to the class body so the warmstart module stays
# usable in environments without torch installed (e.g. data-gen-only nodes).
def _torch_modules():
    import torch
    from torch.utils.data import IterableDataset, get_worker_info
    return torch, IterableDataset, get_worker_info


def split_files_train_val(
    files: list[Path], val_fraction: float, seed: int = 0
) -> tuple[list[Path], list[Path]]:
    """Deterministically partition a file list into train/val by FILE
    (= by GAME, since one .npz = one game). Each file goes to exactly one
    side; positions never leak across the split.

    Edge cases:
      - val_fraction == 0.0: no val files; all go to train.
      - val_fraction == 1.0: rejected — production training requires a
        non-empty train split. Use a small positive fraction or split
        externally if you really want pure-val.
      - val_fraction outside [0, 1): rejected.
      - n == 0: returns ([], []).
      - n == 1 with 0 < val_fraction < 1: file goes to train; rounding
        a single file to a val split silently empties train.
    """
    if not (0.0 <= val_fraction < 1.0):
        raise ValueError(
            f"val_fraction must satisfy 0 <= val_fraction < 1, got {val_fraction!r}"
        )
    n = len(files)
    if n == 0:
        return [], []
    rng = random.Random(seed)
    perm = list(range(n))
    rng.shuffle(perm)
    if val_fraction == 0.0 or n < 2:
        n_val = 0
    else:
        n_val = max(1, int(round(n * val_fraction)))
        n_val = min(n_val, n - 1)  # never empty the train split
    val_idx = set(perm[:n_val])
    train = [f for i, f in enumerate(files) if i not in val_idx]
    val = [f for i, f in enumerate(files) if i in val_idx]
    return train, val


def make_streaming_dataset(
    files: list[Path],
    *,
    shuffle_files_each_epoch: bool = True,
    shuffle_within_file: bool = True,
    seed: int = 0,
):
    """Build a torch IterableDataset that streams (board, scalar, policy,
    value, mask) tuples from the given .npz file list.

    Worker sharding: when used with DataLoader(num_workers > 0), each worker
    sees a disjoint slice of the file list. File order is shuffled per-epoch
    with a worker-local epoch counter so different workers don't yield in
    lock-step. Within a file, position order is also optionally shuffled.

    Each .npz holds ~10 positions; loading one is ~50ms. 500K positions
    across 50K files ≈ ~5 min per epoch of pure file-IO with 1 worker, or
    ~1.3 min with 4 workers.
    """
    torch, IterableDataset, get_worker_info = _torch_modules()

    files = list(files)

    class StreamingWarmstartDataset(IterableDataset):  # type: ignore[valid-type, misc]
        def __init__(self) -> None:
            super().__init__()
            self.files = files
            self.seed = seed
            self.epoch = 0

        def set_epoch(self, epoch: int) -> None:
            """Called once per training epoch by the trainer to vary the
            file-shuffle seed. Without this, every epoch sees the same
            file order — fine if `shuffle_files_each_epoch=False`, bad
            otherwise.
            """
            self.epoch = epoch

        def __iter__(self):
            wi = get_worker_info()
            n_workers = wi.num_workers if wi is not None else 1
            worker_id = wi.id if wi is not None else 0
            local_files = list(self.files)
            if shuffle_files_each_epoch:
                # zlib.crc32 is process-stable; Python's hash() is salted by
                # PYTHONHASHSEED so reusing it gives different orderings across
                # runs with the same seed. Reproducibility matters for ablations.
                import zlib
                key = f"{self.seed}|{self.epoch}".encode()
                rng = random.Random(zlib.crc32(key))
                rng.shuffle(local_files)
            # Shard across workers AFTER the shuffle so each worker still
            # gets a representative slice.
            local_files = local_files[worker_id::n_workers]
            for path in local_files:
                ds = GameDataset.load(path)
                if len(ds) == 0:
                    continue
                idx_order = list(range(len(ds)))
                if shuffle_within_file:
                    import zlib
                    key2 = f"{self.seed}|{self.epoch}|{path!s}".encode()
                    rng2 = random.Random(zlib.crc32(key2))
                    rng2.shuffle(idx_order)
                for i in idx_order:
                    yield (
                        torch.from_numpy(ds.boards[i]),
                        torch.from_numpy(ds.scalars[i]),
                        torch.from_numpy(ds.policies[i]),
                        torch.tensor(ds.values[i], dtype=torch.float32),
                        torch.from_numpy(ds.valid_masks[i]),
                        torch.from_numpy(ds.ownership[i]),
                    )

    return StreamingWarmstartDataset()


def count_positions(files: list[Path]) -> int:
    """Cheap pass to sum position counts without loading the full arrays.
    Used by the trainer to log dataset size; relies on .npz storing the
    `boards` array's shape header, which np.load reads lazily.
    """
    total = 0
    for f in files:
        try:
            with np.load(f) as data:
                total += int(data["values"].shape[0])
        except Exception as e:
            raise RuntimeError(
                f"failed to load .npz (corrupt or truncated?): {f}"
            ) from e
    return total
