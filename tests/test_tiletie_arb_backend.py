"""Contracts for the RUST ARB-judge leg — campaign work item **W1**.

`scripts/tiletie/tier1_rust_leg.py` + the `--arb-backend` wiring in
`scripts/tiletie/run_tiletie.py` + `--cap-j inf` / uncapped arm recording in
`scripts/tiletie/build_positions.py`.

Design authority:
  * `measurement/tiearb_widening_20260817/PLAN_B_gt_16.md` §0.1-0.4, §3 (W1)
  * `measurement/tiearb_widening_20260817/PLAN_J_gt_4.md` §8 (shared-run reqs)
  * `measurement/tiearb_widening_20260817/CAMPAIGN.md` rulings 1-3
  * `measurement/tiearb2_stage2_20260817/PHASE_A.md` §3 (`G-BITEXACT`)

FAST UNIT TESTS ONLY. The one test that runs real playouts is the bit-exactness
gate, and it is deliberately tiny: 4 banked legs x 4 CRN worlds x 2 picks = 32
rust playouts (~3 s), spanning 1- to 125-ply continuations. No timing assertion
is made anywhere — `c` is re-measured on an idle box, per the house rule that a
timing bench is an exclusive tenant.

⛔ NO PYTHON PLAYOUTS RUN BY DEFAULT. The python leg costs c ~ 2.2-2.7
worker-s/playout, so re-running it here would blow the test budget by ~50x. The
parity reference is therefore the BANKED python-judge output (the Stage-1b
`tier1-greedy` records, already adjudicated and burned), which is exactly how
Phase A's `G-BITEXACT` graded the port. A LIVE python-vs-rust re-run is provided
as `test_live_python_leg_parity`, SKIPPED unless `TILETIE_PARITY_LIVE=1` — run it
in the post-freeze smoke, not in CI.
"""
from __future__ import annotations

import copy
import json
import os
import struct
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
import tier1_rust_leg as TRL  # noqa: E402

OSP = pytest.importorskip("oracle_score_pilot")

FIXTURE_PATH = REPO / "tests" / "data" / "tiletie" / "tier1_rust_leg_fixtures.json"


def _bits(x) -> int:
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def _item(f: dict) -> dict:
    """One fixture -> the `--positions-jsonl` row shape the leg runners consume."""
    return {k: f[k] for k in ("rid", "root_id", "deck_seed", "actions", "ply",
                              "pick_a", "pick_b", "root_player", "checksum",
                              "rules_profile", "stratum")}


@pytest.fixture(scope="module")
def fixtures() -> dict:
    if not FIXTURE_PATH.is_file():
        pytest.skip(f"no banked parity fixture at {FIXTURE_PATH}")
    return json.loads(FIXTURE_PATH.read_text())


def _args(**kw):
    import argparse

    base = dict(judges=["clair-puct"], m=32, arb_backend="python",
                arb_legal_mask_cache=True, workers=4)
    base.update(kw)
    return argparse.Namespace(**base)


# --------------------------------------------------------------------------- #
# 1. backend resolution — the default must not move                            #
# --------------------------------------------------------------------------- #
def test_default_backend_map_is_unchanged():
    """Behaviour preservation: without --arb-backend, every leg resolves exactly
    as it did before W1."""
    assert RT.backend_for("clair-puct", "walled") == "rust"
    assert RT.backend_for("clair-puct", "fixed_v1") == "python"
    assert RT.backend_for("tier1-greedy", "walled") == "python"
    assert RT.backend_for("tier1-greedy", "fixed_v1") == "python"


def test_arb_backend_rust_promotes_only_the_arb_judge_on_walled():
    assert RT.backend_for("tier1-greedy", "walled", "rust") == "rust"
    # the rust tier1 port replays under the DEFAULT GameConfig -> walled only
    assert RT.backend_for("tier1-greedy", "fixed_v1", "rust") == "python"
    assert RT.backend_for("tier1-greedy", "app_aug2", "rust") == "python"
    # the pricing judge is untouched by the ARB flag
    assert RT.backend_for("clair-puct", "walled", "rust") == "rust"
    assert RT.backend_for("clair-puct", "fixed_v1", "rust") == "python"


