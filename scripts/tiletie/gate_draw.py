#!/usr/bin/env python3
"""`G-DRAW` — the satisfiable replacement for the retired `G-CAP`. **Owned by W5**
(DESIGN §8 builder delta 2; in rev R1 this gate had no owner).

`PLAN_J_gt_4` §6's `G-CAP` asked a gate to assert that the recorded `J = 4`
subset reproduces the **deployed** rust draw. That is false by construction —
the corpus-time draw is `random.Random(sha256("tiletie-cap"|rid|20260812))`
(python) and the runtime draw is MT19937 seeded
`sha256("tiearb2-deploy-v1"|state_digest|ply|"cap")` (rust); the two are
deliberately NOT stream-identical, so the gate would fail on every healthy run.
`DESIGN.md` §5 retires it and replaces it with this gate, which asserts only
what is actually asserted-able: that the recorded subset is exactly what THIS
repo's own seeded draw produces, at the run's `git_rev`.

Per rid, all four conjuncts of `READ_RULE` §2 `G-DRAW`:

  1. `[arms_full[0]] + _seeded_cap(rid, arms_full[1:], 4)[0] == subset_j4`
     — exact list identity. ⚠️ `_seeded_cap` returns `(kept, capped, dropped)`
     WITHOUT the reference arm while `subset_j4 = [ref] + kept`; comparing the
     raw return to `subset_j4` fails on every healthy run (REVIEW_R1 defect 11).
  2. `subset_j4_id` equals `build_positions._subset_id(rid, subset_j4)`.
  3. `len(subset_j4) == min(4, len(arms_full))`.
  4. `n_mismatch == 0` over the whole corpus.

It does **NOT** assert agreement with the deployed rust draw. The population
licence for that comparison rides as rider `I7-draw-scope`, whose unverified
conjunct (the dedupe partition) is reported as a magnitude by `D-DRAW`.

Emits `{gate, n_checked, n_mismatch, ok, git_rev, ...}` — the exact spellings
`READ_RULE` §2 addresses at `RUN/GATE_DRAW.json`.

Exit codes
    0   every rid reproduces
    1   at least one mismatch (loud banner)
    2   an input is missing / unreadable
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_positions as BP                                       # noqa: E402

DEPLOYED_CAP_J = BP.DEPLOYED_CAP_J


class DrawGateInputError(RuntimeError):
    """An input the gate needs is missing or malformed (exit 2)."""


def git_rev(repo=REPO) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def recompute_subset_j4(rid: str, arms_full: list, cap_j: int = DEPLOYED_CAP_J) -> list:
    """The identity of record: reference arm force-included, `j-1` drawn
    uniformly without replacement from `arms_full[1:]` by the seeded draw."""
    kept, _capped, _dropped = BP._seeded_cap(rid, list(arms_full[1:]), cap_j)
    return [arms_full[0]] + list(kept)


def check_rid(rid: str, meta: dict, cap_j: int = DEPLOYED_CAP_J) -> dict:
    """All four per-rid conjuncts. Returns a per-rid verdict dict (no arm values
    leak into the report — only booleans and lengths)."""
    arms_full = meta.get("arms_full")
    subset = meta.get("subset_j4")
    if not arms_full or not subset:
        return {"rid": rid, "ok": False, "reason": "arms_full/subset_j4 absent",
                "identity_ok": False, "subset_id_ok": False, "size_ok": False}
    expect = recompute_subset_j4(rid, arms_full, cap_j)
    identity_ok = list(subset) == expect
    want_id = BP._subset_id(rid, list(subset))
    subset_id_ok = meta.get("subset_j4_id") == want_id
    size_ok = len(subset) == min(cap_j, len(arms_full))
    ok = identity_ok and subset_id_ok and size_ok
    return {"rid": rid, "ok": ok, "identity_ok": identity_ok,
            "subset_id_ok": subset_id_ok, "size_ok": size_ok,
            "n_arms_full": len(arms_full), "n_subset_j4": len(subset),
            "reason": None if ok else "conjunct failed"}


def run_gate(arms_paths, *, cap_j: int = DEPLOYED_CAP_J, repo=REPO) -> dict:
    """Evaluate `G-DRAW` over one or more `ARMS.json` files (S1 and S2)."""
    per_stratum, mismatches = {}, []
    n_checked = n_mismatch = 0
    n_identity = n_subset_id = n_size = 0
    for p in arms_paths:
        p = Path(p)
        if not p.is_file():
            raise DrawGateInputError(f"ARMS.json not found: {p}")
        try:
            arms = json.loads(p.read_text())
        except json.JSONDecodeError as exc:
            raise DrawGateInputError(f"{p}: not JSON ({exc})") from exc
        if not isinstance(arms, dict):
            raise DrawGateInputError(
                f"{p}: expected a rid-keyed object, got {type(arms).__name__}")
        s_checked = s_bad = 0
        for rid, meta in sorted(arms.items()):
            v = check_rid(rid, meta, cap_j)
            n_checked += 1
            s_checked += 1
            n_identity += bool(v["identity_ok"])
            n_subset_id += bool(v["subset_id_ok"])
            n_size += bool(v["size_ok"])
            if not v["ok"]:
                n_mismatch += 1
                s_bad += 1
                if len(mismatches) < 20:
                    mismatches.append(v)
        per_stratum[str(p)] = {"n_checked": s_checked, "n_mismatch": s_bad}

    return {
        "gate": "G-DRAW",
        "goal": "the recorded J=4 subset is exactly this repo's own seeded draw "
                "at the run's git_rev; it asserts NOTHING about the deployed "
                "rust draw (DESIGN §5, rider I7-draw-scope)",
        "inputs": [str(p) for p in arms_paths],
        "deployed_cap_j": cap_j,
        "cap_seed_tag": BP.CAP_SEED_TAG,
        "cap_seed_date": BP.CAP_SEED_DATE,
        "n_checked": n_checked,
        "n_mismatch": n_mismatch,
        "n_identity_ok": n_identity,
        "n_subset_id_ok": n_subset_id,
        "n_size_ok": n_size,
        "by_arms_file": per_stratum,
        "mismatch_examples": mismatches,
        "git_rev": git_rev(repo),
        "ok": n_checked > 0 and n_mismatch == 0,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arms", action="append", required=True,
                    help="ARMS.json to check (repeatable: S1 and S2)")
    ap.add_argument("--cap-j", type=int, default=DEPLOYED_CAP_J)
    ap.add_argument("--out", default=None, help="write GATE_DRAW.json here")
    a = ap.parse_args(argv)

    try:
        report = run_gate(a.arms, cap_j=a.cap_j)
    except DrawGateInputError as exc:
        print(f"\n{'=' * 70}\n[G-DRAW] COULD NOT EVALUATE: {exc}\n{'=' * 70}",
              file=sys.stderr)
        return 2

    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(report, indent=2, sort_keys=True))
        print(f"[G-DRAW] -> {a.out}")
    print(f"[G-DRAW] n_checked={report['n_checked']} "
          f"n_mismatch={report['n_mismatch']} git_rev={report['git_rev']}")
    if not report["ok"]:
        print(f"\n{'=' * 70}\n[G-DRAW] ***** GATE FAILED *****\n"
              f"[G-DRAW] {report['n_mismatch']} of {report['n_checked']} rid(s) "
              f"do not reproduce the recorded J=4 subset.\n{'=' * 70}",
              file=sys.stderr)
        return 1
    print("[G-DRAW] PASS — every recorded subset_j4 reproduces exactly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
