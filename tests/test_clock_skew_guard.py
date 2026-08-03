"""The shared CLOCK-SKEW GUARD: it must fire on skew, and every launcher must carry it.

THE BUG THIS PINS (found live 2026-07-30 23:26, roadmap F7c).
`carcassonne_ai/claim.py:is_stale()` compares a claim file's mtime -- on the CIFS
share that is the SERVER's clock -- against the CLIENT's `time.time()`. A client
whose clock runs fast by more than `--claim-stale-secs` sees EVERY claim on the
share as stale, including claims a sibling box is actively working, and steals
them all. The laptop's WSL2 clock was +11697 s after a host sleep and had taken
100% of the local box's claims within 3 minutes; both boxes then computed the
SAME seeds. Nothing crashes and nothing warns -- duplicate work is "harmless" by
claim.py's own contract -- so the only symptom is missing throughput.

The guard therefore has to be BOTH correct and universal, and those are two
different failures, so this file tests two different things:

  1. SEMANTICS -- the guard actually aborts on injected skew and passes on none.
     Skew is injected the honest way: a `date` shim on PATH, so the real code
     path runs unmodified. There are no test-only hooks in the shell library.
  2. COVERAGE -- every `--shared-claim` launcher in scripts/ carries it. A guard
     that exists in one launcher is what the incident already looked like.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import stat
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
LIB = REPO / "scripts" / "measurement_infra" / "clock_skew_guard.sh"

# The two launchers that pioneered the guard inline. They were live when the
# shared lib was hoisted (F7c), so they deliberately keep their own copies; a
# later cleanup can dedupe them. They still have to be covered, just differently.
INLINE_DONORS = {
    "scripts/classical_search/leaf_ablation_launcher.sh",
    "scripts/classical_search/capscurve_resweep_launcher.sh",
}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _run(script: str, tmp_path: pathlib.Path, env_extra=None, path_prefix=None):
    """Run a snippet that sources the lib, from the repo root."""
    path = tmp_path / "snippet.sh"
    path.write_text("set -euo pipefail\n. " + str(LIB) + "\n" + script)
    env = dict(os.environ)
    env.pop("OUT_ROOT", None)  # never let the ambient shell pick the probe dir
    if path_prefix:
        env["PATH"] = str(path_prefix) + os.pathsep + env["PATH"]
    env.update(env_extra or {})
    return subprocess.run(
        ["bash", str(path)], capture_output=True, text=True, timeout=60,
        cwd=str(REPO), env=env,
    )


def _date_shim(tmp_path: pathlib.Path, offset: int) -> pathlib.Path:
    """A PATH-shadowing `date` whose epoch is `offset` seconds off.

    This is exactly the real failure mode -- a box whose wall clock disagrees
    with the share's -- reproduced without touching the system clock and without
    a single test-only branch in the shell library.
    """
    real = shutil.which("date", path="/usr/bin:/bin")
    assert real, "no system `date` to shim"
    d = tmp_path / ("shim%+d" % offset)
    d.mkdir()
    shim = d / "date"
    shim.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "+%s" ]; then echo $(( $(' + real + " +%s) + " + str(offset) + " )); "
        'else exec ' + real + ' "$@"; fi\n'
    )
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return d


def _shell_scripts() -> list[pathlib.Path]:
    return sorted(p for p in (REPO / "scripts").rglob("*.sh") if p.is_file())


def _shared_claim_launchers() -> list[pathlib.Path]:
    """.sh files that actually INVOKE a --shared-claim run (comments don't count)."""
    out = []
    for p in _shell_scripts():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s.startswith("#") and "--shared-claim" in s:
                out.append(p)
                break
    return out


# --------------------------------------------------------------------------
# 1. semantics
# --------------------------------------------------------------------------
def test_lib_exists_and_is_syntactically_valid():
    assert LIB.is_file(), f"{LIB} missing"
    r = subprocess.run(["bash", "-n", str(LIB)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr


def test_passes_when_there_is_no_skew(tmp_path):
    probe = tmp_path / "out"
    r = _run(f'carc_clock_skew_guard "{probe}"\necho REACHED_END\n', tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "clock-skew guard OK" in r.stdout
    assert "REACHED_END" in r.stdout


@pytest.mark.parametrize("offset,direction", [(11697, "AHEAD"), (-11697, "BEHIND")])
def test_fires_on_injected_skew(tmp_path, offset, direction):
    """Both signs abort: ahead steals siblings' claims, behind loses its own."""
    probe = tmp_path / "out"
    r = _run(
        f'carc_clock_skew_guard "{probe}"\necho REACHED_END\n',
        tmp_path, path_prefix=_date_shim(tmp_path, offset),
    )
    assert r.returncode == 3, f"guard did not abort on {offset}s skew: {r.stdout}{r.stderr}"
    assert "REACHED_END" not in r.stdout, "guard printed FATAL but let the run continue"
    assert "FATAL" in r.stdout
    assert str(offset) in r.stdout, "the message must quote the measured skew"
    assert direction in r.stdout, "the message must say which way this box is wrong"
    assert os.uname().nodename.split(".")[0] in r.stdout, "must name the offending box"
    assert str(probe) in r.stdout, "must name the directory it probed"


def test_small_skew_is_tolerated(tmp_path):
    """Sub-threshold drift is normal; aborting on it would make the guard useless."""
    probe = tmp_path / "out"
    r = _run(f'carc_clock_skew_guard "{probe}"\n', tmp_path, path_prefix=_date_shim(tmp_path, 30))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "clock-skew guard OK (30s" in r.stdout


def test_threshold_is_configurable(tmp_path):
    probe = tmp_path / "out"
    shim = _date_shim(tmp_path, 120)
    tight = _run(f'carc_clock_skew_guard "{probe}"\n', tmp_path,
                 env_extra={"CARC_CLOCK_SKEW_MAX": "10"}, path_prefix=shim)
    loose = _run(f'carc_clock_skew_guard "{probe}"\n', tmp_path,
                 env_extra={"CARC_CLOCK_SKEW_MAX": "600"}, path_prefix=shim)
    assert tight.returncode == 3, tight.stdout
    assert loose.returncode == 0, loose.stdout + loose.stderr


def test_check_reports_without_exiting(tmp_path):
    """`carc_clock_skew_check` is the handleable form -- it returns, never exits."""
    probe = tmp_path / "out"
    r = _run(
        f'rc=0; carc_clock_skew_check "{probe}" || rc=$?\necho "CHECK_RC=$rc"\n',
        tmp_path, path_prefix=_date_shim(tmp_path, 11697),
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "CHECK_RC=3" in r.stdout


def test_unprobeable_dir_warns_but_does_not_block(tmp_path):
    """Fail OPEN when the skew cannot be measured at all.

    A local-only run, or a box with no share mounted, must not be bricked by a
    guard about a share it never touches -- but it must say so out loud, so a
    silent no-op can't be mistaken for a passing check.
    """
    r = _run('carc_clock_skew_guard "/proc/definitely/not/writable"\necho REACHED_END\n', tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WARNING" in r.stdout and "UNCHECKED" in r.stdout
    assert "REACHED_END" in r.stdout


def test_explicit_disable_is_loud(tmp_path):
    """The escape hatch exists so nobody deletes the guard line; it must shout."""
    probe = tmp_path / "out"
    r = _run(f'carc_clock_skew_guard "{probe}"\necho REACHED_END\n', tmp_path,
             env_extra={"CARC_CLOCK_SKEW_DISABLE": "1"},
             path_prefix=_date_shim(tmp_path, 11697))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "DISABLED" in r.stdout and "REACHED_END" in r.stdout


def test_defaults_to_out_root_when_the_caller_set_one(tmp_path):
    probe = tmp_path / "from_out_root"
    probe.mkdir()
    r = _run('carc_clock_skew_guard\n', tmp_path, env_extra={"OUT_ROOT": str(probe)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert str(probe) in r.stdout


def test_does_not_alter_the_callers_shell_options(tmp_path):
    """Sourcing the lib must not turn `set -e` on for a launcher that runs without it.

    Several launchers deliberately use `set -uo pipefail` (no -e) so a single
    failed cell doesn't kill an overnight queue. A guard that flipped -e on
    would silently change their failure behaviour.
    """
    path = tmp_path / "noerrexit.sh"
    path.write_text(
        "set -uo pipefail\n"
        f". {LIB}\n"
        f'carc_clock_skew_guard "{tmp_path / "out"}"\n'
        "false\n"
        "echo SURVIVED_A_FAILURE\n"
    )
    r = subprocess.run(["bash", str(path)], capture_output=True, text=True, timeout=60, cwd=str(REPO))
    assert "SURVIVED_A_FAILURE" in r.stdout, r.stdout + r.stderr


# --------------------------------------------------------------------------
# 2. coverage
# --------------------------------------------------------------------------
def test_launcher_enumeration_is_not_vacuous():
    """Guard the guard: an empty list would make the coverage test green forever."""
    assert len(_shared_claim_launchers()) > 20


def test_every_shared_claim_launcher_carries_the_guard():
    missing = []
    for p in _shared_claim_launchers():
        rel = p.relative_to(REPO).as_posix()
        text = p.read_text(encoding="utf-8", errors="replace")
        if rel in INLINE_DONORS:
            ok = "CLOCK-SKEW GUARD" in text and "clock skew vs the share" in text
        else:
            ok = "clock_skew_guard.sh" in text and "carc_clock_skew_guard" in text
        if not ok:
            missing.append(rel)
    assert not missing, (
        "these launchers pass --shared-claim with NO clock-skew guard, so a box with a "
        "fast clock will steal every sibling's live claim and silently halve the cluster. "
        "Add the stanza documented at the top of scripts/measurement_infra/clock_skew_guard.sh:"
        "\n  " + "\n  ".join(missing)
    )


def test_donors_still_have_their_inline_guard():
    """The hoist must not have quietly removed the guard from where it started."""
    for rel in sorted(INLINE_DONORS):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert "CLOCK-SKEW GUARD" in text, f"{rel}: inline guard disappeared"
        assert "exit 3" in text, f"{rel}: inline guard no longer aborts"
