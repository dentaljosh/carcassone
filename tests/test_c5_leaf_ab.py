"""C5 Stage-0 leaf A/B harness tests (design: measurement/classical_search/
C5_LEAF_RETUNE_DESIGN.md §"Stage 0").

Covers the S0 blocking gate for candidate-leaf A/B in the clairvoyant PUCT screen
harness (scripts/classical_search/eval_puct_priors.py --cand-leaf-json):

  * --cand-leaf-json parsing / field coercion (closure_p int keys, v29_meeple_curve
    tuple, null -> curve OFF, replace-fields on DEFAULT_CONFIG, unknown-field raise);
  * cy-float-path guard rejects object-forcing leaf terms;
  * CONFIG mirror: candidate resolved LeafConfig == champion (DEFAULT_CONFIG) when the
    flag is absent, and != when it differs (design S0 item 2);
  * OVERRIDE REACHES THE HOT PATH: a different leaf cfg (bonus_cap 5 vs 8) yields a
    different Cython float leaf value on at least one board of a played game (proves
    the override is not silently dropped by a cached/global config, .pyx included);
  * BIT-EXACT MIRROR GATE (the S0 gate): --cand-leaf-json = the champion leaf verbatim
    reproduces the no-flag run move-for-move on shared seeds (identical per-game
    records + summary), so the default path is byte-identical and the override plumbing
    is provably transparent when it equals the default.

The harness sets the production v2.9 Bmild_cap8 leaf env via setdefault at import, so
importing eval_puct_priors FIRST keeps DEFAULT_CONFIG the cap8 production leaf here.
"""
from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "classical_search" / "eval_puct_priors.py"

_spec = importlib.util.spec_from_file_location("eval_puct_priors", SCRIPT)
epp = importlib.util.module_from_spec(_spec)
sys.modules["eval_puct_priors"] = epp  # fork-Pool workers unpickle _play_one by module name
_spec.loader.exec_module(epp)

sys.path.insert(0, str(REPO / "src"))
from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai import virtual_score_v2 as vs2  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402

DEF = epp.DEFAULT_CONFIG


# --------------------------------------------------------------------------- #
# --cand-leaf-json parsing + field coercion                                    #
# --------------------------------------------------------------------------- #
def test_absent_flag_is_none():
    assert epp._load_cand_leaf_cfg(None) is None
    assert epp._load_cand_leaf_cfg("") is None


def test_replace_fields_on_default():
    cfg = epp._load_cand_leaf_cfg('{"bonus_cap": 5, "opp_bonus_cap": 5}')
    assert cfg.bonus_cap == 5.0 and cfg.opp_bonus_cap == 5.0
    # every other field is inherited verbatim from DEFAULT_CONFIG (replace-fields)
    assert cfg.closure_p == DEF.closure_p
    assert cfg.v29_meeple_curve == DEF.v29_meeple_curve
    assert cfg.meeple_k == DEF.meeple_k


def test_closure_p_keys_coerced_to_int():
    cfg = epp._load_cand_leaf_cfg('{"closure_p": {"1": 0.4, "2": 0.16, "3": 0.04}}')
    assert cfg.closure_p == {1: 0.4, 2: 0.16, 3: 0.04}
    assert all(isinstance(k, int) for k in cfg.closure_p)  # not "1"/"2"/"3"


def test_curve_coerced_to_tuple_and_null_is_off():
    cfg = epp._load_cand_leaf_cfg('{"v29_meeple_curve": [-6, -3, 0, 0, 1, 2, 3, 4]}')
    assert cfg.v29_meeple_curve == (-6.0, -3.0, 0.0, 0.0, 1.0, 2.0, 3.0, 4.0)
    assert isinstance(cfg.v29_meeple_curve, tuple)
    off = epp._load_cand_leaf_cfg('{"v29_meeple_curve": null, "meeple_k": 2.0}')
    assert off.v29_meeple_curve is None and off.meeple_k == 2.0


def test_unknown_field_raises():
    with pytest.raises(ValueError):
        epp._load_cand_leaf_cfg('{"bogus_knob": 1}')


def test_non_object_json_raises():
    with pytest.raises(ValueError):
        epp._load_cand_leaf_cfg("[1, 2, 3]")


def test_path_or_inline(tmp_path):
    p = tmp_path / "leaf.json"
    p.write_text('{"bonus_cap": 12}')
    assert epp._load_cand_leaf_cfg(str(p)).bonus_cap == 12.0
    assert epp._load_cand_leaf_cfg('{"bonus_cap": 12}').bonus_cap == 12.0


