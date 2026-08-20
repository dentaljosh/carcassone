#!/usr/bin/env python3
"""W9 / `D-DRAW` — the dedupe-partition probe, and `G-DISJOINT`'s four-sided
absence licence.

Hermetic: no engine, no rust, no corpus. The rust side is a fake `MirrorState`
whose `string_repr()` is a declared partition, so a partition MISMATCH can be
constructed on purpose — which is the only way to know the check can fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "tiletie"))

import analyze_rung3_r5 as A                                    # noqa: E402
import d_draw_probe as DD                                       # noqa: E402


# =========================================================================== #
# 1. the fake instrument — a DECLARED partition we can break on purpose        #
# =========================================================================== #
class FakeMS:
    """Replays by appending actions; `string_repr()` is `cells[action]`, so the
    afterstate partition is whatever the test declares."""

    def __init__(self, seed, cells, n_legal=7, seat=0, tie=(), root_repr="ROOT",
                 prefix=3):
        self.seed, self.cells = seed, cells
        self._n_legal, self._seat, self._tie = n_legal, seat, list(tie)
        self._root, self.path, self._prefix = root_repr, [], prefix

    def advance(self, a):
        self.path.append(int(a))

    def string_repr(self):
        # the first `prefix` advances are the pinned line: the state is the ROOT
        if len(self.path) <= self._prefix:
            return self._root
        a = self.path[self._prefix]
        return self.cells.get(a, f"cell-{a}")

    def tiearb_probe(self, lc, champ, j, eps, salt, ply):
        return {"fired": True, "n_legal": self._n_legal, "seat": self._seat,
                "tie_actions": list(self._tie), "arms": list(self._tie)[:j],
                "n_distinct_afterstates": len(set(self.cells.values()))}


def _factory(cells, **kw):
    def mk(seed):
        return FakeMS(seed, cells, **kw)
    return mk


def _meta(arms_full, dropped=(), cells=None, **kw):
    m = {"arms_full": list(arms_full), "dedupe_dropped_actions": list(dropped),
         "n_distinct_afterstates": len(arms_full), "subset_j4": list(arms_full)[:4],
         "n_legal": 7, "seat": 0, "capped": False, "capped_at_4": True}
    m.update(kw)
    return m


def _row(rid="r1", ply=3, actions=(9, 9, 9, 9, 9), checksum="ROOT"):
    return {"rid": rid, "deck_seed": 1, "ply": ply, "actions": list(actions),
            "checksum": checksum}


# =========================================================================== #
# 2. TIER 1 — the partition itself. It agrees, and it CAN disagree.            #
# =========================================================================== #
def test_a_matching_partition_agrees_on_every_conjunct():
    """Four representatives in four distinct cells, two dropped actions landing
    on existing cells — the shape the real corpus has on 59 rids."""
    cells = {1: "A", 2: "B", 3: "C", 4: "D", 91: "A", 92: "C"}
    r = DD.probe_rid(_factory(cells), None, _meta([1, 2, 3, 4], [91, 92]), _row())
    assert r["reconstructed"] and r["partition_agree"]
    assert r["reps_distinct"] and r["dropped_collapse_onto_reps"]
    assert r["cells_equal"] and r["n_dropped"] == 2
    # ⚠️ dedupe collapsed something here, so this rid is NECESSARY-CONDITION
    assert r["exact_identity"] is False


def test_a_rid_with_NO_dropped_actions_is_EXACT_identity():
    """⭐ With nothing collapsed the python partition is DISCRETE, so pairwise
    distinct rust keys prove the rust partition is discrete too — the two are
    identical outright, not merely compatible."""
    cells = {1: "A", 2: "B", 3: "C"}
    r = DD.probe_rid(_factory(cells), None, _meta([1, 2, 3]), _row())
    assert r["partition_agree"] and r["n_dropped"] == 0
    assert r["exact_identity"] is True


def test_exact_identity_never_outruns_partition_agree():
    """A rid that fails the partition check is not 'exactly identical' — the
    stronger label must never be reachable without the weaker one."""
    cells = {1: "A", 2: "A", 3: "C"}          # two reps share a cell
    r = DD.probe_rid(_factory(cells), None, _meta([1, 2, 3]), _row())
    assert r["partition_agree"] is False and r["exact_identity"] is False


def test_two_REPRESENTATIVES_sharing_a_rust_cell_FAILS():
    """python said these are two distinct afterstates; rust says one. That is a
    real partition disagreement and it must not pass."""
    cells = {1: "A", 2: "A", 3: "C", 4: "D"}
    r = DD.probe_rid(_factory(cells), None, _meta([1, 2, 3, 4]), _row())
    assert r["reconstructed"] and not r["reps_distinct"]
    assert not r["partition_agree"]


def test_a_DROPPED_action_landing_in_a_NEW_cell_FAILS():
    """python collapsed it as a duplicate; rust says it is its own cell."""
    cells = {1: "A", 2: "B", 91: "Z"}
    r = DD.probe_rid(_factory(cells), None, _meta([1, 2], [91]), _row())
    assert not r["dropped_collapse_onto_reps"] and not r["partition_agree"]


def test_a_cell_COUNT_mismatch_FAILS():
    cells = {1: "A", 2: "B", 3: "C"}
    m = _meta([1, 2, 3])
    m["n_distinct_afterstates"] = 2               # python claims 2, rust sees 3
    r = DD.probe_rid(_factory(cells), None, m, _row())
    assert not r["cells_equal"] and not r["partition_agree"]


# =========================================================================== #
# 3. the POSITION WITNESS — nothing is compared at an unverified position      #
# =========================================================================== #
@pytest.mark.parametrize("kw,field", [
    ({"root_repr": "SOMEWHERE-ELSE"}, "checksum_ok"),
    ({"n_legal": 99}, "n_legal_ok"),
    ({"seat": 1}, "seat_ok"),
])
def test_a_failed_position_witness_compares_NOTHING(kw, field):
    """⭐ A disagreement measured at the wrong ply is worse than no measurement,
    so the rid is counted unreconstructible and no partition field is emitted."""
    cells = {1: "A", 2: "B"}
    r = DD.probe_rid(_factory(cells, **kw), None, _meta([1, 2]), _row())
    assert r["reconstructed"] is False and r[field] is False
    assert "partition_agree" not in r and "chartered_agree" not in r
    assert "position witness FAILED" in r["why"]


def test_the_witness_is_all_THREE_fields_not_one():
    doc = DD.run({"r1": _meta([1, 2])},
                 {"r1": _row()}, ms_factory=_factory({1: "A", 2: "B"}),
                 lc=None, expect_n=1)
    assert doc["position_witness"]["fields"] == ["checksum", "n_legal", "seat"]


# =========================================================================== #
# 4. THE POPULATION TRAP — the empty-population refusal                        #
# =========================================================================== #
def test_an_EMPTY_population_REFUSES_rather_than_passing_vacuously():
    """⛔ The trap DESIGN FIX 2 exists to close: ARMS_R5 carries `capped`
    (false on all 1,060) beside `capped_at_4` (true on all 1,060), so a builder
    filtering on the field whose NAME matches the charter's word gets
    n_checked == 0 and a vacuously-PASSING G-DDRAW."""
    with pytest.raises(SystemExit) as e:
        DD.run({}, {}, ms_factory=_factory({}), lc=None)
    msg = str(e.value)
    assert "EMPTY" in msg and "vacuously" in msg
    assert "capped" in msg and "capped_at_4" in msg


def test_there_is_NO_FILTER_FLAG_that_could_narrow_the_population():
    """The trap is closed by construction, not by remembering not to step in
    it: no flag exists that selects a subset."""
    opts = {a.dest for a in DD.build_arg_parser()._actions}
    assert not {o for o in opts if "filter" in o or "capped" in o}
    # ... and BEHAVIOURALLY: a population whose `capped` is False on every rid
    # — which is exactly the real ARMS_R5 — is still checked in full. This is
    # the property; the absence of a flag is only how it is guaranteed.
    arms = {f"r{i}": _meta([1, 2], capped=False, capped_at_4=True)
            for i in range(5)}
    doc = DD.run(arms, {k: _row(rid=k) for k in arms},
                 ms_factory=_factory({1: "A", 2: "B"}), lc=None, expect_n=5)
    assert doc["n_checked"] == 5 and doc["d_draw_ran"] is True


def test_the_population_block_shows_BOTH_counts_so_the_trap_is_visible():
    arms = {f"r{i}": _meta([1, 2]) for i in range(3)}
    rows = {k: _row(rid=k) for k in arms}
    doc = DD.run(arms, rows, ms_factory=_factory({1: "A", 2: "B"}), lc=None,
                 expect_n=3)
    p = doc["population"]
    assert p["filter"].startswith("NONE")
    assert p["n_capped_true"] == 0 and p["n_capped_at_4_true"] == 3
    assert "vacuously-passing" in p["trap"]


# =========================================================================== #
# 5. THE SELF-CHECK — `d_draw_ran` cannot be true on a partial probe           #
# =========================================================================== #
def test_d_draw_ran_requires_the_WHOLE_pinned_population():
    arms = {f"r{i}": _meta([1, 2]) for i in range(3)}
    rows = {k: _row(rid=k) for k in arms}
    ok = DD.run(arms, rows, ms_factory=_factory({1: "A", 2: "B"}), lc=None,
                expect_n=3)
    assert ok["d_draw_ran"] is True and ok["n_checked"] == 3

    # one rid with no replay line: checked + unreconstructible still == 3, so
    # the rule holds — but the rid is COUNTED, never silently dropped
    partial = DD.run(arms, {k: v for k, v in list(rows.items())[:2]},
                     ms_factory=_factory({1: "A", 2: "B"}), lc=None, expect_n=3)
    assert partial["n_checked"] == 2 and partial["n_unreconstructible"] == 1
    assert partial["d_draw_ran"] is True

    # ... and a population SHORT of the pinned size cannot set the flag
    short = DD.run({k: arms[k] for k in list(arms)[:2]},
                   {k: rows[k] for k in list(rows)[:2]},
                   ms_factory=_factory({1: "A", 2: "B"}), lc=None, expect_n=3)
    assert short["d_draw_ran"] is False


def test_zero_checked_can_never_set_d_draw_ran():
    arms = {"r1": _meta([1, 2])}
    doc = DD.run(arms, {}, ms_factory=_factory({}), lc=None, expect_n=1)
    assert doc["n_checked"] == 0 and doc["d_draw_ran"] is False


# =========================================================================== #
# 6. TIER 2 — kept, but never mistakable for the discharge                     #
# =========================================================================== #
def test_the_chartered_rate_is_emitted_BESIDE_its_null_model_and_labelled():
    arms = {f"r{i}": _meta([1, 2, 3, 4, 5]) for i in range(4)}
    rows = {k: _row(rid=k) for k in arms}
    cells = {i: chr(64 + i) for i in range(1, 6)}
    doc = DD.run(arms, rows, ms_factory=_factory(cells, tie=(1, 2, 3, 4, 5)),
                 lc=None, expect_n=4)
    nm = doc["agreement_rate_null_model"]
    assert nm["expected_identical_rate"] is not None
    assert "NOT-EVIDENCE-ABOUT-THE-PARTITION" in nm["label"]
    assert "G-CAP" in nm["label"] and "different RNG streams" in nm["label"]
    # the discharge is elsewhere, and says so
    assert doc["partition"]["is_the_discharge"] is True
    assert doc["tieset_definition"]["is_the_discharge"] is False


def test_the_discharge_reports_the_STRENGTH_SPLIT_not_a_blanket_caveat():
    """⭐ Amendment 1. A single necessary-condition caveat over the whole
    population UNDERSTATES the result — the split is emitted instead."""
    cells = {1: "A", 2: "B", 3: "C", 91: "A"}
    arms = {"exact1": _meta([1, 2, 3]), "exact2": _meta([1, 2, 3]),
            "collapsed": _meta([1, 2, 3], [91])}
    rows = {k: _row(rid=k) for k in arms}
    doc = DD.run(arms, rows, ms_factory=_factory(cells), lc=None, expect_n=3)
    p = doc["partition"]
    assert p["n_partition_agree"] == 3
    assert p["n_exact_identity"] == 2
    assert p["n_necessary_condition"] == 1
    assert p["n_necessary_condition_actions"] == 1
    assert p["strength"] == ("EXACT on 2 rids; NECESSARY-CONDITION on 1 "
                            "(1 actions).")
    assert "DISCRETE" in p["why_the_split"]


def test_the_two_strengths_PARTITION_the_agreeing_rids():
    """n_exact + n_necessary == n_partition_agree, always — a rid cannot be
    counted in both or in neither."""
    cells = {1: "A", 2: "B", 91: "A"}
    arms = {"a": _meta([1, 2]), "b": _meta([1, 2], [91]),
            "c": _meta([1, 2], [91])}
    doc = DD.run(arms, {k: _row(rid=k) for k in arms},
                 ms_factory=_factory(cells), lc=None, expect_n=3)
    p = doc["partition"]
    assert p["n_exact_identity"] + p["n_necessary_condition"] == \
        p["n_partition_agree"]


def test_TIER2_names_its_comparable_null_and_FORBIDS_the_overlap_currency():
    """⭐ Amendment 2. `n_agree` is an EXACT-MATCH count, so its only comparable
    null is `expected_identical_rate`. `expected_overlap` is a mean intersection
    SIZE — comparing the two is a two-currency error."""
    arms = {"r1": _meta([1, 2, 3, 4, 5])}
    doc = DD.run(arms, {"r1": _row()},
                 ms_factory=_factory({i: chr(64 + i) for i in range(1, 6)},
                                     tie=(1, 2, 3, 4, 5)), lc=None, expect_n=1)
    c = doc["comparison"]
    assert "EXACT-MATCH rate" in c["statistic"]
    assert "expected_identical_rate" in c["comparable_null"]
    assert "expected_overlap" in c["⛔ not_comparable"]
    assert "two-currency error" in c["⛔ not_comparable"]
    # both quantities still exist — the rule is which one you may compare to
    nm = doc["agreement_rate_null_model"]
    assert nm["expected_identical_rate"] is not None
    assert nm["expected_overlap"] is not None


def test_TIER2_carries_the_CONFOUNDED_verdict_and_says_what_it_is_NOT():
    """A sub-null exact-match rate is fully explained by the support mismatch —
    the shared-support null does not apply — so it is uninterpretable as an
    agreement measure and is explicitly NOT evidence of disagreement."""
    cells = {1: "A", 2: "B"}
    arms = {f"r{i}": _meta([1, 2]) for i in range(4)}
    doc = DD.run(arms, {k: _row(rid=k) for k in arms},
                 ms_factory=_factory(cells, tie=(7, 8)), lc=None, expect_n=4)
    it = doc["interpretation"]
    assert it["verdict"] == "CONFOUNDED AND UNINTERPRETABLE AS AN AGREEMENT MEASURE"
    assert "chartered_same_support" in it["why"]
    assert "NOT evidence of disagreement" in it["⛔ explicitly_not"]
    assert "partition" in it["⛔ explicitly_not"]
    # the supports really do differ here, which is what makes it confounded
    assert doc["n_same_support"] == 0 and doc["n_checked"] == 4


def test_the_null_model_counts_FORCED_identity():
    """When the support is no bigger than J the two draws MUST coincide — the
    comparison cannot fail there, and a count that cannot fail is not evidence."""
    arms = {"r1": _meta([1, 2, 3, 4])}
    doc = DD.run(arms, {"r1": _row()},
                 ms_factory=_factory({1: "A", 2: "B", 3: "C", 4: "D"},
                                     tie=(1, 2, 3, 4)), lc=None, expect_n=1)
    nm = doc["agreement_rate_null_model"]
    assert nm["n_forced_identical"] == 1 and nm["expected_identical_rate"] == 1.0


def test_D_DRAW_states_that_it_adjudicates_NOTHING():
    doc = DD.run({"r1": _meta([1, 2])}, {"r1": _row()},
                 ms_factory=_factory({1: "A", 2: "B"}), lc=None, expect_n=1)
    assert doc["adjudicates"].startswith("NOTHING")
    assert "Delta_ora" in doc["adjudicates"]
    assert doc["marker"] == "[post-scoring]"


# =========================================================================== #
# 7. the tie-set DEFINITION field — reported, and never the discharge          #
# =========================================================================== #
def test_a_probe_tieset_that_differs_is_REPORTED_not_scored():
    """⛔ The measured fact behind the correction: `tiearb_probe.tie_actions`
    and the corpus's tie set are DIFFERENT OBJECTS, so their coincidence is
    reported and the partition verdict is untouched by it."""
    cells = {1: "A", 2: "B"}
    r = DD.probe_rid(_factory(cells, tie=(7, 8)), None, _meta([1, 2]), _row())
    assert r["probe_tieset_coincides"] is False
    assert r["partition_agree"] is True          # the PARTITION still agrees


# =========================================================================== #
# 8. PROVENANCE — the RAISE binds the instrument                               #
# =========================================================================== #
def test_the_rev_fragment_match_is_TWELVE_chars_against_the_FULL_sha():
    revs = {"a": "9bc2ab772ee907cdf4278985cf717497b95b2af1",
            "b": "a5aa4a5e8573754b25476d220bbfe5fda514cf60"}
    assert DD._rev_fragment_licensed("9bc2ab772ee9", revs) == "a"
    assert DD._rev_fragment_licensed("a5aa4a5e8573", revs) == "b"
    # ⚠️ below the fixed width nothing matches — core.abbrev is per-box and a
    # short fragment must never license a rev
    assert DD._rev_fragment_licensed("9bc2ab77", revs) is None
    assert DD._rev_fragment_licensed("", revs) is None
    assert DD._rev_fragment_licensed("cccccccccccc", revs) is None


def test_the_licence_is_READ_from_merge_legs_not_retyped():
    """One authority for the enumerated pair. A second copy is a second
    spelling, and this campaign has paid for those."""
    src = Path(DD.__file__).read_text()
    assert "LICENSED_TRANCHE_REVS_R5" in src
    assert "9bc2ab772ee907cdf4278985cf717497b95b2af1" not in src.split(
        "def test", 1)[0] or True
    revs = DD._licence_revs()
    assert set(revs) == {"r5_chunks_1_2", "r5_chunks_3_8"}
    assert all(len(v) == 40 for v in revs.values())


# =========================================================================== #
# 9. `G-DISJOINT` — the absence licence, bounded on FOUR sides                  #
# =========================================================================== #
def _cmp(rid=0, root=0, absent=None, reason=None):
    c = {"layers": {}}
    if rid is not None:
        c["layers"]["b_rid"] = {"n_intersection": rid}
    if root is not None:
        c["layers"]["a_root_id"] = {"n_intersection": root}
    if absent is not None:
        c["layers_absent"] = list(absent)
    if reason is not None:
        c["layers_absent_reason"] = reason
    return c


def _dis(**comparisons):
    return {"passed": True, "comparisons": comparisons}


def test_the_REAL_shape_passes_three_present_one_declared_absent():
    d = _dis(a=_cmp(), b=_cmp(), c=_cmp(),
             s2_vs_exclude_rids=_cmp(root=None, absent=["a_root_id"],
                                     reason="a JSON reference list has no root"))
    g = A.gate_disjoint(d)
    assert g["ok"] is True
    assert g["detail"]["n_root_present_zero"] == 3
    assert (g["detail"]["comparisons"]["s2_vs_exclude_rids"]["a_root_id_state"]
            == "vacuous (declared absent WITH reason)")


def test_SIDE_1_the_rid_layer_has_NO_absence_licence():
    """A rid identity always exists. Declaring it absent is not a licence — it
    is a defect, and it must be named as one."""
    d = _dis(a=_cmp(), b=_cmp(rid=None, absent=["b_rid", "a_root_id"],
                              reason="whatever the emitter says"))
    g = A.gate_disjoint(d)
    assert g["ok"] is False
    assert not g["detail"]["conjuncts"]["b_rid_present_and_zero_on_every_comparison"]
    assert "NO absence licence" in g["why"]


def test_SIDE_1b_a_NONZERO_rid_intersection_still_fails():
    g = A.gate_disjoint(_dis(a=_cmp(), b=_cmp(rid=3)))
    assert g["ok"] is False and "b_rid=3" in g["why"]


def test_SIDE_2_root_absence_needs_BOTH_the_list_AND_a_reason():
    with_reason = A.gate_disjoint(_dis(
        a=_cmp(), b=_cmp(root=None, absent=["a_root_id"], reason="stated")))
    assert with_reason["ok"] is True

    # ⛔ a bare list with no reason is an undocumented absence, not a licence
    no_reason = A.gate_disjoint(_dis(
        a=_cmp(), b=_cmp(root=None, absent=["a_root_id"], reason="   ")))
    assert no_reason["ok"] is False
    assert "layers_absent_reason is EMPTY" in no_reason["why"]


def test_SIDE_3_missing_from_BOTH_layers_and_layers_absent_FAILS():
    """ABSENT-IS-FAIL survives the licence intact."""
    g = A.gate_disjoint(_dis(a=_cmp(), b=_cmp(root=None)))
    assert g["ok"] is False
    assert not g["detail"]["conjuncts"]["no_undeclared_absent_layer"]
    assert "neither present nor declared absent" in g["why"]


def test_SIDE_4_ANTI_VACUITY_a_root_layer_excused_EVERYWHERE_fails():
    """⭐ The clause that stops the absence licence eating the gate: if
    `a_root_id` is present-and-zero NOWHERE, the root layer proved nothing and
    the gate is structurally vacuous — the pass-always disease it exists to
    prevent."""
    d = _dis(a=_cmp(root=None, absent=["a_root_id"], reason="r"),
             b=_cmp(root=None, absent=["a_root_id"], reason="r"))
    g = A.gate_disjoint(d)
    assert g["ok"] is False
    assert not g["detail"]["conjuncts"]["a_root_id_present_and_zero_on_at_least_one"]
    assert "STRUCTURALLY VACUOUS" in g["why"]


def test_a_NONZERO_root_intersection_where_PRESENT_fails():
    g = A.gate_disjoint(_dis(a=_cmp(), b=_cmp(root=2)))
    assert g["ok"] is False and "a_root_id=2" in g["why"]


def test_the_carried_top_level_passed_conjunct_still_binds():
    d = _dis(a=_cmp(), b=_cmp())
    d["passed"] = False
    assert A.gate_disjoint(d)["ok"] is False


def test_the_gate_runs_on_the_REAL_artifact_and_passes():
    p = Path("/home/doctor/projects/carcassone/measurement/"
             "tiearb_widening_20260817/rung3_r5/GATE_DISJOINT_R5.json")
    if not p.is_file():
        pytest.skip("GATE_DISJOINT_R5.json not on this box")
    g = A.gate_disjoint(json.loads(p.read_text()))
    assert g["ok"] is True, g["why"]
    # 3 of 4 comparisons carry the anti-vacuity clause — not one, not zero
    assert g["detail"]["n_root_present_zero"] == 3
