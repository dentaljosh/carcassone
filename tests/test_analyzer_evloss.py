"""Contracts for the Phase-5 EV-loss grader (scripts/analyzer/ev_loss.py).

Five groups, in the house pinning style of `tests/test_analyzer.py`:

  A. bucket machinery   — names + quantiles pinned as constants, boundary
                          behaviour asserted at both cut points
  B. units (D1)         — delta_points_tanh_est sign, monotonicity, clipping
  C. pool arithmetic    — Q == W/N, bits round trip, the best-action rule IS
                          fair_agent.pooled_q_argmax
  D. epoch resolution   — archive (start_rule, grid_rule) -> rules profile,
                          fail-closed on anything unknown
  E. end to end         — a real archive, a real Rust champion, a few plies:
                          delta_q >= 0 for every rated ply, forced and latched
                          plies excluded from the primary readout, and the
                          shipped artifacts' measured null quantiles pinned.

E skips (not fails) when the archive corpus or the Rust extension is absent —
same pattern as `tests/test_analyzer.py:34-38`.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "analyzer"))
sys.path.insert(0, str(REPO / "scripts" / "human_anchor"))

import ev_loss as EV  # noqa: E402

E4_DIR = REPO / "measurement" / "e4_games"
ART_DIR = REPO / "measurement" / "analyzer_evloss_20260805"

# The two shipped artifacts and their MEASURED null quantiles. These are not
# design constants — they are the calibration result, pinned so that a change to
# the grader, the leaf, the budget or the seeds cannot move the bucket
# boundaries silently. Re-deriving them means re-stamping the readout.
PINNED_NULL_P95 = {"EV_LOSS_g1_867966.json": 0.0471812558508575,
                   "EV_LOSS_g2_161583.json": 0.12452271784464798}
PINNED_NULL_P99 = {"EV_LOSS_g1_867966.json": 0.13978914641315918,
                   "EV_LOSS_g2_161583.json": 0.1680688971104433}


def _has_rust():
    try:
        import carc_rs  # noqa: F401
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# A. buckets — names and quantiles pinned, boundaries asserted
# --------------------------------------------------------------------------- #

def test_bucket_names_and_quantiles_pinned():
    assert EV.BUCKETS == ("agree", "within_noise", "inaccuracy", "blunder")
    assert (EV.NULL_Q_INACCURACY, EV.NULL_Q_BLUNDER) == (0.95, 0.99)
    assert EV.LEAF_HASH_OF_RECORD == "a36d2e15a3b3d71d"
    assert (EV.VALUE_NORM, EV.TANH_CLIP) == (15.0, 0.999)


def _rec(dq, agrees=False, kind="pimc"):
    return {"kind": kind, "delta_q": dq, "agrees": agrees}


def test_bucket_boundaries_are_inclusive_at_the_cut_points():
    """`within_noise` is delta_q <= p95 and `inaccuracy` is p95 < delta_q <= p99.
    Both cut points are CLOSED from below, so a value exactly ON a threshold takes
    the LESS severe label. Pinned because a flipped inequality moves every census."""
    p95, p99 = 0.05, 0.10
    assert EV.bucket_of(_rec(0.0, agrees=True), p95, p99) == "agree"
    assert EV.bucket_of(_rec(0.049), p95, p99) == "within_noise"
    assert EV.bucket_of(_rec(p95), p95, p99) == "within_noise"      # ON p95
    assert EV.bucket_of(_rec(p95 + 1e-12), p95, p99) == "inaccuracy"
    assert EV.bucket_of(_rec(p99), p95, p99) == "inaccuracy"        # ON p99
    assert EV.bucket_of(_rec(p99 + 1e-12), p95, p99) == "blunder"
    assert EV.bucket_of(_rec(1.5), p95, p99) == "blunder"


def test_agree_wins_over_every_threshold():
    """A ply where the search's best action IS the played action is `agree`
    whatever the thresholds say — delta_q is 0 there by construction."""
    assert EV.bucket_of(_rec(0.0, agrees=True), 0.0, 0.0) == "agree"


def test_forced_exact_and_unrated_plies_have_no_bucket():
    assert EV.bucket_of(_rec(None, kind="forced"), 0.05, 0.10) is None
    assert EV.bucket_of(_rec(None, kind="exact"), 0.05, 0.10) is None
    assert EV.bucket_of(_rec(None, kind="pimc"), 0.05, 0.10) is None   # unrated


def test_quantile_helper_matches_the_corpus_stats_convention():
    xs = [0.0, 1.0, 2.0, 3.0, 4.0]
    assert EV._quantile(xs, 0.0) == 0.0
    assert EV._quantile(xs, 1.0) == 4.0
    assert EV._quantile(xs, 0.5) == pytest.approx(2.0)
    assert EV._quantile([], 0.95) is None
    assert EV._quantile([7.0], 0.95) == 7.0


def test_null_is_the_paired_absolute_difference_of_the_two_passes():
    a = [{"ply": 0, "kind": "pimc", "delta_q": 0.10, "agrees": False, "action_best": 1},
         {"ply": 1, "kind": "pimc", "delta_q": 0.00, "agrees": True, "action_best": 2},
         {"ply": 2, "kind": "forced", "delta_q": None, "agrees": False},
         {"ply": 3, "kind": "pimc", "delta_q": None, "agrees": False, "action_best": 3}]
    b = [{"ply": 0, "kind": "pimc", "delta_q": 0.04, "agrees": False, "action_best": 1},
         {"ply": 1, "kind": "pimc", "delta_q": 0.00, "agrees": True, "action_best": 2},
         {"ply": 2, "kind": "forced", "delta_q": None, "agrees": False},
         {"ply": 3, "kind": "pimc", "delta_q": 0.5, "agrees": False, "action_best": 3}]
    null = EV.build_null(a, b)
    # ply 2 is forced, ply 3 is unrated in pass A -> neither contributes.
    assert null["n"] == 2
    assert sorted(null["samples_sorted"]) == pytest.approx([0.0, 0.06])
    # the agree/agree ply contributes a 0 and is deliberately kept (it is a real
    # ply on which the instrument was stable)
    assert null["n_disagree_only"] == 1


# --------------------------------------------------------------------------- #
# B. D1 units — delta_points_tanh_est
# --------------------------------------------------------------------------- #

def test_tanh_points_sign_and_zero():
    assert EV._tanh_points(0.3, 0.3) == pytest.approx(0.0)
    assert EV._tanh_points(0.3, 0.1) > 0            # best better than played
    assert EV._tanh_points(0.1, 0.3) < 0            # only reachable un-eligible


def test_tanh_points_is_monotone_in_the_gap():
    prev = -math.inf
    for q_played in (0.5, 0.4, 0.3, 0.2, 0.1, 0.0, -0.5):
        v = EV._tanh_points(0.6, q_played)
        assert v > prev
        prev = v


def test_tanh_points_clips_at_the_pinned_bound():
    """|Q| -> 1 makes atanh blow up; D1 clips at 0.999, so a Q of 1.0 and a Q of
    0.999 must price identically and the value must stay finite."""
    hard = EV._tanh_points(1.0, 0.0)
    clipped = EV._tanh_points(EV.TANH_CLIP, 0.0)
    assert hard == pytest.approx(clipped)
    assert math.isfinite(hard)
    assert hard == pytest.approx(EV.VALUE_NORM * math.atanh(EV.TANH_CLIP))
    assert EV._tanh_points(-5.0, 0.0) == pytest.approx(
        EV.VALUE_NORM * math.atanh(-EV.TANH_CLIP))


# --------------------------------------------------------------------------- #
# C. pool arithmetic
# --------------------------------------------------------------------------- #

def test_bits_round_trip():
    """`fbits` is the inverse of `fair_common.ubits` (which cannot be imported
    here — it pulls in prod_leaf_env, which refuses to load after carcassonne_ai)."""
    for x in (0.0, 1.0, -1.0, 5682.0, 75.24902747247587, 1e-300, -2.5e17):
        assert EV.fbits(EV.ubits(x)) == x
    # And it agrees with the real thing's definition, bit for bit.
    assert EV.ubits(1.0) == 0x3FF0000000000000
    assert EV.fbits(0x3FF0000000000000) == 1.0


def test_best_action_rule_is_the_production_pooled_q_argmax():
    """The grader's best action MUST be `fair_agent.pooled_q_argmax`, not a naive
    argmax over Q — an action with pooled N < min_visits is INELIGIBLE however
    good its Q looks, and picking it would disagree with the agent's own move."""
    fair_agent = pytest.importorskip("carcassonne_ai.fair_agent")
    # action 7 has the best Q but only 1 visit -> ineligible at min_visits=2.
    agg_n = {3: 5682.0, 5: 5325.0, 7: 1.0}
    agg_w = {3: 75.249, 5: 45.710, 7: 0.99}
    naive = max(agg_n, key=lambda a: agg_w[a] / agg_n[a])
    assert naive == 7
    assert fair_agent.pooled_q_argmax(agg_n, agg_w, min_visits=2) == 3
    # ties break on (Q, N, -action): same Q -> more visits wins, then lower action.
    assert fair_agent.pooled_q_argmax({1: 10.0, 2: 20.0}, {1: 5.0, 2: 10.0}, 2) == 2
    assert fair_agent.pooled_q_argmax({1: 10.0, 2: 10.0}, {1: 5.0, 2: 5.0}, 2) == 1
    # min_visits is the production default, not a local choice.
    assert float(fair_agent.DEFAULT_MIN_POOLED_VISITS) == 2.0


