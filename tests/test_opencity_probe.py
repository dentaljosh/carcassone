"""`chain_capability_probe.py --require opencity` — the launch blocker for any
open-city cell (measurement/opencity_term_20260812/CALIB_READ_RULE.md §4:
"Stale-wheel capability probe is a launch blocker, not a nicety").

WHAT FAILURE THIS GUARDS. `rust_agent.leaf_config_rs` forwards the four
`opencity_*` kwargs to `carc_rs.LeafConfigRs` ONLY when the dose is nonzero,
precisely so a wheel built before the term raises `TypeError` instead of quietly
serving a default-off leaf. That is fail-closed — but only if something actually
calls it before the cell starts. A launcher that swallowed the `TypeError`, or a
box whose wheel was never rebuilt, would run a candidate arm that IS the champion:
the cell completes, writes a clean manifest, and reads a perfect null. Nothing in
the output would say so. Every test here exists to make that outcome impossible to
reach quietly.

The probe is therefore checked on three axes, and this module covers all three:

  1. STRUCTURE  — the knobs exist on `LeafConfig`, the candidate leaf hash MOVES off
                  `a36d2e15a3b3d71d`, thresholds are validated (`--no-runtime-probe`).
  2. RUNTIME    — the LOADED `carc_rs` accepts the kwargs and exposes `opencity_term`.
  3. FUNCTION   — the dose CHANGES the leaf value, and the dose-0 identity cell is
                  BIT-EXACT on BOTH leaves (rust and python). (1) and (2) are
                  structure; only (3) excludes "accepted and ignored".

⚠️ ARM C IS EXPECTED TO FAIL (3), AND THAT IS NOT A BUG. TERM_SPEC §6 measured the
`(size_min=6, edge_min=3)` predicate firing on 0.0% of golden-corpus leaf values.
The probe is deliberately NOT special-cased for it — a tight arm that never fires
and a stale wheel are indistinguishable *to the probe*, so it reports the failure
and lets the caller decide. `run_calib_laptop.sh` gates on arms A and B only, for
exactly this reason. The tests below pin the DISCRIMINATOR: even for arm C, the
dose-0 and identity-control checks must still pass, which is what separates
"this arm's predicate never fires" from "this build has no term".

Nothing here plays a game, claims a band, ssh's anywhere, or writes governance.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CS = REPO / "scripts" / "classical_search"
sys.path.insert(0, str(CS))

import chain_capability_probe as probe          # noqa: E402

CHAMP = "a36d2e15a3b3d71d"
PROBE_PY = CS / "chain_capability_probe.py"

# The CALIB_READ_RULE §1 ladder: three threshold arms x two doses. Held symmetric.
ARM_A = (4.0, 2)      # production spec
ARM_B = (3.0, 2)      # loose
ARM_C = (6.0, 3)      # tight — TERM_SPEC §6 measured 0.0% bite
DOSES = "0.5,2.0"

# The launcher env canon (scripts/classical_search/denial_simsplit_chain.sh). It must be
# exported BEFORE the interpreter starts: DEFAULT_CONFIG is resolved at
# virtual_score_v2 import time, so a test that set it in-process would be too late.
# This is also why every probe test here is a SUBPROCESS rather than an in-process call.
CHAMP_ENV = {
    "CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-10,-5,-1.25,0,2.5,3.75,5,6.25",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_USE_FLAT_LEAF": "1", "CARCASSONNE_USE_CY_REPR": "1",
    "CARCASSONNE_USE_CY_LEAF": "1", "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1", "CARCASSONNE_FIX_R9": "1",
}


def _run(args, tmp_path=None, timeout=600):
    """Run the probe CLI under the champion env canon. Returns (rc, report|None)."""
    env = dict(os.environ)
    env.update(CHAMP_ENV)
    out = None
    if tmp_path is not None:
        out = Path(tmp_path) / "probe.json"
        args = [*args, "--json-out", str(out)]
    p = subprocess.run([sys.executable, str(PROBE_PY), *args],
                       capture_output=True, text=True, timeout=timeout, env=env)
    rep = None
    if out is not None and out.exists():
        rep = json.loads(out.read_text())
    elif p.stdout.strip():
        try:
            rep = json.loads(p.stdout)
        except json.JSONDecodeError:                                  # pragma: no cover
            rep = None
    return p.returncode, rep


def _checks(rep):
    return {c["check"]: c for c in rep["checks"]}


def _arm_args(arm, *, runtime, doses=DOSES):
    size_min, edge_min = arm
    a = ["--require", "opencity", "--doses", doses,
         "--size-min", str(size_min), "--edge-min", str(edge_min)]
    if not runtime:
        a.append("--no-runtime-probe")
    return a


def _carc_rs_has_term():
    """True iff the LOADED build carries the term. This is the exact discriminator the
    probe's own fail-closed seam uses, so the skip can never mask a real regression."""
    try:
        import carc_rs
    except Exception:
        return False
    try:
        carc_rs.LeafConfigRs([(1, 0.5)], 8., 8., opencity_dose=1.0, opencity_size_min=4.0,
                             opencity_edge_min=2, opencity_symmetric=True)
    except TypeError:
        return False
    except Exception:                                                 # pragma: no cover
        return False
    return True


