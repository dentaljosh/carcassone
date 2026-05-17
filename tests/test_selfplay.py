"""Tests for selfplay.play_one_selfplay_game — the Phase 4 game-generation
primitive."""
from __future__ import annotations

import numpy as np

from carcassonne_ai.action_space import action_size
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.selfplay import play_one_selfplay_game


def _uniform_evaluator(board) -> tuple[np.ndarray, float]:
    a = action_size(board.offset.size)
    return np.full(a, 1.0 / a, dtype=np.float32), 0.0


def _play(seed: int = 0, sims: int = 4, temp_threshold: int = 5,
          value_target: str = "score_diff"):
    g = Game(enable_legal_moves_cache=True)
    return play_one_selfplay_game(
        game=g,
        evaluator=_uniform_evaluator,
        sims=sims,
        c_puct=1.5,
        dirichlet_alpha=0.3,
        dirichlet_eps=0.25,
        temp_threshold=temp_threshold,
        seed=seed,
        max_plies=400,
        value_target=value_target,
    )


def test_play_one_game_produces_nonempty_dataset() -> None:
    ds = _play(seed=0, sims=2, temp_threshold=3)
    assert len(ds) > 0
    A = ds.policies.shape[1]
    g = Game(enable_legal_moves_cache=True)
    assert A == action_size(g.window_size)


def test_value_targets_wl_mode() -> None:
    """value_target='wl' → raw z ∈ {-1, 0, +1} (AlphaZero-canonical)."""
    ds = _play(seed=1, sims=2, temp_threshold=3, value_target="wl")
    unique = set(ds.values.tolist())
    assert unique.issubset({-1.0, 0.0, 1.0}), f"unexpected values: {unique}"


def test_value_targets_score_diff_mode() -> None:
    """value_target='score_diff' (the default) → tanh(margin/15): a graded
    value strictly inside (-1, 1). A non-draw game yields a non-integer
    magnitude — exactly what distinguishes it from the 'wl' encoding and
    makes it blendable with the tanh(vs2/15) heuristic leaf (Option 2)."""
    ds = _play(seed=1, sims=2, temp_threshold=3)  # default = score_diff
    vals = ds.values.tolist()
    assert all(-1.0 < v < 1.0 for v in vals), f"out of (-1,1): {set(vals)}"
    if any(abs(v) > 1e-9 for v in vals):  # not a draw
        assert any(v not in (-1.0, 0.0, 1.0) for v in vals), (
            "score_diff produced only integer values — not graded"
        )


def test_value_targets_share_one_magnitude() -> None:
    """Every position's target is ±z_p0 (sign-flipped by player-to-move), so
    across one game the targets take at most one distinct magnitude. Holds
    for both encodings — it is the 'sign flips with the player' invariant."""
    for vt in ("score_diff", "wl"):
        ds = _play(seed=2, sims=2, temp_threshold=3, value_target=vt)
        mags = {round(abs(v), 6) for v in ds.values.tolist()}
        assert len(mags) == 1, f"{vt}: >1 distinct magnitude: {mags}"


def test_policy_targets_are_distributions_over_legal_actions() -> None:
    """Each policy row sums to ~1.0 and has zero mass on invalid actions.

    Uses production-like sims=25 to exercise the full PUCT tree expansion
    path. At sims=3 the tree is too shallow to trigger the
    snapshot-mask-vs-MCTS-mask divergence the smoke run hit.
    """
    ds = _play(seed=3, sims=25, temp_threshold=5)
    for i in range(len(ds)):
        p = ds.policies[i]
        m = ds.valid_masks[i]
        s = float(p.sum())
        assert abs(s - 1.0) < 1e-3, f"row {i} sums to {s}"
        invalid_mass = float(p[~m].sum())
        assert invalid_mass < 1e-6, f"row {i} has mass on invalid actions: {invalid_mass}"


def test_seed_determinism() -> None:
    ds1 = _play(seed=7, sims=2, temp_threshold=3)
    ds2 = _play(seed=7, sims=2, temp_threshold=3)
    assert len(ds1) == len(ds2)
    assert np.array_equal(ds1.values, ds2.values)
    assert np.allclose(ds1.policies, ds2.policies)


def test_save_load_roundtrip(tmp_path) -> None:
    """Phase 4 stores per-game .npz; verify the standard GameDataset IO works."""
    ds = _play(seed=4, sims=2, temp_threshold=3)
    out = tmp_path / "g.npz"
    ds.save(out)
    from carcassonne_ai.warmstart import GameDataset
    loaded = GameDataset.load(out)
    assert len(loaded) == len(ds)
    assert np.array_equal(loaded.values, ds.values)
    assert np.allclose(loaded.policies, ds.policies)
