#!/usr/bin/env python3
"""Phase 2 analysis — join ROOT_ACTION_AUDIT + MIDGAME labels + sample; emit agreement tables.

Pure offline. No game playing. Reads:
  measurement/search_policy_mixing/ROOT_ACTION_AUDIT.jsonl     (new variant roots + signals)
  measurement/midgame_reference/MIDGAME_REFERENCE_LABELS.jsonl (reused roots + teacher child-Q)
  measurement/midgame_reference/MIDGAME_POSITION_SAMPLE.jsonl  (routing context: score_diff, etc.)

Writes:
  ROOT_ACTION_RESULTS.csv             (overall per-variant agreement)
  ROOT_ACTION_RESULTS_BY_BAND.csv     (per-variant top-1 vs teacher by band)
  ROOT_ACTION_RESULTS_BY_DISAGREEMENT.csv (recovery within the 4 disagreement subsets)
  + prints by-source / by-sharpness summaries to stdout for the writeup.
"""
from __future__ import annotations
import csv
import json
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SPM = os.path.join(REPO, "measurement", "search_policy_mixing")
MID = os.path.join(REPO, "measurement", "midgame_reference")

TEACHER = "heur3200_choice"
BANDS = ["opening", "early_mid", "mid", "late_mid", "pre_endgame"]

# variant display name -> (field, source-file)   source: 'aud' | 'lab'
VARIANTS = [
    ("ITER8_PROD@200",            "iter8_choice",          "lab"),
    ("ITER8_NORESID@200(=pol+v27leaf)", "iter8_noresid_choice", "aud"),
    ("ITER8_POLICY_ROOT_ONLY",    "iter8_prior_argmax",    "lab"),
    ("V27_STATIC_ROOT_ONLY",      "v27_static_choice",     "lab"),
    ("HEUR_200",                  "heur200_choice",        "aud"),
    ("HEUR_800",                  "heur800_choice",        "lab"),
    ("HEUR_1600",                 "heur1600_choice",       "lab"),
    ("HEUR_3200(teacher)",        "heur3200_choice",       "lab"),
]


def load():
    aud = {json.loads(l)["position_id"]: json.loads(l) for l in open(os.path.join(SPM, "ROOT_ACTION_AUDIT.jsonl"))}
    lab = {json.loads(l)["position_id"]: json.loads(l) for l in open(os.path.join(MID, "MIDGAME_REFERENCE_LABELS.jsonl"))}
    smp = {json.loads(l)["position_id"]: json.loads(l) for l in open(os.path.join(MID, "MIDGAME_POSITION_SAMPLE.jsonl"))}
    rows = []
    for pid in aud:
        if pid not in lab:
            continue
        r = dict(lab[pid])
        r.update(aud[pid])             # audit fields win on key overlap (none conflict materially)
        if pid in smp:
            r["score_diff_mover"] = smp[pid].get("score_diff_mover")
        rows.append(r)
    return rows


def choice(row, field, src):
    return row.get(field)


def frac(xs):
    xs = [x for x in xs if x is not None]
    return (sum(xs) / len(xs)) if xs else float("nan")