needs_term = pytest.mark.skipif(
    not _carc_rs_has_term(),
    reason="stale carc_rs: the loaded build predates the open-city term "
           "(rebuild: maturin build --release -m rust/carc/carc-py/Cargo.toml)")


# --------------------------------------------------------------------------- #
# Pure helpers — no env, no carc_rs, no DEFAULT_CONFIG                         #
# --------------------------------------------------------------------------- #
def test_cand_leaf_spec_always_writes_all_four_knobs():
    """Self-describing cell JSON: a default that is merely IMPLIED is a cell nobody can
    reconstruct from disk six weeks later."""
    spec = probe.opencity_cand_leaf_spec(0.5, 4.0, 2, True)
    assert set(spec) == {"opencity_dose", "opencity_size_min",
                         "opencity_edge_min", "opencity_symmetric"}
    assert spec["opencity_dose"] == 0.5
    assert spec["opencity_size_min"] == 4.0          # TILES, not points
    assert spec["opencity_edge_min"] == 2
    assert spec["opencity_symmetric"] is True
    assert isinstance(spec["opencity_edge_min"], int)


def test_cand_leaf_spec_round_trips_through_json():
    spec = probe.opencity_cand_leaf_spec(2.0, 3.0, 2, False)
    assert json.loads(json.dumps(spec)) == spec


@pytest.mark.parametrize("edge_min", [0, -1, -5])
def test_cand_leaf_spec_refuses_edge_min_below_one(edge_min):
    """`open_n >= edge_min` with edge_min < 1 prices EVERY incomplete city — a different
    term (TERM_SPEC §5), and c5_leaf_override raises on it, so the cell could never run."""
    with pytest.raises(ValueError, match="edge_min"):
        probe.opencity_cand_leaf_spec(0.5, 4.0, edge_min, True)


@pytest.mark.parametrize("size_min", [0.0, 0.5, -3.0])
def test_cand_leaf_spec_refuses_size_min_below_one_tile(size_min):
    with pytest.raises(ValueError, match="size_min"):
        probe.opencity_cand_leaf_spec(0.5, size_min, 2, True)


def test_cell_tags_are_unique_across_the_six_preregistered_cells():
    """Two cells must never share a directory: the six-cell ladder is three threshold arms
    x two doses, and a tag collision would silently overwrite one cell with another."""
    tags = [probe.opencity_cell_tag(d, s, e, True)
            for (s, e) in (ARM_A, ARM_B, ARM_C) for d in (0.5, 2.0)]
    assert len(set(tags)) == 6, tags