# --------------------------------------------------------------------------- #
# D. epoch -> rules profile (D4.2), fail closed
# --------------------------------------------------------------------------- #

AUG2_ARCHIVE = E4_DIR / "1785975832_66810.json"
PRE_0801_ARCHIVES = ("1785205383_867966.json", "1785466497_161583.json")


def test_archive_epoch_resolves_to_a_rules_profile():
    """A pre-2026-08-01 archive carries NO start_rule/grid_rule; those games were
    played on the engine of record and must be graded under `walled`."""
    assert EV.resolve_profile_name({}) == "walled"
    assert EV.resolve_profile_name({"start_rule": None, "grid_rule": None}) == "walled"
    assert EV.resolve_profile_name({"start_rule": "engine", "grid_rule": "engine6"}) == "walled"
    # The 2026-08-02 Android build. NOT fixed_v1 — see the retraction below.
    assert EV.resolve_profile_name(
        {"start_rule": "retail", "grid_rule": "centered18"}) == "app_aug2"


def test_explicit_rules_profile_stamp_wins():
    """The fixed_v1 app stamps its profile; a stamp is authoritative."""
    assert EV.resolve_profile_name(
        {"rules_profile": "fixed_v1", "start_rule": "retail",
         "grid_rule": "centered18"}) == "fixed_v1"
    assert EV.resolve_profile_name({"rules_profile": "walled"}) == "walled"
    # ...and it is validated against the registry, not trusted blindly.
    with pytest.raises(ValueError):
        EV.resolve_profile_name({"rules_profile": "not_a_profile"})


