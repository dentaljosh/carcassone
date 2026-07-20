"""Track-F Gate A oracle-prior probe contract (F2, 2026-07-19).

Covers the three pieces the Gate A "oracle-prior production-depth headroom" probe
adds (docs/reviews/INTEGRATED_REVIEW_20260719.md §"Candidate 2 / Gate A"):

  1. prior-distribution extraction — ``_oracle_prior_from_visits`` (visits -> prior,
     transposition-alias folding, epsilon floor, renormalization, degenerate case)
     and ``_root_action_groups`` (legal actions grouped by resulting board);
  2. the NeuralMCTS ONE-SHOT root-prior override hook — OFF is byte-identical
     (root priors = the heuristic softmax), ON replaces the root priors and is
     consumed after a single search (never leaks to a later move);
  3. the harness plumbing — OFF omits every oracle_* field (schema-identical) and
     leaves the config signature unchanged; ON records the cost fields losslessly
     and the _OraclePriorPrefix runs both search phases at the right budgets.

Leaf env is pinned to the production v2.9 Bmild_cap8 substrate BEFORE importing
carcassonne_ai (mirrors tests/test_heuristic_prior_mcts.py)."""
from __future__ import annotations

import os

os.environ.setdefault("CARCASSONNE_V25_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_OPP_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "0")
os.environ.setdefault("CARCASSONNE_V29_MEEPLE_CURVE", "-8,-4,-1,0,2,3,4,5")
os.environ.setdefault("CARCASSONNE_V25_MEEPLE_K", "2.0")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import importlib.util
import json
import random
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorAgent,
    HeuristicPriorConfig,
)
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402

# Import the harness module by path (same idiom as test_puct_priors_watchdog).
_SCRIPT = REPO / "scripts" / "classical_search" / "eval_puct_priors.py"
_spec = importlib.util.spec_from_file_location("eval_puct_priors", _SCRIPT)
epp = importlib.util.module_from_spec(_spec)
sys.modules["eval_puct_priors"] = epp
_spec.loader.exec_module(epp)


def _new_game():
    return Game(enable_legal_moves_cache=True)


def _play_random(game, board, rng, n):
    """Advance the board by n random legal plies (a non-trivial mid-board root)."""
    for _ in range(n):
        if game.get_game_ended(board, 0) != 0.0:
            break
        legal = np.flatnonzero(game.get_valid_moves(board))
        board, _ = game.get_next_state(board, int(rng.choice(legal)))
    return board


def _cfg():
    return HeuristicPriorConfig(
        c_puct=1.5, tau_p=5.0, leaf_quantize="float", final_select="visits",
        value_norm=15.0, leaf_cfg=DEFAULT_CONFIG, reuse_tree=False, root_select="puct",
    )


# --------------------------------------------------------------------------- #
# 1. Prior-distribution extraction (pure math — the visits->prior contract).    #
# --------------------------------------------------------------------------- #
def test_prior_from_visits_basic_normalized():
    # three singleton groups, visits 40/30/30 -> priors 0.4/0.3/0.3 (eps tiny).
    groups = {0: [0], 1: [1], 2: [2]}
    counts = {0: 40.0, 1: 30.0, 2: 30.0}
    ov = epp._oracle_prior_from_visits(groups, counts, eps_coef=1e-3)
    assert set(ov) == {0, 1, 2}
    assert ov[0] == pytest.approx(0.4, abs=1e-3)
    assert ov[1] == pytest.approx(0.3, abs=1e-3)
    assert sum(ov.values()) == pytest.approx(1.0, abs=1e-9)


def test_prior_from_visits_alias_folding():
    # actions 0 & 3 collide (one transposition group, repr = lowest index 0).
    groups = {0: [0, 3], 1: [1], 2: [2]}
    # the pre-search deduped distribution carries the group's combined count on a
    # SINGLE member — test the case where that member is the HIGHER index (3).
    counts = {3: 40.0, 1: 30.0, 2: 30.0}
    ov = epp._oracle_prior_from_visits(groups, counts, eps_coef=1e-3)
    # whole group mass sits on the repr (0); the alias member (3) gets exactly 0.
    assert ov[3] == 0.0
    assert ov[0] == pytest.approx(0.4, abs=1e-3)
    # every legal action is covered, and the repr-mass sums to 1.
    assert set(ov) == {0, 1, 2, 3}
    assert ov[0] + ov[1] + ov[2] == pytest.approx(1.0, abs=1e-9)


