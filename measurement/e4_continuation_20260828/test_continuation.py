#!/usr/bin/env python3
"""Contract tests for the E4 CONTINUATION-PRICING instrument.

§1 pins the pairing arithmetic on HAND-COMPUTED fixtures (the mover-sign
convention and the CRN-witness gate), §2 the world-seeding CRN property, §3 the
target selector (outcome-blindness, the decile match, determinism), §4 the
frozen constants against PREREG.md, and §5 the aggregate estimator (the
cluster-robust SE and the pre-registered contrast).
"""
from __future__ import annotations

import importlib.util
import json
import math
import re
from pathlib import Path

import pytest

D = Path(__file__).resolve().parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, D / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CP = _load("continue_plies")
BT = _load("build_continuation_targets")
AG = _load("aggregate")


def arm(margin, **w):
    base = {"root_repr_sha": "R", "world_deck_sha": "W", "world_deck_len": 30,
            "n_drawn_prefix": 40, "n_legal_root": 12,
            "det_seed_base_at_root": 999, "move_idx_at_root": 40}
    base.update(w)
    return {"status": "OK", "margin_p0_minus_p1": margin, "witness": base}


# --------------------------------------------------------------------------- #
# §1 the pairing arithmetic — hand fixtures                                     #
# --------------------------------------------------------------------------- #
def test_seat0_mover_sign_positive_when_owner_arm_scores_more():
    """P0 mover: owner arm ends +7, cf arm ends +2 -> the played move is worth
    +5 points TO THE MOVER."""
    r = CP.pair_price(arm(7), arm(2), actor=0)
    assert r["status"] == "OK"
    assert r["delta_pts_mover"] == 5
    assert (r["margin_owner"], r["margin_cf"]) == (7, 2)


def test_seat0_mover_sign_negative_when_owner_arm_scores_less():
    assert CP.pair_price(arm(-4), arm(3), actor=0)["delta_pts_mover"] == -7


def test_seat1_mover_sign_is_negated():
    """P1 mover: the margin is P0-P1, so a LOWER margin is BETTER for the mover.
    owner -6, cf -1 -> owner is 5 points better FOR P1 -> +5."""
    assert CP.pair_price(arm(-6), arm(-1), actor=1)["delta_pts_mover"] == 5
    assert CP.pair_price(arm(3), arm(-2), actor=1)["delta_pts_mover"] == -5


def test_identical_arms_price_to_exactly_zero_at_both_seats():
    assert CP.pair_price(arm(11), arm(11), actor=0)["delta_pts_mover"] == 0
    assert CP.pair_price(arm(11), arm(11), actor=1)["delta_pts_mover"] == 0


def test_antisymmetry_of_the_mover_sign():
    """The same two arms priced at the two seats are exact negations."""
    a, b = arm(9), arm(-3)
    assert (CP.pair_price(a, b, 0)["delta_pts_mover"]
            == -CP.pair_price(a, b, 1)["delta_pts_mover"])


@pytest.mark.parametrize("field", list(CP.CRN_WITNESS_KEYS))
def test_any_crn_witness_mismatch_voids_the_pair(field):
    """A pair whose arms did not share a root/world/seed is NOT a paired
    contrast — it must VOID, never price."""
    r = CP.pair_price(arm(7), arm(2, **{field: "XX-DIFFERENT"}), actor=0)
    assert r["status"] == "VOID"
    assert r["reason"] == "crn_witness_mismatch"
    assert field in r["fields"]
    assert "delta_pts_mover" not in r


def test_matching_witnesses_price_and_report_the_witness():
    r = CP.pair_price(arm(7), arm(2), actor=0)
    assert set(r["crn_witness"]) == set(CP.CRN_WITNESS_KEYS)


@pytest.mark.parametrize("bad", ["TIME_SKIPPED", "OOM_SKIPPED", "ERROR"])
def test_a_skipped_arm_voids_the_pair_on_either_side(bad):
    for owner, cf in ((({"status": bad}), arm(2)), (arm(7), {"status": bad})):
        r = CP.pair_price(owner, cf, actor=0)
        assert r["status"] == "VOID" and r["reason"] == "arm_not_ok"
        assert "delta_pts_mover" not in r


# --------------------------------------------------------------------------- #
# §2 CRN by construction                                                        #
# --------------------------------------------------------------------------- #
def test_world_rng_has_no_arm_term_so_both_arms_get_one_permutation():
    """The generator's ONLY inputs are (deck_seed, ply, world) — the CRN
    guarantee, asserted on the function's own outputs."""
    deck = list(range(40))
    outs = []
    for _ in range(2):                       # "two arms" call it identically
        d = list(deck)
        CP.world_rng(12345, 77, 3).shuffle(d)
        outs.append(d)
    assert outs[0] == outs[1]
    assert sorted(outs[0]) == deck           # a permutation, nothing added/lost