def test_cell_tag_separates_the_symmetry_flag():
    """opencity_symmetric=False is a DIFFERENT TERM (TERM_SPEC §3), not a rung — so it may
    never collide with its symmetric twin."""
    sym = probe.opencity_cell_tag(0.5, 4.0, 2, True)
    asym = probe.opencity_cell_tag(0.5, 4.0, 2, False)
    assert sym != asym
    assert sym.endswith("sym") and asym.endswith("asym")


def test_cell_tag_carries_both_thresholds():
    tag = probe.opencity_cell_tag(0.5, 4.0, 2, True)
    assert "d0p5" in tag and "t4" in tag and "e2" in tag


def test_opencity_tag_cannot_be_confused_with_a_denial_tag():
    """The two terms' size axes are in DIFFERENT UNITS (tiles vs points). Distinct prefixes
    are what stops a reader carrying a threshold across."""
    assert not probe.opencity_cell_tag(1.0, 5.0, 2, True).startswith("d1_denial")
    assert probe.cell_tag(1.0, 5.0, 2).startswith("d1_denial")


def test_parse_doses_still_refuses_the_identity_dose():
    """Dose 0.0 IS the champion leaf. The hash gate cannot catch an accidentally-zeroed
    dose (see test_dose0_identity_hash_is_reported_not_assumed), so this refusal is the
    only gate that does."""
    with pytest.raises(ValueError, match="IDENTITY"):
        probe.parse_doses("0.0")
    with pytest.raises(ValueError, match="IDENTITY"):
        probe.parse_doses("0.5,0.0")


def test_d0_identity_constant_moves_every_threshold():
    """The point of the identity cell is that the dose gate holds even with the OTHER three
    knobs moved. If it stopped moving them, the control would prove nothing."""
    d0 = probe.OPENCITY_D0_IDENTITY
    assert d0["opencity_dose"] == 0.0
    assert d0["opencity_size_min"] != 4.0
    assert d0["opencity_edge_min"] != 2
    assert d0["opencity_symmetric"] is False


# --------------------------------------------------------------------------- #
# Structure — --no-runtime-probe (no carc_rs, no playouts)                     #
# --------------------------------------------------------------------------- #
def test_structural_probe_passes_and_moves_every_cand_hash(tmp_path):
    rc, rep = _run(_arm_args(ARM_A, runtime=False), tmp_path)
    assert rc == 0, rep
    assert rep["ok"] is True
    assert rep["champ_leaf_hash"] == CHAMP
    ch = _checks(rep)
    assert ch["py_leafconfig_fields"]["ok"]
    assert ch["py_flat_opencity_term"]["ok"]
    assert ch["env_is_champion_leaf"]["ok"]
    assert len(rep["cells"]) == 2
    hashes = {c["cand_leaf_hash"] for c in rep["cells"]}
    assert CHAMP not in hashes
    assert len(hashes) == 2
    assert any(k.startswith("cand_hash_moves[") for k in ch)
    assert all(v["ok"] for k, v in ch.items() if k.startswith("cand_hash_"))
    assert "SKIPPED" in rep["runtime_probe"]


def test_every_preregistered_arm_is_structurally_fundable(tmp_path):
    """All six cells must produce distinct candidate leaves — including arm C, whose
    predicate never fires. A cell that cannot even be CONSTRUCTED is a different failure
    from one that constructs and never bites, and the calibration must be able to tell
    them apart."""
    seen = {}
    for name, arm in (("A", ARM_A), ("B", ARM_B), ("C", ARM_C)):
        rc, rep = _run(_arm_args(arm, runtime=False), tmp_path / name)
        assert rc == 0, (name, rep)
        for c in rep["cells"]:
            assert c["cand_leaf_hash"] != CHAMP
            seen[c["cand_leaf_hash"]] = c["tag"]
    assert len(seen) == 6, seen


