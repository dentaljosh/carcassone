"""Contract tests for scripts/measurement_infra/gate_b_fair_pimc.py — the FAIR-PIMC
variant of the Gate-B fixed-root depth-transfer harness.

The claims worth pinning (all cheap: tiny per-world sim budgets, k_dets=2):
  (a) PARITY WITH THE DEPLOYED AGENT — the harness's ``q_argmax_action`` at the deepest
      level equals what a real ``FairHeuristicPriorAgent`` (built through
      champion_factory) returns from ``choose_action`` on the same root with the same
      seed, and its pooled visit counts equal the agent's ``last_pooled_visits``.
      This is the whole correctness story: the harness must BE the deployed agent.
  (b) WITHIN-WORLD BIT-EXACTNESS — the snapshot at level L equals a standalone L-sim
      search of the SAME world (this is what makes one deep search per world legitimate).
  (c) the (N, W_rootpov) harvester agrees with production's ``pool_root_stats``.
  (d) the pooled-VISITS rule breaks ties to the lowest action id.
  (e) the pre-registered subset is a reproducible function of (n, seed).

Env: the production leaf block is set before importing carcassonne_ai (the harness module
itself does this via setdefault at import; repeated here so import order cannot matter).
"""
import os

for _k, _v in {
    "CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0", "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1", "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1", "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
}.items():
    os.environ.setdefault(_k, _v)

import json
import sys
from collections import defaultdict
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

import gate_b_fair_pimc as GB  # noqa: E402
from carcassonne_ai import champion_factory as CF  # noqa: E402
from carcassonne_ai.fair_agent import pool_root_stats  # noqa: E402
from carcassonne_ai.mcts import NeuralMCTS  # noqa: E402
import gen_endgame_positions as GEP  # noqa: E402

ROOTS = REPO / "measurement" / "f3_public_state_oracle" / "roots_k3_suite.jsonl"
LEVELS = (6, 12, 24)     # tiny: the contracts are structural, not strength claims
K_DETS = 2


@pytest.fixture(scope="module")
def cfg():
    return CF.production_prior_cfg()


@pytest.fixture(scope="module")
def root():
    if not ROOTS.exists():
        pytest.skip(f"root suite missing: {ROOTS}")
    return GB._load_roots(str(ROOTS))[0]


def _run(cfg, root, verify=True):
    GB._init_worker(cfg, LEVELS, K_DETS, 600, verify, 2)
    rec = GB._process_root(root)
    assert rec.get("ok"), rec.get("error", "") + rec.get("traceback", "")
    return rec


def test_parity_with_deployed_fair_agent(cfg, root):
    """(a) harness deepest-level pooled-Q pick == FairHeuristicPriorAgent.choose_action,
    and the pooled visit counts match the agent's own last_pooled_visits."""
    rec = _run(cfg, root, verify=False)
    L = str(max(LEVELS))
    game, board = GEP.replay_to(rec["seed"], rec["ply"])
    agent = CF.build_fair_champion(game, cfg=cfg, sims=max(LEVELS), k_dets=K_DETS,
                                   seed=rec["mcts_seed"])
    assert int(agent.choose_action(board)) == rec["per_level"][L]["q_argmax_action"]
    pooled = {int(k): float(v) for k, v in agent.last_pooled_visits.items()}
    assert sum(pooled.values()) == rec["per_level"][L]["sum_N"]
    assert len(pooled) == rec["per_level"][L]["n_children"]
    for t in rec["per_level"][L]["top3"]:
        assert pooled[int(t["action"])] == t["N"]
    # the fair agent must NOT have used the solver on a k=3 root (pure PIMC decision)
    assert agent.exact_moves == 0 and agent.heur_moves == 1
    assert rec["exact_latch"] is False


def test_within_world_bit_exactness(cfg, root):
    """(b) snapshot-at-L == standalone L-sim search, per world, at every level."""
    rec = _run(cfg, root, verify=True)
    be = rec["bit_exact_within_world"]
    assert set(be) == {str(L) for L in LEVELS}
    assert all(v["match"] for v in be.values()), be


def test_read_children_nw_matches_pool_root_stats(cfg, root):
    """(c) the harvester's dedup + root-POV W sign is production's pool_root_stats."""
    game, board = GEP.replay_to(root["seed"], root["ply"])
    ev = CF.build_fair_champion(game, cfg=cfg, sims=24, k_dets=1, seed=7)._evaluator
    m = NeuralMCTS(game=game, evaluator=ev, simulations=24, c_puct=cfg.c_puct, seed=7)
    m.search(board)
    r = m._nodes[game.string_representation(board)]
    agg_n, agg_w = defaultdict(float), defaultdict(float)
    pool_root_stats(r, agg_n, agg_w)
    mine = GB.read_children_nw(r, r.player_to_move)
    assert {a: n for a, (n, w) in mine.items()} == {int(a): v for a, v in agg_n.items()}
    for a, (n, w) in mine.items():
        assert w == pytest.approx(agg_w[a])


def test_pooled_visits_tiebreak_lowest_action():
    """(d) argmax pooled visits, ties -> lowest action id (the final_select='visits' rule)."""
    agg_n = {9: 5.0, 3: 5.0, 7: 4.0}
    agg_w = {9: 1.0, 3: 0.0, 7: 9.0}     # Q must NOT influence the visits rule
    assert GB._pooled_visits_best(agg_n, agg_w)[0] == 3
    assert GB._pooled_visits_best({}, {}) is None


def test_subset_is_reproducible_and_pre_registerable():
    """(e) --subset-n/--subset-seed selects a deterministic, order-stable sample."""
    roots = [{"seed": i, "ply": 1} for i in range(100)]
    a = GB._subset(roots, 10, 1234)
    b = GB._subset(roots, 10, 1234)
    c = GB._subset(roots, 10, 5678)
    assert a == b and a != c
    assert len(a) == 10
    assert a == sorted(a, key=lambda r: roots.index(r))   # canonical order preserved
    assert len(GB._subset(roots, 500, 1)) == 100          # n > population -> all


def test_summary_shape(cfg, root):
    """SUMMARY carries both decision-rule families + the sanity flags a reader needs."""
    rec = _run(cfg, root, verify=False)
    s = GB._summary([rec])
    for k in ("agree_shallowest_vs_deepest", "agree_shallowest_vs_deepest_q",
              "prior_survival_by_level", "prior_survival_q_by_level",
              "played_eq_q_argmax_by_level", "mean_top2_q_gap_by_level",
              "n_exact_latch", "prior_worlds_identical_frac"):
        assert k in s, k
    assert s["regime"] == "fair_pimc" and s["k_dets"] == K_DETS
    json.dumps(s)   # must be serializable