def test_prior_from_visits_epsilon_floor_keeps_exploration_alive():
    # group 1 and 2 got ZERO pre-search visits -> must be floored to eps, not 0,
    # so PUCT can still explore them. eps = eps_coef / n_groups.
    groups = {0: [0], 1: [1], 2: [2]}
    counts = {0: 100.0}  # only group 0 visited
    ov = epp._oracle_prior_from_visits(groups, counts, eps_coef=1e-3)
    eps = 1e-3 / 3
    assert ov[1] > 0.0 and ov[2] > 0.0
    # floored value renormalized: raw {1,2}=eps, {0}=1 -> normalize by (1+2eps).
    assert ov[1] == pytest.approx(eps / (1 + 2 * eps), rel=1e-6)
    assert ov[0] == pytest.approx(1.0 / (1 + 2 * eps), rel=1e-6)
    assert sum(ov.values()) == pytest.approx(1.0, abs=1e-9)


def test_prior_from_visits_degenerate_all_zero_is_uniform():
    groups = {0: [0], 1: [1], 5: [5]}
    ov = epp._oracle_prior_from_visits(groups, {}, eps_coef=1e-3)
    assert ov[0] == pytest.approx(1 / 3) and ov[1] == pytest.approx(1 / 3)
    assert sum(ov.values()) == pytest.approx(1.0, abs=1e-9)


def test_root_action_groups_partition_legal_actions():
    game = _new_game()
    board = _play_random(game, game.get_init_board(), random.Random(3), 12)
    legal = {int(a) for a in np.flatnonzero(game.get_valid_moves(board))}
    groups = epp._root_action_groups(game, board)
    # reprs are lowest-index members; members partition the legal set exactly.
    members = [m for ms in groups.values() for m in ms]
    assert sorted(members) == sorted(legal)
    assert len(members) == len(set(members))          # no action in two groups
    for repr_a, ms in groups.items():
        assert repr_a == min(ms)


# --------------------------------------------------------------------------- #
# 2. NeuralMCTS one-shot root-prior override hook.                              #
# --------------------------------------------------------------------------- #
def test_override_off_is_heuristic_priors():
    """Default (unarmed) search leaves root priors = the heuristic softmax."""
    game = _new_game()
    board = _play_random(game, game.get_init_board(), random.Random(1), 10)
    agent = HeuristicPriorAgent(_new_game(), _cfg(), simulations=24, seed=0)
    assert agent.mcts._root_prior_override is None  # inert by default
    agent.clear()
    agent.mcts.search(board)
    root = agent.mcts._nodes[agent.game.string_representation(board)]
    # heuristic priors are a normalized distribution over legal actions.
    assert sum(root.priors.values()) == pytest.approx(1.0, abs=1e-5)
    assert all(p >= 0.0 for p in root.priors.values())


def test_override_on_replaces_root_priors_and_is_one_shot():
    game = _new_game()
    board = _play_random(game, game.get_init_board(), random.Random(7), 10)

    # baseline heuristic priors (never-armed agent, deterministic).
    base = HeuristicPriorAgent(_new_game(), _cfg(), simulations=24, seed=0)
    base.clear()
    base.mcts.search(board)
    base_root = base.mcts._nodes[base.game.string_representation(board)]
    heur_priors = {int(a): float(base_root.priors[a]) for a in base_root.valid_actions}

    # build a NON-heuristic override (reverse the heuristic mass across groups).
    groups = epp._root_action_groups(base.game, board)
    reprs = sorted(groups)
    fake_counts = {r: float(10 * (i + 1)) for i, r in enumerate(reprs)}
    override = epp._oracle_prior_from_visits(groups, fake_counts, eps_coef=1e-3)

    agent = HeuristicPriorAgent(_new_game(), _cfg(), simulations=24, seed=0)
    agent.mcts.set_root_prior_override(override)
    agent.clear()                       # clear() must NOT drop the armed override
    assert agent.mcts._root_prior_override is not None
    agent.mcts.search(board)
    root = agent.mcts._nodes[agent.game.string_representation(board)]
    # root priors now equal the override exactly (deeper nodes untouched).
    for a in root.valid_actions:
        assert root.priors[a] == pytest.approx(override.get(int(a), 0.0), abs=1e-9)
    # the injection actually changed something vs the heuristic priors.
    assert any(abs(root.priors[a] - heur_priors[a]) > 1e-6 for a in root.valid_actions)
    # ONE-SHOT: consumed after the single search.
    assert agent.mcts._root_prior_override is None

    # a subsequent (un-armed) search falls back to the heuristic priors.
    agent.clear()
    agent.mcts.search(board)
    root2 = agent.mcts._nodes[agent.game.string_representation(board)]
    for a in root2.valid_actions:
        assert root2.priors[a] == pytest.approx(heur_priors[int(a)], abs=1e-9)