def test_dose0_identity_hash_is_reported_not_assumed(tmp_path):
    """A load-bearing negative result, pinned so nobody later 'fixes' it into an assertion.

    All four knobs sit in `_LEAF_HASH_EXCLUDE_IF_DEFAULT`, but a field is dropped only
    while it holds its DEFAULT value — and the identity cell deliberately moves three of
    them. So the dose-0 cell does NOT hash as the champion, which means the
    `cand_hash_moves` gate would happily pass a cell whose dose had been accidentally
    zeroed. That is exactly why `parse_doses` refuses 0.0."""
    rc, rep = _run(_arm_args(ARM_A, runtime=False), tmp_path)
    assert rc == 0
    d0 = rep["dose0_identity"]
    assert d0["leaf_hash"] != CHAMP
    assert d0["hash_equals_champion"] is False
    assert "cannot catch" in d0["note"]


@pytest.mark.parametrize("args,why", [
    (["--require", "opencity", "--doses", DOSES, "--size-min", "4"],
     "missing --edge-min"),
    (["--require", "opencity", "--doses", DOSES, "--edge-min", "2"],
     "missing --size-min"),
    (["--require", "opencity", "--size-min", "4", "--edge-min", "2"],
     "missing --doses"),
    (["--require", "opencity", "--doses", "0.0", "--size-min", "4", "--edge-min", "2"],
     "dose 0.0 is the identity control"),
    (["--require", "opencity", "--doses", DOSES, "--size-min", "4", "--edge-min", "0"],
     "edge_min < 1"),
])
def test_bad_arguments_exit_7_with_a_report_not_a_traceback(args, why, tmp_path):
    """Exit 7 is the chain's 'refuse to launch' code. A traceback (exit 1) or a silent 0
    would both be read by a launcher as something other than 'do not start this cell'."""
    rc, rep = _run([*args, "--no-runtime-probe"], tmp_path)
    assert rc == 7, why
    assert rep is not None and rep["ok"] is False
    assert any(not c["ok"] for c in rep["checks"]), why


def test_denial_mode_is_unregressed(tmp_path):
    """The opencity mode is ADDITIVE. The denial chain is still armed in cron."""
    rc, rep = _run(["--require", "denial", "--doses", "1.0", "--size-min", "5",
                    "--open-max", "3", "--no-runtime-probe"], tmp_path)
    assert rc == 0, rep
    assert rep["capability"] == "denial"
    assert rep["ok"] is True


def test_cells_out_tsv_is_written_for_opencity(tmp_path):
    """The per-box launchers read exactly this file; denial's mode writes it and opencity's
    must too, or a launcher silently gets an empty cell list."""
    cells = tmp_path / "cells.tsv"
    rc, _ = _run([*_arm_args(ARM_A, runtime=False), "--cells-out", str(cells)], tmp_path)
    assert rc == 0
    rows = [r for r in cells.read_text().splitlines() if r.strip()]
    assert len(rows) == 2
    for r in rows:
        tag, cand_json, cand_hash = r.split("\t")
        assert tag.startswith("oc_")
        assert json.loads(cand_json)["opencity_dose"] > 0
        assert cand_hash != CHAMP


# --------------------------------------------------------------------------- #
# Runtime + functional — the stale-wheel trap itself                           #
# --------------------------------------------------------------------------- #
@needs_term
def test_runtime_probe_passes_on_the_spec_arm(tmp_path):
    rc, rep = _run(_arm_args(ARM_A, runtime=True), tmp_path)
    assert rc == 0, rep
    ch = _checks(rep)
    assert ch["carc_rs_accepts_opencity_kwargs"]["ok"]
    assert ch["carc_rs_exposes_opencity_term"]["ok"]
    assert ch["carc_rs_opencity_changes_leaf"]["ok"]
    assert ch["carc_rs_identity_control"]["ok"]
    assert rep["functional"]["values_moved"] > 0
    assert rep["functional"]["identity_control_breaks"] == 0


