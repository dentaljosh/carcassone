"""Self-play game generation for Phase 4.

Plays one full self-play game using NeuralMCTS with AlphaZero-style
sampling: τ=1 for the first `temp_threshold` plies (exploration), then
τ→0 (greedy on visit counts). Dirichlet noise mixed into the root prior
each move.

Returns a GameDataset (same schema as warmstart) so the existing IO and
streaming-dataset machinery can be reused unchanged.

Value targets are the actual game outcome z ∈ {-1, 0, +1}, sign-flipped
per position by which player was to move at that position.
"""
from __future__ import annotations

from typing import Callable

import numpy as np

from .action_space import action_size as compute_action_size
from .game_wrapper import Game
from .mcts import NeuralMCTS
from .warmstart import GameDataset


def play_one_selfplay_game(
    *,
    game: Game,
    evaluator: Callable[[object], tuple[np.ndarray, float]],
    sims: int,
    c_puct: float,
    dirichlet_alpha: float,
    dirichlet_eps: float,
    temp_threshold: int,
    seed: int,
    max_plies: int = 400,
    batch_size: int = 1,
    batch_evaluator: Callable[[list], tuple[np.ndarray, np.ndarray]] | None = None,
    virtual_loss: float = 1.0,
) -> GameDataset:
    """Play one self-play game; emit a GameDataset of all positions.

    For each ply:
      - Run NeuralMCTS (with root Dirichlet noise) for `sims` simulations.
      - Build policy target = root visit distribution / total visits.
      - Pick the action via select_for_training(τ): τ=1 if ply < threshold,
        else τ=0.
      - Snapshot (canonical board, scalars, mask, policy_target, current_player).
    After the game ends, backfill value_target = z, sign-flipped per ply
    so each position sees its current player's outcome.

    Args:
      game: a Game instance (legal-moves cache enabled).
      evaluator: NeuralMCTS evaluator — Callable[[Board], (priors, value)].
      sims: NeuralMCTS simulation budget per move.
      c_puct: PUCT exploration constant.
      dirichlet_alpha: root Dirichlet α (pass 0 to disable noise; should
                       be > 0 for self-play).
      dirichlet_eps: prior-mixing weight ε (pass 0 to disable; default 0.25
                     in caller).
      temp_threshold: plies < this use τ=1 (sample); plies ≥ this use τ=0
                      (argmax visits).
      seed: RNG seed for the engine + MCTS sampler. Same seed → same game.
      max_plies: hard upper bound to defend against any infinite-loop bug.
                 Carcassonne games are at most ~200 plies in our scope.
      batch_size: NeuralMCTS batch size for virtual-loss / batched-eval
                  mode. 1 = serial (default; matches earlier behavior).
                  >1 = collect K leaves per sim batch and evaluate them in
                  one network call (~2-4× per-game speedup when GPU is
                  the bottleneck).
      batch_evaluator: GPU-batched evaluator. Required for batched mode to
                       actually save GPU time; if None and batch_size>1,
                       falls back to per-board calls of `evaluator` (still
                       gets vloss diversification but no GPU batching).
      virtual_loss: PUCT W-penalty applied to in-flight nodes during batch
                    selection. Default 1.0 (works for unit-clamped values
                    in [-1, +1]).

    Returns:
      GameDataset with N rows where N = number of plies in the game.
    """
    import random as _random

    # Engine deck shuffle uses the global random module — must seed it.
    _random.seed(seed)

    board = game.get_init_board()
    A = compute_action_size(game.window_size)

    # NeuralMCTS reuses the same Game instance; tree is cleared per move
    # since the next root is a new state and the search semantics are
    # cleaner without stale subtree mass. (Same pattern as the warmstart
    # MCTS labeling path.) clear() also frees the legal-moves cache.
    mcts = NeuralMCTS(
        game=game,
        evaluator=evaluator,
        simulations=sims,
        c_puct=c_puct,
        seed=seed,
        dirichlet_alpha=dirichlet_alpha,
        dirichlet_eps=dirichlet_eps,
        batch_size=batch_size,
        batch_evaluator=batch_evaluator,
        virtual_loss=virtual_loss,
    )

    boards_arr: list[np.ndarray] = []
    scalars_arr: list[np.ndarray] = []
    policies_arr: list[np.ndarray] = []
    masks_arr: list[np.ndarray] = []
    players_arr: list[int] = []  # current_player at each ply, for value sign

    ply = 0
    while game.get_game_ended(board, 0) == 0.0 and ply < max_plies:
        cur_player = board.state.current_player
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break

        # Snapshot the canonical board encoding from the current player's POV.
        obs, scalars = game.get_canonical_form(board, cur_player)

        # Run MCTS, build policy target from visit counts.
        mcts.clear()
        mcts.search(board)
        counts, actions = mcts.root_visit_distribution(board)
        policy = np.zeros(A, dtype=np.float32)
        # Defensive: intersect MCTS-produced visits with the snapshot mask
        # before normalizing. In rare cases NeuralMCTS produces a visit on
        # an action the outer `get_valid_moves(board)` call doesn't include
        # (most likely a stale legal-moves-cache entry from a prior search;
        # not yet root-caused). Without this clip, the trainer's policy-CE
        # validator (which checks "no mass on masked-off actions") aborts
        # the run. Dropping such visits is correct: the snapshot mask is
        # the contract for legality at this position. If everything got
        # filtered we fall back to uniform-over-legal.
        kept = 0.0
        if counts.sum() > 0:
            for a, c in zip(actions, counts):
                ai = int(a)
                if mask[ai]:
                    policy[ai] = float(c)
                    kept += float(c)
        if kept > 0:
            policy /= kept
        else:
            policy[legal] = 1.0 / legal.size

        # Pick the action.
        temperature = 1.0 if ply < temp_threshold else 0.0
        action = mcts.select_for_training(board, temperature=temperature)

        boards_arr.append(obs.astype(np.float32))
        scalars_arr.append(scalars.astype(np.float32))
        policies_arr.append(policy)
        masks_arr.append(mask.astype(bool))
        players_arr.append(cur_player)

        board, _ = game.get_next_state(board, action)
        ply += 1

    # Backfill value targets from the final outcome.
    # game.get_game_ended returns tanh((scores[player] - scores[opp]) / 15).
    # For self-play training we want raw z ∈ {-1, 0, +1}: sign of the score
    # diff at game end.
    p0_score = int(board.state.scores[0])
    p1_score = int(board.state.scores[1])
    if p0_score > p1_score:
        z_p0 = 1.0
    elif p0_score < p1_score:
        z_p0 = -1.0
    else:
        z_p0 = 0.0
    values_arr = np.array(
        [z_p0 if p == 0 else -z_p0 for p in players_arr], dtype=np.float32
    )

    if not boards_arr:
        # Edge case: game terminated before any plies were recorded.
        return GameDataset(
            boards=np.empty((0, 0, 0, 0), dtype=np.float32),
            scalars=np.empty((0, 0), dtype=np.float32),
            policies=np.empty((0, A), dtype=np.float32),
            values=np.empty((0,), dtype=np.float32),
            valid_masks=np.empty((0, A), dtype=bool),
        )

    return GameDataset(
        boards=np.stack(boards_arr),
        scalars=np.stack(scalars_arr),
        policies=np.stack(policies_arr),
        values=values_arr,
        valid_masks=np.stack(masks_arr),
    )
