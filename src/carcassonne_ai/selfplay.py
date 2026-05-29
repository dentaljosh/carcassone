"""Self-play game generation for Phase 4.

Plays one full self-play game using NeuralMCTS with AlphaZero-style
sampling: τ=1 for the first `temp_threshold` plies (exploration), then
τ→0 (greedy on visit counts). Dirichlet noise mixed into the root prior
each move.

Returns a GameDataset (same schema as warmstart) so the existing IO and
streaming-dataset machinery can be reused unchanged.

Value targets encode the game outcome from each position's current-player
POV. Two modes (see `value_target`): "score_diff" (default) = tanh(margin/15),
the same graded currency as the v2.7 heuristic leaf tanh(vs2/15); "wl" = ±1/0,
the AlphaZero-canonical win/loss target.
"""
from __future__ import annotations

import copy
from typing import Callable

import numpy as np

from .action_space import action_size as compute_action_size
from .aux_targets import (
    OWNERSHIP_PLANES,
    extract_terminal_ownership,
    ownership_planes,
)
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
    value_target: str = "score_diff",
    anchor_evaluator: Callable[[object], tuple[np.ndarray, float]] | None = None,
    anchor_batch_evaluator: Callable[[list], tuple[np.ndarray, np.ndarray]] | None = None,
    learner_player_idx: int = 0,
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
      value_target: how to encode the per-position outcome target.
                    "score_diff" (default) → tanh((p0-p1)/15), the graded
                    margin in the same currency as the v2.7 heuristic leaf
                    (Option 2, DECISIONS 2026-05-17 — lets a value head
                    blended into the leaf predict the same quantity).
                    "wl" → ±1/0, the AlphaZero-canonical win/loss target.
      anchor_evaluator: if set, switches to anchor-fraction mode — the
                       learner (using `evaluator`) plays as
                       `learner_player_idx`; the anchor (using
                       `anchor_evaluator`) plays the other side.
                       Only the learner's moves are recorded; the anchor's
                       moves are played but never saved (their value targets
                       would teach the learner the anchor's policy).
                       The anchor's MCTS runs with no Dirichlet noise and
                       τ=0 always — it's meant to be a strong static
                       opponent, not an exploring agent.
      anchor_batch_evaluator: optional GPU-batched evaluator for the anchor
                              side, mirroring `batch_evaluator`.
      learner_player_idx: 0 or 1 — which player the learner takes when
                          anchor_evaluator is set. Ignored otherwise.

    Returns:
      GameDataset with N rows: in standard self-play N = total plies; in
      anchor-fraction mode N = plies where the learner moved (~½ of total).
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
    learner_mcts = NeuralMCTS(
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

    # Anchor-fraction mode: a second MCTS for the fixed opponent. No Dirichlet
    # noise — the anchor is meant to play its strongest line, not explore.
    # learner_player_idx is ignored if anchor_evaluator is None.
    if anchor_evaluator is not None:
        if learner_player_idx not in (0, 1):
            raise ValueError(
                f"learner_player_idx must be 0 or 1, got {learner_player_idx}"
            )
        anchor_mcts: NeuralMCTS | None = NeuralMCTS(
            game=game,
            evaluator=anchor_evaluator,
            simulations=sims,
            c_puct=c_puct,
            seed=seed ^ 0xDEADBEEF,
            dirichlet_alpha=0.0,
            dirichlet_eps=0.0,
            batch_size=batch_size,
            batch_evaluator=anchor_batch_evaluator,
            virtual_loss=virtual_loss,
        )
    else:
        anchor_mcts = None

    boards_arr: list[np.ndarray] = []
    scalars_arr: list[np.ndarray] = []
    policies_arr: list[np.ndarray] = []
    masks_arr: list[np.ndarray] = []
    players_arr: list[int] = []  # current_player at each ply, for value sign
    offsets_arr: list = []  # board.offset per recorded ply, for ownership projection

    # Track the pre-terminal board + the terminating action so we can rebuild a
    # meeple-intact terminal state for the ownership aux labels. (We can't read
    # ownership off the final board: the engine's count_final_scores consumes the
    # meeples at termination. And we can't stub count_final_scores during play —
    # the v2.7 leaf eval calls it on every MCTS leaf. So we re-apply just the last
    # action to a copy with scoring stubbed for that single call.)
    prev_board = board
    last_action: int | None = None

    ply = 0
    while game.get_game_ended(board, 0) == 0.0 and ply < max_plies:
        cur_player = board.state.current_player
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            break

        # Route by player when in anchor-fraction mode; otherwise the learner
        # plays both sides as in standard self-play.
        is_learner_move = (anchor_mcts is None) or (cur_player == learner_player_idx)
        mcts = learner_mcts if is_learner_move else anchor_mcts

        # Snapshot the canonical board encoding from the current player's POV.
        # (Only used if we actually record this move.)
        if is_learner_move:
            obs, scalars = game.get_canonical_form(board, cur_player)

        # Run MCTS, build policy target from visit counts.
        mcts.clear()
        mcts.search(board)

        if is_learner_move:
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

        # Pick the action. Anchor side always plays τ=0 (strongest line, no
        # sampling) — only the learner explores via the τ schedule.
        if is_learner_move:
            temperature = 1.0 if ply < temp_threshold else 0.0
        else:
            temperature = 0.0
        action = mcts.select_for_training(board, temperature=temperature)

        if is_learner_move:
            boards_arr.append(obs.astype(np.float32))
            scalars_arr.append(scalars.astype(np.float32))
            policies_arr.append(policy)
            masks_arr.append(mask.astype(bool))
            players_arr.append(cur_player)
            offsets_arr.append(board.offset)

        prev_board = board
        last_action = int(action)
        board, _ = game.get_next_state(board, action)
        ply += 1

    # Backfill value targets from the final outcome, sign-flipped per ply so
    # each position sees its own current-player's result. `z_p0` is player 0's
    # target:
    #   "score_diff" → tanh((p0 - p1) / 15): the graded margin, same scale and
    #                  currency as the v2.7 heuristic leaf tanh(vs2/15). A value
    #                  head trained on this predicts a *margin*, so blending it
    #                  into the leaf (Option 2) interpolates like-for-like.
    #   "wl"         → sign(p0 - p1) ∈ {-1, 0, +1}: AlphaZero-canonical W/L.
    # The loop can also exit via the max_plies cap or the no-legal-moves break;
    # in both cases the game did NOT finish, so board.state.scores is mid-game
    # and the value targets below would be silently wrong. Fail loudly — a
    # corrupt game record poisons training worse than a lost game does.
    if game.get_game_ended(board, 0) == 0.0:
        raise RuntimeError(
            f"self-play game did not terminate (ply={ply}, max_plies={max_plies})"
            f" — refusing to emit a dataset with mid-game value targets"
        )
    p0_score = int(board.state.scores[0])
    p1_score = int(board.state.scores[1])
    if value_target == "score_diff":
        z_p0 = float(np.tanh((p0_score - p1_score) / 15.0))
    elif value_target == "wl":
        z_p0 = float(np.sign(p0_score - p1_score))
    else:
        raise ValueError(
            f"value_target must be 'score_diff' or 'wl', got {value_target!r}"
        )
    values_arr = np.array(
        [z_p0 if p == 0 else -z_p0 for p in players_arr], dtype=np.float32
    )

    W = game.window_size
    if not boards_arr:
        # Edge case: game terminated before any plies were recorded.
        return GameDataset(
            boards=np.empty((0, 0, 0, 0), dtype=np.float32),
            scalars=np.empty((0, 0), dtype=np.float32),
            policies=np.empty((0, A), dtype=np.float32),
            values=np.empty((0,), dtype=np.float32),
            valid_masks=np.empty((0, A), dtype=bool),
            ownership=np.empty((0, OWNERSHIP_PLANES, W, W), dtype=np.float32),
        )

    # Ownership aux labels = the FINAL feature ownership, projected onto each
    # recorded position's window + POV (every position predicts the game's
    # outcome, like the value target). Rebuild a meeple-intact terminal state by
    # re-applying the terminating action with count_final_scores stubbed for that
    # one call (see the note where prev_board is declared).
    from wingedsheep.carcassonne.utils.points_collector import PointsCollector

    term_board = copy.deepcopy(prev_board)
    _orig_cfs = PointsCollector.count_final_scores
    PointsCollector.count_final_scores = classmethod(lambda cls, game_state: None)
    try:
        game.apply_action_inplace(term_board, last_action)
    finally:
        PointsCollector.count_final_scores = _orig_cfs
    if not term_board.state.is_terminated():
        raise RuntimeError(
            "ownership-label reconstruction did not reach a terminal state "
            f"(ply={ply}) — refusing to emit mislabeled ownership targets"
        )
    records = extract_terminal_ownership(term_board.state)
    ownership_arr = np.stack(
        [
            ownership_planes(records, offsets_arr[i], players_arr[i], W)
            for i in range(len(boards_arr))
        ]
    )

    return GameDataset(
        boards=np.stack(boards_arr),
        scalars=np.stack(scalars_arr),
        policies=np.stack(policies_arr),
        values=values_arr,
        valid_masks=np.stack(masks_arr),
        ownership=ownership_arr,
    )