@needs_term
def test_dose0_is_bit_exact_on_BOTH_leaves(tmp_path):
    """The task's core requirement. `opencity_dose` gates the whole term, so the identity
    cell — dose 0 with all three other knobs MOVED — must be bit-identical to the champion
    on the rust leaf AND the python leaf. If the gate leaked, every rung of a dose ladder
    would be a mixture of a dose effect and a threshold effect."""
    rc, rep = _run(_arm_args(ARM_A, runtime=True), tmp_path)
    assert rc == 0, rep
    f = rep["functional"]
    ch = _checks(rep)
    assert ch["carc_rs_dose0_bit_exact"]["ok"]
    assert ch["py_dose0_bit_exact"]["ok"]
    assert f["rs_dose0_values_compared"] > 0 and f["rs_dose0_breaks"] == 0
    assert f["py_dose0_values_compared"] > 0 and f["py_dose0_breaks"] == 0


@needs_term
def test_both_leaves_accept_the_knobs_and_agree_on_the_bite(tmp_path):
    """Rust and python are bit-exact mirrors (reconcile_leaf --configs opencity), so the
    two independently-sampled 'values moved' counts must agree. A divergence here means one
    leaf got the knobs and the other did not — the exact half-wired state that would make a
    cell's candidate arm depend on which backend a worker happened to load."""
    rc, rep = _run(_arm_args(ARM_A, runtime=True), tmp_path)
    assert rc == 0, rep
    f = rep["functional"]
    assert f["py_values_moved"] == f["values_moved"]
    assert f["py_values_same"] == f["values_same"]


@needs_term
def test_arm_C_reads_zero_bite_and_says_so_rather_than_passing(tmp_path):
    """TERM_SPEC §6 measured the (6 tiles, 3 edges) predicate firing on 0.0% of
    golden-corpus leaf values, and the probe reproduces that here on scripted playouts.

    Two properties are pinned, and the second is the important one:
      (a) the probe FAILS (rc 7) rather than reporting a green cell whose candidate arm is
          operationally the champion — it is deliberately not special-cased for arm C;
      (b) the failure is CONFINED to the two *_changes_leaf checks. The dose-0 and
          identity-control checks still pass, which is precisely what distinguishes 'this
          arm's predicate never fires' from 'this build has no term'. A stale wheel could
          not produce this signature: it would fail carc_rs_accepts_opencity_kwargs first
          and return before any playout ran.

    This is why run_calib_laptop.sh gates on arms A and B and merely REPORTS arm C."""
    rc, rep = _run(_arm_args(ARM_C, runtime=True), tmp_path)
    assert rc == 7, rep
    ch = _checks(rep)
    failed = {k for k, v in ch.items() if not v["ok"]}
    assert failed == {"carc_rs_opencity_changes_leaf", "py_opencity_changes_leaf"}, failed
    assert ch["carc_rs_accepts_opencity_kwargs"]["ok"]
    assert ch["carc_rs_exposes_opencity_term"]["ok"]
    assert ch["carc_rs_dose0_bit_exact"]["ok"]
    assert ch["py_dose0_bit_exact"]["ok"]
    assert rep["functional"]["values_moved"] == 0
    assert rep["functional"]["py_values_moved"] == 0


@needs_term
def test_loose_arm_bites_harder_than_the_spec_arm(tmp_path):
    """The ladder's SHAPE, measured rather than assumed: widening the predicate (B: 3 tiles
    vs A: 4) can only add qualifying cities, never remove one. Monotonicity is a property
    of the term itself, so a violation means the thresholds are not doing what §2 says."""
    _, rep_a = _run(_arm_args(ARM_A, runtime=True), tmp_path / "a")
    _, rep_b = _run(_arm_args(ARM_B, runtime=True), tmp_path / "b")
    assert rep_b["functional"]["values_moved"] >= rep_a["functional"]["values_moved"] > 0
