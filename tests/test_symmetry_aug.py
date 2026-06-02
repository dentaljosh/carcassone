"""Tests for the C5 symmetry-augmentation board-tensor rotation
(board_repr.rotate_board_repr_90).

Three levels of rigor:
  1. The channel permutation is a valid bijection and rotate×4 == identity.
  2. Hand-geometry directional pinning: a feature placed on a KNOWN side/corner
     at a known cell lands exactly where a 90° CCW rotation must send it (uses
     np.rot90 as the spatial ground truth; the channel index is hand-derived).
  3. Structural preservation on a REAL encoded game board: tile-present count,
     per-side edge one-hot validity, and meeple counts are all conserved.
"""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))

import numpy as np

from carcassonne_ai import board_repr as BR
from carcassonne_ai.board_repr import (
    CH_EDGES,
    CH_FARMER_MEEPLE_MINE,
    CH_NORMAL_MEEPLE_MINE,
    CH_TILE_PRESENT,
    CORNERS_4,
    EDGE_BLOCK,
    EDGE_CATEGORIES,
    N_CHANNELS,
    SIDES_4,
    compute_window_offset,
    encode_board,
    rotate_board_repr_90,
)
from carcassonne_ai.game_wrapper import Game
from wingedsheep.carcassonne.objects.side import Side


W = 9  # small window for synthetic tests


def test_channel_perm_is_bijection():
    perm = BR._ROT_CHANNEL_PERM
    assert perm.shape == (N_CHANNELS,)
    assert sorted(perm.tolist()) == list(range(N_CHANNELS))


def test_rotate_four_times_is_identity():
    rng = np.random.default_rng(0)
    arr = rng.random((N_CHANNELS, W, W)).astype(np.float32)
    out = arr
    for _ in range(4):
        out = rotate_board_repr_90(out)
    np.testing.assert_allclose(out, arr, atol=0)


def test_rotate_shape_guard():
    import pytest

    with pytest.raises(ValueError):
        rotate_board_repr_90(np.zeros((N_CHANNELS, W), dtype=np.float32))
    with pytest.raises(ValueError):
        rotate_board_repr_90(np.zeros((N_CHANNELS + 1, W, W), dtype=np.float32))


def _expected_rotated_cell(r: int, c: int) -> tuple[int, int]:
    """Where (r, c) goes under np.rot90(k=1) — the spatial ground truth."""
    m = np.zeros((W, W), dtype=np.float32)
    m[r, c] = 1.0
    mr = np.rot90(m, k=1)
    er, ec = map(int, np.argwhere(mr == 1.0)[0])
    return er, ec


def test_edge_direction_top_to_left():
    # A CITY edge (cat 0) on side TOP at cell (2, 5). Under 90° CCW the TOP edge
    # becomes the LEFT edge (a tile facing up, rotated CCW, faces left).
    arr = np.zeros((N_CHANNELS, W, W), dtype=np.float32)
    top_city = CH_EDGES + SIDES_4.index(Side.TOP) * EDGE_CATEGORIES + 0
    arr[top_city, 2, 5] = 1.0
    out = rotate_board_repr_90(arr)

    left_city = CH_EDGES + SIDES_4.index(Side.LEFT) * EDGE_CATEGORIES + 0
    er, ec = _expected_rotated_cell(2, 5)
    assert out[left_city, er, ec] == 1.0
    assert out[left_city].sum() == 1.0
    # the TOP-city channel must now be empty (the feature moved off it)
    assert out[top_city].sum() == 0.0


def test_farmer_corner_direction_tl_to_bl():
    # A farmer on the TOP_LEFT corner. Under 90° CCW the NW corner -> SW corner
    # (BOTTOM_LEFT).
    arr = np.zeros((N_CHANNELS, W, W), dtype=np.float32)
    tl = CH_FARMER_MEEPLE_MINE + CORNERS_4.index(Side.TOP_LEFT)
    arr[tl, 3, 1] = 1.0
    out = rotate_board_repr_90(arr)

    bl = CH_FARMER_MEEPLE_MINE + CORNERS_4.index(Side.BOTTOM_LEFT)
    er, ec = _expected_rotated_cell(3, 1)
    assert out[bl, er, ec] == 1.0
    assert out[bl].sum() == 1.0
    assert out[tl].sum() == 0.0


def test_center_meeple_slot_is_rotation_fixed():
    from carcassonne_ai.board_repr import SIDES_5

    arr = np.zeros((N_CHANNELS, W, W), dtype=np.float32)
    center = CH_NORMAL_MEEPLE_MINE + SIDES_5.index(Side.CENTER)
    arr[center, 4, 6] = 1.0
    out = rotate_board_repr_90(arr)
    # stays on the CENTER channel; only the cell moves (spatial rotation)
    er, ec = _expected_rotated_cell(4, 6)
    assert out[center, er, ec] == 1.0
    assert out[center].sum() == 1.0


