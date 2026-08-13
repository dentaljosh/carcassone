"""`chain_capability_probe.py --require jrules` — the launch blocker for any
J-rules-on-search cell (`measurement/jrules_on_search_20260813/DESIGN.md` §11 **G4**).

Sibling of `tests/test_opencity_probe.py`, same three axes, same subprocess style;
the term-level contracts live next door in `tests/test_jrules_term.py`.

WHAT FAILURE THIS GUARDS. `rust_agent.leaf_config_rs` forwards the two `jrules_*`
kwargs to `carc_rs.LeafConfigRs` ONLY when the dose is nonzero, precisely so a wheel
built before the bundle raises `TypeError` instead of quietly serving a default-off
leaf. That is fail-closed — but only if something actually calls it before the cell
starts. A launcher that swallowed the `TypeError`, or a box whose wheel was never
rebuilt, would run a candidate arm that IS the champion: the cell completes, writes a
clean manifest, and reads a perfect null. For THIS term that null has a second, worse
reading available — "the anchor's self-described strategy is worth nothing" instead of
"his strategy never ran" — which is exactly the misreading the whole build exists to
prevent. Every test here exists to make that outcome impossible to reach quietly.

  1. STRUCTURE  — the knobs exist on `LeafConfig`, the rule bits are unmoved, the
                  candidate hashes MOVE off `a36d2e15a3b3d71d` **and match DESIGN §9's
                  pre-registered values**, bad masks are refused (`--no-runtime-probe`).
  2. RUNTIME    — the LOADED `carc_rs` accepts the kwargs and exposes `jrules_term`;
                  a STALE build makes the probe exit 7 before any playout runs
                  (simulated here, so the guard is tested on a rebuilt box too).
  3. FUNCTION   — the dose CHANGES the leaf value, and the dose-0 identity cell (dose
                  off, `jrules_mask` MOVED to 27) is BIT-EXACT on BOTH leaves. (1) and
                  (2) are structure; only (3) excludes "accepted and ignored".

Two jrules-only differences from the open-city mode, both deliberate:
  * `--doses` DEFAULTS to DESIGN §7's pre-registered ladder `{0.5, 1.0, 2.0}` — that
    ladder was written down, with its FUND-SMALLEST read-rule, before any number was
    read, so unlike an open-city threshold arm it cannot smuggle in an unregistered cell;
  * the moved knob in the identity control is the `jrules_mask`, not a threshold.

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

# DESIGN §7's ladder and §9's published hashes — the primary cell is mask 31 (JR_ALL).
LADDER = (0.5, 1.0, 2.0)
JR_ALL = 31
MASK_NO_J5 = 27          # JR_ALL minus JR_J5: the identity control's MOVED knob

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


def _run(args, tmp_path=None, timeout=600, extra_env=None):
    """Run the probe CLI under the champion env canon. Returns (rc, report|None)."""
    env = dict(os.environ)
    env.update(CHAMP_ENV)
    env.update(extra_env or {})
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


def _args(*, runtime, doses=None, mask=None):
    a = ["--require", "jrules"]
    if doses is not None:
        a += ["--doses", doses]
    if mask is not None:
        a += ["--mask", str(mask)]
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
        carc_rs.LeafConfigRs([(1, 0.5)], 8., 8., jrules_dose=1.0, jrules_mask=31)
    except TypeError:
        return False
    except Exception:                                                 # pragma: no cover
        return False
    return True


needs_term = pytest.mark.skipif(
    not _carc_rs_has_term(),
    reason="stale carc_rs: the loaded build predates the J-rules term "
           "(rebuild: maturin build --release -m rust/carc/carc-py/Cargo.toml)")


# --------------------------------------------------------------------------- #
# Pure helpers — no env, no carc_rs, no DEFAULT_CONFIG                         #
# --------------------------------------------------------------------------- #
def test_cand_leaf_spec_always_writes_both_knobs():
    """Self-describing cell JSON: a default that is merely IMPLIED is a cell nobody can
    reconstruct from disk six weeks later. (An explicit mask 31 hashes identically to an
    omitted one — the field is excluded-if-default — which is what lets DESIGN §8's O4'
    and this rule coexist; test_preregistered_hashes_reproduce_on_this_box pins it.)"""
    spec = probe.jrules_cand_leaf_spec(1.0, JR_ALL)
    assert set(spec) == {"jrules_dose", "jrules_mask"}
    assert spec["jrules_dose"] == 1.0
    assert spec["jrules_mask"] == JR_ALL
    assert isinstance(spec["jrules_mask"], int)


def test_cand_leaf_spec_round_trips_through_json():
    spec = probe.jrules_cand_leaf_spec(0.5, MASK_NO_J5)
    assert json.loads(json.dumps(spec)) == spec


@pytest.mark.parametrize("mask", [0, -1, -31])
def test_cand_leaf_spec_refuses_a_mask_that_selects_no_rule(mask):
    """Mask 0 makes the bundle identically zero: the candidate arm IS the champion while
    still hashing differently, so `cand_hash_moves` cannot catch it. Refuse at argument
    time rather than 40 minutes into a cell."""
    with pytest.raises(ValueError, match="at least one rule"):
        probe.jrules_cand_leaf_spec(1.0, mask)


@pytest.mark.parametrize("mask", [32, 63, 255])
def test_cand_leaf_spec_refuses_bits_no_rule_defines(mask):
    """Both leaves mask with `&`, so a bit above JR_ALL is SILENTLY DROPPED — the cell
    would run as `mask & 31` while its JSON claims otherwise. A typo, not a cell."""
    with pytest.raises(ValueError, match="JR_ALL"):
        probe.jrules_cand_leaf_spec(1.0, mask)


def test_cell_tags_are_unique_across_the_ladder_and_carry_the_mask():
    """A mask ablation at the same dose is a DIFFERENT candidate leaf, not a rung — so it
    may never share a directory with the primary cell."""
    tags = [probe.jrules_cell_tag(d, m) for m in (JR_ALL, MASK_NO_J5) for d in LADDER]
    assert len(set(tags)) == 6, tags
    assert probe.jrules_cell_tag(1.0, JR_ALL) != probe.jrules_cell_tag(1.0, MASK_NO_J5)
    assert "d0p5" in probe.jrules_cell_tag(0.5, JR_ALL)
    assert "m31" in probe.jrules_cell_tag(0.5, JR_ALL)


def test_jrules_tag_cannot_be_confused_with_a_denial_or_opencity_tag():
    """Three terms, three prefixes. Distinct stems are what stop a reader carrying a dose
    across — and these doses mean different things: jrules is ADDED, the other two are
    SUBTRACTED."""
    tag = probe.jrules_cell_tag(1.0, JR_ALL)
    assert tag.startswith("jr_")
    assert not tag.startswith("d1_denial") and not tag.startswith("oc_")


def test_default_ladder_is_the_preregistered_one():
    """The one mode with a defaulted dose list. It is only defensible while the default IS
    DESIGN §7's ladder, so pin it — and pin that §9's hash table covers exactly it."""
    assert probe.parse_doses(probe.JRULES_LADDER) == list(LADDER)
    assert set(probe.JRULES_PREREGISTERED_HASHES) == set(LADDER)


def test_parse_doses_still_refuses_the_identity_dose():
    """Dose 0.0 IS the champion leaf. The hash gate cannot catch an accidentally-zeroed
    dose (see test_dose0_identity_hash_is_reported_not_assumed), so this refusal is the
    only gate that does."""
    with pytest.raises(ValueError, match="IDENTITY"):
        probe.parse_doses("0.0")
    with pytest.raises(ValueError, match="IDENTITY"):
        probe.parse_doses("0.5,0.0")


def test_d0_identity_constant_moves_the_mask():
    """The point of the identity cell is that the dose gate holds even with the OTHER knob
    moved. If it stopped moving it, the control would prove nothing."""
    d0 = probe.JRULES_D0_IDENTITY
    assert d0["jrules_dose"] == 0.0
    assert d0["jrules_mask"] == MASK_NO_J5 != JR_ALL
    assert d0["jrules_mask"] == probe.JR_ALL - probe.JR_J5      # J5 is the dropped rule


# --------------------------------------------------------------------------- #
# Structure — --no-runtime-probe (no carc_rs, no playouts)                     #
# --------------------------------------------------------------------------- #
def test_structural_probe_passes_and_moves_every_cand_hash(tmp_path):
    rc, rep = _run(_args(runtime=False), tmp_path)
    assert rc == 0, rep
    assert rep["ok"] is True
    assert rep["champ_leaf_hash"] == CHAMP
    ch = _checks(rep)
    assert ch["py_leafconfig_fields"]["ok"]
    assert ch["py_flat_jrules_term"]["ok"]
    assert ch["py_rule_bits_unmoved"]["ok"]
    assert ch["env_is_champion_leaf"]["ok"]
    assert len(rep["cells"]) == 3
    hashes = {c["cand_leaf_hash"] for c in rep["cells"]}
    assert CHAMP not in hashes
    assert len(hashes) == 3
    assert all(v["ok"] for k, v in ch.items() if k.startswith("cand_hash_"))
    assert "DESIGN" in rep["doses_source"]
    assert "SKIPPED" in rep["runtime_probe"]


def test_preregistered_hashes_reproduce_on_this_box(tmp_path):
    """DESIGN §9 published a `cand_leaf_hash` per rung. Recomputing them here is strictly
    stronger than `cand_hash_moves`: it proves the env canon AND the spec construction
    together reproduce the number the design committed to — pre-flight item 4 of §9."""
    rc, rep = _run(_args(runtime=False), tmp_path)
    assert rc == 0, rep
    got = {c["dose"]: c["cand_leaf_hash"] for c in rep["cells"]}
    assert got == {0.5: "46a7652670123027", 1.0: "a87fb6801b81d588",
                   2.0: "56db6c2247dee55f"}
    ch = _checks(rep)
    assert all(ch[f"cand_hash_preregistered[{c['tag']}]"]["ok"] for c in rep["cells"])


def test_an_ablation_mask_is_not_graded_against_the_primary_cells_hashes(tmp_path):
    """§9's table is for the mask-31 primary cell only. A mask ablation is a legitimate,
    different leaf — it must pass, with no pre-registered hash claimed for it."""
    rc, rep = _run(_args(runtime=False, doses="1.0", mask=MASK_NO_J5), tmp_path)
    assert rc == 0, rep
    (cell,) = rep["cells"]
    assert cell["preregistered_hash"] is None
    assert cell["cand_leaf_hash"] not in {CHAMP, "a87fb6801b81d588"}
    assert not any(k.startswith("cand_hash_preregistered[") for k in _checks(rep))


def test_dose0_identity_hash_is_reported_not_assumed(tmp_path):
    """A load-bearing negative result, pinned so nobody later 'fixes' it into an assertion.

    Both knobs sit in `_LEAF_HASH_EXCLUDE_IF_DEFAULT`, but a field is dropped only while
    it holds its DEFAULT value — and the identity cell deliberately moves the mask. So the
    dose-0 cell does NOT hash as the champion, which means the `cand_hash_moves` gate
    would happily pass a cell whose dose had been accidentally zeroed. That is exactly why
    `parse_doses` refuses 0.0."""
    rc, rep = _run(_args(runtime=False), tmp_path)
    assert rc == 0
    d0 = rep["dose0_identity"]
    assert json.loads(d0["cand_leaf_json"]) == {"jrules_dose": 0.0, "jrules_mask": 27}
    assert d0["leaf_hash"] != CHAMP
    assert d0["hash_equals_champion"] is False
    assert "cannot catch" in d0["note"]


@pytest.mark.parametrize("args,why", [
    (["--require", "jrules", "--doses", "0.0"], "dose 0.0 is the identity control"),
    (["--require", "jrules", "--doses", "1.0", "--mask", "0"], "mask selects no rule"),
    (["--require", "jrules", "--doses", "1.0", "--mask", "63"], "mask above JR_ALL"),
    (["--require", "jrules", "--doses", "-1.0"], "negative dose"),
    (["--require", "jrules", "--doses", "0.5,0.5"], "duplicate dose"),
])
def test_bad_arguments_exit_7_with_a_report_not_a_traceback(args, why, tmp_path):
    """Exit 7 is the chain's 'refuse to launch' code. A traceback (exit 1) or a silent 0
    would both be read by a launcher as something other than 'do not start this cell'."""
    rc, rep = _run([*args, "--no-runtime-probe"], tmp_path)
    assert rc == 7, why
    assert rep is not None and rep["ok"] is False
    assert any(not c["ok"] for c in rep["checks"]), why


def test_a_mangled_env_canon_fails_rather_than_measuring_something_else(tmp_path):
    """`DEFAULT_CONFIG` is resolved at import time, so the probe's champion-hash assert is
    what proves the CALLER's env is the champion's. Knock one knob off and the probe must
    refuse — a cell launched from that shell would grade a candidate against a leaf that
    is not the champion."""
    rc, rep = _run(_args(runtime=False), tmp_path,
                   extra_env={"CARCASSONNE_V25_MEEPLE_K": "0.0"})
    assert rc == 7
    assert _checks(rep)["env_is_champion_leaf"]["ok"] is False


def test_denial_and_opencity_modes_are_unregressed(tmp_path):
    """The jrules mode is ADDITIVE. The denial chain is still armed in cron and the
    open-city calibration still reads this same script."""
    rc, rep = _run(["--require", "denial", "--doses", "1.0", "--size-min", "5",
                    "--open-max", "3", "--no-runtime-probe"], tmp_path / "d")
    assert rc == 0 and rep["capability"] == "denial" and rep["ok"] is True
    rc, rep = _run(["--require", "opencity", "--doses", "0.5,2.0", "--size-min", "4",
                    "--edge-min", "2", "--no-runtime-probe"], tmp_path / "o")
    assert rc == 0 and rep["capability"] == "opencity" and rep["ok"] is True


def test_cells_out_tsv_is_written_for_jrules(tmp_path):
    """The per-box launchers read exactly this file; denial's and opencity's modes write
    it and jrules' must too, or a launcher silently gets an empty cell list."""
    cells = tmp_path / "cells.tsv"
    rc, _ = _run([*_args(runtime=False), "--cells-out", str(cells)], tmp_path)
    assert rc == 0
    rows = [r for r in cells.read_text().splitlines() if r.strip()]
    assert len(rows) == 3
    for r in rows:
        tag, cand_json, cand_hash = r.split("\t")
        assert tag.startswith("jr_")
        spec = json.loads(cand_json)
        assert spec["jrules_dose"] > 0 and spec["jrules_mask"] == JR_ALL
        assert cand_hash != CHAMP


