"""Contract tests for the strategic-behavior motif detector.

Fast (pure helpers + one short greedy replay). Run:
  .venv/bin/python -m pytest scripts/strategic_ladder/test_motifs.py -q
"""
import os
import sys

os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import motifs as M
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.rule_based_player import RuleBasedPlayer
from wingedsheep.carcassonne.objects.game_phase import GamePhase


def test_motif_set_is_rules_correct():
    # the removed meeple-phase steal/denial must NOT be in the set (illegal in 2p base)
    assert M.MOTIFS == ("block", "avoid_feeding", "contest_merge", "farm_claim")
    assert "farm_denial" not in M.MOTIFS and "contest" not in M.MOTIFS


def test_pclose_schedule():
    assert M.pclose(0) == 1.0
    assert M.pclose(1) == 0.5
    assert M.pclose(2) == 0.2
    assert M.pclose(3) == 0.0
    # non-increasing
    vals = [M.pclose(k) for k in range(6)]
    assert all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1))


def test_phase_buckets():
    assert M.phase_of(2) == "endgame"
    assert M.phase_of(10) == "pre_endgame"
    assert M.phase_of(20) == "late_mid"
    assert M.phase_of(40) == "midgame"
    assert M.phase_of(60) == "opening"


def test_score_take_semantics():
    labs = {"farm_claim": M.MotifLabel(opportunity=True, satisfying={5, 9}, best_magnitude=6.0),
            "block": M.MotifLabel(opportunity=False)}
    assert M.score_take(labs, 5)["farm_claim"] == "took"
    assert M.score_take(labs, 7)["farm_claim"] == "missed"
    assert M.score_take(labs, 5)["block"] is None


def test_label_position_keys_and_satisfying_subset_legal():
    """Over a short greedy game: labels expose all motifs; every satisfying set is a
    subset of the legal actions; contest_merge never fires in MEEPLES phase."""
    np.random.seed(7)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    player = RuleBasedPlayer(seed=4242)
    saw_farm_claim = False
    saw_any_tiles_motif = False
    guard = 0
    while not game.get_game_ended(board, 0) and guard < 220:
        guard += 1
        mask = game.get_valid_moves(board)
        legal = set(int(i) for i in np.flatnonzero(mask))
        labels = M.label_position(game, board, sorted(legal))
        assert set(labels.keys()) == set(M.MOTIFS)
        is_tiles = board.state.phase == GamePhase.TILES
        for m, lab in labels.items():
            if not lab.opportunity:
                continue
            assert lab.satisfying, f"{m} opportunity with empty satisfying set"
            assert lab.satisfying <= legal, f"{m} satisfying not subset of legal"
            if m == "farm_claim":
                saw_farm_claim = True
                assert not is_tiles, "farm_claim is a MEEPLES motif"
            if m == "contest_merge":
                assert is_tiles, "contest_merge must be TILES-phase only"
            if m in ("block", "avoid_feeding", "contest_merge"):
                saw_any_tiles_motif = saw_any_tiles_motif or is_tiles
        a = int(player.choose_action(game, board, mask))
        board, _ = game.get_next_state(board, a)
    assert saw_farm_claim, "expected at least one farm_claim opportunity in a full game"
    assert saw_any_tiles_motif, "expected at least one TILES-phase motif opportunity"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
