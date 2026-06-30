"""Tests for the independent rollout-MCTS opponent (Ameneyro et al. 2020).

This player is Step-7 stage-1: an out-of-ecosystem ruler whose ONLY evaluation
signal is random playouts to terminal, sharing zero DNA with the v2.7/v2.9
``virtual_score`` leaf. These tests assert:
  (a) it only ever returns LEGAL actions across a fuzz of positions,
  (b) it plays a full game to terminal without error,
  (c) at a modest budget it clearly beats a uniform-random player,
  (d) it imports NONE of the v2.7/v2.9 leaf machinery.

Kept light (small n, modest sims) — CPU only, the GPU is busy elsewhere.
"""
from __future__ import annotations

import random

import numpy as np
import pytest

from carcassonne_ai.ameneyro_mcts import AmeneyroMCTSPlayer
from carcassonne_ai.game_wrapper import Game


def _engine_legal(board) -> set[int]:
    """Authoritative, OFFSET-CORRECT legal set computed straight from the engine,
    bypassing Game's legal-moves cache.

    The cache is keyed by string_representation, which collides across boards
    that differ only in window offset (a meeples-phase quirk in the vendored
    engine) — so ``game.get_valid_moves`` can return a mask encoded against the
    wrong offset. Tests must validate legality against the engine truth, not the
    (possibly poisoned) cache, otherwise a correct move looks illegal. The player
    itself uses this same uncached path internally.
    """
    from wingedsheep.carcassonne.utils.action_util import ActionUtil

    from carcassonne_ai.action_space import WindowOverflowError, encode

    out: set[int] = set()
    for action in ActionUtil.get_possible_actions(board.state):
        try:
            out.add(int(encode(action, board.offset, board.state.phase.value)))
        except WindowOverflowError:
            continue
    return out


def _play_to_terminal_collecting(player: AmeneyroMCTSPlayer, game: Game, seed: int,
                                  via_choose_action: bool) -> Game:
    """Drive `player` (controls every move) to terminal, asserting legality at
    every step against the engine-truth legal set. Returns the terminal board."""
    random.seed(seed)
    board = game.get_init_board()
    while game.get_game_ended(board, 0) == 0.0:
        legal = _engine_legal(board)
        if via_choose_action:
            mask = game.get_valid_moves(board)
            a = player.choose_action(game, board, mask)
        else:
            player.clear()
            a = player.best_action(board)
        assert a in legal, f"player returned illegal action {a} not in {sorted(legal)[:5]}..."
        board, _ = game.get_next_state(board, a)
    return board


# --- (a) legality fuzz across many positions ---------------------------------

def test_only_returns_legal_actions_across_positions() -> None:
    """Fuzz: from a spread of mid-game positions reached by random play, the
    player's choice is always in the legal mask. Covers both entry points."""
    for seed in range(6):
        game = Game(enable_legal_moves_cache=True)
        player = AmeneyroMCTSPlayer(game=game, sims=24, seed=seed)
        random.seed(seed)
        board = game.get_init_board()
        rng = random.Random(seed)
        # Walk to a random mid-game depth via random play, then probe the player.
        depth = rng.randint(0, 40)
        for _ in range(depth):
            if game.get_game_ended(board, 0) != 0.0:
                break
            mask = game.get_valid_moves(board)
            legal = np.flatnonzero(mask)
            board, _ = game.get_next_state(board, int(rng.choice(legal)))
        if game.get_game_ended(board, 0) != 0.0:
            continue
        mask = game.get_valid_moves(board)
        legal = set(np.flatnonzero(mask).tolist())
        # both contracts
        player.clear()
        a_best = player.best_action(board)
        a_choose = player.choose_action(game, board, mask)
        assert a_best in legal
        assert a_choose in legal


# --- (b) full game to terminal, no error -------------------------------------

def test_plays_full_game_to_terminal_best_action() -> None:
    game = Game(enable_legal_moves_cache=True)
    player = AmeneyroMCTSPlayer(game=game, sims=16, seed=1)
    board = _play_to_terminal_collecting(player, game, seed=1, via_choose_action=False)
    assert board.state.is_terminated()


def test_plays_full_game_to_terminal_choose_action() -> None:
    game = Game(enable_legal_moves_cache=True)
    player = AmeneyroMCTSPlayer(game=game, sims=16, seed=2)
    board = _play_to_terminal_collecting(player, game, seed=2, via_choose_action=True)
    assert board.state.is_terminated()


def test_rave_variant_plays_full_game() -> None:
    """The optional RAVE flag must also produce legal play to terminal."""
    game = Game(enable_legal_moves_cache=True)
    player = AmeneyroMCTSPlayer(game=game, sims=16, seed=3, use_rave=True)
    board = _play_to_terminal_collecting(player, game, seed=3, via_choose_action=False)
    assert board.state.is_terminated()


# --- forced-move + bad-config guards -----------------------------------------

def test_forced_move_shortcut_returns_the_only_legal_action() -> None:
    game = Game(enable_legal_moves_cache=True)
    player = AmeneyroMCTSPlayer(game=game, sims=8, seed=0)
    board = game.get_init_board()
    mask = np.zeros(game.get_action_size(), dtype=bool)
    only = int(np.flatnonzero(game.get_valid_moves(board))[0])
    mask[only] = True
    assert player.choose_action(game, board, mask) == only


