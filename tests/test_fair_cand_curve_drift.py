"""--allow-cand-curve-drift: the CANDIDATE-side leaf-SHAPE escape hatch
(scripts/classical_search/eval_fair_puct.py).

The pre-registered curve-shape cell
(measurement/curve_shape_scope_20260809/PREREG_DRAFT.md §3) needs a deck-paired
fair-vs-fair-champion head-to-head whose CANDIDATE arm carries a v29_meeple_curve
that differs from the champion's curve125. Before this flag that combination
hard-exited on `_assert_netprior_leaf`'s unconditional curve125 check.

What is under test (the invariants, not the plumbing):
  (a) FLAG OFF is unchanged — a non-curve125 candidate still hard-exits with the
      original "expected curve125" message, on BOTH sides.
  (b) FLAG ON stamps instead of asserting, on the CANDIDATE side only, and records
      cand_curve_drift_allowed + the literal resolved curve + the leaf hash.
  (c) The stamping path is still a GATE: a None curve or a wrong-length /
      non-finite curve is a mis-specified cell and must SystemExit.
  (d) The OPPONENT side keeps the unmodified assert — `_assert_netprior_leaf` is
      untouched and still refuses anything but curve125, so the flag can never
      symmetrise the cell.
  (e) The flag is scoped to `--info fair --opponent fair-champion` at argparse
      time; every other arm rejects it.

No games are played (helper functions + argparse only), so this file runs in
seconds. Importing eval_fair_puct FIRST keeps DEFAULT_CONFIG the production
cap8/curve100 leaf (the harness sets it via setdefault at import).
"""
from __future__ import annotations

import dataclasses as dc
import importlib.util
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "classical_search" / "eval_fair_puct.py"

_spec = importlib.util.spec_from_file_location("eval_fair_puct", SCRIPT)
efp = importlib.util.module_from_spec(_spec)
sys.modules["eval_fair_puct"] = efp
_spec.loader.exec_module(efp)

DEF = efp.DEFAULT_CONFIG
# Bflattop-like (rho ~ 0.5): 8 finite floats, deliberately NOT curve125.
ALT_CURVE = (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 4.375, 5.0)


def _cand(curve):
    return dc.replace(efp._curve125_leaf_cfg(), v29_meeple_curve=curve)


# --------------------------------------------------------------------------- #
# (a) flag OFF: the original rejection still fires
# --------------------------------------------------------------------------- #
def test_flag_off_still_rejects_an_alt_curve_candidate():
    with pytest.raises(SystemExit, match="expected curve125"):
        efp._assert_netprior_leaf(_cand(ALT_CURVE), side="candidate",
                                  tag="head-to-head")


def test_allow_leaf_hash_drift_does_not_open_the_curve_check():
    """--allow-leaf-hash-drift downgrades the HASH check only (strict=False)."""
    with pytest.raises(SystemExit, match="expected curve125"):
        efp._assert_netprior_leaf(_cand(ALT_CURVE), strict=False, side="candidate",
                                  tag="head-to-head")


# --------------------------------------------------------------------------- #
# (b) flag ON: the candidate is STAMPED, not asserted
# --------------------------------------------------------------------------- #
def test_stamp_accepts_an_eight_entry_alt_curve_and_records_the_drift():
    cfg = _cand(ALT_CURVE)
    prov = efp._stamp_cand_leaf(cfg, tag="head-to-head")
    assert prov["cand_curve_drift_allowed"] is True
    assert prov["curve_values"] == list(ALT_CURVE)
    assert prov["leaf_hash"] == efp._leaf_hash(cfg)
    # it must NOT claim to be curve125 anywhere in the human-readable label
    assert "curve125" not in prov["curve"].split("NOT curve125")[0]
    assert prov["leaf_hash"] != efp.CURVE125_LEAF_HASH
    # the champ-dialect frozen hash is best-effort provenance, same key as the assert
    assert "frozen_config_hash_champ_dialect" in prov
    # the curve125 reference is carried so a reader can size the contrast
    assert prov["curve125_reference"]["leaf_hash"] == efp.CURVE125_LEAF_HASH


