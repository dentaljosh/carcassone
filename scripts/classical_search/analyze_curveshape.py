#!/usr/bin/env python3
"""Read the Part-A curvature probe cells and apply the PRE-REGISTERED A-readings.

Pre-registration: measurement/curve_shape_scope_20260809/PREREG_DRAFT.md Part A.

PRIMARY STATISTIC is the deck-paired point margin z. In eval_fair_puct's summary.json
that is `paired_z` (accompanying `paired_mean_margin`, always candidate-minus-opponent);
there is no key literally named `margin_z`. Elo (`elo`, `elo_sig_1sigma`) is reported
alongside, as the prereg requires.

Branch precedence, evaluated IN THIS ORDER, first that fires wins:
    INSTRUMENT-BROKEN -> KILL -> UNRESOLVABLE -> PARK -> PROMOTE

A-gate 0 (checked FIRST): C0_identity must read |elo| < 25 AND show identical leaf
hashes on both arms AND rules_profile fixed_v1 AND r9_env_ok on both arms. Fail =>
ABORT, no cell counts.

A-readings:
  A1  all of C1/C2/C3 within +/-25 elo of C0 (no |paired_z| >= 2.0)  -> SURFACE FLAT
  A2  any cell <= -40 elo with paired_z <= -2.0                      -> CURVATURE PRESENT
  A3  any cell >= +35 elo with paired_z >= +2.0                      -> HAND-PICKED WINNER
  A4  mixed, no cell past +/-2 sigma                                 -> UNRESOLVABLE
A2 and A3 can co-fire; A3 takes precedence.

⚠️ n=400 deck-paired resolves ~+/-12 elo at 1 sigma, so the +/-25 elo band is ~2 sigma.
A cell reading +20 is UNRESOLVED, not null. The script prints that caveat with the verdict.

⚠️ COMPLETION GUARD (PREREG §6.4): a cell completing <90% of its games is VOID and its
number must not be quoted (the C5 x1.75 hang produced a hang-biased +134 that looked
like a discovery).
"""
import argparse
import json
from pathlib import Path

CELLS = ["C0_identity", "C1_flattop", "C2_broadlow", "C3_hoard"]
IDENTITY = "C0_identity"


