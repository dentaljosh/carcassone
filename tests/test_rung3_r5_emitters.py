#!/usr/bin/env python3
"""Tests for the rung3_r5 emitter spec
(`measurement/tiearb_widening_20260817/rung3_r5/DESIGN.md` §R5-FINAL.i,
`READ_RULE.md` §2, spec commit `bed67165`):

  * `scripts/tiletie/build_r5_corpus.py` (NEW) — `CORPUS_R5.json` +
    `GATE_INTERNAL_DUPE.json`
  * `scripts/tiletie/gate_disjoint.py --r5` (EXTENDED) — `GATE_DISJOINT_R5.json`
  * `scripts/tiletie/r5_fixtures.py` (NEW) — the 9-fixture A1 set + the
    marker-list completeness pass

Covers: every addressed key present with the right type, on BOTH a synthetic
corpus and (read-only) the REAL R4 post-exclusion S2 leg; the internal-dupe
exclusion reproduces 1,064 -> 1,060 on that real leg; `GATE_DISJOINT_R5`'s
rid/root layers fire on a synthetic leak; A1 fixture completeness fails
loudly when a fixture is removed.

Fast, hermetic (except the one real-leg test, which is read-only and skips
if the file is absent from this checkout).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TILETIE = REPO / "scripts" / "tiletie"
if str(TILETIE) not in sys.path:
    sys.path.insert(0, str(TILETIE))

import build_r5_corpus as BR5                                       # noqa: E402
import gate_disjoint as GD                                          # noqa: E402
import r5_fixtures as RF                                            # noqa: E402
import widening_fixtures as WF                                      # noqa: E402

BUILD_SCRIPT = TILETIE / "build_r5_corpus.py"
FIXTURES_SCRIPT = TILETIE / "r5_fixtures.py"

#: The REAL, on-disk R4 post-exclusion S2 leg — read-only. It is untracked,
#: generated data: this worktree's checkout may not have it even though the
#: MAIN checkout that generated it does (worktrees share git history, not
#: untracked working-tree files). Tried at this worktree's own path FIRST,
#: falling back to the main checkout's — the real-leg test SKIPS only if
#: NEITHER location has it.
_REL = "measurement/tiearb_widening_20260817/shared_run_r4/corpus/positions_s2/positions_walled_leg1.jsonl"
_REL_GD = "measurement/tiearb_widening_20260817/shared_run_r4/GATE_DISJOINT.json"
_REL_ARMS = "measurement/tiearb_widening_20260817/shared_run_r4/corpus/positions_s2/ARMS.json"
_MAIN_CHECKOUT = Path("/home/doctor/projects/carcassone")


def _first_existing(*candidates):
    for c in candidates:
        if c.is_file():
            return c
    return candidates[0]


REAL_LEG = _first_existing(REPO / _REL, _MAIN_CHECKOUT / _REL)
REAL_R4_GATE_DISJOINT = _first_existing(REPO / _REL_GD, _MAIN_CHECKOUT / _REL_GD)
#: R4's REAL, pre-exclusion S2 ARMS.json -- "R4_ARMS", DESIGN ruling
#: `a13ed934`'s population authority is computed FROM this.
REAL_R4_ARMS = _first_existing(REPO / _REL_ARMS, _MAIN_CHECKOUT / _REL_ARMS)


# --------------------------------------------------------------------------- #
# synthetic leg + R4-gate-disjoint fixture builders                            #
# --------------------------------------------------------------------------- #
def write_leg(path, records):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return path


def _row(seed, ply, checksum, tag=""):
    return {"rid": f"tt_sp_{seed}_p{ply}{tag}", "root_id": f"sp_{seed}",
            "deck_seed": seed, "ply": ply, "checksum": checksum}


def make_synthetic_leg(tmp_path, *, planted_dupe=True, planted_oob=True):
    """A tiny leg: some banked (135e9) rows, some extension (137e9) rows, one
    planted same-band dupe pair (both extension, ply 7), and one seed OUTSIDE
    both declared ranges (so `n_out_of_band`/`n_seeds_136e9` exercise a
    nonzero shape, not just the healthy-corpus zero)."""
    rows = [
        _row(135000000350, 10, "A"),
        _row(135000000351, 11, "B"),
        _row(137000000508, 20, "C"),
        _row(137000000509, 21, "D"),
    ]
    if planted_dupe:
        rows += [_row(137000000510, 7, "DUPE"), _row(137000000511, 7, "DUPE")]
    if planted_oob:
        rows += [_row(136000000005, 3, "OOB136"),   # released-unused band
                 _row(999999999999, 4, "OOBOTHER")]  # not in ANY declared range
    return write_leg(tmp_path / "positions_walled_leg1.jsonl", rows)


def make_r4_gate_disjoint(tmp_path, *, s2_rids=()):
    p = tmp_path / "GATE_DISJOINT.json"
    p.write_text(json.dumps({"digest_exclusions": {"S2": {"rids": list(s2_rids)}}}))
    return p


def make_matching_r4_arms(tmp_path, leg_path, *, name="R4_ARMS.json"):
    """A `build_arms_index`-shaped `R4_ARMS.json` covering EXACTLY the rid
    set of `leg_path` (a13ed934's D4 invariant: the leg and ARMS must
    enumerate the same population) -- built from the SAME leg rows, so the
    two can never drift apart in a test fixture the way they must never
    drift apart in the real corpus."""
    records = [json.loads(ln) for ln in Path(leg_path).read_text().splitlines()
              if ln.strip()]
    arms = {r["rid"]: {"arms": [1, 2], "root_id": r["root_id"],
                       "stratum": "selfplay", "rules_profile": "walled",
                       "game_label": f"g{r['deck_seed']}",
                       "deck_seed": r["deck_seed"], "ply": r["ply"],
                       "seat": 0, "k_remaining": 10, "phase_bucket": "mid",
                       "tercile": 1, "n_legal": 2, "n_cand": 2,
                       "tie_size_exact": 2, "gap": 0.0, "capped": False,
                       "dropped_actions": [], "champ_action": 1,
                       "champ_arm_index": 0, "champ_outside_tieset": False}
           for r in records}
    p = Path(tmp_path) / name
    p.write_text(json.dumps(arms))
    return p


# =========================================================================== #
# build_r5_corpus.py                                                          #
# =========================================================================== #
def test_synthetic_corpus_key_types(tmp_path):
    leg = make_synthetic_leg(tmp_path)
    gd = make_r4_gate_disjoint(tmp_path, s2_rids=["tt_sp_135000000350_p10"])
    r4_arms = make_matching_r4_arms(tmp_path, leg)
    corpus, dupe, arms_r5 = BR5.build(
        leg_path=leg, r4_gate_disjoint_path=gd, r4_arms_path=r4_arms,
        expect_leg_sha256="", expect_exclusion_sha256="")

    str_keys = ("leg_path", "leg_sha256", "r4_exclusion_list_sha256",
               "r4_arms_path", "arms_r5_path", "arms_r5_sha256")
    int_keys = ("n_in", "n_excluded_r5", "n_positions", "n_distinct_seeds",
               "max_positions_per_seed", "n_out_of_band", "n_seeds_136e9",
               "arms_r5_n_rids")
    for k in str_keys:
        assert isinstance(corpus[k], str) and corpus[k], k
    for k in int_keys:
        assert isinstance(corpus[k], int) and not isinstance(corpus[k], bool), k
    assert isinstance(corpus["excluded_rids"], list)
    assert all(isinstance(r, str) for r in corpus["excluded_rids"])
    assert isinstance(corpus["seed_ranges"], dict)
    assert len(corpus["leg_sha256"]) == 64
    assert len(corpus["r4_exclusion_list_sha256"]) == 64
    assert len(corpus["arms_r5_sha256"]) == 64

    assert isinstance(dupe["n_positions"], int)
    assert isinstance(dupe["n_dupe_groups"], int)
    assert isinstance(dupe["n_dupe_positions"], int)
    assert isinstance(dupe["d_internal"], float)
    assert isinstance(dupe["ply_histogram"], dict)
    assert isinstance(dupe["band_pairs"], list)
    assert all(isinstance(b, str) for b in dupe["band_pairs"])
    assert isinstance(dupe["leg_sha256"], str) and len(dupe["leg_sha256"]) == 64

    assert isinstance(arms_r5, dict)
    assert len(arms_r5) == corpus["arms_r5_n_rids"] == corpus["n_positions"]
    for rid, v in arms_r5.items():
        assert isinstance(rid, str)
        assert isinstance(v, dict) and "root_id" in v


def test_synthetic_corpus_planted_dupe_and_residual_excluded(tmp_path):
    leg = make_synthetic_leg(tmp_path, planted_dupe=True, planted_oob=False)
    gd = make_r4_gate_disjoint(tmp_path, s2_rids=["tt_sp_135000000350_p10"])
    r4_arms = make_matching_r4_arms(tmp_path, leg)
    corpus, dupe, arms_r5 = BR5.build(
        leg_path=leg, r4_gate_disjoint_path=gd, r4_arms_path=r4_arms,
        expect_leg_sha256="", expect_exclusion_sha256="")
    assert corpus["n_in"] == 6
    assert dupe["n_dupe_groups"] == 1
    assert dupe["n_dupe_positions"] == 2
    # the residual (from the R4 exclusion list, still present) + the later
    # dupe member = 2 excluded
    assert corpus["n_excluded_r5"] == 2
    assert corpus["n_positions"] == 4
    assert "tt_sp_135000000350_p10" in corpus["excluded_rids"]
    assert "tt_sp_137000000511_p7" in corpus["excluded_rids"]   # later-ordered
    assert "tt_sp_137000000510_p7" not in corpus["excluded_rids"]  # kept (earlier)
    assert dupe["ply_histogram"] == {7: 2}
    assert dupe["band_pairs"] == ["137e9<->137e9"]

    # ARMS_R5 == R4_ARMS.rids - excluded_rids, in BOTH directions
    r4_arms_rids = set(json.loads(Path(r4_arms).read_text()))
    assert set(arms_r5) == r4_arms_rids - set(corpus["excluded_rids"])
    for excl in corpus["excluded_rids"]:
        assert excl not in arms_r5
    # ARMS_R5 entries are a VERBATIM copy of R4_ARMS -- never re-derived/
    # re-shaped
    r4_arms_full = json.loads(Path(r4_arms).read_text())
    for rid, v in arms_r5.items():
        assert v == r4_arms_full[rid]


def test_synthetic_corpus_out_of_band_counts(tmp_path):
    leg = make_synthetic_leg(tmp_path, planted_dupe=False, planted_oob=True)
    gd = make_r4_gate_disjoint(tmp_path)
    r4_arms = make_matching_r4_arms(tmp_path, leg)
    corpus, _, _ = BR5.build(leg_path=leg, r4_gate_disjoint_path=gd,
                             r4_arms_path=r4_arms,
                             expect_leg_sha256="", expect_exclusion_sha256="")
    assert corpus["n_out_of_band"] == 2      # 136e9 seed + the "999999999999" seed
    assert corpus["n_seeds_136e9"] == 1


def test_leg_sha256_mismatch_raises(tmp_path):
    leg = make_synthetic_leg(tmp_path)
    gd = make_r4_gate_disjoint(tmp_path)
    with pytest.raises(BR5.BuildError, match="leg sha256 mismatch"):
        BR5.build(leg_path=leg, r4_gate_disjoint_path=gd,
                  expect_leg_sha256="0" * 64, expect_exclusion_sha256="")


def test_exclusion_list_sha256_mismatch_raises(tmp_path):
    leg = make_synthetic_leg(tmp_path)
    gd = make_r4_gate_disjoint(tmp_path, s2_rids=["some_rid"])
    with pytest.raises(BR5.BuildError, match="r4_exclusion_list_sha256 mismatch"):
        BR5.build(leg_path=leg, r4_gate_disjoint_path=gd,
                  expect_leg_sha256="", expect_exclusion_sha256="0" * 64)


def test_r4_exclusion_list_sha256_canonical_formula():
    """DESIGN R5-FINAL.j, exact: sha256(json.dumps(sorted(rids))), default
    separators, no sort_keys, UTF-8, no trailing newline."""
    import hashlib
    rids = ["b_rid", "a_rid", "c_rid"]
    expected = hashlib.sha256(
        json.dumps(sorted(rids)).encode("utf-8")).hexdigest()
    assert BR5.r4_exclusion_list_sha256(rids) == expected
    # order-independence: the function itself sorts
    assert (BR5.r4_exclusion_list_sha256(["c_rid", "a_rid", "b_rid"])
            == expected)


# =========================================================================== #
# a13ed934 -- ARMS_R5.json, the materialized population authority              #
# =========================================================================== #
def test_assert_rid_sets_equal_passes_when_equal():
    BR5.assert_rid_sets_equal({"a", "b"}, {"b", "a"}, what="x")  # no raise


def test_assert_rid_sets_equal_fires_on_missing_direction():
    """`expected` has a rid `actual` lacks -- the "materialized set is
    INCOMPLETE" direction."""
    with pytest.raises(BR5.BuildError, match=r"1 missing.*0 extra"):
        BR5.assert_rid_sets_equal({"a"}, {"a", "b"}, what="x")


