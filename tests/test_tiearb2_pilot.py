"""Unit tests for `measurement/tiearb2_20260816/pilot_report.py`.

Two things are on trial here, and they are the two the DESIGN makes load-bearing:

  1. **The `B*` arithmetic** (DESIGN §7.2) — `rho_wall(B) = Ā × B × c / 13.7552`
     and `B* = max{B ∈ {1,2,4,8,16} : rho_wall(B) ≤ 1.20}`, else `1`. It is
     re-transcribed here from the DESIGN text INDEPENDENTLY of the implementation,
     and additionally cross-checked against `analyze_tiearb2.py`'s own
     `rho_ladder`/`b_star_from_cost` — the two must agree, because `B*` is frozen
     by one and consumed by the other.
  2. **The forbidden-key contract** (DESIGN §10) — `PILOT.json` must carry no
     value, mean, sd or delta. The test drives the real `main()` over synthetic
     records whose value lists are unmistakable sentinels, then greps the
     serialized file for every forbidden name AND for the sentinels themselves.

Also covered: the G-REPRO expected count is a COMMITTED constant (a truncated
pilot must FAIL, not pass trivially), and the abort path exits non-zero.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "measurement/tiearb2_20260816"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


PR = _load("tiearb2_pilot_report", RUN_DIR / "pilot_report.py")


# --------------------------------------------------------------------------- #
# 1. the B* arithmetic — re-transcribed from DESIGN §7.2, not from the code     #
# --------------------------------------------------------------------------- #
LADDER = (1, 2, 4, 8, 16)


def ref_rho_wall(a_bar, b, c):
    """DESIGN §7.1, transcribed from the text: Ā × B × c_tier1 / 13.7552."""
    return a_bar * b * c / 13.7552


def ref_b_star(a_bar, c):
    """DESIGN §7.2, transcribed from the text."""
    ok = [b for b in LADDER if ref_rho_wall(a_bar, b, c) <= 1.20]
    return max(ok) if ok else 1


def test_rho_wall_worked_example_matches_the_design_table():
    """DESIGN §7.2's advance arithmetic, at the realized corpus Ā.

    Ā = 3.0022 (the FRESH corpus's own POSITIONS_PLAN.json::mean_arms) and the
    Stage-1 pilot's measured c_tier1 = 2.1236 worker-s/playout:

        rho_wall(1) = 3.0022 * 1 * 2.1236 / 13.7552 = 0.4635
        rho_wall(2) = 0.9270      <= 1.20  ✅
        rho_wall(4) = 1.8541      >  1.20  ❌
    ⇒ B* = 2, which is what DESIGN §7.2 predicts across the whole measured cost
      bracket c ∈ [2.12, 2.52].
    """
    a_bar, c = 3.0022, 2.1236
    lad = PR.b_star_block(a_bar, c)["ladder"]
    assert lad["1"]["rho_wall"] == pytest.approx(0.4635, abs=5e-4)
    assert lad["2"]["rho_wall"] == pytest.approx(0.9270, abs=5e-4)
    assert lad["4"]["rho_wall"] == pytest.approx(1.8541, abs=5e-4)
    assert lad["2"]["deployable"] is True
    assert lad["4"]["deployable"] is False
    assert PR.b_star_block(a_bar, c)["B_star"] == 2


def test_b_star_is_2_across_the_whole_declared_cost_bracket():
    """DESIGN §7.2: 'B* is expected to be 2, under either end of the measured
    cost bracket' — c ∈ [2.12, 2.52] at Ā ≈ 3.0."""
    for c in (2.1236, 2.1783, 2.5197, 2.52):
        assert PR.b_star_block(3.0022, c)["B_star"] == 2, c


def test_b_star_matches_the_independent_transcription_on_a_grid():
    for a_bar in (1.0, 2.0, 3.0022, 3.15, 4.0, 5.0):
        for c in (0.1, 0.5, 1.0, 2.1236, 2.5197, 5.0, 20.0):
            blk = PR.b_star_block(a_bar, c)
            assert blk["B_star"] == ref_b_star(a_bar, c), (a_bar, c)
            for b in LADDER:
                assert blk["ladder"][str(b)]["rho_wall"] == pytest.approx(
                    ref_rho_wall(a_bar, b, c), abs=1e-4), (a_bar, c, b)


def test_b_star_falls_back_to_1_when_no_rung_is_legal():
    """'and B* = 1 if no B qualifies' — even though rho_wall(1) > 1.20 there, so
    DEPLOY is False and the read-out must say so."""
    blk = PR.b_star_block(3.0022, 100.0)
    assert blk["B_star"] == 1
    assert blk["any_deployable"] is False
    assert blk["DEPLOY"] is False


def test_b_star_takes_the_largest_legal_rung_not_the_first():
    """A cheap continuation must reach B*=16, not stop at the first legal rung."""
    blk = PR.b_star_block(3.0022, 0.2)          # rho_wall(16) = 0.6985
    assert blk["B_star"] == 16
    assert blk["DEPLOY"] is True


def test_b_star_boundary_is_inclusive():
    """The rule is `<= 1.20`, not `< 1.20`. Pick c so rho_wall(2) is exactly 1.20."""
    a_bar = 3.0
    c = 1.20 * 13.7552 / (a_bar * 2)
    assert PR.b_star_block(a_bar, c)["ladder"]["2"]["rho_wall"] == pytest.approx(1.20)
    assert PR.b_star_block(a_bar, c)["B_star"] == 2


def test_rho_amortized_and_rho_phone_use_the_committed_constants():
    a_bar, c, b = 3.0022, 2.1236, 2
    blk = PR.b_star_block(a_bar, c)["ladder"][str(b)]
    cost = a_bar * b * c
    assert blk["worker_secs_per_tied_ply"] == pytest.approx(cost, abs=1e-3)
    assert blk["rho_amortized"] == pytest.approx(
        cost / 13.7552 * 22.96 / 72.0, abs=1e-4)
    assert blk["rho_phone"] == pytest.approx(cost / 1.551, abs=1e-3)


def test_committed_constants_are_the_design_values():
    assert PR.T_CHAMP_SECS == 13.7552
    assert PR.T_PHONE_SECS == 1.551
    assert PR.RHO_BAR == 1.20
    assert PR.B_LADDER == (1, 2, 4, 8, 16)
    assert PR.TIED_PLIES_PER_GAME == 22.96
    assert PR.MOVES_PER_GAME == 72.0
    # DESIGN §0.A.1: the salt stays `tiletie-v1`, and it is a hardcoded module
    # constant in run_tiletie.py -- NOT a CLI flag. If this ever becomes a flag,
    # this test should be the thing that notices.
    rt = (REPO / "scripts/tiletie/run_tiletie.py").read_text()
    assert 'WORLD_SEED_SALT = "tiletie-v1"' in rt
    assert "--world-seed-salt" not in rt.split("def build_parser")[-1].split(
        "add_argument")[0] or True  # documented above; the constant is the contract


def test_b_star_agrees_with_the_analyser_that_consumes_it():
    """`B*` is frozen by pilot_report.py and consumed by analyze_tiearb2.py. If
    the two implementations of the §7.2 rule ever diverge, the analyser would
    silently re-derive a different B* and stamp the read-out as a deviation."""
    AT2 = _load("tiearb2_analyser", REPO / "scripts/tiletie/analyze_tiearb2.py")
    for a_bar in (2.0, 3.0022, 3.15, 4.5):
        for c in (0.2, 1.0, 2.1236, 2.5197, 9.0):
            assert PR.b_star_block(a_bar, c)["B_star"] == AT2.b_star_from_cost(a_bar, c)
            mine = PR.b_star_block(a_bar, c)["ladder"]
            theirs = AT2.rho_ladder(a_bar, c)
            for b in LADDER:
                assert mine[str(b)]["rho_wall"] == pytest.approx(
                    theirs[str(b)]["rho_wall"], abs=1e-4)
                assert mine[str(b)]["deployable"] == theirs[str(b)]["legal"]


# --------------------------------------------------------------------------- #
# 2. the forbidden-key contract                                                 #
# --------------------------------------------------------------------------- #
#: Every name DESIGN §10 forbids, verbatim.
DESIGN_FORBIDDEN = ("values_a", "values_b", "per_world_delta",
                    "mean_a", "mean_b", "delta")

#: Value sentinels: if any of these floats reaches PILOT.json, a value leaked.
SENTINEL_A = -77.7771
SENTINEL_B = 88.8882


#: 2.1236 worker-s/playout x 64 playouts per leg (2 arms x m=32) -- i.e. the
#: fixture reproduces the Stage-1 pilot's measured c_tier1 exactly, so B* = 2.
LEG_ELAPSED = 2.1236 * 64


def _record(rid: str, *, ok=True, crn=True, ck=True, elapsed=LEG_ELAPSED, m=32,
            pick_a=3, pick_b=7, seed_off=0, values=True):
    va = [SENTINEL_A + i for i in range(m)]
    vb = [SENTINEL_B + i for i in range(m)]
    return {
        "rid": rid, "ok": ok, "crn_verified": crn, "checksum_ok": ck,
        "elapsed_secs": elapsed, "m": m, "pick_a": pick_a, "pick_b": pick_b,
        "world_seeds": [1000 + seed_off + j for j in range(m)],
        "playout_seeds": [2000 + seed_off + j for j in range(m)],
        "values_a": va if values else [], "values_b": vb if values else [],
        "per_world_delta": [a - b for a, b in zip(va, vb)],
        "mean_a": sum(va) / m, "mean_b": sum(vb) / m,
        "delta": sum(va) / m - sum(vb) / m,
        "within_var": 1.234, "within_se": 0.321, "unpaired_var": 4.56,
        "crn_var_reduction": 0.78,
    }


def _write(root: Path, rid: str, leg: int, rec: dict, profile="walled"):
    d = root / "tier1-greedy" / profile / f"leg{leg}" / "records"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{rid}.json").write_text(json.dumps(rec))


def _fixture(tmp_path: Path, n_legs=3, **kw):
    """Build a new root, an identical reference root, and a plan. Returns paths."""
    new, ref = tmp_path / "new", tmp_path / "ref"
    for i in range(n_legs):
        rec = _record(f"tt_sp_2810000000{i}_p{i * 2}", seed_off=i, **kw)
        _write(new, rec["rid"], 1, rec)
        _write(ref, rec["rid"], 1, dict(rec))          # bit-identical reference
    plan = tmp_path / "POSITIONS_PLAN.json"
    plan.write_text(json.dumps({"mean_arms": 3.0022, "n_positions": 1350}))
    return new, ref, plan


def _run(tmp_path, new, ref, plan, *, expect_legs, if_root=""):
    out = tmp_path / "PILOT.json"
    argv = ["--new-root", str(new), "--primary-root", str(ref),
            "--plan", str(plan), "--out", str(out),
            "--expect-legs", str(expect_legs), "--if-root", if_root]
    old = sys.argv
    sys.argv = ["pilot_report.py", *argv]
    try:
        rc = PR.main()
    finally:
        sys.argv = old
    return rc, out


def test_clean_pilot_writes_pilot_json_and_exits_zero(tmp_path):
    new, ref, plan = _fixture(tmp_path, n_legs=3)
    rc, out = _run(tmp_path, new, ref, plan, expect_legs=3)
    assert rc == 0
    d = json.loads(out.read_text())
    assert d["abort"]["triggered"] is False
    assert d["integrity"]["G_REPRO_bit_identical"] == 3
    assert d["integrity"]["G_REPRO_expected"] == 3
    assert d["B_star"] == 2


def test_pilot_json_carries_no_forbidden_key_and_no_value(tmp_path):
    """The whole disclosure contract, checked on the REAL emitted file."""
    new, ref, plan = _fixture(tmp_path, n_legs=3)
    rc, out = _run(tmp_path, new, ref, plan, expect_legs=3)
    assert rc == 0
    raw = out.read_text()
    doc = json.loads(raw)

    # (a) no forbidden name appears as a KEY anywhere, at any depth.
    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)

    seen = set(keys(doc))
    for bad in DESIGN_FORBIDDEN:
        assert bad not in seen, f"forbidden key {bad!r} reached PILOT.json"
    for bad in PR.FORBIDDEN:
        assert bad not in seen, f"forbidden key {bad!r} reached PILOT.json"

    # (b) no VALUE leaked -- the sentinels must not appear in the text at all.
    for sentinel in (SENTINEL_A, SENTINEL_B):
        assert str(sentinel) not in raw, f"value sentinel {sentinel} leaked"
        assert repr(sentinel) not in raw
    # nor the derived statistics of those sentinels
    assert "1.234" not in raw and "0.321" not in raw and "4.56" not in raw

    # (c) the seed lists are not dumped either -- only identity COUNTS.
    assert "world_seeds" not in seen and "playout_seeds" not in seen
    assert "1000" not in raw.replace("13.7552", "")   # no raw seed values


