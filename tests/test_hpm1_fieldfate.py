"""Row-extraction contract for the HP-M1 bag-conditioned field-fate KILL GATE.

Prereg: measurement/hpm1_fieldfate_gate_20260830/PREREG.md

What these tests actually protect (each one is a way the gate could return a
WRONG answer rather than a failure):

  * the tile-class derivation matching the prereg's published table -- if the
    engine's tile set ever moves, the disclosed feature definition rots silently;
  * the bag being the real remaining multiset -- an off-by-one bag would make
    every bag feature a lie while every number still looked plausible;
  * the two-pass join -- pass 2's features must attach to pass 1's fates for the
    SAME deployment, or the gate would be regressing noise on noise;
  * the leaf counterfactual restoring the state -- a leaked mutation would
    poison every subsequent row in the same game;
  * the fold rule actually grouping by game -- leakage across folds is exactly
    the CL-084 failure the prereg is written to avoid.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HPM1_DIR = Path(os.environ.get(
    "HPM1_DIR", REPO / "measurement/hpm1_fieldfate_gate_20260830"))


def _load(name):
    path = HPM1_DIR / f"{name}.py"
    if not path.exists():
        pytest.skip(f"{path} not present")
    spec = importlib.util.spec_from_file_location(f"hpm1_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def census():
    return _load("fieldfate_census")


@pytest.fixture(scope="module")
def gate():
    return _load("fieldfate_gate")


# --------------------------------------------------------------------------- #
# 1. the disclosed tile-class derivation                                       #
# --------------------------------------------------------------------------- #
PREREG_CLASS_TOTALS = {
    "CE0_FR1_CH1": 6, "CE0_FR2_CH0": 17, "CE0_FR3_CH0": 4, "CE0_FR4_CH0": 1,
    "CE1_FR1_CH0": 5, "CE1_FR2_CH0": 10, "CE1_FR3_CH0": 3,
    "CE2_FR1_CH0": 10, "CE2_FR2_CH0": 8,
    "CE3_FR1_CH0": 4, "CE3_FR2_CH0": 3, "CE4_FR0_CH0": 1,
}


def test_tile_classes_match_prereg_table(census):
    tct = census.tile_class_table()
    assert len(tct) == 32, "base tile KIND count moved"
    assert sum(v["count"] for v in tct.values()) == 72, "base tile count moved"
    totals = {}
    for v in tct.values():
        totals[census.class_key(v)] = totals.get(census.class_key(v), 0) + v["count"]
    assert totals == PREREG_CLASS_TOTALS, (
        "the engine tile set no longer matches PREREG 3.2's published class "
        "table -- the disclosed feature definition is stale, FAIL LOUDLY")


def test_feature_order_is_frozen_and_unique(census):
    names = census.feature_names(census.tile_class_table())
    assert len(names) == len(set(names))
    assert len(names) == 45, f"feature count drifted from the prereg's 45: {len(names)}"
    # the 28-strong BAG block, excluding the two bag x field interaction terms
    # that happen to share the prefix
    bagblock = [n for n in names if n.startswith("bag_")
                and not n.startswith("bag_closable")]
    assert len(bagblock) == 28, bagblock
    for must in ("bag_n", "bag_ge1", "bag_closable_unfin", "proj_finished_cities",
                 "invade_risk", "field_entry_cells", "ply_frac"):
        assert must in names


# --------------------------------------------------------------------------- #
# 2..5 need a real replay -- one E4 archive is enough and costs ~seconds        #
# --------------------------------------------------------------------------- #
def _one_e4(census):
    games = sorted(Path(census.REPO, "measurement/e4_games").glob("*.json"))
    import ev_loss
    for p in games:
        a = json.loads(p.read_text())
        if not a.get("ok", True):
            continue
        if ev_loss.resolve_profile_name(a) == "fixed_v1":
            return p
    pytest.skip("no fixed_v1 E4 archive on disk")


@pytest.fixture(scope="module")
def replayed(census):
    import ev_loss
    ev_loss.prepare_env("fixed_v1")
    path = _one_e4(census)
    tct = census.tile_class_table()
    classes = sorted({census.class_key(v) for v in tct.values()})
    cfg, _ = census.leaf_cfg()
    rows, gmeta = census.census_one("E4", path.name, str(path), "fixed_v1",
                                    tct, classes, cfg, None)
    return rows, gmeta, census


def test_game_reconciles(replayed):
    _, gmeta, _ = replayed
    assert gmeta["recon_ok"], gmeta.get("notes")
    assert gmeta["final_scores"] == gmeta["recorded_scores"]


def test_rows_are_deduped_and_wellformed(replayed):
    rows, gmeta, _ = replayed
    ok = [r for r in rows if r["ok"]]
    assert ok, "a real E4 game with no farmer deployment at all is implausible"
    keys = [(r["corpus"], r["game"], r["uid"]) for r in ok]
    assert len(keys) == len(set(keys)), "duplicate deployment rows"
    assert len(rows) == gmeta["n_farm_commits"], (
        "row count must equal the kernel's farmer-commit count -- a mismatch "
        "means pass 2 silently dropped or invented deployments")
    for r in ok:
        assert r["y"] in (0, 1)
        assert r["y"] == int(r["realized_pts"] > 0)
        assert 0 <= r["claim_ply"] < r["n_plies"]
        assert r["seat_role"] in ("owner", "champion")
        assert r["b_leaf"] is not None and r["b_bag"] is not None


def test_two_passes_agree_with_the_banked_kernel(replayed):
    """The fate labels must be exactly the banked Stage-A census's farm commits."""
    rows, gmeta, census = replayed
    import stage_a_census as SA
    path = _one_e4(census)
    g = SA.census_game(str(path), "fixed_v1")
    banked = {}
    for r in SA.extract_events(g):
        if r["row"] == "commit" and r["cls"] == "farm":
            banked[r["uid"]] = r
    ours = {r["uid"]: r for r in rows}
    assert set(ours) == set(banked), "farmer-deployment sets differ from the kernel"
    for uid, b in banked.items():
        o = ours[uid]
        assert o["player"] == b["player"]
        assert o["claim_ply"] == b["ply"]
        assert abs(float(o["realized_pts"]) - float(b["realized_pts"])) < 1e-9


