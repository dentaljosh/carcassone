#!/usr/bin/env python3
"""Probe §5A — read the 4 arm summaries -> the pre-registered read-out.

Δ_indep_tempo = regret_reduction(all_three) - regret_reduction(both)
  >= 3pp  -> CRACK (H-5A-live): tempo is a separated 3rd axis, record the lead
  <  1pp  -> CEILING-EARNED (H-5A-inert): three independent axes, ship
  [1,3)pp -> WEAK LEAD: small real residual, strong claim NOT earned

Also reports the positive-control guard: `both` must reproduce CL-037's non-inert
~-20.5%; if it is inert (~0), the gate is INVALID (depth floored) — read no null.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "measurement/probe_5a/arms")
VARIANT = sys.argv[2] if len(sys.argv) > 2 else "V4_listwise"


def rr(arm):
    p = ROOT / arm / VARIANT / "summary.json"
    if not p.exists():
        return None
    s = json.loads(p.read_text())["overall"]
    return {"regret_reduction_pct": s["regret_reduction_pct"], "best_alpha": s["best_alpha"],
            "net_alone_tau": s["net_alone"]["tau"], "beats_leaf": s["beats_leaf"]}


def main():
    arms = {a: rr(a) for a in ("none", "both", "tempo_only", "all_three")}
    print("arm         regret_red%  best_alpha  net_tau  beats_leaf")
    for a, v in arms.items():
        if v is None:
            print(f"  {a:10s}  <missing>"); continue
        print(f"  {a:10s}  {v['regret_reduction_pct']:+7.2f}    {v['best_alpha']:>6}   "
              f"{v['net_alone_tau']:+.3f}   {v['beats_leaf']}")
    if any(v is None for v in arms.values()):
        print("\n[incomplete] not all arms present yet.")
        return

    both = arms["both"]["regret_reduction_pct"]
    allt = arms["all_three"]["regret_reduction_pct"]
    delta = allt - both

    # positive-control guard (§4 depth requirement)
    control_live = arms["both"]["best_alpha"] != "0.0" and both > 5.0
    print(f"\npositive control 'both' regret_red = {both:+.2f}%  (CL-037 was -20.5% / a=0.05)")
    if not control_live:
        print(">>> GATE INVALID: 'both' positive control did NOT reproduce non-inert at this depth.")
        print(">>> Read no null. Report 'positive control did not reproduce' (§4 stop).")
        return

    print(f"Δ_indep_tempo = all_three({allt:+.2f}) − both({both:+.2f}) = {delta:+.2f}pp")
    if delta >= 3.0:
        verdict = "CRACK (H-5A-live) — tempo is a separated 3rd axis; record the lead, no loop"
    elif delta < 1.0:
        verdict = "CEILING-EARNED (H-5A-inert) — three independent axes; ship"
    else:
        verdict = "WEAK LEAD — small real tempo residual; strong claim NOT earned"
    print(f"\n===== §5A VERDICT: {verdict} =====")

    (ROOT / "verdict_5a.json").write_text(json.dumps(
        {"arms": arms, "both_rr": both, "all_three_rr": allt,
         "delta_indep_tempo_pp": delta, "control_live": control_live,
         "verdict": verdict}, indent=2))
    print(f"[saved] {ROOT/'verdict_5a.json'}")


if __name__ == "__main__":
    main()