def test_assert_rid_sets_equal_fires_on_extra_direction():
    """`actual` has a rid `expected` lacks -- the "materialized set carries
    something it should NOT" direction."""
    with pytest.raises(BR5.BuildError, match=r"0 missing.*1 extra"):
        BR5.assert_rid_sets_equal({"a", "b"}, {"a"}, what="x")


def test_assert_rid_sets_equal_fires_on_both_directions_at_once():
    with pytest.raises(BR5.BuildError, match=r"1 missing.*1 extra"):
        BR5.assert_rid_sets_equal({"a", "c"}, {"a", "b"}, what="x")


def test_leg_and_r4_arms_rid_mismatch_raises_both_directions(tmp_path):
    """The D4 invariant (a13ed934: "the leg files enumerate exactly the ARMS
    rids") checked at build time -- a rid only in the leg, or only in
    ARMS.json, must RAISE either way."""
    leg = make_synthetic_leg(tmp_path, planted_dupe=False, planted_oob=False)
    gd = make_r4_gate_disjoint(tmp_path)

    # direction 1: a rid in the leg that ARMS.json does not have
    arms_missing_one = make_matching_r4_arms(tmp_path, leg, name="arms_missing.json")
    body = json.loads(arms_missing_one.read_text())
    del body[next(iter(body))]
    arms_missing_one.write_text(json.dumps(body))
    with pytest.raises(BR5.BuildError, match="only in the leg"):
        BR5.build(leg_path=leg, r4_gate_disjoint_path=gd,
                  r4_arms_path=arms_missing_one,
                  expect_leg_sha256="", expect_exclusion_sha256="")

    # direction 2: a rid in ARMS.json that the leg does not have
    arms_extra_one = make_matching_r4_arms(tmp_path, leg, name="arms_extra.json")
    body2 = json.loads(arms_extra_one.read_text())
    body2["tt_sp_999999999999_p1"] = {"root_id": "sp_999999999999"}
    arms_extra_one.write_text(json.dumps(body2))
    with pytest.raises(BR5.BuildError, match="only in ARMS.json"):
        BR5.build(leg_path=leg, r4_gate_disjoint_path=gd,
                  r4_arms_path=arms_extra_one,
                  expect_leg_sha256="", expect_exclusion_sha256="")