def test_unstamped_retail_centered18_is_never_fixed_v1():
    """THE REGRESSION that voided the 2026-08-05 grading of game 3.

    `(retail, centered18)` hits `fixed_v1` uniquely on (start_rule, grid_rule)
    alone, but the 2026-08-02 app build plays that pair while keeping drifting
    cloister scan, `next_player` and R9 OFF. Absence of the `rules_profile`
    stamp is positive evidence of a pre-fixed_v1 build."""
    for extra in ({}, {"cloister_rule": None, "farm_rule": None},
                  {"cloister_rule": "drifting", "unplaceable_rule": "next_player"}):
        got = EV.resolve_profile_name(
            dict({"start_rule": "retail", "grid_rule": "centered18"}, **extra))
        assert got != "fixed_v1"
        assert got == "app_aug2"


def test_unknown_epoch_fails_closed():
    with pytest.raises(ValueError):
        EV.resolve_profile_name({"start_rule": "retail", "grid_rule": "centered42"})
    with pytest.raises(ValueError):
        EV.resolve_profile_name({"start_rule": "lobster"})
    # A pre-fixed_v1 build cannot have played centered18 with the ENGINE start
    # tile, nor retail on the engine6 grid — no such app exists, so refuse.
    with pytest.raises(ValueError):
        EV.resolve_profile_name({"start_rule": "engine", "grid_rule": "centered18"})
    with pytest.raises(ValueError):
        EV.resolve_profile_name({"start_rule": "retail", "grid_rule": "engine6"})
    # A full rule tuple no pre-fixed_v1 build plays (this is fixed_v1's tuple,
    # unstamped) must raise rather than resolve to fixed_v1 by the back door.
    with pytest.raises(ValueError):
        EV.resolve_profile_name({"start_rule": "retail", "grid_rule": "centered18",
                                 "cloister_rule": "fixed", "unplaceable_rule": "redraw"})