def _encode_real_board(seed: int):
    game = Game()
    random.seed(seed)
    board = game.get_init_board()
    for _ in range(40):
        if board.state.is_terminated():
            break
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        board, _ = game.get_next_state(board, int(random.choice(legal)))
    off = compute_window_offset(board.state, window_size=BR.DEFAULT_WINDOW_SIZE)
    return encode_board(board.state, board.state.current_player, off)


def test_rotate_action_round_trip_full_space():
    from carcassonne_ai.action_space import action_size, rotate_action

    for W in (5, 9, 25):
        A = action_size(W)
        for a in range(A):
            r = a
            for _ in range(4):
                r = rotate_action(r, W)
            assert r == a, f"action {a} not identity after 4 rotations (W={W})"


def test_rotate_action_cell_matches_rot90():
    # A tile action's cell remap must match np.rot90(k=1) — the same spatial
    # transform rotate_board_repr_90 applies.
    from carcassonne_ai.action_space import N_ROTATIONS, rotate_action

    Wt = 9
    for wr in range(Wt):
        for wc in range(Wt):
            idx = (wr * Wt + wc) * N_ROTATIONS + 0  # rot=0
            out = rotate_action(idx, Wt)
            cell = out // N_ROTATIONS
            nwr, nwc = divmod(cell, Wt)
            er, ec = _expected_rotated_cell_W(wr, wc, Wt)
            assert (nwr, nwc) == (er, ec)


def _expected_rotated_cell_W(r, c, w):
    m = np.zeros((w, w), dtype=np.float32)
    m[r, c] = 1.0
    mr = np.rot90(m, k=1)
    er, ec = map(int, np.argwhere(mr == 1.0)[0])
    return er, ec


def test_rotate_tile_delta_matches_edge_channel_perm():
    # ROT_TILE_DELTA must be the unique tile.turn() delta that reproduces the
    # edge-channel permutation rotate_board_repr_90 applies — i.e. the action's
    # tile-orientation remap agrees with the board-repr's edge rotation.
    from carcassonne_ai.action_space import ROT_TILE_DELTA
    from carcassonne_ai.board_repr import _encode_tile_edges, CH_EDGES, EDGE_BLOCK
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles

    eperm = BR._ROT_CHANNEL_PERM[CH_EDGES:CH_EDGES + EDGE_BLOCK]
    universal = set(range(4))
    for T in base_tiles.values():
        for rot in range(4):
            placed = T.turn(rot)
            rotated_edges = _encode_tile_edges(placed)[eperm]
            universal &= {
                d for d in range(4)
                if np.array_equal(_encode_tile_edges(placed.turn(d)), rotated_edges)
            }
    assert universal == {ROT_TILE_DELTA}, f"edge-perm delta {sorted(universal)} != {ROT_TILE_DELTA}"


def test_action_side_maps_are_inverse_of_board_src_maps():
    # rotate_action's forward side/corner maps must be the exact inverse of
    # board_repr's source maps, so action and board rotate the SAME direction.
    from carcassonne_ai.action_space import _FWD_CORNER, _FWD_SIDE

    for s, fwd in _FWD_SIDE.items():
        assert BR._SRC_SIDE_4[fwd] == s
    for c, fwd in _FWD_CORNER.items():
        assert BR._SRC_CORNER[fwd] == c


def test_action_rotation_perm_rotates_policy_consistently():
    from carcassonne_ai.action_space import (
        action_rotation_perm, action_size, rotate_action,
    )

    W = 9
    A = action_size(W)
    P = action_rotation_perm(W)
    assert P.shape == (A,)
    assert sorted(P.tolist()) == list(range(A))  # bijection

    rng = np.random.default_rng(1)
    policy = rng.random(A).astype(np.float32)
    policy /= policy.sum()
    rotated = np.zeros_like(policy)
    rotated[P] = policy
    # mass preserved
    np.testing.assert_allclose(rotated.sum(), policy.sum(), rtol=1e-6)
    # each action's mass lands on its rotate_action slot
    for a in range(A):
        assert rotated[rotate_action(a, W)] == policy[a]
    # 4 rotations of the vector return to the original
    out = policy.copy()
    for _ in range(4):
        nxt = np.zeros_like(out)
        nxt[P] = out
        out = nxt
    np.testing.assert_allclose(out, policy, atol=0)


def test_passes_are_rotation_fixed():
    from carcassonne_ai.action_space import (
        meeple_pass_index, rotate_action, tile_pass_index,
    )

    for W in (5, 9, 25):
        assert rotate_action(tile_pass_index(W), W) == tile_pass_index(W)
        assert rotate_action(meeple_pass_index(W), W) == meeple_pass_index(W)


