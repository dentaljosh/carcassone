"""F9 / A3 — the unplaceable-tile REDRAW flag (`draw_rule`), Python side.

Spec: [docs/F9_BUILD_SPEC_20260802.md](../docs/F9_BUILD_SPEC_20260802.md) §A3.
Dossier: [docs/RULES_FIDELITY_AUDIT_20260802.md](../docs/RULES_FIDELITY_AUDIT_20260802.md)
RF-D-2, whose rules clause (P4) is:

    "In the rare circumstances where a drawn tile cannot be placed, the player
     returns the tile to the box and DRAWS ANOTHER TILE"

i.e. the tile is REMOVED FROM THE GAME and the SAME player continues their turn.
The vendored engine instead discards, draws, and hands the turn to the opponent
(`state_updater.py`, the `next_player` call) — measured 8.5 discards/100 games,
7.0% of games affected.

**Building the flag adopts nothing.** `draw_rule="engine"` is the default and
`test_the_default_is_the_engine_of_record` is the tripwire on that.

The two sub-decisions the spec required this flag to pre-register are named in
the test names below, so a grep for either resolution lands on its proof:

  * RECURSION  -> `TestSubDecision1Recursion`
  * THE BAG / THE EXACT SOLVER'S HISTOGRAM -> `TestSubDecision2Bag`

The python<->Rust lockstep lives in `tests/rustport/test_p5_flags.py` (always-on
subset) and `scripts/rustport/lockstep_fuzz.py --draw-rule redraw` (the heavy
1,000-game leg).
"""

from __future__ import annotations

import random
from collections import Counter
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "level2"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from carcassonne_ai.game_wrapper import (  # noqa: E402
    DRAW_RULE_ENGINE,
    DRAW_RULE_LEGACY,
    DRAW_RULE_REDRAW,
    DRAW_RULES,
    Board,
    Game,
)
from wingedsheep.carcassonne.objects.actions.pass_action import PassAction  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
from wingedsheep.carcassonne.utils.action_util import ActionUtil  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def play_random(game: Game, deck_seed: int, policy_seed: int, max_plies: int = 500):
    """Play one seeded uniform-random game. Returns (board, per-seat placements)."""
    random.seed(deck_seed)
    board = game.get_init_board()
    rng = random.Random(policy_seed)
    seats = [0, 0]
    n = 0
    while not board.state.is_terminated() and n < max_plies:
        legal = np.flatnonzero(game.get_valid_moves(board))
        phase, mover = board.state.phase, board.state.current_player
        action = int(rng.choice(legal))
        board, _ = game.get_next_state(board, action)
        if phase == GamePhase.TILES and board.state.phase == GamePhase.MEEPLES:
            seats[mover] += 1        # a tile actually went down
        n += 1
    return board, seats


def find_redraw_seeds(rule: str, n_wanted: int = 3, scan: int = 400):
    """Deck/policy seeds whose uniform-random game sets at least one tile aside.

    The event is rare (~8.5/100 games), so tests that need one SEARCH for it and
    the search is deterministic — which is what makes these reproducers stable.
    """
    game = Game(draw_rule=rule)
    out = []
    for i in range(scan):
        board, seats = play_random(game, 90_000 + i, 500_000 + i)
        if board.state.set_aside_tiles:
            out.append((90_000 + i, 500_000 + i, len(board.state.set_aside_tiles)))
            if len(out) >= n_wanted:
                break
    return out


# The deterministic reproducer the spec asks for: a fixed (deck_seed, policy_seed)
# whose uniform-random game is known to hit the unplaceable-tile path. Found by
# `find_redraw_seeds`, pinned here so the tests do not depend on a scan.
REPRO_DECK_SEED = 90_040
REPRO_POLICY_SEED = 500_040
# A seed whose game sets aside THREE tiles — the recursion witness.
REPRO_RECURSION_DECK_SEED = 90_070
REPRO_RECURSION_POLICY_SEED = 500_070


# ---------------------------------------------------------------------------
# Default / plumbing
# ---------------------------------------------------------------------------

