"""Contract for scripts/classical_search/menu_block_summary.py's rules_profile gate.

Regression for the false-fire found while computing CL-072's pooled n=800 read-out
(2026-08-11): the gate hardcoded `!= "fixed_v1"`, which fires on any cell legitimately
run under a different rules epoch -- e.g. CL-072's block E (n->800 extension), which
must run under `walled` to match its n=400 sibling's epoch for pooling. The fix makes
the gate compare against a caller-supplied `--expected-rules-profile` (default
`fixed_v1`, preserving old behavior for every existing caller).
"""
from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "classical_search" / "menu_block_summary.py"


def _write_cell(tmp_path: Path, rules_profile_name: str, r9_env_ok: bool = True,
                 opp_leaf_hash: str = "a36d2e15a3b3d71d") -> Path:
    cell = tmp_path / "cell"
    cell.mkdir()
    (cell / "summary.json").write_text(json.dumps({
        "n": 400, "n_paired": 200, "W": 190, "D": 10, "L": 200,
        "elo": -10.0, "elo_sig_1sigma": 17.4, "paired_z": -1.2,
        "paired_mean_margin": -1.1, "paired_se_margin": 0.9, "wr": 0.5,
    }))
    (cell / "manifest.json").write_text(json.dumps({
        "rules_profile": {"name": rules_profile_name, "r9_env_ok": r9_env_ok},
        "config": {"opp_leaf_hash": opp_leaf_hash},
    }))
    # menu_block_summary.py counts files starting with "seed" and ending ".json" on disk.
    (cell / "seed000000000000_a0.json").write_text("{}")
    return cell


def _run(cell_dir: Path, out_path: Path, extra_argv=()):
    argv = ["menu_block_summary.py", "--dir", str(cell_dir), "--label", "t",
            "--out", str(out_path), *extra_argv]
    old_argv = sys.argv
    sys.argv = argv
    try:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    except SystemExit as e:
        assert e.code in (0, None), f"menu_block_summary.py exited {e.code}"
    finally:
        sys.argv = old_argv
    return json.loads(out_path.read_text())


def test_default_expects_fixed_v1_and_gates_walled(tmp_path):
    """Unchanged behavior: a walled cell fails the DEFAULT (fixed_v1) gate."""
    cell = _write_cell(tmp_path, "walled")
    out = _run(cell, tmp_path / "out.json")
    assert out["expected_rules_profile"] == "fixed_v1"
    assert out["wiring_gates_clean"] is False
    assert any("rules_profile" in g for g in out["wiring_gate_failures"])
    assert "READ_BLOCK" in out


def test_fixed_v1_cell_clean_by_default(tmp_path):
    cell = _write_cell(tmp_path, "fixed_v1")
    out = _run(cell, tmp_path / "out.json")
    assert out["wiring_gates_clean"] is True
    assert out["wiring_gate_failures"] == []
    assert "READ_BLOCK" not in out


def test_walled_cell_clean_when_walled_is_declared_expected(tmp_path):
    """The block-E fix: --expected-rules-profile walled must not false-fire on a
    legitimately-walled cell."""
    cell = _write_cell(tmp_path, "walled")
    out = _run(cell, tmp_path / "out.json", extra_argv=["--expected-rules-profile", "walled"])
    assert out["expected_rules_profile"] == "walled"
    assert out["wiring_gates_clean"] is True
    assert out["wiring_gate_failures"] == []
    assert "READ_BLOCK" not in out


def test_wrong_profile_still_gates_even_with_expected_override(tmp_path):
    """The gate still catches a genuine mismatch against whatever WAS declared expected."""
    cell = _write_cell(tmp_path, "fixed_v1")
    out = _run(cell, tmp_path / "out.json", extra_argv=["--expected-rules-profile", "walled"])
    assert out["wiring_gates_clean"] is False
    assert any("rules_profile" in g for g in out["wiring_gate_failures"])


def test_other_gates_unweakened(tmp_path):
    """r9_env_ok and opp_leaf_hash gates still fire independent of the profile gate."""
    cell = _write_cell(tmp_path, "fixed_v1", r9_env_ok=False, opp_leaf_hash="deadbeef")
    out = _run(cell, tmp_path / "out.json")
    assert out["wiring_gates_clean"] is False
    failures = " ".join(out["wiring_gate_failures"])
    assert "r9_env_ok" in failures
    assert "opponent leaf hash" in failures
