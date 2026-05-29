"""Tests for Path B aux-target ownership extraction + the engine farm-scoring fix.

Three contracts:
  1. `opposite_farmer_side` is a bijective involution (the 2026-05-29 fix; the
     vendored engine had TRT->BRR, making farmer adjacency asymmetric).
  2. `FarmUtil.find_farm` is start-independent: every farmer meeple in a farm
     yields the identical connected component regardless of which meeple it
     starts the flood-fill from.
  3. `extract_terminal_ownership` reconciles EXACTLY with the engine's
     `count_final_scores` — the per-feature ownership points it attributes sum to
     the engine's end-of-game additions, on a sample that exercises farms.

The engine consumes meeples at termination, so (2) and (3) stub
count_final_scores during play to keep the terminal state meeple-intact.
"""
from __future__ import annotations

import copy
import random

import numpy as np
import pytest

from carcassonne_ai.aux_targets import (
    extract_terminal_ownership,
    scores_from_records,
)
from carcassonne_ai.game_wrapper import Game
from wingedsheep.carcassonne.objects.farmer_side import FarmerSide
from wingedsheep.carcassonne.objects.meeple_type import MeepleType
from wingedsheep.carcassonne.utils.farm_util import FarmUtil
from wingedsheep.carcassonne.utils.points_collector import PointsCollector
from wingedsheep.carcassonne.utils.side_modification_util import SideModificationUtil


def test_opposite_farmer_side_is_bijective_involution():
    images = []
    for fs in FarmerSide:
        opp = SideModificationUtil.opposite_farmer_side(fs)
        images.append(opp)
        assert SideModificationUtil.opposite_farmer_side(opp) is fs, (
            f"opposite_farmer_side not an involution at {fs}: -> {opp} -> "
            f"{SideModificationUtil.opposite_farmer_side(opp)}"
        )
    assert len(set(images)) == len(list(FarmerSide)), "opposite_farmer_side not bijective"


def _play_to_terminal(game: Game, seed: int, max_plies: int = 400):
    random.seed(seed)
    board = game.get_init_board()
    plies = 0
    while game.get_game_ended(board, 0) == 0.0 and plies < max_plies:
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break
        board, _ = game.get_next_state(board, int(random.choice(legal.tolist())))
        plies += 1
    return board


def _farm_keyset(farm):
    return frozenset(
        (f.coordinate.row, f.coordinate.column, id(f.farmer_connection))
        for f in farm.farmer_connections_with_coordinate
    )


@pytest.fixture
def _stub_final_scoring():
    """Stub count_final_scores so terminal states keep their meeples."""
    orig = PointsCollector.count_final_scores
    PointsCollector.count_final_scores = classmethod(lambda cls, game_state: None)
    try:
        yield orig
    finally:
        PointsCollector.count_final_scores = orig


def test_find_farm_is_start_independent(_stub_final_scoring):
    game = Game()
    bad = 0
    for seed in range(120):
        board = _play_to_terminal(game, seed)
        if not board.state.is_terminated():
            continue
        st = board.state
        components = []
        for player in range(2):
            for mp in st.placed_meeples[player]:
                if mp.meeple_type not in (MeepleType.FARMER, MeepleType.BIG_FARMER):
                    continue
                farm = FarmUtil.find_farm_by_coordinate(
                    game_state=st, position=mp.coordinate_with_side
                )
                components.append(_farm_keyset(farm))
        for i in range(len(components)):
            for j in range(i + 1, len(components)):
                if components[i] & components[j] and components[i] != components[j]:
                    bad += 1
    assert bad == 0, f"{bad} start-dependent farm components (find_farm flood-fill bug)"


