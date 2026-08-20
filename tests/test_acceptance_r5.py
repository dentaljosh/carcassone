"""Tests for `scripts/tiletie/acceptance_r5.py` — the R5 `A1`/`A2`/`A3` auditor.

⛔ **NOTHING HERE TOUCHES THE REAL RUN DIRECTORY.** Every pass runs against a
synthetic tree built in `tmp_path`. The ONE real file these tests read is
`READ_RULE.md` itself — read-only, and read for the reason the tool exists: the
completeness assertion is over THAT FILE, so a test that invents its own rule
file would prove only that the tool agrees with itself.

The hard requirements each get a test, and they are named after the defect they
exist to catch, not after the function they call.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO / "scripts" / "tiletie" / "acceptance_r5.py"
#: read-only; NEVER edited, NEVER copied into the worktree's own tree
REAL_READ_RULE = Path(
    "/home/doctor/projects/carcassone/measurement/tiearb_widening_20260817"
    "/rung3_r5/READ_RULE.md")


def _load():
    spec = importlib.util.spec_from_file_location("acceptance_r5", TOOL_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()


# --------------------------------------------------------------------------- #
# the synthetic RUN tree                                                        #
# --------------------------------------------------------------------------- #
#: ⭐ DISTINCTIVE SENTINELS. If any of these ever appears in stdout or in the
#: `--json-out` document, the auditor has become a READ-OUT and has spent the
#: single-use pair.
SENTINELS = ("0.13820001", "SENTINEL_LEAK_9f3a", "1060777", "SENTINEL_PATH_7c1d")


def _w(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True))


def _sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_run(tmp_path: Path, *, with_legs=True, with_readout=True,
              with_fixtures=True, complete_fixtures=True) -> Path:
    """A synthetic R5 RUN dir that a healthy A1/A2/A3 all pass on.

    The layout mirrors the real one only where an ADDRESS depends on it: the
    R4 gate file sits BESIDE the run dir (`../shared_run_r4/`), because that is
    where the pinned recomputation recipe reaches for it.
    """
    run = tmp_path / "run"
    run.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REAL_READ_RULE, run / "READ_RULE.md")

    # ---- the R4 gate file, beside the run dir, and the pinned exclusion list -
    rids = ["tt_sp_135000000839_p2", "tt_sp_135000000101_p4"]
    _w(tmp_path / "shared_run_r4" / "GATE_DISJOINT.json",
       {"digest_exclusions": {"S2": {"rids": rids}}})
    import hashlib
    excl_sha = hashlib.sha256(
        json.dumps(sorted(rids)).encode("utf-8")).hexdigest()

    # ---- the physical leg file, under a SENTINEL-named directory ------------ #
    leg = tmp_path / "SENTINEL_PATH_7c1d" / "positions_walled_leg1.jsonl"
    leg.parent.mkdir(parents=True, exist_ok=True)
    leg.write_text('{"rid": "tt_sp_1_p2"}\n')

    # ---- the population authority ------------------------------------------- #
    _w(run / "ARMS_R5.json",
       {"tt_sp_1_p2": {"arms": [1, 2], "ply": 2, "root_id": "sp_1"}})

    _w(run / "CORPUS_R5.json", {
        "leg_path": str(leg),
        "leg_sha256": _sha(leg),
        "r4_exclusion_list_sha256": excl_sha,
        "n_in": 1064,
        "n_excluded_r5": 4,
        "n_positions": 1060777,                     # ⭐ sentinel
        "excluded_rids": ["tt_sp_135000000839_p2"],
        "arms_r5_sha256": _sha(run / "ARMS_R5.json"),
        "seed_ranges": {"banked_135e9": [1, 2]},
        "n_distinct_seeds": 980,
        "n_out_of_band": 0,
        "n_seeds_136e9": 0,
        "max_positions_per_seed": 3,
    })
    _w(run / "FLOORS_R5.json",
       {"population_authority": {"arms_r5_sha256": _sha(run / "ARMS_R5.json")}})

    _w(run / "STAGING_R5.json", {
        "arms_r5_sha256": _sha(run / "ARMS_R5.json"),
        "staged_arms_sha256": _sha(run / "ARMS_R5.json"),
        "arms_copy_identical": True, "n_leg_rids": 1060, "n_arms_rids": 1060,
        "rid_sets_equal": True, "missing_in_leg": [], "missing_in_arms": [],
        "stage_chunks_rid_set_agrees": True, "n_chunks": 8,
    })
    _w(run / "GATE_INTERNAL_DUPE.json", {
        "n_positions": 1064, "n_dupe_groups": 3, "n_dupe_positions": 6,
        "d_internal": 0.13820001,                   # ⭐ sentinel
        "ply_histogram": {"2": 6}, "band_pairs": ["137e9<->137e9"],
        "leg_sha256": _sha(leg),
    })
    # ⚠️ one comparison legitimately has NO `a_root_id` layer (a JSON reference
    # list has no root identity) — the real emitter records `layers_absent`
    # rather than fabricating a zero, and a healthy run must still pass.
    _w(run / "GATE_DISJOINT_R5.json", {
        "passed": True,
        "comparisons": {
            "s2_vs_tiletie0812": {"layers": {
                "a_root_id": {"n_intersection": 0},
                "b_rid": {"n_intersection": 0}}},
            "s2_vs_exclude_rids": {
                "layers": {"b_rid": {"n_intersection": 0}},
                "layers_absent": ["a_root_id"]},
        },
    })
    _w(run / "SMOKE_R5.json", {"m_worlds": 32, "driver": "run_tiletie --smoke"})

    # ---- post-scoring emitters ---------------------------------------------- #
    _w(run / "RUN_MANIFEST_R5.json", {
        "m_worlds": 32, "b_ceiling_from_m": 16,
        "world_seed_salt": "SENTINEL_LEAK_9f3a",    # ⭐ sentinel
        "arb_backend": "rust", "arb_legal_mask_cache": True,
        "resolved_backend_by_leg": {"tier1-greedy/walled": "rust"},
    })
    _w(run / "corpus" / "positions_s2" / "POSITIONS_PLAN.json",
       {"deployed_cap_j": 4})
    _w(run / "corpus" / "positions_s2" / "ARMS.json",
       {"tt_sp_1_p2": {"cap_seed": 7}, "tt_sp_2_p4": {"cap_seed": 9}})
    _w(run / "D_DRAW.json", {"n_checked": 100})
    _w(run / "MERGE_REPORT_s2.json", {"ok": True})
    if with_legs:
        _w(run / "legs/s2/tier1-greedy/walled/leg1/manifest.json",
           {"resolved_config": {"m": 32, "world_seed_salt": "tiletie-v1",
                                "legal_mask_cache": True}})
    if with_readout:
        _w(run / "verdicts" / "READOUT.json", {"widening": {
            "completion": {"s2_n": 1007},
            "failed": {"n_failed_rids": 0, "n_attempted": 1060, "rate": 0.0,
                       "by_class": {}},
            "j_rider": {"d_draw": {"d_draw_ran": True}}}})

    if with_fixtures:
        f = run / "fixtures"
        f.mkdir(parents=True, exist_ok=True)
        for name, src in (
                ("CORPUS_R5.fixture.json", run / "CORPUS_R5.json"),
                ("ARMS_R5.fixture.json", run / "ARMS_R5.json"),
                ("STAGING_R5.fixture.json", run / "STAGING_R5.json"),
                ("GATE_INTERNAL_DUPE.fixture.json",
                 run / "GATE_INTERNAL_DUPE.json"),
                ("GATE_DISJOINT_R5.fixture.json", run / "GATE_DISJOINT_R5.json"),
                ("SMOKE_R5.fixture.json", run / "SMOKE_R5.json"),
                ("RUN_MANIFEST_R5.fixture.json", run / "RUN_MANIFEST_R5.json"),
                ("D_DRAW.fixture.json", run / "D_DRAW.json"),
                ("MERGE_REPORT_s2.fixture.json", run / "MERGE_REPORT_s2.json"),
                ("READOUT.fixture.json", run / "verdicts" / "READOUT.json"),
                ("leg_manifest.fixture.json",
                 run / "legs/s2/tier1-greedy/walled/leg1/manifest.json"),
        ):
            if src.is_file():
                shutil.copyfile(src, f / name)
        if complete_fixtures:
            # the two the REAL pair does not commit — see the module report
            shutil.copyfile(run / "corpus/positions_s2/POSITIONS_PLAN.json",
                            f / "POSITIONS_PLAN.fixture.json")
            shutil.copyfile(run / "corpus/positions_s2/ARMS.json",
                            f / "ARMS.fixture.json")
    return run


def cli(run: Path, which: str, out: Path = None):
    cmd = [sys.executable, str(TOOL_PATH), "--pass", which, "--run", str(run)]
    if out:
        cmd += ["--json-out", str(out)]
    return subprocess.run(cmd, capture_output=True, text=True)


# --------------------------------------------------------------------------- #
# REQUIREMENT 3 — the parser, on a small auditable sample                       #
# --------------------------------------------------------------------------- #
SAMPLE = """
# sample

