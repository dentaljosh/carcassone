#!/usr/bin/env python3
"""Contract tests for the SYNTH-MECH instrument (CL-083 clause corroboration).

§1 pins `synth_mech.price_unit`'s pairing arithmetic and mover-sign convention
on hand fixtures BUILT FROM A REAL UNIT'S NUMBERS; §2 the WITNESSES
(`scope_witness`/`champ_witness`) on the real fixture censuses, mutated to
drive each of the five armed failure modes; §3 the CRN / `root_identity`
proof, including the between-family-vs-within-family `det_seed_base_at_root`
distinction; §4 the FROZEN SELECTOR (`build_targets`) — determinism, the cap,
the divergence routing, and a reproduction of `targets_fixture.jsonl`; §5 the
shape predicate `stratum_of`; §6 the adjudicator's cluster-robust statistics;
§7 the adjudicator's gate suite end to end under `--smoke`; §8 fixture
provenance.

⚠️⚠️ **FIXTURE DISCIPLINE** (house rule, `measurement/e1b_armed_continuation_
20260901/test_e1b.py`). `selftest_fixture/` is the ACTUAL output of a real
14-unit DRY smoke at production knobs — `units/*.json`, `select/*.json`,
`games/*.json`, `manifest_fixture.json`, `targets_fixture.jsonl`,
`SELECTION_fixture.json` — copied byte-for-byte. §2/§3/§5/§7/§8 address those
real nested shapes directly. §1's hand-built arm dicts use REAL margins lifted
off `unit_999900000002_p114_w0.json` (a genuine defense-stratum unit) so the
arithmetic tests are pinned to a document, not an invented expectation. §4's
synthetic ROW fixtures (kept minimal, shape-faithful to `_select_ply`'s
output) are ARITHMETIC-ONLY, in the same spirit as E-1b's §1/§5 — they test
`build_targets`' cap/routing logic, which the emitter has no further say in.

⚠️ **`cell` IS NOT REPRODUCIBLE FROM THIS FIXTURE.** `SELECTION.json`'s
matching cell for each target row is a tercile index computed over the FULL
candidate pool (`d_pool + c_pool`, ~576 real select rows in the actual
pre-freeze harvest); `selftest_fixture/select/` carries only the 7 select
rows for the 7 plies that were FINALLY chosen, not that pool. Re-running
`build_targets` on just those 7 rows reproduces every field of
`targets_fixture.jsonl` byte-for-byte EXCEPT `cell` (verified below) — §4
asserts exactly that, and does not fabricate the missing pool.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import statistics
from pathlib import Path

import pytest

D = Path(__file__).resolve().parent
FIX = D / "selftest_fixture"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, D / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SM = _load("synth_mech")
AD = _load("adjudicate_synth")


def _units():
    return AD.load_units(FIX / "units")


def _targets():
    return AD.load_targets(FIX / "targets_fixture.jsonl")


def _manifest():
    return AD.load_json_or_none(FIX / "manifest_fixture.json")


def _selection():
    return AD.load_json_or_none(FIX / "SELECTION_fixture.json")


def _select_rows():
    return [json.loads(p.read_text())
           for p in sorted((FIX / "select").glob("s_*.json"))]


def _real_unit(deck_seed, ply, world):
    for u in _units():
        if (u["deck_seed"], u["ply"], u["world"]) == (deck_seed, ply, world):
            return u
    raise KeyError((deck_seed, ply, world))


# --------------------------------------------------------------------------- #
# §1 THE SIGN CONVENTION — synth_mech.price_unit, built from a REAL unit's     #
#    margins (unit_999900000002_p114_w0.json: mover=1,                        #
#    margins pick_champ__champ=27 pick_armed__champ=26 pick_champ__armed=22   #
#    pick_armed__armed=26 -> delta_pts_mover champ=1 armed=-4 family_delta=-5) #
# --------------------------------------------------------------------------- #
REAL_MARGINS = {"pick_champ__champ": 27, "pick_armed__champ": 26,
                "pick_champ__armed": 22, "pick_armed__armed": 26}
REAL_WITNESS = {"root_repr_sha": "R", "world_deck_sha": "W", "world_deck_len": 8,
                "n_drawn_prefix": 63, "n_legal_root": 40,
                SM.DET_SEED_KEY: 999, "move_idx_at_root": 114}


def _mk_arms(margins, witness_overrides=None, family_witness_ok=True):
    witness_overrides = witness_overrides or {}
    arms = {}
    for name in SM.ARMS:
        pick, fam = name.split("__")
        w = dict(REAL_WITNESS)
        w.update(witness_overrides.get(name, {}))
        arms[name] = {
            "status": "OK", "arm": name, "pick": pick, "family": fam,
            "margin_p0_minus_p1": margins[name], "witness": w,
            "family_witness": {"ok": family_witness_ok,
                              "failures": [] if family_witness_ok else ["x"]},
        }
    return arms


def test_seat0_and_seat1_mover_sign_are_negations_on_real_margins():
    """The REAL unit is a seat-1 mover; a seat-0 read of the SAME margins must
    be the exact negation of the seat-1 read, on both families."""
    arms = _mk_arms(REAL_MARGINS)
    r0 = SM.price_unit(arms, mover=0)
    r1 = SM.price_unit(arms, mover=1)
    assert r0["status"] == r1["status"] == "OK"
    assert r0["delta_pts_mover"]["champ"] == -r1["delta_pts_mover"]["champ"]
    assert r0["delta_pts_mover"]["armed"] == -r1["delta_pts_mover"]["armed"]
    assert r0["family_delta"] == -r1["family_delta"]


def test_seat1_mover_reproduces_the_real_unit_s_recorded_price():
    """A regression pin: the hand-built arms, priced at the real unit's
    recorded mover (1), reproduce the real unit's `pair` block exactly."""
    real = _real_unit(999900000002, 114, 0)
    assert real["mover"] == 1
    r = SM.price_unit(_mk_arms(REAL_MARGINS), mover=1)
    assert r["delta_pts_mover"] == real["pair"]["delta_pts_mover"] == {"champ": 1, "armed": -4}
    assert r["family_delta"] == real["pair"]["family_delta"] == -5