# --------------------------------------------------------------------------- #
# 2. leg_command routing                                                       #
# --------------------------------------------------------------------------- #
def _leg_kw(**kw):
    base = dict(positions_path="/tmp/p.jsonl", profile="walled", judge="tier1-greedy",
                m=32, oracle_sims=100, workers=7, n=11, out_root="/tmp/out",
                out_subdir="tier1-greedy/walled/leg1", resume=True)
    base.update(kw)
    return base


def test_leg_command_default_still_runs_the_pilot():
    cmd = RT.leg_command(**_leg_kw())
    assert str(RT.PILOT) in cmd
    assert str(RT.TIER1_RUST_LEG) not in cmd
    assert cmd[cmd.index("--backend") + 1] == "python"


def test_leg_command_rust_arb_runs_the_rust_leg_runner():
    cmd = RT.leg_command(**_leg_kw(arb_backend="rust"))
    assert str(RT.TIER1_RUST_LEG) in cmd
    assert str(RT.PILOT) not in cmd
    # the pilot's --backend/--oracle-policy flags do not exist on the rust runner
    assert "--backend" not in cmd
    assert "--oracle-policy" not in cmd
    assert cmd[cmd.index("--m") + 1] == "32"
    assert cmd[cmd.index("--n") + 1] == "11"
    assert cmd[cmd.index("--workers") + 1] == "7"
    assert cmd[cmd.index("--world-seed-salt") + 1] == RT.WORLD_SEED_SALT
    assert "--legal-mask-cache" in cmd and "--no-legal-mask-cache" not in cmd
    assert "--resume" in cmd


def test_leg_command_rust_arb_honours_the_honest_mask_flag():
    cmd = RT.leg_command(**_leg_kw(arb_backend="rust"), legal_mask_cache=False)
    assert "--no-legal-mask-cache" in cmd
    assert "--legal-mask-cache" not in cmd


def test_leg_command_rust_arb_falls_back_to_the_pilot_off_walled():
    """A profile the rust mirror cannot represent must run the PYTHON pilot, not
    the rust runner with a wrong-rules replay."""
    cmd = RT.leg_command(**_leg_kw(profile="fixed_v1", arb_backend="rust"))
    assert str(RT.PILOT) in cmd
    assert cmd[cmd.index("--backend") + 1] == "python"


def test_leg_command_clair_puct_is_byte_identical_under_the_new_flag():
    a = RT.leg_command(**_leg_kw(judge="clair-puct"))
    b = RT.leg_command(**_leg_kw(judge="clair-puct"), arb_backend="rust")
    assert a == b


# --------------------------------------------------------------------------- #
# 3. --m as a flag, bounded                                                    #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("m,ok", [(1, True), (32, True), (128, True),
                                  (0, False), (129, False), (-4, False)])
def test_check_m_bounds(m, ok):
    got = RT.check_m(_args(m=m))
    assert got["ok"] is ok
    if ok:
        # PLAN_B_gt_16 §0.2: the SELECTION parity half caps B, not M.
        assert got["b_ceiling"] == m // 2


def test_preflight_m_raises_loudly_out_of_range():
    assert TRL.preflight_m(128)["ok"] is True
    with pytest.raises(SystemExit):
        TRL.preflight_m(256)
    with pytest.raises(SystemExit):
        TRL.preflight_m(0)


def test_m_max_matches_the_campaign_design():
    assert RT.M_MAX == TRL.M_MAX == 128


def test_default_m_is_still_32():
    args = RT.build_arg_parser().parse_args([])
    assert args.m == 32
    assert args.arb_backend == "python"
    assert args.arb_legal_mask_cache is True
    assert args.smoke_judge == "clair-puct"


# --------------------------------------------------------------------------- #
# 4. preflights FAIL LOUD (the J13 lesson: no silent python fallback)          #
# --------------------------------------------------------------------------- #
def test_preflight_profile_refuses_non_walled():
    assert TRL.preflight_profile("walled")["ok"] is True
    with pytest.raises(SystemExit) as exc:
        TRL.preflight_profile("fixed_v1")
    assert "fixed_v1" in str(exc.value)


