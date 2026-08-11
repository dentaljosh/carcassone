#!/usr/bin/env python3
"""
Autopsy Part B/C — merge rod_ov_iter_08's root labels onto ROOT_AUDIT_V28.jsonl and
answer THE question: did iter_08 move its root moves TOWARD heur@3200 (ruler-aligned
improvement) or ORTHOGONALLY (anti-RoD1 style)?

Baseline = RoD1 (rod_choice); treatment = iter_08 (iter08ov_choice). All comparable:
same 1000 positions, same v2.8 leaf, same NeuralMCTS@200/c3.0, same best_action selector,
same per-position seed.
"""
import json, os, csv
from collections import defaultdict

D = "measurement/rod_v28_overnight_flywheel/autopsy"
ITER08 = os.path.join(D, "iter08_root_labels.jsonl")
ROOTAUDIT = "measurement/rod_v28_continuation/ROOT_AUDIT_V28.jsonl"
BANDS = ["opening", "early_mid", "mid", "late_mid", "pre_endgame"]


def load(p):
    return {r["position_id"]: r for r in (json.loads(l) for l in open(p) if l.strip())}


def main():
    it08 = load(ITER08)
    ra = load(ROOTAUDIT)
    ids = sorted(set(it08) & set(ra))
    rows = []
    for pid in ids:
        a, r = it08[pid], ra[pid]
        ic = a["iter08ov_choice"]
        rc = r.get("rod_choice"); pc = r.get("parent_choice"); h3 = r.get("heur3200_v28_choice")
        rows.append(dict(
            position_id=pid, band=r.get("band"), source_bucket=r.get("source_bucket"),
            k_remaining=r.get("k_remaining"),
            iter08=ic, rod=rc, parent=pc, h3200=h3,
            it_top1=a.get("iter08ov_top1_visit_share"), it_rootv=a.get("iter08ov_root_value"),
            it_eq_h3=int(ic == h3), rod_eq_h3=int(rc == h3), par_eq_h3=int(pc == h3),
            it_eq_rod=int(ic == rc), it_eq_par=int(ic == pc),
        ))

    def agg(rs):
        n = len(rs)
        def f(k): return sum(x[k] for x in rs) / n if n else float("nan")
        # toward/away decomposition for iter08 vs RoD1 baseline
        diverged = [x for x in rs if not x["it_eq_rod"]]
        tow = sum(1 for x in diverged if x["it_eq_h3"] and not x["rod_eq_h3"])
        awy = sum(1 for x in diverged if x["rod_eq_h3"] and not x["it_eq_h3"])
        nei = len(diverged) - tow - awy
        return dict(n=n, it_eq_h3=f("it_eq_h3"), rod_eq_h3=f("rod_eq_h3"), par_eq_h3=f("par_eq_h3"),
                    it_eq_rod=f("it_eq_rod"), it_eq_par=f("it_eq_par"),
                    n_div=len(diverged), tow=tow, awy=awy, nei=nei)

    out = ["# Autopsy Part B/C — iter_08 ROOT-move audit (the decisive toward/away-h3200 test)",
           "",
           f"Merged {len(ids)} positions (iter08 labels ∩ ROOT_AUDIT_V28). v2.8 leaf, NeuralMCTS@200/c3.0,",
           "best_action selector, net-on-CPU — identical method to the cached rod/parent labels.",
           "",
           "## Root-move agreement vs heur@3200_v28 (top-1), by band",
           "band | n | iter08≡h3200 | RoD1≡h3200 | parent≡h3200 | **Δ(iter08−RoD1)** | iter08≡RoD1 | iter08≡parent",
           "--- | --- | --- | --- | --- | --- | --- | ---"]
    ov = agg(rows)
    by = defaultdict(list)
    for x in rows: by[x["band"]].append(x)
    for b in BANDS:
        if b not in by: continue
        a = agg(by[b])
        out.append(f"{b} | {a['n']} | {a['it_eq_h3']:.3f} | {a['rod_eq_h3']:.3f} | {a['par_eq_h3']:.3f} | "
                   f"{a['it_eq_h3']-a['rod_eq_h3']:+.3f} | {a['it_eq_rod']:.3f} | {a['it_eq_par']:.3f}")
    out.append(f"**ALL** | {ov['n']} | {ov['it_eq_h3']:.3f} | {ov['rod_eq_h3']:.3f} | {ov['par_eq_h3']:.3f} | "
               f"**{ov['it_eq_h3']-ov['rod_eq_h3']:+.3f}** | {ov['it_eq_rod']:.3f} | {ov['it_eq_par']:.3f}")

    out += ["", "## Toward/away decomposition (iter_08's divergence FROM RoD1)", ""]
    for label, rs in [("ALL", rows)] + [(b, by[b]) for b in BANDS if b in by]:
        a = agg(rs)
        net = a["tow"] - a["awy"]
        verdict = "h3200-ALIGNED" if net > 0 else "orthogonal/style" if net == 0 else "ANTI-aligned"
        out.append(f"- **{label}**: iter08 diverged from RoD1 on {a['n_div']}/{a['n']} "
                   f"({100*a['n_div']/a['n']:.1f}%): toward h3200={a['tow']}, away={a['awy']}, "
                   f"neither={a['nei']} → net {net:+d} ({verdict})")

    # Part C lite: confident distinctive disagreements (iter08 != rod AND iter08 != h3200), highest visit-share
    distinct = [x for x in rows if not x["it_eq_rod"] and not x["it_eq_h3"]
                and x["it_top1"] is not None]
    distinct.sort(key=lambda x: -x["it_top1"])
    out += ["", "## Part C (lite) — iter_08's most CONFIDENT distinctive picks",
            "(positions where iter08 disagrees with BOTH RoD1 and h3200, sorted by iter08 root visit-share;",
            "these are iter08's stylistic signature moves — candidates for move-level inspection)", "",
            "position_id | band | k | n_legal? | iter08 | rod | h3200 | it_top1_share | it_rootv",
            "--- | --- | --- | --- | --- | --- | --- | --- | ---"]
    for x in distinct[:25]:
        out.append(f"{x['position_id']} | {x['band']} | {x['k_remaining']} | — | {x['iter08']} | "
                   f"{x['rod']} | {x['h3200']} | {x['it_top1']} | {x['it_rootv']}")

    # CSV of the full per-position table
    csvp = os.path.join(D, "root_disagreement_iter08.csv")
    cols = ["position_id","band","source_bucket","k_remaining","iter08","rod","parent","h3200",
            "it_eq_h3","rod_eq_h3","par_eq_h3","it_eq_rod","it_eq_par","it_top1","it_rootv"]
    with open(csvp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for x in rows: w.writerow({k: x.get(k) for k in cols})
    out += ["", f"Full table CSV: {csvp}", f"iter08 labels: {ITER08}"]

    digest = os.path.join(D, "PART_BC_digest.md")
    open(digest, "w").write("\n".join(out))
    print("\n".join(out))
    print(f"\n[written] {digest}")


if __name__ == "__main__":
    main()