def test_distinct_worlds_give_distinct_permutations():
    deck = list(range(40))
    seen = set()
    for w in range(CP.M_WORLDS):
        d = list(deck)
        CP.world_rng(12345, 77, w).shuffle(d)
        seen.add(tuple(d))
    assert len(seen) == CP.M_WORLDS


def test_world_permutation_is_independent_of_evaluation_order():
    """World w is the same permutation regardless of which worlds ran before it
    (a fresh generator per world, not one advanced stream)."""
    deck = list(range(40))
    a = list(deck); CP.world_rng(1, 2, 5).shuffle(a)
    for w in (0, 1, 2, 3, 4):
        junk = list(deck); CP.world_rng(1, 2, w).shuffle(junk)
    b = list(deck); CP.world_rng(1, 2, 5).shuffle(b)
    assert a == b


def test_different_plies_and_seeds_give_different_worlds():
    deck = list(range(40))
    def perm(s, p, w):
        d = list(deck); CP.world_rng(s, p, w).shuffle(d); return tuple(d)
    assert perm(1, 2, 0) != perm(2, 2, 0)
    assert perm(1, 2, 0) != perm(1, 3, 0)


# --------------------------------------------------------------------------- #
# §3 the target selector                                                        #
# --------------------------------------------------------------------------- #
OUTCOME_TOKENS = ("winner", "final_scores", "recorded_scores", "margin",
                  "realized", "delta_pts_mover", "price_", "scores_at_ply",
                  "regret")


def test_selector_reads_no_outcome_field():
    """Outcome-blind BY CONSTRUCTION: the selector's source may not even MENTION
    an outcome field (docstring prose about outcome-blindness is stripped first
    so the guard cannot be defeated by, or trip over, its own comment)."""
    src = (D / "build_continuation_targets.py").read_text()
    src = re.sub(r'""".*?"""', "", src, flags=re.S)
    src = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    for tok in OUTCOME_TOKENS:
        assert tok not in src, f"selector mentions outcome token {tok!r}"


def test_carried_fields_carry_no_outcome():
    for tok in OUTCOME_TOKENS:
        assert not any(tok in f for f in BT.CARRY)


def test_largest_remainder_apportions_exactly_and_breaks_ties_low():
    q = BT.largest_remainder({0: 1, 1: 1, 2: 1}, 4)
    assert sum(q.values()) == 4
    assert q[0] == 2 and q[1] == 1 and q[2] == 1     # tie -> the LOWER decile
    q2 = BT.largest_remainder({1: 4, 2: 6, 3: 4, 4: 4, 0: 1, 5: 1, 7: 1}, 30)
    assert sum(q2.values()) == 30


def test_match_controls_is_deterministic_and_sized():
    pool = [{"game": f"g{i%7}", "ply": i, "ply_frac": (i % 10) / 10 + 0.01}
            for i in range(60)]
    tgt = [{"game": "t", "ply": i, "ply_frac": 0.15 + 0.05 * (i % 4)}
           for i in range(20)]
    a, qa, sa = BT.match_controls(pool, tgt, 12, 777)
    b, qb, sb = BT.match_controls(pool, tgt, 12, 777)
    assert [(r["game"], r["ply"]) for r in a] == [(r["game"], r["ply"]) for r in b]
    assert len(a) == 12 and len({(r["game"], r["ply"]) for r in a}) == 12
    assert sum(qa.values()) == 12 and qa == qb and sa == sb


def test_match_controls_shortfall_is_filled_toward_the_target_centre():
    """A decile the pool cannot fill is filled from the nearest remaining
    candidates, so the sample never comes back short."""
    pool = ([{"game": "g", "ply": i, "ply_frac": 0.11} for i in range(20)]
            + [{"game": "h", "ply": 100 + i, "ply_frac": 0.91} for i in range(2)])
    tgt = [{"game": "t", "ply": i, "ply_frac": 0.91} for i in range(10)]
    got, _, short = BT.match_controls(pool, tgt, 8, 5)
    assert len(got) == 8 and short == 6


def test_frozen_target_set_matches_its_meta_and_is_all_divergent():
    tp, mp = D / "targets_continuation.jsonl", D / "TARGETS.json"
    if not tp.exists():
        pytest.skip("target set not built yet")
    rows = [json.loads(l) for l in tp.open()]
    meta = json.loads(mp.read_text())
    assert len(rows) == meta["total"]["n"]
    assert all(r["counterfactual_agrees"] is False for r in rows)
    assert all(r["counterfactual_action"] != r["played_action"] for r in rows)
    assert len({(r["game"], r["ply"]) for r in rows}) == len(rows)
    for s, blk in meta["by_stratum"].items():
        assert sum(1 for r in rows if r["stratum"] == s) == blk["n"]
    assert sum(1 for r in rows if r["stratum"] == "control") == BT.N_CONTROL