def test_preflight_wheel_refuses_a_missing_wheel(monkeypatch):
    """A missing/stale carc_rs must ABORT, never degrade to python: a 12.2x cost
    surprise under a manifest that claims 'rust' is exactly the J13 failure."""
    monkeypatch.setitem(sys.modules, "carc_rs", None)   # import returns None -> attr fail
    with pytest.raises(SystemExit) as exc:
        TRL.preflight_wheel()
    assert "carc_rs" in str(exc.value)


def test_preflight_wheel_refuses_a_stale_wheel(monkeypatch):
    """A wheel that imports but predates the Phase-A port is just as fatal."""
    carc_rs = pytest.importorskip("carc_rs")
    stale = type(sys)("carc_rs")           # a bare module object: no tier1_leg
    stale.__version__ = carc_rs.__version__
    monkeypatch.setitem(sys.modules, "carc_rs", stale)
    with pytest.raises(SystemExit) as exc:
        TRL.preflight_wheel()
    assert "tier1_leg" in str(exc.value)


def test_check_arb_backend_python_is_inert():
    got = RT.check_arb_backend(_args(arb_backend="python"))
    assert got["ok"] is True and got["arb_backend"] == "python"


def test_check_arb_backend_rust_without_the_arb_judge_is_inert():
    got = RT.check_arb_backend(_args(arb_backend="rust", judges=["clair-puct"]))
    assert got["ok"] is True and "inert" in got["note"]


def test_check_arb_backend_rejects_an_unknown_backend():
    got = RT.check_arb_backend(_args(arb_backend="cuda"))
    assert got["ok"] is False


def test_check_arb_backend_rust_passes_with_a_live_wheel():
    pytest.importorskip("carc_rs")
    got = RT.check_arb_backend(_args(arb_backend="rust",
                                     judges=["clair-puct", "tier1-greedy"]))
    assert got["ok"] is True, got
    assert got["wheel"]["ok"] is True
    assert got["seeds"]["ok"] is True


def test_check_arb_backend_surfaces_a_wheel_failure(monkeypatch):
    monkeypatch.setattr(TRL, "preflight_wheel",
                        lambda: (_ for _ in ()).throw(SystemExit("no wheel")))
    got = RT.check_arb_backend(_args(arb_backend="rust",
                                     judges=["tier1-greedy"]))
    assert got["ok"] is False and "no wheel" in got["problems"][0]


# --------------------------------------------------------------------------- #
# 5. the CRN seed derivation — imported, prefix-stable, and checked            #
# --------------------------------------------------------------------------- #
def test_preflight_seeds_asserts_prefix_stability():
    got = TRL.preflight_seeds("tiletie-v1", 128)
    assert got["ok"] is True
    assert got["prefix_stable_at"] == [1, 2, 4, 8, 16, 32, 64, 128]


def test_preflight_seeds_refuses_an_m_dependent_derivation(monkeypatch):
    """PLAN_B_gt_16 §0.1 is the load-bearing property: if `M` ever entered the
    world seed, every `B <= M/2` sub-read of one paid run would be void. The
    preflight must catch that, not assume it."""
    real = OSP.world_seeds

    def m_dependent(rid, m, salt):
        # self-consistent at the run's own M (so the FIRST guard passes), but
        # the shorter ladder rungs disagree -- exactly the failure that would
        # void every sub-read while looking healthy at face value.
        return real(rid, m, salt) if m == 32 else [s + m for s in real(rid, m, salt)]

    monkeypatch.setattr(OSP, "world_seeds", m_dependent)
    with pytest.raises(SystemExit) as exc:
        TRL.preflight_seeds("tiletie-v1", 32)
    assert "PREFIX-STABILITY" in str(exc.value)


def test_preflight_seeds_refuses_a_self_inconsistent_derivation(monkeypatch):
    real = OSP.world_seeds
    monkeypatch.setattr(OSP, "world_seeds",
                        lambda rid, m, salt: [s + 1 for s in real(rid, m, salt)])
    with pytest.raises(SystemExit) as exc:
        TRL.preflight_seeds("tiletie-v1", 8)
    assert "not self-consistent" in str(exc.value)