def test_arms_r5_schema_matches_build_positions_build_arms_index():
    """DESIGN ruling a13ed934: "same schema as build_positions.
    build_arms_index output". Verified against the REAL emitter, not a
    hand-typed key list that could drift from it."""
    sys.path.insert(0, str(TILETIE))
    import build_positions as BP                                  # noqa: E402
    pos = {
        "rid": "r1", "arms": [1, 2], "root_id": "root1", "stratum": "selfplay",
        "source": "bank", "rules_profile": "walled", "game_label": "g1",
        "deck_seed": 1, "ply": 5, "seat": 0, "k_remaining": 10,
        "phase_bucket": "mid", "tercile": 1, "n_legal": 2, "n_cand": 2,
        "tie_size_exact": 2, "gap": 0.0, "capped": False,
        "dropped_actions": [], "champ_action": 1, "champ_arm_index": 0,
        "champ_outside_tieset": False,
    }
    expected_keys = set(BP.build_arms_index([pos])["r1"])
    # every key build_arms_index emits must be present on a REAL R4_ARMS
    # entry -- ARMS_R5 is a verbatim copy, so this transitively covers it
    if REAL_R4_ARMS.is_file():
        r4_arms = json.loads(REAL_R4_ARMS.read_text())
        sample = next(iter(r4_arms.values()))
        missing = expected_keys - set(sample)
        assert not missing, f"real ARMS.json entry is missing {missing}"


