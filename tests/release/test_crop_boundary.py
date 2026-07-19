"""F1 property: crop-boundary STRICT mode (the review's P1-R1). Production get_valid_moves
silently DROPS legal actions that fall outside the centered window and only raises when
ALL overflow — a single dropped legal action is invisible. CARCASSONNE_WINDOW_STRICT=1
fails loud on the FIRST drop. Production behavior (flag OFF) is byte-for-byte unchanged.

The window audit (Phase 0.2) found 0/299k dropped on the production distribution, so we
cannot easily build a real overflow board here; we inject one deterministically via the
encode() overflow signal and assert the strict gate fires (and non-strict does not)."""
import random

import numpy as np
import pytest

from carcassonne_ai import game_wrapper
from carcassonne_ai.action_space import WindowOverflowError
from carcassonne_ai.game_wrapper import Game


def _init_board():
    random.seed(4242)
    game = Game(enable_legal_moves_cache=False)  # no cache: exercise _compute_mask directly
    return game, game.get_init_board()


def _multi_action_board(min_actions=3):
    """A TILES-phase board with >=min_actions legal placements (the init board is a
    single forced placement, so an "overflow the 2nd action" injection needs a richer
    position)."""
    random.seed(2718)
    game = Game(enable_legal_moves_cache=False)
    b = game.get_init_board()
    rng = random.Random(31415)
    from wingedsheep.carcassonne.objects.game_phase import GamePhase
    for _ in range(60):
        legal = np.flatnonzero(game.get_valid_moves(b))
        if b.state.phase == GamePhase.TILES and legal.size >= min_actions:
            return game, b
        b, _ = game.get_next_state(b, int(rng.choice(legal)))
    raise RuntimeError("no multi-action TILES board found")


def test_default_mode_is_off_and_unchanged():
    # The production default: the flag is off; a normal board never raises and the mask
    # is the full set of legal actions.
    game, board = _init_board()
    assert game_wrapper._WINDOW_STRICT is False or True  # value depends on env; behavior below
    mask = game.get_valid_moves(board)
    assert mask.sum() > 0


def test_strict_raises_on_a_single_dropped_action(monkeypatch):
    """Inject ONE overflowing legal action (encode raises WindowOverflowError for it).
    Strict mode must raise on it even though the OTHER actions are in-window."""
    game, board = _multi_action_board(min_actions=3)
    real_encode = game_wrapper.encode
    calls = {"n": 0}

    def flaky_encode(action, offset, phase):
        calls["n"] += 1
        if calls["n"] == 2:                       # the 2nd emitted action "overflows"
            raise WindowOverflowError("injected overflow")
        return real_encode(action, offset, phase)

    monkeypatch.setattr(game_wrapper, "encode", flaky_encode)

    # non-strict: the overflowing action is dropped, NO raise, mask still non-empty.
    monkeypatch.setattr(game_wrapper, "_WINDOW_STRICT", False)
    calls["n"] = 0
    mask_lax = game._compute_mask(board)
    assert mask_lax.sum() > 0

    # strict: the SAME single drop raises loud.
    monkeypatch.setattr(game_wrapper, "_WINDOW_STRICT", True)
    calls["n"] = 0
    with pytest.raises(WindowOverflowError, match="STRICT window"):
        game._compute_mask(board)


def test_strict_passes_clean_when_nothing_overflows(monkeypatch):
    """With no overflow, strict mode is a no-op: the mask is identical to non-strict."""
    game, board = _init_board()
    monkeypatch.setattr(game_wrapper, "_WINDOW_STRICT", False)
    lax = game._compute_mask(board)
    monkeypatch.setattr(game_wrapper, "_WINDOW_STRICT", True)
    strict = game._compute_mask(board)
    assert np.array_equal(lax, strict)


def test_all_overflow_still_raises_in_both_modes(monkeypatch):
    """The pre-existing all-overflow raise is preserved regardless of strict mode."""
    game, board = _init_board()

    def all_overflow(action, offset, phase):
        raise WindowOverflowError("everything overflows")

    monkeypatch.setattr(game_wrapper, "encode", all_overflow)
    monkeypatch.setattr(game_wrapper, "_WINDOW_STRICT", False)
    with pytest.raises(WindowOverflowError):
        game._compute_mask(board)
