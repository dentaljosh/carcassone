#!/usr/bin/env python3
"""Apply CALIB_READ_RULE.md §3 to the open-city calibration's SUMMARY.json, MECHANICALLY.

    make_calib_readout.py --summary calib/SUMMARY.json -o .

The whole point of this file is that the branch is computed by CODE from a rule that was
committed BEFORE any flip rate existed (`CALIB_READ_RULE.md`, commit 6148388) — not chosen
by a reader who has already seen the ladder. It emits `CALIB_READOUT.json` (machine) and
`CALIB_READOUT.md` (the denial readout's shape).

It measures nothing and plays nothing: it is a pure function from SUMMARY.json to a branch.

THE RULE, restated exactly as §3 states it (evaluated in order, first to fire wins), with
`f(arm, dose)` = champion-ply pick-flip rate over the full corpus:

  1. FUND-SMALLEST      any cell f >= 0.10
  2. FUND-MARGINAL      else any cell 0.05 <= f < 0.10   (underpowered BY CONSTRUCTION)
  3. STRUCTURAL-NO-FUND else f < 0.05 everywhere AND the ladder is flat
                        ("arm B's best f is less than ~2x arm C's best f")
  4. UNRESOLVED         else (f < 0.05 everywhere but the ladder is clearly rising)

Branches 3 and 4 BOTH mean: no dose is fundable. §2's arithmetic is why — below ~5% the
cell cannot produce a resolvable result at either instrument at affordable n EVEN IF THE
TERM IS GENUINELY GOOD, so running it buys a guaranteed null, a consumed deck band, and a
false "open-city shaping is dead" line in the record.

TWO PLACES THE RULE NEEDS AN EXPLICIT READING, both resolved here in the direction the rule
argues for, and both surfaced in the output rather than buried:

  (a) §3.1 says "the smallest dose and the tightest thresholds that reach f >= 0.10", then
      immediately "prefer widening the predicate over raising the dose when both reach the
      bar, and prefer the least perturbation that clears it". Those pull against each other
      only if read as one key; read as the rule argues (T is a PRODUCT of two excesses, so
      dose is the dangerous axis and §5 says bracket DOWNWARD), the ordering is:
      minimise DOSE first, then take the TIGHTEST thresholds that still clear the bar at
      that dose. Tightness is ordered by the predicate's restrictiveness: a cell whose
      (size_min, edge_min) are both >= another's is tighter. For the fixed ladder that is
      C(6,3) tighter than A(4,2) tighter than B(3,2).
  (b) §3.3's flatness test divides by arm C's best f, and arm C is EXPECTED to read ~0
      (TERM_SPEC §6 measured its predicate firing on 0.0% of golden-corpus leaf values).
      At exactly C=0 the ratio is undefined. Handled explicitly: B==0 and C==0 is FLAT
      (nothing expresses anywhere — the structural finding), while B>0 and C==0 is RISING
      (the predicate is the binding constraint — that is branch 4's whole description).
      The ambiguity is reported in the output either way.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

READ_RULE_COMMIT = "6148388"          # CALIB_READ_RULE.md, committed BEFORE any arm ran
FUND_BAR = 0.10                       # §3.1
FLOOR = 0.05                          # §2 / §3.2 / §3.3
FLAT_RATIO = 2.0                      # §3.3 "less than ~2x"

# The ladder, fixed by CALIB_READ_RULE §1. Named here so the readout can assert the
# SUMMARY it was handed is the pre-registered ladder and not some other grid.
ARMS = {"A": (4.0, 2), "B": (3.0, 2), "C": (6.0, 3)}
DOSES = (0.5, 2.0)


def cell_name(arm: str, dose: float) -> str:
    """MUST reproduce `opencity_e4_replay.DEFAULT_ARM_SPECS`' names exactly.

    Those are `A_d0p5` / `A_d2p0` — one decimal place, `.` -> `p`. A `%g` formatting
    (which would give `A_d2`) silently misses every dose-2.0 cell on lookup, so the
    format is pinned here and asserted against the observed SUMMARY keys in `build()`."""
    return f"{arm}_d{dose:.1f}".replace(".", "p")


def tighter_or_equal(x, y) -> bool:
    """Predicate x is at least as restrictive as y on BOTH axes."""
    return x[0] >= y[0] and x[1] >= y[1]


def tightness_rank(knobs) -> tuple:
    """Sort key: more restrictive first. Both axes raise restrictiveness."""
    return (-float(knobs["size_min"]), -int(knobs["edge_min"]))


def decide(cells: dict) -> dict:
    """`cells`: {name: {arm, dose, size_min, edge_min, flip_rate, flips, n}} -> verdict.

    Pure. This is the only place the branch is chosen."""
    rates = {n: c["flip_rate"] for n, c in cells.items()}
    at_bar = [n for n, f in rates.items() if f is not None and f >= FUND_BAR]
    marginal = [n for n, f in rates.items() if f is not None and FLOOR <= f < FUND_BAR]

    v = {"read_rule_commit": READ_RULE_COMMIT, "bar": FUND_BAR, "floor": FLOOR,
         "cells_at_or_above_bar": sorted(at_bar), "cells_in_marginal_band": sorted(marginal)}

    # ---- branch 1 -----------------------------------------------------------
    if at_bar:
        # (a) minimise dose first, then tightest thresholds at that dose.
        min_dose = min(cells[n]["dose"] for n in at_bar)
        pool = [n for n in at_bar if cells[n]["dose"] == min_dose]
        chosen = sorted(pool, key=lambda n: tightness_rank(cells[n]))[0]
        funded = [chosen]
        c = cells[chosen]

        # "plus one dose above and (if it also clears 0.05) one below" — at the SAME
        # thresholds. The ladder is fixed at {0.5, 2.0}: §4 forbids inventing a rung.
        above = [d for d in DOSES if d > c["dose"]]
        if above:
            nm = cell_name(c["arm"], min(above))
            if nm in cells:
                funded.append(nm)
        below = [d for d in DOSES if d < c["dose"]]
        if below:
            nm = cell_name(c["arm"], max(below))
            if nm in cells and (rates.get(nm) or 0.0) >= FLOOR:
                funded.append(nm)

        v.update({
            "branch": "FUND-SMALLEST",
            "fundable": True,
            "chosen_cell": chosen,
            "funded_cells": funded[:3],
            "why": (f"§3.1 fires: {len(at_bar)} cell(s) reach f >= {FUND_BAR:.2f}. Among "
                    f"them the smallest dose is {min_dose:g}; among cells at that dose the "
                    f"tightest predicate that still clears the bar is "
                    f"(size_min={c['size_min']:g} TILES, edge_min={c['edge_min']}). Dose is "
                    f"minimised first because T is a PRODUCT of two excesses (TERM_SPEC §5: "
                    f"bracket downward), so an equal dose perturbs the leaf's global scale "
                    f"more than for denial."),
        })
        return v

    # ---- branch 2 -----------------------------------------------------------
    if marginal:
        top = sorted(marginal, key=lambda n: rates[n], reverse=True)[:2]
        v.update({
            "branch": "FUND-MARGINAL",
            "fundable": True,
            "funded_cells": top,
            "underpowered_by_construction": True,
            "why": (f"§3.2 fires: no cell reaches {FUND_BAR:.2f}, but {len(marginal)} sit in "
                    f"[{FLOOR:.2f}, {FUND_BAR:.2f}). At most two are funded, at the "
                    f"highest-f settings. THE SCREEN'S PREREG MUST RECORD THAT IT IS "
                    f"UNDERPOWERED BY CONSTRUCTION: a null from it bounds nothing and must "
                    f"be written up as 'not resolvable at n=200', never as a kill."),
        })
        return v

    # ---- branches 3 / 4 -----------------------------------------------------
    b_best = max((rates[cell_name("B", d)] or 0.0) for d in DOSES)
    c_best = max((rates[cell_name("C", d)] or 0.0) for d in DOSES)
    if b_best == 0.0 and c_best == 0.0:
        flat, ambiguity = True, ("arm B and arm C both read EXACTLY 0. The rule's ratio "
                                 "test is undefined at 0/0; read as FLAT — nothing "
                                 "expresses anywhere, which is the structural finding "
                                 "branch 3 exists to record.")
    elif c_best == 0.0:
        flat, ambiguity = False, ("arm C reads EXACTLY 0 while arm B does not, so the "
                                 "ratio B/C is undefined (infinite). Read as RISING: a "
                                 "predicate that fires at B and never at C is the binding "
                                 "constraint branch 4 describes.")
    else:
        flat, ambiguity = (b_best < FLAT_RATIO * c_best), None

    v.update({
        "arm_B_best": b_best, "arm_C_best": c_best,
        "ladder_ratio_B_over_C": (b_best / c_best if c_best else None),
        "ladder_flat": flat,
        "ladder_ambiguity": ambiguity,
        "fundable": False,
        "funded_cells": [],
    })
    if flat:
        v.update({
            "branch": "STRUCTURAL-NO-FUND",
            "why": (f"§3.3 fires: every cell is below the {FLOOR:.0%} resolvable floor and "
                    f"the ladder is flat (arm B best {b_best:.4f} < {FLAT_RATIO:g}x arm C "
                    f"best {c_best:.4f}). NO DOSE IS FUNDABLE. Record the structural "
                    f"finding, flip LEVER_INDEX to a measured 'does not express' rather "
                    f"than a strength kill, and name the re-specified successor (a term "
                    f"keyed to WHAT OUR MOVE CHANGES) as NEVER-TRIED. ⚠️ §3.3 carries a "
                    f"pre-registered prediction that this branch firing would be a GENUINE "
                    f"SURPRISE for this term — write it up as one, not as a routine null."),
        })
    else:
        v.update({
            "branch": "UNRESOLVED",
            "why": (f"§3.4 fires: every cell is below the {FLOOR:.0%} resolvable floor, but "
                    f"the ladder is clearly rising as the predicate loosens (arm B best "
                    f"{b_best:.4f} vs arm C best {c_best:.4f}). The PREDICATE is the "
                    f"binding constraint and the tested range was too tight. NO DOSE IS "
                    f"FUNDABLE and no screen may be bought on this readout: report the "
                    f"ladder and hand the threshold choice to Joshua — going looser than "
                    f"arm B (size_min 3 at edge_min 2 already prices nearly every "
                    f"incomplete city) starts changing what the term MEANS."),
        })
    return v


def build(summary: dict) -> dict:
    arms_knobs = summary.get("arm_knobs", {})
    cells = {}
    for name, per in summary["arms"].items():
        k = arms_knobs.get(name, {})
        arm = name.split("_")[0]
        cells[name] = {
            "arm": arm, "dose": float(k.get("dose", 0.0)),
            "size_min": float(k.get("size_min", 0.0)), "edge_min": int(k.get("edge_min", 0)),
            "symmetric": k.get("symmetric"), "leaf_hash": k.get("leaf_hash"),
            "flips": per["flips_total"], "n": per["n_graded"],
            "flip_rate": per["flip_rate"], "wilson95": per["wilson95"],
            "wilson95_half_width": per["wilson95_half_width"],
            "phase_split": per["phase_split"],
        }

    # The ladder actually run must BE the pre-registered ladder.
    expected = {cell_name(a, d) for a in ARMS for d in DOSES}
    ladder_ok = set(cells) == expected
    knobs_ok = all(
        (cells[cell_name(a, d)]["size_min"], cells[cell_name(a, d)]["edge_min"]) == ARMS[a]
        and cells[cell_name(a, d)]["dose"] == d and cells[cell_name(a, d)]["symmetric"] is True
        for a in ARMS for d in DOSES) if ladder_ok else False

    if not ladder_ok:
        raise SystemExit(
            "REFUSING TO READ: the SUMMARY's cells are not the pre-registered ladder.\n"
            f"  expected: {sorted(expected)}\n  observed: {sorted(cells)}\n"
            "CALIB_READ_RULE §4 fixes the arms and the dose ladder; a readout over a "
            "different grid would be a new calibration wearing this one's name.")

    verdict = decide(cells)
    integrity = {
        "ladder_is_preregistered": ladder_ok and knobs_ok,
        "expected_cells": sorted(expected),
        "observed_cells": sorted(cells),
        "all_replay_scores_match": summary["all_replay_scores_match"],
        "replay_scores_mismatch_archives": summary["replay_scores_mismatch_archives"],
        "n_games": summary["n_games"],
        "n_graded_plies": summary["n_graded_plies"],
        "rules_profile_histogram": summary["rules_profile_histogram"],
        "champ_agrees_archive_rate": summary["champ_agrees_archive_rate"],
        "leaf_hashes_distinct": len({c["leaf_hash"] for c in cells.values()}) == len(cells),
        "no_cand_hash_equals_champion": all(
            c["leaf_hash"] != "a36d2e15a3b3d71d" for c in cells.values()),
    }
    # A failed replay checksum VOIDS the calibration (§1). Say so in the verdict itself.
    if not integrity["all_replay_scores_match"]:
        verdict = {**verdict, "branch": "VOID",
                   "fundable": False, "funded_cells": [],
                   "why": ("CALIB_READ_RULE §1: any archive that fails its replay checksum "
                           "VOIDS the whole calibration. Fix and re-run — re-running is "
                           "free (no band, no games, deterministic searches). Offending "
                           f"archives: {integrity['replay_scores_mismatch_archives']}")}
    return {"schema": "carcassonne-opencity-calib-readout/v1",
            "cells": cells, "verdict": verdict, "integrity": integrity}


def to_md(r: dict, summary: dict) -> str:
    v, cells, ig = r["verdict"], r["cells"], r["integrity"]
    L = []
    A = L.append
    A("# OPEN-CITY CALIBRATION — READOUT (dose/threshold selection)")
    A("")
    A(f"> **STATUS: RAN AND READ {summary.get('_read_date', '2026-08-13')}. "
      f"Branch `{v['branch']}` fired.**")
    A("> 0 games played, no deck band consumed, no elo statistic computed, no `results.csv`")
    A("> row owed. `governance/PRODUCTION.yaml` untouched. The selection rule was committed")
    A(f"> in [CALIB_READ_RULE.md](CALIB_READ_RULE.md) (`{READ_RULE_COMMIT}`) **before any")
    A("> arm's flip rate was read** — the numbers below were produced against a fixed rule,")
    A("> not the other way round.")
    A(">")
    if v["fundable"]:
        A(f"> **Fundable cells: {', '.join(v['funded_cells'])}.**")
    else:
        A("> **NO DOSE IS FUNDABLE.** Every cell sits below the 5% resolvable floor; per")
        A("> §2's arithmetic such a cell cannot produce a resolvable result at either")
        A("> instrument at affordable n **even if the term is genuinely good**.")
    A("")
    A("## 1. What ran")
    A("")
    A(f"Six cells — three threshold arms x two doses, `opencity_symmetric` held **True** in")
    A(f"all of them — replayed the **{ig['n_games']} banked E4 human-vs-champion archives**,")
    A("re-running the production search at every champion decision ply with the open-city")
    A("leaf against the production leaf under CRN (shared agent seed, shared `_move_idx`),")
    A("recording whether the **pick changes**. All six candidate arms and the champion arm")
    A("share ONE champion search per ply, so every arm is compared against the same pick.")
    A(f"Each cell graded **{ig['n_graded_plies']:,} champion plies**. Instrument:")
    A("[`opencity_e4_replay.py`](../../scripts/classical_search/opencity_e4_replay.py).")
    A("")
    hist = ", ".join(f"{n} `{p}`" for p, n in sorted(ig["rules_profile_histogram"].items(),
                                                     key=lambda kv: -kv[1]))
    ok = "true" if ig["all_replay_scores_match"] else "**FALSE — CALIBRATION VOID**"
    A(f"**Integrity: {ig['n_games']}/{ig['n_games']} archives replayed with "
      f"`replay_scores_match: {ok}`.** Rules epoch resolved per archive from its own stamp,")
    A(f"as required ({hist}); each archive replays at the budget it was played at. The")
    A(f"champion reproduced the archived move on "
      f"{ig['champ_agrees_archive_rate']:.1%} of graded plies.")
    A("")
    A("## 2. The ladder")
    A("")
    A("| arm | `opencity_size_min` (TILES) | `opencity_edge_min` | flip rate @ dose 0.5 | "
      "@ dose 2.0 |")
    A("|---|---|---|---|---|")
    for a in ("A", "B", "C"):
        row = []
        for d in DOSES:
            c = cells[cell_name(a, d)]
            lo, hi = c["wilson95"]
            row.append(f"**{c['flip_rate']:.2%}** ({c['flips']}/{c['n']}) "
                       f"<br><sub>95% CI {lo:.2%}–{hi:.2%}</sub>")
        lab = {"A": "A (production spec)", "B": "B (loose)", "C": "C (tight)"}[a]
        A(f"| {lab} | {ARMS[a][0]:g} | {ARMS[a][1]} | {row[0]} | {row[1]} |")
    A("")
    A("Wilson-95 CIs are reported per CALIB_READ_RULE §1. **The rule anticipated that the")
    A("bars would not be knife-edge; for one cell that expectation did not hold, and it is")
    A("the cell the rule selects — see §3.**")
    A("")
    A("## 3. Verdict against the committed rule")
    A("")
    A(f"**§3 branch `{v['branch']}` fires.** {v['why']}")
    A("")

    # --- honesty check: is the SELECTED cell's margin over the bar inside its own CI? ---
    if v.get("chosen_cell"):
        c = cells[v["chosen_cell"]]
        lo, hi = c["wilson95"]
        if lo < FUND_BAR <= c["flip_rate"]:
            alt = [n for n, cc in cells.items()
                   if cc["wilson95"][0] >= FUND_BAR and cc["dose"] == c["dose"]]
            alt = sorted(alt, key=lambda n: tightness_rank(cells[n]))
            A(f"⚠️ **THE SELECTED CELL SITS ON THE BAR.** `{v['chosen_cell']}` reads")
            A(f"**{c['flip_rate']:.2%}** against a bar of {FUND_BAR:.0%} — it clears by")
            A(f"{(c['flip_rate'] - FUND_BAR) * 100:.2f} pp, and its own Wilson-95 interval")
            A(f"({lo:.2%}–{hi:.2%}) **straddles the bar**. The rule is written on `f`, the")
            A("point estimate, and it has been applied exactly as written — rewriting it now")
            A("to read the interval instead would be precisely the after-the-numbers rule")
            A("change §5 forbids. But the consequence should be stated plainly rather than")
            A("discovered later:")
            A("")
            if alt:
                A(f"- Read on the **CI lower bound** instead, the selection would move to")
                A(f"  `{alt[0]}` (lower bound "
                  f"{cells[alt[0]]['wilson95'][0]:.2%} ≥ {FUND_BAR:.0%}) — a **looser**")
                A("  predicate at the same dose, which is the direction §3.1's own rationale")
                A("  ('prefer widening the predicate over raising the dose') points anyway.")
            A(f"- The funded pair therefore rests on a cell whose expressiveness is")
            A(f"  ~{FUND_BAR:.0%} ± {c['wilson95_half_width'] * 100:.1f} pp. If the screen it")
            A("  buys reads null, 'the term does not express' is **not** an available")
            A("  reading — the honest one is that it was funded at the edge of the floor.")
            A("- This is a decision for Joshua, not for this readout: the rule's answer is")
            A(f"  `{v['chosen_cell']}`, and the alternative is recorded, not taken.")
            A("")
    if v["fundable"]:
        A(f"- **Funded: {', '.join(v['funded_cells'])}.**")
        if v.get("underpowered_by_construction"):
            A("- ⚠️ **Underpowered by construction.** A null from this screen bounds nothing.")
    else:
        A("- **Funded: nothing. No dose is named, and none should be.** The rule's whole")
        A("  purpose is to stop a cell being bought below the floor; picking the")
        A("  highest-f cell anyway would be exactly the forking path it forbids.")
        A("- The denial precedent is why this guard is not optional: denial's")
        A("  **production-spec** arm read **4.45%** — below the floor — while a looser arm")
        A("  read **13.62%**. A default screen would have used the spec thresholds and")
        A("  bought a guaranteed null.")
    if v.get("ladder_ambiguity"):
        A(f"- ⚠️ **Rule-reading note:** {v['ladder_ambiguity']}")
    A("")
    A("## 4. Secondary observations (descriptive; NOT inputs to the funding decision)")
    A("")
    A("CALIB_READ_RULE §4 bars \"where the flips land\" from the funding decision, precisely")
    A("because it is the kind of finding that could be used to rescue a cell failing the bar.")
    A("")
    for a in ("A", "B", "C"):
        for d in DOSES:
            c = cells[cell_name(a, d)]
            ps = c["phase_split"]
            if c["flips"]:
                A(f"- `{cell_name(a, d)}`: {c['flips']} flips — "
                  f"{ps['tiles']} tile-phase, {ps['meeples']} meeple-phase"
                  + (f" ({ps['tile_share']:.0%} tiles)" if ps["tile_share"] is not None else ""))
    A("")
    c_best = max(cells[cell_name("C", d)]["flip_rate"] for d in DOSES)
    if c_best > 0:
        A("### 4b. Arm C is NOT zero — the one place the term surprised its own spec")
        A("")
        A("TERM_SPEC §6 measured the `(6 tiles, 3 edges)` predicate firing on **0.0%** of")
        A("golden-corpus leaf values, CALIB_READ_RULE §3 recorded the expectation that")
        A("\"arm C is expected to read ≈ 0\", and the capability probe reproduces that on")
        A("scripted playouts (0 of 288 sampled leaf values move, on BOTH the rust and the")
        A("python leaf). **On the real E4 boards it fires anyway:**")
        A(f"`C_d0p5` {cells[cell_name('C', 0.5)]['flip_rate']:.2%} and "
          f"`C_d2p0` {cells[cell_name('C', 2.0)]['flip_rate']:.2%} of champion plies flip.")
        A("")
        A("The read-rule asked for this explicitly — \"a nonzero arm C would itself be")
        A("information\" — so it is recorded as such. The reconciliation is that the golden")
        A("corpus and the probe's scripted playouts simply do not contain 6-tile cities with")
        A("3 open edges, while real games against a human do. **The operational lesson is")
        A("about the instruments, not the term: a predicate that reads 0.0% on the golden")
        A("corpus is not thereby inert in play, and the capability probe cannot gate an arm")
        A("whose bite it cannot reproduce** (which is why `run_calib_laptop.sh` gates on arms")
        A("A and B and merely reports C).")
        A("")
    A("## 5. What this does NOT say")
    A("")
    A("1. **Flip rate is not strength.** A changed pick is not a better pick, and a flip may")
    A("   be free in EV. Nothing here predicts the sign of anything.")
    A("2. **The wiring bite is not a flip rate.** TERM_SPEC §6's 21.9% counts leaf VALUES")
    A("   that differ on the golden corpus; this counts DECISIONS that change on the E4")
    A("   corpus. The denial precedent shows the gap is large.")
    A("3. **Mixed rules epochs and mixed budgets** across the archives (each replayed at its")
    A("   own) make this a pooled *expressiveness* measure, not a per-epoch estimate.")
    A("4. **Nothing here licenses a strength claim** and `governance/PRODUCTION.yaml` is")
    A("   untouched on every branch. Per **CL-079**, even a funded screen at the 2750")
    A("   ablation instrument is a screen — never a kill and never an adoption.")
    A("")
    A("## 6. Cell identity (provenance)")
    A("")
    A("| cell | dose | size_min | edge_min | symmetric | `cand_leaf_hash` |")
    A("|---|---|---|---|---|---|")
    for a in ("A", "B", "C"):
        for d in DOSES:
            c = cells[cell_name(a, d)]
            A(f"| `{cell_name(a, d)}` | {c['dose']:g} | {c['size_min']:g} | {c['edge_min']} "
              f"| {c['symmetric']} | `{c['leaf_hash']}` |")
    A("")
    A(f"All six distinct: {ig['leaf_hashes_distinct']}. None equals the champion")
    A(f"`a36d2e15a3b3d71d`: {ig['no_cand_hash_equals_champion']}. Ladder is the")
    A(f"pre-registered one: {ig['ladder_is_preregistered']}.")
    A("")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--summary", required=True)
    ap.add_argument("-o", "--out-dir", required=True)
    ap.add_argument("--read-date", default="2026-08-13")
    a = ap.parse_args()

    summary = json.loads(Path(a.summary).read_text())
    summary["_read_date"] = a.read_date
    r = build(summary)
    out = Path(a.out_dir)
    (out / "CALIB_READOUT.json").write_text(json.dumps(r, indent=1))
    (out / "CALIB_READOUT.md").write_text(to_md(r, summary))
    print(json.dumps(r["verdict"], indent=1))
    print(f"\nwrote {out/'CALIB_READOUT.json'} and {out/'CALIB_READOUT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
