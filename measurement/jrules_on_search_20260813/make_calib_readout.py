#!/usr/bin/env python3
"""Apply CALIB_READ_RULE.md §3 to the J-rules calibration's SUMMARY.json, MECHANICALLY.

    make_calib_readout.py --summary calib/SUMMARY.json -o .

The whole point of this file is that the branch is computed by CODE from a rule that was
committed BEFORE any flip rate existed (`CALIB_READ_RULE.md`, commit bf0f94cf) — not chosen
by a reader who has already seen the ladder. It emits `CALIB_READOUT.json` (machine) and
`CALIB_READOUT.md` (the open-city readout's shape).

It measures nothing and plays nothing: it is a pure function from SUMMARY.json to a branch.
Written and committed BEFORE the calibration's SUMMARY.json was read, for the same reason
the rule was.

THE RULE, restated exactly as §3 states it (evaluated in order, first to fire wins), with
`f(d)` = champion-ply pick-flip POINT ESTIMATE over the full corpus at dose `d`:

  3.0 VOID          integrity fails (replay checksum / partial / hash / ladder identity)
  3.1 FINER-RUNG    f(1.0) > 0.20 STRICTLY and the 0.25 rung has not been measured
                    -> measure dose 0.25 on the same corpus, then re-enter from the top
  3.2 FUND-SMALLEST any rung f >= 0.10 -> fund EXACTLY ONE cell, the SMALLEST such dose
  3.3 NO-EXPRESSION else -> report and STOP; dose > 2.0 forbidden, mask fishing forbidden

Two readings the rule fixes explicitly, reproduced here so the code cannot drift from it:

  (a) **The bar is on the POINT ESTIMATE, not the Wilson-95 lower bound** (§2). That is the
      open-city convention, under which CL-080's `A_d0p5` was funded at a 10.09% point
      estimate whose lower bound is below 10%. A rung that clears on the point estimate but
      whose lower bound is under the bar is funded AND labelled `marginal` — a disclosure,
      never a tie-break.
  (b) **Smallest DOSE wins, not largest f** (§3.2), and exactly ONE cell is funded. §3.2
      declines DESIGN §8's two-dose provision: under CL-080 the larger rung is a larger
      perturbation with a worse prior, and this rule may not be quoted to justify it.
      Non-monotone ladders are read as measured — the smallest clearing dose still wins.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

READ_RULE_COMMIT = "bf0f94cf"          # CALIB_READ_RULE.md, committed BEFORE any arm ran
FUND_BAR = 0.10                        # §2 / §3.2, on the POINT ESTIMATE
FINER_TRIGGER = 0.20                   # §3.1, STRICTLY greater than
FINER_DOSE = 0.25                      # §3.1, the one pre-committed rung
CHAMP_LEAF_HASH = "a36d2e15a3b3d71d"   # governance/PRODUCTION.yaml

#: The ladder, fixed by CALIB_READ_RULE §1 (mask held at 31 in every rung).
DOSES = (0.5, 1.0, 2.0)
MASK = 31


def cell_name(dose: float) -> str:
    """MUST reproduce `jrules_e4_replay.DEFAULT_ARM_SPECS`' names exactly.

    Those are `d0p5` / `d1p0` / `d2p0` — one decimal place, `.` -> `p` — and the
    pre-committed finer rung is `d0p25` (TWO decimals). So: two decimals, trailing zeros
    stripped but never past the first decimal place. A plain `%g` (`d1`) or a plain
    `.rstrip('0')` (`d1.`) silently misses every whole-number dose on lookup, which is why
    `tests/test_jrules_calib_readout.py::test_cell_names_match_the_instrument` pins this
    against the instrument's own `DEFAULT_ARM_SPECS` names."""
    s = f"{dose:.2f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    return "d" + s.replace(".", "p")


