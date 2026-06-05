"""Self-play game generation for Phase 4.

Plays one full self-play game using NeuralMCTS with AlphaZero-style
sampling: τ=1 for the first `temp_threshold` plies (exploration), then
τ→0 (greedy on visit counts). Dirichlet noise mixed into the root prior
each move.

Returns a GameDataset (same schema as warmstart) so the existing IO and
streaming-dataset machinery can be reused unchanged.

Value targets encode each position's value from its current-player POV. Modes
(see `value_target`): "score_diff" (default) = tanh(outcome margin/15), the same
graded currency as the v2.7 heuristic leaf tanh(vs2/15); "score_diff_wide" =
tanh(margin/40) (C6 de-saturated); "wl" = ±1/0, the AlphaZero-canonical win/loss
target; "search_value" = the per-position MCTS root.Q (the overfitting fix,
DECISIONS 2026-06-04 — ~100× more independent value labels than one-per-game z).
"""
from __future__ import annotations

import copy
import os
import time
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


def _v27_leaf_value(state, player: int) -> float:
    """v2.7 heuristic leaf value at `state` from `player`'s POV, in [-1, 1] —
    `tanh(virtual_score_v2(state, player) / 15)`, the SAME currency as the
    leaf wrapper's value (evaluators.make_v25_value_wrapper). The target for the
    `value_target="v2_7"` mimic-v2.7 diagnostic (STEP B.0). DEFAULT_CONFIG honors
    the CARCASSONNE_V25_* env (production v2.7 = DROP_THREE_OPEN, CAP=12)."""
    from .virtual_score_v2 import DEFAULT_CONFIG, virtual_score_v2
    return float(np.tanh(virtual_score_v2(state, player, DEFAULT_CONFIG) / 15.0))


# --- throughput-bench instrumentation (gated; zero-cost unless CARC_BENCH_TP set) ---
_BENCH_TP = os.environ.get("CARC_BENCH_TP")
_bench_moves = 0
_bench_last = 0.0