def test_pre_0801_archives_are_still_walled_epoch():
    """The two pre-2026-08-01 archives must not move — their shipped artifacts
    were graded under `walled` and stay valid."""
    for name in PRE_0801_ARCHIVES:
        p = E4_DIR / name
        if not p.exists():
            pytest.skip(f"{name} absent")
        a = json.loads(p.read_text())
        assert EV.resolve_profile_name(a) == "walled"


def test_the_aug2_archive_resolves_to_app_aug2_not_fixed_v1():
    """Pinned against the REAL archive — this is the regression that caused the
    2026-08-05 retraction (EVLOSS_READOUT.md 6b)."""
    if not AUG2_ARCHIVE.exists():
        pytest.skip("aug-2 archive absent")
    a = json.loads(AUG2_ARCHIVE.read_text())
    # The discriminator itself: the fixed_v1 app stamps these; this build did not.
    assert a.get("start_rule") == "retail" and a.get("grid_rule") == "centered18"
    for f in ("rules_profile", "cloister_rule", "farm_rule"):
        assert a.get(f) in (None, ""), f"{f} present => this is NOT a pre-fixed_v1 archive"
    assert EV.resolve_profile_name(a) == "app_aug2"
    # ...and through `load_archive`'s provenance dict, the production path.
    assert EV.resolve_profile_name(
        EV.load_archive(AUG2_ARCHIVE)["provenance"]) == "app_aug2"


def test_app_aug2_profile_tuple_is_pinned_field_by_field():
    """A future registry edit must not silently change what past archives grade
    as. Every field of `app_aug2` is pinned here."""
    from carcassonne_ai import rules_profile

    p = rules_profile.PROFILES["app_aug2"]
    assert p.name == "app_aug2"
    assert p.grid_rule == "centered18"
    assert p.start_row == 18
    assert p.start_col == 15
    assert p.start_rule == "retail"
    assert p.cloister_scan == "drifting"       # NOT fixed — the A2 lever is absent
    assert p.unplaceable_tile == "next_player"  # NOT redraw — the A3 lever is absent
    assert p.r9_env_expected is False           # R9 OFF on the 2026-08-02 build
    assert (p.board_rows, p.board_cols) == (35, 35)
    assert p.window_size == rules_profile.PROFILES["walled"].window_size
    assert p.is_walled is False and p.fixed_start_tile is True and p.recentred is True
    # It differs from fixed_v1 in exactly the three levers fixed_v1 adds.
    fv = rules_profile.PROFILES["fixed_v1"]
    assert (fv.cloister_scan, fv.unplaceable_tile, fv.r9_env_expected) == (
        "fixed", "redraw", True)
    assert (p.grid_rule, p.start_row, p.start_rule) == (
        fv.grid_rule, fv.start_row, fv.start_rule)


# --------------------------------------------------------------------------- #
# E. end to end on a real archive + the shipped artifacts
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def graded():
    archives = sorted(E4_DIR.glob("*.json"))
    if not archives:
        pytest.skip("no E4 archives")
    if not _has_rust():
        pytest.skip("carc_rs (rust champion) not built")
    arch = EV.load_archive(archives[0])
    name = EV.resolve_profile_name(arch["provenance"])
    EV.prepare_env(name)
    plies, meta = EV.grade_pass(
        arch, name, seed=12345, sims=int(arch["sims_effective"]),
        k_dets=int(arch["k_dets_effective"]), rust_threads=None,
        exact_tail=False, limit=14, progress=False)
    return arch, plies, meta