# --------------------------------------------------------------------------- #
# cy-float-path guard                                                          #
# --------------------------------------------------------------------------- #
def test_cy_path_guard_accepts_screen_axes():
    # all 6 pre-registered screen axes stay on the cy float path -> no raise
    for spec in ('{"bonus_cap": 5, "opp_bonus_cap": 5}',
                 '{"opp_bonus_cap": 4}',
                 '{"closure_p": {"1": 0.4, "2": 0.16, "3": 0.04}}',
                 '{"v29_meeple_curve": [-6, -3, -0.75, 0, 1.5, 2.25, 3, 3.75]}',
                 '{"v29_meeple_curve": null, "meeple_k": 2.0}',
                 '{"bag_close": true}'):
        epp._assert_cy_float_path(epp._load_cand_leaf_cfg(spec))  # must not raise


def test_cy_path_guard_rejects_object_path_terms():
    with pytest.raises(ValueError):        # v2.8 -> object path
        epp._assert_cy_float_path(epp._load_cand_leaf_cfg('{"v28_meeple_k": 1.0}'))
    with pytest.raises(ValueError):        # v2.9 non-curve -> object path
        epp._assert_cy_float_path(epp._load_cand_leaf_cfg('{"v29_punish_k": 1.0}'))
    with pytest.raises(ValueError):        # deck-aware closure -> non-cy path
        epp._assert_cy_float_path(epp._load_cand_leaf_cfg('{"tile_counting_closure": true}'))


# --------------------------------------------------------------------------- #
# CONFIG mirror: cand-side LeafConfig == champ when absent, != when it differs  #
# --------------------------------------------------------------------------- #
def test_config_mirror_equal_when_absent():
    from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig
    # flag absent -> candidate leaf resolves to DEFAULT_CONFIG == champion side
    cand = HeuristicPriorConfig(leaf_cfg=(epp._load_cand_leaf_cfg(None) or DEF))
    assert cand.resolved_leaf_cfg() == DEF


def test_config_mirror_differs_when_flag_differs():
    from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig
    cand = HeuristicPriorConfig(leaf_cfg=epp._load_cand_leaf_cfg('{"bonus_cap": 5}'))
    assert cand.resolved_leaf_cfg() != DEF
    assert cand.resolved_leaf_cfg().bonus_cap == 5.0 and DEF.bonus_cap == 8.0


