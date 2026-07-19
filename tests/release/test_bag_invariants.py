"""F1 property: current-tile / bag / score invariants hold at EVERY ply. Counts stay
in-range, nothing goes negative, scores never decrease, the deck only shrinks. A break
here means the engine state the leaf/search read is internally inconsistent."""
import random

import numpy as np

from carcassonne_ai.game_wrapper import Game


def _plies(seed, limit=400):
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    b = game.get_init_board()
    rng = random.Random(seed ^ 0xBEEF)
    n = 0
    yield game, b
    while game.get_game_ended(b, 0) == 0.0 and n < limit:
        legal = np.flatnonzero(game.get_valid_moves(b))
        b, _ = game.get_next_state(b, int(rng.choice(legal)))
        n += 1
        yield game, b


def test_meeple_hand_counts_in_range():
    for seed in (11, 22, 33):
        for game, b in _plies(seed):
            st = b.state
            for p in range(st.players):
                assert 0 <= st.meeples[p] <= 7, \
                    f"seed {seed}: player {p} has {st.meeples[p]} meeples in hand (expect 0..7)"


def test_scores_nonnegative_and_monotone():
    for seed in (11, 22, 33):
        prev = None
        for game, b in _plies(seed):
            s = list(b.state.scores)
            assert all(x >= 0 for x in s), f"negative score {s}"
            if prev is not None:
                assert all(c >= p for c, p in zip(s, prev)), \
                    f"seed {seed}: score decreased {prev} -> {s} (Carcassonne scores only rise)"
            prev = s


def test_deck_shrinks_and_tiles_conserve():
    for seed in (11, 22, 33):
        prev_deck = None
        prev_placed = None
        for game, b in _plies(seed):
            st = b.state
            deck_len = len(st.deck)
            placed = len(st.placed_coords)
            if prev_deck is not None:
                assert deck_len <= prev_deck, f"deck grew {prev_deck} -> {deck_len}"
                assert placed >= prev_placed, f"placed tiles decreased {prev_placed} -> {placed}"
            # total placed never exceeds the board's tile budget.
            assert placed <= b.total_tiles, f"placed {placed} > total_tiles {b.total_tiles}"
            prev_deck, prev_placed = deck_len, placed


def test_tiles_phase_has_a_tile_and_legal_moves():
    from wingedsheep.carcassonne.objects.game_phase import GamePhase
    for seed in (11, 22):
        for game, b in _plies(seed):
            st = b.state
            if game.get_game_ended(b, 0) != 0.0:
                continue
            if st.phase == GamePhase.TILES:
                assert st.next_tile is not None, "TILES phase with no tile in hand"
            mask = game.get_valid_moves(b)
            assert mask.sum() > 0, "a non-terminal position with no legal move"


def test_current_player_is_valid():
    for seed in (11, 22, 33):
        for game, b in _plies(seed):
            assert b.state.current_player in (0, 1)
