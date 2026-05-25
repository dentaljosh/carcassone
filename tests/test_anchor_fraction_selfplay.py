"""Tests for anchor-fraction self-play in selfplay.play_one_selfplay_game.

Anchor-fraction self-play mixes learner-vs-anchor games into the standard
learner-vs-learner self-play to break rock-paper-scissors drift (the failure
mode that killed the Option B chain — DECISIONS.md 2026-05-24).

Contract under test:
  - When anchor_evaluator is None, output is byte-identical to legacy behavior.
  - When anchor_evaluator is set, only the learner's moves are saved
    (players_arr contains exactly one value: learner_player_idx).
  - learner_player_idx must be 0 or 1; anything else raises.
  - Anchor games legally terminate (same engine, both sides play legal moves).
"""
from __future__ import annotations

import numpy as np
import pytest

from carcassonne_ai.action_space import action_size
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.selfplay import play_one_selfplay_game


def _uniform_evaluator(board) -> tuple[np.ndarray, float]:
    a = action_size(board.offset.size)
    return np.full(a, 1.0 / a, dtype=np.float32), 0.0


def _biased_evaluator(board) -> tuple[np.ndarray, float]:
    """A distinct-from-uniform evaluator so anchor-vs-learner games actually
    have a policy gap. Slight bias toward the first half of the action space."""
    a = action_size(board.offset.size)
    p = np.full(a, 1.0 / a, dtype=np.float32)
    half = a // 2
    p[:half] *= 1.1
    p[half:] *= 0.9
    p /= p.sum()
    return p, 0.0


def _play(**kw):
    g = Game(enable_legal_moves_cache=True)
    defaults = dict(
        game=g,
        evaluator=_uniform_evaluator,
        sims=4,
        c_puct=1.5,
        dirichlet_alpha=0.3,
        dirichlet_eps=0.25,
        temp_threshold=5,
        seed=0,
        max_plies=400,
        value_target="score_diff",
    )
    defaults.update(kw)
    return play_one_selfplay_game(**defaults)


def test_anchor_none_is_byte_identical_to_legacy() -> None:
    """Regression: anchor_evaluator=None must produce the same dataset the
    pre-change code did. Same seed → same boards/policies/values."""
    ds_legacy = _play(seed=11, sims=4, temp_threshold=3)
    ds_new_default = _play(
        seed=11, sims=4, temp_threshold=3,
        anchor_evaluator=None, learner_player_idx=0,
    )
    assert len(ds_legacy) == len(ds_new_default)
    assert np.array_equal(ds_legacy.values, ds_new_default.values)
    assert np.allclose(ds_legacy.policies, ds_new_default.policies)
    assert np.array_equal(ds_legacy.valid_masks, ds_new_default.valid_masks)


def test_invalid_learner_player_idx_raises() -> None:
    with pytest.raises(ValueError, match="learner_player_idx"):
        _play(
            seed=0, sims=2, temp_threshold=3,
            anchor_evaluator=_biased_evaluator, learner_player_idx=2,
        )


@pytest.mark.parametrize("learner_idx", [0, 1])
def test_only_learner_moves_recorded(learner_idx: int) -> None:
    """In anchor mode, exactly the learner's moves must appear in the saved
    dataset — anchor moves must not contribute records. The check we have
    available post-hoc is that every value-target sign matches a single
    player POV (the learner's). Internal players_arr is consumed by the value
    sign-flip and discarded; we infer learner-only by the all-same-sign
    invariant within a non-draw game."""
    ds = _play(
        seed=20 + learner_idx, sims=4, temp_threshold=3,
        anchor_evaluator=_biased_evaluator, learner_player_idx=learner_idx,
    )
    # Anchor mode still produces records (the learner played roughly half the
    # plies; even a short game gives a few learner moves). If we got an empty
    # dataset, something is wrong with routing or the engine terminated early.
    assert len(ds) > 0, "no learner-side records produced — routing bug?"
    # Every value target is z_p0 if learner==player 0, else -z_p0. All
    # learner-side records share one signed magnitude — same invariant as in
    # legacy self-play (test_value_targets_share_one_magnitude), but here the
    # signs must also all be identical (only one player recorded), not flip
    # ply-to-ply.
    vals = ds.values.tolist()
    if any(abs(v) > 1e-9 for v in vals):  # skip exact draws
        signs = {1 if v > 0 else (-1 if v < 0 else 0) for v in vals}
        signs.discard(0)
        assert len(signs) == 1, (
            f"learner-only mode produced multiple signs in values: "
            f"{set(vals)} — anchor records are leaking in"
        )


def test_anchor_game_record_count_less_than_legacy() -> None:
    """An anchor game's saved dataset should have strictly fewer records than
    the same-seed legacy game (~half), because the anchor's moves are not
    saved. Use seed determinism so the comparison is apples-to-apples."""
    # Legacy run: learner plays both sides.
    ds_full = _play(seed=33, sims=4, temp_threshold=3)
    # Anchor run with same seed: only learner moves recorded.
    ds_anchor = _play(
        seed=33, sims=4, temp_threshold=3,
        anchor_evaluator=_biased_evaluator, learner_player_idx=0,
    )
    assert len(ds_anchor) < len(ds_full), (
        f"anchor game recorded {len(ds_anchor)} >= legacy {len(ds_full)} — "
        f"anchor moves should not be saved"
    )
    # Sanity: should be roughly half (allow generous slack — exact ratio
    # depends on whether the game ended on player 0's or player 1's turn).
    ratio = len(ds_anchor) / max(1, len(ds_full))
    assert 0.30 <= ratio <= 0.70, (
        f"anchor/legacy record ratio {ratio:.2f} is not near 0.5 — "
        f"routing may be off (saved {len(ds_anchor)} of {len(ds_full)})"
    )


def test_anchor_game_completes_legally() -> None:
    """Smoke: an anchor game terminates without raising, and all policy rows
    are valid distributions on legal actions (same contract as legacy)."""
    ds = _play(
        seed=42, sims=8, temp_threshold=5,
        anchor_evaluator=_biased_evaluator, learner_player_idx=1,
    )
    assert len(ds) > 0
    for i in range(len(ds)):
        p = ds.policies[i]
        m = ds.valid_masks[i]
        assert abs(float(p.sum()) - 1.0) < 1e-3
        assert float(p[~m].sum()) < 1e-6
