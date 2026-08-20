#!/usr/bin/env python3
"""W-FREEZE-LATCH — the PreToolUse latch that refuses a MAIN-TREE commit while a
scoring leg is live (DEVIATIONS D5 (b), ruling `3b7cd11a`).

⭐ WHY A HOOK AND NOT MORE CARE. The B64 aggregator commit was merged to main
while rung-3's local scoring leg was live — the same class that voided the first
JCZ run, and the direct cause of R5's two-rev split. The mitigation (the
instrument diff happened to be empty) was LUCK, NOT DESIGN: nothing about the
merge checked whether a leg was live, and had the commit touched `rust/`, `src/`
or `scripts/tiletie/`, chunks 3-5 would have been UNRECOVERABLE. The discipline
has failed TWICE and both times at the ORCHESTRATOR's hands — which is the
argument for a mechanism rather than more care.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "scripts" / "hooks" / "pretooluse_lint.py"
R5 = REPO / "measurement" / "tiearb_widening_20260817" / "rung3_r5"
B64 = REPO / "measurement" / "tiearb_widening_20260817" / "b64_cell"

sys.path.insert(0, str(HOOK.parent))
import pretooluse_lint as LINT                                     # noqa: E402


def _sentinel(tmp_path, name="rung3_r5"):
    d = tmp_path / "measurement" / name
    d.mkdir(parents=True)
    (d / LINT.RUN_LIVE_NAME).write_text(json.dumps(
        {"what": f"{name} scoring leg", "host": "Doctor", "pid": 1234}))
    return tmp_path


def test_the_latch_BLOCKS_a_main_tree_commit_while_a_leg_is_live(tmp_path,
                                                                 monkeypatch):
    monkeypatch.setattr(LINT, "REPO", str(_sentinel(tmp_path)))
    msg = LINT._freeze_latch("git commit -m 'x'", cwd=str(tmp_path))
    assert msg is not None
    assert "W-FREEZE-LATCH" in msg and "LIVE" in msg
    assert "RUN_LIVE.json" in msg
    assert "LUCK, NOT DESIGN" in msg
    assert "worktree" in msg


def test_the_latch_ALLOWS_when_no_leg_is_live(tmp_path, monkeypatch):
    (tmp_path / "measurement").mkdir()
    monkeypatch.setattr(LINT, "REPO", str(tmp_path))
    assert LINT._freeze_latch("git commit -m 'x'", cwd=str(tmp_path)) is None


def test_the_latch_ALLOWS_a_WORKTREE_commit_even_while_live(tmp_path, monkeypatch):
    """A commit inside a git worktree is exactly the safe pattern this project
    already mandates for a live tree, so it is never latched."""
    monkeypatch.setattr(LINT, "REPO", str(_sentinel(tmp_path)))
    wt = "/home/doctor/projects/carcassone/.claude/worktrees/agent-abc"
    assert LINT._freeze_latch(f"git -C {wt} commit -m 'x'", cwd=str(tmp_path)) is None
    assert LINT._freeze_latch("git commit -m 'x'", cwd=wt) is None
    # ... but a `-C` back into the main tree IS latched
    assert LINT._freeze_latch(f"git -C {tmp_path} commit -m 'x'",
                              cwd=wt) is not None


def test_the_latch_only_fires_on_a_COMMIT(tmp_path, monkeypatch):
    monkeypatch.setattr(LINT, "REPO", str(_sentinel(tmp_path)))
    for benign in ("git status", "git add -A", "git log --oneline -1",
                   "ls measurement/"):
        assert LINT._freeze_latch(benign, cwd=str(tmp_path)) is None


def _hook(cmd, tmp_path, monkeypatch, capsys):
    """Drive the real hook end-to-end: returns (exit_code, stderr)."""
    monkeypatch.setattr(LINT, "REPO", str(tmp_path))
    payload = json.dumps({"tool_name": "Bash", "cwd": str(tmp_path),
                          "tool_input": {"command": cmd}})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    rc = LINT.main()
    return rc, capsys.readouterr().err


@pytest.mark.parametrize("cmd,blocked", [
    ("git commit -m 'x'", True),
    # ⚠️ a bare `# allow-freeze` does NOT override — the override cannot be
    # muscle-memory, it has to be an argument.
    ("git commit -m 'x'  # allow-freeze", True),
    ("git commit -m 'x'  # allow-freeze:", True),
    ("git commit -m 'x'  # allow-freeze:   ", True),
    ("git commit -m 'x'  # allow-freeze: chunk 8 is the last leg and it is "
     "already merged", False),
    # `# nolint` still wins — it is the documented skip-all
    ("git commit -m 'x'  # nolint", False),
])
def test_the_override_REQUIRES_A_REASON(cmd, blocked, tmp_path, monkeypatch,
                                        capsys):
    _sentinel(tmp_path)
    rc, err = _hook(cmd, tmp_path, monkeypatch, capsys)
    assert (rc == 2) is blocked, (cmd, rc, err)
    assert ("W-FREEZE-LATCH" in err) is blocked, (cmd, err)


def test_the_latch_is_WIRED_into_the_hook_with_the_mandatory_reason():
    src = HOOK.read_text()
    assert "_freeze_latch(cmd, data.get(\"cwd\"))" in src
    assert r'if not re.search(r"#\s*allow-freeze\s*:\s*\S", cmd):' in src
    assert "allow-freeze: <reason>" in src        # documented in the docstring
    assert "REASON MANDATORY" in src


def test_BOTH_launchers_drop_and_CLEAR_the_sentinel_with_a_trap():
    """Orchestrator-proof by construction: the sentinel is a FILE, visible to
    WHOEVER commits, and a trap clears it so an abort cannot leave the tree
    latched."""
    for f in (R5 / "run_scoring_r5.sh", B64 / "run_cells.sh"):
        src = f.read_text()
        assert "W-FREEZE-LATCH" in src, f
        assert "run_live_drop" in src and "run_live_clear" in src, f
        assert "trap 'run_live_clear' EXIT INT TERM" in src, f
        assert LINT.RUN_LIVE_NAME in src, f
        # ⚠️ never on a dry run — a dry run scores nothing
        assert ('if [ "${DRY_RUN:-0}" -eq 0 ]; then' in src
                or 'if [ "$DRY" -eq 0 ]; then' in src), f
        assert subprocess.run(["bash", "-n", str(f)]).returncode == 0, f


def test_the_sentinel_is_found_anywhere_under_measurement(tmp_path, monkeypatch):
    root = tmp_path / "measurement" / "some_campaign" / "nested"
    root.mkdir(parents=True)
    (root / LINT.RUN_LIVE_NAME).write_text("{}")
    monkeypatch.setattr(LINT, "REPO", str(tmp_path))
    live = LINT._live_sentinels()
    assert len(live) == 1 and live[0].endswith(LINT.RUN_LIVE_NAME)
    assert LINT._freeze_latch("git commit -m x", cwd=str(tmp_path)) is not None


def test_the_hook_FAILS_OPEN_if_measurement_is_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(LINT, "REPO", str(tmp_path / "nope"))
    assert LINT._live_sentinels() == []
    assert LINT._freeze_latch("git commit -m x", cwd=str(tmp_path)) is None
