#!/usr/bin/env python3
"""EMIT `INSTRUMENT_IDENTITY.json` — the witness the two-rev tranche licence
requires (deviation D4.11, commit `93f83e26`).

The completion tranche (chunks 9-16) scores at a LATER REV than the committed
tranche (chunks 1-8), necessarily: the staging code that produced it did not
exist at the older rev. `merge_legs.py` keeps `git_rev`/`code_rev`
IDENTITY_REQUIRED by default and accepts exactly ONE enumerated pair — and only
when this witness also exists and asserts an EMPTY INSTRUMENT DIFF between the
two revs.

    ⚠️ NEVER HAND-WRITE THIS FILE. Every field is computed live here, and
    `merge_legs` RE-DERIVES the committed diff itself before believing any of
    it. The file is the *why* (recipe, scope, per-box working-tree state); the
    re-derivation is the *proof*. A hand-written witness would be a claim.

WHAT IT RECORDS
  revs               both full shas, resolved with `git rev-parse`
  instrument_paths   the CORRECTED set (D4.11 Amendment 2 — the proposal named
                     `scripts/tiletie/oracle_score_pilot.py`, which does NOT
                     exist; the pilot is under `scripts/measurement_infra/`, and
                     a witness over a non-existent path is VACUOUSLY TRUE)
  path_existence     every path, at BOTH revs — the generalised form of that
                     same lesson, so an empty diff can never be vacuous again
  committed_diff     `git diff` between the two revs, scoped to those paths,
                     PLUS the recipe as a runnable string so a reader re-derives
                     rather than trusts
  working_tree       ⚠️ D4.11 Amendment 3: `git diff A..B` compares COMMITS and
                     is BLIND to uncommitted dirt in the instrument scripts, so
                     `git status --porcelain` scoped to the same paths is
                     captured PER BOX at witness time

THE LAPTOP BOX. `--box laptop:laptop-wsl` captures the remote porcelain over
ssh in the path-stable `git -C <abs>` form (Claude Code drops `cd` from ssh
commands — see CLAUDE.md). Without it the file records the local box only, and
the laptop capture stays an executor step: the tranche is TWO-BOX, so a
local-only witness covers only half the working trees.
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import merge_legs as ML  # noqa: E402  (the licence + path list live there, once)

REPO = ML.REPO
SCHEMA = ML.INSTRUMENT_IDENTITY_SCHEMA


def _git(repo, *args, host=None) -> tuple:
    """(rc, stdout, stderr). Remote calls use `git -C <abs>` — never a `cd`."""
    cmd = ["git", "-C", str(repo), *args]
    if host:
        cmd = ["ssh", host, " ".join(_q(c) for c in cmd)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def _q(s: str) -> str:
    return s if all(c.isalnum() or c in "-_/.=:" for c in s) else "'" + s.replace("'", "'\\''") + "'"


def _die(msg: str) -> "NoReturn":  # noqa: F821
    raise SystemExit(f"REFUSING: {msg}")


def resolve_revs(repo, revs: dict) -> dict:
    out = {}
    for name, sha in sorted(revs.items()):
        rc, full, err = _git(repo, "rev-parse", f"{sha}^{{commit}}")
        if rc != 0:
            _die(f"{name}: {sha} does not resolve in {repo} ({err.strip()})")
        full = full.strip()
        if not full.lower().startswith(str(sha).lower()[:8]):
            _die(f"{name}: {sha} resolved to {full}, which is not a prefix match")
        rc, subject, _ = _git(repo, "log", "-1", "--format=%H%n%cI%n%s", full)
        lines = subject.splitlines()
        out[name] = {
            "sha": full, "short": full[:8],
            "committed_utc": lines[1] if len(lines) > 1 else None,
            "subject": lines[2] if len(lines) > 2 else None,
        }
    return out


def path_existence(repo, shas) -> dict:
    """Every instrument path must EXIST at both revs — Amendment 2, generalised.
    An "empty diff" over a path that is not there is vacuously true."""
    out, missing = {}, []
    for path in ML.INSTRUMENT_PATHS:
        row = {}
        for sha in shas:
            rc, listing, _ = _git(repo, "ls-tree", "-r", "--name-only", sha, "--", path)
            n = len([ln for ln in listing.splitlines() if ln.strip()])
            row[sha[:8]] = {"present": rc == 0 and n > 0, "n_tracked_files": n}
            if not row[sha[:8]]["present"]:
                missing.append((path, sha[:8]))
        out[path] = row
    if missing:
        _die(f"instrument path(s) absent at a licensed rev: {missing} — a "
             f"witness over a path that does not exist is VACUOUSLY TRUE "
             f"(D4.11 Amendment 2). Fix the path list, do not emit.")
    return out


def committed_diff(repo, a: str, b: str) -> dict:
    rc, names, err = _git(repo, "diff", "--name-only", a, b, "--", *ML.INSTRUMENT_PATHS)
    if rc != 0:
        _die(f"git diff failed: {err.strip()}")
    changed = [ln for ln in names.splitlines() if ln.strip()]
    rc, stat, _ = _git(repo, "diff", "--stat", a, b, "--", *ML.INSTRUMENT_PATHS)
    return {
        "recipe": "git -C " + str(repo) + " diff --name-only " + a + " " + b
                  + " -- " + " ".join(ML.INSTRUMENT_PATHS),
        "recipe_note": "re-run this; it must print nothing. merge_legs.py runs "
                       "the same comparison itself before honouring the licence.",
        "rev_a": a, "rev_b": b, "paths": list(ML.INSTRUMENT_PATHS),
        "n_files_changed": len(changed), "files_changed": changed[:50],
        "stat": stat.strip(), "empty": not changed,
    }


def working_tree(repo, *, box: str, host=None) -> dict:
    rc, porcelain, err = _git(repo, "status", "--porcelain", "--",
                              *ML.INSTRUMENT_PATHS, host=host)
    if rc != 0:
        _die(f"box {box}: git status failed ({err.strip()}) — a box whose "
             f"working tree cannot be read is NOT witnessed, and a missing "
             f"capture must never read as clean")
    rc2, head, _ = _git(repo, "rev-parse", "HEAD", host=host)
    lines = [ln for ln in porcelain.splitlines() if ln.strip()]
    return {
        "box": box, "host": host or platform.node(), "repo": str(repo),
        "via": "ssh" if host else "local",
        "head": head.strip() if rc2 == 0 else None,
        "porcelain": "\n".join(lines), "n_entries": len(lines),
        "clean": not lines,
        "scope": list(ML.INSTRUMENT_PATHS),
        "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def build(repo=REPO, *, boxes=(("local", None),), revs=None) -> dict:
    repo = Path(repo)
    resolved = resolve_revs(repo, revs or ML.LICENSED_TRANCHE_REVS)
    shas = sorted(v["sha"] for v in resolved.values())
    if len(shas) != 2:
        _die(f"the licence must enumerate exactly two revs, got {len(shas)}")
    by_box = {}
    for name, host in boxes:
        by_box[name] = working_tree(repo, box=name, host=host)
    doc = {
        "schema": SCHEMA,
        "run_id": ML.RUN_ID,
        "deviation": "D4.11 (measurement/tiearb_widening_20260817/DEVIATIONS.md, "
                     "commit 93f83e26)",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generator": "measurement/tiearb_widening_20260817/instrument_identity.py",
        "revs": resolved,
        "instrument_paths": list(ML.INSTRUMENT_PATHS),
        "path_existence": path_existence(repo, shas),
        "committed_diff": committed_diff(repo, shas[0], shas[1]),
        "working_tree": {
            "by_box": by_box,
            "note": "D4.11 Amendment 3 — `git diff A..B` compares COMMITS and is "
                    "blind to uncommitted dirt in the instrument scripts. The "
                    "tranche is TWO-BOX, so a witness carrying only one box "
                    "covers only half the working trees.",
        },
        "covers": "the INTERPRETED half of the instrument — AND, via `rust/` in "
                  "both the diff scope and the porcelain capture, §D4.13 "
                  "conjunct (iii), which is what lets the COMPILED half's "
                  "carc_rs_build divergence be licensed across the two tranches. "
                  "⚠️ `rust/` is therefore LOAD-BEARING here: drop it from the "
                  "path list and merge_legs refuses with R4.",
        "governance": "Measurement plumbing only. Reads no record, no value and "
                      "no statistic. Writes no governance file.",
    }
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=str(REPO))
    ap.add_argument("--out", default=None,
                    help=f"default: RUN/{ML.INSTRUMENT_IDENTITY_NAME} "
                         f"(the address D4.11 names)")
    ap.add_argument("--box", action="append", default=None,
                    help="NAME[:SSH_HOST] — repeatable. Default: local only. "
                         "Use e.g. --box local --box laptop:laptop-wsl to "
                         "capture BOTH working trees (D4.11 Amendment 3).")
    ap.add_argument("--licence", default="R4", choices=sorted(ML.LICENCE_SETS),
                    help="WHICH RUN's enumerated pair this witness is for. It "
                         "selects the pair AND the default output filename "
                         "together (R4 -> INSTRUMENT_IDENTITY.json, R5 -> "
                         "INSTRUMENT_IDENTITY_R5.json), so a witness can never "
                         "be mistaken for another run's.")
    ap.add_argument("--rev", action="append", default=None,
                    help="NAME=SHA — repeatable. ⚠️ NOT a licence: merge_legs "
                         "holds the enumerated pair and REFUSES a witness that "
                         "names a different one. Exists so the generator is "
                         "testable on a scratch repo.")
    a = ap.parse_args(argv)

    boxes = []
    for spec in (a.box or ["local"]):
        name, _, host = spec.partition(":")
        boxes.append((name, host or None))

    revs = ML.LICENCE_SETS[a.licence]
    if a.rev:
        revs = {}
        for spec in a.rev:
            name, sep, sha = spec.partition("=")
            if not sep:
                _die(f"--rev wants NAME=SHA, got {spec!r}")
            revs[name] = sha

    doc = build(a.repo, boxes=tuple(boxes), revs=revs)
    doc["licence"] = a.licence
    out = Path(a.out or (ML.RUN_DIR / ML.IDENTITY_NAME_BY_LICENCE[a.licence]))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")

    cd = doc["committed_diff"]
    print(f"[instrument-identity] licence: {a.licence}  -> {out.name}")
    print(f"[instrument-identity] revs: "
          + ", ".join(f"{k}={v['short']}" for k, v in sorted(doc["revs"].items())))
    print(f"[instrument-identity] committed diff over {len(ML.INSTRUMENT_PATHS)} "
          f"path(s): {'EMPTY' if cd['empty'] else str(cd['n_files_changed']) + ' FILE(S) CHANGED'}")
    for name, v in sorted(doc["working_tree"]["by_box"].items()):
        print(f"[instrument-identity] working tree {name} ({v['host']}, {v['via']}): "
              f"{'clean' if v['clean'] else str(v['n_entries']) + ' DIRTY entr(ies)'}")
    if len(boxes) == 1:
        print("[instrument-identity] ⚠️ ONE BOX captured. The tranche is TWO-BOX; "
              "add --box laptop:laptop-wsl or the laptop's tree is unwitnessed.")
    print(f"[instrument-identity] -> {out}")
    return 0 if cd["empty"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
