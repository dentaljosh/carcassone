#!/usr/bin/env python3
"""Compute the B>64 rung(s) and fire the PREREG branch. Emits B128_LADDER.json.

Read-side estimator is `measurement/arb_costopt_prep/phase_b_capture.RootBoot`
(percentile ROOT bootstrap, cluster = root_id, 2000 reps, seed 20260819) —
imported, not re-derived. Ladder values come from the published primitives via
`b128_lib.ladder_row`.

    python build_ladder.py --ext /mnt/c/carc-shared/b128_offline/ext_j128 \
        [--ext /mnt/c/carc-shared/b128_offline/ext_j256] --b-max 128
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import b128_lib as L  # noqa: E402

sys.path.insert(0, os.path.join(L.WT, "measurement/arb_costopt_prep"))
from phase_b_capture import RootBoot, PHASES  # noqa: E402

DELTA_STAR = 0.030          # PREREG §4.2, fixed before reading
PHASE_CUTS_SRC = ("scripts/measurement_infra/sample_agreement_roots.py:96 verbatim, "
                  "strict-cut fall-through reproduced (k==48 and k==24 -> 'late')")


def load_ext(dirs):
    """rid -> {leg: {'values_a':[...], 'values_b':[...]}}, blocks concatenated in
    the order the --ext dirs are given (j0 ascending). Also returns the gate
    counters for G-ID-4/5/7."""
    blocks = []
    g = {"n_files": 0, "n_ok": 0, "n_crn_verified": 0, "n_checksum_ok": 0,
         "n_seed_exact": 0, "n_len_128": 0, "j0_seen": Counter(), "bad": []}
    from oracle_score_pilot import playout_seed, world_seeds
    for d in dirs:
        by = defaultdict(dict)
        for f in glob.glob(os.path.join(d, "leg*", "*.json")):
            rec = json.load(open(f))
            g["n_files"] += 1
            j0 = int(rec["j0"])
            g["j0_seen"][j0] += 1
            rid, leg = rec["rid"], int(rec["leg"])
            g["n_ok"] += bool(rec.get("ok"))
            g["n_crn_verified"] += bool(rec.get("crn_verified"))
            g["n_checksum_ok"] += bool(rec.get("checksum_ok"))
            ln = (len(rec["values_a"]) == 128 and len(rec["values_b"]) == 128)
            g["n_len_128"] += ln
            want_w = world_seeds(rid, j0 + 128, L.SALT)[j0:j0 + 128]
            want_p = [playout_seed(rid, j, L.SALT) for j in range(j0, j0 + 128)]
            se = (list(rec["world_seeds"]) == want_w
                  and list(rec["playout_seeds"]) == want_p)
            g["n_seed_exact"] += se
            if not (rec.get("ok") and ln and se) and len(g["bad"]) < 5:
                g["bad"].append({"rid": rid, "leg": leg, "j0": j0,
                                 "ok": rec.get("ok"), "len_ok": ln, "seed_ok": se,
                                 "error": rec.get("error")})
            by[rid][leg] = {"values_a": rec["values_a"], "values_b": rec["values_b"]}
        blocks.append(dict(by))
    merged = defaultdict(dict)
    for blk in blocks:
        for rid, legs in blk.items():
            for leg, v in legs.items():
                cur = merged[rid].get(leg)
                if cur is None:
                    merged[rid][leg] = {"values_a": list(v["values_a"]),
                                        "values_b": list(v["values_b"])}
                else:
                    cur["values_a"] += list(v["values_a"])
                    cur["values_b"] += list(v["values_b"])
    g["j0_seen"] = dict(g["j0_seen"])
    g["pass"] = bool(g["n_files"]
                     and g["n_ok"] == g["n_files"] == g["n_crn_verified"]
                     == g["n_checksum_ok"] == g["n_seed_exact"] == g["n_len_128"])
    return dict(merged), g


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ext", action="append", required=True)
    ap.add_argument("--b-max", type=int, default=128)
    ap.add_argument("--out", default=os.path.join(HERE, "..", "B128_LADDER.json"))
    a = ap.parse_args(argv)
    t0 = time.time()

    b_ladder = tuple(b for b in (1, 2, 4, 8, 16, 32, 64, 128, 256) if b <= a.b_max)
    out = {"artifact": "B128_LADDER",
           "prereg": "measurement/b128_offline_prep/PREREG.md",
           "generated_by": "measurement/b128_offline_prep/scripts/build_ladder.py",
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "corpus": "tiearb_widening_20260817/shared_run_r4 stratum S1, walled",
           "bands_pooled": ["135e9 (retained, 551)", "137e9 (fresh, 793)"],
           "primary_key_template": "arb_j4_E64_B{b}",
           "estimator": ("record mean; percentile ROOT bootstrap, cluster=root, "
                         "2000 reps, seed 20260819 (phase_b_capture.RootBoot, "
                         "imported not re-derived). Contrasts on the SAME draw."),
           "phase_cut_source": PHASE_CUTS_SRC,
           "judge_family_label": (
               "CL-085 rider: ABSOLUTE capture LEVELS are IN-FAMILY judge-priced "
               "(clair-puct pricing judge / tier1-greedy arbiter judge) and travel "
               "with that caveat. The rung-to-rung CONTRAST is the robust class "
               "and is what the branch reads."),
           "cross_band_label": "CL-068: corpora are NEVER pooled.",
           "b_ladder": list(b_ladder), "games_played": 0,
           "results_csv_row": ("NONE — 0 games, offline oracle-class instrument "
                               "(house precedent); no band claim either."),
           "gates": {}}

    arms = L.load_arms()
    if_by = L.load_records("clair-puct")
    arb_by = L.load_records("tier1-greedy")
    banked = L.load_banked_rows()
    ext, g_ext = load_ext(a.ext)
    out["gates"]["G_ID_4_5_7_records"] = g_ext
    out["ext_dirs"] = list(a.ext)

    # every analysed rid/leg must have an extension block
    pos0, _ = L.assemble(arms, if_by, arb_by)
    miss = [(rid, leg) for rid, p in pos0.items() for leg in p["have_legs"]
            if leg not in ext.get(rid, {})]
    out["gates"]["G_COVERAGE"] = {"n_positions": len(pos0),
                                  "n_missing_ext_legs": len(miss),
                                  "examples": miss[:5],
                                  "pass": not miss}
    if miss:
        out["branch"] = "VOID"
        out["void_reason"] = "extension block incomplete"
        json.dump(out, open(a.out, "w"), indent=1, sort_keys=True)
        print("VOID — incomplete extension:", len(miss))
        return 1

    m_new = 128 * (1 + len(a.ext))
    pos, counts = L.assemble(arms, if_by, arb_by, ext_by_rid=ext)
    out["assemble_counts"] = counts
    out["m_extended"] = m_new

    # ---- compute rows at the extended M ------------------------------------ #
    rows = []
    lens = Counter()
    for rid in sorted(pos):
        for r in pos[rid]["matrix_arb"]:
            lens[len(r)] += 1
        rows.append(L.ladder_row(pos[rid], b_ladder))
    out["gates"]["G_ID_5_matrix_len"] = {
        "arb_row_lengths": dict(lens), "expected": m_new,
        "pass": set(lens) == {m_new}}

    # ---- G-ID-2: rungs <= 64 STILL bit-identical at the extended M ---------- #
    keys = [f"arb_{s}_E{e}_B{b}" for s in ("j4", "full")
            for e in L.E_LEVELS for b in L.B_LADDER_PUBLISHED]
    cmp2 = {"n_cmp": 0, "n_bit_identical": 0, "mismatch": []}
    for row in rows:
        b = banked[row["rid"]]
        for k in keys:
            if k not in b:
                continue
            cmp2["n_cmp"] += 1
            if L.f64bits(row[k]) == L.f64bits(b[k]):
                cmp2["n_bit_identical"] += 1
            elif len(cmp2["mismatch"]) < 8:
                cmp2["mismatch"].append({"rid": row["rid"], "key": k,
                                         "ours": row[k], "banked": b[k]})
    cmp2["pass"] = bool(cmp2["n_cmp"] and cmp2["n_cmp"] == cmp2["n_bit_identical"])
    cmp2["assertion"] = ("nesting: at M=%d, sorted(sel)[:b] and sorted(eva)[:E] "
                         "for b<=64 are the SAME worlds as at M=128" % m_new)
    out["gates"]["G_ID_2"] = cmp2

    # ---- bootstrap ---------------------------------------------------------- #
    for r in rows:
        for i in range(1, len(b_ladder)):
            lo, hi = b_ladder[i - 1], b_ladder[i]
            r[f"d_{lo}_{hi}"] = r[f"arb_j4_E64_B{hi}"] - r[f"arb_j4_E64_B{lo}"]
            r[f"dfull_{lo}_{hi}"] = (r[f"arb_full_E64_B{hi}"]
                                     - r[f"arb_full_E64_B{lo}"])
            r[f"dE16_{lo}_{hi}"] = (r[f"arb_j4_E16_B{hi}"] - r[f"arb_j4_E16_B{lo}"])
    boot = RootBoot(rows)
    out["n"] = len(rows)
    out["n_roots"] = boot.g
    out["phase_counts"] = dict(Counter(r["phase_bucket"] for r in rows))

    def m_ph(p):
        return lambda r: r["phase_bucket"] == p

    def m_midlate(r):
        return r["phase_bucket"] in ("mid", "late")

    masks = {"ALL": None, "early": m_ph("early"), "mid": m_ph("mid"),
             "late": m_ph("late"), "midlate": m_midlate}

    out["ladder"] = {}
    for b in b_ladder:
        k = f"arb_j4_E64_B{b}"
        out["ladder"][f"B{b}"] = {n: boot.stat(k, mk) for n, mk in masks.items()}
    out["ladder_full"] = {
        f"B{b}": {n: boot.stat(f"arb_full_E64_B{b}", mk) for n, mk in masks.items()}
        for b in b_ladder}
    out["ladder_E16"] = {
        f"B{b}": {n: boot.stat(f"arb_j4_E16_B{b}", mk) for n, mk in masks.items()}
        for b in b_ladder}
    out["rung_steps"] = {}
    for i in range(1, len(b_ladder)):
        lo, hi = b_ladder[i - 1], b_ladder[i]
        out["rung_steps"][f"B{lo}->B{hi}"] = {
            "j4_E64": {n: boot.stat(f"d_{lo}_{hi}", mk) for n, mk in masks.items()},
            "full_E64": {n: boot.stat(f"dfull_{lo}_{hi}", mk)
                         for n, mk in masks.items()},
            "j4_E16": {n: boot.stat(f"dE16_{lo}_{hi}", mk) for n, mk in masks.items()},
            "frac_pick_changed": float(
                sum(1 for r in rows if r[f"d_{lo}_{hi}"] != 0) / len(rows)),
        }

    # ---- cumulative SPAN contrasts (more stable than a single rung step) ---- #
    spans = [(lo, hi) for lo, hi in ((16, 64), (32, 128), (64, 256), (16, 256))
             if lo in b_ladder and hi in b_ladder]
    for r in rows:
        for lo, hi in spans:
            r[f"s_{lo}_{hi}"] = r[f"arb_j4_E64_B{hi}"] - r[f"arb_j4_E64_B{lo}"]
    boot_s = RootBoot(rows)
    out["span_contrasts"] = {
        f"B{lo}->B{hi}": {n: boot_s.stat(f"s_{lo}_{hi}", mk)
                          for n, mk in masks.items()}
        for lo, hi in spans}
    out["span_note"] = ("cumulative spans across several doublings. A single rung "
                        "step is the noisiest possible read of a ladder; the span "
                        "is the same quantity accumulated. NOT pre-registered as a "
                        "branch input -- reported as trend context only.")

    # ---- G-ID-6: published B=64 LEVELS reproduce to 4 dp -------------------- #
    pub = json.load(open(os.path.join(
        L.WT, "measurement/arb_costopt_prep/PHASE_B_CAPTURE.json")))["corpus_A"]["ladder"]
    rep = {"tol": 1e-4, "cells": {}, "n_ok": 0, "n_cmp": 0}
    for b in L.B_LADDER_PUBLISHED:
        for p in ["ALL"] + PHASES:
            ours = out["ladder"][f"B{b}"][p]["value"]
            theirs = pub[f"B{b}"][p]["value"]
            ok = abs(ours - theirs) < 1e-4
            rep["n_cmp"] += 1
            rep["n_ok"] += ok
            if b == 64 or not ok:
                rep["cells"][f"B{b}/{p}"] = {"ours": ours, "published": theirs,
                                             "ok": bool(ok)}
    rep["pass"] = rep["n_ok"] == rep["n_cmp"]
    out["gates"]["G_ID_6"] = rep

    out["gates"]["all_pass"] = all(
        out["gates"][g]["pass"] for g in
        ("G_ID_4_5_7_records", "G_COVERAGE", "G_ID_5_matrix_len", "G_ID_2", "G_ID_6"))
    pre = json.load(open(os.path.join(L.WT,
                    "measurement/b128_offline_prep/GATE_IDENTITY_PRE.json")))
    out["gates"]["pre_gates"] = {k: pre[k]["pass"] for k in
                                 ("G_ID_1", "G_ID_3", "G_ID_4_generator", "G_ID_8")}
    out["gates"]["all_pass"] = bool(out["gates"]["all_pass"]
                                    and all(out["gates"]["pre_gates"].values()))

    # ---- fire the PREREG branch on the 64 -> 128 contrast ------------------- #
    step = out["rung_steps"]["B64->B128"]["j4_E64"]
    dml, dall = step["midlate"], step["ALL"]
    out["primary"] = {"delta_star": DELTA_STAR,
                      "PRIMARY_A_pooled": dall, "PRIMARY_B_midlate": dml}
    if not out["gates"]["all_pass"]:
        branch, why = "VOID", "an identity gate in PREREG §3 failed"
    elif dml["z"] is not None and dml["z"] >= 2.0 and dml["value"] > 0:
        branch, why = "LADDER-CLIMBS", "Delta_midlate >= +2 sigma"
    elif dall["z"] is not None and dall["z"] >= 2.0 and dall["value"] > 0:
        branch, why = "LADDER-CLIMBS", "Delta_ALL >= +2 sigma (pooled)"
    elif dml["z"] is not None and dml["z"] <= -2.0:
        branch, why = "LADDER-REGRESSES", "Delta_midlate <= -2 sigma"
    elif (dml["ci95"][1] is not None and dml["ci95"][1] < DELTA_STAR
          and dall["ci95"][1] is not None and dall["ci95"][1] < DELTA_STAR):
        branch, why = ("LADDER-FLAT",
                       "both 95%% CI upper bounds < delta*=%.3f" % DELTA_STAR)
    else:
        branch, why = "UNRESOLVED", "CI straddles both 0 and delta*"
    out["branch"] = branch
    out["branch_reason"] = why
    out["implication"] = (
        "CLIMBS => the B128-vs-B64 game H2H gets sized and proposed for funding. "
        "FLAT / REGRESSES / UNRESOLVED => it does not get funded on this evidence."
        if branch != "VOID" else "VOID => no number quoted; report the gate failure.")

    # ---- realized cost ------------------------------------------------------ #
    cost = {"shards": []}
    for d in a.ext:
        for mf in sorted(glob.glob(os.path.join(d, "manifest_shard*.json"))):
            m = json.load(open(mf))
            cost["shards"].append({k: m.get(k) for k in
                                   ("host", "n_ok", "n_failed", "wall_secs",
                                    "elapsed_secs_sum", "n_playouts",
                                    "secs_per_playout")})
            cost.setdefault("carc_rs_binary_sha", {})[m.get("host", "?")] = (
                m.get("preflight", {}).get("wheel", {}).get("carc_rs_binary_sha"))
            cost.setdefault("carc_rs_build", {})[m.get("host", "?")] = (
                m.get("preflight", {}).get("wheel", {}).get("carc_rs_build"))
    cost["total_new_playouts"] = sum(s["n_playouts"] or 0 for s in cost["shards"])
    cost["total_cpu_secs"] = round(sum(s["elapsed_secs_sum"] or 0
                                       for s in cost["shards"]), 1)
    cost["max_wall_secs"] = max([s["wall_secs"] or 0 for s in cost["shards"]] or [0])
    cost["secs_per_playout_realized"] = (
        round(cost["total_cpu_secs"] / cost["total_new_playouts"], 6)
        if cost["total_new_playouts"] else None)
    cost["banked_r4_secs_per_playout_preswap"] = 0.2249
    cost["speedup_vs_banked"] = (
        round(0.2249 / cost["secs_per_playout_realized"], 2)
        if cost["secs_per_playout_realized"] else None)
    cost["new_oracle_playouts"] = 0
    cost["new_oracle_note"] = ("clair-puct worlds 0..127 REUSED verbatim; the "
                               "ladder never indexes an eval world >= 128.")
    out["cost"] = cost

    out["elapsed_secs"] = round(time.time() - t0, 1)
    with open(a.out, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    rowdst = os.path.join(os.path.dirname(a.out), "per_position_b128.jsonl")
    with open(rowdst, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    print("BRANCH:", branch, "-", why)
    print("gates all_pass:", out["gates"]["all_pass"])
    for nm in ("ALL", "early", "mid", "late", "midlate"):
        c = step[nm]
        print(f"  d(64->128) {nm:>8}: {c['value']:+.4f} "
              f"[{c['ci95'][0]:+.4f},{c['ci95'][1]:+.4f}] se={c['se_root']:.4f} "
              f"z={c['z']:+.2f} n={c['n']}")
    print("wrote", os.path.abspath(a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