def test_digest_reuse_no_local_hashlib_of_checksums(tmp_path, monkeypatch):
    """`build_r5_corpus.py` must compute its checksum digests through
    `gate_disjoint.load_digest_map`, never a second hash of its own."""
    leg = make_synthetic_leg(tmp_path)
    gd = make_r4_gate_disjoint(tmp_path)
    r4_arms = make_matching_r4_arms(tmp_path, leg)
    calls = []
    real = GD.load_digest_map

    def spy(paths):
        calls.append(list(paths))
        return real(paths)

    monkeypatch.setattr(BR5.GD, "load_digest_map", spy)
    BR5.build(leg_path=leg, r4_gate_disjoint_path=gd, r4_arms_path=r4_arms,
             expect_leg_sha256="", expect_exclusion_sha256="")
    assert len(calls) == 1


# --------------------------------------------------------------------------- #
# the REAL R4 post-exclusion S2 leg -- read-only                               #
# --------------------------------------------------------------------------- #
_REAL_INPUTS_PRESENT = (REAL_LEG.is_file() and REAL_R4_GATE_DISJOINT.is_file()
                        and REAL_R4_ARMS.is_file())


@pytest.mark.skipif(not _REAL_INPUTS_PRESENT,
                    reason="the real (untracked, generated) R4 S2 leg / "
                          "GATE_DISJOINT.json / ARMS.json are not present "
                          "in this checkout")
def test_real_leg_reproduces_1064_to_1060():
    corpus, dupe, arms_r5 = BR5.build(leg_path=REAL_LEG,
                                      r4_gate_disjoint_path=REAL_R4_GATE_DISJOINT,
                                      r4_arms_path=REAL_R4_ARMS)
    assert corpus["n_in"] == 1064
    assert corpus["n_excluded_r5"] == 4
    assert corpus["n_positions"] == 1060
    assert corpus["leg_sha256"] == BR5.EXPECTED_LEG_SHA256
    assert corpus["r4_exclusion_list_sha256"] == BR5.EXPECTED_R4_EXCLUSION_LIST_SHA256
    assert corpus["n_distinct_seeds"] == 980
    assert corpus["max_positions_per_seed"] == 3
    assert corpus["n_out_of_band"] == 0
    assert corpus["n_seeds_136e9"] == 0
    assert dupe["n_dupe_groups"] == 3
    assert dupe["n_dupe_positions"] == 6
    assert dupe["d_internal"] == pytest.approx(0.002819548872180451)
    assert dupe["ply_histogram"] == {2: 6}
    assert dupe["band_pairs"] == ["137e9<->137e9"] * 3
    assert "tt_sp_135000000839_p2" in corpus["excluded_rids"]

    # a13ed934: ARMS_R5.json, the materialized population authority
    assert len(arms_r5) == 1060 == corpus["arms_r5_n_rids"]
    r4_arms = json.loads(REAL_R4_ARMS.read_text())
    assert len(r4_arms) == 1064
    excluded = set(corpus["excluded_rids"])
    assert set(arms_r5) == set(r4_arms) - excluded            # BOTH directions:
    assert not (set(arms_r5) - (set(r4_arms) - excluded))     # nothing extra
    assert not ((set(r4_arms) - excluded) - set(arms_r5))     # nothing missing
    for rid in excluded:
        assert rid not in arms_r5
    # verbatim copy -- same schema as build_positions.build_arms_index
    # output (a real ARMS.json entry already IS that shape)
    sample_rid = next(iter(arms_r5))
    assert arms_r5[sample_rid] == r4_arms[sample_rid]
    assert set(arms_r5[sample_rid]) == set(r4_arms[sample_rid])
    # the sha recorded in CORPUS_R5.json is the sha of the file the CLI
    # actually writes (same canonical serialization both times)
    assert corpus["arms_r5_sha256"] == hashlib_sha256_of_json(arms_r5)


def hashlib_sha256_of_json(d) -> str:
    import hashlib
    return hashlib.sha256(
        json.dumps(d, indent=2, sort_keys=True).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# CLI                                                                           #
# --------------------------------------------------------------------------- #
def test_cli_build_r5_corpus_synthetic(tmp_path):
    leg = make_synthetic_leg(tmp_path)
    gd = make_r4_gate_disjoint(tmp_path)
    r4_arms = make_matching_r4_arms(tmp_path, leg)
    corpus_out = tmp_path / "CORPUS_R5.json"
    dupe_out = tmp_path / "GATE_INTERNAL_DUPE.json"
    arms_r5_out = tmp_path / "ARMS_R5.json"
    r = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--leg", str(leg),
         "--r4-gate-disjoint", str(gd), "--r4-arms", str(r4_arms),
         "--expect-leg-sha256", "", "--expect-exclusion-list-sha256", "",
         "--corpus-out", str(corpus_out), "--dupe-out", str(dupe_out),
         "--arms-r5-out", str(arms_r5_out)],
        capture_output=True, text=True)
    # 0 = clean, 1 = the (correctly, on this tiny saturated fixture)
    # tripped G-INTERNAL-DUPE guard -- either way both artifacts must exist
    assert r.returncode in (0, 1), r.stderr
    assert corpus_out.is_file() and dupe_out.is_file() and arms_r5_out.is_file()
    body = json.loads(corpus_out.read_text())
    assert body["schema"] == "carcassonne-rung3-r5-corpus/v1"
    arms_r5_body = json.loads(arms_r5_out.read_text())
    assert len(arms_r5_body) == body["arms_r5_n_rids"]


