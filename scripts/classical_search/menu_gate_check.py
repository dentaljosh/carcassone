#!/usr/bin/env python3
"""ITEM 2 WIRING GATE (2a) — the HARD BLOCKER, read entirely from the manifests.

Spec: docs/LEVER_MENU_PLAN_20260810.md section 4.2 ("2a - WIRING GATE").

WHY THIS EXISTS. `LeafConfig.farm_growth_off` has a complete code path to the fair harness
(flat_leaf / carc-core leaf -> rust_agent.leaf_config_rs -> search_config_rs -> RustFairAgent
-> eval_fair_puct.py --cand-leaf-json) but it has NEVER been exercised through
eval_fair_puct.py: zero farm_growth_off manifests exist anywhere on the share. The precedent
for treating that as a blocker rather than a formality is the caps/curve build, which caught
the CLAIRVOYANT RUST MIRRORS IGNORING `--rules-profile` ENTIRELY. A knob that is silently
dropped produces a perfectly plausible ~0 elo null.

The gate is three manifest assertions plus a sign control:

  1. the CANDIDATE's resolved leaf hash DIFFERS from the champion's a36d2e15a3b3d71d
     (proves the knob was applied, not silently dropped);
  2. the OPPONENT arm resolves EXACTLY a36d2e15a3b3d71d (proves the reference did not move);
  3. rules_profile.name == fixed_v1, rules_profile.r9_env_ok == true, and k_dets 8 /
     sims_per_det 1376 on BOTH arms;
  4. SIGN CONTROL: a farm_base_off micro-cell must read STRONGLY NEGATIVE (the recorded
     reference is -132.9 .. -142.1 elo). A knob that reads ~0 where the reference reads -140
     is broken wiring, not a null.

If the gate fails, item 2 STOPS and becomes a build task. "Fix it and keep the games" is
explicitly not allowed.

Exit 0 = PASS. Exit 1 = FAIL (the chain must not launch block B). Exit 2 = missing inputs.
"""
import argparse
import json
import os
import sys

CHAMP_LEAF_HASH = "a36d2e15a3b3d71d"
# ⚠️ THE ROUND'S FROZEN BUDGET, not "whatever PRODUCTION.yaml says today". These are the
# knobs the 2026-08-10 menu round's cells were LAUNCHED at (k8x1376 = 11008, the champion
# budget of that date); the gate's job is to prove the round's own arms are configured
# alike, so it must NOT track later promotions — champion.fair_deploy went to k16x1376 =
# 22016 on 2026-08-30 and these cells are still k8x1376, correctly. Deliberately literal;
# contrast eval_fair_puct.PROD_KNOBS, which asks a LIVE question ("is this cell the shipped
# champion?") and therefore must LOAD governance/PRODUCTION.yaml instead of restating it.
DEPLOY_K_DETS = 8
DEPLOY_SIMS = 1376
# The recorded farm_base_off knockout magnitude (CL-074 farm rows, bands 1.00e11 / 1.05e11).
# The control is a MICRO-cell, so the bar is a SIGN-and-order-of-magnitude bar, not a CI test.
SIGN_CONTROL_MAX_ELO = -40.0