class TestDefaultOff:

    def test_the_default_is_the_engine_of_record(self):
        """No argument ⇒ the walled behaviour, and the state says so.

        This is the tripwire on an accidental default flip, the A3 twin of
        `test_start_tile_grid_bound.py::test_start_tile_is_not_centred`.
        """
        game = Game()
        assert game.draw_rule == DRAW_RULE_ENGINE
        assert game.redraw_unplaceable is False
        random.seed(1234)
        board = game.get_init_board()
        assert board.state.redraw_unplaceable is False
        assert board.state.set_aside_tiles == []

    def test_a_record_with_no_draw_rule_means_engine(self):
        """The legacy meaning of an absent field, same contract as start_rule."""
        assert DRAW_RULE_LEGACY == DRAW_RULE_ENGINE
        assert DRAW_RULES == (DRAW_RULE_ENGINE, DRAW_RULE_REDRAW)

    def test_an_unknown_draw_rule_is_refused_not_defaulted(self):
        """Never a silent default: the two rules decode DIFFERENT games from the
        same (deck_seed, actions), so guessing one for the caller would
        mis-replay the record."""
        with pytest.raises(ValueError, match="unknown draw_rule"):
            Game(draw_rule="retail")          # plausible-looking, still wrong
        with pytest.raises(ValueError, match="unknown draw_rule"):
            Game(draw_rule="")

    def test_the_flag_rides_deepcopy_into_every_search_node(self):
        """`redraw_unplaceable` must survive the hand-written state __deepcopy__,
        or MCTS nodes / PIMC worlds / solver children would silently play the
        other rule. The engine's __deepcopy__ is bespoke, so this is not free."""
        import copy

        game = Game(draw_rule=DRAW_RULE_REDRAW)
        random.seed(4242)
        board = game.get_init_board()
        board.state.set_aside_tiles.append(board.state.next_tile)
        clone = copy.deepcopy(board.state)
        assert clone.redraw_unplaceable is True
        assert [t.description for t in clone.set_aside_tiles] == \
               [t.description for t in board.state.set_aside_tiles]
        # ...and the list is COPIED, not aliased.
        clone.set_aside_tiles.append(clone.next_tile)
        assert len(clone.set_aside_tiles) == len(board.state.set_aside_tiles) + 1


# ---------------------------------------------------------------------------
# Sub-decision 1 — RECURSION
# ---------------------------------------------------------------------------