# --------------------------------------------------------------------------- #
# Runtime + functional — the stale-wheel trap itself                           #
# --------------------------------------------------------------------------- #
@needs_term
def test_runtime_probe_passes_on_the_preregistered_ladder(tmp_path):
    rc, rep = _run(_args(runtime=True), tmp_path)
    assert rc == 0, rep
    ch = _checks(rep)
    assert ch["carc_rs_accepts_jrules_kwargs"]["ok"]
    assert ch["carc_rs_exposes_jrules_term"]["ok"]
    assert ch["carc_rs_jrules_changes_leaf"]["ok"]
    assert ch["carc_rs_identity_control"]["ok"]
    assert rep["functional"]["values_moved"] > 0
    assert rep["functional"]["identity_control_breaks"] == 0


@needs_term
def test_dose0_is_bit_exact_on_BOTH_leaves(tmp_path):
    """The core requirement. `jrules_dose` gates the whole bundle, so the identity cell —
    dose 0 with the mask MOVED to 27 — must be bit-identical to the champion on the rust
    leaf AND the python leaf, even though it HASHES differently. If the gate leaked, every
    rung of the dose ladder would be a mixture of a dose effect and a mask effect."""
    rc, rep = _run(_args(runtime=True), tmp_path)
    assert rc == 0, rep
    f = rep["functional"]
    ch = _checks(rep)
    assert ch["carc_rs_dose0_bit_exact"]["ok"]
    assert ch["py_dose0_bit_exact"]["ok"]
    assert f["rs_dose0_values_compared"] > 0 and f["rs_dose0_breaks"] == 0
    assert f["py_dose0_values_compared"] > 0 and f["py_dose0_breaks"] == 0
    # ...and the hash, which is NOT the evidence, still differs — both facts together are
    # the control (DESIGN §11 G4: the hash alone cannot prove the gate holds).
    assert rep["dose0_identity"]["leaf_hash"] != CHAMP


