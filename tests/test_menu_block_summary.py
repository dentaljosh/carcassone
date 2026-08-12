"""Contract for scripts/classical_search/menu_block_summary.py.

1. The rules_profile gate. Regression for the false-fire found while computing CL-072's
   pooled n=800 read-out (2026-08-11): the gate hardcoded `!= "fixed_v1"`, which fires on
   any cell legitimately run under a different rules epoch -- e.g. CL-072's block E
   (n->800 extension), which must run under `walled` to match its n=400 sibling's epoch
   for pooling. The fix makes the gate compare against a caller-supplied
   `--expected-rules-profile` (default `fixed_v1`, preserving old behavior for every
   existing caller).

2. The ms/move ratio's harness-convention detection (added 2026-08-12). Two harnesses name
   the two sides' cost fields incompatibly -- `champ_prefix_ms_per_move` is the OPPONENT in
   eval_puct_priors and the CANDIDATE in eval_fair_puct -- so the extractor must detect the
   convention from which other field is present (`cand_prefix_ms_per_move` vs
   `rung_ms_per_move`). It previously only handled the ablation pair, so
   `ms_ratio_cand_over_opp` came out null on EVERY fair-PIMC cell.
"""
from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "classical_search" / "menu_block_summary.py"


def _write_cell(tmp_path: Path, rules_profile_name: str, r9_env_ok: bool = True,
                 opp_leaf_hash: str = "a36d2e15a3b3d71d", extra_summary: dict | None = None,
                 name: str = "cell") -> Path:
    cell = tmp_path / name
    cell.mkdir()
    summary = {
        "n": 400, "n_paired": 200, "W": 190, "D": 10, "L": 200,
        "elo": -10.0, "elo_sig_1sigma": 17.4, "paired_z": -1.2,
        "paired_mean_margin": -1.1, "paired_se_margin": 0.9, "wr": 0.5,
    }
    summary.update(extra_summary or {})
    (cell / "summary.json").write_text(json.dumps(summary))
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


# --------------------------------------------------------------------------- #
# ms/move ratio: harness-convention detection                                  #
# --------------------------------------------------------------------------- #
# The two emitters, verified by reading them (2026-08-12):
#   eval_puct_priors.py:1325  cand_prefix_ms_per_move == CANDIDATE
#                             champ_prefix_ms_per_move == OPPONENT
#   eval_fair_puct.py:1990    champ_prefix_ms_per_move == CANDIDATE
#                             rung_ms_per_move         == OPPONENT   (no cand_prefix_* at all)

def test_fair_convention_ratio_is_champ_over_rung(tmp_path):
    """REGRESSION (fails against the pre-2026-08-12 code, which emitted null here).

    A fair-PIMC cell has no `cand_prefix_ms_per_move`, so the old `if cm and chm` guard
    fell through and the cost figure was silently dropped from every fair verdict extract.
    """
    cell = _write_cell(tmp_path, "fixed_v1", extra_summary={
        "champ_prefix_ms_per_move": 1200.0,   # CANDIDATE in this harness
        "rung_ms_per_move": 800.0,            # OPPONENT
    })
    out = _run(cell, tmp_path / "out.json")
    assert out["ms_ratio_cand_over_opp"] == pytest.approx(1200.0 / 800.0)
    assert out["ms_ratio_source"] == "eval_fair_puct (champ_prefix/rung)"
    # the opponent-side field must be carried through, not just consumed
    assert out["rung_ms_per_move"] == pytest.approx(800.0)
    # the caveat must state the FAIR convention and keep the shared-tenancy warning
    assert "champ_prefix_*` is the CANDIDATE" in out["ms_ratio_caveat"]
    assert "shared-tenancy" in out["ms_ratio_caveat"]


def test_ablation_convention_ratio_is_cand_over_champ(tmp_path):
    """Unchanged behaviour for the 2750 ablation instrument."""
    cell = _write_cell(tmp_path, "fixed_v1", extra_summary={
        "cand_prefix_ms_per_move": 1500.0,    # CANDIDATE
        "champ_prefix_ms_per_move": 1000.0,   # OPPONENT in THIS harness
    })
    out = _run(cell, tmp_path / "out.json")
    assert out["ms_ratio_cand_over_opp"] == pytest.approx(1500.0 / 1000.0)
    assert out["ms_ratio_source"] == "eval_puct_priors (cand_prefix/champ_prefix)"
    assert "rung_ms_per_move" not in out
    # the caveat must NOT claim champ_prefix is the candidate here -- it is the opponent
    assert "`champ_prefix_*` is the OPPONENT" in out["ms_ratio_caveat"]
    assert "shared-tenancy" in out["ms_ratio_caveat"]


def test_no_ms_fields_leaves_ratio_absent(tmp_path):
    """Neither convention detectable => no ratio, no source, no crash."""
    cell = _write_cell(tmp_path, "fixed_v1")
    out = _run(cell, tmp_path / "out.json")
    assert out.get("ms_ratio_cand_over_opp") is None
    assert "ms_ratio_source" not in out
    assert "ms_ratio_caveat" not in out
    assert out["wiring_gates_clean"] is True   # everything else still works


def test_zero_opponent_ms_does_not_divide_by_zero(tmp_path):
    """The truthiness guard's job: a 0 divisor must skip the ratio, not raise."""
    cell = _write_cell(tmp_path, "fixed_v1", extra_summary={
        "champ_prefix_ms_per_move": 1200.0, "rung_ms_per_move": 0.0,
    })
    out = _run(cell, tmp_path / "out.json")
    assert out.get("ms_ratio_cand_over_opp") is None


def test_real_fair_deploy_cell_numbers(tmp_path):
    """Real data: the denial fair-PIMC deploy cell (2026-08-12).

    Literal values off the cell's summary.json; the extract must read ~0.9522, i.e. the
    candidate is slightly CHEAPER than its opponent -- a figure that read as `null` before
    the fix.
    """
    cell = _write_cell(tmp_path, "fixed_v1", extra_summary={
        "champ_prefix_ms_per_move": 1466.5112025522967,
        "rung_ms_per_move": 1540.2018627912876,
    })
    out = _run(cell, tmp_path / "out.json")
    assert out["ms_ratio_cand_over_opp"] == pytest.approx(0.9522, abs=1e-4)
    assert out["ms_ratio_source"] == "eval_fair_puct (champ_prefix/rung)"