def test_banked_seeds_reproduce_from_the_derivation(fixtures):
    """The Phase-A seed witness, on the fixture: the banked records' seeds are
    exactly `world_seed(rid, j, salt)` / `playout_seed(rid, j, salt)`."""
    salt = fixtures["world_seed_salt"]
    for f in fixtures["fixtures"]:
        n = len(f["world_seeds"])
        assert f["world_seeds"] == [OSP.world_seed(f["rid"], j, salt)
                                    for j in range(n)], f["rid"]
        assert f["playout_seeds"] == [OSP.playout_seed(f["rid"], j, salt)
                                      for j in range(n)], f["rid"]


# --------------------------------------------------------------------------- #
# 6. ⭐ THE BIT-EXACTNESS GATE (Phase-A style, tiny)                            #
# --------------------------------------------------------------------------- #
def test_rust_leg_is_bit_identical_to_the_banked_python_judge(fixtures):
    """`G-BITEXACT` in miniature: the rust ARB leg must reproduce the PYTHON
    judge's per-world values BIT-for-BIT (raw f64 patterns, never `==` after a
    cast) and its playout ply counts exactly, on banked legs spanning early to
    endgame positions.

    The python side is the adjudicated Stage-1b corpus, not a re-run — the same
    construction `scripts/tiletie/verify_tier1_rust.py` graded the port with.
    """
    carc_rs = pytest.importorskip("carc_rs")
    n_val, n_ply, n_cmp = 0, 0, 0
    for f in fixtures["fixtures"]:
        va, vb, pa, pb, _cache = carc_rs.tier1_leg(
            f["deck_seed"], f["actions"], f["ply"], f["pick_a"], f["pick_b"],
            f["root_player"], f["world_seeds"], f["playout_seeds"],
            fixtures["max_plies"], fixtures["legal_mask_cache"])
        for got_v, want_v, got_p, want_p in ((va, f["values_a"], pa, f["playout_plies_a"]),
                                             (vb, f["values_b"], pb, f["playout_plies_b"])):
            assert len(got_v) == len(want_v)
            for j in range(len(want_v)):
                n_cmp += 1
                n_val += int(_bits(got_v[j]) == _bits(want_v[j]))
                n_ply += int(int(got_p[j]) == int(want_p[j]))
    # committed counts, not len(whatever_was_found) — a truncated fixture must
    # FAIL the gate, not satisfy it trivially (PHASE_A.md §3).
    expected = len(fixtures["fixtures"]) * fixtures["n_worlds"] * 2
    assert n_cmp == expected
    assert n_val == expected, f"{expected - n_val}/{expected} values not bit-identical"
    assert n_ply == expected, f"{expected - n_ply}/{expected} ply counts differ"


def test_score_one_record_matches_the_banked_python_values(fixtures):
    """The same gate through the actual production entry point, so the record
    the run writes — not just the FFI call — is the thing proven equal."""
    pytest.importorskip("carc_rs")
    f = fixtures["fixtures"][0]
    m = fixtures["n_worlds"]
    item = _item(f)
    rec = TRL.score_one(item, m=m, salt=fixtures["world_seed_salt"],
                        max_plies=fixtures["max_plies"],
                        legal_mask_cache=fixtures["legal_mask_cache"],
                        world_deck_witness=True)
    assert rec["ok"] is True, rec.get("error")
    assert rec["checksum_ok"] is True
    assert [_bits(v) for v in rec["values_a"]] == [_bits(v) for v in f["values_a"]]
    assert [_bits(v) for v in rec["values_b"]] == [_bits(v) for v in f["values_b"]]
    assert rec["playout_plies_a"] == f["playout_plies_a"]
    assert rec["world_seeds"] == f["world_seeds"]
    assert rec["playout_seeds"] == f["playout_seeds"]
    assert rec["m"] == m and rec["arb_backend"] == "rust"
    assert rec["oracle_policy"] == "tier1-greedy"
    # the CRN witness is the rust one, and the python field is ABSENT, not faked
    assert rec["crn_verified"] is True
    assert rec["crn_witness"] == TRL.CRN_WITNESS_RUST
    assert len(rec["world_deck_hash"]) == m
    assert "afterstate_deck_hash_a" not in rec
    assert "afterstate_deck_hash_b" not in rec
    # position_delta is the pilot's own, imported not reimplemented
    assert rec["mean_a"] == pytest.approx(sum(f["values_a"]) / m)
    assert "per_world_delta" in rec and "within_var" in rec
    # the no-op witness is 0-or-m and its keys are NAMED APART from the python
    # leg's per-world ones (they are computed on the root deck, not on a world)
    assert rec["distinct_afterstates"] in (0, m)
    assert "afterstate_board_key_a_root" in rec
    assert "afterstate_board_key_a" not in rec