def test_family_delta_is_armed_minus_champ_delta():
    r = SM.price_unit(_mk_arms(REAL_MARGINS), mover=1)
    assert r["family_delta"] == r["delta_pts_mover"]["armed"] - r["delta_pts_mover"]["champ"]


def test_identical_margins_price_to_exactly_zero_at_both_seats():
    flat = {k: 10 for k in SM.ARMS}
    for mover in (0, 1):
        r = SM.price_unit(_mk_arms(flat), mover=mover)
        assert r["delta_pts_mover"] == {"champ": 0, "armed": 0}
        assert r["family_delta"] == 0


@pytest.mark.parametrize("bad_status", ["TIME_SKIPPED", "OOM_SKIPPED", "ERROR"])
def test_a_unit_with_any_non_ok_arm_is_void(bad_status):
    arms = _mk_arms(REAL_MARGINS)
    arms["pick_armed__armed"] = {"status": bad_status}
    r = SM.price_unit(arms, mover=1)
    assert r["status"] == "VOID" and r["reason"] == "arm_not_ok"


def test_a_crn_witness_mismatch_across_arms_voids_the_unit():
    arms = _mk_arms(REAL_MARGINS, witness_overrides={
        "pick_armed__armed": {"root_repr_sha": "DIFFERENT"}})
    r = SM.price_unit(arms, mover=1)
    assert r["status"] == "VOID" and r["reason"] == "root_identity_mismatch"


def test_a_failed_family_witness_voids_the_unit_as_arm_witness_failed():
    arms = _mk_arms(REAL_MARGINS)
    arms["pick_armed__armed"]["family_witness"] = {"ok": False, "failures": ["x"]}
    r = SM.price_unit(arms, mover=1)
    assert r["status"] == "VOID" and r["reason"] == "arm_witness_failed"


# --------------------------------------------------------------------------- #
# §2 THE WITNESSES — scope_witness / champ_witness on the REAL fixture         #
#    censuses, mutated to drive each of the five armed failure modes           #
# --------------------------------------------------------------------------- #
def _real_armed_census():
    u = _real_unit(999900000001, 124, 0)      # identity unit: champ arms zero,
    return dict(u["arms"]["pick_armed__armed"]["jr_expansions"])   # armed nonzero


def _real_champ_census():
    u = _real_unit(999900000001, 124, 0)
    return dict(u["arms"]["pick_champ__champ"]["jr_expansions"])


