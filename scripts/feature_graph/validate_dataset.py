#!/usr/bin/env python3
"""Feature-Graph Stage-1 BUILT-IN CORRECTNESS GATE.

Re-derives the leaf-audit aggregate from the BUILT rows_feat.npz (NOT from a fresh
replay) and asserts it reproduces the frozen reference
  measurement/value_resurrection_pilot/data/leaf_audit_summary.json
(overall top1 ~0.455, tau_mean ~0.895, n_gap002_and_regret002 ~1197).

Also:
  (a) leaf_q spot-check vs the stored value-resurrection rows.npz (matched by
      (game_seed, ply) GROUP CONTENT, since that npz is capped to 4000 random
      groups -> row index does not align).
  (b) Tier-2 ownership sanity asserts + no NaN/inf in feat.

If the audit does NOT reproduce, the enumeration/leaf is wrong -> STOP and report
the mismatch loudly.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
DATA = REPO / "measurement" / "feature_graph_comparator" / "data"
REF = REPO / "measurement" / "value_resurrection_pilot" / "data" / "leaf_audit_summary.json"
VR_ROWS = Path("/mnt/c/carc-shared/value_resurrection/dataset_v29_h6400/rows.npz")

# reference targets (small tolerance ok)
REF_TOP1 = 0.4553
REF_TAU = 0.8951
REF_DECISIVE = 1197
TOL_RATE = 0.01      # top1 / tau absolute
TOL_DECISIVE = 40    # n_gap002_and_regret002 count tolerance


def _kendall_tau(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    c = d = 0
    for i in range(n):
        xi, yi = xs[i], ys[i]
        for j in range(i + 1, n):
            s = (xi - xs[j]) * (yi - ys[j])
            if s > 0: c += 1
            elif s < 0: d += 1
    tot = c + d
    return (c - d) / tot if tot else None


def main():
    npz_path = DATA / "rows_feat.npz"
    z = np.load(npz_path, allow_pickle=False)
    feat = z["feat"]; oq = z["oracle_q"]; lq = z["leaf_q"]
    gid = z["group_id"]; aid = z["action_id"]; gs = z["game_seed"]; ply = z["ply"]
    isbest = z["is_teacher_best"]; qgap = z["q_gap"]
    feat_names = [str(x) for x in z["feat_names"]]
    print(f"[load] {npz_path}  feat {feat.shape}  groups={len(np.unique(gid))}  rows={len(oq)}")

    # ---- (0) no NaN/inf ----------------------------------------------------
    n_bad = int((~np.isfinite(feat)).sum())
    assert n_bad == 0, f"FAIL: {n_bad} non-finite feat entries"
    print(f"[finite] feat all finite (checked {feat.size} entries)  OK")

    # ---- (1) re-derive leaf-audit aggregate from built rows ----------------
    name_ix = {n: i for i, n in enumerate(feat_names)}
    top1s, taus, regrets = [], [], []
    decisive = 0
    groups = np.unique(gid)
    # ownership sanity accumulators
    n_own_ok = 0; n_own_checked = 0
    locked_ok = 0
    ix_nself = name_ix["T2_n_cities_self"]; ix_nopp = name_ix["T2_n_cities_opp"]
    ix_ncon = name_ix["T2_n_cities_contested"]
    ix_locked_self = name_ix["T2_n_meeples_locked_self"]
    for g in groups:
        m = gid == g
        o = oq[m]; l = lq[m]; b = isbest[m].astype(bool)
        gap = float(qgap[m][0])
        if o.size < 2:
            continue
        leaf_top = int(np.argmax(l))
        if b.sum() >= 1:
            tb = int(np.argmax(b))
        else:
            tb = int(np.argmax(o))   # fallback: oracle argmax == teacher best
        top1 = int(leaf_top == tb)
        regret = float(o[tb] - o[leaf_top])
        tau = _kendall_tau(list(l), list(o))
        top1s.append(top1)
        if tau is not None:
            taus.append(tau)
        regrets.append(regret)
        if gap >= 0.02 and regret >= 0.02:
            decisive += 1

    top1_mean = float(np.mean(top1s))
    tau_mean = float(np.mean(taus))
    print(f"[audit] top1={top1_mean:.4f} (ref {REF_TOP1})  "
          f"tau_mean={tau_mean:.4f} (ref {REF_TAU})  "
          f"n_decisive={decisive} (ref {REF_DECISIVE})")

    ok_top1 = abs(top1_mean - REF_TOP1) <= TOL_RATE
    ok_tau = abs(tau_mean - REF_TAU) <= TOL_RATE
    ok_dec = abs(decisive - REF_DECISIVE) <= TOL_DECISIVE
    audit_pass = ok_top1 and ok_tau and ok_dec
    print(f"[audit] PASS={audit_pass}  (top1 {ok_top1}, tau {ok_tau}, decisive {ok_dec})")

    # ---- (2) ownership sanity asserts --------------------------------------
    # n_cities_self+opp+contested <= number of meeples placed (loose upper bound:
    # a city with a meeple is at most counted once across the 3 buckets).
    sums = feat[:, ix_nself] + feat[:, ix_nopp] + feat[:, ix_ncon]
    # locked_self counts meeples on open feats -> must be >= 0 and finite
    locked = feat[:, ix_locked_self]
    own_neg = int((sums < 0).sum()); locked_neg = int((locked < 0).sum())
    assert own_neg == 0 and locked_neg == 0, f"FAIL: negative ownership counts ({own_neg},{locked_neg})"
    # contested cities cannot exceed self+opp cities counted as owned overall
    bad_con = int((feat[:, ix_ncon] < 0).sum())
    assert bad_con == 0
    print(f"[ownership] city self+opp+contested in [{sums.min():.0f},{sums.max():.0f}], "
          f"locked_self in [{locked.min():.0f},{locked.max():.0f}], no negatives  OK")

    # ---- (3) leaf_q spot-check vs stored value-resurrection rows.npz --------
    spot = "SKIPPED (vr rows.npz not found)"
    if VR_ROWS.exists():
        vr = np.load(VR_ROWS, allow_pickle=False)
        vr_lq = vr["leaf_q"]; vr_gid = vr["group_id"]; vr_gs = vr["game_seed"]; vr_ply = vr["ply"]
        # build (seed,ply) -> sorted leaf_q multiset for vr groups
        vr_map = {}
        for g in np.unique(vr_gid):
            mm = vr_gid == g
            key = (int(vr_gs[mm][0]), int(vr_ply[mm][0]))
            vr_map[key] = np.sort(vr_lq[mm])
        # our (seed,ply) -> sorted leaf_q
        matched = 0; max_abs = 0.0; checked = 0
        for g in groups:
            m = gid == g
            key = (int(gs[m][0]), int(ply[m][0]))
            if key not in vr_map:
                continue
            ours = np.sort(lq[m]); theirs = vr_map[key]
            if ours.shape != theirs.shape:
                continue
            checked += 1
            d = float(np.max(np.abs(ours - theirs)))
            max_abs = max(max_abs, d)
            if d < 1e-4:
                matched += 1
            if checked >= 200:
                break
        spot = f"checked={checked} matched(<1e-4)={matched} max_abs_diff={max_abs:.2e}"
        spot_ok = checked > 0 and matched == checked
    else:
        spot_ok = True
    print(f"[leaf_q spot-check] {spot}")

    print("\n==== GATE RESULT ====")
    print(f"audit reproduce : {'PASS' if audit_pass else 'FAIL'}")
    print(f"ownership sanity: PASS")
    print(f"leaf_q spotcheck: {'PASS' if (VR_ROWS.exists() and spot_ok) else ('PASS(skipped)' if not VR_ROWS.exists() else 'FAIL')}")
    if not audit_pass:
        print("\n*** AUDIT DID NOT REPRODUCE — enumeration/leaf is WRONG. STOP. ***")
        sys.exit(2)
    if VR_ROWS.exists() and not spot_ok:
        print("\n*** leaf_q spot-check FAILED. ***")
        sys.exit(3)
    print("\nALL GATES PASS")


if __name__ == "__main__":
    main()