def test_bag_is_the_real_remaining_multiset(replayed):
    """PREREG 3.1: the board-derived bag must equal the engine's own deck size at
    every claim ply. This is the whole feature block's correctness in one bit."""
    rows, _, _ = replayed
    ok = [r for r in rows if r["ok"]]
    assert all(r["bag_ok"] for r in ok), (
        "board-derived bag failed its accounting gate at some claim ply")
    # MEASURED and asserted, not assumed: the wrapper draws the next tile at the
    # END of the meeple action, so exactly one tile is drawn-but-unplaced at the
    # post-claim state. Treating it as unknown is the correct knowledge state
    # (the actor chose the meeple before it was drawn) -- but if the engine ever
    # changes WHEN it draws, this is the assertion that says so.
    assert {r["bag_minus_deck"] for r in ok} <= {0, 1}
    assert 1 in {r["bag_minus_deck"] for r in ok}
    for r in ok:
        x = r["x"]
        assert x["bag_n"] == sum(x[f"bag_ce{k}"] for k in range(5))
        assert x["bag_n"] == sum(x[f"bag_fr{k}"] for k in range(5))
        assert x["bag_ge1"] >= x["bag_ge2"] >= x["bag_ge3"] >= x["bag_ge4"]
        assert x["bag_ce0"] + x["bag_ge1"] == x["bag_n"]
        assert 0 <= x["invade_risk"] <= 1
        assert x["proj_finished_cities"] >= x["field_finished_cities"]
        assert x["bag_closable_unfin"] <= x["field_unfinished_cities"]