# --------------------------------------------------------------------------- #
# OVERRIDE REACHES THE CYTHON HOT PATH: cap5 != cap8 leaf value on some board   #
# --------------------------------------------------------------------------- #
def _played_states(seed: int, n_moves: int):
    """Play a fixed pseudo-random game from the init board, yielding states."""
    rng = random.Random(seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    states = [board.state]
    for _ in range(n_moves):
        if game.get_game_ended(board, 0) != 0.0:
            break
        legal = [a for a, ok in enumerate(game.get_valid_moves(board)) if ok]
        board, _ = game.get_next_state(board, rng.choice(legal))
        states.append(board.state)
    return states


def test_override_changes_cython_leaf_value():
    # cap5 must clip a large anticipation bonus that cap8 does not -> the CYTHON
    # float leaf (USE_CY_LEAF=1 in the harness env) differs on at least one board.
    cap8 = epp._load_cand_leaf_cfg(None) or DEF
    cap5 = epp._load_cand_leaf_cfg('{"bonus_cap": 5, "opp_bonus_cap": 5}')
    assert cap8.bonus_cap == 8.0 and cap5.bonus_cap == 5.0     # env is the cap8 leaf
    diffs = 0
    for st in _played_states(seed=9990004321, n_moves=120):
        if st.players != 2:
            continue
        for player in (0, 1):
            v8 = flat_leaf.flat_virtual_score_v2_float(st, player, cap8, False)
            v5 = flat_leaf.flat_virtual_score_v2_float(st, player, cap5, False)
            if v8 != v5:
                diffs += 1
    assert diffs > 0, "cap5 override never reached the leaf hot path (silently dropped?)"


def test_override_reaches_prior_evaluator():
    # the same override reaches the PRODUCTION evaluator (make_heuristic_prior_evaluator
    # -> flat_virtual_score_v2_float): value/priors differ on at least one board.
    from carcassonne_ai.heuristic_prior_mcts import (
        HeuristicPriorConfig, make_heuristic_prior_evaluator,
    )
    game = Game(enable_legal_moves_cache=True)
    ev8 = make_heuristic_prior_evaluator(game, HeuristicPriorConfig(leaf_cfg=DEF))
    ev5 = make_heuristic_prior_evaluator(
        game, HeuristicPriorConfig(leaf_cfg=epp._load_cand_leaf_cfg('{"bonus_cap": 5, "opp_bonus_cap": 5}')))
    # rebuild boards (the evaluator needs a Board, not a bare state)
    rng = random.Random(9990004321)
    board = game.get_init_board()
    changed = False
    for _ in range(120):
        if game.get_game_ended(board, 0) != 0.0:
            break
        _, val8 = ev8(board)
        _, val5 = ev5(board)
        if val8 != val5:
            changed = True
            break
        legal = [a for a, ok in enumerate(game.get_valid_moves(board)) if ok]
        board, _ = game.get_next_state(board, rng.choice(legal))
    assert changed, "override did not change the prior-evaluator value on any board"


# --------------------------------------------------------------------------- #
# BIT-EXACT MIRROR GATE (the S0 gate)                                          #
# --------------------------------------------------------------------------- #
def _run_cell(tmp: Path, sub: str, extra: list[str]):
    # The fork-Pool pickles _play_one by module name; make sure sys.modules
    # ["eval_puct_priors"] resolves to THIS module's copy during the Pool run
    # (another test file loads the same script under the same name at collection),
    # then restore so sibling harness tests keep their own binding.
    prev = sys.modules.get("eval_puct_priors")
    sys.modules["eval_puct_priors"] = epp
    try:
        rc = epp.main([
            "--candidate", "puct", "--opponent", "puct",
            "--cand-sims", "16", "--c-puct", "1.5", "--tau-p", "5",
            "--leaf-quantize", "float", "--final-select", "visits", "--value-norm", "15",
            "--exact-k", "2", "--n", "4", "--paired", "--workers", "2",
            "--seed-start", "9990000000",
            "--out-root", str(tmp), "--out-subdir", sub, "--no-results-csv"] + extra)
    finally:
        if prev is not None:
            sys.modules["eval_puct_priors"] = prev
    assert rc == 0
    out = tmp / sub
    recs = {p.name: json.load(open(p)) for p in out.glob("seed*.json")}
    summ = json.load(open(out / "summary.json"))
    man = json.load(open(out / "manifest.json"))["config"]
    return recs, summ, man


def test_mirror_champion_verbatim_bit_exact(tmp_path):
    # champion leaf VERBATIM, spelled out through the override path (exercising the
    # closure_p / curve coercions), must resolve to DEFAULT_CONFIG -> identical play.
    champ = DEF
    mirror = json.dumps({
        "bonus_cap": champ.bonus_cap, "opp_bonus_cap": champ.opp_bonus_cap,
        "closure_p": {str(k): v for k, v in champ.closure_p.items()},
        "v29_meeple_curve": (list(champ.v29_meeple_curve)
                             if champ.v29_meeple_curve is not None else None),
        "meeple_k": champ.meeple_k,
    })
    base_recs, base_summ, base_man = _run_cell(tmp_path, "noflag", [])
    over_recs, over_summ, over_man = _run_cell(tmp_path, "mirror", ["--cand-leaf-json", mirror])

    assert base_recs and set(base_recs) == set(over_recs)   # same seeds/seats present
    for name in base_recs:
        b, o = base_recs[name], over_recs[name]
        for k in ("diff", "score_p0", "score_p1", "moves", "deck_hash",
                  "cand_prefix_moves", "cand_exact_moves", "won_by_cand", "drew"):
            assert b[k] == o[k], f"{name}: {k} differs (no-flag {b[k]} vs mirror {o[k]})"
    # identical games -> identical aggregate verdict
    for k in ("W", "L", "D", "paired_mean_margin", "avg_diff"):
        assert base_summ[k] == over_summ[k], f"summary {k} differs"

    # manifest provenance: per-side leaf hashes present; mirror == champ (== no-flag)
    assert base_man["cand_leaf_hash"] == base_man["champ_leaf_hash"]
    assert over_man["cand_leaf_hash"] == over_man["champ_leaf_hash"]
    assert over_man["cand_leaf_hash"] == base_man["cand_leaf_hash"]
    assert base_man["cand_leaf_json"] is None and over_man["cand_leaf_json"] == mirror


def test_mirror_manifest_records_distinct_hashes_when_leaf_differs(tmp_path):
    _, _, man = _run_cell(tmp_path, "cap5",
                          ["--cand-leaf-json", '{"bonus_cap": 5, "opp_bonus_cap": 5}'])
    # candidate leaf differs from the (untouched) champion side -> hashes must differ
    assert man["cand_leaf_hash"] != man["champ_leaf_hash"]
    assert man["cand_leaf_cfg"]["bonus_cap"] == 5.0
    assert man["champ_leaf_cfg"]["bonus_cap"] == DEF.bonus_cap == 8.0
    # the champion PUCT opponent block still carries the env DEFAULT_CONFIG leaf
    assert man["opponent"]["leaf_cfg"]["bonus_cap"] == 8.0
