"""Hash collision check for string_representation."""
from __future__ import annotations

import os
import random
from multiprocessing import Pool

import numpy as np

from carcassonne_ai.game_wrapper import Game


def _walk_one_game(seed: int) -> tuple[set[str], int, str | None]:
    """Play one random game collecting all string_representations.
    Returns (set_of_reprs, n_moves, error_or_None).
    A within-game collision is an error (every move changes something)."""
    g = Game()
    random.seed(seed)
    board = g.get_init_board()
    seen: set[str] = set()
    moves = 0
    while g.get_game_ended(board, 0) == 0.0:
        sig = g.string_representation(board)
        if sig in seen:
            return seen, moves, f"seed {seed} move {moves}: within-game repr collision"
        seen.add(sig)
        mask = g.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        board, _ = g.get_next_state(board, int(random.choice(legal)))
        moves += 1
    return seen, moves, None


def test_no_collisions_within_a_single_game_progression() -> None:
    """Within one game every state must be unique (something changes each step).
    Therefore the set of repr strings collected during a game equals the move
    count. A collision means two truly-distinct states hashed to the same
    repr — a hash logic bug.
    """
    workers = min(os.cpu_count() or 1, 20)
    with Pool(processes=workers) as pool:
        results = pool.map(_walk_one_game, range(20))
    for seen, moves, err in results:
        assert err is None, err
        assert len(seen) == moves


def test_shielded_and_unshielded_tile_produce_distinct_signatures() -> None:
    """The vendored engine has had at least one description-collision bug:
    `city_diagonal_top_left_road` and `city_diagonal_top_left_shield_road`
    shared the same description string. We patched the engine, but the
    rotation signature also pins shield/chapel/flowers as defense in depth.
    This test asserts that signature distinction directly so any future
    upstream collision is caught loudly.
    """
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles
    from carcassonne_ai.game_wrapper import _tile_rotation_signature

    shielded = base_tiles["city_diagonal_top_left_shield_road"]
    plain = base_tiles["city_diagonal_top_left_road"]
    assert shielded.shield is True
    assert plain.shield is False
    assert _tile_rotation_signature(shielded) != _tile_rotation_signature(plain)


def test_repr_is_deterministic_for_the_same_state() -> None:
    g = Game()
    board = g.get_init_board()
    s1 = g.string_representation(board)
    s2 = g.string_representation(board)
    assert s1 == s2


def test_repr_diversity_across_random_play() -> None:
    """30 games (parallelized) should produce thousands of distinct
    representations, demonstrating the hash isn't pathologically collapsing.
    """
    workers = min(os.cpu_count() or 1, 30)
    with Pool(processes=workers) as pool:
        results = pool.map(_walk_one_game, range(30))
    union: set[str] = set()
    for seen, _moves, err in results:
        assert err is None, err
        union |= seen
    assert len(union) > 2000, f"expected >2000 distinct reprs, got {len(union)}"
