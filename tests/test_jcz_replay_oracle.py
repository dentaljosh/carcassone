"""F9 / D1 — CI mode for the JCloisterZone runtime replay oracle.

The D0 pytest (``test_jcz_tile_oracle.py``) guards our *tile data* against JCZ's.
This one guards the *traversal, legality and scoring* that consume it: a full game
is replayed through both engines in lockstep and every divergence must fall in the
classified set.

SKIPPED when ``~/jcz_spike/JCloisterZone/build/Engine.jar`` is absent — the jar is
28 MB and deliberately not vendored (``measurement/jcz_spike_20260803/SPIKE_REPORT.md``
records the two-minute build). Nothing else here needs Java.

⚠️ The oracle is run on ``fixed_v1`` + R9, which is the ONLY configuration in which
our engine and JCZ are playing the same rules. Under ``walled`` the audit's five
named divergences are live by design and the harness classifies rather than fails
on them; asserting "no divergence" there would assert the audit away.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "jcz_oracle" / "replay_diff.py"
JAR = Path(os.environ.get(
    "JCZ_JAR", os.path.expanduser("~/jcz_spike/JCloisterZone/build/Engine.jar")))
GAMES = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"

pytestmark = pytest.mark.skipif(
    not JAR.exists(), reason=f"JCZ Engine.jar not built at {JAR} (see SPIKE_REPORT.md)")


def _run(tmp_path: Path, *extra: str, limit: int = 2):
    out = tmp_path / "oracle.json"
    cmd = [sys.executable, str(SCRIPT), "--games", str(GAMES), "--limit", str(limit),
           "--out", str(out), "--fail-on-real", *extra]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900, cwd=REPO)
    return proc, out


@pytest.mark.slow
def test_fixed_v1_r9_has_no_unclassified_divergence(tmp_path):
    """The clean profile must agree with JCZ outright — no divergence at all."""
    import json

    proc, out = _run(tmp_path, "--profile", "fixed_v1", "--policy", "seeded", "--r9")
    assert proc.returncode == 0, f"unclassified divergence:\n{proc.stdout}\n{proc.stderr}"
    data = json.loads(out.read_text())
    assert data["r9"] is True
    assert not data["real"], data["real"]
    # …and the money number: every game's FINAL SCORES must match exactly.
    assert data["score_agreement"]["compared"] == data["n_games"]
    assert data["score_agreement"]["agree"] == data["n_games"], [
        (g["deck_seed"], g["our_final"], g["jcz_final"]) for g in data["games"]
        if not g["final_agree"]]


@pytest.mark.slow
def test_walled_record_divergence_is_fully_classified(tmp_path):
    """The engine of record diverges — but only in the audit's NAMED ways.

    This is the assertion that would catch a *new* rules bug: the known five stay
    classified, so anything else lands in ``REAL`` and fails.
    """
    import json

    proc, out = _run(tmp_path, "--profile", "walled", "--policy", "record", "--r9")
    assert proc.returncode == 0, f"unclassified divergence:\n{proc.stdout}\n{proc.stderr}"
    data = json.loads(out.read_text())
    assert not data["real"], data["real"]


@pytest.mark.slow
def test_r9_flag_flips_the_farm_classes(tmp_path):
    """R9 off must light up the farm classes; R9 on must extinguish them.

    A guard against the fix silently regressing to a no-op — the failure mode a
    default-off remediation flag is most exposed to.
    """
    import json

    _, off = _run(tmp_path / "off", "--profile", "fixed_v1", "--policy", "seeded",
                  limit=2)
    _, on = _run(tmp_path / "on", "--profile", "fixed_v1", "--policy", "seeded",
                 "--r9", limit=2)
    off_t, on_t = json.loads(off.read_text())["totals"], json.loads(on.read_text())["totals"]
    assert off_t.get("FARM_ATOM_SET", 0) > 0, off_t
    assert on_t.get("FARM_ATOM_SET", 0) == 0, on_t
    assert on_t.get("FARM_PARTITION", 0) == 0, on_t