def decide(cells: dict) -> dict:
    """`cells`: {name: {dose, mask, flip_rate, wilson95, flips, n}} -> verdict. Pure."""
    rates = {n: c["flip_rate"] for n, c in cells.items()}
    at_bar = [n for n, f in rates.items() if f is not None and f >= FUND_BAR]
    have_finer = cell_name(FINER_DOSE) in cells
    f_one = rates.get(cell_name(1.0))

    v = {"read_rule_commit": READ_RULE_COMMIT, "bar": FUND_BAR,
         "bar_statistic": "point estimate (CALIB_READ_RULE §2; Wilson-95 LB reported only)",
         "finer_rung_trigger": FINER_TRIGGER, "finer_rung_present": have_finer,
         "f_at_dose_1": f_one,
         "cells_at_or_above_bar": sorted(at_bar, key=lambda n: cells[n]["dose"])}

    # ---- §3.1 finer rung — fires BEFORE any funding ---------------------------
    if f_one is not None and f_one > FINER_TRIGGER and not have_finer:
        v.update({
            "branch": "FINER-RUNG",
            "fundable": False,
            "funded_cells": [],
            "next_action": (f"measure the pre-committed rung dose {FINER_DOSE:g} "
                            f"(`--arm d0p25:{FINER_DOSE:g}:{MASK}`) on the SAME corpus, seed "
                            "and budget — the instrument is resumable, so this is an added "
                            "--arm over the same output directory — then re-run this readout"),
            "why": (f"§3.1 fires: f(1.0) = {f_one:.2%} > {FINER_TRIGGER:.0%} STRICTLY and the "
                    f"dose-{FINER_DOSE:g} rung has not been measured. Per DESIGN §7(ii), if "
                    "the bundle expresses at >20% of picks at its own literal magnitudes then "
                    "the ladder's LOW end is where the decision lives — CL-080's −190 elo cell "
                    "sat at an 18.89% flip rate. NOTHING IS FUNDED until the finer rung is "
                    "measured; this is the only rung addition the rule authorises and it "
                    "fires at most once."),
        })
        return v

    # ---- §3.2 FUND-SMALLEST ---------------------------------------------------
    if at_bar:
        chosen = min(at_bar, key=lambda n: cells[n]["dose"])
        c = cells[chosen]
        lo = c["wilson95"][0]
        marginal = lo < FUND_BAR
        v.update({
            "branch": "FUND-SMALLEST",
            "fundable": True,
            "chosen_cell": chosen,
            "chosen_dose": c["dose"],
            "funded_cells": [chosen],
            "marginal": marginal,
            "why": (f"§3.2 fires: {len(at_bar)} rung(s) reach f >= {FUND_BAR:.0%} on the point "
                    f"estimate. The SMALLEST such dose is {c['dose']:g} "
                    f"(f = {c['flip_rate']:.2%}, {c['flips']}/{c['n']}), so that is the named "
                    "dose and EXACTLY ONE cell is funded. Larger rungs are not funded however "
                    "much better they express: per CL-080 (open-city flipped 10.09% -> −53.8 "
                    "elo and 18.89% -> −190.3 elo at the deploy budget) clearing the bar buys "
                    "RESOLVABILITY, NOT SAFETY, and a bigger flip rate is a bigger risk."),
        })
        return v

    # ---- §3.3 NO-EXPRESSION ---------------------------------------------------
    best = max((f for f in rates.values() if f is not None), default=0.0)
    v.update({
        "branch": "NO-EXPRESSION",
        "fundable": False,
        "funded_cells": [],
        "best_flip_rate": best,
        "all_zero": best == 0.0,
        "why": (f"§3.3 fires: every rung of the ladder is below the {FUND_BAR:.0%} bar (best "
                f"{best:.2%}). The finding is 'the J-rules bundle does not express at deploy "
                "depth' — report the full ladder with CIs and realized n, flip the LEVER_INDEX "
                "row to a MEASURED 'does not express at search depth', and STOP. Explicitly "
                "forbidden by §3.3: inflating the dose above 2.0 to force expression (above "
                "2.0 it is a different evaluator, not the champion's leaf plus his strategy), "
                "fishing through jrules_mask ablations for a clearing combination, and funding "
                "on the depth-1 greedy proxy. This is NOT a refutation of the anchor's "
                "strategy — it is the measured statement that, as an additive leaf term at "
                "these doses, it does not change what an 11,008-sim search plays."),
    })
    return v