def test_override_group_mass_is_representative_invariant():
    """The injected root priors sum to 1 over legal actions regardless of which
    transposition member the search later elects as the group representative
    (aliases carry 0; their mass folds back via prior_bonus)."""
    game = _new_game()
    board = _play_random(game, game.get_init_board(), random.Random(11), 14)
    groups = epp._root_action_groups(game, board)
    counts = {r: float(i + 1) for i, r in enumerate(sorted(groups))}
    ov = epp._oracle_prior_from_visits(groups, counts, eps_coef=1e-3)
    # per group: exactly the repr carries mass, all other members are 0.
    for repr_a, members in groups.items():
        assert ov[repr_a] > 0.0
        for m in members:
            if m != repr_a:
                assert ov[m] == 0.0
    assert sum(ov.values()) == pytest.approx(1.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# 3. Harness plumbing — OFF byte-identical schema, ON records cost losslessly.  #
# --------------------------------------------------------------------------- #
def _mk_result(**kw):
    base = dict(seed=1, a_seat=0, cand_sims=48, champ_sims=48, score_p0=10,
                score_p1=8, diff=2, won_by_cand=True, drew=False, elapsed_s=1.0,
                moves=10, cand_prefix_moves=5, champ_prefix_moves=5)
    base.update(kw)
    return epp.GameResult(**base)


def test_save_omits_oracle_fields_when_off(tmp_path):
    p = tmp_path / "seed1_a0.json"
    epp._save(p, _mk_result())
    d = json.load(open(p))
    assert not any(k.startswith("oracle_") for k in d), "OFF cell must be schema-identical"
    # reload is lossless (defaults refill the omitted fields).
    r2 = epp._try_load(p)
    assert r2.oracle_prior_moves == 0 and r2.oracle_presearch_leaf_calls == 0


def test_save_includes_oracle_fields_when_on(tmp_path):
    p = tmp_path / "seed1_a0.json"
    epp._save(p, _mk_result(oracle_prior_moves=70, oracle_presearch_secs=16.8,
                            oracle_mainsearch_secs=7.6, oracle_presearch_leaf_calls=8117,
                            oracle_mainsearch_leaf_calls=4061))
    d = json.load(open(p))
    assert d["oracle_prior_moves"] == 70
    assert d["oracle_presearch_leaf_calls"] == 8117
    r2 = epp._try_load(p)                      # lossless round-trip
    assert r2.oracle_mainsearch_leaf_calls == 4061


def test_variant_sig_config_identical_off_tagged_on():
    class A:  # minimal args stand-in for _variant_sig
        c_puct = 1.5
        tau_p = 5.0
        final_select = "visits"
        c_lcb = 1.0
        reuse_tree = False
        value_norm = 15.0
        root_select = "puct"
        gumbel_m = 16
        gumbel_retain_g = True
        gumbel_c_visit = 50.0
        gumbel_c_scale = 1.0
        opp_pin_champion = False
        oracle_prior_mult = None

    a = A()
    assert epp._variant_sig(a) == "", "OFF must not perturb the champion config signature"
    a.oracle_prior_mult = 3
    assert epp._variant_sig(a) == "-oracle3"


def test_oracle_prefix_runs_both_phases_and_reaches_root():
    """End-to-end: one _OraclePriorPrefix move runs the pre-search (mult x sims)
    and the main search, the override reaches the root, and the pre-search does
    ~mult x the leaf work of the main search."""
    board = _play_random(_new_game(), _new_game().get_init_board(), random.Random(5), 12)
    pref = epp._OraclePriorPrefix(_new_game(), _new_game(), _cfg(),
                                  sims=16, mult=3, eps_coef=1e-3, seed=0)
    game = _new_game()
    mv = pref.move(board)
    assert game.get_valid_moves(board)[mv], "oracle prefix returned an illegal action"
    assert pref.oracle_moves == 1
    assert pref.last_reached_root, "override distribution never reached the root"
    assert pref.presearch_leaf_calls > pref.mainsearch_leaf_calls
    # pre-search runs ~mult x the main leaf work (3x sims); allow slack for
    # terminal/transposition early-outs.
    ratio = pref.presearch_leaf_calls / max(1, pref.mainsearch_leaf_calls)
    assert 2.3 < ratio < 3.7, f"pre/main leaf ratio {ratio:.2f} not ~mult=3"