def test_score_one_reports_a_bad_checksum_rather_than_scoring_it(fixtures):
    pytest.importorskip("carc_rs")
    f = fixtures["fixtures"][-1]
    item = _item(f)
    item["checksum"] = "not-the-board"
    rec = TRL.score_one(item, m=1, salt=fixtures["world_seed_salt"], max_plies=400,
                        legal_mask_cache=True, world_deck_witness=False)
    assert rec["ok"] is False and rec["error"] == "checksum_mismatch"
    assert "values_a" not in rec


def test_score_one_reports_an_illegal_pick(fixtures):
    pytest.importorskip("carc_rs")
    f = fixtures["fixtures"][-1]
    item = _item(f)
    item["pick_b"] = 999999
    rec = TRL.score_one(item, m=1, salt=fixtures["world_seed_salt"], max_plies=400,
                        legal_mask_cache=True, world_deck_witness=False)
    assert rec["ok"] is False and rec["error"] == "pick_b_illegal_at_root"


def test_score_one_records_the_mask_mode(fixtures):
    """The honest-mask variant is allowed but must be SELF-DESCRIBING: a record
    that ran it is not python-comparable and has to say so."""
    pytest.importorskip("carc_rs")
    f = fixtures["fixtures"][-1]
    item = _item(f)
    rec = TRL.score_one(item, m=1, salt=fixtures["world_seed_salt"], max_plies=400,
                        legal_mask_cache=False, world_deck_witness=False)
    assert rec["ok"] is True
    assert rec["legal_mask_cache"] is False


def test_prefix_stability_holds_on_a_banked_leg(fixtures):
    """PLAN_B_gt_16 §0.1 end-to-end: scoring 2 worlds gives BIT-IDENTICAL values
    to the first 2 worlds of a 4-world run. This is what makes every `B <= M/2`
    a free sub-read of one paid run."""
    pytest.importorskip("carc_rs")
    f = fixtures["fixtures"][-1]
    item = _item(f)
    kw = dict(salt=fixtures["world_seed_salt"], max_plies=400,
              legal_mask_cache=True, world_deck_witness=True)
    wide = TRL.score_one(dict(item), m=4, **kw)
    narrow = TRL.score_one(dict(item), m=2, **kw)
    assert [_bits(v) for v in narrow["values_a"]] == \
           [_bits(v) for v in wide["values_a"][:2]]
    assert narrow["world_seeds"] == wide["world_seeds"][:2]
    assert narrow["world_deck_hash"] == wide["world_deck_hash"][:2]


# --------------------------------------------------------------------------- #
# 7. the CRN cross-leg witness understands both backends' witnesses            #
# --------------------------------------------------------------------------- #
def _rust_rec(rid, values, seeds=(1, 2)):
    return {"rid": rid, "values_a": list(values), "crn_verified": True,
            "world_seeds": list(seeds), "playout_seeds": list(seeds),
            "world_deck_hash": ["aa", "bb"]}


def _py_rec(rid, values, seeds=(1, 2)):
    return {"rid": rid, "values_a": list(values), "crn_verified": True,
            "world_seeds": list(seeds), "playout_seeds": list(seeds),
            "afterstate_deck_hash_a": ["aa", "bb"],
            "afterstate_deck_hash_b": ["aa", "bb"]}