def build(summary: dict) -> dict:
    knobs = summary.get("arm_knobs", {})
    cells = {}
    for name, per in summary["arms"].items():
        k = knobs.get(name, {})
        cells[name] = {
            "dose": float(k.get("dose", 0.0)), "mask": int(k.get("mask", 0)),
            "rules": k.get("rules"), "leaf_hash": k.get("leaf_hash"),
            "flips": per["flips_total"], "n": per["n_graded"],
            "flip_rate": per["flip_rate"], "wilson95": per["wilson95"],
            "wilson95_half_width": per["wilson95_half_width"],
            "phase_split": per["phase_split"],
        }

    # The ladder actually run must BE the pre-registered ladder (optionally plus the ONE
    # pre-committed finer rung). Anything else is a different calibration wearing this
    # one's name.
    expected = {cell_name(d) for d in DOSES}
    allowed = expected | {cell_name(FINER_DOSE)}
    if not (expected <= set(cells) <= allowed):
        raise SystemExit(
            "REFUSING TO READ: the SUMMARY's cells are not the pre-registered ladder.\n"
            f"  required: {sorted(expected)}\n"
            f"  allowed extra: {cell_name(FINER_DOSE)} (§3.1's pre-committed rung only)\n"
            f"  observed: {sorted(cells)}\n"
            "CALIB_READ_RULE §4 fixes the ladder and the mask; a readout over a different "
            "grid would be a new calibration wearing this one's name.")
    knobs_ok = all(cells[cell_name(d)]["dose"] == d for d in DOSES) and \
        all(c["mask"] == MASK for c in cells.values())

    verdict = decide(cells)
    integrity = {
        "ladder_is_preregistered": knobs_ok,
        "required_cells": sorted(expected),
        "observed_cells": sorted(cells, key=lambda n: cells[n]["dose"]),
        "masks_all_jr_all": all(c["mask"] == MASK for c in cells.values()),
        "all_replay_scores_match": summary["all_replay_scores_match"],
        "replay_scores_mismatch_archives": summary["replay_scores_mismatch_archives"],
        "n_games": summary["n_games"],
        "n_graded_plies": summary["n_graded_plies"],
        "rules_profile_histogram": summary["rules_profile_histogram"],
        "champ_agrees_archive_rate": summary["champ_agrees_archive_rate"],
        "leaf_hashes_distinct": len({c["leaf_hash"] for c in cells.values()}) == len(cells),
        "no_cand_hash_equals_champion": all(c["leaf_hash"] != CHAMP_LEAF_HASH
                                            for c in cells.values()),
    }
    # §3.0: integrity failure VOIDS the calibration. Say so in the verdict itself.
    voids = []
    if not integrity["all_replay_scores_match"]:
        voids.append("replay checksum not clean on "
                     f"{integrity['replay_scores_mismatch_archives']}")
    if not integrity["ladder_is_preregistered"]:
        voids.append("the ladder's knobs are not the pre-registered ones")
    if not integrity["no_cand_hash_equals_champion"]:
        voids.append("a candidate leaf hash equals the champion's (silent null)")
    if not integrity["leaf_hashes_distinct"]:
        voids.append("two rungs share a leaf hash (one measurement wearing two names)")
    if voids:
        verdict = {**verdict, "branch": "VOID", "fundable": False, "funded_cells": [],
                   "void_reasons": voids,
                   "why": ("CALIB_READ_RULE §3.0: the validity gate fails — " +
                           "; ".join(voids) + ". Fix and re-run; re-running is free (no band, "
                           "no games, deterministic searches). No branch may be read off a "
                           "void run and no number from one may be quoted anywhere.")}
    return {"schema": "carcassonne-jrules-calib-readout/v1",
            "cells": cells, "verdict": verdict, "integrity": integrity}


