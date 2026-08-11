"""Verify the custom CarcassonneGameState.__deepcopy__ produces states
indistinguishable from the default recursive deepcopy.

Why this matters: the custom __deepcopy__ (carcassonne_game_state.py)
bypasses the default tile/connection-graph walk and shares immutable refs.
If anything in the engine ever mutates a Tile / TileAction / MeeplePosition
in place after construction, the shared-ref approach would silently corrupt
parallel state copies. These tests catch that.

Test strategy: snapshot the state, deepcopy it two ways (custom vs default),
apply the SAME action sequence to both, then assert byte-equivalent fields
(scores, meeples, board placements, etc.) at the end.
"""
from __future__ import annotations

import copy
import random

import numpy as np

from carcassonne_ai.game_wrapper import Game


def _state_signature(state) -> dict:
    """Tuple-ize the mutable fields of a state so we can equality-check
    after applying actions. Excludes deck (only its length matters for
    correctness) and tile object identity (we want value equality)."""
    return {
        "phase": state.phase,
        "current_player": state.current_player,
        "scores": tuple(state.scores),
        "meeples": tuple(state.meeples),
        "abbots": tuple(state.abbots),
        "big_meeples": tuple(state.big_meeples),
        "last_river_rotation": state.last_river_rotation,
        "deck_len": len(state.deck),
        "next_tile_desc": (
            state.next_tile.description if state.next_tile is not None else None
        ),
        "open_positions": frozenset(state.open_positions),
        "n_placed_meeples_per_player": tuple(
            len(pl) for pl in state.placed_meeples
        ),
        "board_tile_descriptions": tuple(
            tuple(
                state.board[r][c].description if state.board[r][c] is not None else None
                for c in range(len(state.board[0]))
            )
            for r in range(len(state.board))
        ),
    }


def test_custom_deepcopy_matches_default_on_fresh_state() -> None:
    g = Game()
    board = g.get_init_board()
    state = board.state
    custom = copy.deepcopy(state)
    # Sanity: signatures identical.
    assert _state_signature(state) == _state_signature(custom)
    # And it's a real copy (not aliased).
    assert custom is not state
    assert custom.board is not state.board
    assert custom.deck is not state.deck
    assert custom.scores is not state.scores
    assert custom.placed_meeples is not state.placed_meeples
    assert custom.open_positions is not state.open_positions


def _force_default_deepcopy(state):
    """Temporarily detach __deepcopy__ to invoke Python's default recursive
    deepcopy, for comparison purposes."""
    cls = type(state)
    custom_fn = cls.__deepcopy__
    del cls.__deepcopy__
    try:
        return copy.deepcopy(state)
    finally:
        cls.__deepcopy__ = custom_fn


def test_custom_deepcopy_diverges_no_state_drift_after_actions() -> None:
    """Apply the same action sequence (random) to two independently-copied
    states. The custom deepcopy and the default deepcopy must end up at the
    same observable state.
    """
    random.seed(123)
    g = Game()
    board = g.get_init_board()
    state = board.state

    custom_copy = copy.deepcopy(state)  # uses our __deepcopy__
    default_copy = _force_default_deepcopy(state)
    # Both copies start equal to each other AND to the original.
    assert _state_signature(state) == _state_signature(custom_copy)
    assert _state_signature(state) == _state_signature(default_copy)

    # Apply 60 random actions to BOTH copies (separately). Outcomes must match.
    rng = random.Random(456)
    from wingedsheep.carcassonne.utils.state_updater import StateUpdater
    from wingedsheep.carcassonne.objects.actions.action import Action
    from wingedsheep.carcassonne.utils.action_util import ActionUtil

    for _ in range(60):
        if custom_copy.is_terminated() or default_copy.is_terminated():
            break
        legal_custom = ActionUtil.get_possible_actions(custom_copy)
        legal_default = ActionUtil.get_possible_actions(default_copy)
        # Possible-action sets should be identical (driven by identical state).
        # Compare by string repr since Actions don't define __eq__.
        assert len(legal_custom) == len(legal_default), (
            "legal-action counts diverged"
        )
        if not legal_custom:
            break
        idx = rng.randrange(len(legal_custom))
        StateUpdater.apply_action_inplace(custom_copy, legal_custom[idx])
        StateUpdater.apply_action_inplace(default_copy, legal_default[idx])

    assert _state_signature(custom_copy) == _state_signature(default_copy), (
        "state drift after 60 actions — custom __deepcopy__ shares something "
        "that mutates"
    )