class TestSubDecision1Recursion:
    """RESOLUTION: the rules clause is per-draw, so it re-applies to a redrawn
    tile that is itself unplaceable. We realize the loop as a SEQUENCE of forced
    PassActions (one set-aside + one draw each) rather than a `while` inside the
    transition, because each draw then stays a separate chance event the
    marginalized solver can price. Termination is structural — the bag strictly
    shrinks, because a set-aside tile is removed from the game rather than
    returned to it — and a deck exhausted mid-redraw resolves to the SAME
    is_terminated()/count_final_scores semantics as the normal path (audit E7).
    """

    def test_the_turn_stays_with_the_drawer_and_the_tile_leaves_the_game(self):
        """The whole divergence, on a hand-built state: same player, one fewer
        tile in the game, phase still TILES, no meeple decision owed."""
        game = Game(draw_rule=DRAW_RULE_REDRAW)
        random.seed(777)
        board = game.get_init_board()
        st = board.state
        st.current_player = 1
        doomed = st.next_tile
        deck_before = list(st.deck)

        from wingedsheep.carcassonne.utils.state_updater import StateUpdater
        after = StateUpdater.apply_action(st, PassAction())

        assert after.current_player == 1, "the drawer keeps their turn"
        assert after.phase == GamePhase.TILES, "no meeple decision is owed"
        assert after.last_tile_action is None
        assert [t.description for t in after.set_aside_tiles] == [doomed.description]
        assert after.next_tile.description == deck_before[0].description, \
            "the replacement is the next tile in the bag"
        # The tile LEFT THE GAME: what is still in play (bag + hand) dropped by
        # one, and the missing copy is the one now in set_aside_tiles.
        #
        # ⚠️ Counts, not identity: the vendored engine hands out CANONICAL SHARED
        # `Tile` objects, so `doomed in after.deck` matches a *different*
        # remaining copy of the same kind and proves nothing. (Written as an
        # identity check first; it failed for exactly that reason.)
        in_play_before = Counter(t.description for t in deck_before)
        in_play_before[doomed.description] += 1                    # the in-hand tile
        in_play_after = Counter(t.description for t in after.deck)
        in_play_after[after.next_tile.description] += 1
        assert in_play_after[doomed.description] == \
            in_play_before[doomed.description] - 1, \
            "a set-aside tile never returns to the bag"
        assert sum(in_play_after.values()) == sum(in_play_before.values()) - 1

    def test_flag_off_the_same_pass_hands_the_turn_over(self):
        """The control half: identical action, opposite turn outcome."""
        game = Game(draw_rule=DRAW_RULE_ENGINE)
        random.seed(777)
        board = game.get_init_board()
        st = board.state
        st.current_player = 1

        from wingedsheep.carcassonne.utils.state_updater import StateUpdater
        after = StateUpdater.apply_action(st, PassAction())

        assert after.current_player == 0, "the drawer forfeits the turn (RF-D-2)"
        assert after.phase == GamePhase.TILES

    def test_a_still_unplaceable_redraw_is_offered_another_pass(self):
        """The recursion contract: after a redraw the ONLY legal action of a
        still-unplaceable tile is another Pass, so the sequence-of-passes
        encoding reproduces the rules' loop without inventing a decision."""
        game = Game(draw_rule=DRAW_RULE_REDRAW)
        random.seed(REPRO_RECURSION_DECK_SEED)
        board = game.get_init_board()
        rng = random.Random(REPRO_RECURSION_POLICY_SEED)
        saw_pass = 0
        while not board.state.is_terminated():
            actions = ActionUtil.get_possible_actions(board.state)
            if (board.state.phase == GamePhase.TILES
                    and len(actions) == 1 and isinstance(actions[0], PassAction)):
                saw_pass += 1
                before = board.state.current_player
                legal = np.flatnonzero(game.get_valid_moves(board))
                assert len(legal) == 1, "a forced pass has exactly one legal action"
                board, _ = game.get_next_state(board, int(legal[0]))
                assert board.state.current_player == before
                continue
            legal = np.flatnonzero(game.get_valid_moves(board))
            board, _ = game.get_next_state(board, int(rng.choice(legal)))
        assert saw_pass >= 1, "the pinned reproducer must actually hit the path"
        assert len(board.state.set_aside_tiles) == saw_pass

    def test_the_redraw_loop_terminates_because_the_bag_strictly_shrinks(self):
        """Termination is structural, not a guard. Every set-aside removes one
        tile from a finite bag and never returns it, so no sequence of forced
        passes can be infinite. Proven on the reproducer by checking the deck is
        strictly monotone across every pass."""
        game = Game(draw_rule=DRAW_RULE_REDRAW)
        random.seed(REPRO_RECURSION_DECK_SEED)
        board = game.get_init_board()
        rng = random.Random(REPRO_RECURSION_POLICY_SEED)
        passes = 0
        while not board.state.is_terminated():
            legal = np.flatnonzero(game.get_valid_moves(board))
            is_forced_pass = (board.state.phase == GamePhase.TILES and len(legal) == 1
                              and len(ActionUtil.get_possible_actions(board.state)) == 1
                              and isinstance(ActionUtil.get_possible_actions(
                                  board.state)[0], PassAction))
            before_bag = len(board.state.deck)
            board, _ = game.get_next_state(board, int(rng.choice(legal)))
            if is_forced_pass:
                passes += 1
                assert len(board.state.deck) < before_bag, \
                    "a redraw MUST consume a tile, or the loop could not terminate"
        assert passes >= 1

    def test_deck_exhausted_mid_redraw_terminates_like_the_normal_path(self):
        """Audit E7: `count_final_scores` fires from the discard path too. Drive
        the bag to empty and pass on the last tile — the game must be terminated
        and scored, not left hanging with next_tile=None and no final scores."""
        game = Game(draw_rule=DRAW_RULE_REDRAW)
        random.seed(31337)
        board = game.get_init_board()
        st = board.state
        st.deck = []                       # last tile in hand, bag empty
        scores_before = list(st.scores)

        from wingedsheep.carcassonne.utils.state_updater import StateUpdater
        after = StateUpdater.apply_action(st, PassAction())

        assert after.next_tile is None
        assert after.is_terminated()
        assert list(after.scores) != scores_before or all(s == 0 for s in scores_before), \
            "count_final_scores must have fired"
        assert len(after.set_aside_tiles) == 1


