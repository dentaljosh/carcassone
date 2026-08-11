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


def _varied_evaluator(board) -> tuple[np.ndarray, float]:
    """Uniform priors but a position-VARYING leaf value (decreases as the deck
    drains). The constant-0 uniform evaluator backs up Q=0 everywhere — useless
    for testing search_value, which records root.Q. A deck-size-driven value
    gives distinct root.Q across plies so the recorded targets genuinely vary."""
    a = action_size(board.offset.size)
    pri = np.full(a, 1.0 / a, dtype=np.float32)
    val = float(np.tanh((len(board.state.deck) - 35) / 20.0))
    return pri, val


def _play(seed: int = 0, sims: int = 4, temp_threshold: int = 5,
          value_target: str = "score_diff", evaluator=_uniform_evaluator,
          interior_min_visits: int = 8, interior_max_per_move: int = 16):
    g = Game(enable_legal_moves_cache=True)
    return play_one_selfplay_game(
        game=g,
        evaluator=evaluator,
        sims=sims,
        c_puct=1.5,
        dirichlet_alpha=0.3,
        dirichlet_eps=0.25,
        temp_threshold=temp_threshold,
        seed=seed,
        max_plies=400,
        value_target=value_target,
        interior_min_visits=interior_min_visits,
        interior_max_per_move=interior_max_per_move,
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


def test_value_targets_score_diff_wide_mode() -> None:
    """value_target='score_diff_wide' → tanh(margin/40), the C6 de-saturated
    target. Like score_diff it is graded inside (-1, 1), but with a wider norm
    it sits further from the saturating ±1 region for the same margin — so for
    any non-draw the |wide| magnitude is strictly LESS than the |/15| one."""
    wide = _play(seed=1, sims=2, temp_threshold=3, value_target="score_diff_wide")
    narrow = _play(seed=1, sims=2, temp_threshold=3, value_target="score_diff")
    wvals, nvals = wide.values.tolist(), narrow.values.tolist()
    assert all(-1.0 < v < 1.0 for v in wvals), f"out of (-1,1): {set(wvals)}"
    wmag = max(abs(v) for v in wvals)
    nmag = max(abs(v) for v in nvals)
    if nmag > 1e-9:  # same seed → same game → same margin; not a draw
        assert wmag < nmag, f"wide {wmag} should be < narrow {nmag} (less saturated)"


def test_value_targets_share_one_magnitude() -> None:
    """Every position's target is ±z_p0 (sign-flipped by player-to-move), so
    across one game the targets take at most one distinct magnitude. Holds
    for all encodings — it is the 'sign flips with the player' invariant."""
    for vt in ("score_diff", "score_diff_wide", "wl"):
        ds = _play(seed=2, sims=2, temp_threshold=3, value_target=vt)
        mags = {round(abs(v), 6) for v in ds.values.tolist()}
        assert len(mags) == 1, f"{vt}: >1 distinct magnitude: {mags}"


def test_value_targets_search_value_mode() -> None:
    """value_target='search_value' → per-position MCTS root.Q (current-player
    POV), the overfitting fix. Contract: one value per recorded position, all in
    [-1, 1]. Crucially, UNLIKE the outcome encodings (one shared magnitude per
    game — see test_value_targets_share_one_magnitude), search values vary
    position-to-position; with a deck-varying leaf value we get >1 distinct
    magnitude, proving these are genuine per-position root.Q, not a re-baked z."""
    ds = _play(seed=1, sims=8, temp_threshold=3, value_target="search_value",
               evaluator=_varied_evaluator)
    vals = ds.values.tolist()
    assert len(vals) == len(ds.boards) == ds.policies.shape[0]
    assert all(-1.0 <= v <= 1.0 for v in vals), f"out of [-1,1]: {set(vals)}"
    assert all(np.isfinite(v) for v in vals)
    mags = {round(abs(v), 6) for v in vals}
    assert len(mags) > 1, (
        "search_value collapsed to one magnitude — likely zeros (constant "
        f"evaluator leaked) or the outcome z, not per-position root.Q: {mags}"
    )


def test_search_value_matches_root_q_per_ply() -> None:
    """The recorded search_value for each ply equals NeuralMCTS.root_value at
    that position — i.e. selfplay writes exactly root.Q, index-aligned. Replays
    the same seeded game move-by-move and checks the first recorded ply's target
    against an independent search's root.Q (current-player POV)."""
    from carcassonne_ai.mcts import NeuralMCTS

    ds = _play(seed=5, sims=8, temp_threshold=3, value_target="search_value",
               evaluator=_varied_evaluator)
    # Re-derive ply 0's root.Q independently with the same evaluator/sims/seed.
    g = Game(enable_legal_moves_cache=True)
    import random as _r
    _r.seed(5)
    board = g.get_init_board()
    mcts = NeuralMCTS(game=g, evaluator=_varied_evaluator, simulations=8,
                      c_puct=1.5, seed=5, dirichlet_alpha=0.3, dirichlet_eps=0.25)
    mcts.search(board)
    rq = mcts.root_value(board)
    assert abs(float(ds.values[0]) - rq) < 1e-6, (
        f"recorded search_value[0]={ds.values[0]} != root.Q={rq}"
    )


def test_search_value_seed_determinism() -> None:
    ds1 = _play(seed=9, sims=6, value_target="search_value",
                evaluator=_varied_evaluator)
    ds2 = _play(seed=9, sims=6, value_target="search_value",
                evaluator=_varied_evaluator)
    assert np.array_equal(ds1.values, ds2.values)


def test_search_value_differs_from_outcome_target() -> None:
    """Same seeded game, search_value vs score_diff → different value arrays
    (the whole point: the target source changed). Lengths match (same plies)."""
    sv = _play(seed=2, sims=8, value_target="search_value",
               evaluator=_varied_evaluator)
    sd = _play(seed=2, sims=8, value_target="score_diff",
               evaluator=_varied_evaluator)
    assert len(sv.values) == len(sd.values)
    assert not np.allclose(sv.values, sd.values)


# --- search_value_tree (flywheel step 1) -----------------------------------


def test_search_value_tree_emits_interior_value_only_rows() -> None:
    """search_value_tree = search_value (full trajectory rows) PLUS value-only
    rows harvested from the search tree interior. Contract:
      - more rows than plain search_value on the same seed (interior added);
      - aux_mask=True trajectory rows EXACTLY reproduce the search_value run;
      - aux_mask=False interior rows are value-only: zero policy, all-False mask,
        zero ownership, finite value in [-1,1]; and the value head still trains
        on them (their value is the node's search Q, not necessarily zero)."""
    sv = _play(seed=3, sims=24, temp_threshold=3, value_target="search_value",
               evaluator=_varied_evaluator)
    tree = _play(seed=3, sims=24, temp_threshold=3,
                 value_target="search_value_tree", evaluator=_varied_evaluator,
                 interior_min_visits=2, interior_max_per_move=8)

    aux = tree.aux_mask.astype(bool)
    n_traj = int(aux.sum())
    n_int = int((~aux).sum())
    assert n_traj == len(sv.values), "trajectory rows must match search_value"
    assert n_int > 0, "expected interior value-only rows at sims=24"
    assert len(tree) == n_traj + n_int

    # Trajectory rows (aux=True) reproduce the search_value run exactly.
    assert np.array_equal(tree.values[aux], sv.values)
    assert np.array_equal(tree.policies[aux], sv.policies)

    # Interior rows (aux=False) are value-only with dummy other heads.
    iv = tree.values[~aux]
    assert np.all(np.isfinite(iv)) and np.all(np.abs(iv) <= 1.0)
    assert np.all(tree.policies[~aux] == 0.0)
    assert not np.any(tree.valid_masks[~aux])          # all-False masks
    assert np.all(tree.ownership[~aux] == 0.0)


def test_search_value_tree_roundtrips_aux_mask(tmp_path) -> None:
    """The mixed aux_mask survives a GameDataset save/load roundtrip."""
    from carcassonne_ai.warmstart import GameDataset
    tree = _play(seed=4, sims=24, temp_threshold=3,
                 value_target="search_value_tree", evaluator=_varied_evaluator,
                 interior_min_visits=2, interior_max_per_move=8)
    p = tmp_path / "seed_tree.npz"
    tree.save(p)
    r = GameDataset.load(p)
    assert np.array_equal(r.aux_mask, tree.aux_mask)
    assert not r.aux_mask.all(), "expected a mix of full + value-only rows"


def test_search_value_tree_default_modes_are_all_full_rows() -> None:
    """A non-tree mode produces an all-True aux_mask (every row full)."""
    ds = _play(seed=1, sims=8, value_target="search_value",
               evaluator=_varied_evaluator)
    assert ds.aux_mask.all()


# --- v2_7 (mimic-v2.7 diagnostic, STEP B.0) --------------------------------


def test_v2_7_trajectory_target_is_v27_leaf_value() -> None:
    """value_target='v2_7' → each trajectory row's value is the v2.7 leaf value
    tanh(vs2(state, current_player)/15) at that position, NOT the outcome or
    root.Q. Check ply 0 against an independent v2.7 leaf computation."""
    from carcassonne_ai.selfplay import _v27_leaf_value

    ds = _play(seed=5, sims=8, temp_threshold=3, value_target="v2_7",
               evaluator=_varied_evaluator, interior_min_visits=2,
               interior_max_per_move=8)
    aux = ds.aux_mask.astype(bool)
    g = Game(enable_legal_moves_cache=True)
    board = g.get_init_board()
    expect = _v27_leaf_value(board.state, board.state.current_player)
    traj_vals = ds.values[aux]
    assert abs(float(traj_vals[0]) - expect) < 1e-6, (
        f"v2_7 trajectory[0]={traj_vals[0]} != v2.7 leaf {expect}"
    )
    # All values are tanh-bounded and finite (trajectory + interior).
    assert np.all(np.isfinite(ds.values)) and np.all(np.abs(ds.values) <= 1.0)


def test_v2_7_emits_interior_value_only_rows() -> None:
    """v2_7 (like search_value_tree) emits value-only interior rows; their value
    is the v2.7 leaf at the interior node (finite, in [-1,1]); other heads dummy."""
    ds = _play(seed=3, sims=24, temp_threshold=3, value_target="v2_7",
               evaluator=_varied_evaluator, interior_min_visits=2,
               interior_max_per_move=8)
    aux = ds.aux_mask.astype(bool)
    assert int((~aux).sum()) > 0, "expected interior value-only rows at sims=24"
    iv = ds.values[~aux]
    assert np.all(np.isfinite(iv)) and np.all(np.abs(iv) <= 1.0)
    assert np.all(ds.policies[~aux] == 0.0)
    assert not np.any(ds.valid_masks[~aux])


def test_v2_7_differs_from_search_value_and_outcome() -> None:
    """Same seeded game: v2_7 targets differ from both search_value and
    score_diff (the whole point — a different target source)."""
    v27 = _play(seed=2, sims=8, value_target="v2_7", evaluator=_varied_evaluator)
    sv = _play(seed=2, sims=8, value_target="search_value",
               evaluator=_varied_evaluator)
    # Compare only trajectory rows (search_value has no interior rows).
    aux = v27.aux_mask.astype(bool)
    assert len(v27.values[aux]) == len(sv.values)
    assert not np.allclose(v27.values[aux], sv.values)


# --- search_value_rank (STEP B.1: sibling-ranking groups) -------------------


def test_search_value_rank_emits_sibling_groups() -> None:
    """search_value_rank = search_value trajectory rows + value-only interior
    rows tagged with a group_id linking SIBLINGS. Contract:
      - trajectory rows: aux=True, group_id=-1;
      - group rows: aux=False, group_id>=0, and each present group has >=2 members
        (a parent's children) — the listwise loss needs >=2 to rank;
      - group_ids are globally offset by seed (seed*100000+).
    """
    ds = _play(seed=7, sims=32, temp_threshold=3, value_target="search_value_rank",
               evaluator=_varied_evaluator, interior_min_visits=2,
               interior_max_per_move=6)
    aux = ds.aux_mask.astype(bool)
    gid = ds.group_id
    # trajectory rows: full + ungrouped
    assert np.all(gid[aux] == -1)
    grouped = gid[~aux]
    assert grouped.size > 0, "expected sibling-group interior rows at sims=32"
    assert np.all(grouped >= 0), "interior group rows must have group_id>=0"
    # each present group has >=2 members
    uniq, counts = np.unique(grouped, return_counts=True)
    assert np.all(counts >= 2), f"every group needs >=2 siblings, got {counts}"
    # seed offset applied (group ids are large, seed*100000+)
    assert uniq.min() >= 7 * 100000


def test_search_value_rank_group_ids_unique_per_game() -> None:
    """Two different seeds → disjoint group_id ranges (so a mixed-file batch
    never merges two games' groups)."""
    a = _play(seed=1, sims=32, temp_threshold=3, value_target="search_value_rank",
              evaluator=_varied_evaluator, interior_min_visits=2,
              interior_max_per_move=6)
    b = _play(seed=2, sims=32, temp_threshold=3, value_target="search_value_rank",
              evaluator=_varied_evaluator, interior_min_visits=2,
              interior_max_per_move=6)
    ga = set(int(x) for x in a.group_id if x >= 0)
    gb = set(int(x) for x in b.group_id if x >= 0)
    assert ga and gb and ga.isdisjoint(gb)


def test_on_ply_search_hook_yields_root_sibling_groups() -> None:
    """Step-2 PeNS ranking arm B' hook: under an OUTCOME value_target
    (score_diff_wide) + record_boards_override=True, the on_ply_search callback
    receives the LIVE MCTS per recorded ply, and mcts.root_sibling_group returns
    the root's children with their backed-up Q. Contract:
      - at least one ply yields a group with >=2 children;
      - each child is (board, player_to_move, Q) with board recorded (not None)
        and Q finite in [-1, 1];
      - all children of one group share one player_to_move (Carcassonne never
        mixes tile/meeple actors at a node).
    """
    g = Game(enable_legal_moves_cache=True)
    seen_groups: list[list] = []

    def _on_ply_search(mcts, parent_board, board, cur_player, ply):
        grp = mcts.root_sibling_group(board, min_child_visits=2, max_children=8)
        if grp:
            seen_groups.append(grp)

    play_one_selfplay_game(
        game=g, evaluator=_varied_evaluator, sims=32, c_puct=1.5,
        dirichlet_alpha=0.3, dirichlet_eps=0.25, temp_threshold=3, seed=11,
        value_target="score_diff_wide", on_ply_search=_on_ply_search,
        record_boards_override=True,
    )
    assert seen_groups, "expected >=1 root sibling group at sims=32"
    for grp in seen_groups:
        assert len(grp) >= 2
        players = set()
        for cb, cp, cq in grp:
            assert cb is not None, "record_boards_override should store child boards"
            assert -1.0 <= cq <= 1.0 and np.isfinite(cq)
            players.add(cp)
        assert len(players) == 1, f"one group must share one player_to_move, got {players}"


def test_root_sibling_group_empty_without_record_boards() -> None:
    """Without record_boards_override (the default MSE-gen path), child boards are
    not stored, so root_sibling_group returns [] — the hook is a no-op and the MSE
    path pays nothing."""
    g = Game(enable_legal_moves_cache=True)
    nonempty = 0

    def _on_ply_search(mcts, parent_board, board, cur_player, ply):
        nonlocal nonempty
        if mcts.root_sibling_group(board, min_child_visits=2):
            nonempty += 1

    play_one_selfplay_game(
        game=g, evaluator=_varied_evaluator, sims=32, c_puct=1.5,
        dirichlet_alpha=0.3, dirichlet_eps=0.25, temp_threshold=3, seed=12,
        value_target="score_diff_wide", on_ply_search=_on_ply_search,
        # record_boards_override defaults False
    )
    assert nonempty == 0, "child boards must not be recorded without the override"


def test_listwise_ranking_loss_orders_siblings() -> None:
    """The listwise loss is ~0 when predictions already order siblings like the
    targets, and large when reversed; 0 when no group has >=2 members."""
    import torch
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
    from train_iter import listwise_ranking_loss

    grp = torch.tensor([5, 5, 5, -1], dtype=torch.int64)
    tgt = torch.tensor([0.9, 0.0, -0.9, 0.5])
    good = listwise_ranking_loss(tgt.clone(), tgt, grp, 0.2)   # pred==target
    bad = listwise_ranking_loss(-tgt, tgt, grp, 0.2)            # reversed
    assert good.item() < bad.item()
    none = listwise_ranking_loss(tgt, tgt, torch.tensor([-1, -1, -1, -1]), 0.2)
    assert none.item() == 0.0


def test_centered_group_mse_offset_invariant_and_orders() -> None:
    """The Lever 2 centered MSE: 0 when pred matches target up to a per-group
    CONSTANT (centering removes absolute level), and large when reversed; 0 when
    no group has >=2 members."""
    import torch
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
    from train_iter import centered_group_mse

    grp = torch.tensor([5, 5, 5, -1], dtype=torch.int64)
    tgt = torch.tensor([0.9, 0.0, -0.9, 0.5])
    exact = centered_group_mse(tgt.clone(), tgt, grp)
    assert exact.item() < 1e-6
    # a per-group constant offset is FREE (absolute level doesn't matter).
    offset = centered_group_mse(tgt + 0.37, tgt, grp)
    assert offset.item() < 1e-6
    # reversed ordering → large.
    bad = centered_group_mse(-tgt, tgt, grp)
    assert bad.item() > exact.item() + 0.1
    none = centered_group_mse(tgt, tgt, torch.tensor([-1, -1, -1, -1]))
    assert none.item() == 0.0


# --- residual (Lever 1: head predicts Δ = search-Q − v2.7 leaf) -------------


def test_residual_target_equals_searchQ_minus_v27() -> None:
    """value_target='residual' → each trajectory row's value is exactly
    (search root.Q) − (v2.7 leaf value) at that position. Verify against a
    search_value run (root.Q) and a v2_7 run (v2.7 leaf) on the SAME seeded
    game — the three share an identical trajectory, so per-row:
        residual_traj == search_value − v2_7_traj.
    """
    res = _play(seed=11, sims=8, temp_threshold=3, value_target="residual",
                evaluator=_varied_evaluator, interior_min_visits=2,
                interior_max_per_move=8)
    sv = _play(seed=11, sims=8, temp_threshold=3, value_target="search_value",
               evaluator=_varied_evaluator)
    v27 = _play(seed=11, sims=8, temp_threshold=3, value_target="v2_7",
                evaluator=_varied_evaluator, interior_min_visits=2,
                interior_max_per_move=8)
    res_traj = res.values[res.aux_mask.astype(bool)]
    v27_traj = v27.values[v27.aux_mask.astype(bool)]
    assert len(res_traj) == len(sv.values) == len(v27_traj)
    assert np.allclose(res_traj, sv.values - v27_traj, atol=1e-6), (
        "residual trajectory targets must equal search_value − v2_7"
    )


def test_residual_emits_ungrouped_interior_rows() -> None:
    """residual (like search_value_tree) emits value-only interior rows tagged
    group_id=-1 (it trains with plain MSE, not the ranking loss). Residuals can
    span [-2, 2] (Q − v2.7, each in [-1,1]); just require finite + in range."""
    ds = _play(seed=3, sims=24, temp_threshold=3, value_target="residual",
               evaluator=_varied_evaluator, interior_min_visits=2,
               interior_max_per_move=8)
    aux = ds.aux_mask.astype(bool)
    assert int((~aux).sum()) > 0, "expected interior rows at sims=24"
    assert np.all(ds.group_id == -1), "residual interior rows are ungrouped"
    iv = ds.values[~aux]
    assert np.all(np.isfinite(iv)) and np.all(np.abs(iv) <= 2.0)
    assert np.all(ds.policies[~aux] == 0.0)
    assert not np.any(ds.valid_masks[~aux])


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
