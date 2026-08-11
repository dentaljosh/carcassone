#!/usr/bin/env python3
"""PROBE B §4A verdict reader (docs/PROBE_B_FAIR_INFO_SPEC.md §4A).

Reads the 6 arm summaries (fair|clair x both|bag_only|farm_only) from an eval
out-root and prints the pre-registered fourth-nail read:

  H-4A-inert : does the value's "can rank with residual over the leaf" (best_alpha>0,
               beats_leaf) SURVIVE fair targets, or go inert (alpha=0, no regret-red)?
               fair inert + clair non-inert  -> FOURTH NAIL (Gate-B not a clairvoyance
               artifact). fair non-inert      -> clairvoyance artifact, verdict changes.
  H-4A-bag   : does the bag input's contribution GROW under fair targets vs clair?
               bag-marginal = regret_red(both) - regret_red(farm_only) [bag's add-on],
               plus bag_only standalone. Grows under fair -> clairvoyance-suppression;
               vanishes -> genuine (regime-invariant) redundancy (CL-037).

Usage: python verdict_4a.py <eval_out_root>   (e.g. measurement/probe_b_4a/eval_full)
"""
import json, sys, os

BASE = sys.argv[1] if len(sys.argv) > 1 else "measurement/probe_b_4a/eval_full"
ARMS = ["clair_both", "clair_bag_only", "clair_farm_only",
        "fair_both", "fair_bag_only", "fair_farm_only"]


def load(arm):
    p = os.path.join(BASE, arm, "V4_listwise", "summary.json")
    if not os.path.exists(p):
        return None
    return json.load(open(p))["overall"]


def main():
    rows = {}
    print(f"§4A eval @ {BASE}\n")
    print(f"{'arm':<18}{'best_alpha':>11}{'regret_red%':>12}{'net_tau':>9}{'beats_leaf':>12}{'n_test':>8}")
    for a in ARMS:
        d = load(a)
        if d is None:
            print(f"{a:<18}{'  MISSING':>11}")
            continue
        rows[a] = d
        print(f"{a:<18}{d['best_alpha']:>11}{d['regret_reduction_pct']:>12.1f}"
              f"{d['net_alone']['tau']:>9.3f}{str(d['beats_leaf']):>12}{d['net_alone']['n']:>8}")
    if not all(a in rows for a in ARMS):
        print("\n[incomplete — not all 6 arms present]")
        return
    print()

    def rr(a):
        return rows[a]["regret_reduction_pct"]

    def a0(a):
        return float(rows[a]["best_alpha"]) == 0.0

    # H-4A-inert
    print("== H-4A-inert (does value ranking survive fair targets?) ==")
    print(f"  clair_both: alpha={rows['clair_both']['best_alpha']} regret_red={rr('clair_both'):+.1f}% "
          f"beats_leaf={rows['clair_both']['beats_leaf']}")
    print(f"  fair_both : alpha={rows['fair_both']['best_alpha']} regret_red={rr('fair_both'):+.1f}% "
          f"beats_leaf={rows['fair_both']['beats_leaf']}")
    clair_ranks = (not a0("clair_both")) and rows["clair_both"]["beats_leaf"]
    fair_inert = a0("fair_both") and (rr("fair_both") <= 1.0)
    if clair_ranks and fair_inert:
        print("  -> FOURTH NAIL: value ranks under clairvoyant targets but goes INERT under fair "
              "(adds nothing over the leaf). Gate-B was NOT a clairvoyance artifact; the ceiling holds.")
    elif not fair_inert:
        print("  -> INERT BREAKS under fair (value ranks with residual): part of Gate-B was a "
              "clairvoyance artifact -> the fair-info flywheel has room the clairvoyant regime hid.")
    else:
        print("  -> AMBIGUOUS: clair baseline did not rank as expected; inspect the arms.")

    # H-4A-bag
    print("\n== H-4A-bag (does bag's contribution grow under fair?) ==")
    bag_marg_clair = rr("clair_both") - rr("clair_farm_only")
    bag_marg_fair = rr("fair_both") - rr("fair_farm_only")
    print(f"  clair: bag_only={rr('clair_bag_only'):+.1f}%  bag-marginal(both-farm)={bag_marg_clair:+.1f}pp")
    print(f"  fair : bag_only={rr('fair_bag_only'):+.1f}%  bag-marginal(both-farm)={bag_marg_fair:+.1f}pp")
    if bag_marg_fair > bag_marg_clair + 2.0 or rr("fair_bag_only") > rr("clair_bag_only") + 2.0:
        print("  -> bag contribution GROWS under fair: CL-037 redundancy was partly clairvoyance-suppression.")
    else:
        print("  -> bag contribution does NOT grow (vanishes/inert under fair): genuine regime-invariant "
              "redundancy (CL-037 holds across regimes) -> reinforces the fourth nail.")


if __name__ == "__main__":
    main()