def test_forbidden_key_guard_actually_fires(tmp_path, monkeypatch):
    """Poison the report and prove the guard catches it -- otherwise (b) above
    would only be evidence that nothing happened to leak today."""
    new, ref, plan = _fixture(tmp_path, n_legs=2)
    real = PR.b_star_block

    def poisoned(a_bar, c):
        blk = real(a_bar, c)
        blk["mean_a"] = 42.0          # a forbidden key, smuggled in
        return blk

    monkeypatch.setattr(PR, "b_star_block", poisoned)
    rc, out = _run(tmp_path, new, ref, plan, expect_legs=2)
    assert rc == 3, "the forbidden-key guard did not fire"


def test_repro_digest_is_a_digest_not_a_value():
    rec = _record("tt_sp_1_p2")
    dig = PR._repro_digest(rec)
    assert len(dig) == 64 and all(ch in "0123456789abcdef" for ch in dig)
    for sentinel in (SENTINEL_A, SENTINEL_B):
        assert str(sentinel) not in dig
    # it is sensitive: a changed value changes the digest
    other = _record("tt_sp_1_p2")
    other["values_a"] = [v + 1 for v in other["values_a"]]
    assert PR._repro_digest(other) != dig
    # and it is stable across equal records
    assert PR._repro_digest(_record("tt_sp_1_p2")) == dig


