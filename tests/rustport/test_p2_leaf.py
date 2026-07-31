"""Fast guards for the rustport P2 leaf (v2.9.2 `Bmild_cap8_curve125`).

The full G2 gate is `scripts/rustport/reconcile_leaf.py --corpus all`
(golden / midgame / K3 / distill / champ / E4 / panel).  These are the cheap
always-on subset plus the unit-level contracts a corpus replay would only catch
indirectly: the `_LEAF_VALUE_PANEL` semantic guard, the on-disk golden leaf
values, the flat-vs-engine base-score cross-check, and the two config shapes
where the Python leaf *raises* rather than computing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "measurement_infra",
           REPO / "scripts" / "rustport"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

carc_rs = pytest.importorskip("carc_rs", reason="build with `maturin develop --release`")

import reconcile_leaf as rec  # noqa: E402  (flips flat_leaf.USE_CY_LEAF to False)

from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai import flat_leaf_cy as cyleaf  # noqa: E402
from root_replay import replay_actions  # noqa: E402

GOLDEN = REPO / "tests" / "golden" / "golden_fixture.json"


@pytest.fixture(scope="module")
def fixture() -> dict:
    return json.loads(GOLDEN.read_text())


def test_python_leg_is_really_pure_python():
    """The three-leg comparison is worthless if leg 1 secretly routes to the .so."""
    assert flat_leaf.USE_CY_LEAF is False


def test_leaf_value_panel_reproduces_against_carc_rs():
    """`champion_factory._LEAF_VALUE_PANEL` — the deepest champion-leaf guard."""
    out = rec._panel_job({})
    assert out["mismatches"] == []
    assert out["disk_values"] == 4


def test_golden_frozen_leaf_values_from_disk(fixture):
    """Every leaf value FROZEN IN THE FIXTURE, re-judged by Rust.

    56 positions x (3 dialects x 2 POVs + 1 base pair) = 448 values, compared
    against the file — not against a live Python re-computation.
    """
    total = 0
    for seed_s, g in sorted(fixture["games"].items(), key=lambda kv: int(kv[0])):
        seed = int(g.get("deck_seed", seed_s))
        frozen = [p for p in fixture["positions"] if int(p["deck_seed"]) == seed]
        if not frozen:
            continue
        out = rec._golden_disk_job({
            "label": f"goldendisk/{seed}", "deck_seed": seed,
            "actions": [int(a) for a in g["actions"]], "frozen": frozen,
        })
        assert out["mismatches"] == [], out["mismatches"][:3]
        total += out["disk_values"]
    # 6 dialect values (3 x 2 POVs) + 2 base-score values per position
    assert total == 8 * len(fixture["positions"]) == 448


def test_three_legs_agree_on_one_golden_game(fixture):
    """Python-flat vs Cython-flat vs Rust, every ply, the whole config matrix."""
    seed_s, g = sorted(fixture["games"].items(), key=lambda kv: int(kv[0]))[0]
    out = rec._replay_job({
        "label": f"golden/{seed_s}", "deck_seed": int(g.get("deck_seed", seed_s)),
        "actions": [int(a) for a in g["actions"]], "stride": 1, "configs": "all",
    })
    assert out["mismatches"] == [], out["mismatches"][:3]
    assert out["values"] > 5000
    # every config in the matrix was actually exercised
    assert set(out["by_config"]) == set(rec._cfgs("all"))


def test_float_leg_is_compared_bit_exactly(fixture):
    """The float leaf is what `leaf_quantize: float` makes production use; the
    gate must be bit equality, not `int(round(...))` agreement."""
    seed_s, g = sorted(fixture["games"].items(), key=lambda kv: int(kv[0]))[0]
    acts = [int(a) for a in g["actions"]]
    cfg = rec._cfgs("core")["prod-curve125"]
    rcfg = rec._to_rs(cfg)
    game, board = replay_actions(int(seed_s), acts, 0)
    ms = carc_rs.MirrorState.from_seed(str(seed_s))
    seen_fractional = 0
    for i, a in enumerate(acts):
        for p in (0, 1):
            f_py = float(flat_leaf.flat_virtual_score_v2_float(board.state, p, cfg))
            f_cy = float(cyleaf.flat_virtual_score_v2_cy_float(board.state, p, cfg, False))
            f_rs = float(ms.leaf_value_float(p, rcfg))
            assert f_py.hex() == f_cy.hex() == f_rs.hex(), f"ply {i} pov {p}"
            if f_rs != int(f_rs):
                seen_fractional += 1
        board, _ = game.get_next_state(board, int(a))
        ms.advance(int(a))
    assert seen_fractional > 50, "the float leg must actually carry sub-integer values"


def test_flat_decomposition_base_score_matches_the_engine_route():
    """`flat_base_score` computed from the union-find decomposition must equal
    the engine's own clone + `count_final_scores` (P1's route) at every ply."""
    ms = carc_rs.MirrorState.from_seed("4242")
    plies = 0
    while not ms.is_terminal() and plies < 400:
        for p in (0, 1):
            assert ms.flat_base_score_decomp(p) == ms.flat_base_score(p), f"ply {plies}"
        ms.advance(ms.legal_actions()[0])
        plies += 1
    assert plies > 100


def test_unsupported_configs_raise_like_python():
    from carcassonne_ai.virtual_score_v2 import LeafConfig

    ms = carc_rs.MirrorState.from_seed("1")
    tc = LeafConfig(closure_p={1: 0.5}, bonus_cap=8.0, opp_bonus_cap=8.0,
                    tile_counting_closure=True)
    with pytest.raises(NotImplementedError):
        ms.leaf_value(0, rec._to_rs(tc))
    slack = LeafConfig(closure_p={1: 0.5}, bonus_cap=8.0, opp_bonus_cap=8.0,
                       closure_continuous_slack=0.5)
    with pytest.raises(NotImplementedError):
        ms.leaf_value(0, rec._to_rs(slack))
    # Term R without a curve is a ValueError in `flat_return_term`
    no_curve = LeafConfig(closure_p={1: 0.5}, bonus_cap=8.0, opp_bonus_cap=8.0,
                          v29_meeple_return_k=1.0)
    with pytest.raises(ValueError):
        ms.leaf_value(0, rec._to_rs(no_curve))


def test_curve125_values_are_the_governance_values():
    """PRODUCTION.yaml says assert curve VALUES, not fingerprints."""
    assert rec._CURVE125 == (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)
    ms = carc_rs.MirrorState.from_seed("1")
    for i, want in enumerate(rec._CURVE125):
        ms.make_empty_panel_state(i, 3)   # curve[3] == 0.0 on both curves
        assert float(ms.leaf_value_float(0, carc_rs.LeafConfigRs.curve125())) == want


def test_bag_stats_matches_python():
    from carcassonne_ai.flat_leaf import _bag_stats

    fx = json.loads(GOLDEN.read_text())
    seed_s, g = sorted(fx["games"].items(), key=lambda kv: int(kv[0]))[0]
    acts = [int(a) for a in g["actions"]]
    game, board = replay_actions(int(seed_s), acts, 0)
    ms = carc_rs.MirrorState.from_seed(str(seed_s))
    for a in acts:
        assert tuple(ms.bag_stats()) == tuple(_bag_stats(board.state))
        board, _ = game.get_next_state(board, int(a))
        ms.advance(int(a))