def test_non_random_rollout_policy_is_rejected() -> None:
    """We must NOT silently accept a heuristic rollout (that would reintroduce
    the v2.7/v2.9 circularity this opponent exists to avoid)."""
    with pytest.raises(ValueError):
        AmeneyroMCTSPlayer(rollout_policy="greedy")


# --- (c) strength smoke vs uniform-random ------------------------------------

def _play_match(args: tuple) -> int:
    """One game: AmeneyroMCTSPlayer on `mcts_seat`, uniform-random opponent.
    Returns the score differential from the MCTS player's perspective.

    Module-level + single tuple arg so it pickles for multiprocessing.Pool
    (the project convention — cf. game_wrapper._play_one_random_game). Each game
    plays to terminal; the MCTS seat searches every one of its moves.
    """
    mcts_seat, sims, seed, use_rave = args
    game = Game(enable_legal_moves_cache=True)
    player = AmeneyroMCTSPlayer(game=game, sims=sims, seed=seed, use_rave=use_rave)
    random.seed(seed)
    board = game.get_init_board()
    rng = random.Random(seed + 7919)
    while game.get_game_ended(board, 0) == 0.0:
        cur = board.state.current_player
        if cur == mcts_seat:
            player.clear()
            a = player.best_action(board)
        else:
            legal = np.flatnonzero(game.get_valid_moves(board))
            a = int(rng.choice(legal))
        board, _ = game.get_next_state(board, a)
    s0, s1 = board.state.scores
    return (s0 - s1) if mcts_seat == 0 else (s1 - s0)


def test_beats_uniform_random_at_modest_budget() -> None:
    """Rollout MCTS should crush a uniform-random player.

    Kept CPU-light: n=8 games at sims=15, run in parallel across a Pool (each
    full game to terminal is ~30s single-threaded; the MCTS seat searches every
    move with random rollouts to terminal). The margin is large — a single game
    at sims=15 already lands ~+48 score diff — so n=8 is plenty to detect a
    miswired rollout. This is NOT a strength verdict vs the heuristic (that is a
    later orchestrated step); it only proves the rollout MCTS is wired right.
    """
    import multiprocessing as mp

    n_games = 8
    sims = 15
    args = [(i % 2, sims, 1000 + i, False) for i in range(n_games)]
    workers = min(n_games, mp.cpu_count())
    with mp.Pool(processes=workers) as pool:
        diffs = pool.map(_play_match, args)

    wins = sum(1 for d in diffs if d > 0)
    wr = wins / n_games
    mean_diff = sum(diffs) / len(diffs)
    assert wr >= 0.75, (
        f"AmeneyroMCTSPlayer(sims={sims}) won only {wins}/{n_games} ({wr:.0%}, "
        f"mean diff {mean_diff:+.1f}) vs random — expected a clear majority; "
        f"rollout MCTS may be miswired"
    )


# --- (d) zero v2.7/v2.9 DNA --------------------------------------------------

def test_imports_no_heuristic_leaf() -> None:
    """The player's evaluation must be playout-only. Assert the module (and the
    engine it instantiates) never pull in any v2.7/v2.9 leaf or a network.

    We check (1) the source text of the module names no forbidden symbol, and
    (2) that constructing + running the player does not import any leaf module
    into sys.modules as a side effect of OUR code path. (game_wrapper itself is
    leaf-free; the leaf modules are only imported lazily by HeuristicMCTS /
    NeuralMCTS / RuleBasedPlayer, none of which this player touches.)
    """
    import sys
    import carcassonne_ai.ameneyro_mcts as mod

    src = open(mod.__file__).read()
    # Allow these tokens only inside comments/docstrings; assert no executable
    # import line references them.
    forbidden = ("virtual_score", "flat_leaf", "leaf_v29", "make_v25", "compact_leaf")
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"') or stripped.startswith("'"):
            continue
        if stripped.startswith("import ") or stripped.startswith("from "):
            for f in forbidden:
                assert f not in line, f"forbidden leaf import in ameneyro_mcts.py: {line!r}"

    # Runtime: a fresh import of the player module must not have dragged in any
    # leaf module. (If something gets transitively imported here it would be a
    # regression worth catching.)
    leaf_mods = [
        "carcassonne_ai.virtual_score",
        "carcassonne_ai.virtual_score_v2",
        "carcassonne_ai.flat_leaf",
        "carcassonne_ai.leaf_v29",
        "carcassonne_ai.network",
    ]
    # Remove any already-loaded leaf modules so we can detect if OUR construction
    # re-imports them. (Other tests in the session may have loaded them; we only
    # care that AmeneyroMCTSPlayer construction+search does not.)
    saved = {m: sys.modules.pop(m, None) for m in leaf_mods}
    try:
        game = Game(enable_legal_moves_cache=True)
        p = AmeneyroMCTSPlayer(game=game, sims=8, seed=0)
        p.clear()
        p.best_action(game.get_init_board())
        leaked = [m for m in leaf_mods if m in sys.modules]
        assert not leaked, f"AmeneyroMCTSPlayer pulled in leaf modules: {leaked}"
    finally:
        # restore
        for m, v in saved.items():
            if v is not None:
                sys.modules[m] = v
