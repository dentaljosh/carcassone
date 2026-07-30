"""Contract tests for scripts/measurement_infra/run_watchdog.sh's orphan-claim guard.

Added 2026-07-30 (buried-caveats audit F14). The guard's whole contract is:

    a claim whose record EXISTS is history (keep it);
    a claim with NO record blocks resume forever (clear it).

It used to hardcode the record extension as ``.json``, which silently INVERTED that
contract on a gen cell armed with ``seed_*.npz``: no ``.json`` ever exists beside a
``.npz``, so every claim read record-less and the guard deleted all of them — including
the claims of games already banked. These tests pin the extension to the glob.

The helper block is extracted from the shell script by its BEGIN/END markers so the tests
run the REAL code rather than a copy (the script's main body is an infinite poll loop and
cannot be invoked directly).
"""

import pathlib
import subprocess

import pytest

SCRIPT = (pathlib.Path(__file__).resolve().parents[1]
          / "scripts" / "measurement_infra" / "run_watchdog.sh")

BEGIN = "# --- BEGIN testable helpers"
END = "# --- END testable helpers ---"


def _helper_block() -> str:
    lines = SCRIPT.read_text().splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.startswith(BEGIN)]
    ends = [i for i, ln in enumerate(lines) if ln.startswith(END)]
    assert len(starts) == 1 and len(ends) == 1, "helper markers must appear exactly once"
    assert starts[0] < ends[0]
    return "\n".join(lines[starts[0] + 1:ends[0]])


def _run_guard(glob: str) -> subprocess.CompletedProcess:
    """Run the real REC_EXT derivation + clear_orphan_claims against `glob`."""
    script = "\n".join([
        "set -uo pipefail",
        f"GLOB={glob!r}",
        "say() { :; }",
        _helper_block(),
        "clear_orphan_claims",
    ])
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True)


def _make_cell(tmp_path, ext):
    """A cell with one BANKED seed (record + claim) and one ORPHAN seed (claim only)."""
    banked_claim = tmp_path / "seed_001.claim"
    banked_rec = tmp_path / f"seed_001.{ext}"
    orphan_claim = tmp_path / "seed_002.claim"
    for p in (banked_claim, banked_rec, orphan_claim):
        p.write_text("x")
    return banked_claim, banked_rec, orphan_claim


@pytest.mark.parametrize("ext", ["npz", "json"])
def test_guard_keeps_banked_claim_and_clears_orphan(tmp_path, ext):
    """The contract, on both the gen (.npz) and eval (.json) record shapes."""
    banked_claim, banked_rec, orphan_claim = _make_cell(tmp_path, ext)

    proc = _run_guard(f"{tmp_path}/seed_*.{ext}")
    assert proc.returncode == 0, proc.stderr

    assert banked_claim.exists(), (
        f"REGRESSION (audit F14): the claim of an already-banked .{ext} record was deleted — "
        "a relaunch would re-play completed seeds")
    assert banked_rec.exists(), "the guard must never touch record files"
    assert not orphan_claim.exists(), "a record-less claim must be cleared or resume stalls forever"


def test_npz_cell_is_not_wiped_by_a_json_hardcode(tmp_path):
    """The exact regression: a .npz gen cell containing NO .json at all.

    Under the old hardcode every claim here read record-less and all were deleted.
    """
    for i in range(5):
        (tmp_path / f"seed_{i:03d}.npz").write_text("x")
        (tmp_path / f"seed_{i:03d}.claim").write_text("x")

    proc = _run_guard(f"{tmp_path}/seed_*.npz")
    assert proc.returncode == 0, proc.stderr

    survivors = sorted(p.name for p in tmp_path.glob("*.claim"))
    assert len(survivors) == 5, (
        f"all 5 banked claims must survive; got {survivors}")


def test_extensionless_glob_is_rejected_loudly(tmp_path):
    """Fail closed: an un-parseable glob must exit non-zero, not silently guess."""
    proc = _run_guard(f"{tmp_path}/seed_records")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "plain .<ext>" in proc.stderr


def test_helper_block_has_no_json_hardcode():
    """Belt and braces: the guard must not name a record extension literally."""
    block = _helper_block()
    guard = block[block.index("clear_orphan_claims"):]
    assert ".json" not in guard and ".npz" not in guard, (
        "clear_orphan_claims must derive the extension from REC_EXT, never hardcode one")