def test_world_witness_key_discriminates_the_backends():
    assert RT.world_witness_key(_py_rec("r", [1.0])) == "afterstate_deck_hash_a"
    assert RT.world_witness_key(_rust_rec("r", [1.0])) == "world_deck_hash"
    assert RT.world_witness_key({"rid": "r"}) == ""


def test_crn_cross_leg_passes_on_matched_rust_legs():
    got = RT.check_crn_cross_leg({1: {"r": _rust_rec("r", [1.0, 2.0])},
                                  2: {"r": _rust_rec("r", [1.0, 2.0])}})
    assert got["ok"] is True
    assert got["world_witness_kinds"] == ["world_deck_hash"]


def test_crn_cross_leg_still_passes_on_matched_python_legs():
    got = RT.check_crn_cross_leg({1: {"r": _py_rec("r", [1.0, 2.0])},
                                  2: {"r": _py_rec("r", [1.0, 2.0])}})
    assert got["ok"] is True
    assert got["world_witness_kinds"] == ["afterstate_deck_hash_a"]


def test_crn_cross_leg_fails_loudly_on_mixed_backends():
    """The two witnesses are DIFFERENT quantities. A set of legs that mixes them
    must be reported as a harness error, never pass vacuously."""
    got = RT.check_crn_cross_leg({1: {"r": _py_rec("r", [1.0, 2.0])},
                                  2: {"r": _rust_rec("r", [1.0, 2.0])}})
    assert got["ok"] is False
    assert any("DIFFERENT backends" in p for p in got["per_rid"]["r"]["problems"])
    assert set(got["world_witness_kinds"]) == {"afterstate_deck_hash_a",
                                               "world_deck_hash"}


def test_crn_cross_leg_still_catches_a_real_value_mismatch():
    got = RT.check_crn_cross_leg({1: {"r": _rust_rec("r", [1.0, 2.0])},
                                  2: {"r": _rust_rec("r", [1.0, 3.0])}})
    assert got["ok"] is False
    assert any("values_a raw-f64-bit MISMATCH" in p
               for p in got["per_rid"]["r"]["problems"])


def test_crn_cross_leg_catches_a_witness_value_mismatch():
    bad = _rust_rec("r", [1.0, 2.0])
    bad["world_deck_hash"] = ["aa", "zz"]
    got = RT.check_crn_cross_leg({1: {"r": _rust_rec("r", [1.0, 2.0])},
                                  2: {"r": bad}})
    assert got["ok"] is False
    assert any("world_deck_hash differs" in p
               for p in got["per_rid"]["r"]["problems"])


# --------------------------------------------------------------------------- #
# 8. manifest — fully resolved config                                          #
# --------------------------------------------------------------------------- #
def test_rust_leg_manifest_carries_the_resolved_config():
    import argparse

    args = argparse.Namespace(
        positions_jsonl="/tmp/p.jsonl", rules_profile="walled", m=128,
        world_seed_salt="tiletie-v1", oracle_sims=100, max_plies=400,
        legal_mask_cache=True, world_deck_witness=True, strict_crn=False,
        workers=30, n=17, resume=True, out_root="/tmp/o", out_subdir="s")
    man = TRL.build_manifest(args, {"wheel": {"ok": True}}, 17,
                             [{"ok": True, "elapsed_secs": 1.0, "crn_verified": True},
                              {"ok": False, "error": "boom", "elapsed_secs": 0.5}],
                             wall=2.0)
    rc = man["resolved_config"]
    assert rc["m"] == 128 and rc["arb_backend"] == "rust"
    assert rc["legal_mask_cache"] is True
    assert rc["world_seed_salt"] == "tiletie-v1"
    assert man["n_ok"] == 1 and man["n_failed"] == 1 and man["errors"] == ["boom"]
    assert man["n_playouts"] == 1 * 2 * 128
    # a production leg NEVER quotes a cost figure
    assert "c_worker_secs_per_playout" not in man