def main():
    rows = load()
    n = len(rows)
    print(f"joined positions: {n}")

    # ---- overall agreement table ----
    out = []
    for name, fld, src in VARIANTS:
        t1_teacher = frac([1 if r.get(fld) == r[TEACHER] else 0 for r in rows])
        t1_h800    = frac([1 if r.get(fld) == r["heur800_choice"] else 0 for r in rows])
        t1_iter8   = frac([1 if r.get(fld) == r["iter8_choice"] else 0 for r in rows])
        t1_v27     = frac([1 if r.get(fld) == r["v27_static_choice"] else 0 for r in rows])
        out.append((name, n, round(t1_teacher, 4), round(t1_h800, 4), round(t1_iter8, 4), round(t1_v27, 4)))
    with open(os.path.join(SPM, "ROOT_ACTION_RESULTS.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["variant", "n", "top1_vs_teacher_h3200", "top1_vs_heur800", "top1_vs_iter8prod", "top1_vs_v27static"])
        w.writerows(out)
    print("\n=== OVERALL (vs heur@3200 teacher) ===")
    print(f"{'variant':36s} {'n':>5s} {'vs_teach':>9s} {'vs_h800':>8s} {'vs_iter8':>9s} {'vs_v27':>7s}")
    for r in out:
        print(f"{r[0]:36s} {r[1]:5d} {r[2]:9.3f} {r[3]:8.3f} {r[4]:9.3f} {r[5]:7.3f}")

    # ---- by band ----
    with open(os.path.join(SPM, "ROOT_ACTION_RESULTS_BY_BAND.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["variant"] + BANDS)
        print("\n=== top1 vs teacher BY BAND ===")
        print(f"{'variant':36s} " + " ".join(f"{b:>11s}" for b in BANDS))
        for name, fld, src in VARIANTS:
            cells = []
            for b in BANDS:
                br = [r for r in rows if r["band"] == b]
                cells.append(frac([1 if r.get(fld) == r[TEACHER] else 0 for r in br]))
            w.writerow([name] + [round(c, 4) for c in cells])
            print(f"{name:36s} " + " ".join(f"{c:11.3f}" for c in cells))

    # ---- disagreement subsets ----
    def sub_A(r): return r["iter8_choice"] != r[TEACHER]
    def sub_B(r): return r["v27_static_choice"] != r[TEACHER]
    def sub_C(r): return r["iter8_choice"] == r[TEACHER] and r["v27_static_choice"] != r[TEACHER]
    def sub_D(r): return r["v27_static_choice"] == r[TEACHER] and r["iter8_choice"] != r[TEACHER]
    SUBS = [("A: iter8 != teacher", sub_A), ("B: v27 != teacher", sub_B),
            ("C: iter8=teacher & v27!=teacher", sub_C), ("D: v27=teacher & iter8!=teacher", sub_D)]
    with open(os.path.join(SPM, "ROOT_ACTION_RESULTS_BY_DISAGREEMENT.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["subset", "n"] + [v[0] for v in VARIANTS])
        print("\n=== recovery (top1 vs teacher) WITHIN disagreement subsets ===")
        for sname, pred in SUBS:
            sr = [r for r in rows if pred(r)]
            recs = [round(frac([1 if r.get(fld) == r[TEACHER] else 0 for r in sr]), 4) for _, fld, _ in VARIANTS]
            w.writerow([sname, len(sr)] + recs)
            print(f"  [{sname}] n={len(sr)}")
            for (name, _, _), rec in zip(VARIANTS, recs):
                print(f"      {name:36s} {rec:.3f}")

    # ---- residual decomposition headline ----
    print("\n=== RESIDUAL DECOMPOSITION (prod resid0.25 vs noresid resid0, paired same seed) ===")
    agree_pn = frac([1 if r["iter8_choice"] == r["iter8_noresid_choice"] else 0 for r in rows])
    prod_t = frac([1 if r["iter8_choice"] == r[TEACHER] else 0 for r in rows])
    nores_t = frac([1 if r["iter8_noresid_choice"] == r[TEACHER] else 0 for r in rows])
    print(f"  prod==noresid root agreement: {agree_pn:.3f}  (1-this = residual flips the root pick: {1-agree_pn:.3f})")
    print(f"  prod    vs teacher: {prod_t:.3f}")
    print(f"  noresid vs teacher: {nores_t:.3f}   (delta from residual = {prod_t-nores_t:+.4f})")
    # in the subset where residual flips the pick, who is right vs teacher?
    flip = [r for r in rows if r["iter8_choice"] != r["iter8_noresid_choice"]]
    if flip:
        pf = frac([1 if r["iter8_choice"] == r[TEACHER] else 0 for r in flip])
        nf = frac([1 if r["iter8_noresid_choice"] == r[TEACHER] else 0 for r in flip])
        print(f"  on the {len(flip)} flip positions: prod-right {pf:.3f} vs noresid-right {nf:.3f}")

    # ---- equal-sims net-vs-heur ----
    print("\n=== EQUAL-SIMS @200: iter8 (net+leaf) vs heur@200 (pure search) ===")
    print(f"  iter8_prod@200  vs teacher: {prod_t:.3f}")
    print(f"  iter8_noresid@200 vs teacher: {nores_t:.3f}")
    print(f"  heur@200        vs teacher: {frac([1 if r['heur200_choice']==r[TEACHER] else 0 for r in rows]):.3f}")
    print(f"  heur@800        vs teacher: {frac([1 if r['heur800_choice']==r[TEACHER] else 0 for r in rows]):.3f}")

    # ---- by source ----
    print("\n=== top1 vs teacher BY SOURCE (key variants) ===")
    srcs = sorted(set(r["source_bucket"] for r in rows))
    key = ["ITER8_PROD@200", "ITER8_NORESID@200(=pol+v27leaf)", "HEUR_200", "HEUR_800", "V27_STATIC_ROOT_ONLY"]
    keymap = {nm: fld for nm, fld, _ in VARIANTS}
    print(f"{'source':12s} {'n':>5s} " + " ".join(f"{k.split('(')[0][:14]:>15s}" for k in key))
    for s in srcs:
        srr = [r for r in rows if r["source_bucket"] == s]
        cells = [frac([1 if r.get(keymap[k]) == r[TEACHER] else 0 for r in srr]) for k in key]
        print(f"{s:12s} {len(srr):5d} " + " ".join(f"{c:15.3f}" for c in cells))

    # ---- by sharpness (policy_top1_prob, v27_gap, n_legal) ----
    def bin_report(label, keyfn, edges):
        print(f"\n=== top1 vs teacher BY {label} ===")
        print(f"{'bin':16s} {'n':>5s} {'iter8':>7s} {'noresid':>8s} {'heur200':>8s} {'heur800':>8s} {'v27':>6s}")
        prev = None
        for e in edges + [float('inf')]:
            sel = [r for r in rows if keyfn(r) is not None and (prev is None or keyfn(r) > prev) and keyfn(r) <= e]
            lab = f"({prev},{e}]" if prev is not None else f"<= {e}"
            if sel:
                c_i = frac([1 if r["iter8_choice"]==r[TEACHER] else 0 for r in sel])
                c_n = frac([1 if r["iter8_noresid_choice"]==r[TEACHER] else 0 for r in sel])
                c_h2 = frac([1 if r["heur200_choice"]==r[TEACHER] else 0 for r in sel])
                c_h8 = frac([1 if r["heur800_choice"]==r[TEACHER] else 0 for r in sel])
                c_v = frac([1 if r["v27_static_choice"]==r[TEACHER] else 0 for r in sel])
                print(f"{lab:16s} {len(sel):5d} {c_i:7.3f} {c_n:8.3f} {c_h2:8.3f} {c_h8:8.3f} {c_v:6.3f}")
            prev = e
    bin_report("policy_top1_prob", lambda r: r.get("policy_top1_prob"), [0.15, 0.25, 0.40, 0.60])
    bin_report("v27_gap", lambda r: r.get("v27_gap"), [0, 1, 2, 4])
    bin_report("n_legal", lambda r: r.get("n_legal"), [10, 20, 30, 45])

    print("\n[done] wrote ROOT_ACTION_RESULTS.csv / _BY_BAND.csv / _BY_DISAGREEMENT.csv to", SPM)


if __name__ == "__main__":
    main()