def _synth_dataset(n=3, w=5, seed=7):
    from carcassonne_ai.action_space import action_size
    from carcassonne_ai.aux_targets import OWNERSHIP_PLANES
    from carcassonne_ai.warmstart import GameDataset

    rng = np.random.default_rng(seed)
    A = action_size(w)
    pol = rng.random((n, A)).astype(np.float32)
    pol /= pol.sum(axis=1, keepdims=True)
    return GameDataset(
        boards=rng.random((n, N_CHANNELS, w, w)).astype(np.float32),
        scalars=rng.random((n, 10)).astype(np.float32),
        policies=pol,
        values=rng.random(n).astype(np.float32),
        valid_masks=(rng.random((n, A)) > 0.5),
        ownership=rng.integers(-1, 2, (n, OWNERSHIP_PLANES, w, w)).astype(np.float32),
    )


def test_dataset_rotation_round_trip_and_consistency():
    from carcassonne_ai.warmstart import rotate_dataset_90

    ds = _synth_dataset()
    # single-sample primitive consistency: batched row 0 == single-sample fn
    r1 = rotate_dataset_90(ds)
    np.testing.assert_allclose(r1.boards[0], rotate_board_repr_90(ds.boards[0]))
    # 4 rotations == identity across all rotated fields
    cur = ds
    for _ in range(4):
        cur = rotate_dataset_90(cur)
    np.testing.assert_allclose(cur.boards, ds.boards, atol=0)
    np.testing.assert_allclose(cur.policies, ds.policies, atol=0)
    np.testing.assert_array_equal(cur.valid_masks, ds.valid_masks)
    np.testing.assert_allclose(cur.ownership, ds.ownership, atol=0)
    # orientation-invariant fields unchanged by a rotation
    np.testing.assert_allclose(r1.scalars, ds.scalars)
    np.testing.assert_allclose(r1.values, ds.values)
    # policy mass preserved per row
    np.testing.assert_allclose(r1.policies.sum(axis=1), ds.policies.sum(axis=1), rtol=1e-6)


def test_augment_with_rotations_quadruples():
    from carcassonne_ai.warmstart import augment_with_rotations

    ds = _synth_dataset(n=3)
    aug = augment_with_rotations(ds)
    assert len(aug) == 12  # 4 x 3
    # first block is the originals untouched
    np.testing.assert_allclose(aug.boards[:3], ds.boards, atol=0)
    np.testing.assert_allclose(aug.values[:3], ds.values, atol=0)
    # all four blocks share the same value/scalar rows (rotation-invariant)
    for k in range(4):
        np.testing.assert_allclose(aug.values[k * 3:(k + 1) * 3], ds.values, atol=0)


def test_streaming_augment_flag_quadruples_rows(tmp_path):
    from carcassonne_ai.warmstart import make_streaming_dataset

    ds = _synth_dataset(n=4, w=5)
    path = tmp_path / "seed_0.npz"
    ds.save(path)

    base = list(make_streaming_dataset([path], shuffle_files_each_epoch=False,
                                       shuffle_within_file=False))
    aug = list(make_streaming_dataset([path], shuffle_files_each_epoch=False,
                                      shuffle_within_file=False,
                                      augment_rotations=True))
    assert len(base) == 4          # original rows
    assert len(aug) == 16          # 4 rotations x 4 rows
    # each yielded item is the 6-tuple (board, scalar, policy, value, mask, own)
    assert len(aug[0]) == 6


def test_real_board_structural_preservation():
    for seed in range(5):
        arr = _encode_real_board(seed)
        out = rotate_board_repr_90(arr)
        # tile-present count conserved
        assert out[CH_TILE_PRESENT].sum() == arr[CH_TILE_PRESENT].sum()
        # every present tile still has exactly one edge category per side
        present = np.argwhere(out[CH_TILE_PRESENT] == 1.0)
        for (r, c) in present:
            for i in range(len(SIDES_4)):
                block = out[CH_EDGES + i * EDGE_CATEGORIES:
                            CH_EDGES + (i + 1) * EDGE_CATEGORIES, r, c]
                assert block.sum() == 1.0, f"side {i} not one-hot at ({r},{c})"
        # total edge mass conserved (16 channels x present tiles)
        np.testing.assert_allclose(
            out[CH_EDGES:CH_EDGES + EDGE_BLOCK].sum(),
            arr[CH_EDGES:CH_EDGES + EDGE_BLOCK].sum(),
        )
        # round-trip on a real board too
        rt = out
        for _ in range(3):
            rt = rotate_board_repr_90(rt)
        np.testing.assert_allclose(rt, arr, atol=0)