def test_a_real_armed_census_passes_scope_witness():
    w = SM.scope_witness(_real_armed_census(), "opp")
    assert w["ok"], w["failures"]
    assert w["coverage"] == 1.0                # this fixture's boost is an exact partition


def test_a_real_champ_census_passes_champ_witness_as_exactly_all_zero():
    w = SM.champ_witness(_real_champ_census())
    assert w["ok"], w["failures"]


def test_armed_failure_1_missing_key_is_stale_wheel_not_zeros():
    """ABSENT is not zero: a missing key must fire the stale-wheel failure,
    never be silently treated as `boosted == 0`."""
    census = _real_armed_census()
    del census["boosted"]
    w = SM.scope_witness(census, "opp")
    assert not w["ok"]
    assert any(f.startswith("census_missing_keys") for f in w["failures"])
    assert w["coverage"] is None


def test_armed_failure_2_total_not_positive():
    census = _real_armed_census()
    census["total"] = 0
    w = SM.scope_witness(census, "opp")
    assert not w["ok"] and "total_not_positive" in w["failures"]


def test_armed_failure_3_own_mover_out_of_range():
    census = _real_armed_census()
    census["own_mover"] = census["total"] + 1
    w = SM.scope_witness(census, "opp")
    assert not w["ok"] and "own_mover_out_of_range" in w["failures"]


def test_armed_failure_4_boosted_not_positive_knob_never_expressed():
    census = _real_armed_census()
    census["boosted"] = 0
    w = SM.scope_witness(census, "opp")
    assert not w["ok"]
    assert "boosted_not_positive__knob_never_expressed" in w["failures"]


def test_armed_failure_5_boosted_outside_scope():
    census = _real_armed_census()
    den = census["total"] - census["own_mover"]
    census["boosted"] = den + 1
    w = SM.scope_witness(census, "opp")
    assert not w["ok"]
    assert any(f.startswith("boosted_outside_scope") for f in w["failures"])


def test_champ_census_missing_key_is_stale_wheel_not_zeros():
    census = _real_champ_census()
    del census["total"]
    w = SM.champ_witness(census)
    assert not w["ok"]
    assert any(f.startswith("census_missing_keys") for f in w["failures"])


def test_champ_census_nonzero_fails():
    census = _real_champ_census()
    census["boosted"] = 1
    w = SM.champ_witness(census)
    assert not w["ok"]


def test_family_witness_dispatches_on_family_name():
    armed_c, champ_c = _real_armed_census(), _real_champ_census()
    assert SM.family_witness(armed_c, "armed")["ok"]
    assert SM.family_witness(champ_c, "champ")["ok"]


# --------------------------------------------------------------------------- #
# §3 CRN / root_identity                                                       #
# --------------------------------------------------------------------------- #
def _real_witnesses(deck_seed=999900000002, ply=114, world=0):
    u = _real_unit(deck_seed, ply, world)
    return {name: dict(u["arms"][name]["witness"]) for name in SM.ARMS}


def test_the_real_four_arm_witness_set_passes_root_identity():
    ri = SM.root_identity(_real_witnesses())
    assert ri["ok"], ri


def test_a_mutated_crn_field_fails_root_identity_and_names_the_field():
    w = _real_witnesses()
    w["pick_armed__armed"]["root_repr_sha"] = "SOMETHING_ELSE"
    ri = SM.root_identity(w)
    assert not ri["ok"] and ri["reason"] == "root_identity_mismatch"
    assert "root_repr_sha" in ri["fields"]


@pytest.mark.parametrize("field", SM.CRN_WITNESS_KEYS)
def test_every_crn_field_is_gated_by_root_identity(field):
    w = _real_witnesses()
    orig = w["pick_armed__armed"][field]
    w["pick_armed__armed"][field] = "DIFFERENT" if isinstance(orig, str) else orig + 999
    ri = SM.root_identity(w)
    assert not ri["ok"] and field in ri["fields"]


def test_det_seed_base_differing_between_families_does_not_fail():
    """`det_seed_base_at_root` is an AGENT property; the two families are
    different agents, so a between-family difference is expected and must
    NOT fail root_identity — only a WITHIN-family difference may."""
    w = _real_witnesses()
    for pick in SM.PICKS:
        w[f"{pick}__champ"][SM.DET_SEED_KEY] = 111111
        w[f"{pick}__armed"][SM.DET_SEED_KEY] = 222222
    ri = SM.root_identity(w)
    assert ri["ok"], ri