def test_end_to_end_pool_arithmetic_and_delta_q(graded):
    arch, plies, meta = graded
    budget = int(arch["sims_effective"]) * int(arch["k_dets_effective"])
    assert plies, "graded nothing"
    rated = [r for r in plies if r["kind"] == "pimc" and r.get("delta_q") is not None]
    assert rated, "no rated plies in the prefix"
    for r in rated:
        # ΔQ >= 0 always: the best action is best over the SAME eligible set the
        # played action was found in.
        assert r["delta_q"] >= 0.0, r
        assert r["delta_q"] == pytest.approx(r["q_best"] - r["q_played"])
        assert r["delta_points_tanh_est"] >= 0.0
        # Q is W/N, and the pool always spends exactly the whole budget.
        assert r["pool_total_visits"] == pytest.approx(budget)
        assert -1.0 <= r["q_best"] <= 1.0 and -1.0 <= r["q_played"] <= 1.0
        assert r["n_visits_best"] >= meta["min_pooled_visits"]
        assert r["agrees"] == (r["action_played_rep"] == r["action_best"])
        if r["agrees"]:
            assert r["delta_q"] == pytest.approx(0.0)


def test_end_to_end_q_played_is_w_over_n_of_the_alias_representative(graded):
    """The pool is keyed by the alias group's representative (lowest action), so
    the played action is often absent from it verbatim; its Q must be read off
    min(group), never treated as unvisited."""
    _arch, plies, _meta = graded
    aliased = [r for r in plies if r["kind"] == "pimc"
               and r.get("alias_group_size", 1) > 1]
    for r in plies:
        if r["kind"] != "pimc":
            continue
        assert r["action_played_rep"] <= r["action_played"]
        assert r["n_alias_groups"] <= r["n_legal"]
        assert r["n_pooled"] <= r["n_alias_groups"]
    if aliased:
        r = aliased[0]
        assert r["n_alias_groups"] < r["n_legal"]


def test_end_to_end_forced_and_latched_are_excluded(graded):
    _arch, plies, _meta = graded
    for r in plies:
        if r["kind"] == "forced":
            assert r["n_legal"] == 1
            assert "delta_q" not in r and "q_played" not in r
            assert EV.bucket_of(dict(r, delta_q=None), 0.05, 0.1) is None
        if r["kind"] == "exact":
            assert "delta_q" not in r
            assert r["k_remaining"] <= _meta["exact_max_k"]


def test_end_to_end_provenance(graded):
    _arch, _plies, meta = graded
    assert meta["agent_manifest"]["leaf_hashes"]["harness_leaf_hash"] == \
        EV.LEAF_HASH_OF_RECORD
    assert meta["agent_manifest"]["search"]["value_norm"] == EV.VALUE_NORM
    assert meta["rules_profile"]["name"] == "walled"
    assert meta["rules_profile"]["r9_env_ok"] is True


# --- the shipped artifacts -------------------------------------------------- #

@pytest.mark.parametrize("name", sorted(PINNED_NULL_P95))
def test_shipped_artifact_nulls_and_gate_are_pinned(name):
    p = ART_DIR / name
    if not p.exists():
        pytest.skip(f"artifact missing: {p}")
    rep = json.loads(p.read_text())
    assert rep["schema"] == EV.SCHEMA
    thr = rep["buckets"]["thresholds"]
    assert thr["inaccuracy_gt"] == pytest.approx(PINNED_NULL_P95[name], rel=1e-9)
    assert thr["blunder_gt"] == pytest.approx(PINNED_NULL_P99[name], rel=1e-9)
    assert thr["from_quantiles"] == [EV.NULL_Q_INACCURACY, EV.NULL_Q_BLUNDER]
    itg = rep["integrity"]
    assert itg["replay_scores_match"] is True
    assert itg["mirror_desync_events"] == 0
    assert itg["leaf_hash_ok"] is True
    assert itg["rules_profile_name"] == "walled"
    assert itg["pool_total_visits_always_full_budget"] is True
    assert rep["acceptance_gate"]["pass"] is True
    # every rated ply carries a bucket; forced/exact/unrated never do
    for r in rep["plies"]:
        rated = r["kind"] == "pimc" and r.get("delta_q") is not None
        assert (r["bucket"] is not None) == rated
        if rated:
            assert r["delta_q"] >= 0.0