def _bench_tick() -> None:
    """Count one self-play move; emit a per-worker cumulative line every ~3s.
    Used by scripts/bench_pipeline_sweep.py to measure moves/sec (a smooth,
    fast-to-steady-state throughput unit, unlike bursty game completions).
    No-op (one truthiness check per move) unless CARC_BENCH_TP is set."""
    global _bench_moves, _bench_last
    if not _BENCH_TP:
        return
    _bench_moves += 1
    now = time.perf_counter()
    if now - _bench_last >= 3.0:
        print(f"BENCHTP pid={os.getpid()} t={now:.3f} moves={_bench_moves}", flush=True)
        _bench_last = now


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
    interior_min_visits: int = 8,
    interior_max_per_move: int = 16,
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
      value_target: how to encode the per-position value target.
                    "score_diff" (default) → tanh((p0-p1)/15), the graded
                    margin in the same currency as the v2.7 heuristic leaf
                    (Option 2, DECISIONS 2026-05-17 — lets a value head
                    blended into the leaf predict the same quantity).
                    "score_diff_wide" → tanh((p0-p1)/40), the C6 de-saturated
                    outcome target.
                    "wl" → ±1/0, the AlphaZero-canonical win/loss target.
                    "search_value" → per-position MCTS root.Q (current-player
                    POV), the overfitting fix (DECISIONS 2026-06-04): ~100× more
                    independent value labels than the one-per-game outcome z.
                    Requires recording root.Q per learner ply (done above).
                    "search_value_tree" → search_value (root.Q trajectory rows)
                    PLUS value-ONLY rows harvested from the SEARCH TREE INTERIOR
                    (flywheel step 1, DECISIONS 2026-06-04): each well-visited
                    interior node contributes (its board → its converged Q) so
                    the value head sees the off-trajectory positions search
                    actually queries — the fix for the −576 pure-NN-leaf cliff.
                    Interior rows carry aux_mask=False (value-only; dummy
                    policy/mask/ownership skipped by the policy/ownership losses).
      interior_min_visits: search_value_tree only — keep an interior node as a
                    value target only if its visit count N >= this (a converged
                    Q, not N=1 noise). Default 8 (reasonable at sims≈200).
      interior_max_per_move: search_value_tree only — cap on interior rows kept
                    per move (top-N by visits), to bound dataset blow-up since
                    the interior dwarfs the one trajectory row. Default 16.
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
    # search_value_tree harvests tree-interior boards → the learner's MCTS must
    # store each expanded node's board (record_boards). Off for every other mode
    # so eval / normal self-play keep the lean per-node footprint.
    record_interior = value_target in (
        "search_value_tree", "v2_7", "search_value_rank", "residual"
    )
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
        record_boards=record_interior,
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
    # value_target="search_value"/"search_value_tree": per-ply MCTS root.Q
    # (current-player POV), the per-position search value used as the value
    # target instead of the one-per-game outcome z (overfitting fix, DECISIONS
    # 2026-06-04).
    search_values_arr: list[float] = []
    # value_target="search_value_tree" only: value-ONLY rows harvested from the
    # SEARCH TREE INTERIOR (flywheel step 1). Already in current-player POV
    # (encoding from node.player_to_move, paired with that node's Q) → no flip.
    interior_boards_arr: list[np.ndarray] = []
    interior_scalars_arr: list[np.ndarray] = []
    interior_values_arr: list[float] = []
    # value_target="search_value_rank" only (STEP B.1): per-interior-row group id
    # linking SIBLINGS (children of one parent node) so the trainer's listwise
    # ranking loss can order each group by its search Q. -1 = not in a ranking
    # group (trajectory rows + the search_value_tree/v2_7 ungrouped interior rows).
    # group_id = seed*100000 + counter → globally unique across games/files (so a
    # mixed-file batch never merges two games' groups). Carcassonne games have far
    # fewer than 100k groups.
    interior_group_arr: list[int] = []
    next_group_id = int(seed) * 100000

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
        # NOTE (review S1, 2026-05-31 — INTENTIONAL, not a bug): `ply` is the
        # GAME CLOCK (total plies, incremented every move at the bottom of the
        # loop), so the learner's τ=1 exploration window closes by game *progress*,
        # not by a per-learner-move quota. This is the correct AlphaZero
        # convention: temperature decay is tied to how deep into the game a
        # position is (opening vs midgame), which the game clock measures. In
        # anchor games the learner therefore samples τ=1 on ~half of
        # `temp_threshold` of its own moves — which is the right game-stage-
        # relative amount, not a halved quota. Deliberately kept as game-clock
        # gating; do not switch to a learner-only counter without re-validating.
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
            if value_target in (
                "search_value", "search_value_tree", "search_value_rank"
            ):
                # root.Q from the search we just ran (root still in mcts._nodes;
                # select_for_training reads but never clears it). Already current-
                # player POV → aligns with values_arr; no sign flip. Append in the
                # SAME is_learner_move guard so it stays index-aligned with players_arr.
                search_values_arr.append(float(mcts.root_value(board)))
            elif value_target == "v2_7":
                # mimic-v2.7 diagnostic (STEP B.0, DECISIONS 2026-06-05 pm-2): the
                # target is the v2.7 LEAF VALUE at this position (current-player
                # POV), NOT the outcome/search-Q. Tests whether a 7M head can even
                # REPRESENT v2.7's sibling-ranking under MSE (STEP A: the outcome/
                # search-Q head ranks siblings at ~chance, τ=0.08, vs v2.7's 0.58).
                search_values_arr.append(_v27_leaf_value(board.state, cur_player))
            elif value_target == "residual":
                # Lever 1 (DECISIONS 2026-06-05): the head predicts the RESIDUAL
                # Δ = search-Q − v2.7 leaf value (both current-player POV). At leaf
                # time the wrapper computes tanh(vs2/15) + scale·Δ, so the value
                # inherits v2.7's sibling-ranking and only nudges it where the deep
                # search disagrees with the heuristic.
                search_values_arr.append(
                    float(mcts.root_value(board))
                    - _v27_leaf_value(board.state, cur_player)
                )
            if value_target in ("search_value_tree", "v2_7", "residual"):
                # Harvest tree-INTERIOR value targets from the search we just ran
                # (tree still live; next-iter clear() hasn't fired) — the
                # off-trajectory positions search actually queries. search_value_tree
                # uses the node's converged Q; v2_7 uses the v2.7 leaf value at the
                # node (so the mimic-v2.7 head also sees v2.7-at-interior, matching
                # how the leaf is used during search).
                for nb, nb_player, nb_q in mcts.interior_value_targets(
                    board,
                    min_visits=interior_min_visits,
                    max_nodes=interior_max_per_move,
                ):
                    oi, si = game.get_canonical_form(nb, nb_player)
                    interior_boards_arr.append(oi.astype(np.float32))
                    interior_scalars_arr.append(si.astype(np.float32))
                    if value_target == "v2_7":
                        interior_values_arr.append(
                            _v27_leaf_value(nb.state, nb_player)
                        )
                    elif value_target == "residual":
                        # Δ = search-Q − v2.7 leaf value at this interior node
                        # (Lever 1; same residual target as the trajectory rows).
                        interior_values_arr.append(
                            float(nb_q) - _v27_leaf_value(nb.state, nb_player)
                        )
                    else:
                        interior_values_arr.append(float(nb_q))
                    interior_group_arr.append(-1)  # ungrouped
            elif value_target == "search_value_rank":
                # STEP B.1 (the ranking loss): harvest SIBLING GROUPS — each
                # well-visited parent's children, tagged with a shared group_id —
                # so train_iter's listwise loss orders each group by its search Q.
                # min_parent_visits ties to interior_min_visits (a parent at least
                # as visited as a kept child); max_children = interior_max_per_move.
                for grp in mcts.interior_sibling_groups(
                    board,
                    min_parent_visits=max(8, 2 * interior_min_visits),
                    min_child_visits=interior_min_visits,
                    max_groups=6,
                    max_children=interior_max_per_move,
                ):
                    gid = next_group_id
                    next_group_id += 1
                    for nb, nb_player, nb_q in grp:
                        oi, si = game.get_canonical_form(nb, nb_player)
                        interior_boards_arr.append(oi.astype(np.float32))
                        interior_scalars_arr.append(si.astype(np.float32))
                        interior_values_arr.append(float(nb_q))
                        interior_group_arr.append(gid)

        prev_board = board
        last_action = int(action)
        board, _ = game.get_next_state(board, action)
        ply += 1
        _bench_tick()

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
    if value_target in (
        "search_value", "search_value_tree", "v2_7", "search_value_rank", "residual"
    ):
        # Per-position value target recorded per learner ply above — MCTS root.Q
        # (search_value*) or the v2.7 leaf value (v2_7). ~100× more independent
        # labels than the one-per-game outcome z → directly attacks the value
        # head's overfitting (0.79 train → 0.32 held-out; DECISIONS 2026-06-04).
        # Already current-player-POV-signed, so no per-ply z-flip.
        if len(search_values_arr) != len(players_arr):
            raise RuntimeError(
                f"{value_target} mode: recorded {len(search_values_arr)} value "
                f"targets but {len(players_arr)} learner plies — record-site / "
                f"is_learner_move mismatch"
            )
        values_arr = np.array(search_values_arr, dtype=np.float32)
    else:
        p0_score = int(board.state.scores[0])
        p1_score = int(board.state.scores[1])
        if value_target == "score_diff":
            z_p0 = float(np.tanh((p0_score - p1_score) / 15.0))
        elif value_target == "score_diff_wide":
            # C6 de-saturation: /15 pins to ±1 for 30-80pt margins, killing
            # mid-range calibration under MSE. /40 keeps the graded margin inside
            # tanh's responsive region for the realistic base-only score spread.
            z_p0 = float(np.tanh((p0_score - p1_score) / 40.0))
        elif value_target == "wl":
            z_p0 = float(np.sign(p0_score - p1_score))
        else:
            raise ValueError(
                "value_target must be 'score_diff', 'score_diff_wide', 'wl', "
                f"'search_value', 'search_value_tree', 'v2_7', "
                f"'search_value_rank', or 'residual', got {value_target!r}"
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

    boards_full = np.stack(boards_arr)
    scalars_full = np.stack(scalars_arr)
    policies_full = np.stack(policies_arr)
    values_full = values_arr
    masks_full = np.stack(masks_arr)
    ownership_full = ownership_arr
    aux_mask_full = np.ones(len(boards_arr), dtype=bool)  # trajectory rows = full
    # group_id (STEP B.1): trajectory rows are never in a ranking group → -1.
    group_id_full = np.full(len(boards_arr), -1, dtype=np.int64)

    # search_value_tree: append the harvested tree-interior value-ONLY rows.
    # Their boards/scalars are real (encoded from the interior node + its POV);
    # policy/mask/ownership are dummy zeros carried only to keep the 6 arrays
    # column-aligned — the trainer skips them via aux_mask=False. Value = node.Q.
    if interior_boards_arr:
        n_int = len(interior_boards_arr)
        boards_full = np.concatenate([boards_full, np.stack(interior_boards_arr)])
        scalars_full = np.concatenate([scalars_full, np.stack(interior_scalars_arr)])
        policies_full = np.concatenate(
            [policies_full, np.zeros((n_int, A), dtype=np.float32)]
        )
        values_full = np.concatenate(
            [values_full, np.array(interior_values_arr, dtype=np.float32)]
        )
        masks_full = np.concatenate(
            [masks_full, np.zeros((n_int, A), dtype=bool)]
        )
        ownership_full = np.concatenate(
            [ownership_full, np.zeros((n_int, OWNERSHIP_PLANES, W, W), dtype=np.float32)]
        )
        aux_mask_full = np.concatenate(
            [aux_mask_full, np.zeros(n_int, dtype=bool)]
        )
        group_id_full = np.concatenate(
            [group_id_full, np.array(interior_group_arr, dtype=np.int64)]
        )

    return GameDataset(
        boards=boards_full,
        scalars=scalars_full,
        policies=policies_full,
        values=values_full,
        valid_masks=masks_full,
        ownership=ownership_full,
        aux_mask=aux_mask_full,
        group_id=group_id_full,
    )