def test_det_seed_base_differing_within_a_family_fails():
    w = _real_witnesses()
    for pick in SM.PICKS:
        w[f"{pick}__champ"][SM.DET_SEED_KEY] = 111111
        w[f"{pick}__armed"][SM.DET_SEED_KEY] = 222222
    w["pick_armed__armed"][SM.DET_SEED_KEY] = 333333     # breaks WITHIN armed
    ri = SM.root_identity(w)
    assert not ri["ok"] and ri["reason"] == "root_identity_mismatch"
    assert "armed" in ri["det_seed_families"]
    assert "champ" not in ri["det_seed_families"]


def test_root_identity_reports_arms_missing_when_an_arm_is_absent():
    w = _real_witnesses()
    del w["pick_armed__armed"]
    ri = SM.root_identity(w)
    assert not ri["ok"] and ri["reason"] == "arms_missing"


# --------------------------------------------------------------------------- #
# §4 THE FROZEN SELECTOR — synth_mech.build_targets                            #
# --------------------------------------------------------------------------- #
def test_build_targets_is_deterministic_same_input_byte_identical_output():
    rows = _select_rows()
    a = SM.build_targets(rows, n_per_stratum=3, n_identity=1)
    b = SM.build_targets(rows, n_per_stratum=3, n_identity=1)
    ga = "".join(json.dumps(r, sort_keys=True) + "\n" for r in a["targets"])
    gb = "".join(json.dumps(r, sort_keys=True) + "\n" for r in b["targets"])
    assert ga == gb


def test_build_targets_reproduces_the_frozen_targets_modulo_cell():
    """⚠️ `cell` is NOT reproducible from this fixture's select rows (module
    docstring) — the tercile edges depend on the full candidate pool, which
    selftest_fixture/select/ does not carry (it holds only the 7 rows that
    were FINALLY selected). Every OTHER field — stratum routing, picks, the
    shape census, the matching covariates themselves — reproduces
    byte-for-byte, which is what IS assertable from this fixture."""
    rows = _select_rows()
    built = SM.build_targets(rows, n_per_stratum=3, n_identity=1)
    want = [json.loads(l) for l in
           (FIX / "targets_fixture.jsonl").read_text().splitlines() if l.strip()]

    def strip_cell(r):
        r = dict(r)
        r.pop("cell", None)
        return r

    got_sorted = sorted(built["targets"], key=lambda r: (r["deck_seed"], r["ply"]))
    want_sorted = sorted(want, key=lambda r: (r["deck_seed"], r["ply"]))
    assert len(got_sorted) == len(want_sorted) == 7
    assert [strip_cell(r) for r in got_sorted] == [strip_cell(r) for r in want_sorted]
    sel = built["selection"]
    assert (sel["n_defense"], sel["n_control"], sel["n_identity"]) == (3, 3, 1)


def _mk_select_row(deck_seed, ply, *, stratum_raw, diverges=True, ply_frac=0.75,
                   n_legal=30, top2_gap_champ=0.02, n_plugs=None, n_plies=140):
    if n_plugs is None:
        n_plugs = 2 if stratum_raw == "defense" else 0
    return {
        "status": "OK", "schema": SM.SCHEMA + "/select",
        "deck_seed": deck_seed, "ply": ply, "profile": "fixed_v1",
        "n_plies": n_plies, "ply_frac": ply_frac, "mover": 0, "phase": "tiles",
        "n_legal": n_legal, "n_unseen_tiles": 10,
        "root_repr_sha": f"r{deck_seed}_{ply}",
        "pick_champ": 100 + ply, "pick_armed": (101 + ply) if diverges else 100 + ply,
        "diverges": diverges, "top2_gap_champ": top2_gap_champ,
        "top2_gap_armed": top2_gap_champ,
        "shape": {"n_plugs": n_plugs, "n_distinct_plug_cells": min(n_plugs, 1),
                 "n_tile_actions": n_legal, "plug_share": 0.0, "n_threat_pairs": 1,
                 "n_merge_cells": n_plugs, "n_victims": 1, "n_opp_parts": 1,
                 "max_threat_pts": 5.0, "threat_classes": ["farm"],
                 "cfg": {"victim_min_tiles": 5, "victim_min_pts": 4}},
        "stratum_raw": stratum_raw,
    }


