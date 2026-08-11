"""Gate C0 unit tests — feature emitter + sanity-floor machinery.

Covers:
  * the per-component feature emitter: fixed-length keys + the leaf-term
    reconstruction (lt_base + lt_bonus_self - lt_bonus_opp + lt_meeple_curve
    rounds to lt_leaf_score == virtual_score_v2) + ranker consistency, on real
    replayed K<=2 roots (no solve needed -> fast);
  * the verbatim kendall_tau_b / group_metrics copies in c0_fit match the
    harness originals bit-for-bit;
  * the cross-fit machinery: no seed leakage, and OLS on a single monotone
    feature preserves the per-root ranking exactly (the sanity-floor guarantee);
  * (integration, skipped if the cache is absent) the real leaf-score-only OLS
    cross-fit reproduces the leaf floor == 0.6153.

These tests set the v2.9 leaf env and force the flat leaf so the numbers match
the export/harness regardless of import order.
"""
import os
import sys
import math
from pathlib import Path

import numpy as np
import pytest

REPO = Path("/home/doctor/projects/carcassone")
# v2.9 leaf env (must match c0_export / solver_score) — set before importing carc.
os.environ.setdefault("CARCASSONNE_V25_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_OPP_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "0")
os.environ.setdefault("CARCASSONNE_V29_MEEPLE_CURVE", "-8,-4,-1,0,2,3,4,5")
os.environ.setdefault("CARCASSONNE_V25_MEEPLE_K", "2.0")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

for p in ["src", "scripts/level2", "scripts/feature_planes_gate",
          "scripts/canonical_az", "scripts", "measurement/gatec_c0_20260723"]:
    sys.path.insert(0, str(REPO / p))

import c0_features as CF          # noqa: E402
import c0_fit as CFIT             # noqa: E402
from carcassonne_ai import flat_leaf as FL  # noqa: E402
from carcassonne_ai.virtual_score_v2 import virtual_score_v2  # noqa: E402
import eval_hybrid_handoff as EH  # noqa: E402

FL.USE_FLAT_LEAF = True  # force flat path so vs2 == the flat reconstruction exactly
CFG = EH._heur_leaf_cfg(2.0)


def _load_roots(n):
    from gen_endgame_positions import replay_to, k_remaining
    from solver_score import load_sibling_roots, DEFAULT_QPROBE, DEFAULT_POOL, make_v29_leaf_ranker
    recs = load_sibling_roots(DEFAULT_QPROBE, DEFAULT_POOL)
    cand = [r for r in recs if int(r.get("k_remaining", 99)) <= 2]
    cand.sort(key=lambda r: (int(r["seed"]), int(r["ply"])))
    return cand[:n], replay_to, k_remaining, make_v29_leaf_ranker()


def test_metric_copies_match_harness():
    """c0_fit.kendall_tau_b / group_metrics == the harness originals."""
    from value_ranking_train import kendall_tau_b as kt_orig
    from step1_train import group_metrics as gm_orig
    rng = np.random.default_rng(7)
    for _ in range(200):
        n = int(rng.integers(2, 30))
        # inject ties (integer-valued) to exercise the tau-b tie handling
        x = rng.integers(-3, 4, size=n).astype(float)
        yv = rng.integers(-3, 4, size=n).astype(float)
        a = CFIT.kendall_tau_b(x, yv)
        b = kt_orig(x, yv)
        assert (math.isnan(a) and math.isnan(b)) or abs(a - b) < 1e-12
        ra, t1a, taua = CFIT.group_metrics(x, yv)
        rb, t1b, taub = gm_orig(x, yv)
        assert abs(ra - rb) < 1e-12 and t1a == t1b
        assert (math.isnan(taua) and math.isnan(taub)) or abs(taua - taub) < 1e-12


def test_feature_emitter_fixed_length_and_reconstruction():
    """Fixed keys across children + leaf-term reconstruction + ranker match."""
    cand, replay_to, k_remaining, leaf_ranker = _load_roots(3)
    order = CF.feature_order(CFG)
    assert CF.LEAF_SCORE_KEY in order
    for k in CF.LEAF_TERM_KEYS:
        assert k in order
    n_checked = 0
    for rec in cand:
        seed, ply = int(rec["seed"]), int(rec["ply"])
        game, board = replay_to(seed, ply)
        assert game.string_representation(board) == rec["checksum"]
        assert k_remaining(board) <= 2
        rp = board.state.current_player
        legal = list(np.flatnonzero(game.get_valid_moves(board)).astype(int))
        assert len(legal) >= 2
        for a in legal:
            child = game.get_next_state(board, int(a))[0]
            d = CF.emit_features_dict(child.state, rp, CFG)
            assert list(d.keys()) == order              # fixed length + order
            ended = game.get_game_ended(child, rp)
            if ended == 0:
                recon = (d["lt_base"] + d["lt_bonus_self"]
                         - d["lt_bonus_opp"] + d["lt_meeple_curve"])
                vs2 = virtual_score_v2(child.state, rp, CFG)
                assert int(round(recon)) == vs2         # terms reconstruct the leaf
                assert d[CF.LEAF_SCORE_KEY] == float(vs2)
                lr = leaf_ranker(child, rp, game)
                assert abs(lr - math.tanh(vs2 / 15.0)) < 1e-12
                n_checked += 1
    assert n_checked > 20


def test_make_folds_no_seed_leakage():
    """Every seed maps to exactly one fold (grouped cross-fit)."""
    rng = np.random.default_rng(0)
    # synthetic: 200 roots, seeds may repeat (stress the grouping)
    seeds = rng.integers(0, 60, size=200).astype(np.int64)
    fold = CFIT.make_folds(seeds, CFIT.N_FOLDS, CFIT.FOLD_RNG_SEED)
    from collections import defaultdict
    sf = defaultdict(set)
    for s, f in zip(seeds, fold):
        sf[int(s)].add(int(f))
    assert all(len(v) == 1 for v in sf.values())
    assert set(fold.tolist()) <= set(range(CFIT.N_FOLDS))


def test_ols_single_monotone_feature_preserves_ranking():
    """Cross-fit OLS on ONE positively-correlated feature reproduces the direct
    per-root tau exactly (the leaf-score-only sanity-floor guarantee)."""
    rng = np.random.default_rng(3)
    n_roots = 40
    Xs, ys, groups, root_seed = [], [], [], []
    for gi in range(n_roots):
        n = int(rng.integers(4, 12))
        yv = rng.normal(size=n)              # solver values
        f = yv + 0.05 * rng.normal(size=n)   # feature ~ monotone with y
        Xs.append(f.reshape(-1, 1)); ys.append(yv)
        groups.append(np.full(n, gi, dtype=np.int64))
        root_seed.append(gi)                 # unique seed per root
    X = np.concatenate(Xs); y = np.concatenate(ys); group = np.concatenate(groups)
    root_seed = np.array(root_seed, dtype=np.int64)
    fold = CFIT.make_folds(root_seed, CFIT.N_FOLDS, 0)
    fn = lambda a, b, c: CFIT.ridge_fit_predict(a, b, c, 0.0)  # noqa: E731
    reg, t1, tau, forr = CFIT.crossfit_eval(X, y, group, fold, fn, CFIT.N_FOLDS)
    # direct per-root tau on the raw feature
    for gi in range(n_roots):
        m = group == gi
        direct = CFIT.kendall_tau_b(X[m, 0], y[m])
        assert (math.isnan(direct) and math.isnan(tau[gi])) or abs(direct - tau[gi]) < 1e-9


def test_sanity_floor_on_real_cache_if_present():
    """Integration: the real leaf-score-only OLS cross-fit reproduces the leaf
    floor and == 0.6153.  Skipped until c0_export has produced the cache."""
    cache = REPO / "measurement" / "gatec_c0_20260723" / "cache" / "c0_cache.npz"
    if not cache.exists():
        pytest.skip("c0_cache.npz not yet produced")
    z = np.load(cache, allow_pickle=True)
    X = z["X"].astype(np.float64); y = z["y"].astype(np.float64)
    group = z["group"].astype(np.int64)
    names = [str(s) for s in z["feature_names"]]
    root_seed = z["root_seed"].astype(np.int64)
    root_leaf_tau = z["root_leaf_tau"].astype(np.float64)
    leaf_floor = float(np.nanmean(root_leaf_tau))
    assert abs(leaf_floor - 0.6153) < 0.002, f"leaf floor {leaf_floor} != 0.6153"
    ix = names.index(CF.LEAF_SCORE_KEY)
    fold = CFIT.make_folds(root_seed, CFIT.N_FOLDS, CFIT.FOLD_RNG_SEED)
    fn = lambda a, b, c: CFIT.ridge_fit_predict(a, b, c, 0.0)  # noqa: E731
    reg, t1, tau, forr = CFIT.crossfit_eval(
        X[:, [ix]], y, group, fold, fn, CFIT.N_FOLDS)
    got = float(np.nanmean(tau))
    # single positive-slope feature -> ranking identical to the leaf, per root
    assert abs(got - leaf_floor) < 1e-6, f"leaf-score OLS {got} != leaf floor {leaf_floor}"