# --------------------------------------------------------------------------- #
# §4 the frozen constants                                                       #
# --------------------------------------------------------------------------- #
def test_prereg_constants_match_the_code():
    txt = (D / "PREREG.md").read_text()
    for name, val in (("WORLD_SEED", CP.WORLD_SEED),
                      ("CONTINUATION_SEED", CP.CONTINUATION_SEED),
                      ("M_WORLDS", CP.M_WORLDS),
                      ("ARM_WALL_CAP_S", CP.ARM_WALL_CAP_S),
                      ("CONTROL_SEED", BT.CONTROL_SEED),
                      ("N_CONTROL", BT.N_CONTROL)):
        assert re.search(rf"^{name}\s*=\s*{val}\s*$", txt, re.M), \
            f"PREREG.md does not pin {name} = {val}"


def test_arms_are_exactly_two_and_named():
    assert CP.ARMS == ("arm_owner", "arm_cf")


# --------------------------------------------------------------------------- #
# §5 the estimator                                                              #
# --------------------------------------------------------------------------- #
def _row(game, ply, stratum, actor, deltas):
    return [{"game": game, "ply": ply, "world": w, "stratum": stratum,
             "actor": actor, "k": 30, "ply_frac": 0.4,
             "pair": {"status": "OK", "delta_pts_mover": d}}
            for w, d in enumerate(deltas)]


def test_ply_price_is_the_mean_over_worlds():
    plies = AG.collapse_worlds(_row("g1", 10, "invasion", 0, [2, 4, 0, 2]))
    assert len(plies) == 1
    assert plies[0]["price"] == pytest.approx(2.0)
    assert plies[0]["m_worlds_ok"] == 4


def test_a_ply_with_any_void_world_keeps_the_worlds_that_landed():
    rows = _row("g1", 10, "invasion", 0, [2, 4])
    rows.append({"game": "g1", "ply": 10, "world": 2, "stratum": "invasion",
                 "actor": 0, "k": 30, "ply_frac": 0.4,
                 "pair": {"status": "VOID", "reason": "arm_not_ok"}})
    plies = AG.collapse_worlds(rows)
    assert plies[0]["m_worlds_ok"] == 2 and plies[0]["price"] == pytest.approx(3.0)
    assert plies[0]["m_worlds_void"] == 1


def test_cluster_robust_se_uses_games_not_plies():
    """Two games, four plies. Clustering on GAMES must not read the four plies
    as four independent draws."""
    plies = [{"game": "a", "price": 10.0}, {"game": "a", "price": 10.0},
             {"game": "b", "price": 0.0}, {"game": "b", "price": 0.0}]
    st = AG.cluster_stats(plies)
    assert st["n"] == 4 and st["n_clusters"] == 2
    assert st["mean"] == pytest.approx(5.0)
    # perfectly correlated within game: the 2-cluster SE is the between-game SE
    assert st["se"] == pytest.approx(5.0)
    naive = AG.cluster_stats([{"game": f"g{i}", "price": p["price"]}
                              for i, p in enumerate(plies)])
    assert naive["se"] < st["se"]


def test_cluster_se_of_a_constant_is_zero_and_z_is_none():
    st = AG.cluster_stats([{"game": "a", "price": 3.0}, {"game": "b", "price": 3.0}])
    assert st["mean"] == 3.0 and st["se"] == pytest.approx(0.0)
    assert st["z"] is None


def test_contrast_is_a_difference_of_means_with_cluster_robust_se():
    """Disjoint games. Per-game influences on the difference are
    +0.5, -0.5 (arm A) and -0.5, +0.5 (arm B); sum of squares 1.0, times the
    G/(G-1) = 4/3 finite-cluster correction -> se = sqrt(4/3)."""
    a = [{"game": "a", "price": 6.0}, {"game": "b", "price": 4.0}]
    b = [{"game": "c", "price": 1.0}, {"game": "d", "price": -1.0}]
    c = AG.contrast(a, b)
    assert c["diff"] == pytest.approx(5.0)
    assert c["n_clusters"] == 4 and c["n_shared_clusters"] == 0
    assert c["se"] == pytest.approx(math.sqrt(4.0 / 3.0))
    assert c["z"] == pytest.approx(5.0 / c["se"])


def test_contrast_shares_a_game_cluster_safely():
    """A game contributing plies to BOTH arms is de-correlated by differencing
    WITHIN that cluster, not by pretending independence. Here each game's
    influence on arm A exactly cancels its influence on arm B, so the paired
    difference has ZERO cluster variance — which independent pooling could
    never see."""
    a = [{"game": "a", "price": 6.0}, {"game": "b", "price": 4.0}]
    b = [{"game": "a", "price": 1.0}, {"game": "b", "price": -1.0}]
    c = AG.contrast(a, b)
    assert c["diff"] == pytest.approx(5.0)
    assert c["n_shared_clusters"] == 2
    assert c["se"] == pytest.approx(0.0)
    assert c["z"] is None
