"""Contracts for `scripts/tiletie/build_positions.py` and `scripts/tiletie/run_tiletie.py`.

Unit tests only. No oracle runs, no champion searches, no gate runs, no
subprocesses that touch the engine. Census rows are synthesised in a tmp dir.

Covers:
  1. arm construction (reference = min(tie_actions_exact), ascending order,
     champion pick inside/outside the tie set, deterministic capping that never
     drops arms[0])
  2. rid STABILITY across legs of one position (the CRN contract)
  3. rid UNIQUENESS within a leg file, and across two E4 archives sharing a
     deck_seed
  4. every emitted line round-trips through
     `oracle_score_pilot.load_positions_jsonl` without raising
  5. `POSITIONS_PLAN.json` cost arithmetic against a hand-computed example
     (DESIGN.md #7.1)
  6. `run_tiletie.py` preflight refuses on a failing gate / missing positions
     file / a leg whose line count disagrees with the plan -- via
     monkeypatch/fakes, never a real gate or pilot run
  7. the smoke mode's CRN cross-leg witness checker, against synthetic
     `records/<rid>.json` files (no real oracle run)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "scripts" / "tiletie", REPO / "scripts" / "measurement_infra"):
    sp = str(_p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import build_positions as BP  # noqa: E402
import run_tiletie as RT  # noqa: E402

OSP = pytest.importorskip("oracle_score_pilot")


# --------------------------------------------------------------------------- #
# fixtures / helpers                                                            #
# --------------------------------------------------------------------------- #
def _row(**kw) -> dict:
    base = {
        "stratum": "e4", "source": "e4", "rules_profile": "fixed_v1",
        "game_label": "g1", "deck_seed": 1, "ply": 2, "seat": 0,
        "k_remaining": 40, "phase_bucket": "mid", "tercile": 1,
        "n_legal": 10, "n_cand": 10, "checksum": "CKSUM",
        "action_played": None, "tie_exact": True, "tie_size_exact": 2,
        "tie_actions_exact": [5, 7], "tie_actions_exact_truncated": False,
        "argmax_action": 5, "top1": 10.0, "top2": 10.0, "gap": 0.0,
    }
    base.update(kw)
    return base


# --------------------------------------------------------------------------- #
# 1. arm construction                                                           #
# --------------------------------------------------------------------------- #
def test_arm_reference_is_min_tie_actions_ascending():
    row = _row(tie_actions_exact=[9, 3, 7], argmax_action=3, tie_size_exact=3)
    out = BP.build_tie_arms(row, cap_j=4)
    assert out["arms"] == [3, 7, 9]
    assert out["capped"] is False
    assert out["dropped_actions"] == []


def test_arm_reference_mismatch_fails_loudly():
    row = _row(tie_actions_exact=[9, 3, 7], argmax_action=99, tie_size_exact=3)
    with pytest.raises(AssertionError):
        BP.build_tie_arms(row, cap_j=4)


def test_champion_pick_inside_tieset_records_index_no_growth():
    row = _row(action_played=7)
    tie = BP.build_tie_arms(row, cap_j=4)
    champ = BP.resolve_champion_arm(row, tie["arms"], {}, allow_missing=False)
    assert champ["arms"] == [5, 7]
    assert champ["champ_arm_index"] == 1
    assert champ["champ_outside_tieset"] is False
    assert champ["champ_action"] == 7


def test_champion_pick_outside_tieset_is_appended():
    row = _row(action_played=42)
    tie = BP.build_tie_arms(row, cap_j=4)
    champ = BP.resolve_champion_arm(row, tie["arms"], {}, allow_missing=False)
    assert champ["arms"] == [5, 7, 42]
    assert champ["champ_arm_index"] == 2
    assert champ["champ_outside_tieset"] is True


def test_selfplay_champion_pick_from_champ_picks_map():
    row = _row(stratum="selfplay", source="bank", rules_profile="walled",
              deck_seed=111, ply=3, tie_actions_exact=[2, 4], argmax_action=2,
              action_played=None)
    rid = BP.rid_for(row)
    tie = BP.build_tie_arms(row, cap_j=4)
    champ = BP.resolve_champion_arm(row, tie["arms"], {rid: {"champ_action": 99}},
                                    allow_missing=False)
    assert champ["arms"] == [2, 4, 99]
    assert champ["champ_outside_tieset"] is True


def test_selfplay_missing_champ_pick_raises_unless_allowed():
    row = _row(stratum="selfplay", source="bank", deck_seed=111, ply=3,
              tie_actions_exact=[2, 4], argmax_action=2)
    tie = BP.build_tie_arms(row, cap_j=4)
    with pytest.raises(KeyError):
        BP.resolve_champion_arm(row, tie["arms"], {}, allow_missing=False)
    champ = BP.resolve_champion_arm(row, tie["arms"], {}, allow_missing=True)
    assert champ["champ_pick_missing"] is True
    assert champ["arms"] == tie["arms"]           # unchanged -- no arm appended
    assert champ["champ_action"] is None


def test_cap_is_deterministic_and_never_drops_arm_zero():
    row = _row(tie_actions_exact=[1, 2, 3, 4, 5, 6, 7], argmax_action=1,
              tie_size_exact=7)
    out1 = BP.build_tie_arms(row, cap_j=4)
    out2 = BP.build_tie_arms(row, cap_j=4)
    assert out1 == out2                             # same rid -> same seed -> same draw
    assert out1["capped"] is True
    assert out1["arms"][0] == 1                      # arm[0] (the reference) is NEVER dropped
    assert len(out1["arms"]) == 4                     # cap_j=4 -> ref + 3 candidates
    assert set(out1["arms"][1:]) <= set(row["tie_actions_exact"][1:])
    assert sorted(out1["dropped_actions"] + out1["arms"][1:]) == row["tie_actions_exact"][1:]


def test_two_e4_archives_sharing_a_deck_seed_get_distinct_rids():
    # measurement/e4_games/ genuinely has two archives sharing deck_seed=523563
    # (1786325073_523563.json and 1786329790_523563.json) -- rid must key on
    # game_label, not deck_seed, or these would collide.
    a = _row(game_label="1786325073_523563", deck_seed=523563, ply=10)
    b = _row(game_label="1786329790_523563", deck_seed=523563, ply=10)
    assert BP.rid_for(a) != BP.rid_for(b)
    assert BP.root_id_for(a) != BP.root_id_for(b)


# --------------------------------------------------------------------------- #
# 2-4. full-pipeline: rid stability, uniqueness, round-trip                     #
# --------------------------------------------------------------------------- #
@pytest.fixture()
def built_positions(tmp_path):
    e4_dir = tmp_path / "e4_games"
    e4_dir.mkdir()
    (e4_dir / "g1.json").write_text(json.dumps({"actions": list(range(30))}))

    bank_path = tmp_path / "roots.jsonl"
    bank_path.write_text(json.dumps({"deck_seed": 111, "ply": 3,
                                     "actions": list(range(20)),
                                     "checksum": "BANKCKSUM"}) + "\n")
    champ_games_path = tmp_path / "champ_games.jsonl"
    champ_games_path.write_text("")

    row_a = _row(stratum="e4", source="e4", rules_profile="fixed_v1",
                game_label="g1", deck_seed=999, ply=2, seat=0,
                tie_actions_exact=[5, 7, 9], argmax_action=5, tie_size_exact=3,
                action_played=7, checksum="E4CKSUM")
    row_b = _row(stratum="selfplay", source="bank", rules_profile="walled",
                game_label=None, deck_seed=111, ply=3, seat=1,
                tie_actions_exact=[2, 4], argmax_action=2, tie_size_exact=2,
                action_played=4, checksum="BANKCKSUM")
    rid_b = BP.rid_for(row_b)

    out_dir = tmp_path / "positions"
    plan = BP.build(
        [row_a, row_b], out_dir=out_dir, champ_picks={rid_b: {"champ_action": 99}},
        cap_j=4, n=0, sample_seed=20260812, playout_secs=1.65, e4_dir=e4_dir,
        bank_roots_path=bank_path, champ_games_path=champ_games_path,
        allow_missing_champ_picks=False)
    return {"out_dir": out_dir, "plan": plan, "row_a": row_a, "row_b": row_b}


def test_rid_stable_across_legs(built_positions):
    out_dir = built_positions["out_dir"]
    leg1 = [json.loads(x) for x in
            (out_dir / "positions_fixed_v1_leg1.jsonl").read_text().splitlines()]
    leg2 = [json.loads(x) for x in
            (out_dir / "positions_fixed_v1_leg2.jsonl").read_text().splitlines()]
    assert len(leg1) == 1 and len(leg2) == 1
    # THE CRN CONTRACT (DESIGN #2.1): every leg of one position must carry the
    # IDENTICAL rid, because oracle_score_pilot derives its world/playout seeds
    # from sha256(tag|rid|j|salt) -- same rid across legs -> same M CRN worlds
    # for every arm at that position, with no change to the instrument at all.
    assert leg1[0]["rid"] == leg2[0]["rid"] == BP.rid_for(built_positions["row_a"])
    assert leg1[0]["pick_a"] == leg2[0]["pick_a"] == 5   # arm[0] identical too
    assert leg1[0]["pick_b"] == 7
    assert leg2[0]["pick_b"] == 9


def test_rid_uniqueness_within_leg_file_enforced_by_the_pilot(tmp_path):
    dup = tmp_path / "dup_leg1.jsonl"
    line = {"rid": "same", "deck_seed": 1, "ply": 0, "pick_a": 1, "pick_b": 2,
           "root_player": 0, "actions": [1, 2, 3]}
    dup.write_text(json.dumps(line) + "\n" + json.dumps(line) + "\n")
    with pytest.raises(ValueError, match="duplicate rid"):
        OSP.load_positions_jsonl(dup)


def test_every_emitted_line_round_trips_through_the_pilot_loader(built_positions):
    out_dir = built_positions["out_dir"]
    files = list(out_dir.glob("positions_*_leg*.jsonl"))
    assert len(files) == 4       # fixed_v1 leg1/leg2, walled leg1/leg2
    for f in files:
        items = OSP.load_positions_jsonl(f)
        assert items, f"{f} round-tripped to zero items"
        for it in items:
            assert isinstance(it["actions"], list) and it["actions"]
            assert it["pick_a"] != it["pick_b"]
            assert it["root_id"]


def test_arms_json_covers_every_rid_in_the_positions_files(built_positions):
    out_dir = built_positions["out_dir"]
    arms = json.loads((out_dir / "ARMS.json").read_text())
    for f in out_dir.glob("positions_*_leg*.jsonl"):
        for line in f.read_text().splitlines():
            rid = json.loads(line)["rid"]
            assert rid in arms


# --------------------------------------------------------------------------- #
# 5. POSITIONS_PLAN.json cost arithmetic vs a hand-computed example             #
# --------------------------------------------------------------------------- #
def test_cost_plan_matches_hand_computation():
    positions = [
        {"arms": [1, 2, 3], "capped": False, "stratum": "e4", "rules_profile": "fixed_v1"},
        {"arms": [1, 2], "capped": False, "stratum": "selfplay", "rules_profile": "walled"},
        {"arms": [1, 2, 3, 4, 5], "capped": True, "stratum": "selfplay",
         "rules_profile": "walled"},
    ]
    plan = BP.cost_plan(positions, cap_j=4, sample_seed=42, playout_secs=2.0,
                        m_worlds=32, t_champ_secs=10.0, workers=(14, 22))

    # hand computation, DESIGN.md #7.1:
    #   total_arm_playouts = sum((A_p - 1) * 2 * M)
    #     = (3-1)*2*32 + (2-1)*2*32 + (5-1)*2*32 = 128 + 64 + 256 = 448
    #   oracle_worker_secs = 448 * 2.0 = 896.0
    #   champ_pick_secs    = n_selfplay(2) * t_champ(10.0) = 20.0
    #   total_secs         = 916.0
    assert plan["n_positions"] == 3
    assert plan["n_e4"] == 1 and plan["n_selfplay"] == 2
    assert plan["max_arms"] == 5
    assert plan["mean_arms"] == pytest.approx(10 / 3)
    assert plan["n_positions_capped"] == 1
    assert plan["total_arm_playouts"] == 448
    assert plan["oracle_worker_secs"] == pytest.approx(896.0)
    assert plan["champ_pick_secs"] == pytest.approx(20.0)
    assert plan["total_worker_secs"] == pytest.approx(916.0)
    assert plan["eta_by_workers"]["W=14"]["wall_secs"] == pytest.approx(916.0 / 14)
    assert plan["eta_by_workers"]["W=14"]["wall_hours"] == pytest.approx(916.0 / (3600 * 14))
    assert plan["eta_by_workers"]["W=22"]["wall_secs"] == pytest.approx(916.0 / 22)
    assert plan["eta_by_workers"]["W=22"]["wall_hours"] == pytest.approx(916.0 / (3600 * 22))


def test_cost_plan_zero_positions_is_well_defined():
    plan = BP.cost_plan([], cap_j=4, sample_seed=1, playout_secs=1.65)
    assert plan["n_positions"] == 0
    assert plan["total_arm_playouts"] == 0
    assert plan["total_worker_secs"] == 0.0


# --------------------------------------------------------------------------- #
# schema-drift guard                                                            #
# --------------------------------------------------------------------------- #
def test_missing_required_field_fails_loudly(tmp_path):
    row = _row()
    del row["tie_exact"]
    p = tmp_path / "rows.jsonl"
    p.write_text(json.dumps(row) + "\n")
    with pytest.raises(KeyError, match="tie_exact"):
        BP.load_census_rows(p)


def test_load_census_rows_accepts_the_real_chain_census_schema(tmp_path):
    """Every REQUIRED_ROW_FIELDS key is a subset of chain_census.ROW_SCHEMA_KEYS
    (if that module is importable) -- guards against the two schemas silently
    drifting apart."""
    sys.path.insert(0, str(REPO / "scripts" / "tiletie"))
    cc = pytest.importorskip("chain_census")
    assert set(BP.REQUIRED_ROW_FIELDS) <= set(cc.ROW_SCHEMA_KEYS)


# =========================================================================== #
# 6. run_tiletie.py preflight -- refuses on a failing check, never runs a       #
#    real gate/pilot; only `check_positions` is exercised for real, with real   #
#    temp files, since that is pure filesystem/JSON logic.                      #
# =========================================================================== #
def _ok_check(**extra) -> dict:
    d = {"ok": True}
    d.update(extra)
    return d


def _run_argv(tmp_path, positions_dir, *, yes=False) -> list:
    argv = ["--positions-dir", str(positions_dir),
           "--gate-out", str(tmp_path / "GATE_RECHECK.json"),
           "--manifest-out", str(tmp_path / "RUN_MANIFEST.json"),
           "--smoke-manifest", str(tmp_path / "SMOKE_MANIFEST.json"),
           "--logs-dir", str(tmp_path / "logs"),
           "--out-root", str(tmp_path / "out_root"),
           "--workers", "2"]
    if yes:
        argv.append("--yes")
    return argv


def _mock_passing_engine_checks(monkeypatch) -> None:
    """gate/leaf_hash/git_clean all PASS -- only `check_positions` (real, pure
    filesystem+JSON) is left to decide the outcome."""
    monkeypatch.setattr(RT, "check_gate", lambda args: _ok_check(verdict="PASS",
                                                                 mismatches=[]))
    monkeypatch.setattr(RT, "check_leaf_hash", lambda: _ok_check())
    monkeypatch.setattr(RT, "check_git_clean",
                        lambda args: _ok_check(git_rev="abc123", dirty_paths=[]))


def _forbid_launch(monkeypatch) -> None:
    def _boom(*a, **kw):
        raise AssertionError("no subprocess may be launched when preflight refuses")
    monkeypatch.setattr(RT, "launch_legs", _boom)
    monkeypatch.setattr(RT.subprocess, "Popen", _boom)


def test_check_positions_flags_missing_file(tmp_path):
    pos_dir = tmp_path / "positions"
    pos_dir.mkdir()
    (pos_dir / "POSITIONS_PLAN.json").write_text(json.dumps(
        {"files": {"fixed_v1/leg1": {"path": str(pos_dir / "positions_fixed_v1_leg1.jsonl"),
                                     "n": 1}}}))
    (pos_dir / "ARMS.json").write_text(json.dumps({}))
    # the leg file itself is never written
    report = RT.check_positions(argparse.Namespace(positions_dir=str(pos_dir)))
    assert report["ok"] is False
    assert any("missing positions file" in p for p in report["problems"])


def test_check_positions_flags_line_count_mismatch(built_positions):
    out_dir = built_positions["out_dir"]
    leg1 = out_dir / "positions_fixed_v1_leg1.jsonl"
    extra = json.dumps({"rid": "extra", "deck_seed": 1, "ply": 0, "pick_a": 1,
                       "pick_b": 2, "root_player": 0, "actions": [1, 2]})
    leg1.write_text(leg1.read_text() + extra + "\n")
    report = RT.check_positions(argparse.Namespace(positions_dir=str(out_dir)))
    assert report["ok"] is False
    assert any("line count" in p for p in report["problems"])


def test_check_positions_passes_on_a_well_formed_plan(built_positions):
    report = RT.check_positions(
        argparse.Namespace(positions_dir=str(built_positions["out_dir"])))
    assert report["ok"] is True
    assert report["n_leg_files"] == 4


def test_preflight_refuses_when_gate_fails(monkeypatch, built_positions, tmp_path):
    monkeypatch.setattr(RT, "check_gate", lambda args: {"ok": False, "verdict": "FAIL",
                                                        "mismatches": [{"field": "x"}]})
    monkeypatch.setattr(RT, "check_leaf_hash", lambda: _ok_check())
    monkeypatch.setattr(RT, "check_git_clean",
                        lambda args: _ok_check(git_rev="abc123", dirty_paths=[]))
    args = RT.build_arg_parser().parse_args(
        _run_argv(tmp_path, built_positions["out_dir"]))
    report = RT.preflight(args)
    assert report["ok"] is False
    assert report["checks"]["gate"]["ok"] is False
    assert report["checks"]["positions"]["ok"] is True    # positions are fine on their own


def test_main_refuses_and_launches_nothing_when_gate_fails(monkeypatch, built_positions,
                                                            tmp_path):
    monkeypatch.setattr(RT, "check_gate", lambda args: {"ok": False, "verdict": "FAIL",
                                                        "mismatches": [{"field": "x"}]})
    monkeypatch.setattr(RT, "check_leaf_hash", lambda: _ok_check())
    monkeypatch.setattr(RT, "check_git_clean",
                        lambda args: _ok_check(git_rev="abc123", dirty_paths=[]))
    _forbid_launch(monkeypatch)

    rc = RT.main(_run_argv(tmp_path, built_positions["out_dir"], yes=True))
    assert rc == 2
    manifest = json.loads((tmp_path / "RUN_MANIFEST.json").read_text())
    assert manifest["error"] == "preflight_failed"
    assert manifest["legs"] == []


def test_main_refuses_when_a_positions_file_is_missing(monkeypatch, built_positions,
                                                        tmp_path):
    _mock_passing_engine_checks(monkeypatch)
    _forbid_launch(monkeypatch)
    (built_positions["out_dir"] / "positions_fixed_v1_leg1.jsonl").unlink()

    rc = RT.main(_run_argv(tmp_path, built_positions["out_dir"], yes=True))
    assert rc == 2
    manifest = json.loads((tmp_path / "RUN_MANIFEST.json").read_text())
    assert manifest["error"] == "preflight_failed"


def test_main_refuses_when_leg_line_count_disagrees(monkeypatch, built_positions, tmp_path):
    _mock_passing_engine_checks(monkeypatch)
    _forbid_launch(monkeypatch)
    leg1 = built_positions["out_dir"] / "positions_fixed_v1_leg1.jsonl"
    extra = json.dumps({"rid": "extra", "deck_seed": 1, "ply": 0, "pick_a": 1,
                       "pick_b": 2, "root_player": 0, "actions": [1, 2]})
    leg1.write_text(leg1.read_text() + extra + "\n")

    rc = RT.main(_run_argv(tmp_path, built_positions["out_dir"], yes=True))
    assert rc == 2


def test_main_without_yes_prints_plan_and_launches_nothing(monkeypatch, built_positions,
                                                            tmp_path):
    _mock_passing_engine_checks(monkeypatch)
    _forbid_launch(monkeypatch)

    rc = RT.main(_run_argv(tmp_path, built_positions["out_dir"], yes=False))
    assert rc == 0
    manifest = json.loads((tmp_path / "RUN_MANIFEST.json").read_text())
    assert manifest["legs"] == []
    assert manifest["error"] is None


# =========================================================================== #
# 7. the smoke mode's CRN cross-leg witness (peer-requested addendum)           #
# =========================================================================== #
def _rec(values_a, world_seeds, playout_seeds, deck_hash, crn_verified=True) -> dict:
    return {"values_a": values_a, "values_b": [v + 1 for v in values_a],
           "world_seeds": world_seeds, "playout_seeds": playout_seeds,
           "afterstate_deck_hash_a": deck_hash, "crn_verified": crn_verified}


def test_crn_cross_leg_passes_on_identical_records():
    leg1 = {"r1": _rec([1.0, 2.5, -3.25], [10, 20, 30], [1, 2, 3], "deadbeef")}
    leg2 = {"r1": _rec([1.0, 2.5, -3.25], [10, 20, 30], [1, 2, 3], "deadbeef")}
    out = RT.check_crn_cross_leg({1: leg1, 2: leg2})
    assert out["ok"] is True
    assert out["n_ok"] == out["n_rids"] == 1


def test_crn_cross_leg_catches_a_1ulp_values_a_divergence():
    leg1 = {"r1": _rec([1.0, 2.5, -3.25], [10, 20, 30], [1, 2, 3], "deadbeef")}
    nudged = math.nextafter(2.5, 3.0)             # exactly 1 ULP -- `==` on the
    assert nudged != 2.5                          # decimal repr can hide this
    leg2 = {"r1": _rec([1.0, nudged, -3.25], [10, 20, 30], [1, 2, 3], "deadbeef")}
    out = RT.check_crn_cross_leg({1: leg1, 2: leg2})
    assert out["ok"] is False
    assert any("values_a" in p for p in out["per_rid"]["r1"]["problems"])


def test_crn_cross_leg_catches_world_seed_divergence():
    leg1 = {"r1": _rec([1.0], [10], [1], "deadbeef")}
    leg2 = {"r1": _rec([1.0], [11], [1], "deadbeef")}
    out = RT.check_crn_cross_leg({1: leg1, 2: leg2})
    assert out["ok"] is False
    assert any("world_seeds" in p for p in out["per_rid"]["r1"]["problems"])


def test_crn_cross_leg_catches_playout_seed_divergence():
    leg1 = {"r1": _rec([1.0], [10], [1], "deadbeef")}
    leg2 = {"r1": _rec([1.0], [10], [2], "deadbeef")}
    out = RT.check_crn_cross_leg({1: leg1, 2: leg2})
    assert out["ok"] is False
    assert any("playout_seeds" in p for p in out["per_rid"]["r1"]["problems"])


def test_crn_cross_leg_catches_deck_hash_divergence():
    leg1 = {"r1": _rec([1.0], [10], [1], "deadbeef")}
    leg2 = {"r1": _rec([1.0], [10], [1], "cafef00d")}
    out = RT.check_crn_cross_leg({1: leg1, 2: leg2})
    assert out["ok"] is False
    assert any("afterstate_deck_hash_a" in p for p in out["per_rid"]["r1"]["problems"])


def test_crn_cross_leg_catches_crn_verified_false():
    leg1 = {"r1": _rec([1.0], [10], [1], "deadbeef", crn_verified=False)}
    leg2 = {"r1": _rec([1.0], [10], [1], "deadbeef")}
    out = RT.check_crn_cross_leg({1: leg1, 2: leg2})
    assert out["ok"] is False
    assert any("crn_verified" in p for p in out["per_rid"]["r1"]["problems"])


def test_crn_cross_leg_requires_matching_rid_sets():
    leg1 = {"r1": _rec([1.0], [10], [1], "deadbeef")}
    leg2 = {"r2": _rec([1.0], [10], [1], "deadbeef")}
    with pytest.raises(ValueError, match="rid set"):
        RT.check_crn_cross_leg({1: leg1, 2: leg2})


def test_crn_cross_leg_requires_at_least_two_legs():
    leg1 = {"r1": _rec([1.0], [10], [1], "deadbeef")}
    with pytest.raises(ValueError, match=">= 2 legs"):
        RT.check_crn_cross_leg({1: leg1})


def test_crn_cross_leg_scales_to_three_legs():
    leg1 = {"r1": _rec([1.0, 2.0], [10, 11], [1, 2], "deadbeef")}
    leg2 = {"r1": _rec([1.0, 2.0], [10, 11], [1, 2], "deadbeef")}
    leg3 = {"r1": _rec([1.0, 2.0], [10, 11], [1, 2], "deadbeef")}
    out = RT.check_crn_cross_leg({1: leg1, 2: leg2, 3: leg3})
    assert out["ok"] is True
    assert out["legs_checked"] == [1, 2, 3]


def test_load_leg_records_reads_from_disk(tmp_path):
    records_dir = tmp_path / "out" / "records"
    records_dir.mkdir(parents=True)
    (records_dir / "r1.json").write_text(json.dumps(_rec([1.0], [10], [1], "deadbeef")))
    recs = RT.load_leg_records(tmp_path / "out", ["r1"])
    assert recs["r1"]["values_a"] == [1.0]


def test_load_leg_records_raises_on_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        RT.load_leg_records(tmp_path / "nowhere", ["r1"])


# --------------------------------------------------------------------------- #
# smoke position selection/filtering (pure, no subprocess)                      #
# --------------------------------------------------------------------------- #
def test_select_smoke_positions_picks_multi_leg_rids(built_positions):
    out_dir = built_positions["out_dir"]
    sel = RT.select_smoke_positions(out_dir, min_arms=3, n=5)
    assert set(sel["rids"]) == {BP.rid_for(built_positions["row_a"]),
                                BP.rid_for(built_positions["row_b"])}
    assert sel["synthesized"] is True          # only 2 available, wanted 5
    assert sel["note"] is not None


def test_select_smoke_positions_empty_when_none_qualify(tmp_path):
    (tmp_path / "ARMS.json").write_text(json.dumps({"r1": {"arms": [1, 2]}}))  # no leg2
    sel = RT.select_smoke_positions(tmp_path, min_arms=3, n=5)
    assert sel["rids"] == []
    assert "NO positions" in sel["note"]


def test_build_smoke_positions_filters_to_chosen_rids(built_positions):
    out_dir = built_positions["out_dir"]
    rid_a = BP.rid_for(built_positions["row_a"])
    built = RT.build_smoke_positions(out_dir, [rid_a], "fixed_v1", legs=(1, 2))
    assert built[1]["n"] == 1 and built[1]["rids"] == [rid_a]
    assert built[2]["n"] == 1 and built[2]["rids"] == [rid_a]
    assert Path(built[1]["path"]).is_file()


# --------------------------------------------------------------------------- #
# Regressions for the two defects the 2026-08-12 SMOKE caught (SMOKE.md #2).    #
# Both were silent-or-costly, so both get a named test.                         #
# --------------------------------------------------------------------------- #
def test_select_smoke_positions_is_profile_aware(tmp_path):
    """REGRESSION: the smoke selector chose the globally-first eligible rids
    from the (global) ARMS.json and the caller then filtered a PER-PROFILE leg
    file, so the intersection was empty and the smoke "ran" in 0.2 s over ZERO
    positions while still printing a throughput number.

    `ARMS.json` is global; leg files are per rules profile (R9 is import-latched
    so a profile cannot share a process). Selection must therefore filter on
    `rules_profile` BEFORE taking the first n."""
    arms = {
        # alphabetically first, but a DIFFERENT profile -- the trap
        "tt_e4_aaa_p1": {"arms": [1, 2, 3], "rules_profile": "walled"},
        "tt_e4_aab_p2": {"arms": [1, 2, 3], "rules_profile": "walled"},
        "tt_e4_zzz_p3": {"arms": [4, 5, 6], "rules_profile": "fixed_v1"},
    }
    (tmp_path / "ARMS.json").write_text(json.dumps(arms))

    sel = RT.select_smoke_positions(tmp_path, profile="fixed_v1", min_arms=3, n=5)
    assert sel["rids"] == ["tt_e4_zzz_p3"], "must not leak other profiles' rids"

    sel_w = RT.select_smoke_positions(tmp_path, profile="walled", min_arms=3, n=5)
    assert sel_w["rids"] == ["tt_e4_aaa_p1", "tt_e4_aab_p2"]

    # profile=None keeps the old global behaviour (used only by callers that
    # genuinely want every profile).
    assert len(RT.select_smoke_positions(tmp_path, profile=None, min_arms=3,
                                         n=5)["rids"]) == 3


def test_backend_is_resolved_per_profile_not_per_judge():
    """REGRESSION: rust was selected from the JUDGE alone, but the clairvoyant
    Rust ruler cannot mirror non-default rules -- `RustCarryClairvoyantAgent`
    seeds `MirrorState.from_deck()` with no geometry/rules config, so on
    `fixed_v1` every position failed (5/5 in the smoke). Only `walled` (whose
    `game_kwargs()` is `{}`) may use rust."""
    assert RT.backend_for("clair-puct", "walled") == "rust"
    assert RT.backend_for("clair-puct", "fixed_v1") == "python"
    assert RT.backend_for("clair-puct", "app_aug2") == "python"
    # tier1-greedy is python everywhere -- it is out of the identity gate's scope
    for prof in ("walled", "fixed_v1", "app_aug2"):
        assert RT.backend_for("tier1-greedy", prof) == "python"


def test_leg_command_carries_the_profile_resolved_backend():
    """The per-profile backend must reach the actual pilot argv, not just the
    helper (the smoke's failure was in argv, not in a helper)."""
    def argv_for(profile):
        return RT.leg_command(
            positions_path="/tmp/p.jsonl", profile=profile, judge="clair-puct",
            m=32, oracle_sims=100, workers=4, n=10, out_root="/tmp/out",
            out_subdir="x", resume=True)

    walled = argv_for("walled")
    assert walled[walled.index("--backend") + 1] == "rust"
    fixed = argv_for("fixed_v1")
    assert fixed[fixed.index("--backend") + 1] == "python"
    # --n is ALWAYS explicit: the pilot defaults to 20 and a per-leg subsample
    # would destroy the cross-leg CRN.
    assert "--n" in fixed and fixed[fixed.index("--n") + 1] == "10"
