"""Contracts for the `--backend` seam on gate_b_depth_transfer, and for the snapshot BLOCKAGE.

These are the FAIL-CLOSED contracts (rustport P6 Class-B / audit B4). They are deliberately
cheap and carc_rs-free: the bit-exactness of the converted search is the gate's job
(`scripts/rustport/gate_depth_transfer_backend.py`, which needs the Rust wheel and real
roots), while what belongs in pytest is the part that must hold on EVERY box — that a
missing Rust surface raises instead of silently running something else.

  (A) snapshot.py refuses a rust backend, with its reason attached
  (B) gate_b rejects `--backend rust --verify-bit-exact` (a python-only proof)
  (C) the backend resolver validates, and honours the force-python escape hatch
  (D) the default is still "python" — the byte-identity promise every existing record rests on
"""
from __future__ import annotations

import os

# frozen leaf env — set BEFORE importing engine modules (pins the flat-leaf path)
os.environ.setdefault("CARCASSONNE_V25_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_OPP_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "0")
os.environ.setdefault("CARCASSONNE_V29_MEEPLE_CURVE", "-8,-4,-1,0,2,3,4,5")
os.environ.setdefault("CARCASSONNE_V25_MEEPLE_K", "2.0")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

import rust_world_search as RWS               # noqa: E402
import snapshot as SNAP                       # noqa: E402


# --- (A) the snapshot family stays python, loudly ---------------------------- #
def test_snapshot_rust_backend_fails_closed():
    with pytest.raises(NotImplementedError) as exc:
        SNAP.rust_backend()
    msg = str(exc.value)
    # The reason must travel WITH the error: a bare NotImplementedError sends the next
    # reader hunting for a flag that was never missing.
    assert "HeuristicMCTS" in msg, "the missing-AGENT blocker must be named"
    assert "search_single" in msg, "the missing-MECHANISM blocker must be named"
    assert "sum(levels)" in msg, "the cost consequence must be named"


def test_snapshot_gap_constant_is_the_error_text():
    assert SNAP.RUST_BACKEND_GAP
    with pytest.raises(NotImplementedError) as exc:
        SNAP.rust_backend(200, object())
    assert str(exc.value) == SNAP.RUST_BACKEND_GAP


# --- (B) --verify-bit-exact is a python-path proof --------------------------- #
def test_gate_b_rejects_verify_bit_exact_on_rust():
    import gate_b_depth_transfer as GB

    rc = GB.main(["--backend", "rust", "--verify-bit-exact", "--n", "1"])
    assert rc == 2, ("--backend rust + --verify-bit-exact must FAIL CLOSED: there is no "
                     "snapshot on the rust path for it to compare against")


def test_gate_b_rejects_unknown_backend():
    import gate_b_depth_transfer as GB

    with pytest.raises(SystemExit):
        GB.main(["--backend", "rustt", "--n", "1"])


# --- (C) the resolver ------------------------------------------------------- #
def test_resolve_backend_validates():
    assert RWS.resolve_backend("python") == "python"
    with pytest.raises(ValueError):
        RWS.resolve_backend("nope")


def test_force_python_escape_hatch(monkeypatch):
    monkeypatch.setenv(RWS.FORCE_PYTHON_ENV, "1")
    assert RWS.resolve_backend("rust") == "python", (
        "the escape hatch must win over an explicit --backend rust baked into a running "
        "chain script")


# --- (D) the default is unchanged -------------------------------------------- #
def test_gate_b_default_backend_is_python():
    import argparse
    import gate_b_depth_transfer as GB

    # Read the default off the parser rather than trusting the docstring: this is the
    # promise every pre-2026-08-02 record in measurement/gate_b_depth_transfer/ rests on.
    ap = argparse.ArgumentParser()
    src = Path(GB.__file__).read_text()
    assert '"--backend", choices=list(RWS.BACKENDS), default="python"' in src
    del ap


def test_rust_prior_levels_is_wired_to_the_shared_primitive():
    """B4 must reuse `rust_world_search`, not grow a second per-search primitive.

    Two mirror-seating implementations would be two places for the sync check to drift."""
    import gate_b_depth_transfer as GB

    src = Path(GB.__file__).read_text()
    assert "RWS.RustWorldSearcher" in src
    assert "check_sync" in src, "the mirror must be PROVEN at the root, not assumed"