def test_cli_build_r5_corpus_sha_mismatch_exits_2(tmp_path):
    leg = make_synthetic_leg(tmp_path)
    gd = make_r4_gate_disjoint(tmp_path)
    r = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--leg", str(leg),
         "--r4-gate-disjoint", str(gd),
         "--expect-leg-sha256", "0" * 64,
         "--corpus-out", str(tmp_path / "c.json"),
         "--dupe-out", str(tmp_path / "d.json")],
        capture_output=True, text=True)
    assert r.returncode == 2
    assert "sha256 mismatch" in r.stderr


# =========================================================================== #
# gate_disjoint.py --r5                                                       #
# =========================================================================== #
def _two_band_corpus(tmp_path):
    s2 = tmp_path / "positions_s2"
    WF.make_corpus(s2, n_positions=3, m=32, seed=1, rid_prefix="banked",
                   band_lo=135000000350)
    # append extension-band rids to the SAME ARMS.json/leg so base_vs_extension
    # has both sides populated
    ext = tmp_path / "positions_ext_tmp"
    WF.make_corpus(ext, n_positions=3, m=32, seed=2, rid_prefix="ext",
                   band_lo=137000000508)
    arms = json.loads((s2 / "ARMS.json").read_text())
    arms_ext = json.loads((ext / "ARMS.json").read_text())
    arms.update(arms_ext)
    (s2 / "ARMS.json").write_text(json.dumps(arms))
    return s2


def _ref_corpus(tmp_path, name, *, seed, band_lo):
    d = tmp_path / name
    WF.make_corpus(d, n_positions=2, m=32, seed=seed, rid_prefix=name, band_lo=band_lo)
    return d / "ARMS.json"


def test_r5_disjoint_healthy_passes_and_types(tmp_path):
    s2 = _two_band_corpus(tmp_path)
    refs = {"tiletie0812": _ref_corpus(tmp_path, "spent1", seed=9, band_lo=28000000000),
            "tiearb2_0816": _ref_corpus(tmp_path, "spent2", seed=13, band_lo=29000000000)}
    report = GD.run_r5_gate(s2_arms=s2 / "ARMS.json", refs=refs, exclude_ref_rids={"unrelated_excluded_rid"})
    assert isinstance(report["passed"], bool)
    assert report["passed"] is True
    assert sorted(report["comparisons"]) == sorted(GD.R5_COMPARISONS)
    for name in GD.R5_COMPARISONS:
        c = report["comparisons"][name]
        assert set(c["layers"]) <= {"a_root_id", "b_rid"}
        for L in c["layers"].values():
            assert isinstance(L["n_intersection"], int)
    assert "digest_layer" in report and "NOT CARRIED" in report["digest_layer"]
    # base_vs_extension must see BOTH sides non-empty on this fixture
    bve = report["comparisons"]["base_vs_extension"]
    assert bve["layers"]["a_root_id"]["n_new"] > 0
    assert bve["layers"]["a_root_id"]["n_ref"] > 0


def test_r5_disjoint_root_leak_fires(tmp_path):
    s2 = _two_band_corpus(tmp_path)
    ref1_path = _ref_corpus(tmp_path, "spent1", seed=9, band_lo=28000000000)
    refs = {"tiletie0812": ref1_path,
            "tiearb2_0816": _ref_corpus(tmp_path, "spent2", seed=13, band_lo=29000000000)}

    # plant a leak: give an S2 rid the SAME root_id as a spent1 rid
    arms_s2 = json.loads((s2 / "ARMS.json").read_text())
    arms_ref1 = json.loads(ref1_path.read_text())
    leaked_root = next(iter(arms_ref1.values()))["root_id"]
    some_s2_rid = next(iter(arms_s2))
    arms_s2[some_s2_rid]["root_id"] = leaked_root
    (s2 / "ARMS.json").write_text(json.dumps(arms_s2))

    report = GD.run_r5_gate(s2_arms=s2 / "ARMS.json", refs=refs, exclude_ref_rids={"unrelated_excluded_rid"})
    assert report["passed"] is False
    c = report["comparisons"]["s2_vs_tiletie0812"]
    assert c["layers"]["a_root_id"]["n_intersection"] >= 1
    assert c["passed"] is False


def test_r5_disjoint_rid_leak_fires(tmp_path):
    s2 = _two_band_corpus(tmp_path)
    ref1_path = _ref_corpus(tmp_path, "spent1", seed=9, band_lo=28000000000)
    refs = {"tiletie0812": ref1_path,
            "tiearb2_0816": _ref_corpus(tmp_path, "spent2", seed=13, band_lo=29000000000)}

    arms_s2 = json.loads((s2 / "ARMS.json").read_text())
    arms_ref1 = json.loads(ref1_path.read_text())
    leaked_rid = next(iter(arms_ref1))
    arms_s2[leaked_rid] = arms_ref1[leaked_rid]
    (s2 / "ARMS.json").write_text(json.dumps(arms_s2))

    report = GD.run_r5_gate(s2_arms=s2 / "ARMS.json", refs=refs, exclude_ref_rids={"unrelated_excluded_rid"})
    assert report["passed"] is False
    c = report["comparisons"]["s2_vs_tiletie0812"]
    assert c["layers"]["b_rid"]["n_intersection"] >= 1


