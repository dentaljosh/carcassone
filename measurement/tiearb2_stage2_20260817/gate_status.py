#!/usr/bin/env python3
"""Is a deferred reconcile gate already satisfied, for the CODE THAT IS HERE NOW?

`deferred_full_gates.sh` calls this before each gate so a re-launch after a kill
does not re-pay work that is already banked. It prints one word on stdout —
`SKIP` or `RUN` — plus a human-readable reason on stderr, and exits 0 either way
(a non-zero exit means the check itself broke, and the caller must then RUN).

The whole point is that "already banked" is a claim about a BINARY and a SOURCE
TREE, not about a filename. A G6 PASS certifies the `carc_rs` .so it actually
ran against; if the .so or the Python side moved since, the PASS says nothing
about today and the gate has to run again.

  backend   `measurement/rustport_p6/G6_backend_run.json`
            SKIP iff verdict == PASS
                 AND the recorded `carc_rs_binary_sha` == the installed one
                 AND `git diff --quiet <its git_rev>..HEAD -- src/ engine/
                     scripts/rustport/` (Python side unmoved; the .so hash
                     already covers the Rust side, and covers it better than a
                     git rev does — see the build-id note below)

  exact     `measurement/rustport_exact_solver/G7_exact_solver_<tag>.json`
            same rules, minus the backend-only fields.

⚠️ DO NOT substitute `carc_rs_build_id()` for the binary sha here. That id is
GIT-derived (`carc_rs-<ver>+<git rev>+<rustc>`), so it moves on every commit
whether or not the wheel was rebuilt, and does NOT move when the wheel IS
rebuilt from an unchanged tree. Verified 2026-08-23: the installed .so is
byte-identical to the one G6 passed on (sha a4318fd5…), while its build id had
already drifted a97c5dab -> 0966be03 purely from commits. The sha is the honest
witness; the build id is a label.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# Paths whose movement invalidates a banked reconcile PASS. The Rust side is
# deliberately absent: the installed .so's sha is checked directly, which is
# stronger than asking git whether rust/ moved.
PY_GUARD_PATHS = ["src/", "engine/", "scripts/rustport/"]


def installed_binary_sha() -> str:
    sys.path.insert(0, str(REPO / "src"))
    from carcassonne_ai.rust_agent import carc_rs_binary_sha
    return carc_rs_binary_sha()


def _diff_names(*args: str) -> tuple[bool, list[str]]:
    d = subprocess.run(["git", "-C", str(REPO), "diff", "--name-only", *args,
                        "--", *PY_GUARD_PATHS], capture_output=True, text=True)
    if d.returncode != 0:
        return False, [f"git diff failed: {d.stderr.strip()[:200]}"]
    return True, [x for x in d.stdout.split() if x]


def git_paths_unmoved(rev: str, allow_dirty: bool) -> tuple[bool, str]:
    rev = rev.split("-")[0]  # strip a "-dirty" suffix
    ok = subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", f"{rev}^{{commit}}"],
                        capture_output=True)
    if ok.returncode != 0:
        return False, f"git rev {rev!r} is not in this repo"

    good, moved = _diff_names(f"{rev}..HEAD")
    if not good:
        return False, moved[0]
    if moved:
        return False, f"{len(moved)} guarded file(s) moved since {rev}: {moved[:5]}"

    # ⚠️ `<rev>..HEAD` compares COMMITS. It is blind to an uncommitted edit,
    # and this repo is routinely worked with a dirty src/ (multiple sessions,
    # flag-gated fixes in flight). A gate that skipped on "no commits moved"
    # while game_wrapper.py sat modified in the tree would be certifying code
    # that is not the code that will run. Fail toward RUN.
    good_w, dirty_w = _diff_names()             # unstaged
    good_i, dirty_i = _diff_names("--cached")   # staged
    if not (good_w and good_i):
        return False, (dirty_w + dirty_i)[0]
    dirty = sorted(set(dirty_w) | set(dirty_i))
    if dirty:
        if not allow_dirty:
            return False, (f"{len(dirty)} guarded file(s) are UNCOMMITTED in the "
                           f"working tree: {dirty[:5]} — pass --allow-dirty only "
                           f"if you have checked the edits cannot move this gate")
        return True, (f"guarded Python paths unmoved since {rev}; "
                      f"{len(dirty)} dirty file(s) WAIVED by --allow-dirty: {dirty[:5]}")
    return True, f"guarded Python paths unmoved since {rev} and clean in the tree"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("verdict_json", help="the banked gate verdict to trust or not")
    ap.add_argument("--require-sha", default=None,
                    help="expected carc_rs_binary_sha; default = read it from "
                         "the verdict's own env/carc_rs block")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="waive uncommitted edits under the guarded paths. OFF "
                         "by default: an uncommitted edit is still an edit, and "
                         "a banked PASS cannot vouch for code it never saw")
    args = ap.parse_args()

    def decide(word: str, why: str) -> int:
        print(word)
        print(f"[gate_status] {word}: {why}", file=sys.stderr)
        return 0

    p = Path(args.verdict_json)
    if not p.is_absolute():
        p = REPO / p
    if not p.exists():
        return decide("RUN", f"no banked verdict at {p}")
    try:
        doc = json.loads(p.read_text())
    except Exception as exc:  # noqa: BLE001
        return decide("RUN", f"{p} is unreadable ({type(exc).__name__}) — do not trust it")

    if doc.get("verdict") != "PASS":
        return decide("RUN", f"{p.name} verdict is {doc.get('verdict')!r}, not PASS")

    banked_sha = (args.require_sha
                  or (doc.get("carc_rs") or {}).get("carc_rs_binary_sha")
                  or (doc.get("env") or {}).get("carc_rs_binary_sha"))
    if not banked_sha:
        return decide("RUN", f"{p.name} records no carc_rs_binary_sha — "
                             f"it cannot vouch for today's binary")
    try:
        live_sha = installed_binary_sha()
    except Exception as exc:  # noqa: BLE001
        return decide("RUN", f"cannot hash the installed carc_rs ({exc})")
    if live_sha != banked_sha:
        return decide("RUN", f"carc_rs binary moved: banked {banked_sha} != installed {live_sha}")

    rev = ((doc.get("env") or {}).get("git_rev")
           or (doc.get("carc_rs") or {}).get("code_rev"))
    if not rev:
        return decide("RUN", f"{p.name} records no git_rev — cannot check the Python side")
    unmoved, why = git_paths_unmoved(rev, args.allow_dirty)
    if not unmoved:
        return decide("RUN", why)

    return decide("SKIP", f"{p.name} PASS is still valid — binary {live_sha[:12]} "
                          f"identical and {why}")


if __name__ == "__main__":
    raise SystemExit(main())
