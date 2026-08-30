#!/usr/bin/env python3
"""PREREG §3 identity gates that need NO new playouts: G-ID-1, G-ID-3, G-ID-6, G-ID-8.

Run this BEFORE any new compute. A failure here is VOID.
Writes GATE_IDENTITY_PRE.json.
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import b128_lib as L  # noqa: E402


def main():
    t0 = time.time()
    out = {"artifact": "GATE_IDENTITY_PRE", "prereg": "measurement/b128_offline_prep/PREREG.md",
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "note": "banked-only gates; no new playouts were run to produce this file"}

    arms = L.load_arms()
    if_by = L.load_records("clair-puct")
    arb_by = L.load_records("tier1-greedy")
    banked = L.load_banked_rows()
    out["n_arms_rids"] = len(arms)
    out["n_banked_rows"] = len(banked)

    # ---- G-ID-3: seed prefix-stability on realized banked records ---------- #
    from oracle_score_pilot import playout_seed, world_seeds
    n_rec = n_ws_ok = n_ps_ok = 0
    bad = []
    for judge, by in (("tier1-greedy", arb_by), ("clair-puct", if_by)):
        for rid, legs in by.items():
            for leg, rec in legs.items():
                n_rec += 1
                ws256 = world_seeds(rid, 256, L.SALT)
                ok_w = list(rec["world_seeds"]) == ws256[:128]
                ok_p = list(rec["playout_seeds"]) == [
                    playout_seed(rid, j, L.SALT) for j in range(128)]
                n_ws_ok += ok_w
                n_ps_ok += ok_p
                if not (ok_w and ok_p) and len(bad) < 5:
                    bad.append({"judge": judge, "rid": rid, "leg": leg,
                                "world_ok": ok_w, "playout_ok": ok_p})
    out["G_ID_3"] = {"n_records": n_rec, "n_world_seed_prefix_ok": n_ws_ok,
                     "n_playout_seed_prefix_ok": n_ps_ok, "examples_bad": bad,
                     "pass": bool(n_rec and n_ws_ok == n_rec and n_ps_ok == n_rec),
                     "assertion": "world_seeds(rid,256,salt)[:128] == banked record seeds"}

    # ---- G-ID-4 (generator half): shifted seeds == world_seeds(...,256)[128:] #
    ws_sh, ps_sh = L.shifted_seed_fns(128)
    probes = sorted(arms)[:200]
    ok_g = all(ws_sh(r, 128, L.SALT) == world_seeds(r, 256, L.SALT)[128:256]
               for r in probes)
    ok_g2 = all(ps_sh(r, j, L.SALT) == playout_seed(r, 128 + j, L.SALT)
                for r in probes for j in (0, 1, 63, 127))
    out["G_ID_4_generator"] = {"n_probe_rids": len(probes),
                               "world_seeds_shifted_ok": ok_g,
                               "playout_seed_shifted_ok": ok_g2,
                               "pass": bool(ok_g and ok_g2)}

    # ---- assemble on BANKED matrices (m = 128) ----------------------------- #
    pos, counts = L.assemble(arms, if_by, arb_by)
    out["assemble_counts"] = counts
    out["n_assembled"] = len(pos)
    out["assemble_matches_banked_rowset"] = (set(pos) == set(banked))
    out["only_in_assembled"] = sorted(set(pos) - set(banked))[:10]
    out["only_in_banked"] = sorted(set(banked) - set(pos))[:10]

    # ---- G-ID-1 + G-ID-8: bit-identity with the published ladder ----------- #
    keys = [f"arb_{s}_E{e}_B{b}" for s in ("j4", "full")
            for e in L.E_LEVELS for b in L.B_LADDER_PUBLISHED]
    comp = {"n_rows": 0, "n_cmp": 0, "n_bit_identical": 0, "mismatch": []}
    plumb = {"n_rows": 0, "champ_pos_ok": 0, "arm_order_ok": 0, "n_arms_j4_ok": 0}
    for rid in sorted(pos):
        if rid not in banked:
            continue
        row = L.ladder_row(pos[rid], L.B_LADDER_PUBLISHED)
        b = banked[rid]
        comp["n_rows"] += 1
        for k in keys:
            if k not in b:
                continue
            comp["n_cmp"] += 1
            if L.f64bits(row[k]) == L.f64bits(b[k]):
                comp["n_bit_identical"] += 1
            elif len(comp["mismatch"]) < 8:
                comp["mismatch"].append({"rid": rid, "key": k,
                                         "ours": row[k], "banked": b[k]})
        plumb["n_rows"] += 1
        plumb["champ_pos_ok"] += int(row["champ_pos"] == b["champ_pos"])
        plumb["arm_order_ok"] += int(list(row["arm_order"]) == list(b["arm_order"]))
        plumb["n_arms_j4_ok"] += int(row["n_arms_j4"] == b["n_arms_j4"])
    comp["pass"] = bool(comp["n_cmp"] and comp["n_cmp"] == comp["n_bit_identical"])
    plumb["pass"] = bool(plumb["n_rows"]
                         and plumb["champ_pos_ok"] == plumb["n_rows"]
                         and plumb["arm_order_ok"] == plumb["n_rows"]
                         and plumb["n_arms_j4_ok"] == plumb["n_rows"])
    out["G_ID_1"] = comp
    out["G_ID_8"] = plumb

    out["all_pre_gates_pass"] = all(
        out[g]["pass"] for g in ("G_ID_3", "G_ID_4_generator", "G_ID_1", "G_ID_8"))
    out["elapsed_secs"] = round(time.time() - t0, 1)
    dst = os.path.join(HERE, "..", "GATE_IDENTITY_PRE.json")
    with open(dst, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps({k: v for k, v in out.items()
                      if k not in ("only_in_assembled", "only_in_banked")},
                     indent=1, sort_keys=True)[:4000])
    print("wrote", os.path.abspath(dst))
    return 0 if out["all_pre_gates_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
