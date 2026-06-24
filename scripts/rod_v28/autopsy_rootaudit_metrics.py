#!/usr/bin/env python3
"""
RoD v2.8 iter_08 autopsy — Part F (training curves) + Part B cached half
(parent -> RoD1 -> heur3200 ROOT agreement on the 1000-position midgame set).

All inputs are ALREADY on disk; this only aggregates. No replay/new compute.

Part F  : per-iter *.metrics.json  -> curve of pol/val loss, entropy, value_outcome_corr
Part B* : ROOT_AUDIT_V28.jsonl     -> per-band agreement (RoD1/parent vs heur3200_v28)
          NOTE: this covers the parent->RoD1 leg. The RoD1->iter08(OV) leg needs one
          new label run (iter_08 root choices); flagged in the digest, not computed here.
"""
import json, os, glob, statistics as st
from collections import defaultdict, OrderedDict

OUT = "measurement/rod_v28_overnight_flywheel/autopsy"
os.makedirs(OUT, exist_ok=True)

# ---------- Part F: training curves ----------
CHAIN = OrderedDict()
# parent champion lineage (context): flywheel_residual_attempt2 iter8 is the champion + RoD1's parent
CHAIN["PARENT_champ(fw2_it8)"] = "/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.metrics.json"
CHAIN["RoD1(cont_it01)"]       = "/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.metrics.json"
for i in range(2, 18):
    CHAIN[f"ov_it{i:02d}"] = f"/mnt/c/carc-shared/rod_v28_overnight_flywheel/ckpt/iter_{i:02d}.metrics.json"

def last_epoch(m):
    eps = m.get("epochs", [])
    return eps[-1] if eps else {}

def part_f():
    rows = []
    for name, fp in CHAIN.items():
        if not os.path.exists(fp):
            rows.append((name, "MISSING")); continue
        m = json.load(open(fp))
        le = last_epoch(m)
        lw = m.get("provenance", {}).get("loss_weights", {})
        rows.append(dict(
            name=name,
            vlw=lw.get("value"),
            train_pol=le.get("train_pol_loss"),
            val_pol=le.get("val_pol_loss"),
            train_val=le.get("train_val_loss"),
            val_val=le.get("val_val_loss"),
            train_own=le.get("train_own_loss"),
            pol_entropy=m.get("policy_entropy"),
            base_entropy=m.get("baseline_policy_entropy"),
            value_outcome_corr=m.get("value_outcome_corr"),
            n_train=m.get("n_train_positions"),
        ))
    # CSV
    fp = os.path.join(OUT, "training_curves.csv")
    cols = ["name","vlw","train_pol","val_pol","train_val","val_val","train_own",
            "pol_entropy","base_entropy","value_outcome_corr","n_train"]
    with open(fp, "w") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            if r == "MISSING" or isinstance(r, tuple):
                continue
            f.write(",".join(str(r.get(c, "")) for c in cols) + "\n")
    lines = ["## Part F — training curves (final-epoch; *value_outcome_corr is the key diagnostic*)",
             "",
             "name | VLW | val_pol | val_val | train_own | pol_entropy | value_outcome_corr",
             "--- | --- | --- | --- | --- | --- | ---"]
    for r in rows:
        if isinstance(r, tuple):
            lines.append(f"{r[0]} | MISSING"); continue
        def f3(x): return f"{x:.4f}" if isinstance(x, (int, float)) else str(x)
        lines.append(f"{r['name']} | {r['vlw']} | {f3(r['val_pol'])} | {f3(r['val_val'])} | "
                     f"{f3(r['train_own'])} | {f3(r['pol_entropy'])} | {f3(r['value_outcome_corr'])}")
    lines.append(f"\nCSV: {fp}")
    lines.append("NOTE: val_pol/val_val are each iter's fit to ITS OWN self-play val split "
                 "(different distributions) -> compare with care. value_outcome_corr (normalized "
                 "corr of value head vs game outcome) and pol_entropy are the cross-comparable signals. "
                 "VLW changed 1.0->1.5 at RoD1 (confounds val_val level).")
    return "\n".join(lines)

# ---------- Part B cached half: root agreement (parent -> RoD1 -> heur3200) ----------
ROOT_AUDIT = "measurement/rod_v28_continuation/ROOT_AUDIT_V28.jsonl"
LABELS     = "measurement/midgame_reference/MIDGAME_REFERENCE_LABELS.jsonl"
BAND_ORDER = ["opening","early_mid","mid","late_mid","pre_endgame"]