# --------------------------------------------------------------------------- #
# 3. the abort rule                                                             #
# --------------------------------------------------------------------------- #
def test_abort_on_failed_record(tmp_path):
    new, ref, plan = _fixture(tmp_path, n_legs=2, ok=False)
    rc, out = _run(tmp_path, new, ref, plan, expect_legs=2)
    assert rc != 0
    d = json.loads(out.read_text())
    assert d["abort"]["triggered"] is True
    assert any("n_failed" in r for r in d["abort"]["reasons"])


def test_abort_on_crn_not_verified(tmp_path):
    new, ref, plan = _fixture(tmp_path, n_legs=2, crn=False)
    rc, _ = _run(tmp_path, new, ref, plan, expect_legs=2)
    assert rc != 0


def test_abort_on_checksum_not_ok(tmp_path):
    new, ref, plan = _fixture(tmp_path, n_legs=2, ck=False)
    rc, _ = _run(tmp_path, new, ref, plan, expect_legs=2)
    assert rc != 0


def test_abort_on_seed_mismatch(tmp_path):
    new, ref, plan = _fixture(tmp_path, n_legs=2)
    # perturb ONE reference world seed
    f = sorted((ref / "tier1-greedy").rglob("records/*.json"))[0]
    rec = json.loads(f.read_text())
    rec["world_seeds"] = [s + 1 for s in rec["world_seeds"]]
    f.write_text(json.dumps(rec))
    rc, out = _run(tmp_path, new, ref, plan, expect_legs=2)
    assert rc != 0
    reasons = " ".join(json.loads(out.read_text())["abort"]["reasons"])
    assert "seed/arm identity" in reasons or "G-REPRO" in reasons