def test_build_targets_respects_max_per_game_cap():
    rows = ([_mk_select_row(1, p, stratum_raw="defense") for p in (100, 102, 104)]
           + [_mk_select_row(2, p, stratum_raw="control") for p in (100, 102, 104, 106)])
    built = SM.build_targets(rows, n_per_stratum=10, n_identity=0, max_per_game=2)
    d_seeds = [r["deck_seed"] for r in built["targets"] if r["stratum"] == "defense"]
    c_seeds = [r["deck_seed"] for r in built["targets"] if r["stratum"] == "control"]
    assert d_seeds.count(1) <= 2
    assert c_seeds.count(2) <= 2


def test_build_targets_never_puts_a_non_divergent_ply_in_defense_or_control():
    rows = [_mk_select_row(1, 100, stratum_raw="defense", diverges=False),
           _mk_select_row(2, 100, stratum_raw="control", diverges=False)]
    built = SM.build_targets(rows, n_per_stratum=10, n_identity=10)
    strata = {r["stratum"] for r in built["targets"]}
    assert "defense" not in strata and "control" not in strata


def test_build_targets_never_puts_a_divergent_ply_in_identity():
    rows = [_mk_select_row(1, 100, stratum_raw="defense", diverges=True)
           for _ in (0,)]
    built = SM.build_targets(rows, n_per_stratum=10, n_identity=10)
    assert not [r for r in built["targets"] if r["stratum"] == "identity"]


def test_build_targets_identity_only_draws_from_agreeing_defense_shaped_rows():
    rows = [_mk_select_row(1, 100, stratum_raw="defense", diverges=False),
           _mk_select_row(2, 100, stratum_raw="control", diverges=False)]
    built = SM.build_targets(rows, n_per_stratum=0, n_identity=10)
    ident = [r for r in built["targets"] if r["stratum"] == "identity"]
    assert len(ident) == 1
    assert ident[0]["deck_seed"] == 1     # the control-shaped agree-row is excluded


# --------------------------------------------------------------------------- #
# §5 SHAPE PREDICATE — stratum_of                                              #
# --------------------------------------------------------------------------- #
def test_stratum_of_agrees_with_n_plugs_on_every_fixture_target_row():
    for row in _targets():
        want = "defense" if int(row["shape"]["n_plugs"]) >= 1 else "control"
        assert SM.stratum_of(row["shape"]) == want


def test_stratum_of_matches_every_non_identity_unit_s_stored_stratum():
    for u in _units():
        if u["stratum"] == "identity":
            continue
        assert SM.stratum_of(u["shape"]) == u["stratum"]


@pytest.mark.parametrize("n_plugs,want", [(0, "control"), (1, "defense"), (5, "defense")])
def test_stratum_of_boundary(n_plugs, want):
    assert SM.stratum_of({"n_plugs": n_plugs}) == want


# --------------------------------------------------------------------------- #
# §6 STATISTICS — the cluster-robust SE (adjudicate_synth)                     #
# --------------------------------------------------------------------------- #
def _plies(vals, seeds, field="family_delta"):
    return [{"deck_seed": s, "ply": i, field: v}
           for i, (s, v) in enumerate(zip(seeds, vals))]


def test_cluster_stats_reduces_to_plain_sem_when_every_ply_is_its_own_game():
    vals = [1.0, 3.0, -2.0, 5.0, 0.5, -1.5]
    seeds = list(range(len(vals)))          # every ply its own game
    plies = _plies(vals, seeds)
    cs = AD.cluster_stats(plies, field="family_delta")
    want_se = statistics.stdev(vals) / math.sqrt(len(vals))
    assert cs["n"] == len(vals) and cs["n_clusters"] == len(vals)
    assert cs["se"] == pytest.approx(want_se, rel=1e-9)
    assert cs["mean"] == pytest.approx(statistics.fmean(vals))


def test_a_duplicated_ply_within_one_game_inflates_the_se():
    vals = [1.0, 3.0, -2.0, 5.0, 0.5, -1.5]
    seeds = list(range(len(vals)))
    baseline = AD.cluster_stats(_plies(vals, seeds), field="family_delta")

    dup_seeds = list(seeds)
    dup_seeds[1] = dup_seeds[0]              # ply 1 now shares ply 0's game
    dup = AD.cluster_stats(_plies(vals, dup_seeds), field="family_delta")
    assert dup["se"] > baseline["se"]