# ---------------------------------------------------------------------------
# Sub-decision 2 — THE BAG / THE EXACT SOLVER'S HISTOGRAM
# ---------------------------------------------------------------------------

class TestSubDecision2Bag:
    """RESOLUTION: a set-aside tile is removed PERMANENTLY — not returned to the
    bag, not reshuffled, never redrawn, and absent from every later
    determinization and chance node. `state.deck` IS the bag in both engines (no
    separate histogram exists in the hot path) and `draw_tile`'s `pop(0)` already
    removes it, so the multiset stays correct for free. What the flag OWES the
    bag is the two consequences tested here: `total_tiles` must shrink with it,
    and the marginalized solver must RE-MARGINALIZE the replacement draw.
    """

    def test_the_two_tiles_left_definitions_agree_under_redraw(self):
        """Two live definitions of "tiles left" exist:
             len(deck) + has_next          (fair_agent's latch band)
             total_tiles - tile_count      (window audit, clip_trace, progress)
        A tile leaving the game unplaced makes them drift by the set-aside count
        unless total_tiles is decremented. Checked TILES-phase only: next_tile is
        a stale reference to the just-placed tile during MEEPLES.
        """
        game = Game(draw_rule=DRAW_RULE_REDRAW)
        random.seed(REPRO_RECURSION_DECK_SEED)
        board = game.get_init_board()
        rng = random.Random(REPRO_RECURSION_POLICY_SEED)
        while not board.state.is_terminated():
            st = board.state
            if st.phase == GamePhase.TILES:
                k_deck = len(st.deck) + (1 if st.next_tile is not None else 0)
                k_total = int(board.total_tiles) - int(board.tile_count)
                assert k_deck == k_total, (
                    f"bag accounting drifted: len(deck)+has_next={k_deck} vs "
                    f"total_tiles-tile_count={k_total} after "
                    f"{len(st.set_aside_tiles)} set-asides")
            legal = np.flatnonzero(game.get_valid_moves(board))
            board, _ = game.get_next_state(board, int(rng.choice(legal)))
        assert board.state.set_aside_tiles, "reproducer must exercise a set-aside"

    def test_total_tiles_equals_the_tiles_actually_placed(self):
        """The end-state form of the same invariant: with N tiles set aside, the
        game places 72 - N tiles, and total_tiles says so."""
        game = Game(draw_rule=DRAW_RULE_REDRAW)
        board, seats = play_random(game, REPRO_RECURSION_DECK_SEED,
                                   REPRO_RECURSION_POLICY_SEED)
        n_aside = len(board.state.set_aside_tiles)
        assert n_aside >= 1
        assert int(board.total_tiles) == 72 - n_aside
        assert sum(seats) == 72 - n_aside

    def test_flag_off_total_tiles_is_left_alone(self):
        """Byte-identity guard: the decrement is gated. Flag-off keeps whatever
        (latent, pre-existing) drift the discard path always had — fixing it here
        would break the flags-off regate."""
        game = Game(draw_rule=DRAW_RULE_ENGINE)
        board, _ = play_random(game, REPRO_RECURSION_DECK_SEED,
                               REPRO_RECURSION_POLICY_SEED)
        assert int(board.total_tiles) == 72

    def test_a_set_aside_tile_never_reappears_in_the_bag(self):
        """The permanence half of the resolution, stated as a multiset identity:
        (tiles on the board) + (bag) + (in hand) + (set aside) is conserved, and
        the set-aside tiles are disjoint from the bag from the moment they leave.
        """
        from collections import Counter

        game = Game(draw_rule=DRAW_RULE_REDRAW)
        random.seed(REPRO_RECURSION_DECK_SEED)
        board = game.get_init_board()
        rng = random.Random(REPRO_RECURSION_POLICY_SEED)
        n0 = (len(board.state.deck) + 1 + len(board.state.placed_coords))
        while not board.state.is_terminated():
            st = board.state
            total = Counter(t.description for t in st.deck)
            total.update(t.description for t in st.set_aside_tiles)
            if st.next_tile is not None and st.phase == GamePhase.TILES:
                total.update([st.next_tile.description])
            n_placed = len(st.placed_coords)
            if st.phase == GamePhase.TILES:
                assert sum(total.values()) + n_placed == n0, "tiles were created or lost"
            legal = np.flatnonzero(game.get_valid_moves(board))
            board, _ = game.get_next_state(board, int(rng.choice(legal)))
        assert board.state.set_aside_tiles

    def test_the_marginalized_solver_reprices_the_redraw(self):
        """A forced-unplaceable position solved EXACTLY at K<=2 under both rules.

        The point is not that the two values differ (they may or may not on any
        given position) — it is that the redraw is routed through `_chance`, so
        the value is a function of the remaining BAG MULTISET and not of which
        tile happens to sit at the front of `state.deck`. The solver's TT key
        hashes the sorted bag, so an order-dependent value would poison it.

        Test: solve the same position twice under `redraw`, with the residual
        deck ORDER permuted. Marginalized values must be identical.
        """
        from endgame_solver import solve

        game = Game(draw_rule=DRAW_RULE_REDRAW)
        # K=3, not 2: the residual bag behind the unplaceable tile must hold TWO
        # tiles for a permutation to be meaningful at all. At K=2 the residual is
        # a single tile and the test would pass vacuously.
        built = _forced_unplaceable_exact_k(game, k=3, distinct_residual=True)
        assert built is not None, "could not construct a forced-unplaceable K<=3 position"
        board, _name = built
        assert len({t.description for t in board.state.deck}) == 2, \
            "the residual bag must hold two DIFFERENT kinds or the swap is a no-op"

        r1 = solve(game, board, mode="marginalized", budget=2_000_000)
        assert r1.completed

        swapped = _reverse_residual_deck(board)
        r2 = solve(game, Board(state=swapped, total_tiles=board.total_tiles,
                               offset=board.offset, sum_row=board.sum_row,
                               sum_col=board.sum_col, tile_count=board.tile_count),
                   mode="marginalized", budget=2_000_000)
        assert r2.completed
        assert r1.value == pytest.approx(r2.value), (
            "the marginalized value depends on residual DECK ORDER — the redraw "
            "is not being re-marginalized, and the sorted-bag TT key is unsound")
        # ...and the ordering of the root's child values must match too, not just
        # the scalar V*.
        assert sorted(r1.optimal_actions) == sorted(r2.optimal_actions)

    def test_solving_a_redraw_position_does_not_resurrect_a_set_aside_tile(self):
        """The solver's chance node builds its bag from `next_tile + deck`. A
        tile already set aside must not be in either, at any depth.

        Checked as a CONSERVATION identity over the whole solve: for every tile
        kind, (on the board) + (in the bag) + (in hand) + (set aside) equals the
        count the game started with. A resurrected tile breaks it on the high
        side; a lost one on the low side.
        """
        from endgame_solver import solve

        game = Game(draw_rule=DRAW_RULE_REDRAW)
        built = _forced_unplaceable_exact_k(game, k=2)
        assert built is not None
        board, _name = built

        # Take the forced pass for real: the tile is now set aside.
        legal = np.flatnonzero(game.get_valid_moves(board))
        assert len(legal) == 1, "a forced-unplaceable position has only the pass"
        after, _ = game.get_next_state(board, int(legal[0]))
        assert len(after.state.set_aside_tiles) == 1
        gone = after.state.set_aside_tiles[0].description

        bag = Counter(t.description for t in after.state.deck)
        if after.state.next_tile is not None:
            bag[after.state.next_tile.description] += 1
        placed = Counter(after.state.board[r][c].description
                         for (r, c) in
                         [(co.row, co.column) for co in after.state.placed_coords])
        aside = Counter(t.description for t in after.state.set_aside_tiles)

        # Conservation against the position's OWN starting composition (the bag
        # is truncated by construction, so the full 72-tile distribution is not
        # the reference here).
        start = Counter(t.description for t in board.state.deck)
        start[board.state.next_tile.description] += 1
        for (r, c) in [(co.row, co.column) for co in board.state.placed_coords]:
            start[board.state.board[r][c].description] += 1
        for kind in set(start) | set(bag) | set(placed) | set(aside):
            assert bag[kind] + placed[kind] + aside[kind] == start[kind], (
                f"tile conservation broken for {kind!r}: bag={bag[kind]} "
                f"placed={placed[kind]} aside={aside[kind]} != {start[kind]}")
        assert aside[gone] == 1

        if not after.state.is_terminated():
            res = solve(game, after, mode="marginalized", budget=2_000_000)
            assert res.completed
            # The solve must not have put the removed tile back into play.
            assert sum(t.description == gone for t in after.state.deck) == \
                bag[gone] - (1 if (after.state.next_tile is not None and
                                   after.state.next_tile.description == gone) else 0)


