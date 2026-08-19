#!/usr/bin/env python3
"""Tests for the rung3_r5 staging assembler
(`scripts/tiletie/stage_r5_corpus.py`, drafter commit `97ca0276`'s six-step
recipe, `G-STAGED`).

Covers: every witness field STAGING_R5.json carries; byte-identity failure
on the ARMS copy refuses; the cross-layer invariant fires in BOTH
directions (missing-from-leg and missing-from-ARMS, separately and
together); POSITIONS_PLAN's files-block existence/count/rid-set assertion;
the real-data end-to-end (into a scratch RUN dir, never the live campaign
root) producing the staged dir + STAGING_R5 witness + a REAL `stage_chunks.py
stage` agreement on the real 1,060-rid population; and that the FLOORS sha
the drafter landed (commit `97ca0276`) matches what this build actually
produces.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TILETIE = REPO / "scripts" / "tiletie"
if str(TILETIE) not in sys.path:
    sys.path.insert(0, str(TILETIE))

import build_r5_corpus as BR5                                       # noqa: E402
import gate_disjoint as GD                                          # noqa: E402
import stage_r5_corpus as SR5                                       # noqa: E402
import union_positions as UP                                        # noqa: E402

#: the value drafter commit 97ca0276 landed in FLOORS_R5.json::
#: population_authority.arms_r5_sha256 -- this suite's job is to CONFIRM
#: this build reproduces it, never to author it (FLOORS_R5.json is the
#: drafter's worktree file).
LANDED_ARMS_R5_SHA256 = ("adb4c5bd7cf904a1fe00c839eab722fa79798b9f719b631"
                         "b6f788900f3e5cf8a")

_REL_LEG = "measurement/tiearb_widening_20260817/shared_run_r4/corpus/positions_s2/positions_walled_leg1.jsonl"
_REL_GD = "measurement/tiearb_widening_20260817/shared_run_r4/GATE_DISJOINT.json"
_REL_ARMS = "measurement/tiearb_widening_20260817/shared_run_r4/corpus/positions_s2/ARMS.json"
_REL_PLAN = "measurement/tiearb_widening_20260817/shared_run_r4/corpus/positions_s2/POSITIONS_PLAN.json"
_MAIN_CHECKOUT = Path("/home/doctor/projects/carcassone")


def _first_existing(*candidates):
    for c in candidates:
        if c.is_file():
            return c
    return candidates[0]


REAL_LEG = _first_existing(REPO / _REL_LEG, _MAIN_CHECKOUT / _REL_LEG)
REAL_R4_GATE_DISJOINT = _first_existing(REPO / _REL_GD, _MAIN_CHECKOUT / _REL_GD)
REAL_R4_ARMS = _first_existing(REPO / _REL_ARMS, _MAIN_CHECKOUT / _REL_ARMS)
REAL_R4_SOURCE_PLAN = _first_existing(REPO / _REL_PLAN, _MAIN_CHECKOUT / _REL_PLAN)
_REAL_INPUTS_PRESENT = (REAL_LEG.is_file() and REAL_R4_GATE_DISJOINT.is_file()
                        and REAL_R4_ARMS.is_file()
                        and REAL_R4_SOURCE_PLAN.is_file())


def make_synthetic_source_plan(tmp_path, *, applied=True, name="R4_SOURCE_PLAN.json"):
    """A synthetic R4-source-plan-shaped file, WITH a genuine
    `afterstate_dedupe` block (or, with `applied=False`, deliberately
    without one — for the refuses-loudly test)."""
    body = {
        "schema": "fixture", "m_worlds": 32, "cap_j": None, "uncapped": True,
        "deployed_cap_j": 4, "sample_seed": 1,
        "playout_secs": 0.19, "t_champ_secs": 13.755,
    }
    if applied:
        body["afterstate_dedupe"] = {
            "applied": True,
            "design_ref": "DESIGN.md §6 threat 3 (fixture)",
            "dropped_index_path": str(tmp_path / "DROPPED_ALL_TRANSPOSITION.json"),
            "n_dropped_all_transposition": 0,
        }
    p = tmp_path / name
    p.write_text(json.dumps(body))
    return p


# --------------------------------------------------------------------------- #
# synthetic fixture builders                                                   #
# --------------------------------------------------------------------------- #
def make_synthetic_arms_and_leg(tmp_path, *, n=4, prefix="tt_sp", arm_counts=None):
    """`n` matched rows -- a `positions dir`-shaped leg (COMPLETE schema:
    `root_player`/`rules_profile`/`stratum`/`game_label`/`action_played`/
    `actions`, everything `derive_legs`' `_position_from_leg1_row` needs) +
    a `build_arms_index`-shaped ARMS_R5.json, same rid set by construction.
    `arm_counts` (default all 2 -- leg1 only, no thinning) lets a caller
    build a THINNING population for the leg-ladder tests."""
    arm_counts = list(arm_counts) if arm_counts is not None else [2] * n
    assert len(arm_counts) == n
    rows = []
    for i in range(n):
        seed = 135000000350 + i
        rows.append({"rid": f"{prefix}_{seed}_p{10 + i}",
                    "root_id": f"sp_{seed}", "deck_seed": seed,
                    "ply": 10 + i, "checksum": f"C{i}",
                    "root_player": 0, "rules_profile": "walled",
                    "stratum": "selfplay", "game_label": f"g{seed}",
                    "action_played": 1, "actions": [1, 2, 3]})
    leg = tmp_path / "leg.jsonl"
    leg.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    arms = {r["rid"]: {"arms": list(range(1, k + 1)), "root_id": r["root_id"],
                       "stratum": "selfplay", "rules_profile": "walled",
                       "game_label": r["game_label"],
                       "deck_seed": r["deck_seed"], "ply": r["ply"],
                       "seat": 0, "k_remaining": 10, "phase_bucket": "mid",
                       "tercile": 1, "n_legal": k, "n_cand": k,
                       "tie_size_exact": k, "gap": 0.0, "capped": False,
                       "dropped_actions": [], "champ_action": 1,
                       "champ_arm_index": 0, "champ_outside_tieset": False}
           for r, k in zip(rows, arm_counts)}
    arms_r5 = tmp_path / "ARMS_R5.json"
    arms_r5.write_text(json.dumps(arms))
    return arms_r5, leg, rows


# =========================================================================== #
# step 1-2 -- the byte-identical ARMS copy                                     #
# =========================================================================== #
def test_arms_copy_witness_fields(tmp_path):
    arms_r5, _, _ = make_synthetic_arms_and_leg(tmp_path)
    staged_dir = tmp_path / "staged"
    w = SR5.stage_arms_copy(arms_r5, staged_dir)
    assert set(w) == {"arms_r5_sha256", "staged_arms_sha256",
                      "arms_copy_identical", "staged_arms_path"}
    assert isinstance(w["arms_r5_sha256"], str) and len(w["arms_r5_sha256"]) == 64
    assert isinstance(w["staged_arms_sha256"], str) and len(w["staged_arms_sha256"]) == 64
    assert w["arms_r5_sha256"] == w["staged_arms_sha256"]
    assert w["arms_copy_identical"] is True
    assert (staged_dir / "ARMS.json").is_file()
    assert (staged_dir / "ARMS.json").read_bytes() == arms_r5.read_bytes()


def test_arms_copy_is_not_a_symlink(tmp_path):
    """R4-0.5: symlinks are explicitly ruled out (write-through hazard,
    breaks on archive/move)."""
    arms_r5, _, _ = make_synthetic_arms_and_leg(tmp_path)
    staged_dir = tmp_path / "staged"
    SR5.stage_arms_copy(arms_r5, staged_dir)
    assert not (staged_dir / "ARMS.json").is_symlink()


def test_arms_copy_byte_identity_failure_refuses(tmp_path, monkeypatch):
    arms_r5, _, _ = make_synthetic_arms_and_leg(tmp_path)
    staged_dir = tmp_path / "staged"
    real_write_bytes = Path.write_bytes

    def corrupt_write_bytes(self, data):
        # simulate an I/O corruption ONLY on the staged copy, so the source
        # ARMS_R5.json itself is untouched
        if self.name == "ARMS.json":
            data = data + b"CORRUPTED"
        return real_write_bytes(self, data)

    monkeypatch.setattr(Path, "write_bytes", corrupt_write_bytes)
    with pytest.raises(SR5.StagingError, match="NOT byte-identical"):
        SR5.stage_arms_copy(arms_r5, staged_dir)


def test_arms_copy_missing_source_raises(tmp_path):
    with pytest.raises(SR5.StagingError, match="not found"):
        SR5.stage_arms_copy(tmp_path / "nope.json", tmp_path / "staged")


# =========================================================================== #
# step 3 -- leg filter, THROUGH assert_rid_sets_equal                          #
# =========================================================================== #
def test_leg_filter_keeps_only_arms_rids(tmp_path):
    arms_r5, leg, rows = make_synthetic_arms_and_leg(tmp_path, n=4)
    arms_rids = set(json.loads(arms_r5.read_text()))
    staged_dir = tmp_path / "staged"
    staged_dir.mkdir()
    dest, kept = SR5.stage_leg_filter(leg, arms_rids, staged_dir)
    assert kept == arms_rids
    assert dest.is_file()
    on_disk = {json.loads(ln)["rid"] for ln in dest.read_text().splitlines() if ln.strip()}
    assert on_disk == arms_rids


def test_leg_filter_drops_rows_outside_arms(tmp_path):
    arms_r5, leg, rows = make_synthetic_arms_and_leg(tmp_path, n=4)
    arms_rids = set(json.loads(arms_r5.read_text()))
    # a leg with one EXTRA row the ARMS set does not have
    extra_row = {"rid": "tt_sp_999_p1", "root_id": "sp_999",
                "deck_seed": 999, "ply": 1, "checksum": "EXTRA"}
    leg2 = tmp_path / "leg_with_extra.jsonl"
    leg2.write_text(leg.read_text() + json.dumps(extra_row) + "\n")
    staged_dir = tmp_path / "staged2"
    staged_dir.mkdir()
    dest, kept = SR5.stage_leg_filter(leg2, arms_rids, staged_dir)
    assert "tt_sp_999_p1" not in kept
    assert kept == arms_rids


def test_leg_filter_missing_rid_raises_via_assert_rid_sets_equal(tmp_path, monkeypatch):
    arms_r5, leg, rows = make_synthetic_arms_and_leg(tmp_path, n=4)
    arms_rids = set(json.loads(arms_r5.read_text()))
    # a leg MISSING one of the ARMS rids entirely
    lines = [ln for ln in leg.read_text().splitlines() if ln.strip()]
    leg3 = tmp_path / "leg_missing_one.jsonl"
    leg3.write_text("\n".join(lines[:-1]) + "\n")
    staged_dir = tmp_path / "staged3"
    staged_dir.mkdir()

    calls = []
    real = BR5.assert_rid_sets_equal

    def spy(actual, expected, **kw):
        calls.append((set(actual), set(expected)))
        return real(actual, expected, **kw)

    monkeypatch.setattr(SR5.BR5, "assert_rid_sets_equal", spy)
    with pytest.raises(BR5.BuildError):
        SR5.stage_leg_filter(leg3, arms_rids, staged_dir)
    assert len(calls) == 1   # proves step 3 runs THROUGH the checked tool


# =========================================================================== #
# step 4 -- the cross-layer invariant, BOTH directions, via check_leg_layer    #
# =========================================================================== #
def test_cross_layer_invariant_passes_with_empty_witness_lists():
    w = SR5.cross_layer_invariant({"a", "b"}, {"a", "b"}, where="x")
    assert w == {"n_leg_rids": 2, "n_arms_rids": 2, "rid_sets_equal": True,
                "missing_in_leg": [], "missing_in_arms": []}


def test_cross_layer_invariant_fires_missing_in_leg_direction():
    """ARMS has a rid the leg lacks -- "missing_in_leg" (D4's UNSCORABLE
    direction: a position ARMS claims exists but no leg line backs it)."""
    with pytest.raises(SR5.StagingError, match="missing from the leg"):
        SR5.cross_layer_invariant({"a", "b", "c"}, {"a", "b"}, where="x")


def test_cross_layer_invariant_fires_missing_in_arms_direction():
    """The leg has a rid ARMS lacks -- "missing_in_arms" (D4's UNPLANNED
    direction: a leg line for a position no plan claims)."""
    with pytest.raises(SR5.StagingError, match="missing from ARMS"):
        SR5.cross_layer_invariant({"a", "b"}, {"a", "b", "d"}, where="x")


def test_cross_layer_invariant_fires_both_directions_at_once():
    with pytest.raises(SR5.StagingError) as exc:
        SR5.cross_layer_invariant({"a", "c"}, {"a", "d"}, where="x")
    msg = str(exc.value)
    assert "1 rid(s) missing from the leg" in msg
    assert "1 missing from ARMS" in msg


def test_cross_layer_invariant_uses_check_leg_layer(monkeypatch):
    """The EXISTING checked tool -- never a re-implementation."""
    calls = []
    real = UP.check_leg_layer

    def spy(arms_rids, leg_rids, **kw):
        calls.append((set(arms_rids), set(leg_rids)))
        return real(arms_rids, leg_rids, **kw)

    monkeypatch.setattr(SR5.UP, "check_leg_layer", spy)
    SR5.cross_layer_invariant({"a"}, {"a"}, where="x")
    assert len(calls) == 1


# =========================================================================== #
# step 5 -- POSITIONS_PLAN.json: COPY the R4 source, recompute ONLY the        #
# rid-set-dependent keys (via stage_chunks.subset_plan)                        #
# =========================================================================== #
def test_positions_plan_files_block_shape_and_existence(tmp_path):
    arms_r5_path, leg, rows = make_synthetic_arms_and_leg(tmp_path, n=4)
    arms_r5 = json.loads(arms_r5_path.read_text())
    source_plan_path = make_synthetic_source_plan(tmp_path)
    source_plan = json.loads(source_plan_path.read_text())
    staged_dir = tmp_path / "staged"
    staged_dir.mkdir()
    leg_dest = staged_dir / "positions_walled_leg1.jsonl"
    leg_dest.write_text(leg.read_text())
    files = {SR5.DEFAULT_LEG_KEY: {"path": str(leg_dest), "n": 4}}
    plan_path, plan, carried = SR5.write_positions_plan(
        staged_dir, files, arms_r5, source_plan)
    assert plan_path.is_file()
    assert plan["n_positions"] == 4
    assert plan["cap_j"] is None                 # COPIED from source
    assert plan["uncapped"] is True               # COPIED from source
    assert plan["max_per_game"] == SR5.DEFAULT_MAX_PER_GAME  # the one addition
    assert plan["m_worlds"] == 32                 # COPIED from source
    assert plan["afterstate_dedupe"]["applied"] is True   # COPIED, with provenance
    assert plan["afterstate_dedupe"]["design_ref"]
    assert SR5.DEFAULT_LEG_KEY in plan["files"]
    info = plan["files"][SR5.DEFAULT_LEG_KEY]
    assert Path(info["path"]) == leg_dest
    assert info["n"] == 4
    assert Path(info["path"]).is_file()
    # "chunk"/"label" are chunk-only provenance, stripped at the corpus level
    assert "chunk" not in plan
    assert "label" not in plan
    # carried_keys is the EXPLICIT enumeration: source keys minus
    # RID_DEPENDENT_KEYS
    assert set(carried) == set(source_plan) - SR5.SC.RID_DEPENDENT_KEYS
    assert "afterstate_dedupe" in carried
    assert "cap_j" in carried
    assert "m_worlds" in carried
    assert "n_positions" not in carried            # rid-dependent -- recomputed


def test_positions_plan_rejects_a_files_block_with_orphan_rids(tmp_path):
    """D4's defect: a files block whose rid set does not match the
    population it claims. Here the leg on disk carries a rid ARMS_R5 does
    NOT have -- the plan may never name a population its files do not
    contain."""
    arms_r5_path, leg, rows = make_synthetic_arms_and_leg(tmp_path, n=4)
    arms_r5 = json.loads(arms_r5_path.read_text())
    source_plan = json.loads(make_synthetic_source_plan(tmp_path).read_text())
    staged_dir = tmp_path / "staged"
    staged_dir.mkdir()
    leg_dest = staged_dir / "positions_walled_leg1.jsonl"
    orphan = {"rid": "tt_sp_orphan_p1", "root_id": "sp_orphan",
             "deck_seed": 1, "ply": 1, "checksum": "X"}
    leg_dest.write_text(leg.read_text() + json.dumps(orphan) + "\n")
    files = {SR5.DEFAULT_LEG_KEY: {"path": str(leg_dest), "n": 5}}
    with pytest.raises(SR5.StagingError, match="not in ARMS_R5"):
        SR5.write_positions_plan(staged_dir, files, arms_r5, source_plan)


def test_positions_plan_rejects_missing_leg_file(tmp_path):
    arms_r5_path, leg, rows = make_synthetic_arms_and_leg(tmp_path, n=4)
    arms_r5 = json.loads(arms_r5_path.read_text())
    source_plan = json.loads(make_synthetic_source_plan(tmp_path).read_text())
    staged_dir = tmp_path / "staged"
    staged_dir.mkdir()
    ghost = staged_dir / "positions_walled_leg1.jsonl"
    files = {SR5.DEFAULT_LEG_KEY: {"path": str(ghost), "n": 4}}
    # never written -- write_positions_plan asserts every files{} path exists
    with pytest.raises(SR5.StagingError, match="does not exist"):
        SR5.write_positions_plan(staged_dir, files, arms_r5, source_plan)


# =========================================================================== #
# DESIGN ruling 63ed329b -- legs 2-N DERIVED from the pinned authority,        #
# never adopted (the adopted S2 build is TRUNCATED to leg1)                    #
# =========================================================================== #
def make_thinning_arms_and_leg1(tmp_path):
    """A synthetic THINNING population: arm counts 5, 4, 3, 2, 2 -- so
    `len(arms) > r` gives leg1=5, leg2=3, leg3=2, leg4=1, and no leg5 at
    all (max arm count is 5, so r only goes up to 4). Total pairs =
    sum(k-1 for k in counts) = 4+3+2+1+1 = 11."""
    arms_r5_path, leg, rows = make_synthetic_arms_and_leg(
        tmp_path, n=5, arm_counts=[5, 4, 3, 2, 2])
    return arms_r5_path, leg, rows


def test_derive_legs_on_synthetic_thinning_arm_set(tmp_path):
    arms_r5_path, leg, rows = make_thinning_arms_and_leg1(tmp_path)
    arms_r5 = json.loads(arms_r5_path.read_text())
    staged_dir = tmp_path / "staged"
    staged_dir.mkdir()
    leg1_dest = staged_dir / "positions_walled_leg1.jsonl"
    leg1_dest.write_text(leg.read_text())
    leg1_rows = SR5.load_leg_rows(leg1_dest)

    derived = SR5.derive_legs(arms_r5, leg1_rows, staged_dir)
    # leg1 is NOT re-derived (the adopted file stays authoritative) --
    # derive_legs only returns r >= 2
    assert all(int(k.rpartition("/leg")[2]) >= 2 for k in derived["files"])
    assert "walled/leg2" in derived["files"]
    assert "walled/leg3" in derived["files"]
    assert "walled/leg4" in derived["files"]
    assert "walled/leg5" not in derived["files"]   # max arm count is 5 -> no leg5

    for key, info in derived["files"].items():
        assert Path(info["path"]).is_file()
        # every derived leg file must actually live IN staged_dir, not a
        # leftover temp path
        assert Path(info["path"]).parent == staged_dir

    leg2_rids = set(SR5.load_leg_rows(Path(derived["files"]["walled/leg2"]["path"])))
    expected_leg2 = {rid for rid, v in arms_r5.items() if len(v["arms"]) > 2}
    assert leg2_rids == expected_leg2
    assert len(leg2_rids) == 3          # arm counts 5,4,3 qualify (>2 arms)

    leg4_rids = set(SR5.load_leg_rows(Path(derived["files"]["walled/leg4"]["path"])))
    expected_leg4 = {rid for rid, v in arms_r5.items() if len(v["arms"]) > 4}
    assert leg4_rids == expected_leg4
    assert len(leg4_rids) == 1          # only the arm-count-5 position qualifies


def test_derive_legs_row_schema_matches_write_leg_files(tmp_path):
    """The derived rows carry the EXACT `write_leg_files` schema -- pick_a/
    pick_b from the arm list, checksum/actions/action_played carried from
    the adopted leg1 row, action_best recomputed as arms[r]."""
    arms_r5_path, leg, rows = make_thinning_arms_and_leg1(tmp_path)
    arms_r5 = json.loads(arms_r5_path.read_text())
    staged_dir = tmp_path / "staged"
    staged_dir.mkdir()
    leg1_dest = staged_dir / "positions_walled_leg1.jsonl"
    leg1_dest.write_text(leg.read_text())
    leg1_rows = SR5.load_leg_rows(leg1_dest)

    derived = SR5.derive_legs(arms_r5, leg1_rows, staged_dir)
    leg2_path = Path(derived["files"]["walled/leg2"]["path"])
    leg2_rows = SR5.load_leg_rows(leg2_path)
    rid = next(iter(leg2_rows))
    row = leg2_rows[rid]
    arms = arms_r5[rid]["arms"]
    assert row["pick_a"] == arms[0]
    assert row["pick_b"] == arms[2]
    assert row["action_best"] == arms[2]
    assert row["checksum"] == leg1_rows[rid]["checksum"]        # carried from leg1
    assert row["actions"] == leg1_rows[rid]["actions"]           # carried from leg1
    assert row["action_played"] == leg1_rows[rid]["action_played"]
    assert row["root_player"] == leg1_rows[rid]["root_player"]
    assert row["rules_profile"] == leg1_rows[rid]["rules_profile"]


def test_derive_legs_missing_leg1_row_raises(tmp_path):
    arms_r5_path, leg, rows = make_thinning_arms_and_leg1(tmp_path)
    arms_r5 = json.loads(arms_r5_path.read_text())
    staged_dir = tmp_path / "staged"
    staged_dir.mkdir()
    leg1_dest = staged_dir / "positions_walled_leg1.jsonl"
    leg1_dest.write_text(leg.read_text())
    leg1_rows = SR5.load_leg_rows(leg1_dest)
    del leg1_rows[next(iter(leg1_rows))]   # drop one rid's source row
    with pytest.raises(SR5.StagingError, match="no adopted leg1 row"):
        SR5.derive_legs(arms_r5, leg1_rows, staged_dir)


def test_assert_leg_ladder_exact_predicate_per_leg(tmp_path):
    arms_r5_path, leg, rows = make_thinning_arms_and_leg1(tmp_path)
    arms_r5 = json.loads(arms_r5_path.read_text())
    staged_dir = tmp_path / "staged"
    staged_dir.mkdir()
    leg1_dest = staged_dir / "positions_walled_leg1.jsonl"
    leg1_dest.write_text(leg.read_text())
    leg1_rows = SR5.load_leg_rows(leg1_dest)
    SR5.derive_legs(arms_r5, leg1_rows, staged_dir)

    witness = SR5.assert_leg_ladder(arms_r5, staged_dir, legs=(1, 2, 3, 4),
                                    pinned_counts=(5, 3, 2, 1))
    assert witness["leg_counts"] == {"1": 5, "2": 3, "3": 2, "4": 1}
    assert witness["leg_ladder_matches_expected"] is True
    assert witness["n_total_pairs"] == 5 + 3 + 2 + 1        # == 11


def test_assert_leg_ladder_mismatch_refuses(tmp_path):
    """A WRONG pinned ladder must REFUSE, not silently record the
    disagreement -- this is the substantive check DESIGN ruling `63ed329b`
    pins, not a tautology of the per-leg predicate (which the realized
    counts always satisfy by construction)."""
    arms_r5_path, leg, rows = make_thinning_arms_and_leg1(tmp_path)
    arms_r5 = json.loads(arms_r5_path.read_text())
    staged_dir = tmp_path / "staged"
    staged_dir.mkdir()
    leg1_dest = staged_dir / "positions_walled_leg1.jsonl"
    leg1_dest.write_text(leg.read_text())
    leg1_rows = SR5.load_leg_rows(leg1_dest)
    SR5.derive_legs(arms_r5, leg1_rows, staged_dir)

    with pytest.raises(SR5.StagingError, match="does NOT match the PINNED ladder"):
        SR5.assert_leg_ladder(arms_r5, staged_dir, legs=(1, 2, 3, 4),
                              pinned_counts=(5, 3, 2, 999))     # wrong leg4 count


def test_assert_leg_ladder_missing_leg_file_refuses(tmp_path):
    arms_r5_path, leg, rows = make_thinning_arms_and_leg1(tmp_path)
    arms_r5 = json.loads(arms_r5_path.read_text())
    staged_dir = tmp_path / "staged"
    staged_dir.mkdir()
    leg1_dest = staged_dir / "positions_walled_leg1.jsonl"
    leg1_dest.write_text(leg.read_text())
    # legs 2-4 deliberately NOT derived -- exactly the truncated-build defect
    with pytest.raises(SR5.StagingError, match="missing from the staged dir"):
        SR5.assert_leg_ladder(arms_r5, staged_dir, legs=(1, 2),
                              pinned_counts=(5, 3))


def test_assert_leg_ladder_skips_numeric_check_when_pinned_counts_none(tmp_path):
    """`pinned_counts=None` checks only the per-leg PREDICATE -- useful for a
    corpus that is not the one the real ladder was measured on."""
    arms_r5_path, leg, rows = make_thinning_arms_and_leg1(tmp_path)
    arms_r5 = json.loads(arms_r5_path.read_text())
    staged_dir = tmp_path / "staged"
    staged_dir.mkdir()
    leg1_dest = staged_dir / "positions_walled_leg1.jsonl"
    leg1_dest.write_text(leg.read_text())
    leg1_rows = SR5.load_leg_rows(leg1_dest)
    SR5.derive_legs(arms_r5, leg1_rows, staged_dir)

    witness = SR5.assert_leg_ladder(arms_r5, staged_dir, legs=(1, 2, 3, 4),
                                    pinned_counts=None)
    assert witness["leg_ladder_expected"] is None
    assert witness["leg_ladder_matches_expected"] is True   # skipped, not failed


def test_pinned_leg_ladder_constant_and_total():
    assert SR5.PINNED_LEG_LADDER == (1060, 1060, 1060, 1060, 866, 509, 366,
                                     265, 171, 110, 66, 9)
    assert SR5.PINNED_LEG_LADDER_TOTAL == 6602
    assert SR5.DEFAULT_LEGS == tuple(range(1, 13))


# =========================================================================== #
# the R4 source plan -- COPY never synthesize, refuse if it lacks dedupe       #
# =========================================================================== #
def test_load_r4_source_plan_carries_afterstate_dedupe_with_provenance(tmp_path):
    p = make_synthetic_source_plan(tmp_path)
    plan = SR5.load_r4_source_plan(p)
    dd = plan["afterstate_dedupe"]
    assert dd["applied"] is True
    assert "design_ref" in dd and "dropped_index_path" in dd


def test_load_r4_source_plan_absent_dedupe_refuses(tmp_path):
    """A source without afterstate_dedupe means the corpus genuinely was not
    deduped -- staging must not launder that by silent omission."""
    p = make_synthetic_source_plan(tmp_path, applied=False)
    with pytest.raises(SR5.StagingError, match="afterstate_dedupe"):
        SR5.load_r4_source_plan(p)


def test_load_r4_source_plan_dedupe_applied_false_refuses(tmp_path):
    p = tmp_path / "plan.json"
    p.write_text(json.dumps({"m_worlds": 32,
                            "afterstate_dedupe": {"applied": False}}))
    with pytest.raises(SR5.StagingError, match="afterstate_dedupe"):
        SR5.load_r4_source_plan(p)


def test_load_r4_source_plan_missing_file_raises(tmp_path):
    with pytest.raises(SR5.StagingError, match="not found"):
        SR5.load_r4_source_plan(tmp_path / "nope.json")


# =========================================================================== #
# full six-step assembly, synthetic                                            #
# =========================================================================== #
def test_full_stage_synthetic_end_to_end(tmp_path):
    arms_r5, leg, rows = make_synthetic_arms_and_leg(tmp_path, n=4)
    source_plan = make_synthetic_source_plan(tmp_path)
    # this fixture's positions all carry exactly 2 arms -- only leg1 exists
    # (63ed329b: leg r needs len(arms) > r), so restrict the ladder check to
    # leg1 rather than the real 12-entry pinned ladder.
    report = SR5.stage(
        arms_r5_path=arms_r5, leg_path=leg, r4_source_plan_path=source_plan,
        staged_dir=tmp_path / "run" / "corpus" / "positions_s2",
        stage_chunks_out_root=tmp_path / "run", n_chunks=2,
        legs=(1,), pinned_ladder=(4,))

    expected_keys = {
        "arms_r5_sha256", "staged_arms_sha256", "arms_copy_identical",
        "n_leg_rids", "n_arms_rids", "rid_sets_equal", "missing_in_leg",
        "missing_in_arms", "stage_chunks_rid_set_agrees", "n_chunks",
        "carried_plan_keys", "afterstate_dedupe_carried", "r4_source_plan_path",
        "leg_counts", "leg_ladder_expected", "leg_ladder_matches_expected",
        "n_total_pairs", "expected_total_arm_playouts", "total_arm_playouts_agrees",
    }
    assert expected_keys <= set(report)
    assert report["arms_copy_identical"] is True
    assert report["rid_sets_equal"] is True
    assert report["missing_in_leg"] == []
    assert report["missing_in_arms"] == []
    assert report["n_leg_rids"] == report["n_arms_rids"] == 4
    assert report["stage_chunks_rid_set_agrees"] is True
    assert report["n_chunks"] == 2
    assert report["gate"] == "G-STAGED"
    assert report["afterstate_dedupe_carried"]["applied"] is True
    assert "afterstate_dedupe" in report["carried_plan_keys"]
    # the leg ladder: 4 positions x 2 arms each -> leg1 only, 4 pairs
    assert report["leg_counts"] == {"1": 4}
    assert report["leg_ladder_matches_expected"] is True
    assert report["n_total_pairs"] == 4
    assert report["expected_total_arm_playouts"] == 4 * 2 * 32
    assert report["total_arm_playouts_agrees"] is True
    assert (tmp_path / "run" / "corpus" / "positions_s2" / "ARMS.json").is_file()
    assert (tmp_path / "run" / "corpus" / "positions_s2" /
           "positions_walled_leg1.jsonl").is_file()
    assert (tmp_path / "run" / "corpus" / "positions_s2" /
           "POSITIONS_PLAN.json").is_file()
    assert (tmp_path / "run" / "POSITION_ORDER.json").is_file()


def test_full_stage_source_plan_missing_dedupe_refuses_before_touching_disk(tmp_path):
    """The refuse-loudly path threaded all the way through stage(): a source
    plan without afterstate_dedupe must stop the WHOLE assembly, not just
    step 5 in isolation."""
    arms_r5, leg, rows = make_synthetic_arms_and_leg(tmp_path, n=4)
    bad_source_plan = make_synthetic_source_plan(tmp_path, applied=False)
    with pytest.raises(SR5.StagingError, match="afterstate_dedupe"):
        SR5.stage(arms_r5_path=arms_r5, leg_path=leg,
                 r4_source_plan_path=bad_source_plan,
                 staged_dir=tmp_path / "run" / "corpus" / "positions_s2",
                 stage_chunks_out_root=tmp_path / "run", n_chunks=2)


def test_stage_chunks_disagreement_raises(tmp_path, monkeypatch):
    """If stage_chunks' own re-derivation somehow disagreed, staging must
    RAISE -- never silently report success."""
    arms_r5, leg, rows = make_synthetic_arms_and_leg(tmp_path, n=4)
    source_plan = make_synthetic_source_plan(tmp_path)

    def fake_run_stage_chunks(staged_dir, *, out_root, n_chunks, script):
        return {"order_rids": {"totally_different_rid"}, "n_chunks": n_chunks,
               "order_path": str(out_root / "POSITION_ORDER.json"), "stdout": ""}

    monkeypatch.setattr(SR5, "run_stage_chunks", fake_run_stage_chunks)
    with pytest.raises(SR5.StagingError, match="does NOT agree"):
        SR5.stage(arms_r5_path=arms_r5, leg_path=leg,
                 r4_source_plan_path=source_plan,
                 staged_dir=tmp_path / "run" / "corpus" / "positions_s2",
                 stage_chunks_out_root=tmp_path / "run", n_chunks=2,
                 legs=(1,), pinned_ladder=(4,))


# =========================================================================== #
# CLI                                                                           #
# =========================================================================== #
def test_cli_stage_r5_corpus_synthetic(tmp_path):
    import subprocess
    arms_r5, leg, rows = make_synthetic_arms_and_leg(tmp_path, n=4)
    source_plan = make_synthetic_source_plan(tmp_path)
    staging_out = tmp_path / "STAGING_R5.json"
    r = subprocess.run(
        [sys.executable, str(TILETIE / "stage_r5_corpus.py"),
         "--arms-r5", str(arms_r5), "--leg", str(leg),
         "--r4-source-plan", str(source_plan),
         "--staged-dir", str(tmp_path / "run" / "corpus" / "positions_s2"),
         "--stage-chunks-out-root", str(tmp_path / "run"),
         "--n-chunks-s2", "2", "--legs", "1", "--skip-pinned-ladder",
         "--staging-out", str(staging_out)],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    body = json.loads(staging_out.read_text())
    assert body["arms_copy_identical"] is True
    assert body["stage_chunks_rid_set_agrees"] is True
    assert body["afterstate_dedupe_carried"]["applied"] is True
    assert body["leg_counts"] == {"1": 4}


def test_cli_stage_r5_corpus_source_plan_missing_dedupe_exits_2(tmp_path):
    import subprocess
    arms_r5, leg, rows = make_synthetic_arms_and_leg(tmp_path, n=4)
    bad_source_plan = make_synthetic_source_plan(tmp_path, applied=False)
    staging_out = tmp_path / "STAGING_R5.json"
    r = subprocess.run(
        [sys.executable, str(TILETIE / "stage_r5_corpus.py"),
         "--arms-r5", str(arms_r5), "--leg", str(leg),
         "--r4-source-plan", str(bad_source_plan),
         "--staged-dir", str(tmp_path / "run" / "corpus" / "positions_s2"),
         "--stage-chunks-out-root", str(tmp_path / "run"),
         "--staging-out", str(staging_out)],
        capture_output=True, text=True)
    assert r.returncode == 2
    assert "afterstate_dedupe" in r.stderr
    assert not staging_out.exists()


def test_cli_stage_r5_corpus_missing_arms_exits_2(tmp_path):
    import subprocess
    r = subprocess.run(
        [sys.executable, str(TILETIE / "stage_r5_corpus.py"),
         "--arms-r5", str(tmp_path / "nope.json"),
         "--leg", str(tmp_path / "also_nope.jsonl"),
         "--staged-dir", str(tmp_path / "run" / "corpus" / "positions_s2"),
         "--stage-chunks-out-root", str(tmp_path / "run"),
         "--staging-out", str(tmp_path / "STAGING_R5.json")],
        capture_output=True, text=True)
    assert r.returncode == 2
    assert "COULD NOT STAGE" in r.stderr
    assert not (tmp_path / "STAGING_R5.json").exists()


# =========================================================================== #
# real data -- read-only inputs, scratch RUN dir output                        #
# =========================================================================== #
@pytest.mark.skipif(not _REAL_INPUTS_PRESENT,
                    reason="the real (untracked, generated) R4 S2 leg / "
                          "GATE_DISJOINT.json / ARMS.json are not present "
                          "in this checkout")
def test_real_data_staging_end_to_end(tmp_path):
    """The launch evidence: the REAL 1,064-row leg + REAL ARMS.json ->
    build_r5_corpus.build() -> the REAL ARMS_R5.json (1,060) -> staged
    end-to-end (including a REAL stage_chunks.py stage subprocess) into a
    SCRATCH RUN dir. Never touches the live campaign root."""
    corpus, _, arms_r5 = BR5.build(leg_path=REAL_LEG,
                                   r4_gate_disjoint_path=REAL_R4_GATE_DISJOINT,
                                   r4_arms_path=REAL_R4_ARMS)
    assert len(arms_r5) == 1060
    assert corpus["arms_r5_sha256"] == LANDED_ARMS_R5_SHA256

    arms_r5_path = tmp_path / "ARMS_R5.json"
    arms_r5_path.write_text(json.dumps(arms_r5, indent=2, sort_keys=True))

    report = SR5.stage(
        arms_r5_path=arms_r5_path, leg_path=REAL_LEG,
        r4_source_plan_path=REAL_R4_SOURCE_PLAN,
        staged_dir=tmp_path / "run" / "corpus" / "positions_s2",
        stage_chunks_out_root=tmp_path / "run", n_chunks=8)

    assert report["arms_r5_sha256"] == LANDED_ARMS_R5_SHA256
    assert report["staged_arms_sha256"] == LANDED_ARMS_R5_SHA256
    assert report["arms_copy_identical"] is True
    assert report["n_leg_rids"] == report["n_arms_rids"] == 1060
    assert report["rid_sets_equal"] is True
    assert report["missing_in_leg"] == []
    assert report["missing_in_arms"] == []
    assert report["stage_chunks_rid_set_agrees"] is True
    assert report["n_chunks"] == 8

    # carried-with-provenance, on the REAL data
    dd = report["afterstate_dedupe_carried"]
    assert dd["applied"] is True
    assert dd["design_ref"]
    assert dd["dropped_index_path"]
    assert "afterstate_dedupe" in report["carried_plan_keys"]

    staged_dir = tmp_path / "run" / "corpus" / "positions_s2"
    assert (staged_dir / "ARMS.json").is_file()
    staged_arms = json.loads((staged_dir / "ARMS.json").read_text())
    assert len(staged_arms) == 1060
    staged_leg_rids = {json.loads(ln)["rid"] for ln in
                       (staged_dir / "positions_walled_leg1.jsonl")
                       .read_text().splitlines() if ln.strip()}
    assert len(staged_leg_rids) == 1060
    assert staged_leg_rids == set(staged_arms)

    # print_eta/check_positions compatibility -- the ACTUAL bug this round
    # fixes: a minimal plan crashes run_tiletie.py with a KeyError on the
    # rid-dependent keys (n_e4, n_selfplay, max_arms, mean_arms, …), even
    # though afterstate_dedupe alone would have been present. Every key
    # print_eta indexes DIRECTLY (no .get()) must be present.
    staged_plan = json.loads((staged_dir / "POSITIONS_PLAN.json").read_text())
    for k in ("n_positions", "n_e4", "n_selfplay", "max_arms", "mean_arms",
             "cap_j", "n_positions_capped", "total_arm_playouts",
             "oracle_worker_secs", "champ_pick_secs", "eta_by_workers"):
        assert k in staged_plan, f"print_eta needs {k!r}, staged plan lacks it"

    # THE LAUNCH EVIDENCE (63ed329b): the exact pinned ladder, reproduced on
    # the real adopted corpus, and the cost identity check.
    assert report["leg_ladder_expected"] == list(SR5.PINNED_LEG_LADDER)
    assert report["leg_ladder_matches_expected"] is True
    assert report["leg_counts"] == {
        "1": 1060, "2": 1060, "3": 1060, "4": 1060, "5": 866, "6": 509,
        "7": 366, "8": 265, "9": 171, "10": 110, "11": 66, "12": 9,
    }
    assert report["n_total_pairs"] == SR5.PINNED_LEG_LADDER_TOTAL == 6602
    assert report["expected_total_arm_playouts"] == 6602 * 2 * 32 == 422528
    assert staged_plan["total_arm_playouts"] == 422528
    assert report["total_arm_playouts_agrees"] is True

    # all 12 leg files present on disk, per-leg count matches the plan's
    # own files{} block
    for r in range(1, 13):
        p = staged_dir / f"positions_walled_leg{r}.jsonl"
        assert p.is_file(), f"leg{r} missing from the staged dir"
        n_lines = sum(1 for ln in p.read_text().splitlines() if ln.strip())
        assert n_lines == report["leg_counts"][str(r)]
        assert staged_plan["files"][f"walled/leg{r}"]["n"] == n_lines


@pytest.mark.skipif(not _REAL_INPUTS_PRESENT,
                    reason="the real (untracked, generated) R4 S2 leg / "
                          "GATE_DISJOINT.json / ARMS.json are not present "
                          "in this checkout")
def test_real_data_smoke_positions_find_leg2(tmp_path):
    """The ORIGINAL failure this round's ruling traces to: `run_tiletie.py`'s
    smoke refused on a missing leg2. Verified directly against the REAL
    consumer functions, on the real staged dir, not inferred from file
    presence alone."""
    sys.path.insert(0, str(TILETIE))
    import run_tiletie as RT                                       # noqa: E402

    corpus, _, arms_r5 = BR5.build(leg_path=REAL_LEG,
                                   r4_gate_disjoint_path=REAL_R4_GATE_DISJOINT,
                                   r4_arms_path=REAL_R4_ARMS)
    arms_r5_path = tmp_path / "ARMS_R5.json"
    arms_r5_path.write_text(json.dumps(arms_r5, indent=2, sort_keys=True))
    staged_dir = tmp_path / "run" / "corpus" / "positions_s2"
    SR5.stage(arms_r5_path=arms_r5_path, leg_path=REAL_LEG,
             r4_source_plan_path=REAL_R4_SOURCE_PLAN, staged_dir=staged_dir,
             stage_chunks_out_root=tmp_path / "run", n_chunks=8)

    sel = RT.select_smoke_positions(staged_dir, profile="walled",
                                    stratum="selfplay", min_arms=3, n=5)
    assert sel["rids"], "no smoke-eligible positions found on the staged dir"
    assert sel["synthesized"] is False

    built = RT.build_smoke_positions(staged_dir, sel["rids"], "walled", legs=(1, 2))
    assert 1 in built and 2 in built
    assert built[1]["n"] > 0
    assert built[2]["n"] > 0
    assert Path(built[2]["path"]).is_file()
    assert set(built[2]["rids"]) <= set(sel["rids"])


@pytest.mark.skipif(not _REAL_INPUTS_PRESENT,
                    reason="the real (untracked, generated) R4 S2 leg / "
                          "GATE_DISJOINT.json / ARMS.json are not present "
                          "in this checkout")
def test_real_data_carried_plan_keys_pinned():
    """The enumerated carry set, PINNED against the real R4 source plan --
    a regression here means either the source plan's own key set changed or
    stage_chunks.RID_DEPENDENT_KEYS changed, either of which deserves a
    human look, not a silent drift."""
    source_plan = json.loads(REAL_R4_SOURCE_PLAN.read_text())
    carried = sorted(set(source_plan) - SR5.SC.RID_DEPENDENT_KEYS)
    assert carried == [
        "afterstate_dedupe", "allow_missing_champ_picks", "cap_j",
        "cap_j_label", "census_qualifying_n", "census_rows_n",
        "deployed_cap_j", "design_doc", "exclude_rids", "formula",
        "generated_utc", "m_worlds", "n_positions_champ_pick_missing",
        "playout_secs", "sample_seed", "schema", "t_champ_secs", "uncapped",
        "union_provenance",
    ]


def test_landed_floors_sha_matches_this_build():
    """Confirms (never authors) the value drafter commit 97ca0276 landed in
    FLOORS_R5.json::population_authority.arms_r5_sha256 -- FLOORS_R5.json
    itself is the drafter's worktree file and is not written here."""
    assert LANDED_ARMS_R5_SHA256 == (
        "adb4c5bd7cf904a1fe00c839eab722fa79798b9f719b631b6f788900f3e5cf8a")
    assert len(LANDED_ARMS_R5_SHA256) == 64