def test_run_manifest_records_the_resolved_backend_per_leg(tmp_path, monkeypatch):
    import argparse

    args = argparse.Namespace(
        positions_dir=str(tmp_path), judges=["tier1-greedy"], m=128,
        arb_backend="rust", arb_legal_mask_cache=True, oracle_sims=100,
        workers=30, resume=True)
    legs = [{"judge": "tier1-greedy", "profile": "walled", "leg": 1,
             "backend": "rust"},
            {"judge": "tier1-greedy", "profile": "fixed_v1", "leg": 1,
             "backend": "python"}]
    monkeypatch.setattr(RT, "_r9_for", lambda p: "0")
    man = RT.write_manifest(args, None, legs, tmp_path / "RUN_MANIFEST.json")
    assert man["arb_backend"] == "rust"
    assert man["m_worlds"] == 128 and man["b_ceiling_from_m"] == 64
    assert man["resolved_backend_by_leg"] == {
        "tier1-greedy/walled/leg1": "rust",
        "tier1-greedy/fixed_v1/leg1": "python"}
    # the DECLARED default map is still reported, unchanged
    assert man["judge_backend"] == {"tier1-greedy": "python"}


# --------------------------------------------------------------------------- #
# 9. --cap-j inf + the recorded J=4 subset (PLAN_J_gt_4 §8)                     #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("raw,want", [("4", 4), (4, 4), ("12", 12),
                                      ("inf", None), ("INF", None), ("∞", None),
                                      ("none", None), ("all", None), ("0", None),
                                      (0, None), (None, None), (-1, None)])
def test_parse_cap_j(raw, want):
    assert BP.parse_cap_j(raw) == want


def test_parse_cap_j_refuses_garbage():
    with pytest.raises(ValueError):
        BP.parse_cap_j("lots")


def _tie_row(actions, rid_seed=28100000001, ply=30):
    return {"stratum": "selfplay", "deck_seed": rid_seed, "ply": ply,
            "tie_actions_exact": list(actions),
            "argmax_action": min(actions)}


def test_uncapped_build_keeps_every_arm_and_records_the_j4_subset():
    row = _tie_row([10, 20, 30, 40, 50, 60, 70])
    tie = BP.build_tie_arms(row, None)
    assert tie["arms"] == [10, 20, 30, 40, 50, 60, 70]
    assert tie["capped"] is False and tie["dropped_actions"] == []
    assert tie["arms_full"] == tie["arms"]
    # PLAN_J_gt_4 §8 (2): the deployed cap's materialised subset, recorded even
    # though this build did not apply it.
    assert tie["capped_at_4"] is True
    assert len(tie["subset_j4"]) == BP.DEPLOYED_CAP_J
    assert tie["subset_j4"][0] == 10                      # arms[0] never moves
    assert set(tie["subset_j4"]).issubset(set(tie["arms_full"]))


def test_the_j4_subset_is_an_exact_sub_read_of_the_uncapped_build():
    """⭐ The whole point of the shared run (PLAN_J_gt_4 §3.4): restricting to the
    recorded J=4 subset must reproduce a `--cap-j 4` build EXACTLY, so the capped
    comparator costs nothing extra and shares the CRN worlds."""
    for actions in ([10, 20, 30, 40, 50, 60, 70],
                    [3, 5, 8, 13, 21],
                    [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200]):
        row = _tie_row(actions)
        assert BP.build_tie_arms(row, None)["subset_j4"] == \
               BP.build_tie_arms(row, 4)["arms"]


def test_the_j4_subset_is_recorded_even_when_the_cap_did_not_bite():
    row = _tie_row([10, 20, 30])
    tie = BP.build_tie_arms(row, None)
    assert tie["subset_j4"] == [10, 20, 30]
    assert tie["capped_at_4"] is False


def test_capping_is_a_seeded_draw_not_truncation():
    row = _tie_row([10, 20, 30, 40, 50, 60, 70])
    sub = BP.build_tie_arms(row, 4)["arms"]
    assert sub != [10, 20, 30, 40], "index truncation would correlate with the tie-break"
    assert sub[0] == 10 and len(sub) == 4