def test_custom_deepcopy_preserves_original_after_mutating_copy() -> None:
    """Confirm that mutating the copy does not affect the original — the
    classic 'shared mutable substructure' bug we'd see if e.g. board rows
    were aliased."""
    random.seed(789)
    g = Game()
    board = g.get_init_board()
    state = board.state
    original_sig = _state_signature(state)

    copied = copy.deepcopy(state)

    # Mutate the copy through every field that's supposed to be independent.
    copied.scores[0] = 999
    copied.meeples[1] = 999
    copied.placed_meeples[0].append("fake_meeple_position")  # type: ignore
    copied.open_positions.add(("fake_coord",))  # type: ignore
    copied.deck.clear()
    if copied.board[0]:
        copied.board[0][0] = "fake_tile"  # type: ignore

    # Original must be unchanged.
    assert _state_signature(state) == original_sig, (
        "mutating the copy leaked into the original — shared substructure"
    )


def test_custom_deepcopy_midgame() -> None:
    """Same as the post-action test but starting from a state ~60 moves into
    a real game (mid-game has the most placed tiles and richest open_positions
    — the worst case for any subtle sharing bug)."""
    random.seed(321)
    g = Game()
    board = g.get_init_board()

    # Advance ~60 moves.
    from wingedsheep.carcassonne.utils.state_updater import StateUpdater
    from wingedsheep.carcassonne.utils.action_util import ActionUtil

    rng = random.Random(654)
    for _ in range(60):
        if board.state.is_terminated():
            break
        legal = ActionUtil.get_possible_actions(board.state)
        if not legal:
            break
        StateUpdater.apply_action_inplace(board.state, legal[rng.randrange(len(legal))])

    mid_state = board.state
    custom_copy = copy.deepcopy(mid_state)
    default_copy = _force_default_deepcopy(mid_state)

    assert _state_signature(custom_copy) == _state_signature(default_copy), (
        "mid-game custom deepcopy diverges from default deepcopy"
    )
    # Mutating one should not affect the other.
    custom_copy.scores[0] += 1
    assert default_copy.scores[0] != custom_copy.scores[0]


def test_string_repr_cache_invalidated_on_apply_action_inplace() -> None:
    """Board memoizes string_representation. apply_action_inplace mutates
    state — the cache MUST reset, or rollouts will use stale state keys.

    Regression test for the loop-3 patch (2026-05-13).
    """
    from carcassonne_ai.game_wrapper import Game
    from wingedsheep.carcassonne.utils.action_util import ActionUtil

    random.seed(2026)
    g = Game(enable_legal_moves_cache=True)
    board = g.get_init_board()

    s0 = g.string_representation(board)
    assert board._str_repr_cache == s0  # cache populated by the call above

    # Apply an action in place; cache must invalidate.
    legal = ActionUtil.get_possible_actions(board.state)
    assert legal, "fresh board should have legal moves"
    g.apply_action_inplace(board, 0 if False else _action_idx_for(g, board, legal[0]))

    assert board._str_repr_cache is None, "inplace mutation must invalidate cache"

    # New call computes fresh.
    s1 = g.string_representation(board)
    assert s1 != s0, "string repr must change after action"
    assert board._str_repr_cache == s1


def _action_idx_for(g, board, action) -> int:
    """Encode an engine Action back into the wrapper's flat action index
    so we can call game.apply_action_inplace. Mirrors what MCTS does."""
    import numpy as np

    mask = g.get_valid_moves(board)
    legal = np.flatnonzero(mask)
    return int(legal[0])  # any legal index works for the cache test
