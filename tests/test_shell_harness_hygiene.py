"""Shell-harness hygiene: a FAILED cell must never be able to log rc=0.

THE BUG THIS PINS (found 2026-07-27, fixed in 437f5a7 across 8 scripts). Every
launcher in this repo logs the exit status of the cell it just ran. The natural
way to write that line is the broken way:

    echo "[$(date +%F_%T)] --- RUNG $tag exited rc=$?"

Bash expands a word LEFT TO RIGHT, so the `$(date ...)` command substitution
RUNS -- and overwrites `$?` with its own status (0) -- BEFORE the later `$?` is
expanded. The line therefore reports rc=0 for EVERY run, pass or fail. It is a
silent-failure mode of the worst kind: the log looks normal, the queue moves on,
and the cell it just abandoned is indistinguishable downstream from a real one
except by its `n`. It cost us a k8x1376 rung that "succeeded" 8 seconds after
`FATAL: carc-orch died early`, and the first diagnosis blamed the wrong file
(the wrapper was exiting 1 correctly all along).

Demonstration, if this test ever confuses someone:

    bash -c 'false; echo "[$(date)] rc=$?"'            # -> rc=0   WRONG
    bash -c 'false; rc=$?; echo "[$(date)] rc=$rc"'    # -> rc=1   right

So the rule is mechanical and worth enforcing mechanically: **capture `$?` into a
variable before any command substitution can run.** shellcheck's SC2319 catches
this class, but shellcheck is not installed on these boxes and these scripts are
not in CI -- hence a pytest that greps.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"

# Splitting on the command separators is what keeps the check specific: `$?` is
# only at risk when a command substitution runs earlier IN THE SAME COMMAND WORD.
# `foo=$(bar); echo $?` is perfectly correct -- the `;` ends the command, so the
# `$?` genuinely refers to `bar`.
_SEPARATORS = re.compile(r";|&&|\|\|")
_CMD_SUBST = re.compile(r"\$\(|`")


def _strip_comment(line: str) -> str:
    """Drop a trailing comment. Quote-naive on purpose.

    A `#` inside a quoted string would truncate the line early, which can only
    cause a MISSED finding, never a false one -- the safe direction for a lint.
    """
    hash_at = line.find("#")
    return line if hash_at < 0 else line[:hash_at]


def _offending_segments(line: str) -> list[str]:
    """Segments where a command substitution precedes `$?` in the same command."""
    out = []
    for seg in _SEPARATORS.split(_strip_comment(line)):
        q = seg.find("$?")
        if q < 0:
            continue
        sub = _CMD_SUBST.search(seg)
        if sub is not None and sub.start() < q:
            out.append(seg.strip())
    return out


def _shell_scripts() -> list[pathlib.Path]:
    return sorted(p for p in SCRIPTS.rglob("*.sh") if p.is_file())


def test_scripts_exist():
    """Guard the guard: an empty glob would make every check below vacuously green."""
    assert len(_shell_scripts()) > 20, "expected the scripts/ tree to hold many .sh files"


def test_no_command_substitution_clobbers_dollar_question():
    """No `$?` read after a command substitution in the same command word."""
    findings = []
    for path in _shell_scripts():
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for seg in _offending_segments(line):
                findings.append(f"{path.relative_to(REPO)}:{lineno}: {seg}")
    assert not findings, (
        "`$?` is read after a command substitution runs in the same command word, so it "
        "reports the substitution's status (0), NOT the command's. A failed run will log "
        "rc=0. Capture it first: `cmd` / `rc=$?` / `echo \"[$(date)] rc=$rc\"`.\n  "
        + "\n  ".join(findings)
    )


def test_the_check_actually_catches_the_bug(tmp_path):
    """The lint must fail on the real broken line and pass on the real fixed one.

    Without this, a regex that silently matches nothing would make the test above
    green forever -- the same fail-open shape the bug itself had.
    """
    bad = 'echo "[$(date +%F_%T)] --- RUNG $tag exited rc=$?" | tee -a "$LOG"'
    good_capture = "rc=$?"
    good_separated = "total=$(wc -l < f); echo $?"

    assert _offending_segments(bad), "lint failed to flag the known-broken line"
    assert not _offending_segments(good_capture)
    assert not _offending_segments(good_separated), (
        "a `$?` after a SEPARATE command is legitimate and must not be flagged"
    )
    assert not _offending_segments('  # echo "[$(date)] rc=$?"  <- in a comment')


@pytest.mark.parametrize("snippet,expected", [
    ('false; echo "[$(date)] rc=$?"', "0"),      # the bug, in a real shell
    ("false; rc=$?; echo \"[$(date)] rc=$rc\"", "1"),   # the fix, in a real shell
])
def test_bash_really_behaves_this_way(snippet, expected):
    """Pin the bash semantics themselves, so the rationale above can't rot.

    If a future bash ever stopped clobbering `$?` during word expansion, this is
    where we would find out -- rather than quietly keeping a lint nobody needs.
    """
    out = subprocess.run(["bash", "-c", snippet], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().endswith("rc=" + expected), out.stdout


def test_cell_launchers_report_failure_loudly():
    """The blind-curve queues must surface a failed cell, not log it and continue.

    These are the launchers that actually produce results.csv rows; a cell that
    fails there must be impossible to mistake for a completed one.
    """
    for name in ("blind_curve_queue.sh", "blind_curve_top.sh", "blind_curve_width11008.sh"):
        text = (SCRIPTS / "classical_search" / name).read_text(encoding="utf-8")
        assert "rc=$?" in text, f"{name}: does not capture the cell's exit status at all"
        assert "FAILED" in text, f"{name}: no loud failure branch"
        assert "INCOMPLETE" in text, (
            f"{name}: the failure message must warn that the cell's summary is INCOMPLETE "
            "and must not be read -- an eval cell fails OPEN, unlike self-play"
        )
        assert "exit 1" in text, f"{name}: must exit non-zero so a caller can see the failure"