def test_primary_influence_handles_a_game_shared_by_both_strata():
    defense = [{"deck_seed": 1, "ply": 0, "family_delta": 4.0},
              {"deck_seed": 2, "ply": 1, "family_delta": 2.0}]
    control = [{"deck_seed": 1, "ply": 2, "family_delta": -1.0},   # shares game 1
              {"deck_seed": 3, "ply": 3, "family_delta": 0.5}]
    c = AD.contrast(defense, control, field="family_delta")
    assert c["n_shared_clusters"] == 1
    assert c["diff"] == pytest.approx(statistics.fmean([4.0, 2.0])
                                      - statistics.fmean([-1.0, 0.5]))
    assert c["se"] is not None and c["se"] > 0
    # game 1's influence contribution is the SUM of its defense and control
    # contributions (it appears on both sides of the difference)
    ca, _ = AD._influence(defense, 1.0, "family_delta")
    cb, _ = AD._influence(control, -1.0, "family_delta")
    assert (ca[1] + cb[1]) != ca[1]     # game 1 gets a genuine combined term
    assert set(ca) | set(cb) == {1, 2, 3}


# --------------------------------------------------------------------------- #
# §7 THE ADJUDICATOR — the gate suite end to end, under --smoke                #
# --------------------------------------------------------------------------- #
def test_clean_fixtures_pass_every_gate_under_smoke():
    out = AD.analyse(_units(), _targets(), _manifest(), _selection(),
                     man_path=str(FIX / "manifest_fixture.json"),
                     targets_path=str(FIX / "targets_fixture.jsonl"),
                     selection_path=str(FIX / "SELECTION_fixture.json"),
                     smoke=True)
    failing = [g["gate"] for g in out["GATES"] if g["status"] != "PASS"]
    assert out["gates_all_pass"], failing
    assert {g["gate"] for g in out["GATES"]} == set(AD.GATES_ORDER)


def test_verdict_json_carries_branch_licence_and_forbidden_readings():
    out = AD.analyse(_units(), _targets(), _manifest(), _selection(),
                     man_path=str(FIX / "manifest_fixture.json"),
                     targets_path=str(FIX / "targets_fixture.jsonl"),
                     selection_path=str(FIX / "SELECTION_fixture.json"),
                     smoke=True)
    v = out["VERDICT"]
    assert isinstance(v.get("branch"), str) and v["branch"]
    assert isinstance(v.get("licenses"), str) and v["licenses"]
    assert v.get("forbidden_readings") == AD.FORBIDDEN_READINGS
    assert len(v["forbidden_readings"]) == 9


def test_a_correctness_void_fails_gates_and_never_reads_synth_void_instrument_as_null():
    units = copy.deepcopy(_units())
    units[0]["pair"] = {"status": "VOID", "reason": "root_identity_mismatch"}
    out = AD.analyse(units, _targets(), _manifest(), _selection(),
                     man_path=str(FIX / "manifest_fixture.json"),
                     targets_path=str(FIX / "targets_fixture.jsonl"),
                     selection_path=str(FIX / "SELECTION_fixture.json"),
                     smoke=True)
    assert not out["gates_all_pass"]
    assert out["VERDICT"]["branch"] == "SYNTH-VOID-INSTRUMENT"
    assert out["VERDICT"]["licenses"].startswith("⛔ NOTHING")


# --------------------------------------------------------------------------- #
# §8 FIXTURE PROVENANCE                                                        #
# --------------------------------------------------------------------------- #
def test_every_fixture_unit_is_the_right_schema_and_fully_landed():
    units = _units()
    assert len(units) == 14
    for u in units:
        assert u["schema"] == "defense-mech-synth/v1/unit"
        assert set(u["arms"]) == set(SM.ARMS)
        for name in SM.ARMS:
            assert u["arms"][name]["status"] == "OK"


def test_every_fixture_unit_s_deck_seed_is_in_the_throwaway_range():
    """Throwaway seeds are >= 999900000000 — outside any claimed band, so the
    fixtures can never be mistaken for banded data (PREREG §0.2 item 3)."""
    for u in _units():
        assert u["deck_seed"] >= 999900000000


def test_fixture_manifest_and_selection_agree_with_targets_sha256():
    want = AD.sha256_file(FIX / "targets_fixture.jsonl")
    assert _manifest()["targets_sha256"] == want
    assert _selection()["targets_sha256"] == want
