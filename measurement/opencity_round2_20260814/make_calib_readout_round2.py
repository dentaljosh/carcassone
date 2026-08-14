#!/usr/bin/env python3
"""Apply round-2 CALIB_READ_RULE.md §3 to the two calibration SUMMARY.json files, MECHANICALLY.

    make_calib_readout_round2.py --sym calib/SUMMARY.json --asym calib_asym/SUMMARY.json -o .

Sibling of ../opencity_term_20260812/make_calib_readout.py (the round-1 mechanical
reader): the branch is computed by CODE from a rule committed BEFORE any flip rate
existed (CALIB_READ_RULE.md, commit 9a2abcd5), never chosen by a reader who has seen the
ladder. Emits CALIB_READOUT.json (machine) + CALIB_READOUT.md (the house shape).

THE RULE, restated exactly (§3, per FAMILY in its pre-committed least-perturbation
order, then the global cut):

  families:  C    = [C_d4p0, C_d8p0, C_d16p0]          (dose ascending)
             ACAP = [Acap1_d0p5, Acap1_d2p0, Acap3_d2p0] (dose asc, then cap asc)
             ASYM = [Asym_d0p5, Asym_d2p0]              (dose ascending)
  1. FUND-SMALLEST (per family): first cell in order with f >= 0.10.
  2. FUND-MARGINAL (per family): else the family's highest-f cell with 0.05 <= f < 0.10
     is ELIGIBLE; funded only if fewer than 2 cells were funded by rule 1 overall,
     stamped "underpowered by construction".
  3. NO-FUND (per family): else. (For family C: f < 0.05 even at dose 16 is the
     structural "does not express at <=16x dose" finding.)
  4. Global cut: at most 3 funded total, priority C > ACAP > ASYM.

  Pre-registered predictions (checked and REPORTED; prediction (b) is BINDING for ACAP):
  (a) family C's ladder crosses 10% between doses 8 and 16;
  (b) capped rates <= their uncapped round-1 counterparts at matching dose
      (Acap1_d0p5 <= 10.09%; Acap1_d2p0, Acap3_d2p0 <= 18.89%). A violation means the
      cap is not merely shrinking the perturbation: fund NOTHING from ACAP, mark SURPRISE.

  On-the-bar (mandatory, the A_d0p5 precedent): for every funded cell whose Wilson-95 CI
  straddles its bar, record the straddle AND the cell the rule would have selected on the
  CI lower bound instead. The rule is still read on f, the point estimate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

READ_RULE_COMMIT = "9a2abcd5"       # round-2 CALIB_READ_RULE.md, committed before any arm ran
FUND_BAR = 0.10
FLOOR = 0.05
MAX_FUNDED = 3
MAX_RULE1_FOR_MARGINAL = 2

# (size_min, edge_min, dose, cap, expected_hash, symmetric)
ARMS = {
    "C_d4p0":     (6.0, 3, 4.0, 0.0, "cce11e4d05f0d86e", True),
    "C_d8p0":     (6.0, 3, 8.0, 0.0, "d52332443bc35fcf", True),
    "C_d16p0":    (6.0, 3, 16.0, 0.0, "a4acf6d0925f7606", True),
    "Acap1_d0p5": (4.0, 2, 0.5, 1.0, "d3ac9cc459f6d8d7", True),
    "Acap1_d2p0": (4.0, 2, 2.0, 1.0, "a292f2cb05e45a22", True),
    "Acap3_d2p0": (4.0, 2, 2.0, 3.0, "687f99980adaeee7", True),
    "Asym_d0p5":  (4.0, 2, 0.5, 0.0, "6cfd4e4575aba1bc", False),
    "Asym_d2p0":  (4.0, 2, 2.0, 0.0, "3f05d72016d0d09c", False),
}
FAMILIES = {"C": ["C_d4p0", "C_d8p0", "C_d16p0"],
            "ACAP": ["Acap1_d0p5", "Acap1_d2p0", "Acap3_d2p0"],
            "ASYM": ["Asym_d0p5", "Asym_d2p0"]}
FAMILY_PRIORITY = ["C", "ACAP", "ASYM"]
# round-1 uncapped counterparts for prediction (b), point estimates from
# ../opencity_term_20260812/CALIB_READOUT.md §2 (A_d0p5 10.09%, A_d2p0 18.89%).
ROUND1_UNCAPPED = {"Acap1_d0p5": 0.1009, "Acap1_d2p0": 0.1889, "Acap3_d2p0": 0.1889}


def collect(sym: dict, asym: dict) -> dict:
    """arm name -> {f, ci, flips, n, hash, phase_split} pulled from the two rollups,
    with the pre-registered identity asserted (REFUSE to read a different grid)."""
    cells = {}
    for run_name, summary, want_sym in (("sym", sym, True), ("asym", asym, False)):
        knobs = summary.get("arm_knobs") or {}
        arms = summary.get("arms") or {}
        symmetries = summary.get("opencity_symmetric")
        assert symmetries == [want_sym], (
            f"REFUSING TO READ: {run_name} rollup stamps opencity_symmetric={symmetries}, "
            f"expected [{want_sym}] — an asymmetric run must never be mistaken for a "
            f"symmetric one.")
        assert summary.get("all_replay_scores_match") is True, (
            f"REFUSING TO READ: {run_name} rollup has replay checksum failures "
            f"{summary.get('replay_scores_mismatch_archives')} — CALIB_READ_RULE §1 voids "
            f"the whole calibration.")
        for name, k in knobs.items():
            exp = ARMS.get(name)
            assert exp is not None, f"REFUSING TO READ: unexpected arm {name!r} in {run_name}"
            size_min, edge_min, dose, cap, exp_hash, exp_symmetric = exp
            assert exp_symmetric is want_sym, f"arm {name} in the wrong run ({run_name})"
            got = (float(k.get("size_min")), int(k.get("edge_min")), float(k.get("dose")),
                   float(k.get("cap", 0.0)))
            assert got == (size_min, edge_min, dose, cap), (
                f"REFUSING TO READ: arm {name} knobs {got} != pre-registered "
                f"{(size_min, edge_min, dose, cap)}")
            assert k.get("leaf_hash") == exp_hash, (
                f"REFUSING TO READ: arm {name} leaf_hash {k.get('leaf_hash')} != "
                f"pre-registered {exp_hash}")
            a = arms[name]
            cells[name] = {"f": float(a["flip_rate"]), "ci": list(a["wilson95"]),
                           "flips": int(a["flips_total"]), "n": int(a["n_graded"]),
                           "hash": exp_hash, "phase_split": a.get("phase_split"),
                           "run": run_name}
    missing = set(ARMS) - set(cells)
    assert not missing, f"REFUSING TO READ: pre-registered arms missing from rollups: {missing}"
    return cells


def decide(cells: dict) -> dict:
    per_family = {}
    # prediction (b) — BINDING for ACAP
    b_violations = [n for n, r1 in ROUND1_UNCAPPED.items() if cells[n]["f"] > r1]
    for fam, order in FAMILIES.items():
        entry = {"order": order, "branch": None, "cell": None, "notes": []}
        if fam == "ACAP" and b_violations:
            entry["branch"] = "SURPRISE-NO-FUND"
            entry["notes"].append(
                f"prediction (b) VIOLATED: {b_violations} read above their uncapped round-1 "
                f"counterparts — the cap is not merely shrinking the perturbation; fund "
                f"nothing from ACAP and stop (rule §3, pre-registered).")
            per_family[fam] = entry
            continue
        fund = next((n for n in order if cells[n]["f"] >= FUND_BAR), None)
        if fund is not None:
            entry["branch"] = "FUND-SMALLEST"
            entry["cell"] = fund
        else:
            marginal = [n for n in order if FLOOR <= cells[n]["f"] < FUND_BAR]
            if marginal:
                best = max(marginal, key=lambda n: cells[n]["f"])
                entry["branch"] = "FUND-MARGINAL-ELIGIBLE"
                entry["cell"] = best
                entry["notes"].append("underpowered by construction if funded (rule §3.2)")
            else:
                entry["branch"] = "NO-FUND"
                if fam == "C":
                    entry["notes"].append(
                        "structural: the tight predicate does not express at <=16x dose on "
                        "real play (rule §3.3) — NOT a strength kill")
        per_family[fam] = entry

    rule1 = [per_family[f]["cell"] for f in FAMILY_PRIORITY
             if per_family[f]["branch"] == "FUND-SMALLEST"]
    funded = list(rule1[:MAX_FUNDED])
    marginal_funded = []
    if len(rule1) < MAX_RULE1_FOR_MARGINAL:
        for f in FAMILY_PRIORITY:
            if len(funded) >= MAX_FUNDED:
                break
            e = per_family[f]
            if e["branch"] == "FUND-MARGINAL-ELIGIBLE":
                funded.append(e["cell"])
                marginal_funded.append(e["cell"])
                e["branch"] = "FUND-MARGINAL"
    else:
        for f in FAMILY_PRIORITY:
            if per_family[f]["branch"] == "FUND-MARGINAL-ELIGIBLE":
                per_family[f]["branch"] = "MARGINAL-NOT-FUNDED"
                per_family[f]["notes"].append(
                    f">=2 rule-1 cells funded overall — marginal eligibility lapses (rule §3.2)")

    # on-the-bar recording (mandatory)
    on_the_bar = []
    for n in funded:
        bar = FUND_BAR if n not in marginal_funded else FLOOR
        lo, hi = cells[n]["ci"]
        if lo < bar <= hi:
            fam = next(f for f, o in FAMILIES.items() if n in o)
            alt = next((m for m in FAMILIES[fam] if cells[m]["ci"][0] >= bar), None)
            on_the_bar.append({
                "cell": n, "bar": bar, "f": cells[n]["f"], "wilson95": cells[n]["ci"],
                "ci_straddles_bar": True,
                "selection_on_ci_lower_bound_would_be": alt,
                "consequence": "if this cell lands null, 'the term does not express' is "
                               "NOT an available reading — it was funded at the edge of "
                               "the floor (the A_d0p5 precedent)."})

    # prediction (a) — reported, not binding
    c = {n: cells[n]["f"] for n in FAMILIES["C"]}
    pred_a = {"prediction": "family C crosses 10% between doses 8 and 16",
              "observed": c,
              "held": bool(c["C_d8p0"] < FUND_BAR <= c["C_d16p0"])}

    return {"read_rule_commit": READ_RULE_COMMIT, "per_family": per_family,
            "funded": funded, "marginal_funded": marginal_funded,
            "on_the_bar": on_the_bar, "prediction_a": pred_a,
            "prediction_b_violations": b_violations}


def to_md(r: dict, cells: dict, sym: dict, asym: dict) -> str:
    def pct(x):
        return f"{100.0 * x:.2f}%"
    L = []
    L.append("# OPEN-CITY ROUND 2 CALIBRATION — READOUT (mechanical, rule-first)\n")
    L.append(f"> **STATUS: RAN AND READ 2026-08-14.** 0 games played, no deck band consumed, no elo")
    L.append(f"> statistic computed, no `results.csv` row owed. `governance/PRODUCTION.yaml` untouched.")
    L.append(f"> The selection rule was committed in [CALIB_READ_RULE.md](CALIB_READ_RULE.md)")
    L.append(f"> (`{READ_RULE_COMMIT}`) **before any arm's flip rate was read**; this file was emitted by")
    L.append(f"> [make_calib_readout_round2.py](make_calib_readout_round2.py), a pure function from the")
    L.append(f"> two rollups to the branches.")
    fund_list = ", ".join(f"`{n}`" for n in r["funded"]) or "**none**"
    L.append(f">\n> **Fundable cells: {fund_list}.**\n")
    L.append("## 1. What ran\n")
    L.append(f"Two runs of [`opencity_e4_replay.py`](../../scripts/classical_search/opencity_e4_replay.py)")
    L.append(f"over the banked E4 archives ({sym['n_games']} archives, {sym['n_graded_plies']} champion")
    L.append(f"plies per arm, symmetric run; {asym['n_games']} / {asym['n_graded_plies']} asymmetric run),")
    L.append(f"CRN per ply, rules epoch resolved per archive"
             f" {json.dumps(sym.get('rules_profile_histogram'))}, all replay checksums clean in both runs.\n")
    L.append("## 2. The ladders\n")
    L.append("| family | cell | size_min | edge_min | dose | cap | sym | flip rate | Wilson-95 |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for fam in FAMILY_PRIORITY:
        for n in FAMILIES[fam]:
            s, e, d, cap, _h, symm = ARMS[n]
            c = cells[n]
            L.append(f"| {fam} | `{n}` | {s:g} | {e} | {d:g} | {cap:g} | "
                     f"{'T' if symm else 'F'} | **{pct(c['f'])}** ({c['flips']}/{c['n']}) | "
                     f"{pct(c['ci'][0])}–{pct(c['ci'][1])} |")
    L.append("")
    L.append("## 3. Verdict against the committed rule (per family, then the global cut)\n")
    for fam in FAMILY_PRIORITY:
        e = r["per_family"][fam]
        cell = f" → **`{e['cell']}`**" if e.get("cell") else ""
        L.append(f"- **{fam}**: branch **`{e['branch']}`**{cell}."
                 + ("".join(f" {note}" for note in e["notes"]) if e["notes"] else ""))
    L.append("")
    L.append(f"- **Prediction (a)** ({r['prediction_a']['prediction']}): "
             f"{'HELD' if r['prediction_a']['held'] else 'DID NOT HOLD'} — observed "
             f"{ {k: pct(v) for k, v in r['prediction_a']['observed'].items()} }.")
    L.append(f"- **Prediction (b)** (capped <= uncapped counterparts): "
             + ("VIOLATED by " + ", ".join(r["prediction_b_violations"])
                if r["prediction_b_violations"] else "held."))
    if r["on_the_bar"]:
        L.append("\n### ⚠️ ON-THE-BAR selections (recorded AT CALIBRATION TIME, the A_d0p5 precedent)\n")
        for o in r["on_the_bar"]:
            L.append(f"- `{o['cell']}` reads **{pct(o['f'])}** against a bar of {pct(o['bar'])} and its "
                     f"Wilson-95 ({pct(o['wilson95'][0])}–{pct(o['wilson95'][1])}) **straddles the bar**. "
                     f"On the CI lower bound the selection would be "
                     f"{('`' + o['selection_on_ci_lower_bound_would_be'] + '`') if o['selection_on_ci_lower_bound_would_be'] else '**no cell in this family**'}. "
                     f"{o['consequence']}")
    else:
        L.append("\n(No funded cell's CI straddles its bar.)")
    L.append("\n## 4. Secondary observations (descriptive; NOT inputs to the funding decision)\n")
    for fam in FAMILY_PRIORITY:
        for n in FAMILIES[fam]:
            ps = cells[n].get("phase_split") or {}
            L.append(f"- `{n}`: {cells[n]['flips']} flips — {ps.get('tiles', '?')} tile-phase, "
                     f"{ps.get('meeples', '?')} meeple-phase")
    L.append("\n## 5. What this does NOT say\n")
    L.append("1. **Flip rate is not strength.** Round 1 proved it in the sharpest way: expressiveness")
    L.append("   predicted the magnitude, not the sign, and both funded cells lost (CL-080). Nothing")
    L.append("   here predicts the sign of anything.")
    L.append("2. **Mixed rules epochs and budgets** across archives make this a pooled expressiveness")
    L.append("   measure, not a per-epoch estimate.")
    L.append("3. **Nothing licenses a strength claim**; `governance/PRODUCTION.yaml` untouched on every")
    L.append("   branch. Per CL-079, the verdict instrument is a deploy-budget cell on its own band.")
    L.append("4. **No cross-family or cross-round pooling** — three families, three falsifiers, read")
    L.append("   independently; CL-080's cells are a different candidate set on a retired band.")
    L.append("\n## 6. Cell identity (provenance)\n")
    L.append("| cell | dose | size_min | edge_min | cap | symmetric | `cand_leaf_hash` |")
    L.append("|---|---|---|---|---|---|---|")
    for fam in FAMILY_PRIORITY:
        for n in FAMILIES[fam]:
            s, e, d, cap, h, symm = ARMS[n]
            L.append(f"| `{n}` | {d:g} | {s:g} | {e} | {cap:g} | {symm} | `{h}` |")
    L.append("")
    L.append(f"All {len(ARMS)} distinct: {len({a[4] for a in ARMS.values()}) == len(ARMS)}. "
             f"None equals the champion `a36d2e15a3b3d71d`: "
             f"{all(a[4] != 'a36d2e15a3b3d71d' for a in ARMS.values())}. "
             f"Ladders are the pre-registered ones: asserted at collect() (the reader refuses "
             f"any other grid).")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sym", required=True)
    ap.add_argument("--asym", required=True)
    ap.add_argument("-o", "--out-dir", required=True)
    a = ap.parse_args()
    sym = json.load(open(a.sym))
    asym = json.load(open(a.asym))
    cells = collect(sym, asym)
    r = decide(cells)
    out = Path(a.out_dir)
    (out / "CALIB_READOUT.json").write_text(json.dumps(
        {"cells": cells, **r}, indent=2))
    (out / "CALIB_READOUT.md").write_text(to_md(r, cells, sym, asym))
    print(f"branches: { {f: r['per_family'][f]['branch'] for f in FAMILY_PRIORITY} }")
    print(f"funded: {r['funded']}")
    print(f"on-the-bar: {[o['cell'] for o in r['on_the_bar']]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