def dig(d, *path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def load(run_root: Path, cell: str, prefix: str, n_expected: int):
    d = run_root / f"{prefix}{cell}"
    s_p, m_p = d / "summary.json", d / "manifest.json"
    if not s_p.exists():
        return {"cell": cell, "present": False}
    s = json.loads(s_p.read_text())
    m = json.loads(m_p.read_text()) if m_p.exists() else {}
    rp = m.get("rules_profile") or {}
    # config.cand_leaf_hash / config.opp_leaf_hash are the CANONICAL keys the harness always
    # writes; the nested provenance blocks are fallbacks for shapes that predate them.
    cand = (dig(m, "config", "cand_leaf_hash")
            or dig(m, "config", "cand_curve_drift", "leaf_hash")
            or dig(m, "config", "champion", "netprior_leaf", "leaf_hash")
            or dig(m, "config", "champion", "curve125_leaf_provenance", "leaf_hash")
            or dig(m, "config", "champion", "leaf_hash"))
    opp = (dig(m, "config", "opp_leaf_hash")
           or dig(m, "config", "opponent", "leaf_hash")
           or dig(m, "config", "opponent", "curve125_leaf_provenance", "leaf_hash"))
    n = int(s.get("n", 0))
    return {
        "cell": cell, "present": True,
        "n": n, "n_expected": n_expected,
        "completion": (n / n_expected) if n_expected else 0.0,
        "W": s.get("W"), "D": s.get("D"), "L": s.get("L"),
        "elo": s.get("elo"), "elo_sig": s.get("elo_sig_1sigma"),
        "paired_z": s.get("paired_z"), "paired_mean_margin": s.get("paired_mean_margin"),
        "n_paired": s.get("n_paired"), "avg_diff": s.get("avg_diff"),
        "cand_leaf_hash": cand, "opp_leaf_hash": opp,
        "rules_profile": rp.get("name"), "r9_env_ok": rp.get("r9_env_ok"),
        "cand_curve": dig(m, "config", "champion", "leaf_cfg", "v29_meeple_curve"),
        "opp_curve": dig(m, "config", "opponent", "leaf_cfg", "v29_meeple_curve"),
        "band_seed_start": dig(m, "config", "band_seed_start"),
        "backend": dig(m, "config", "champion", "backend") or m.get("backend"),
    }


def verdict(rows):
    by = {r["cell"]: r for r in rows}
    notes = []

    # ---- completion guard, before anything is read ----
    void = [r["cell"] for r in rows if r.get("present") and r["completion"] < 0.90]
    if void:
        return "VOID_INCOMPLETE", f"cells below 90% completion: {void} — do not quote their numbers", notes

    c0 = by.get(IDENTITY)
    if not c0 or not c0.get("present"):
        return "PENDING", "identity cell has not completed", notes

    # ---- A-gate 0: INSTRUMENT-BROKEN, checked FIRST ----
    problems = []
    if c0["elo"] is None or abs(c0["elo"]) >= 25:
        problems.append(f"identity |elo|={abs(c0['elo']):.1f} >= 25")
    # ⚠️ MISSING evidence is NOT CONTRADICTING evidence. An unreadable hash means the analyzer
    # does not know where the harness put it -- that is a defect in THIS script, not proof the
    # instrument is broken, and calling it INSTRUMENT-BROKEN burns a band for a bug. Report it
    # as its own state so a human sees "I could not check" rather than "the check failed".
    if c0["cand_leaf_hash"] is None or c0["opp_leaf_hash"] is None:
        return "PROVENANCE-UNREADABLE", (
            f"identity cell leaf hashes could not be located in the manifest "
            f"(cand={c0['cand_leaf_hash']}, opp={c0['opp_leaf_hash']}). This is an ANALYZER "
            "path defect, not an instrument verdict: fix the lookup and re-read. The cell's "
            "games are unaffected and are NOT void."), notes
    if c0["cand_leaf_hash"] != c0["opp_leaf_hash"]:
        problems.append(f"identity leaf hashes differ: {c0['cand_leaf_hash']} vs {c0['opp_leaf_hash']}")
    for r in rows:
        if not r.get("present"):
            continue
        if r["rules_profile"] != "fixed_v1":
            problems.append(f"{r['cell']}: rules_profile={r['rules_profile']}")
        if not r["r9_env_ok"]:
            problems.append(f"{r['cell']}: r9_env_ok={r['r9_env_ok']}")
    if problems:
        return "INSTRUMENT-BROKEN", "; ".join(problems) + " => ABORT, no cell counts", notes

    off = [by[c] for c in CELLS if c != IDENTITY and by.get(c, {}).get("present")]
    if len(off) < 3:
        return "PENDING", f"only {len(off)}/3 off-production cells complete", notes

    # NOTE: elo is already candidate-minus-champion, and the identity cell's own elo is the
    # instrument's zero. The prereg says "within +/-25 elo of C0", so compare to C0, not 0.
    z0 = c0["elo"]
    for r in off:
        r["elo_vs_c0"] = r["elo"] - z0
    notes.append(f"identity cell elo {z0:+.1f} used as the instrument zero; "
                 f"'elo_vs_c0' is each cell minus that.")

    fired_a3 = [r for r in off if r["elo_vs_c0"] >= 35 and (r["paired_z"] or 0) >= 2.0]
    fired_a2 = [r for r in off if r["elo_vs_c0"] <= -40 and (r["paired_z"] or 0) <= -2.0]
    any_sig = [r for r in off if abs(r["paired_z"] or 0) >= 2.0]

    if fired_a3:
        return "A3_HAND-PICKED_WINNER", (
            "cells >= +35 elo with paired_z >= +2.0: "
            + ", ".join(f"{r['cell']} ({r['elo_vs_c0']:+.1f}, z {r['paired_z']:+.2f})" for r in fired_a3)
            + " => skip the sweep, take the candidate to S2 then S3/S4"), notes
    if fired_a2:
        return "A2_CURVATURE_PRESENT", (
            "cells <= -40 elo with paired_z <= -2.0: "
            + ", ".join(f"{r['cell']} ({r['elo_vs_c0']:+.1f}, z {r['paired_z']:+.2f})" for r in fired_a2)
            + " => production sits on a real ridge; Part B is a reasonable bet"), notes
    if not any_sig and all(abs(r["elo_vs_c0"]) <= 25 for r in off):
        return "A1_SURFACE_FLAT", (
            "all three off-production cells within +/-25 elo of the identity cell and no "
            "|paired_z| >= 2.0 => the shape response surface is FLAT AT THIS INSTRUMENT'S "
            "RESOLUTION over this neighbourhood. DO NOT FUND PART B. Wording constraint: "
            "'no shape gain >= ~35 elo is findable by a +/-35-elo screen over this "
            "neighbourhood', NEVER 'the shape is optimal'."), notes
    return "A4_UNRESOLVABLE", (
        "mixed: no cell clears its 2-sigma bar but not all sit inside +/-25 elo => PARK. "
        "Record the effect-size floor; do not fund Part B on a sub-2-sigma signal."), notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run-root", default="/mnt/c/carc-shared/curveshape_probe")
    ap.add_argument("--prefix", default="cs_")
    ap.add_argument("--n-expected", type=int, default=400)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rows = [load(Path(a.run_root), c, a.prefix, a.n_expected) for c in CELLS]
    v, why, notes = verdict(rows)
    notes.append("n=400 deck-paired resolves ~+/-12 elo at 1 sigma, so the +/-25 elo band is "
                 "~2 sigma: a cell reading +20 is UNRESOLVED, not null.")
    notes.append("C1/C2/C3 are family-generated while C0 is the LITERAL production table, so "
                 "the off-production cells share a small low-side perturbation that is not "
                 "part of the intended top-axis contrast (PREREG banner, 2nd wart).")
    out = {"verdict": v, "why": why, "notes": notes, "cells": rows}
    txt = json.dumps(out, indent=2, default=str)
    print(txt)
    if a.out:
        Path(a.out).write_text(txt + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