@needs_term
def test_a_nonzero_dose_moves_both_leaves(tmp_path):
    """The check that excludes 'accepted and ignored': a wheel that took the kwargs and
    dropped them on the floor would pass every structural check and still serve the
    champion leaf. DESIGN §6 measured J6 firing on 98% of a random-play corpus, so the
    full bundle biting on essentially every sampled value is the expected shape."""
    rc, rep = _run(_args(runtime=True), tmp_path)
    assert rc == 0, rep
    f = rep["functional"]
    assert f["values_moved"] > 0 and f["py_values_moved"] > 0
    assert f["values_moved"] > f["values_same"]


@needs_term
def test_both_leaves_accept_the_knobs_and_agree_on_the_bite(tmp_path):
    """Rust and python are bit-exact mirrors (reconcile_leaf --configs jrules), so the two
    independently-sampled 'values moved' counts must agree. A divergence here means one
    leaf got the knobs and the other did not — the exact half-wired state that would make
    a cell's candidate arm depend on which backend a worker happened to load."""
    rc, rep = _run(_args(runtime=True), tmp_path)
    assert rc == 0, rep
    f = rep["functional"]
    assert f["py_values_moved"] == f["values_moved"]
    assert f["py_values_same"] == f["values_same"]


@needs_term
def test_the_dose_scales_the_bite_monotonically(tmp_path):
    """The ladder's SHAPE, measured rather than assumed: `score += dose * T` means a
    nonzero T moves the leaf at EVERY nonzero dose, so the sampled bite cannot depend on
    the rung. A rung-dependent count would mean the dose is being read somewhere it
    shouldn't be (e.g. as a threshold)."""
    _, lo = _run(_args(runtime=True, doses="0.5"), tmp_path / "lo")
    _, hi = _run(_args(runtime=True, doses="2.0"), tmp_path / "hi")
    assert lo["functional"]["values_moved"] == hi["functional"]["values_moved"] > 0