def test_r5_disjoint_no_digest_computed(tmp_path, monkeypatch):
    """R5 mode must never read a leg file or hash a checksum at all."""
    s2 = _two_band_corpus(tmp_path)
    refs = {"tiletie0812": _ref_corpus(tmp_path, "spent1", seed=9, band_lo=28000000000),
            "tiearb2_0816": _ref_corpus(tmp_path, "spent2", seed=13, band_lo=29000000000)}

    def _boom(*a, **k):
        raise AssertionError("load_digest_map must never be called in --r5 mode")

    monkeypatch.setattr(GD, "load_digest_map", _boom)
    monkeypatch.setattr(GD, "load_digests", _boom)
    report = GD.run_r5_gate(s2_arms=s2 / "ARMS.json", refs=refs, exclude_ref_rids={"unrelated_excluded_rid"})
    assert report["passed"] is True
    for c in report["comparisons"].values():
        assert "c_position_digest" not in c["layers"]


def test_cli_gate_disjoint_r5(tmp_path):
    # a13ed934: --r5 reads ARMS_R5.json, not <dir>/ARMS.json -- --s2-arms
    # points at the fixture's real filename explicitly here (the fixture
    # helper below writes "ARMS.json"; a13ed934's own filename convention is
    # exercised separately in test_cli_r5_s2_dir_resolves_arms_r5_json).
    s2 = _two_band_corpus(tmp_path)
    ref1 = _ref_corpus(tmp_path, "spent1", seed=9, band_lo=28000000000).parent
    ref2 = _ref_corpus(tmp_path, "spent2", seed=13, band_lo=29000000000).parent
    out = tmp_path / "GATE_DISJOINT_R5.json"
    r = subprocess.run(
        [sys.executable, str(TILETIE / "gate_disjoint.py"), "--r5",
         "--s2-arms", str(s2 / "ARMS.json"),
         "--ref", f"tiletie0812={ref1}", "--ref", f"tiearb2_0816={ref2}",
         "--out", str(out)],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    body = json.loads(out.read_text())
    assert body["mode"] == "r5"
    assert body["passed"] is True


def test_cli_r5_s2_dir_resolves_arms_r5_json(tmp_path):
    """a13ed934: `--s2-dir` (without `--s2-arms`) must resolve
    `<dir>/ARMS_R5.json` -- NEVER `<dir>/ARMS.json` (R4's own pre-exclusion
    file) -- so a bare `--s2-dir` cannot silently read the wrong population."""
    s2 = _two_band_corpus(tmp_path)
    # rename the fixture's ARMS.json to ARMS_R5.json, matching what the
    # real build_r5_corpus.py actually emits alongside it
    (s2 / "ARMS.json").rename(s2 / "ARMS_R5.json")
    ref1 = _ref_corpus(tmp_path, "spent1", seed=9, band_lo=28000000000).parent
    ref2 = _ref_corpus(tmp_path, "spent2", seed=13, band_lo=29000000000).parent
    out = tmp_path / "GATE_DISJOINT_R5.json"
    r = subprocess.run(
        [sys.executable, str(TILETIE / "gate_disjoint.py"), "--r5",
         "--s2-dir", str(s2),
         "--ref", f"tiletie0812={ref1}", "--ref", f"tiearb2_0816={ref2}",
         "--out", str(out)],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    body = json.loads(out.read_text())
    assert body["passed"] is True


def test_r5_default_s2_arms_is_arms_r5_not_plain_arms():
    assert GD.DEFAULT_R5_S2_ARMS.name == "ARMS_R5.json"


# =========================================================================== #
# r5_fixtures.py -- A1                                                        #
# =========================================================================== #
@pytest.fixture(scope="module")
def emitted_fixtures(tmp_path_factory):
    dest = tmp_path_factory.mktemp("r5_fixtures")
    RF.emit_committed_fixtures(dest)
    return dest


def test_eleven_fixtures_emitted(emitted_fixtures):
    got = {p.name for p in emitted_fixtures.glob("*.fixture.json")}
    assert got == set(RF.FIXTURE_NAMES)
    assert len(got) == 11
    assert "ARMS_R5.fixture.json" in got
    assert "STAGING_R5.fixture.json" in got


def test_a1_all_markers_pass_on_committed_fixtures(emitted_fixtures):
    report = RF.check_a1(emitted_fixtures)
    failed = {k: v for k, v in report["markers"].items() if not v["ok"]}
    assert failed == {}
    assert report["passed"] is True
    assert report["n_markers"] == len(RF.A1_MARKERS)


def test_a1_every_marker_targets_one_of_the_eleven_fixtures():
    used = {fname for fname, _, _ in RF.A1_MARKERS.values()}
    assert used == set(RF.FIXTURE_NAMES)


def test_a1_removed_fixture_fails_the_markers_that_name_it(tmp_path):
    dest = tmp_path / "fixtures"
    RF.emit_committed_fixtures(dest)
    (dest / "RUN_MANIFEST_R5.fixture.json").unlink()

    report = RF.check_a1(dest)
    assert report["passed"] is False
    failing = {k for k, v in report["markers"].items() if not v["ok"]}
    expected_failing = {k for k, (fname, _, _) in RF.A1_MARKERS.items()
                        if fname == "RUN_MANIFEST_R5.fixture.json"}
    assert failing == expected_failing
    assert failing  # non-empty — the removed file DOES gate some markers
    # every marker NOT keyed on the removed file must still pass
    for k, v in report["markers"].items():
        if k not in expected_failing:
            assert v["ok"], k


def test_a1_removed_arms_r5_fixture_fails_its_markers(tmp_path):
    """a13ed934: the population authority is MANDATORY, not optional -- its
    fixture's removal must fail A1, the same as any other."""
    dest = tmp_path / "fixtures"
    RF.emit_committed_fixtures(dest)
    (dest / "ARMS_R5.fixture.json").unlink()

    report = RF.check_a1(dest)
    assert report["passed"] is False
    failing = {k for k, v in report["markers"].items() if not v["ok"]}
    expected_failing = {k for k, (fname, _, _) in RF.A1_MARKERS.items()
                        if fname == "ARMS_R5.fixture.json"}
    assert failing == expected_failing
    assert "G-CORPUS::ARMS_R5.json" in failing
    for k, v in report["markers"].items():
        if k not in expected_failing:
            assert v["ok"], k


def test_a1_wrong_type_fails(tmp_path):
    dest = tmp_path / "fixtures"
    RF.emit_committed_fixtures(dest)
    p = dest / "CORPUS_R5.fixture.json"
    body = json.loads(p.read_text())
    body["n_in"] = "not-an-int"
    p.write_text(json.dumps(body))
    report = RF.check_a1(dest)
    assert report["markers"]["G-CORPUS::n_in"]["ok"] is False
    assert report["passed"] is False


def test_a1_bool_not_accepted_as_int_and_vice_versa():
    assert RF._type_ok(True, bool) is True
    assert RF._type_ok(1, int) is True
    assert RF._type_ok(True, int) is False   # bool must NOT satisfy an int marker
    assert RF._type_ok(1, bool) is False     # int must NOT satisfy a bool marker
    assert RF._type_ok(1.5, float) is True
    assert RF._type_ok(1, float) is True     # an int value satisfies a float marker


def test_a1_wildcard_resolves_into_unenumerated_key():
    obj = {"comparisons": {"s2_vs_x": {"layers": {"a_root_id": {"n_intersection": 0}}}}}
    v = RF.resolve_path(obj, "comparisons.*.layers.a_root_id.n_intersection")
    assert v == 0


def test_a1_wildcard_on_empty_object_raises():
    with pytest.raises(RF.A1Error):
        RF.resolve_path({"comparisons": {}}, "comparisons.*.layers")


def test_cli_r5_fixtures_check_fails_on_missing_file(tmp_path):
    dest = tmp_path / "fixtures"
    r = subprocess.run([sys.executable, str(FIXTURES_SCRIPT), "--emit",
                       "--dest", str(dest)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    (dest / "SMOKE_R5.fixture.json").unlink()
    r2 = subprocess.run([sys.executable, str(FIXTURES_SCRIPT), "--check",
                        "--dest", str(dest)], capture_output=True, text=True)
    assert r2.returncode == 1
    assert "COMPLETENESS FAILED" in r2.stderr


# =========================================================================== #
# REVIEW_R4 P1 -- s2_vs_exclude_rids: NEVER an empty default (fail-closed)     #
# =========================================================================== #
def test_r5_disjoint_refuses_empty_exclude_ref(tmp_path):
    s2 = _two_band_corpus(tmp_path)
    refs = {"tiletie0812": _ref_corpus(tmp_path, "spent1", seed=9, band_lo=28000000000),
            "tiearb2_0816": _ref_corpus(tmp_path, "spent2", seed=13, band_lo=29000000000)}
    with pytest.raises(GD.GateInputError, match="refuses to run without a non-empty"):
        GD.run_r5_gate(s2_arms=s2 / "ARMS.json", refs=refs, exclude_ref_rids=set())


def test_r5_disjoint_refuses_none_exclude_ref(tmp_path):
    s2 = _two_band_corpus(tmp_path)
    refs = {"tiletie0812": _ref_corpus(tmp_path, "spent1", seed=9, band_lo=28000000000),
            "tiearb2_0816": _ref_corpus(tmp_path, "spent2", seed=13, band_lo=29000000000)}
    with pytest.raises(GD.GateInputError, match="refuses to run without a non-empty"):
        GD.run_r5_gate(s2_arms=s2 / "ARMS.json", refs=refs, exclude_ref_rids=None)


def test_load_r4_exclusion_rids_missing_file_raises(tmp_path):
    with pytest.raises(GD.GateInputError, match="not found"):
        GD.load_r4_exclusion_rids(tmp_path / "does_not_exist.json")


def test_load_r4_exclusion_rids_wrong_serialization_raises(tmp_path):
    """A GATE_DISJOINT.json-shaped file with no `digest_exclusions.S2.rids`
    path, or a wrong-typed one, must fail loudly -- never coerce to []."""
    not_json = tmp_path / "not_json.json"
    not_json.write_text("{not valid json")
    with pytest.raises(GD.GateInputError, match="not JSON"):
        GD.load_r4_exclusion_rids(not_json)

    wrong_shape = tmp_path / "wrong_shape.json"
    wrong_shape.write_text(json.dumps({"some_other_key": {}}))
    with pytest.raises(GD.GateInputError, match="digest_exclusions.S2.rids"):
        GD.load_r4_exclusion_rids(wrong_shape)

    wrong_type = tmp_path / "wrong_type.json"
    wrong_type.write_text(json.dumps(
        {"digest_exclusions": {"S2": {"rids": "tt_sp_1_p1"}}}))  # a str, not a list
    with pytest.raises(GD.GateInputError, match="not a list"):
        GD.load_r4_exclusion_rids(wrong_type)


def test_cli_r5_refuses_missing_exclude_ref_file(tmp_path):
    s2 = _two_band_corpus(tmp_path)
    ref1 = _ref_corpus(tmp_path, "spent1", seed=9, band_lo=28000000000).parent
    ref2 = _ref_corpus(tmp_path, "spent2", seed=13, band_lo=29000000000).parent
    out = tmp_path / "GATE_DISJOINT_R5.json"
    r = subprocess.run(
        [sys.executable, str(TILETIE / "gate_disjoint.py"), "--r5",
         "--s2-dir", str(s2),
         "--ref", f"tiletie0812={ref1}", "--ref", f"tiearb2_0816={ref2}",
         "--r5-exclude-ref", str(tmp_path / "no_such_file.json"),
         "--out", str(out)],
        capture_output=True, text=True)
    assert r.returncode == 2
    assert not out.exists()
    assert ("not found" in r.stderr) or ("GATE_DISJOINT.json" in r.stderr)


def test_cli_r5_refuses_wrong_shaped_exclude_ref(tmp_path):
    s2 = _two_band_corpus(tmp_path)
    ref1 = _ref_corpus(tmp_path, "spent1", seed=9, band_lo=28000000000).parent
    ref2 = _ref_corpus(tmp_path, "spent2", seed=13, band_lo=29000000000).parent
    bad_ref = tmp_path / "bad_gate_disjoint.json"
    bad_ref.write_text(json.dumps({"digest_exclusions": {"S2": {"rids": []}}}))
    out = tmp_path / "GATE_DISJOINT_R5.json"
    r = subprocess.run(
        [sys.executable, str(TILETIE / "gate_disjoint.py"), "--r5",
         "--s2-dir", str(s2),
         "--ref", f"tiletie0812={ref1}", "--ref", f"tiearb2_0816={ref2}",
         "--r5-exclude-ref", str(bad_ref),
         "--out", str(out)],
        capture_output=True, text=True)
    # an empty rids list loads fine (0 rids) but run_r5_gate then refuses it
    # for being empty -- same fail-closed outcome, different layer
    assert r.returncode == 2
    assert not out.exists()


# --------------------------------------------------------------------------- #
# REVIEW_R4 P1 + a13ed934: the real-list 1 -> 0 pattern, end-to-end, on the   #
# REAL R4 S2 leg + REAL R4_ARMS + the REAL materialized ARMS_R5.json          #
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not _REAL_INPUTS_PRESENT,
                    reason="the real (untracked, generated) R4 S2 leg / "
                          "GATE_DISJOINT.json / ARMS.json are not present "
                          "in this checkout")
def test_real_data_exclude_rids_1_to_0_pattern_end_to_end(tmp_path):
    """REVIEW_R4 (b) + a13ed934: against the REAL 29-rid R4 S2 exclusion
    reference, `s2_vs_exclude_rids` must read `n_intersection = 1` on the
    1,064-rid REAL R4_ARMS (INPUT -- tt_sp_135000000839_p2 is still
    physically present) and `n_intersection = 0` on the 1,060-rid REAL
    materialized `ARMS_R5.json` (OUTPUT -- `build_r5_corpus.py`'s own
    exclusions applied). Uses the REAL build() output directly, not a
    hand-built stand-in -- this IS the launch evidence."""
    corpus, _, arms_r5 = BR5.build(leg_path=REAL_LEG,
                                   r4_gate_disjoint_path=REAL_R4_GATE_DISJOINT,
                                   r4_arms_path=REAL_R4_ARMS)
    excluded = set(corpus["excluded_rids"])
    assert len(excluded) == 4
    assert "tt_sp_135000000839_p2" in excluded
    assert len(arms_r5) == 1060

    r4_arms = json.loads(REAL_R4_ARMS.read_text())
    assert len(r4_arms) == 1064

    input_dir = tmp_path / "input_s2"
    input_dir.mkdir()
    (input_dir / "ARMS.json").write_text(json.dumps(r4_arms))
    output_dir = tmp_path / "output_s2"
    output_dir.mkdir()
    (output_dir / "ARMS_R5.json").write_text(json.dumps(arms_r5))

    ref1 = tmp_path / "ref1"
    WF.make_corpus(ref1, n_positions=1, m=32, seed=1, rid_prefix="unrelatedA", band_lo=1)
    ref2 = tmp_path / "ref2"
    WF.make_corpus(ref2, n_positions=1, m=32, seed=2, rid_prefix="unrelatedB", band_lo=2)
    refs = {"tiletie0812": ref1 / "ARMS.json", "tiearb2_0816": ref2 / "ARMS.json"}

    exclude_ref_rids = set(GD.load_r4_exclusion_rids(REAL_R4_GATE_DISJOINT))
    assert len(exclude_ref_rids) == 29

    report_input = GD.run_r5_gate(s2_arms=input_dir / "ARMS.json", refs=refs,
                                  exclude_ref_rids=exclude_ref_rids)
    report_output = GD.run_r5_gate(s2_arms=output_dir / "ARMS_R5.json", refs=refs,
                                   exclude_ref_rids=exclude_ref_rids)

    c_in = report_input["comparisons"]["s2_vs_exclude_rids"]
    c_out = report_output["comparisons"]["s2_vs_exclude_rids"]
    assert c_in["layers"]["b_rid"]["n_intersection"] == 1
    assert c_in["passed"] is False
    assert report_input["passed"] is False
    assert c_out["layers"]["b_rid"]["n_intersection"] == 0
    assert c_out["passed"] is True
    # the launch gate itself: the REAL materialized population authority,
    # scored against every comparison it is addressed by -- END TO END
    assert report_output["passed"] is True


@pytest.mark.skipif(not REAL_LEG.is_file() or not REAL_R4_GATE_DISJOINT.is_file(),
                    reason="the real (untracked, generated) R4 S2 leg / "
                          "GATE_DISJOINT.json are not present in this checkout")
def test_cli_r5_default_exclude_ref_resolves_to_real_r4_file():
    """The CLI's `--r5-exclude-ref` default IS the real R4 GATE_DISJOINT.json
    path -- verified loadable and non-empty (29 rids), not just present."""
    rids = GD.load_r4_exclusion_rids(GD.DEFAULT_R5_EXCLUDE_REF)
    assert len(rids) == 29