def test_subset_id_is_stable_and_moves_with_the_arms():
    a = BP._subset_id("tt_sp_1_p2", [10, 20, 30, 40])
    assert a == BP._subset_id("tt_sp_1_p2", [10, 20, 30, 40])
    assert a != BP._subset_id("tt_sp_1_p2", [10, 20, 30, 41])
    assert a != BP._subset_id("tt_sp_1_p3", [10, 20, 30, 40])
    assert len(a) == 16


def test_cost_plan_reports_an_uncapped_build_as_such():
    positions = [{"arms": [1, 2, 3], "capped": False, "stratum": "selfplay",
                  "rules_profile": "walled", "subset_j4": [1, 2, 3],
                  "capped_at_4": False}]
    plan = BP.cost_plan(positions, cap_j=None, sample_seed=1, playout_secs=0.18)
    assert plan["cap_j"] is None
    assert plan["cap_j_label"] == "inf"
    assert plan["uncapped"] is True
    assert plan["deployed_cap_j"] == 4
    assert plan["n_positions_capped_at_4"] == 0

    plan4 = BP.cost_plan(positions, cap_j=4, sample_seed=1, playout_secs=0.18)
    assert plan4["cap_j"] == 4 and plan4["cap_j_label"] == "4"
    assert plan4["uncapped"] is False


def test_strict_crn_without_a_witness_is_refused():
    """A CRN check with nothing recorded to check would pass vacuously."""
    argv = ["--positions-jsonl", "/tmp/nope.jsonl", "--out-root", "/tmp/o",
            "--strict-crn", "--no-world-deck-witness"]
    with pytest.raises(SystemExit) as exc:
        TRL.main(argv)
    assert "contradiction" in str(exc.value)


def test_cap_j_label():
    assert BP.cap_j_label(None) == "inf"
    assert BP.cap_j_label(4) == "4"


# --------------------------------------------------------------------------- #
# 10. the LIVE python-vs-rust parity re-run — POST-FREEZE SMOKE ONLY            #
# --------------------------------------------------------------------------- #
@pytest.mark.slow
@pytest.mark.skipif(os.environ.get("TILETIE_PARITY_LIVE") != "1",
                    reason="runs the PYTHON tier1 continuation (c ~ 2.2-2.7 "
                           "worker-s/playout): far outside the unit-test budget. "
                           "Run it in the post-freeze smoke with "
                           "TILETIE_PARITY_LIVE=1 on an idle box.")
def test_live_python_leg_parity(fixtures):
    """Re-run the PYTHON judge on one banked leg and compare to the rust leg.

    This is the honest end-to-end parity gate: it proves the two BACKENDS agree
    today, not merely that rust reproduces a file. It is skipped by default
    because one leg is ~8 python playouts at seconds each.
    """
    pytest.importorskip("carc_rs")
    OSP._init({"level_a": 0, "level_b": 0,
               "alloc_a": {"total": 0, "label": "n/a"},
               "alloc_b": {"total": 0, "label": "n/a"},
               "m": fixtures["n_worlds"], "oracle_sims": 100,
               "oracle_policy": "tier1-greedy",
               "world_seed_salt": fixtures["world_seed_salt"],
               "max_plies": fixtures["max_plies"], "wall_cap": 3600,
               "strict_crn": False, "backend": "python"})
    f = copy.deepcopy(fixtures["fixtures"][-1])          # the cheapest (latest ply)
    item = dict(f, deck_seed=int(f["deck_seed"]))
    py = OSP._process(item)
    assert py.get("ok") is True, py.get("error")
    rs = TRL.score_one(item, m=fixtures["n_worlds"],
                       salt=fixtures["world_seed_salt"],
                       max_plies=fixtures["max_plies"],
                       legal_mask_cache=True, world_deck_witness=True)
    assert rs["ok"] is True, rs.get("error")
    assert [_bits(v) for v in rs["values_a"]] == [_bits(v) for v in py["values_a"]]
    assert [_bits(v) for v in rs["values_b"]] == [_bits(v) for v in py["values_b"]]
    assert rs["playout_plies_a"] == py["playout_plies_a"]
    assert rs["playout_plies_b"] == py["playout_plies_b"]
