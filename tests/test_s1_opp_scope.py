"""S1 — `JrPriorScope::Opp` (opponent-model asymmetry) contract tests.

Design of record: `measurement/s1_asymmetry_prep/DESIGN.md` (+ `SIZING.md`).
Production path: `carc_core::search`, the line-635 scope gate,
`JrPriorScope::Opp => self.root_player != Some(mover)`.

`opp` is the COMPLEMENT of `own`: it boosts the expansion priors only at nodes
where the champion is NOT to move. The leaf value backed up is untouched on
every path and no leaf hash moves — same discipline as surface B's `all`/`own`.

⚠️ **THE TRAP THIS FILE EXISTS FOR (DESIGN §9.2).** Surface B's positive control
asserts that ROOT PRIORS move with dose. Under `opp` the root's mover IS the
root player, so the boost is OFF at the root **by design** and the root priors
are identical. The old control therefore fails on a *correctly wired* build, and
a naive "fix" that made it pass would mean the scope gate was mis-wired. The
replacement is two-sided and scope-aware:

  (a) root priors + root leaf value must NOT move under `opp`;
  (b) the POOLED root stats must move at the deploy sims-per-determinization;
  (c) `Own` and `Opp` boost disjoint sets whose union is `All`'s.

⚠️ PER-BOX REBUILD FOOTGUN (inherited from surface B, restated): the rust-gated
tests below SKIP — they do not fail — when the installed `carc_rs` wheel
predates S1. A skip on a box about to run a cell means that cell would run with
`opp` REJECTED at config construction (fail-closed ValueError, not a silent
null) — rebuild the wheel on that box before launching anything.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "classical_search"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import jrules_priors_e4_replay as jpe4  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig  # noqa: E402


# --------------------------------------------------------------------------- #
# 1. plumbing — no wheel needed                                                #
# --------------------------------------------------------------------------- #
def test_config_accepts_opp_and_still_rejects_junk():
    HeuristicPriorConfig(jrules_prior_dose=1.0, jrules_prior_scope="opp")
    # dose 0 with a moved scope stays legal — it is still the champion.
    HeuristicPriorConfig(jrules_prior_scope="opp")
    for junk in ("both", "OPP", "opponent", "", "oppo"):
        with pytest.raises(ValueError, match="jrules_prior_scope"):
            HeuristicPriorConfig(jrules_prior_scope=junk)


def test_manifest_emits_the_resolved_opp_scope():
    """The wiring gate for surface B is the RESOLVED scope in the manifest —
    this surface deliberately moves no leaf hash, so nothing else can prove
    which arm actually ran."""
    m = HeuristicPriorConfig(jrules_prior_dose=0.5,
                             jrules_prior_scope="opp").as_manifest()
    assert m["jrules_prior_scope"] == "opp"
    assert m["jrules_prior_dose"] == 0.5
    assert m["jrules_prior_mask"] == 31


def test_search_config_rs_forwards_opp_as_a_conditional_kwarg(monkeypatch):
    """Nonzero dose ⇒ the scope string is forwarded; default-off ⇒ no kwarg at
    all, so a pre-S1 wheel keeps serving every champion config unchanged."""
    captured: dict = {}

    class _FakeCfg:
        def __init__(self, *a, **kw):
            captured.update(kw)

    monkeypatch.setitem(sys.modules, "carc_rs",
                        SimpleNamespace(SearchConfigRs=_FakeCfg,
                                        LeafConfigRs=lambda *a, **kw: None))
    from carcassonne_ai import rust_agent
    rust_agent.search_config_rs(
        HeuristicPriorConfig(jrules_prior_dose=0.5, jrules_prior_scope="opp"),
        sims=8)
    assert captured["jrules_prior_scope"] == "opp"
    assert captured["jrules_prior_dose"] == 0.5

    captured.clear()
    rust_agent.search_config_rs(
        HeuristicPriorConfig(jrules_prior_scope="opp"), sims=8)   # dose 0
    assert not any(k.startswith("jrules_prior") for k in captured)


def test_eval_fair_puct_cli_offers_opp():
    """The CLI's `choices` is the launch-time typo guard for the cell."""
    import argparse
    import importlib
    efp = importlib.import_module("eval_fair_puct")
    ap = efp.build_parser() if hasattr(efp, "build_parser") else None
    if ap is None:                                   # parser built inline in main
        src = (REPO / "scripts" / "classical_search" / "eval_fair_puct.py").read_text()
        assert '"--cand-jrules-prior-scope", choices=("all", "own", "opp")' in src
        return
    assert isinstance(ap, argparse.ArgumentParser)
    act = next(a for a in ap._actions if "--cand-jrules-prior-scope" in a.option_strings)
    assert tuple(act.choices) == ("all", "own", "opp")