def part_b_cached():
    if not os.path.exists(ROOT_AUDIT):
        return f"## Part B (cached) — ROOT_AUDIT missing: {ROOT_AUDIT}"
    rows = [json.loads(l) for l in open(ROOT_AUDIT) if l.strip()]
    def band_key(b): return BAND_ORDER.index(b) if b in BAND_ORDER else 99
    by = defaultdict(list)
    for r in rows:
        by[r.get("band","?")].append(r)
    def agg(rs):
        n = len(rs)
        def frac(k): return sum(r.get(k,0) for r in rs)/n if n else float("nan")
        return dict(n=n,
                    rod_eq_h=frac("rod_eq_heur3200"),
                    par_eq_h=frac("parent_eq_heur3200"),
                    rod_eq_par=frac("rod_eq_parent"),
                    par_neq_h=frac("parent_disagrees_heur3200"),
                    rod_fixed=frac("rod_fixed_parent_miss"))
    lines = ["", "## Part B (CACHED half) — root-move agreement on 1000 fixed midgame positions",
             "(heur3200 = v2.8 deep ruler; 'rod' = RoD1 = continuation iter_01; 'parent' = champion fw2_it8)",
             "Covers the parent->RoD1 leg ONLY. RoD1->iter08(OV) leg = the one missing label run.",
             "",
             "band | n | RoD1≡h3200 | parent≡h3200 | RoD1≡parent | parent≠h3200 | rod_fixed_parent_miss",
             "--- | --- | --- | --- | --- | --- | ---"]
    ov = agg(rows)
    for b in sorted(by, key=band_key):
        a = agg(by[b])
        lines.append(f"{b} | {a['n']} | {a['rod_eq_h']:.3f} | {a['par_eq_h']:.3f} | "
                     f"{a['rod_eq_par']:.3f} | {a['par_neq_h']:.3f} | {a['rod_fixed']:.3f}")
    lines.append(f"**ALL** | {ov['n']} | {ov['rod_eq_h']:.3f} | {ov['par_eq_h']:.3f} | "
                 f"{ov['rod_eq_par']:.3f} | {ov['par_neq_h']:.3f} | {ov['rod_fixed']:.3f}")
    # interpretation helpers
    # of positions where parent disagrees with h3200, how often did RoD1 move TO h3200 (fix) vs stay/elsewhere
    par_miss = [r for r in rows if r.get("parent_disagrees_heur3200")]
    if par_miss:
        fixed = sum(r.get("rod_fixed_parent_miss",0) for r in par_miss)
        lines.append("")
        lines.append(f"Of {len(par_miss)} positions where PARENT disagrees with h3200: "
                     f"RoD1 moved TO h3200 in {fixed} ({100*fixed/len(par_miss):.1f}%) "
                     f"-> the rest RoD1 stayed off-ruler or went elsewhere.")
    # how much did RoD1 diverge from parent, and was the divergence net toward h3200?
    diverged = [r for r in rows if not r.get("rod_eq_parent",1)]
    if diverged:
        tow = sum(1 for r in diverged if r.get("rod_eq_heur3200") and not r.get("parent_eq_heur3200"))
        awy = sum(1 for r in diverged if r.get("parent_eq_heur3200") and not r.get("rod_eq_heur3200"))
        nei = len(diverged) - tow - awy
        lines.append(f"RoD1 diverged from parent on {len(diverged)}/{ov['n']} positions "
                     f"({100*len(diverged)/ov['n']:.1f}%): TOWARD h3200={tow}, AWAY from h3200={awy}, "
                     f"neither={nei}.  net-toward = {tow-awy:+d} "
                     f"({'h3200-aligned' if tow>awy else 'orthogonal/style' if tow==awy else 'anti-aligned'}).")
    lines.append(f"\nROOT_AUDIT source: {ROOT_AUDIT}")
    # sharpness context from labels
    if os.path.exists(LABELS):
        labs = [json.loads(l) for l in open(LABELS) if l.strip()]
        lb = defaultdict(list)
        for r in labs: lb[r.get("band","?")].append(r)
        lines.append("")
        lines.append("Sharpness (teacher_gap_q = h3200 best_Q - 2nd_Q; higher = sharper/more decisive) + n_legal by band:")
        lines.append("band | n | mean teacher_gap_q | mean n_legal")
        lines.append("--- | --- | --- | ---")
        for b in sorted(lb, key=band_key):
            gs = [r.get("teacher_gap_q") for r in lb[b] if isinstance(r.get("teacher_gap_q"),(int,float))]
            nl = [r.get("n_legal") for r in lb[b] if isinstance(r.get("n_legal"),(int,float))]
            lines.append(f"{b} | {len(lb[b])} | {st.mean(gs):.4f} | {st.mean(nl):.1f}")
    return "\n".join(lines)

def main():
    doc = ["# RoD v2.8 iter_08 autopsy — Part F + Part B(cached) [free, on-disk only]\n",
           part_f(), part_b_cached()]
    out = os.path.join(OUT, "PART_FB_digest.md")
    open(out, "w").write("\n".join(doc))
    print("\n".join(doc))
    print(f"\n[written] {out}")

if __name__ == "__main__":
    main()