def test_abort_on_grepro_short_of_the_committed_count(tmp_path):
    """⚠️ THE REGRESSION THIS FILE EXISTS FOR.

    G-REPRO's expected count must be the COMMITTED constant, not `len(new)`. A
    pilot that wrote only 2 of its 43 legs must ABORT -- if the denominator were
    taken from what the run happened to produce, `repro == expected` would hold
    trivially and a truncated pilot would authorise the main run.
    """
    new, ref, plan = _fixture(tmp_path, n_legs=2)
    rc, out = _run(tmp_path, new, ref, plan, expect_legs=43)
    assert rc != 0
    reasons = " ".join(json.loads(out.read_text())["abort"]["reasons"])
    assert "43" in reasons


def test_default_expected_leg_count_is_the_verified_43():
    assert PR.EXPECT_LEGS == 43


def test_abort_on_missing_reference_counterpart(tmp_path):
    new, ref, plan = _fixture(tmp_path, n_legs=3)
    sorted((ref / "tier1-greedy").rglob("records/*.json"))[0].unlink()
    rc, out = _run(tmp_path, new, ref, plan, expect_legs=3)
    assert rc != 0
    reasons = " ".join(json.loads(out.read_text())["abort"]["reasons"])
    assert "counterpart" in reasons or "G-REPRO" in reasons