# --------------------------------------------------------------------------- #
# 2. the replay instrument's arm parser                                        #
# --------------------------------------------------------------------------- #
def test_parse_arm_round_trips_opp():
    a = jpe4.parse_arm("s1:0.5:31:opp")
    assert (a.name, a.dose, a.mask, a.scope) == ("s1", 0.5, 31, "opp")
    assert jpe4.parse_arm(a.spec()) == a


@pytest.mark.parametrize("spec", ["x:0.5:31:both", "x:0.5:31:OPP",
                                  "x:0.5:31:opponent", "x:0.5:31:oppo"])
def test_parse_arm_still_rejects_unknown_scopes(spec):
    with pytest.raises(ValueError, match="SCOPE"):
        jpe4.parse_arm(spec)


def test_parse_arms_allows_the_three_way_scope_split():
    """`opp`/`own`/`all` at the same dose+mask are three legitimately different
    cells, not a duplicate-knobs collision."""
    arms = jpe4.parse_arms(["a:1.0:31:all", "o:1.0:31:own", "p:1.0:31:opp"])
    assert [a.scope for a in arms] == ["all", "own", "opp"]
    with pytest.raises(ValueError, match="duplicates the knobs"):
        jpe4.parse_arms(["a:1.0:31:opp", "b:1.0:31:opp"])


# --------------------------------------------------------------------------- #
# 3. E2 — the root visit-distribution TV distance                              #
# --------------------------------------------------------------------------- #
def test_tv_distance_is_zero_for_the_same_distribution_and_scale_free():
    p = {1: 10.0, 2: 30.0, 3: 60.0}
    assert jpe4.tv_distance(p, p) == 0.0
    # normalized per side, so a pure rescale is not a difference
    assert jpe4.tv_distance(p, {k: 7.0 * v for k, v in p.items()}) == pytest.approx(0.0)


def test_tv_distance_counts_actions_absent_from_one_pool():
    """An action in one pool and not the other must contribute its FULL mass —
    dropping it would let a search that moved all its visits elsewhere read as
    perfect agreement."""
    assert jpe4.tv_distance({1: 1.0}, {2: 1.0}) == pytest.approx(1.0)
    assert jpe4.tv_distance({1: 1.0, 2: 1.0}, {1: 1.0}) == pytest.approx(0.5)


def test_tv_distance_returns_none_on_an_empty_pool():
    """`None`, never 0.0: 'no distribution' and 'identical distributions' are
    different facts, and conflating them would let a forced/solved ply read as
    perfect agreement and dilute the corpus mean."""
    assert jpe4.tv_distance({}, {1: 1.0}) is None
    assert jpe4.tv_distance({1: 1.0}, {}) is None
    assert jpe4.tv_distance(None, None) is None


def test_mean_tv_ignores_none_and_reports_none_when_empty():
    assert jpe4.mean_tv([0.0, 1.0, None]) == pytest.approx(0.5)
    assert jpe4.mean_tv([None, None]) is None
    assert jpe4.mean_tv([]) is None


def test_rollup_pools_e2_by_ply_not_by_game():
    """Games carry different graded-ply counts; a mean of per-game means would
    weight a 2-ply game like a 200-ply one."""
    summaries = [
        {"archive": "a", "n_graded": 2, "arms": [{"name": "s1", "dose": 1.0,
                                                  "mask": 31, "scope": "opp"}],
         "flips": {"s1": 0}, "flip_plies": {"s1": []},
         "root_visit_tv_n": {"s1": 2}, "root_visit_tv_sum": {"s1": 2.0},
         "root_visit_tv_mean": {"s1": 1.0}, "replay_scores_match": True},
        {"archive": "b", "n_graded": 8, "arms": [{"name": "s1", "dose": 1.0,
                                                  "mask": 31, "scope": "opp"}],
         "flips": {"s1": 0}, "flip_plies": {"s1": []},
         "root_visit_tv_n": {"s1": 8}, "root_visit_tv_sum": {"s1": 0.0},
         "root_visit_tv_mean": {"s1": 0.0}, "replay_scores_match": True},
    ]
    roll = jpe4.rollup_from_summaries(summaries)
    assert roll["arms"]["s1"]["root_visit_tv_n"] == 10
    assert roll["arms"]["s1"]["root_visit_tv_mean"] == pytest.approx(0.2)
    # NOT 0.5, which is what averaging the two per-game means would give.
    assert roll["arms"]["s1"]["root_visit_tv_mean"] != pytest.approx(0.5)
    # and the arm's SCOPE is stamped, so a readout can never confuse the arms
    assert roll["arm_knobs"]["s1"]["scope"] == "opp"