def to_md(r: dict, summary: dict) -> str:
    v, cells, ig = r["verdict"], r["cells"], r["integrity"]
    order = sorted(cells, key=lambda n: cells[n]["dose"])
    L = []
    A = L.append
    A("# J-RULES ON SEARCH — CALIBRATION READOUT (dose selection)")
    A("")
    A(f"> **STATUS: RAN AND READ {summary.get('_read_date', '2026-08-13')}. "
      f"Branch `{v['branch']}` fired.**")
    A("> 0 games played, no deck band consumed, no elo statistic computed, no `results.csv`")
    A("> row owed, no claim minted. `governance/PRODUCTION.yaml` and")
    A("> `governance/BAND_REGISTRY.csv` untouched. The selection rule was committed in")
    A(f"> [CALIB_READ_RULE.md](CALIB_READ_RULE.md) (`{READ_RULE_COMMIT}`) **before any arm's")
    A("> flip rate was read**, together with the instrument and this rule-applier — the")
    A("> numbers below were produced against a fixed rule, not the other way round.")
    A(">")
    if v["fundable"]:
        A(f"> **Named dose: `{v['chosen_cell']}` (jrules_dose = {v['chosen_dose']:g}, mask 31)"
          f"** — DESIGN §11 **G5 is answered**; G1–G4, G6, G7 remain.")
        if v.get("marginal"):
            A("> ⚠️ **`marginal`** — the named rung clears on the point estimate while its")
            A("> Wilson-95 lower bound sits below the bar (§2). This word is carried into the")
            A("> deploy pre-registration.")
    elif v["branch"] == "FINER-RUNG":
        A("> **NOTHING IS FUNDED YET.** The pre-committed dose-0.25 rung is triggered and")
        A("> must be measured before any dose is named (§3.1).")
    elif v["branch"] == "VOID":
        A("> **VOID — no number here may be quoted.** (§3.0)")
    else:
        A("> **NO DOSE IS FUNDABLE.** The bundle does not express at deploy depth (§3.3);")
        A("> inflating the dose above 2.0 to force expression is explicitly forbidden.")
    A("")
    A("## 1. What ran")
    A("")
    A(f"{len(cells)} rungs — dose ladder {sorted(c['dose'] for c in cells.values())} with")
    A("`jrules_mask` held at **31** (`JR_ALL` = J1|J2|J5|J6|J8) — replayed the")
    A(f"**{ig['n_games']} banked E4 human-vs-champion archives**, re-running the production")
    A("search at every champion decision ply with the J-rules leaf against the production")
    A("leaf under CRN (shared agent seed, shared `_move_idx`), recording whether the **pick")
    A("changes**. Every candidate rung and the champion share ONE champion search per ply, so")
    A(f"all rungs are compared against the same pick. Each rung graded")
    A(f"**{ig['n_graded_plies']:,} champion plies**. Instrument:")
    A("[`jrules_e4_replay.py`](../../scripts/classical_search/jrules_e4_replay.py).")
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
    A("| rung | `jrules_dose` | flip rate | flips / n | Wilson-95 | clears 10% bar? |")
    A("|---|---|---|---|---|---|")
    for n in order:
        c = cells[n]
        lo, hi = c["wilson95"]
        clears = "**yes**" if (c["flip_rate"] or 0.0) >= FUND_BAR else "no"
        if (c["flip_rate"] or 0.0) >= FUND_BAR and lo < FUND_BAR:
            clears += " <br><sub>(point estimate; LB below bar → `marginal`)</sub>"
        A(f"| `{n}` | {c['dose']:g} | **{c['flip_rate']:.2%}** | {c['flips']}/{c['n']} | "
          f"{lo:.2%}–{hi:.2%} | {clears} |")
    A("")
    A("The bar is read on the **point estimate** (CALIB_READ_RULE §2 — the open-city")
    A("convention, under which CL-080's funded `A_d0p5` cleared at 10.09%); the Wilson-95")
    A("interval is reported alongside, as the rule requires.")
    A("")
    A("**The CL-080 anchor, for scale:** the open-city term's funded arms flipped **10.09%**")
    A("and **18.89%** of champion picks on this same corpus with this same statistic, and")
    A("then cost **−53.8 elo** (margin z −5.86) and **−190.3 elo** (z −19.38) at the deploy")
    A("budget. Read this ladder against that: a flip rate says the cell will RESOLVE, not")
    A("that it will resolve positive.")
    A("")
    A("## 3. Verdict against the committed rule")
    A("")
    A(f"**§3 branch `{v['branch']}` fires.** {v['why']}")
    A("")
    if v["fundable"]:
        A(f"- **Named dose: `{v['chosen_cell']}` — `jrules_dose = {v['chosen_dose']:g}`, "
          f"`jrules_mask = 31`.** Exactly one cell (§3.2 declines DESIGN §8's two-dose")
        A("  provision, and this readout may not be quoted to justify a second).")
        A("- The funded cell inherits DESIGN §8 in full: k8×1376 both arms, `rust`, `fixed_v1`")
        A("  + R9, `--exact-k 2`, n = 800 deck-paired, **margin z primary**, on a **fresh**")
        A("  band registered in `governance/BAND_REGISTRY.csv` before game 1, with O0–O12 +")
        A("  O4′ read from the manifest before any strength number is opened.")
        if v.get("marginal"):
            A("- ⚠️ **`marginal`:** the named rung's Wilson-95 lower bound is below the bar.")
            A("  The rule funds on the point estimate and has been applied exactly as written;")
            A("  the label is carried forward so a later null cannot be read as 'the term does")
            A("  not express' when it was funded at the edge of the floor.")
        A("- Still ⛔ before launch: DESIGN §11 **G1, G2, G3, G4, G6, G7**. G5 is now answered.")
    elif v["branch"] == "FINER-RUNG":
        A(f"- **Next action (mechanical):** {v['next_action']}.")
        A("- Nothing may be funded until that rung is measured and this readout is re-run.")
    elif v["branch"] == "VOID":
        for reason in v.get("void_reasons", []):
            A(f"- ⛔ {reason}")
    else:
        A("- **Funded: nothing. No dose is named, and none should be.** Picking the highest-f")
        A("  rung anyway would be exactly the forking path the rule forbids.")
        A("- ⛔ Dose > 2.0 is forbidden (§3.3): above 2.0 this is a different evaluator, not")
        A("  the champion's leaf plus his strategy.")
        A("- ⛔ No mask-ablation fishing for a clearing combination; every mask is a fresh")
        A("  multiple comparison against the same corpus.")
        A("- ✅ This is a real answer to the confound the Joshua-bot tournament left behind,")
        A("  not a routine null — write it up as one.")
    A("")
    A("## 4. Secondary observations (descriptive; NOT inputs to the funding decision)")
    A("")
    A("CALIB_READ_RULE §4 bars \"where the flips land\" from the funding decision, precisely")
    A("because it is the kind of finding that could be used to rescue a rung failing the bar.")
    A("")
    for n in order:
        c = cells[n]
        ps = c["phase_split"]
        if c["flips"]:
            A(f"- `{n}`: {c['flips']} flips — {ps['tiles']} tile-phase, "
              f"{ps['meeples']} meeple-phase"
              + (f" ({ps['tile_share']:.0%} tiles)" if ps["tile_share"] is not None else ""))
    A("")
    A("## 5. What this does NOT say")
    A("")
    A("1. **Flip rate is not strength.** A changed pick is not a better pick, and a flip may")
    A("   be free in EV. Nothing here predicts the sign of anything — and per CL-080 the one")
    A("   time this statistic was followed to a deploy cell, both funded arms went NEGATIVE.")
    A("2. **The expressiveness table is not a flip rate.** DESIGN §6's 95%-of-states / mean")
    A("   |T| ≈ 3.03 counts leaf VALUES on a random-play corpus at depth 0; this counts")
    A("   DECISIONS that change under an 11,008-sim search on real human games.")
    A("3. **The depth-1 greedy probe is not this statistic either** (DESIGN §6's")
    A("   `jr_dose_probe.py`: 0.25 → 12.5%, 0.5 → 18.8%, 1.0 → 25.0% over 32 positions).")
    A("   It was known before the rule was written and the rule forbids funding on it.")
    A("4. **A null on the bundle is not a null on any single rule** — J8 fires on 3% of")
    A("   states (DESIGN §6) and the mask was held at 31 throughout.")
    A("5. **Mixed rules epochs and mixed budgets** across the archives (each replayed at its")
    A("   own) make this a pooled *expressiveness* measure, not a per-epoch estimate.")
    A("6. **Nothing here licenses a strength claim.** Per **CL-079**, only a deploy-budget")
    A("   cell on its own fresh band can produce a kill or an adoption sentence.")
    A("")
    A("## 6. Rung identity (provenance)")
    A("")
    A("| rung | `jrules_dose` | `jrules_mask` | rules | `cand_leaf_hash` |")
    A("|---|---|---|---|---|")
    for n in order:
        c = cells[n]
        A(f"| `{n}` | {c['dose']:g} | {c['mask']} | {'|'.join(c['rules'] or [])} | "
          f"`{c['leaf_hash']}` |")
    A("")
    A(f"All distinct: {ig['leaf_hashes_distinct']}. None equals the champion")
    A(f"`{CHAMP_LEAF_HASH}`: {ig['no_cand_hash_equals_champion']}. Ladder is the")
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