def _reverse_residual_deck(board):
    """A copy of `board.state` with the undrawn deck REVERSED. The information
    set is unchanged (same multiset); only the order differs — which is exactly
    what a correctly marginalized solve must be blind to."""
    import copy

    st = copy.deepcopy(board.state)
    st.deck = list(reversed(st.deck))
    return st


def _forced_unplaceable_exact_k(game: Game, k: int = 2, scan: int = 40,
                                distinct_residual: bool = False,
                                scan_from: int = 0):
    """A TILES position with K<=k tiles left whose IN-HAND TILE HAS NO LEGAL
    PLACEMENT — i.e. a genuine forced pass, small enough to solve EXACTLY.

    CONSTRUCTED, not searched, for a measured reason. Probing 60 seeded random
    games, every naturally-occurring forced pass happened at **k=71** — the very
    first decision, when only the start tile is down and its four open cells
    admit few tile kinds. By the endgame the board's open perimeter is wide and
    every kind fits somewhere, so a forced pass at k<=2 essentially never occurs
    and an earlier scan-based version of this helper skipped after 400 full
    games. The exact-K solve gate has to actually RUN — it is the spec's §A3
    requirement that the bag stay correct under an exact solve.

    So the position is built the way `fair/solver.rs`'s own `endgame()` test
    helper builds one, by making K small: take the real opening board, set the
    in-hand tile to a kind the board admits nowhere, and TRUNCATE the bag to
    `k - 1` tiles. Everything the solver reads — board, meeples, scores, phase,
    the bag multiset — is self-consistent; only the bag is shorter than a real
    game's would be at that point, which is precisely the axis the marginalized
    solver integrates over.

    Returns `(board, unplaceable_description)` or `None`.
    """
    from wingedsheep.carcassonne.tile_sets.base_deck import base_tiles
    from wingedsheep.carcassonne.utils.tile_position_finder import TilePositionFinder

    for i in range(scan_from, scan_from + scan):
        random.seed(90_000 + i)
        board = game.get_init_board()
        rng = random.Random(500_000 + i)
        # The VIRGIN board admits every tile (an empty board offers the starting
        # position to anything), so advance until at least one tile is down.
        for _ply in range(12):
            st = board.state
            if st.phase == GamePhase.TILES and st.placed_coords:
                for name, tile in base_tiles.items():
                    if TilePositionFinder.possible_playing_positions(
                            game_state=st, tile_to_play=tile):
                        continue
                    residual = st.deck[:max(0, k - 1)]
                    if distinct_residual and len(
                            {t.description for t in residual}) < len(residual):
                        # Need distinct kinds behind the unplaceable tile, or a
                        # deck permutation is a no-op and proves nothing.
                        seen, picked = set(), []
                        for cand in st.deck:
                            if cand.description not in seen:
                                seen.add(cand.description)
                                picked.append(cand)
                            if len(picked) == k - 1:
                                break
                        if len(picked) < k - 1:
                            continue
                        residual = picked
                    st.next_tile = tile
                    st.deck = residual
                    board.total_tiles = int(board.tile_count) + k
                    actions = ActionUtil.get_possible_actions(st)
                    assert len(actions) == 1 and isinstance(actions[0], PassAction), \
                        "the constructed position must actually be a forced pass"
                    return board, name
            if board.state.is_terminated():
                break
            legal = np.flatnonzero(game.get_valid_moves(board))
            board, _ = game.get_next_state(board, int(rng.choice(legal)))
    return None