def test_ownership_planes_projection():
    from carcassonne_ai.action_space import WindowOffset
    from carcassonne_ai.aux_targets import (
        FeatureOwnership,
        OWNERSHIP_PLANES,
        ownership_planes,
    )

    off = WindowOffset(origin_row=0, origin_col=0, size=10)
    records = [
        FeatureOwnership("city", ((2, 2),), True, (0,), 4),       # player 0 owns
        FeatureOwnership("road", ((3, 3), (3, 4)), True, (1,), 2),  # player 1 owns
        FeatureOwnership("farm", ((5, 5),), False, (0, 1), 6),     # tie -> neutral
        FeatureOwnership("monastery", ((7, 7),), True, (0,), 9),   # skipped (not a plane)
    ]
    # From player 0's POV.
    planes = ownership_planes(records, off, player=0, window_size=10)
    assert planes.shape == (OWNERSHIP_PLANES, 10, 10)
    assert set(np.unique(planes).tolist()).issubset({-1.0, 0.0, 1.0})
    assert planes[0, 2, 2] == 1.0    # city: player 0 owns -> +1
    assert planes[1, 3, 3] == -1.0   # road: opponent owns -> -1
    assert planes[1, 3, 4] == -1.0
    assert planes[2, 5, 5] == 0.0    # farm tie -> neutral
    # POV flip: from player 1, signs invert.
    planes1 = ownership_planes(records, off, player=1, window_size=10)
    assert planes1[0, 2, 2] == -1.0
    assert planes1[1, 3, 3] == 1.0
    # Out-of-window coords are clipped, not errored.
    far = [FeatureOwnership("city", ((50, 50),), True, (0,), 4)]
    assert ownership_planes(far, off, 0, 10).sum() == 0.0


def test_network_forward_train_shapes():
    import torch

    from carcassonne_ai.aux_targets import OWNERSHIP_PLANES
    from carcassonne_ai.board_repr import N_CHANNELS
    from carcassonne_ai.features import N_SCALAR_FEATURES
    from carcassonne_ai.network import CarcassonneNet

    net = CarcassonneNet()
    b = torch.zeros(2, N_CHANNELS, net.window_size, net.window_size)
    s = torch.zeros(2, N_SCALAR_FEATURES)
    # forward stays a 2-tuple (inference contract unchanged).
    pol, val = net(b, s)
    assert pol.shape == (2, net.action_size) and val.shape == (2,)
    # forward_train adds ownership.
    pol2, val2, own = net.forward_train(b, s)
    assert own.shape == (2, OWNERSHIP_PLANES, net.window_size, net.window_size)
    own_d = own.detach()
    assert own_d.min().item() >= -1.0 and own_d.max().item() <= 1.0


def test_selfplay_emits_ownership():
    from carcassonne_ai.aux_targets import OWNERSHIP_PLANES
    from carcassonne_ai.selfplay import play_one_selfplay_game

    game = Game()
    A = game.get_action_size()

    def evaluator(board):
        return np.ones(A, dtype=np.float32) / A, 0.0

    ds = play_one_selfplay_game(
        game=game, evaluator=evaluator, sims=2, c_puct=1.5,
        dirichlet_alpha=0.3, dirichlet_eps=0.25, temp_threshold=15,
        seed=11, value_target="score_diff",
    )
    n = ds.boards.shape[0]
    W = game.window_size
    assert n > 0
    assert ds.ownership.shape == (n, OWNERSHIP_PLANES, W, W)
    assert set(np.unique(ds.ownership).tolist()).issubset({-1.0, 0.0, 1.0})
    assert int((ds.ownership != 0).sum()) > 0  # the game scored *some* features


def test_ownership_reconciles_with_engine(_stub_final_scoring):
    orig = _stub_final_scoring
    game = Game()
    n_terminal = 0
    farm_games = 0
    for seed in range(60):
        board = _play_to_terminal(game, seed)
        if not board.state.is_terminated():
            continue
        n_terminal += 1
        st = board.state

        pre = list(st.scores)
        records = extract_terminal_ownership(st)
        own = scores_from_records(records, st.players)
        mine = [pre[p] + own[p] for p in range(st.players)]

        truth_state = copy.deepcopy(st)
        orig(game_state=truth_state)
        truth = list(truth_state.scores)

        assert mine == truth, f"seed {seed}: ownership {mine} != engine {truth}"
        if any(r.terrain == "farm" for r in records):
            farm_games += 1

    assert n_terminal > 0, "no games reached terminal"
    assert farm_games > 0, "farm path never exercised — reconciliation is vacuous"