def test_stamp_on_curve125_itself_is_a_no_op_identity():
    """Passing the champion curve through the stamp path yields the champion hash."""
    prov = efp._stamp_cand_leaf(efp._curve125_leaf_cfg())
    assert prov["leaf_hash"] == efp.CURVE125_LEAF_HASH
    assert prov["curve_values"] == list(efp.CURVE125)


# --------------------------------------------------------------------------- #
# (c) the stamping path is still a gate
# --------------------------------------------------------------------------- #
def test_stamp_rejects_a_none_curve():
    with pytest.raises(SystemExit, match="EXPLICIT candidate meeple curve"):
        efp._stamp_cand_leaf(_cand(None))


@pytest.mark.parametrize("bad", [
    (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0),                     # 7 entries
    (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25, 7.0),          # 9 entries
    (),                                                             # empty
    (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, math.inf),           # non-finite
    (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, math.nan),           # non-finite
])
def test_stamp_rejects_a_malformed_curve(bad):
    with pytest.raises(SystemExit, match="8 finite floats"):
        efp._stamp_cand_leaf(_cand(bad))


# --------------------------------------------------------------------------- #
# (d) the OPPONENT side is untouched
# --------------------------------------------------------------------------- #
def test_opponent_side_assert_is_unchanged_and_still_pins_curve125():
    """The reference arm keeps the ORIGINAL function, hashes and all."""
    prov = efp._assert_netprior_leaf(efp._curve125_leaf_cfg(), side="opponent",
                                     tag="head-to-head")
    assert prov["leaf_hash"] == efp.CURVE125_LEAF_HASH
    assert prov["curve"] == "curve125 (production champion, CL-051)"
    assert "cand_curve_drift_allowed" not in prov
    # and it refuses an alt curve on the opponent side no matter what
    with pytest.raises(SystemExit, match="expected curve125"):
        efp._assert_netprior_leaf(_cand(ALT_CURVE), side="opponent",
                                  tag="head-to-head")


def test_the_two_helpers_are_separate_functions():
    """The assert's docstring promises the SAME check both sides — keep it true."""
    assert efp._stamp_cand_leaf is not efp._assert_netprior_leaf
    assert "allow_cand_curve_drift" not in (efp._assert_netprior_leaf.__code__.co_names
                                            + efp._assert_netprior_leaf.__code__.co_varnames)


# --------------------------------------------------------------------------- #
# (e) argparse scoping
# --------------------------------------------------------------------------- #
_BASE = ["--n", "2", "--paired", "--out-root", "/tmp", "--out-subdir", "x",
         "--no-results-csv"]


def _err(argv):
    with pytest.raises(SystemExit) as e:
        efp.main(argv)
    return e


def test_flag_rejected_for_a_net_opponent(capsys):
    _err(["--info", "fair", "--opponent", "net", "--opp-net", "/nonexistent.pt",
          "--allow-cand-curve-drift"] + _BASE)
    assert "--allow-cand-curve-drift applies ONLY" in capsys.readouterr().err


def test_flag_rejected_for_fair_netprior(capsys):
    _err(["--info", "fair-netprior", "--net", "/nonexistent.pt",
          "--opponent", "fair-champion", "--allow-cand-curve-drift"] + _BASE)
    assert "--allow-cand-curve-drift applies ONLY" in capsys.readouterr().err


def test_flag_rejected_for_the_h800_rung_and_greedy(capsys):
    for opp in ("h800", "greedy"):
        _err(["--info", "fair", "--opponent", opp, "--allow-cand-curve-drift"] + _BASE)
        assert "--allow-cand-curve-drift applies ONLY" in capsys.readouterr().err


def test_flag_default_is_off_and_declared_store_true():
    src = SCRIPT.read_text()
    assert 'ap.add_argument("--allow-cand-curve-drift", action="store_true"' in src
    # the help text must name the scope and the opponent pin (governance-readable)
    assert "OPPONENT arm stays PINNED to " in src        # (help text is wrapped)