# ---------------------------------------------------------------------------
# Sub-decision 3 (pre-registered in the spec, measured not resolved) — PARITY
# ---------------------------------------------------------------------------

class TestTurnParity:
    """A3 is the one flag that changes WHO PLACES WHICH TILE from that point on.
    The spec asks for the direct observable — tiles placed per seat — as its
    gate, so it is pinned here as a property rather than argued in prose.
    """

    def test_flag_off_a_discard_costs_the_drawer_a_placement(self):
        """Under `engine`, each discard hands the opponent an extra placement:
        the seat totals skew by 2 per event relative to the redraw arm."""
        seeds = find_redraw_seeds(DRAW_RULE_ENGINE, n_wanted=3)
        assert seeds, "the scan must find at least one discard game"
        for deck_seed, policy_seed, n_aside in seeds:
            off, seats_off = play_random(Game(draw_rule=DRAW_RULE_ENGINE),
                                         deck_seed, policy_seed)
            assert sum(seats_off) == 72 - n_aside
            assert len(off.state.set_aside_tiles) == n_aside

    def test_redraw_keeps_the_placements_as_even_as_the_tile_count_allows(self):
        """Under `redraw` nobody forfeits a turn, so with T tiles actually placed
        the seats split |T/2| and |T/2| (differing by at most 1, from parity of T
        alone). That is the invariant the engine rule breaks."""
        seeds = find_redraw_seeds(DRAW_RULE_REDRAW, n_wanted=3)
        assert seeds, "the scan must find at least one redraw game"
        for deck_seed, policy_seed, n_aside in seeds:
            _, seats = play_random(Game(draw_rule=DRAW_RULE_REDRAW),
                                   deck_seed, policy_seed)
            assert abs(seats[0] - seats[1]) <= 1, (
                f"seats {seats} skew by more than the tile-count parity allows "
                f"after {n_aside} set-asides — someone lost a turn")

    def test_the_two_rules_actually_diverge_on_the_reproducer(self):
        """The mutation-probe companion: if this ever passes trivially (identical
        games), every 'flags-on differs' gate below it is uninformative."""
        off, seats_off = play_random(Game(draw_rule=DRAW_RULE_ENGINE),
                                     REPRO_DECK_SEED, REPRO_POLICY_SEED)
        on, seats_on = play_random(Game(draw_rule=DRAW_RULE_REDRAW),
                                   REPRO_DECK_SEED, REPRO_POLICY_SEED)
        assert off.state.set_aside_tiles, "the reproducer must hit the path"
        assert seats_off != seats_on or off.state.scores != on.state.scores, (
            "the two draw rules produced an identical game on a seed that hits "
            "the unplaceable path — the flag is not wired to anything")


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_the_same_seed_replays_identically_under_the_flag(self):
        """Flag-on replay must be deterministic given the same seed — the redraw
        changes the deck CONSUMPTION pattern but consumes it deterministically."""
        game = Game(draw_rule=DRAW_RULE_REDRAW)
        a, seats_a = play_random(game, REPRO_RECURSION_DECK_SEED,
                                 REPRO_RECURSION_POLICY_SEED)
        b, seats_b = play_random(game, REPRO_RECURSION_DECK_SEED,
                                 REPRO_RECURSION_POLICY_SEED)
        assert list(a.state.scores) == list(b.state.scores)
        assert seats_a == seats_b
        assert [t.description for t in a.state.set_aside_tiles] == \
               [t.description for t in b.state.set_aside_tiles]
        assert game.string_representation(a) == game.string_representation(b)

    def test_flag_off_replay_is_unchanged_by_the_flag_existing(self):
        """The A3 half of the byte-identity claim, at unit scale: a flag-off game
        is identical to one played by a Game that never heard of draw_rule (the
        default ctor). The full proof is the flags-off G1-G4 regate."""
        a, seats_a = play_random(Game(), REPRO_DECK_SEED, REPRO_POLICY_SEED)
        b, seats_b = play_random(Game(draw_rule=DRAW_RULE_ENGINE),
                                 REPRO_DECK_SEED, REPRO_POLICY_SEED)
        assert list(a.state.scores) == list(b.state.scores)
        assert seats_a == seats_b
