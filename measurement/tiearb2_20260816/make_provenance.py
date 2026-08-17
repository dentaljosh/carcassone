#!/usr/bin/env python3
"""RUN_PROVENANCE.json for tiearb2_20260816 — the BLIND-ORDERING record.

It records, mechanically, that the pre-registration was committed BEFORE the
instrument, and the instrument BEFORE the pilot and before one position of the
fresh corpus was scored — the ordering DESIGN.md's banner and READ_RULE.md's
banner both assert. Git history is the proof; this file is the index into it.

  prereg     b46e7199  DESIGN.md + READ_RULE.md, committed together, before the
                       instrument, the pilot and any statistic
  corpus     3dbaa8bf  the corpus-assembly driver + the three-layer G-DISJOINT
                       gate (build only)
  instrument 504ddad1  split_tiearb2.py + analyze_tiearb2.py + the tests, with
                       the read-rule already frozen
  substrate  fccd8cb5  the run dir + WORKERS.conf + the fresh self-play
                       generation launch (CORPUS SUBSTRATE ONLY)

plus `git rev-parse HEAD` AT RUN TIME, the working-tree cleanliness of the paths
that could change a number, and the generation manifest's runtime leaf hash
(`leaf_env.resolved_leaf_hash_runtime`) — DESIGN §4.2 pins it at
`6dfffd57051690f2`, and a mismatch means the fresh games were NOT generated with
the champion leaf of record.

It reads no record, no value and no statistic.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUN_ID = "tiearb2_20260816"

#: (label, commit, what it contains) — the committed blind ordering.
ORDERING = [
    {"label": "prereg", "commit": "b46e7199",
     "files": [f"measurement/{RUN_ID}/DESIGN.md", f"measurement/{RUN_ID}/READ_RULE.md"],
     "note": ("DESIGN + READ_RULE committed in ONE commit, before the instrument, "
              "before the cost pilot, and before one position of the fresh corpus "
              "was scored by either judge.")},
    {"label": "corpus_driver", "commit": "3dbaa8bf",
     "files": ["scripts/tiletie/build_tiearb2_corpus.sh",
               "scripts/tiletie/tiearb2_corpus_lib.py",
               "scripts/tiletie/gate_disjoint.py"],
     "note": "corpus-assembly driver + the three-layer G-DISJOINT gate (build only)."},
    {"label": "instrument", "commit": "504ddad1",
     "files": ["scripts/tiletie/split_tiearb2.py",
               "scripts/tiletie/analyze_tiearb2.py",
               "tests/test_tiearb2.py"],
     "note": ("the Stage-1b instrument (split + analyser + tests), committed AFTER "
              "the read-rule was frozen.")},
    {"label": "substrate", "commit": "fccd8cb5",
     "files": [f"measurement/{RUN_ID}/run_gen.sh", f"measurement/{RUN_ID}/WORKERS.conf"],
     "note": ("run dir + WORKERS.conf + the fresh self-play generation launch. "
              "CORPUS SUBSTRATE ONLY — 0 strength games, no band, no claim id.")},
]

#: DESIGN §4.2 — the champion leaf the fresh games must have been generated with.
EXPECTED_GEN_LEAF_HASH = "6dfffd57051690f2"
#: DESIGN §9 G-LEAF — the harness leaf hash run_tiletie preflights against.
EXPECTED_HARNESS_LEAF_HASH = "a36d2e15a3b3d71d"

DEFAULT_GEN_MANIFEST = Path(f"/mnt/c/carc-shared/{RUN_ID}/gen/manifest.json")

#: Modifications under these paths could change a number; their cleanliness is
#: recorded (run_tiletie's own preflight refuses to launch on the first two).
WATCHED = ("src/carcassonne_ai/", "engine/", "scripts/tiletie/",
           "scripts/measurement_infra/")


def git(*args) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True).stdout.strip()


def commit_block(entry: dict) -> dict:
    c = entry["commit"]
    subject = git("log", "-1", "--format=%s", c)
    out = dict(entry)
    out["resolved"] = bool(subject)
    out["subject"] = subject or None
    out["committed_utc"] = git("log", "-1", "--format=%cI", c) or None
    if subject:
        touched = set(git("show", "--name-only", "--format=", c).splitlines())
        out["files_present_in_commit"] = {f: (f in touched) for f in entry["files"]}
    return out


def gen_leaf_block(path: Path) -> dict:
    if not path.is_file():
        return {"path": str(path), "present": False,
                "note": "the generation manifest was not found; the leaf hash of the "
                        "fresh self-play games could not be verified."}
    d = json.loads(path.read_text())
    # ⚠️ The hash lives at `config.teacher.resolved_leaf_hash_runtime`, NOT under
    # `leaf_env` (which carries only the CARCASSONNE_V25_* cap env vars). Verified
    # against the real manifest; the recursive search below is belt-and-braces so
    # a future manifest layout change is reported rather than silently read as
    # None -- a None here would make `matches_design_4_2` False and look like a
    # leaf mismatch when it is really a schema drift.
    found = []

    def _walk(o, path_str="$"):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "resolved_leaf_hash_runtime":
                    found.append((path_str + "." + k, v))
                _walk(v, path_str + "." + k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                _walk(v, f"{path_str}[{i}]")

    _walk(d)
    got = found[0][1] if found else None
    teacher = (d.get("config") or {}).get("teacher") or {}
    return {
        "path": str(path), "present": True,
        "resolved_leaf_hash_runtime": got,
        "found_at": [p for p, _ in found],
        "expected": EXPECTED_GEN_LEAF_HASH,
        "matches_design_4_2": bool(got == EXPECTED_GEN_LEAF_HASH),
        "leaf": teacher.get("leaf") or teacher.get("leaf_label"),
        "leaf_env": d.get("leaf_env"),
        "rules_profile": d.get("rules_profile"),
        "code_rev": d.get("code_rev"),
        "generated_utc": d.get("utc"),
        "host": d.get("host"),
        "note": ("DESIGN §4.2 pins the generation leaf at 6dfffd57051690f2. A "
                 "mismatch means the fresh games were not generated with the "
                 "champion leaf of record and the corpus is not comparable."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gen-manifest", default=str(DEFAULT_GEN_MANIFEST))
    ap.add_argument("--out", default=str(HERE / "RUN_PROVENANCE.json"))
    a = ap.parse_args(argv)

    head = git("rev-parse", "HEAD")
    porcelain = [ln for ln in git("status", "--porcelain").splitlines() if ln.strip()]
    dirty = {w: sorted(ln[3:] for ln in porcelain if ln[3:].startswith(w))
             for w in WATCHED}

    doc = {
        "schema": "carcassonne-tiearb2-provenance/v1",
        "run_id": RUN_ID,
        "design_doc": f"measurement/{RUN_ID}/DESIGN.md",
        "read_rule": f"measurement/{RUN_ID}/READ_RULE.md",
        "note": ("BLIND ORDERING, PROVEN BY GIT. The design and the read-rule were "
                 "committed together BEFORE the instrument, and the instrument BEFORE "
                 "the cost pilot and before one position of the fresh corpus was "
                 "scored. Only corpus SUBSTRATE precedes the prereg commit, which the "
                 "funding brief permits, restricted to selection metadata."),
        "committed_ordering": [commit_block(e) for e in ORDERING],
        "head_at_run_time": {
            "rev": head,
            "short": head[:8] if head else None,
            "subject": git("log", "-1", "--format=%s"),
            "committed_utc": git("log", "-1", "--format=%cI"),
            "describe": git("describe", "--always", "--dirty"),
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        },
        "working_tree": {
            "n_modified_total": len(porcelain),
            "modified_under_watched_paths": dirty,
            "clean_under_src_and_engine": not (dirty.get("src/carcassonne_ai/")
                                               or dirty.get("engine/")),
            "note": ("run_tiletie.py's own preflight REFUSES to launch when "
                     "src/carcassonne_ai/ or engine/ is modified (mixed-rev "
                     "protection, the worktree-isolation rule)."),
        },
        "generation_leaf": gen_leaf_block(Path(a.gen_manifest)),
        "harness_leaf_hash_expected": EXPECTED_HARNESS_LEAF_HASH,
        "pilot_slice": ("SPENT — the 2026-08-14 OOF run's own cost-pilot rids, already "
                        "burned for inference. The fresh corpus is untouched at pilot "
                        "time (DESIGN §10)."),
        "main_launch_authorised_by": ("the DESIGN §10 mechanical rule, evaluated in "
                                      "PILOT.json. No owner call."),
        "governance": ("Measurement only. 0 strength games on every branch. No "
                       "experiments/results.csv row, no band, no "
                       "governance/BAND_REGISTRY.csv entry, no claim id, "
                       "governance/PRODUCTION.yaml untouched."),
    }
    Path(a.out).write_text(json.dumps(doc, indent=1) + "\n")
    print(json.dumps(doc, indent=1))
    print(f"[wrote] {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