def _g(d, *path, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def check_manifest(man_path, label, expect_cand_differs):
    """Assertions 1-3 against one cell's manifest. Returns (ok, findings, failures)."""
    fails, found = [], {}
    if not os.path.exists(man_path):
        return False, found, [f"{label}: manifest missing at {man_path}"]
    m = json.load(open(man_path))

    cand = _g(m, "config", "cand_leaf_hash")
    opp = _g(m, "config", "opp_leaf_hash")
    prof = _g(m, "rules_profile", "name")
    r9 = _g(m, "rules_profile", "r9_env_ok")
    ck = _g(m, "config", "champion", "k_dets")
    cs = _g(m, "config", "champion", "sims_per_det")
    ok_ = _g(m, "config", "opponent", "k_dets")
    os_ = _g(m, "config", "opponent", "sims_per_det")
    drift = _g(m, "config", "cand_curve_drift_allowed")
    found.update(cand_leaf_hash=cand, opp_leaf_hash=opp, rules_profile=prof, r9_env_ok=r9,
                 cand_k_dets=ck, cand_sims_per_det=cs, opp_k_dets=ok_, opp_sims_per_det=os_,
                 cand_curve_drift_allowed=drift, code_rev=m.get("code_rev"))

    # 1. the knob moved the candidate leaf
    if expect_cand_differs:
        if cand is None:
            fails.append(f"{label}: config.cand_leaf_hash is absent")
        elif cand == CHAMP_LEAF_HASH:
            fails.append(
                f"{label}: ASSERTION 1 FAILED - candidate leaf hash == the champion's "
                f"{CHAMP_LEAF_HASH}. The knob was SILENTLY DROPPED; this is exactly the "
                f"clairvoyant-rust-mirror failure mode. Item 2 is a build task, not a cell.")
    # 2. the opponent is exactly the champion
    if opp != CHAMP_LEAF_HASH:
        fails.append(f"{label}: ASSERTION 2 FAILED - opponent leaf hash {opp!r} != "
                     f"{CHAMP_LEAF_HASH}; the reference arm moved.")
    # 3. rules + budget on both arms
    if prof != "fixed_v1":
        fails.append(f"{label}: ASSERTION 3 FAILED - rules_profile.name {prof!r} != 'fixed_v1'")
    if r9 is not True:
        fails.append(f"{label}: ASSERTION 3 FAILED - rules_profile.r9_env_ok {r9!r} is not true")
    for who, kd, sm in (("candidate", ck, cs), ("opponent", ok_, os_)):
        if kd != DEPLOY_K_DETS or sm != DEPLOY_SIMS:
            fails.append(f"{label}: ASSERTION 3 FAILED - {who} budget is k{kd}x{sm}, expected "
                         f"k{DEPLOY_K_DETS}x{DEPLOY_SIMS} "
                         f"(={DEPLOY_K_DETS * DEPLOY_SIMS}, this ROUND's frozen budget — "
                         "not necessarily today's champion; see the constant's note)")
    return (not fails), found, fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate-dir", required=True,
                    help="the farm_growth_off wiring-gate cell dir (manifest.json + summary.json)")
    ap.add_argument("--control-dir", required=True,
                    help="the farm_base_off SIGN-CONTROL cell dir")
    ap.add_argument("--out", required=True, help="where to write the gate verdict JSON")
    a = ap.parse_args()

    res = {"gate": "ITEM2_WIRING_GATE_2a", "verdict": None, "failures": [],
           "gate_cell": {}, "control_cell": {}}

    ok_g, found_g, fails_g = check_manifest(
        os.path.join(a.gate_dir, "manifest.json"), "gate(farm_growth_off)", True)
    ok_c, found_c, fails_c = check_manifest(
        os.path.join(a.control_dir, "manifest.json"), "control(farm_base_off)", True)
    res["gate_cell"] = found_g
    res["control_cell"] = found_c
    res["failures"] += fails_g + fails_c

    # the two knocked-out leaves must ALSO differ from each other, or one JSON is being
    # applied for both cells (a copy/paste failure the hash-vs-champion check cannot see).
    if found_g.get("cand_leaf_hash") and found_g.get("cand_leaf_hash") == found_c.get("cand_leaf_hash"):
        res["failures"].append(
            "gate and control resolved the SAME candidate leaf hash "
            f"({found_g['cand_leaf_hash']}) - farm_growth_off and farm_base_off are different "
            "knobs and must not produce the same leaf; one cell JSON is not being applied.")

    # 4. SIGN CONTROL
    sp = os.path.join(a.control_dir, "summary.json")
    if not os.path.exists(sp):
        res["failures"].append(f"control: summary.json missing at {sp}")
    else:
        s = json.load(open(sp))
        elo = s.get("elo")
        res["control_cell"].update(n=s.get("n"), W=s.get("W"), D=s.get("D"), L=s.get("L"),
                                   elo=elo, elo_sig_1sigma=s.get("elo_sig_1sigma"),
                                   paired_z=s.get("paired_z"))
        if elo is None:
            res["failures"].append("control: summary.json has no elo")
        elif elo > SIGN_CONTROL_MAX_ELO:
            res["failures"].append(
                f"SIGN CONTROL FAILED - farm_base_off read elo {elo:+.1f}, expected strongly "
                f"negative (recorded reference -132.9..-142.1; bar is <= {SIGN_CONTROL_MAX_ELO}). "
                "A knob that reads ~0 where the reference reads -140 is BROKEN WIRING, not a null.")

    # gate-cell numbers recorded for the audit trail; they are NOT a result and must not be read
    gsp = os.path.join(a.gate_dir, "summary.json")
    if os.path.exists(gsp):
        s = json.load(open(gsp))
        res["gate_cell"].update(n=s.get("n"), W=s.get("W"), D=s.get("D"), L=s.get("L"),
                                elo=s.get("elo"), paired_z=s.get("paired_z"))
        res["gate_cell"]["note"] = ("THROWAWAY numbers from a ~32-game wiring smoke on a "
                                    "disjoint sub-band. NOT a result, NOT poolable, NOT quotable.")

    res["verdict"] = "PASS" if not res["failures"] else "FAIL"
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))
    if res["verdict"] != "PASS":
        print("\nITEM 2 WIRING GATE FAILED. Block B must NOT launch. Item 2 becomes a build "
              "task; do NOT 'fix it and keep the games'.", file=sys.stderr)
        return 1
    print("\nITEM 2 WIRING GATE PASS - block B is cleared to launch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
