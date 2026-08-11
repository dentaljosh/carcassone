"""Configurable-OPPONENT tests for the fair PUCT harness
(scripts/classical_search/eval_fair_puct.py --opponent {h800,fair-champion,net}).

The sibling of tests/test_c5_fair_leaf_ab.py (which covers --cand-leaf-json). Where
that file guards the CANDIDATE-side leaf override, this one guards the OPPONENT axis:

  (a) DEFAULT PATH UNCHANGED: --opponent h800 builds the byte-identical fixed rung
      (HeuristicMCTS @ rung_sims on env DEFAULT_CONFIG, NO endgame handoff, seed+1),
      and _assert_rung_is_ruler still gates the fair-netprior arm.
  (b) TWO-SIDED curve125 AT RUNTIME: in a head-to-head BOTH agents resolve the frozen
      curve125 production leaf — asserted on the leaf the constructed AGENT actually
      searches with (cfg.resolved_leaf_cfg()), not merely on the cfg main() built —
      while env DEFAULT_CONFIG (the h800 ruler) provably never moves. This is the
      `os.environ.setdefault` trap the CURVE125 block in the harness warns about.
  (c) THE OPPONENT IS A REFERENCE, NOT A CANDIDATE: --cand-leaf-json moves the
      candidate's leaf ONLY; the head-to-head opponent stays curve125 (mirroring the
      way the h800 rung never takes the override).
  (d) CROSS-REP: the opponent's representation is inferred from ITS OWN checkpoint
      independently of --net, so a sighted(81ch/42) vs non-sighted(78ch/10) match
      encodes each side on its own encoder.
  (e) SYMMETRY: seat alternation + deck pairing are preserved (a head-to-head where
      one side owned a seat would be worthless), and both sides share every search
      knob so the swap is single-variable.
  (f) SUMMARY SEMANTICS: `diff` is candidate-minus-opponent, and the head-to-head
      "prefix ms/move" compares prefix-to-prefix (the driver-timed rung_secs includes
      the endgame solve, so charging it against the candidate's solver-free prefix
      made two IDENTICAL agents look ~4x apart).
  (g) ASYMMETRIC BUDGETS (--opp-sims / --opp-k-dets): the two deliberate exceptions to
      (e)'s shared-knob rule. UNSET is the load-bearing case — the opponent must fall
      back to the shared --sims/--k-dets so every symmetric run stays byte-identical;
      SET moves ONLY the opponent, is rejected for the h800 rung (which owns
      --rung-sims and is not a PIMC agent at all), and is surfaced per-side in the
      label/manifest/summary so no reader can mistake one side's budget for the
      match's. --opp-k-dets is what makes CL-060's re-open trigger expressible:
      candidate k8x1376 (11008) vs the k4x688 (2752) DEPLOY champion.

No games are played here (agent CONSTRUCTION + config resolution only), so the whole
file runs in seconds. Importing eval_fair_puct FIRST keeps DEFAULT_CONFIG the
production cap8/curve100 leaf (the harness sets it via setdefault at import).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "classical_search" / "eval_fair_puct.py"

_spec = importlib.util.spec_from_file_location("eval_fair_puct", SCRIPT)
efp = importlib.util.module_from_spec(_spec)
sys.modules["eval_fair_puct"] = efp
_spec.loader.exec_module(efp)

sys.path.insert(0, str(REPO / "src"))
from carcassonne_ai.game_wrapper import Game  # noqa: E402

DEF = efp.DEFAULT_CONFIG
CFG_DICT = {"c_puct": 1.5, "tau_p": 5.0, "leaf_quantize": "float",
            "final_select": "visits", "value_norm": 15.0}


def _agent_leaf(agent):
    """The leaf the constructed agent ACTUALLY searches with."""
    prefix = agent._prefix
    if hasattr(prefix, "_cfg"):                 # Fair/HeuristicPriorAgent
        return prefix._cfg.resolved_leaf_cfg()
    raise AssertionError(f"no resolvable cfg on {type(prefix).__name__}")


# --------------------------------------------------------------------------- #
# (a) the h800 DEFAULT path
# --------------------------------------------------------------------------- #
def test_h800_default_builds_the_unchanged_fixed_rung():
    rung = efp._make_opponent("h800", CFG_DICT, 8, 2, 2, 800, seed=1)
    assert isinstance(rung, efp._RungPrefix)
    # the ruler: env DEFAULT_CONFIG (curve100), c=3.0, rung_sims, seed+1
    assert efp._leaf_hash(rung._m._leaf_cfg) == efp.RUNG_CURVE100_LEAF_HASH
    assert rung._m.c == efp.RUNG_C
    # and NO endgame handoff — the fixed-yardstick convention
    assert not hasattr(rung, "exact_moves")
    assert not isinstance(rung, efp._MarginalizedHandoff)


def test_h800_rung_ignores_a_candidate_leaf_override():
    """The ruler must not move even when a curve125 cfg is in play."""
    rung = efp._make_opponent("h800", CFG_DICT, 8, 2, 2, 800, seed=1,
                              opp_leaf_cfg=efp._curve125_leaf_cfg())
    assert efp._leaf_hash(rung._m._leaf_cfg) == efp.RUNG_CURVE100_LEAF_HASH


def test_h800_opponent_stats_are_all_zero():
    """_opp_stats over a rung (no counters) must leave every additive field at its
    default, so an h800 GameResult row is unchanged in every pre-existing field."""
    rung = efp._make_opponent("h800", CFG_DICT, 8, 2, 2, 800, seed=1)
    st = efp._opp_stats(rung)
    assert st == {"opp_prefix_moves": 0, "opp_exact_moves": 0, "opp_prefix_secs": 0.0,
                  "opp_solver_secs": 0.0, "opp_timeouts": 0, "opp_latch_k": None}


def test_assert_rung_is_ruler_still_passes_under_canon_env():
    assert efp._assert_rung_is_ruler() == efp.RUNG_CURVE100_LEAF_HASH


def test_opponent_mode_constants():
    # `bare-net` (BLIND vs SIGHTED, added 2026-07-27) is additive, and `greedy`
    # (tier1 luck-floor cell, added 2026-07-27, c236150) slots at index 1; the
    # legacy modes keep their relative order. bare-net stays deliberately NOT a
    # head-to-head.
    assert efp.OPPONENT_MODES[:4] == ("h800", "greedy", "fair-champion", "net")
    assert efp.OPPONENT_MODES == ("h800", "greedy", "fair-champion", "net", "bare-net")
    # h800 is deliberately NOT a head-to-head: it is the fixed ruler, so it keeps the
    # curve100 leaf, takes no endgame, and skips the two-sided curve125 injection.
    # bare-net is excluded for the mirror-image reason: its opponent must NOT get our
    # curve125 leaf, the endgame tail or the shared-knob framing (see tests/
    # test_bare_net_opponent.py).
    assert efp._HEAD_TO_HEAD == ("fair-champion", "net")
    assert "h800" not in efp._HEAD_TO_HEAD
    assert "bare-net" not in efp._HEAD_TO_HEAD


def test_argparse_default_opponent_is_h800():
    """The default must stay h800 — every pre-existing arm/result is an h800 result."""
    import argparse
    with pytest.raises(SystemExit):          # --help exits 0
        efp.main(["--help"])
    # inspect the declared default directly off a rebuilt parser action
    src = SCRIPT.read_text()
    assert 'ap.add_argument("--opponent", choices=OPPONENT_MODES, default="h800"' in src


# --------------------------------------------------------------------------- #
# (b) two-sided curve125 AT RUNTIME + the setdefault trap
# --------------------------------------------------------------------------- #
def test_env_default_config_is_the_curve100_ruler():
    """The premise of the whole injection scheme: _CANON_ENV pins curve100."""
    assert tuple(float(x) for x in DEF.v29_meeple_curve) == efp.CURVE100
    assert efp._leaf_hash(DEF) == efp.RUNG_CURVE100_LEAF_HASH


def test_curve125_cfg_matches_both_hash_dialects():
    prov = efp._assert_netprior_leaf(efp._curve125_leaf_cfg())
    assert prov["leaf_hash"] == efp.CURVE125_LEAF_HASH
    assert prov["frozen_config_hash_champ_dialect"] == efp.CURVE125_FROZEN_HASH


def test_fair_champion_opponent_resolves_curve125_at_runtime():
    opp = efp._make_opponent("fair-champion", CFG_DICT, 8, 2, 2, 800, seed=1,
                             opp_leaf_cfg=efp._curve125_leaf_cfg())
    leaf = _agent_leaf(opp)
    assert tuple(float(x) for x in leaf.v29_meeple_curve) == efp.CURVE125
    assert efp._leaf_hash(leaf) == efp.CURVE125_LEAF_HASH
    # ...and it IS wrapped in the shared marginalized endgame handoff
    assert isinstance(opp, efp._MarginalizedHandoff)


def test_both_sides_resolve_the_same_curve125_leaf():
    c125 = efp._curve125_leaf_cfg()
    net, rep = efp._random_net_rep(sighted=True)
    cand = efp._make_champion("fair-netprior", efp._cfg_from_dict(CFG_DICT, c125),
                              8, 2, 2, 1, Game(enable_legal_moves_cache=True),
                              net=net, sighted_game=Game(sighted=True), rep=rep)
    opp = efp._make_opponent("fair-champion", CFG_DICT, 8, 2, 2, 800, seed=1,
                             opp_leaf_cfg=c125)
    assert efp._leaf_hash(_agent_leaf(cand)) == efp._leaf_hash(_agent_leaf(opp))
    assert efp._leaf_hash(_agent_leaf(cand)) == efp.CURVE125_LEAF_HASH


def test_injection_never_moves_env_default_config():
    """The setdefault trap: building both curve125 sides must leave DEFAULT_CONFIG
    (the h800 ruler) exactly where it was."""
    before = efp._leaf_hash(DEF)
    c125 = efp._curve125_leaf_cfg()
    efp._make_opponent("fair-champion", CFG_DICT, 8, 2, 2, 800, seed=1, opp_leaf_cfg=c125)
    efp._make_opponent("h800", CFG_DICT, 8, 2, 2, 800, seed=1)
    assert efp._leaf_hash(DEF) == before == efp.RUNG_CURVE100_LEAF_HASH
    assert efp._leaf_hash(c125) != efp._leaf_hash(DEF)


def test_assert_netprior_leaf_rejects_a_curve100_side():
    """A curve100 leaf on either side must fail LOUD (the curve-VALUES check)."""
    with pytest.raises(SystemExit, match="expected curve125"):
        efp._assert_netprior_leaf(DEF, side="opponent", tag="head-to-head")


# --------------------------------------------------------------------------- #
# (c) the opponent is a REFERENCE side — --cand-leaf-json must not move it
# --------------------------------------------------------------------------- #
def test_cand_leaf_override_does_not_move_the_opponent():
    """Mirrors the h800 rule: the reference side never takes the candidate override."""
    import dataclasses as dc
    cand_override = dc.replace(DEF, bonus_cap=5, opp_bonus_cap=5)
    cand = efp._make_champion("fair", efp._cfg_from_dict(CFG_DICT, cand_override),
                              8, 2, 2, 1, Game(enable_legal_moves_cache=True))
    opp = efp._make_opponent("fair-champion", CFG_DICT, 8, 2, 2, 800, seed=1,
                             opp_leaf_cfg=efp._curve125_leaf_cfg())
    assert efp._leaf_hash(_agent_leaf(cand)) != efp._leaf_hash(_agent_leaf(opp))
    assert efp._leaf_hash(_agent_leaf(opp)) == efp.CURVE125_LEAF_HASH


# --------------------------------------------------------------------------- #
# (d) cross-rep: each side encodes on its OWN rep
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("sighted,exp_ch,exp_sc", [(True, 81, 42), (False, 78, 10)])
def test_net_opponent_honours_its_own_rep(sighted, exp_ch, exp_sc):
    net, rep = efp._random_net_rep(sighted=sighted)
    assert (rep["n_input_channels"], rep["n_scalar_features"]) == (exp_ch, exp_sc)
    opp = efp._make_opponent("net", CFG_DICT, 8, 2, 2, 800, seed=1,
                             opp_leaf_cfg=efp._curve125_leaf_cfg(),
                             net=net, sighted_game=Game(sighted=sighted), rep=rep)
    assert isinstance(opp, efp._MarginalizedHandoff)
    assert efp._leaf_hash(_agent_leaf(opp)) == efp.CURVE125_LEAF_HASH


def test_cross_rep_sides_use_different_encoders():
    """The net-vs-net cell is deliberately cross-rep; a shared encoder would silently
    feed one policy head garbage planes."""
    c125 = efp._curve125_leaf_cfg()
    cnet, crep = efp._random_net_rep(sighted=True)
    onet, orep = efp._random_net_rep(sighted=False)
    cand = efp._make_champion("fair-netprior", efp._cfg_from_dict(CFG_DICT, c125),
                              8, 2, 2, 1, Game(enable_legal_moves_cache=True),
                              net=cnet, sighted_game=Game(sighted=True), rep=crep)
    opp = efp._make_opponent("net", CFG_DICT, 8, 2, 2, 800, seed=1, opp_leaf_cfg=c125,
                             net=onet, sighted_game=Game(sighted=False), rep=orep)
    assert crep["sighted"] is True and orep["sighted"] is False
    assert crep["n_input_channels"] != orep["n_input_channels"]
    # both still share the SAME frozen value leaf — only the priors differ
    assert efp._leaf_hash(_agent_leaf(cand)) == efp._leaf_hash(_agent_leaf(opp))


def test_unknown_opponent_mode_fails_loud():
    with pytest.raises(ValueError, match="unknown opponent mode"):
        efp._make_opponent("bogus", CFG_DICT, 8, 2, 2, 800, seed=1)


# --------------------------------------------------------------------------- #
# (e) symmetry: seat alternation + shared knobs
# --------------------------------------------------------------------------- #
def test_seat_alternation_and_deck_pairing_preserved():
    """--paired must give every deck BOTH seats (the candidate's a_seat is balanced),
    and unpaired must still alternate."""
    work = efp._build_work(13_000_000_000, 4, paired=True)
    by_seed = {}
    for seed, seat in work:
        by_seed.setdefault(seed, set()).add(seat)
    assert len(by_seed) == 2
    assert all(seats == {0, 1} for seats in by_seed.values())
    unpaired = efp._build_work(13_000_000_000, 4, paired=False)
    assert [s for _, s in unpaired] == [0, 1, 0, 1]


def test_head_to_head_sides_share_every_search_knob():
    """A prior-swap is only single-variable if the two sides' cfgs differ in NOTHING
    but the prior source (and both carry the same frozen leaf)."""
    c125 = efp._curve125_leaf_cfg()
    cand_cfg = efp._cfg_from_dict(CFG_DICT, c125)
    opp_cfg = efp._cfg_from_dict(CFG_DICT, c125)
    for k in ("c_puct", "tau_p", "leaf_quantize", "final_select", "value_norm"):
        assert getattr(cand_cfg, k) == getattr(opp_cfg, k)
    assert efp._leaf_hash(cand_cfg.resolved_leaf_cfg()) == \
           efp._leaf_hash(opp_cfg.resolved_leaf_cfg())


def test_prod_knobs_match_the_argparse_defaults():
    """The head-to-head opponent is 'the PRODUCTION champion' only because the shared
    knobs default to production; if a default ever drifts, _prod_deviations must catch
    it rather than let the cell silently stop being 'vs production'."""
    class A:
        pass
    a = A()
    for k, v in efp.PROD_KNOBS.items():
        setattr(a, k, v)
    assert efp._prod_deviations(a) == []
    a.k_dets = 2
    a.sims = 32
    dev = efp._prod_deviations(a)
    assert any("k_dets" in d for d in dev) and any("sims" in d for d in dev)


# --------------------------------------------------------------------------- #
# (f) result semantics
# --------------------------------------------------------------------------- #
def _mk(seed, a_seat, diff, opponent="h800", **kw):
    return efp.GameResult(
        seed=seed, a_seat=a_seat, info="fair", exact_k=2, k_dets=2, sims=32,
        rung_sims=800, score_p0=0, score_p1=0, diff=diff, won_by_champ=(diff > 0),
        drew=(diff == 0), elapsed_s=0.0, moves=1, opponent=opponent, **kw)


def test_paired_z_averages_the_two_seats_per_deck():
    """Neither side may own a seat: the paired margin is the seat-balanced mean."""
    res = [_mk(1, 0, +10), _mk(1, 1, -4), _mk(2, 0, +2), _mk(2, 1, +2)]
    mean, z, npair = efp._paired_z(res)
    assert npair == 2
    assert mean == pytest.approx((3.0 + 2.0) / 2)


def test_head_to_head_ms_per_move_compares_prefix_to_prefix():
    """The regression this guards: rung_secs is DRIVER-timed and includes the endgame
    solve; the candidate's champ_prefix_secs does not. Charging the opponent's solver
    time into a prefix comparison made two IDENTICAL agents look ~4x apart."""
    res = [_mk(1, 0, 0, opponent="fair-champion",
               champ_prefix_moves=10, champ_prefix_secs=1.0,
               rung_moves=10, rung_secs=41.0,          # 1.0s prefix + 40s of solving
               opp_prefix_moves=10, opp_prefix_secs=1.0, opp_solver_secs=40.0)]
    summ = efp._summary(res, "fair", 2, 2, 32, 800, opponent="fair-champion")
    # prefix-to-prefix => ~1.0x, NOT 41x
    assert summ["champ_prefix_ms_per_move"] == pytest.approx(100.0)
    assert summ["rung_ms_per_move"] == pytest.approx(100.0)


def test_h800_ms_per_move_keeps_the_historical_driver_timing():
    res = [_mk(1, 0, 0, opponent="h800", champ_prefix_moves=10, champ_prefix_secs=1.0,
               rung_moves=10, rung_secs=5.0)]
    summ = efp._summary(res, "fair", 2, 2, 32, 800, opponent="h800")
    assert summ["rung_ms_per_move"] == pytest.approx(500.0)
    assert summ["opponent"] == "h800"
    assert summ["opponent_label"] == "HeuristicMCTS(h800)"


def test_summary_records_the_opponent_mode():
    res = [_mk(1, 0, +5, opponent="net"), _mk(1, 1, -5, opponent="net")]
    summ = efp._summary(res, "fair-netprior", 2, 2, 32, 800, opponent="net",
                        opp_label="FAIR NET-PRIOR agent (x.pt)")
    assert summ["opponent"] == "net"
    assert summ["opponent_label"] == "FAIR NET-PRIOR agent (x.pt)"


def test_old_result_json_still_loads_into_the_new_dataclass():
    """Backward compat for the resume/cache path: a pre---opponent row has none of the
    additive fields and must default to the h800 semantics."""
    old = {"seed": 1, "a_seat": 0, "info": "fair", "exact_k": 2, "k_dets": 2, "sims": 32,
           "rung_sims": 800, "score_p0": 10, "score_p1": 5, "diff": 5,
           "won_by_champ": True, "drew": False, "elapsed_s": 1.0, "moves": 10}
    r = efp.GameResult(**old)
    assert r.opponent == "h800"
    assert r.opp_exact_moves == 0 and r.opp_latch_k is None


# --------------------------------------------------------------------------- #
# (g) ASYMMETRIC opponent budgets: --opp-sims / --opp-k-dets
#
# UNSET is the load-bearing case: the opponent must fall back to the shared
# --sims/--k-dets so every symmetric run is byte-identical to the pre-flag harness.
# SET moves ONLY the opponent, and every read-out (label, manifest, summary) must
# carry the OPPONENT's own budget rather than the candidate's.
# --------------------------------------------------------------------------- #
C125 = None   # lazily built (the leaf load is the slow part)


def _c125():
    global C125
    if C125 is None:
        C125 = efp._curve125_leaf_cfg()
    return C125


def _fair_opp(sims, k_dets, opp_sims=None, opp_k_dets=None):
    """The head-to-head opponent as _make_opponent builds it, unwrapped to the agent."""
    opp = efp._make_opponent("fair-champion", CFG_DICT, sims, k_dets, 2, 800, seed=1,
                             opp_leaf_cfg=_c125(), opp_sims=opp_sims,
                             opp_k_dets=opp_k_dets)
    return opp._prefix


class _Args:
    """Minimal argparse-Namespace stand-in for the arg-level helpers."""

    def __init__(self, **kw):
        d = {"opponent": "fair-champion", "sims": 688, "k_dets": 4, "opp_sims": None,
             "opp_k_dets": None, "c_puct": 1.5, "tau_p": 5.0,
             "leaf_quantize": "float", "value_norm": 15.0, "opp_net": None}
        d.update(kw)
        for k, v in d.items():
            setattr(self, k, v)


def test_opp_k_dets_unset_falls_back_to_the_shared_k_dets():
    """THE parity property: None must be indistinguishable from 'pass --k-dets'."""
    fallback = _fair_opp(sims=344, k_dets=8, opp_k_dets=None)
    explicit = _fair_opp(sims=344, k_dets=8, opp_k_dets=8)
    assert fallback._k_dets == explicit._k_dets == 8
    assert fallback._sims == explicit._sims == 344


def test_opp_k_dets_moves_only_the_opponent():
    cand = efp._make_champion("fair", efp._cfg_from_dict(CFG_DICT, _c125()),
                              1376, 8, 2, 1, Game(enable_legal_moves_cache=True))._prefix
    opp = _fair_opp(sims=1376, k_dets=8, opp_k_dets=4)
    assert (cand._k_dets, cand._sims) == (8, 1376)
    assert (opp._k_dets, opp._sims) == (4, 1376)


def test_cl060_h2h_is_expressible_only_with_both_flags():
    """CL-060's re-open trigger: candidate k8x1376 (11008) vs the k4x688 (2752) opponent.
    --opp-sims ALONE gives a k8x688=5504 opponent — NOT the intended config.
    (Updated 2026-07-30: k8x1376 IS production since the CL-071 promotion, so the
    deviation polarity flipped — the candidate is now the shipped champion and the
    k4x688 opponent is the deviant. The pre-promotion version of this test asserted
    the inverse and stood stale for a day — the audit-F9 class, in test form.)"""
    sims_only = _fair_opp(sims=1376, k_dets=8, opp_sims=688)
    assert sims_only._k_dets * sims_only._sims == 8 * 688 == 5504   # the wrong opponent
    both = _fair_opp(sims=1376, k_dets=8, opp_sims=688, opp_k_dets=4)
    assert (both._k_dets, both._sims) == (4, 688)
    assert both._k_dets * both._sims == 2752                       # the OLD deploy config
    a = _Args(sims=1376, k_dets=8, opp_sims=688, opp_k_dets=4)
    # the k4x688 OPPONENT deviates on both axes post-CL-071
    dev_opp = efp._prod_deviations(a, sims_override=efp._opp_eff_sims(a),
                                   k_dets_override=efp._opp_eff_k_dets(a))
    assert any("k_dets=4" in d for d in dev_opp) and any("sims=688" in d for d in dev_opp)
    # the CANDIDATE is literally the shipped champion on both budget axes
    assert efp._prod_deviations(a) == []


def test_h800_rung_ignores_opp_k_dets():
    """The rung is a plain HeuristicMCTS — no determinizations at all. It must stay the
    byte-identical fixed ruler no matter what the asymmetry flags say."""
    plain = efp._make_opponent("h800", CFG_DICT, 8, 2, 2, 800, seed=1)
    with_k = efp._make_opponent("h800", CFG_DICT, 8, 2, 2, 800, seed=1,
                                opp_k_dets=99, opp_sims=99)
    assert isinstance(with_k, efp._RungPrefix)
    assert with_k._m.simulations == plain._m.simulations == 800
    assert efp._leaf_hash(with_k._m._leaf_cfg) == efp.RUNG_CURVE100_LEAF_HASH


def test_opp_eff_helpers_default_to_the_shared_knobs():
    sym = _Args(sims=688, k_dets=4)
    assert efp._opp_eff_sims(sym) == 688 and efp._opp_eff_k_dets(sym) == 4
    asym = _Args(sims=1376, k_dets=8, opp_sims=688, opp_k_dets=4)
    assert efp._opp_eff_sims(asym) == 688 and efp._opp_eff_k_dets(asym) == 4


def test_opp_label_reports_the_opponents_own_budget():
    """The label is what lands in summary.json / the run header — it must never show the
    CANDIDATE's budget on the opponent line."""
    assert "k4x688" in efp._opp_label(_Args(sims=1376, k_dets=8, opp_sims=688,
                                            opp_k_dets=4))
    # symmetric: unchanged (the shared knobs)
    assert "k8x1376" in efp._opp_label(_Args(sims=1376, k_dets=8))


def test_prod_deviations_k_dets_override_mirrors_sims_override():
    a = _Args(sims=1376, k_dets=4)
    assert any("k_dets=4" in d for d in efp._prod_deviations(a))
    # the OPPONENT block substitutes ITS own k_dets -> production, no deviation
    assert efp._prod_deviations(a, k_dets_override=8) == []


def test_summary_asymmetry_block_is_absent_when_symmetric():
    """Byte-identical summary.json for every symmetric run: the guard keys appear ONLY
    when an asymmetry flag was explicitly set."""
    res = [_mk(1, 0, +5, opponent="fair-champion"), _mk(1, 1, -5, opponent="fair-champion")]
    sym = efp._summary(res, "fair", 2, 4, 688, 800, opponent="fair-champion")
    for k in ("asymmetric_budgets", "opp_k_dets", "opp_sims", "opp_total_sims",
              "candidate_total_sims"):
        assert k not in sym


def test_summary_asymmetry_block_names_both_sides():
    """`k_dets`/`sims`/`total_sims` are the CANDIDATE's; in an asymmetric run the
    opponent's own budget must sit right next to them so neither can be read as the
    match's."""
    res = [_mk(1, 0, +5, opponent="fair-champion"), _mk(1, 1, -5, opponent="fair-champion")]
    summ = efp._summary(res, "fair", 2, 8, 1376, 800, opponent="fair-champion",
                        opp_k_dets=4, opp_sims=688)
    assert summ["asymmetric_budgets"] is True
    assert (summ["k_dets"], summ["sims"], summ["total_sims"]) == (8, 1376, 11008)
    assert (summ["candidate_k_dets"], summ["candidate_sims"],
            summ["candidate_total_sims"]) == (8, 1376, 11008)
    assert (summ["opp_k_dets"], summ["opp_sims"], summ["opp_total_sims"]) == (4, 688, 2752)


def test_summary_asymmetry_block_fills_the_unset_axis_from_the_shared_knob():
    """--opp-k-dets alone (no --opp-sims): the opponent's sims is the shared --sims."""
    res = [_mk(1, 0, 0, opponent="fair-champion")]
    summ = efp._summary(res, "fair", 2, 8, 344, 800, opponent="fair-champion",
                        opp_k_dets=4)
    assert (summ["opp_k_dets"], summ["opp_sims"], summ["opp_total_sims"]) == (4, 344, 1376)


@pytest.mark.parametrize("flag", ["--opp-k-dets", "--opp-sims"])
def test_asymmetry_flags_are_rejected_for_the_h800_rung(flag, capsys):
    """h800 already owns a budget flag (--rung-sims); silently swallowing an asymmetry
    flag there would mislead. Fail loud."""
    with pytest.raises(SystemExit):
        efp.main(["--info", "fair", "--opponent", "h800", flag, "4"])
    err = capsys.readouterr().err
    assert flag in err and "--rung-sims" in err


def test_opp_k_dets_must_be_at_least_one():
    with pytest.raises(SystemExit):
        efp.main(["--info", "fair", "--opponent", "fair-champion", "--opp-k-dets", "0"])