def test_leaf_counterfactual_restores_state(census):
    """A leaked mutation from the B-LEAF counterfactual would poison every later
    row in the same game -- assert the state is byte-identical afterwards."""
    import ev_loss
    ev_loss.prepare_env("fixed_v1")
    from carcassonne_ai import flat_leaf, rules_profile
    from carcassonne_ai.game_wrapper import Game
    import random as _r

    path = _one_e4(census)
    arch = ev_loss.load_archive(str(path))
    prof = rules_profile.activate("fixed_v1")
    _r.seed(int(arch["deck_seed"]))
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()
    cfg, _ = census.leaf_cfg()
    checked = 0
    for a in arch["actions"]:
        board, _ = game.get_next_state(board, int(a))
        st = board.state
        for p in range(st.players):
            if not st.placed_meeples[p]:
                continue
            mp = st.placed_meeples[p][0]
            before = flat_leaf.flat_virtual_score_v2_float(st, p, cfg, False)
            snap = (list(st.placed_meeples[p]), list(st.meeples))
            census.leaf_marginal(st, p, flat_leaf, cfg, mp, False)
            assert list(st.placed_meeples[p]) == snap[0]
            assert list(st.meeples) == snap[1]
            after = flat_leaf.flat_virtual_score_v2_float(st, p, cfg, False)
            assert before == after
            checked += 1
        if checked > 12:
            break
    assert checked > 0


# --------------------------------------------------------------------------- #
# 6. harness maths                                                             #
# --------------------------------------------------------------------------- #
def test_auc_ties_credited_half(gate):
    assert gate.auc([1, 2, 3, 4], [0, 0, 1, 1]) == 1.0
    assert gate.auc([4, 3, 2, 1], [0, 0, 1, 1]) == 0.0
    assert gate.auc([1, 1, 1, 1], [0, 0, 1, 1]) == 0.5
    assert gate.auc([1, 2, 2, 3], [0, 0, 1, 1]) == 0.875


def test_fold_rule_groups_by_game(gate):
    rows = [{"game": g, "y": i % 2} for g in "abcdefg" for i in range(3)]
    f = gate.folds_for(rows)
    bygame = {}
    for r, k in zip(rows, f):
        bygame.setdefault(r["game"], set()).add(int(k))
    assert all(len(v) == 1 for v in bygame.values()), "a game spans folds — LEAKAGE"
    assert set(int(x) for x in f) <= set(range(gate.N_FOLDS))


def test_game_clusters_is_row_order_invariant(gate):
    """`boot_auc_ci` resamples clusters BY INDEX (`clusters[rng.choice(keys)]`),
    so the mapping from index -> game must be a function of the DATA, not of
    the order rows arrived in the `rows` list — otherwise the same `--seed`
    silently draws a different bootstrap sample whenever a re-extraction
    reorders the underlying jsonl rows (e.g. a parallel-worker census)."""
    import random

    rows = [{"game": g, "x": {"a": i}, "y": i % 2}
            for g in ["g3", "g1", "g5", "g2", "g4"] for i in range(4)]
    shuffled = list(rows)
    random.Random(7).shuffle(shuffled)
    assert [r["game"] for r in rows] != [r["game"] for r in shuffled], \
        "the shuffle must actually change the row order for this test to mean anything"

    c1 = gate.game_clusters(rows)
    c2 = gate.game_clusters(shuffled)
    # canonical order: sorted by game id, independent of input row order
    assert sorted({r["game"] for r in rows}) == ["g1", "g2", "g3", "g4", "g5"]
    games_by_cluster_index_1 = [rows[grp[0]]["game"] for grp in c1]
    games_by_cluster_index_2 = [shuffled[grp[0]]["game"] for grp in c2]
    assert games_by_cluster_index_1 == games_by_cluster_index_2 == \
        ["g1", "g2", "g3", "g4", "g5"]

    # end-to-end: the SAME seed must draw the SAME bootstrap resamples
    # (as a sequence of GAMES) regardless of input row order (the actual
    # failure mode this guards).
    def draw(rs):
        clusters = gate.game_clusters(rs)
        rng = gate._RNG(1234)
        keys = list(range(len(clusters)))
        pick = [clusters[rng.choice(keys)] for _ in keys]
        return [rs[grp[0]]["game"] for grp in pick]

    assert draw(rows) == draw(shuffled)


def test_logistic_recovers_a_separable_signal(gate):
    import numpy as np
    rng = np.random.default_rng(0)
    X = rng.normal(size=(400, 3))
    y = (X[:, 0] + 0.5 * X[:, 1] > 0).astype(int)
    m = gate.Model(X, y)
    assert gate.auc(m.score(X), y) > 0.95