# --------------------------------------------------------------------------- #
# 4. rust-gated: the scope gate itself + the §9.2 liveness suite               #
# --------------------------------------------------------------------------- #
def _carc_rs_with_s1():
    carc_rs = pytest.importorskip("carc_rs")
    if not hasattr(carc_rs.MirrorState, "jrules_prior_probe"):
        pytest.skip("carc_rs wheel predates J-rules priors surface B")
    from carcassonne_ai.rust_agent import leaf_config_rs
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
    try:
        carc_rs.SearchConfigRs(leaf_config_rs(DEFAULT_CONFIG), 8, 1.5, 5.0, 15.0,
                               15.0, "float", "visits", None, 1.0, True,
                               "glibc_fma", jrules_prior_dose=1.0,
                               jrules_prior_scope="opp")
    except (ValueError, TypeError):
        pytest.skip(
            "carc_rs wheel PREDATES S1 (JrPriorScope::Opp) — the per-box rebuild "
            "footgun. Rebuild before any S1 cell on this box: `maturin build "
            "--release` in rust/carc/carc-py + reinstall. (The stale-wheel path "
            "is FAIL-CLOSED: scope='opp' raises at config construction.)")
    return carc_rs


def _cfg(carc_rs, sims, **jr):
    from carcassonne_ai.rust_agent import leaf_config_rs
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG
    return carc_rs.SearchConfigRs(leaf_config_rs(DEFAULT_CONFIG), sims, 1.5, 5.0,
                                  15.0, 15.0, "float", "visits", None, 1.0, True,
                                  "glibc_fma", **jr)


def _control_root(carc_rs):
    m = carc_rs.MirrorState.from_seed(jpe4._CONTROL_SEED)
    for _ in range(jpe4._CONTROL_PLIES):
        la = m.legal_actions()
        m.advance(la[len(la) // 2])
    return m


def test_rust_config_resolves_and_renders_opp():
    carc_rs = _carc_rs_with_s1()
    cfg = _cfg(carc_rs, 8, jrules_prior_dose=0.5, jrules_prior_scope="opp")
    assert cfg.jrules_prior == (0.5, 31, "opp")
    with pytest.raises(ValueError, match="jrules_prior_scope"):
        _cfg(carc_rs, 8, jrules_prior_dose=0.5, jrules_prior_scope="both")


def test_rust_dose0_with_scope_opp_is_bit_identical():
    """dose 0 short-circuits before the scope is read, so `opp` at dose 0 is
    still the champion byte-for-byte — including a zeroed expansion census."""
    carc_rs = _carc_rs_with_s1()
    m = _control_root(carc_rs)
    a = m.search_single(_cfg(carc_rs, 256))
    b = m.search_single(_cfg(carc_rs, 256, jrules_prior_dose=0.0,
                             jrules_prior_mask=27, jrules_prior_scope="opp"))
    assert a == b
    assert (b["jr_expansions_total"], b["jr_expansions_own_mover"],
            b["jr_expansions_boosted"]) == (0, 0, 0)


def test_s1_liveness_suite_passes_all_three_legs():
    """⭐ DESIGN §9.2, end to end, on the shipped instrument's own control."""
    _carc_rs_with_s1()
    jpe4._assert_surface_b_live(("all", "own", "opp"))     # raises SystemExit on failure


def test_leg_a_the_old_symmetric_control_would_have_failed_under_opp():
    """⭐ The trap, made explicit and permanent.

    The surface-B control's assertion ("dose 1.0 moves the root priors") is
    FALSE under `opp` on a correctly wired build. This test pins that it is
    false, so nobody can ever "fix" the control by re-enabling that assertion
    for this scope without a red test explaining why."""
    carc_rs = _carc_rs_with_s1()
    m = _control_root(carc_rs)
    off = m.search_single(_cfg(carc_rs, 32))
    opp = m.search_single(_cfg(carc_rs, 32, jrules_prior_dose=1.0,
                               jrules_prior_scope="opp"))
    assert opp["root_priors"] == off["root_priors"]
    assert opp["root_leaf_value_bits"] == off["root_leaf_value_bits"]
    # ...while the SYMMETRIC scopes do move them, so this is about the scope
    # gate and not about a dead dose.
    for scope in ("all", "own"):
        on = m.search_single(_cfg(carc_rs, 32, jrules_prior_dose=1.0,
                                  jrules_prior_scope=scope))
        assert on["root_priors"] != off["root_priors"], scope


def test_leg_c_the_partition_identity_holds_within_each_tree():
    """`All` boosts the whole population; `Own` boosts the own-mover half;
    `Opp` boosts exactly its complement. Read WITHIN each tree — the three
    scopes' trees diverge the moment a prior moves, so a cross-tree set
    comparison is not well defined (and would not add up)."""
    carc_rs = _carc_rs_with_s1()
    m = _control_root(carc_rs)
    census = {}
    for scope in ("all", "own", "opp"):
        r = m.search_single(_cfg(carc_rs, 1376, jrules_prior_dose=1.0,
                                 jrules_prior_scope=scope))
        census[scope] = (r["jr_expansions_total"], r["jr_expansions_own_mover"],
                         r["jr_expansions_boosted"])
    assert census["all"][2] == census["all"][0]
    assert census["own"][2] == census["own"][1]
    assert census["opp"][2] == census["opp"][0] - census["opp"][1]
    # non-vacuity: both halves of the partition are populated
    tot, own, _ = census["opp"]
    assert 0 < own < tot