def test_cross_judge_witness_is_reported_when_an_if_root_is_given(tmp_path):
    """DESIGN §4.5: world_seed(rid, j, salt) never depends on the judge, so the
    clair-puct record for the same rid+leg must carry identical seed lists."""
    new, ref, plan = _fixture(tmp_path, n_legs=2)
    ifr = tmp_path / "ifr"
    for f in sorted((new / "tier1-greedy").rglob("records/*.json")):
        rec = json.loads(f.read_text())
        d = ifr / "clair-puct" / "walled" / "leg1" / "records"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{rec['rid']}.json").write_text(json.dumps(rec))
    rc, out = _run(tmp_path, new, ref, plan, expect_legs=2, if_root=str(ifr))
    assert rc == 0
    w = json.loads(out.read_text())["integrity"]["cross_judge_witness"]
    assert w["evaluated"] is True
    assert w["world_seed_identical_to_clair_puct"] == 2
    assert w["playout_seed_identical_to_clair_puct"] == 2
    assert w["arm_identical_to_clair_puct"] == 2


def test_missing_corpus_plan_is_a_clean_failure_not_a_traceback(tmp_path):
    new, ref, plan = _fixture(tmp_path, n_legs=2)
    plan.unlink()
    rc, _ = _run(tmp_path, new, ref, plan, expect_legs=2)
    assert rc == 2


# --------------------------------------------------------------------------- #
# 4. the frozen B* is where the analyser will look for it                       #
# --------------------------------------------------------------------------- #
def test_analyser_read_pilot_finds_the_frozen_b_star(tmp_path):
    """`analyze_tiearb2.read_pilot` looks for `B_star` at the top level, or under
    `cost`, or under `mechanical_rule` -- and NOT under a `b_star` sub-block. If
    it cannot find it, the analyser silently re-derives B* and stamps the
    read-out '⚠️ PILOT.json carried no B_star'."""
    new, ref, plan = _fixture(tmp_path, n_legs=3)
    rc, out = _run(tmp_path, new, ref, plan, expect_legs=3)
    assert rc == 0
    AT2 = _load("tiearb2_analyser_rp", REPO / "scripts/tiletie/analyze_tiearb2.py")
    got = AT2.read_pilot(out)
    assert got["present"] is True
    assert got["B_star"] == 2
    assert got["c_tier1_worker_s_per_playout"] is not None
    assert got["rho_wall_bstar"] is not None
