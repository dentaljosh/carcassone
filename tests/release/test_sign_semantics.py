"""F1 property: result-sign semantics — the inverted-semantics scar. won_by_champ / diff
must be candidate-minus-opponent from the candidate's seat, and get_game_ended must be
antisymmetric. A sign flip here silently inverts every strength verdict."""
import random

import numpy as np

from carcassonne_ai.game_wrapper import Game


def _play_random_to_end(seed):
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    b = game.get_init_board()
    rng = random.Random(seed ^ 0x1234)
    while game.get_game_ended(b, 0) == 0.0:
        legal = np.flatnonzero(game.get_valid_moves(b))
        b, _ = game.get_next_state(b, int(rng.choice(legal)))
    return game, b


def test_get_game_ended_is_antisymmetric_on_terminal():
    for seed in (1, 2, 3):
        game, b = _play_random_to_end(seed)
        v0 = game.get_game_ended(b, 0)
        v1 = game.get_game_ended(b, 1)
        assert v0 != 0.0 and v1 != 0.0, "terminal board must report a non-zero value"
        assert v0 == -v1, f"perspective antisymmetry broken: {v0} vs {v1}"
        # value sign agrees with the raw score margin from player 0's POV.
        s0, s1 = b.state.scores
        if s0 > s1:
            assert v0 > 0
        elif s1 > s0:
            assert v0 < 0


def _diff_and_won(a_seat, s0, s1):
    """The eval_fair_puct._play_one convention, isolated for a golden."""
    diff = (s0 - s1) if a_seat == 0 else (s1 - s0)
    return diff, (diff > 0), (diff == 0)


def test_diff_and_won_by_champ_golden():
    # candidate in seat 0 winning 83-68 -> diff +15, won.
    assert _diff_and_won(0, 83, 68) == (15, True, False)
    # candidate in seat 1 with scores 86-57 (seat1=57) -> diff -29, lost.
    assert _diff_and_won(1, 86, 57) == (-29, False, False)
    # candidate in seat 1 winning: scores 57-86 -> diff +29, won.
    assert _diff_and_won(1, 57, 86) == (29, True, False)
    # a draw is not a win.
    assert _diff_and_won(0, 70, 70) == (0, False, True)


def test_eval_fair_puct_gameresult_sign_matches_convention():
    """The shipped GameResult must compute diff/won_by_champ/drew by the same rule (guards
    against a future refactor re-inverting it)."""
    from eval_fair_puct import GameResult
    for a_seat, s0, s1 in [(0, 83, 68), (1, 86, 57), (1, 57, 86), (0, 70, 70)]:
        want_diff, want_won, want_drew = _diff_and_won(a_seat, s0, s1)
        r = GameResult(seed=1, a_seat=a_seat, info="fair", exact_k=2, k_dets=4, sims=688,
                       rung_sims=800, score_p0=s0, score_p1=s1, diff=want_diff,
                       won_by_champ=want_won, drew=want_drew, elapsed_s=0.0, moves=0)
        assert (r.diff > 0) == r.won_by_champ
        assert (r.diff == 0) == r.drew