| gate | marker | conjunct | address |
|---|---|---|---|
| `G-ONE` | `[post-corpus]` | `n == 3` and `some_key` is prose | `RUN/A.json::{x, y}` · `RUN/B.json` |
| `G-TWO` | `[post-scoring]` | nested braces | `RUN/C.json::{passed, deep.<name>.layers.{p,q}.n}` |
| `G-THREE`, `G-FOUR` | `[pre-corpus]` | carried | as carried |
| `G-FIVE` | `[post-scoring]` | readout | `READOUT::widening.a.b` |
"""


def test_parsed_addresses_on_a_small_inline_sample():
    p = m.parsed_addresses(SAMPLE)
    assert p["addresses"] == sorted([
        "RUN/A.json::x", "RUN/A.json::y", "RUN/B.json",
        "RUN/C.json::passed",
        "RUN/C.json::deep.<name>.layers.p.n",
        "RUN/C.json::deep.<name>.layers.q.n",
        "READOUT::widening.a.b",
    ])
    # prose in the address column is NOT an address, and a bare filename with no
    # directory is not one either — that is what keeps `ARMS_R5.json` from being
    # counted twice beside `RUN/ARMS_R5.json`.
    assert "some_key" not in " ".join(p["addresses"])
    # the "as carried" row names NO address and is REPORTED, never resolved
    assert p["carried_without_address"][0]["gates"] == ["G-THREE", "G-FOUR"]


def test_expand_braces_handles_nesting():
    assert m.expand_braces("a.{b,c}.d") == ["a.b.d", "a.c.d"]
    assert m.expand_braces("{p, q.{r,s}.t}") == ["p", "q.r.t", "q.s.t"]
    assert m.expand_braces("no braces") == ["no braces"]
    # an unbalanced brace is returned LITERALLY — a parser that repairs its own
    # input cannot be audited
    assert m.expand_braces("a.{b") == ["a.{b"]


def test_table_covers_exactly_the_real_read_rule_address_set():
    """The verification the build exists for: the table equals the FILE."""
    parsed = m.parsed_addresses(REAL_READ_RULE.read_text())
    comp = m.completeness(m.address_table(), parsed)
    assert comp["uncovered"] == [], "READ_RULE names an address no pass audits"
    assert comp["invented"] == [], "the table names an address READ_RULE does not"
    assert comp["union_equals_table"], "an address is audited at NEITHER pass"
    assert comp["ok"]
    # the carried-gate row: seven gates, no address, reported not resolved
    assert comp["carried_without_address"][0]["gates"] == [
        "G-LEAF", "G-PREFIX", "G-CRN", "G-UNCAPPED", "G-DRAW", "G-ARMS",
        "G-BITEXACT@HEAD"]


# --------------------------------------------------------------------------- #
# the three passes, healthy                                                     #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("which", ["A1", "A2", "A3"])
def test_pass_is_green_on_a_healthy_synthetic_run(tmp_path, which):
    run = build_run(tmp_path)
    r = cli(run, which)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a2_does_not_demand_an_address_its_position_makes_impossible(tmp_path):
    """§1: *no pass may demand an address its own position makes impossible.*
    A2 runs BEFORE the first scoring leg, so no leg manifest and no READOUT
    exist — and it must still pass."""
    run = build_run(tmp_path, with_legs=False, with_readout=False)
    assert cli(run, "A2").returncode == 0
    # ... while A3, which is positioned after them, correctly fails
    assert cli(run, "A3").returncode == 2


def test_every_address_is_audited_at_some_pass(tmp_path):
    run = build_run(tmp_path)
    seen = set()
    for which in ("A1", "A2", "A3"):
        rep, _ = m.run_pass(which, run, run / "READ_RULE.md")
        seen |= {a["address"] for a in rep["addresses"]}
    named = set(m.parsed_addresses(REAL_READ_RULE.read_text())["addresses"])
    assert seen == named


# --------------------------------------------------------------------------- #
# REQUIREMENT 1 — NO VALUE IS EVER PRINTED OR STORED                            #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("which", ["A1", "A2", "A3"])
def test_no_value_leaks_into_stdout_or_the_json_document(tmp_path, which):
    run = build_run(tmp_path)
    out = tmp_path / "report.json"          # deliberately OUTSIDE the run dir
    r = cli(run, which, out=out)
    assert r.returncode == 0, r.stdout + r.stderr
    doc = out.read_text()
    for sentinel in SENTINELS:
        assert sentinel not in r.stdout, f"{sentinel!r} leaked to stdout"
        assert sentinel not in r.stderr, f"{sentinel!r} leaked to stderr"
        assert sentinel not in doc, f"{sentinel!r} leaked into --json-out"
    # what it MAY say: the type name, and nothing narrower
    report = json.loads(doc)
    types = {t for a in report["addresses"] for t in a["types"]}
    assert types <= {"object", "array", "string", "number", "boolean", "null"}


def test_the_type_names_are_the_json_ones_not_pythons():
    assert m.json_type(True) == "boolean"        # ⚠️ before int: bool IS an int
    assert m.json_type(3) == "number"
    assert m.json_type(3.5) == "number"          # int/float would leak a value
    assert m.json_type("x") == "string"
    assert m.json_type([]) == "array"
    assert m.json_type({}) == "object"
    assert m.json_type(None) == "null"


def test_a_null_is_absent(tmp_path):
    run = build_run(tmp_path)
    doc = json.loads((run / "STAGING_R5.json").read_text())
    doc["n_chunks"] = None
    _w(run / "STAGING_R5.json", doc)
    rep, code = m.run_pass("A2", run, run / "READ_RULE.md")
    row = next(a for a in rep["addresses"]
               if a["address"] == "RUN/STAGING_R5.json::n_chunks")
    assert row["state"] == "UNRESOLVED" and row["types"] == ["null"]
    assert code == 2


# --------------------------------------------------------------------------- #
# REQUIREMENT 2 — primary and fallback are resolved INDEPENDENTLY               #
# --------------------------------------------------------------------------- #
def test_a_broken_fallback_is_reported_even_though_its_primary_resolves(tmp_path):
    run = build_run(tmp_path)
    # G-M's primary (`RUN_MANIFEST_R5::m_worlds`) stays healthy; its
    # pre-registered fallback (`…leg<N>/manifest.json::resolved_config.m`) is
    # quietly removed — the fail-always/pass-always defect in the making.
    leg = run / "legs/s2/tier1-greedy/walled/leg1/manifest.json"
    doc = json.loads(leg.read_text())
    del doc["resolved_config"]["m"]
    _w(leg, doc)

    rep, code = m.run_pass("A3", run, run / "READ_RULE.md")
    by = {(a["gate"], a["role"], a["address"]): a for a in rep["addresses"]}
    primary = by[("G-M", "primary", "RUN/RUN_MANIFEST_R5.json::m_worlds")]
    fallback = by[("G-M", "fallback",
                   "RUN/legs/s2/tier1-greedy/walled/leg<N>/manifest.json"
                   "::resolved_config.m")]
    assert primary["state"] == "resolved"
    assert fallback["state"] == "UNRESOLVED"
    # ... and it is RECORDED, not hidden behind the healthy primary
    assert fallback["address"] in rep["unaudited_fallbacks"]
    assert code == 2

    # G-SALT's fallback on the SAME manifest is untouched and still resolves —
    # a log that convicts the wrong row is how a wrong cause survives
    salt = by[("G-SALT", "fallback",
               "RUN/legs/s2/tier1-greedy/walled/leg<N>/manifest.json"
               "::resolved_config.world_seed_salt")]
    assert salt["state"] == "resolved"


# --------------------------------------------------------------------------- #
# REQUIREMENT 3 — the completeness assertion, both directions                   #
# --------------------------------------------------------------------------- #
def test_an_address_named_in_the_file_but_in_no_pass_fails(tmp_path, monkeypatch):
    run = build_run(tmp_path)
    dropped = "RUN/STAGING_R5.json::missing_in_arms"
    monkeypatch.setattr(m, "ADDRESS_TABLE",
                        tuple(r for r in m.ADDRESS_TABLE
                              if r.address != dropped))
    rep, code = m.run_pass("A2", run, run / "READ_RULE.md")
    assert code == 2
    assert rep["completeness"]["uncovered"] == [dropped]
    assert not rep["completeness"]["ok"]


def test_an_address_in_the_table_but_not_in_the_file_fails(tmp_path, monkeypatch):
    run = build_run(tmp_path)
    bogus = m.Addr("RUN/CORPUS_R5.json::invented_key", "G-CORPUS",
                   "[post-corpus]", "CORPUS_R5.json", "invented_key")
    monkeypatch.setattr(m, "ADDRESS_TABLE", m.ADDRESS_TABLE + (bogus,))
    rep, code = m.run_pass("A2", run, run / "READ_RULE.md")
    assert code == 2
    assert rep["completeness"]["invented"] == ["RUN/CORPUS_R5.json::invented_key"]


def test_the_carried_row_is_reported_and_never_counted_as_covered(tmp_path):
    run = build_run(tmp_path)
    rep, code = m.run_pass("A2", run, run / "READ_RULE.md")
    assert code == 0
    carried = rep["completeness"]["carried_without_address"]
    assert len(carried) == 1
    assert "G-BITEXACT@HEAD" in carried[0]["gates"]
    # none of those gates appears as an audited address anywhere
    assert not [a for a in rep["addresses"] if a["gate"] in carried[0]["gates"]]


def test_the_rejected_2_2_spelling_is_surfaced_not_audited():
    """§2.2 REJECTS `SMOKE_R5.json::resolved_config.m`. Auditing it would build
    the fail-always fallback that ruling exists to prevent — so it is reported
    under `rulings_not_addresses` and covered by no pass."""
    parsed = m.parsed_addresses(REAL_READ_RULE.read_text())
    assert "SMOKE_R5.json::resolved_config.m" in parsed["rulings_not_addresses"]
    assert not [a for a in parsed["addresses"] if "resolved_config.m" in a
                and a.startswith("SMOKE")]


# --------------------------------------------------------------------------- #
# REQUIREMENT 4 — A2 VERIFIES THE FREEZE (D6)                                   #
# --------------------------------------------------------------------------- #
def test_one_altered_byte_in_the_leg_file_raises(tmp_path):
    run = build_run(tmp_path)
    leg = Path(json.loads((run / "CORPUS_R5.json").read_text())["leg_path"])
    leg.write_text(leg.read_text().replace("p2", "p3"))     # one byte

    r = cli(run, "A2")
    assert r.returncode == 3, r.stdout + r.stderr
    msg = r.stdout + r.stderr
    assert "RAISE" in msg
    assert "repair" not in msg.lower()          # it does not offer to fix it
    # ⚠️ and the escalation itself must not leak: `leg_path` is a VALUE
    for sentinel in SENTINELS:
        assert sentinel not in msg
    assert "leg_sha256" in msg                  # it names the failing pin


def test_a_drifted_exclusion_list_raises(tmp_path):
    run = build_run(tmp_path)
    gd = tmp_path / "shared_run_r4" / "GATE_DISJOINT.json"
    _w(gd, {"digest_exclusions": {"S2": {"rids": ["tt_sp_999_p9"]}}})
    r = cli(run, "A2")
    assert r.returncode == 3
    assert "RAISE" in r.stderr and "r4_exclusion_list_sha256" in r.stderr


def test_a_missing_r4_gate_file_raises_rather_than_reaching_for_a_txt(tmp_path):
    run = build_run(tmp_path)
    (tmp_path / "shared_run_r4" / "GATE_DISJOINT.json").unlink()
    (tmp_path / "shared_run_r4" / "EXCLUDE_RIDS_S2.txt").write_text("x\n")
    r = cli(run, "A2")
    assert r.returncode == 3
    assert "EXCLUDE_RIDS" in r.stderr    # names the trap it refuses to fall into


def test_a_drifted_population_authority_raises(tmp_path):
    run = build_run(tmp_path)
    _w(run / "ARMS_R5.json", {"tt_sp_1_p2": {"arms": [1, 2, 3]}})
    r = cli(run, "A2")
    assert r.returncode == 3
    assert "arms_r5_sha256" in r.stderr


def test_the_freeze_report_says_match_or_mismatch_and_nothing_else(tmp_path):
    run = build_run(tmp_path)
    rep, code = m.run_pass("A2", run, run / "READ_RULE.md")
    assert code == 0
    results = [c["result"] for c in rep["freeze_verification"]["checks"]]
    assert all(r in ("match", "MISMATCH") or r.startswith("not published")
               for r in results)
    # no sha anywhere in the freeze block (a 64-hex run would be one)
    import re
    assert not re.search(r"[0-9a-f]{64}",
                         json.dumps(rep["freeze_verification"]))


def test_a1_and_a3_do_not_verify_the_freeze(tmp_path):
    """A2 owns the freeze check — A1 is pre-corpus (the artifacts are fixtures)
    and A3 is after the fact. Neither may RAISE on it."""
    run = build_run(tmp_path)
    for which in ("A1", "A3"):
        rep, _ = m.run_pass(which, run, run / "READ_RULE.md")
        assert rep["freeze_verification"] is None


# --------------------------------------------------------------------------- #
# REQUIREMENT 7 — the fixture NAMING CONFLICT is handled AND reported           #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", ["READOUT.fixture.json", "READOUT_R5.fixture.json"])
def test_either_readout_fixture_name_is_accepted_and_the_one_found_is_recorded(
        tmp_path, name):
    run = build_run(tmp_path)
    f = run / "fixtures"
    (f / "READOUT.fixture.json").rename(f / name)
    rep, code = m.run_pass("A1", run, run / "READ_RULE.md")
    assert code == 0
    amb = rep["readout_fixture_ambiguity"]
    assert amb["found"] == name
    assert set(amb["accepted"]) == {"READOUT.fixture.json",
                                    "READOUT_R5.fixture.json"}
    # the CONFLICT itself stays visible — the pair is not edited to settle it
    assert "READOUT.fixture.json" in amb["design_fixture_list_names"]
    assert "READOUT_R5.fixture.json" in amb["execution_layer_ruling_names"]


def test_readout_r5_wins_when_both_names_are_present(tmp_path):
    run = build_run(tmp_path)
    f = run / "fixtures"
    shutil.copyfile(f / "READOUT.fixture.json", f / "READOUT_R5.fixture.json")
    rep, _ = m.run_pass("A1", run, run / "READ_RULE.md")
    assert rep["readout_fixture_ambiguity"]["found"] == "READOUT_R5.fixture.json"


# --------------------------------------------------------------------------- #
# A1 — a missing fixture is a REPORTED HOLE, never a silent pass                 #
# --------------------------------------------------------------------------- #
def test_an_address_with_no_committed_fixture_fails_a1_by_name(tmp_path):
    run = build_run(tmp_path, complete_fixtures=False)
    rep, code = m.run_pass("A1", run, run / "READ_RULE.md")
    assert code == 2
    assert set(rep["no_fixture_committed"]) == {
        "RUN/corpus/positions_s2/POSITIONS_PLAN.json::deployed_cap_j",
        "…/ARMS.json::<rid>.cap_seed"}
    row = next(a for a in rep["addresses"]
               if a["address"] == "…/ARMS.json::<rid>.cap_seed")
    assert "NO COMMITTED FIXTURE" in row["why"]
    # ⚠️ it is still COVERED — reported at A1, resolved live at A3
    assert rep["completeness"]["ok"]


def test_a1_catches_a_misspelled_address_before_the_blind_commit(tmp_path):
    run = build_run(tmp_path)
    doc = json.loads((run / "fixtures" / "SMOKE_R5.fixture.json").read_text())
    doc["resolved_config"] = {"m": doc.pop("m_worlds")}   # §2.2's REJECTED shape
    _w(run / "fixtures" / "SMOKE_R5.fixture.json", doc)
    rep, code = m.run_pass("A1", run, run / "READ_RULE.md")
    assert code == 2
    bad = [a for a in rep["addresses"] if a["state"] == "UNRESOLVED"]
    assert [a["address"] for a in bad] == ["RUN/SMOKE_R5.json::m_worlds"]


def test_a_wildcard_layer_absent_on_one_comparison_does_not_fail_a_healthy_run(
        tmp_path):
    """`s2_vs_exclude_rids` has NO `a_root_id` layer by design — the emitter
    declares it absent rather than fabricating a zero. Demanding the layer on
    EVERY comparison would fail every healthy run."""
    run = build_run(tmp_path)
    rep, code = m.run_pass("A2", run, run / "READ_RULE.md")
    assert code == 0
    row = next(a for a in rep["addresses"] if "a_root_id" in a["address"])
    assert row["state"] == "resolved"


# --------------------------------------------------------------------------- #
# REQUIREMENT 5 — the CLI contract                                              #
# --------------------------------------------------------------------------- #
def test_exit_codes_are_distinct(tmp_path):
    run = build_run(tmp_path)
    assert cli(run, "A2").returncode == 0
    (run / "STAGING_R5.json").unlink()
    assert cli(run, "A2").returncode == 2            # UNRESOLVED
    leg = Path(json.loads((run / "CORPUS_R5.json").read_text())["leg_path"])
    leg.write_text("tampered\n")
    assert cli(run, "A2").returncode == 3            # D6 RAISE outranks a FAIL


def test_it_writes_nothing_into_the_run_dir(tmp_path):
    run = build_run(tmp_path)
    before = {p.relative_to(run): p.stat().st_mtime_ns
              for p in run.rglob("*") if p.is_file()}
    out = tmp_path / "elsewhere" / "report.json"
    assert cli(run, "A1", out=out).returncode == 0
    assert cli(run, "A2", out=out).returncode == 0
    after = {p.relative_to(run): p.stat().st_mtime_ns
             for p in run.rglob("*") if p.is_file()}
    assert before == after
    assert out.is_file()


def test_the_read_rule_defaults_to_the_run_dir_copy(tmp_path):
    run = build_run(tmp_path)
    (run / "READ_RULE.md").unlink()
    r = cli(run, "A2")
    assert r.returncode == 2 and "no address authority" in r.stderr


def test_an_explicit_read_rule_path_is_honoured(tmp_path):
    run = build_run(tmp_path)
    moved = tmp_path / "READ_RULE_elsewhere.md"
    shutil.move(str(run / "READ_RULE.md"), str(moved))
    r = subprocess.run(
        [sys.executable, str(TOOL_PATH), "--pass", "A2", "--run", str(run),
         "--read-rule", str(moved)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_missing_run_dir_is_a_failure_not_a_traceback(tmp_path):
    r = subprocess.run(
        [sys.executable, str(TOOL_PATH), "--pass", "A1",
         "--run", str(tmp_path / "nope")], capture_output=True, text=True)
    assert r.returncode == 2 and "Traceback" not in r.stderr


# --------------------------------------------------------------------------- #
# REQUIREMENT 6 — the two-marker gate is SPLIT, and the split is the one §2 gives
# --------------------------------------------------------------------------- #
def test_g_m_is_split_pre_leg_post_corpus_and_post_post_scoring():
    rows = {r.address: r for r in m.address_table() if r.gate == "G-M"}
    assert rows["RUN/SMOKE_R5.json::m_worlds"].marker == "[post-corpus]"
    assert rows["RUN/RUN_MANIFEST_R5.json::m_worlds"].marker == "[post-scoring]"
    assert rows["RUN/RUN_MANIFEST_R5.json::b_ceiling_from_m"].marker \
        == "[post-scoring]"
    fb = rows["RUN/legs/s2/tier1-greedy/walled/leg<N>/manifest.json"
              "::resolved_config.m"]
    assert fb.marker == "[post-scoring]" and fb.role == "fallback"
    # the point of the split: the halt fires at A2, BEFORE the leg spend
    assert rows["RUN/SMOKE_R5.json::m_worlds"].in_pass("A2")
    assert not rows["RUN/RUN_MANIFEST_R5.json::m_worlds"].in_pass("A2")


def test_every_table_row_carries_a_gate_and_a_marker():
    for r in m.address_table():
        assert r.gate.startswith("G-")
        assert r.marker in ("[pre-corpus]", "[post-corpus]", "[post-scoring]")
        assert r.role in ("primary", "fallback")