# --------------------------------------------------------------------------- #
# The stale wheel, simulated — the gate's whole reason to exist                #
# --------------------------------------------------------------------------- #
_STALE_SHIM = '''\
"""Injected via PYTHONPATH (sitecustomize) to make the LOADED carc_rs look like a
build that predates the J-rules term: default-off configs still work, a set dose
raises exactly the TypeError a stale wheel raises."""
import carc_rs

_real = carc_rs.LeafConfigRs


def _stale(*a, **k):
    for key in list(k):
        if key.startswith("jrules_"):
            raise TypeError(
                "LeafConfigRs() got an unexpected keyword argument '%s'" % key)
    return _real(*a, **k)


carc_rs.LeafConfigRs = _stale
'''


@needs_term
def test_a_stale_wheel_makes_the_probe_exit_7_before_any_playout(tmp_path):
    """THE gate. Against a build that predates the term the probe must fail LOUDLY, and
    the failure must be legible as 'rebuild the wheel' rather than as a tight arm or a
    flaky playout — so it returns at the kwargs seam, before any leaf value is sampled.

    Simulated rather than assumed, because on a rebuilt box the real stale-wheel path is
    unreachable and this guard would otherwise be tested by nobody, ever."""
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "sitecustomize.py").write_text(_STALE_SHIM)
    pypath = os.pathsep.join([str(shim), os.environ.get("PYTHONPATH", "")]).rstrip(
        os.pathsep)
    rc, rep = _run(_args(runtime=True), tmp_path, extra_env={"PYTHONPATH": pypath})
    assert rc == 7, rep
    ch = _checks(rep)
    assert ch["carc_rs_accepts_jrules_kwargs"]["ok"] is False
    assert "PREDATES" in ch["carc_rs_accepts_jrules_kwargs"]["detail"]
    assert "jrules_dose" in ch["carc_rs_accepts_jrules_kwargs"]["detail"]
    # returned at the seam: no leaf value was sampled, so no *_changes_leaf check can
    # have "passed" on a champion-vs-champion comparison.
    assert "functional" not in rep
    assert not any(k.endswith("_changes_leaf") or k.endswith("_bit_exact") for k in ch)
    # ...while the STRUCTURAL checks still passed — that signature is what tells a reader
    # "this box needs a wheel", not "this tree has no term".
    assert ch["py_flat_jrules_term"]["ok"] and ch["env_is_champion_leaf"]["ok"]
