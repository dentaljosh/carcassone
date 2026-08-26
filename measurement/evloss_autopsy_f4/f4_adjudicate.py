#!/usr/bin/env python3
"""F4 ADJUDICATOR — does the R1/R2 per-category leaf-headroom map survive an OUT-OF-FAMILY
judge?  `F4_PREREG.md` §4–§6, evaluated verbatim.

Reads two judged trees over the SAME rids and the SAME CRN worlds:

    <share>/judge/                  clair-puct, rust      (banked, R1 — READ ONLY)
    <share>/judge_f4_tier1greedy/   tier1-greedy, python  (this leg)

and emits `F4_READOUT.json`.

The estimator is NOT re-derived: `hajek`, `cluster_sandwich`, `contrast_cluster`,
`norm_sf`, `holm`, `wsd`, `load_leg` are imported from
`measurement/evloss_autopsy_r2/r2_estimator.py` (themselves byte-for-byte R1's), and the
category membership from `r2_taxonomy.py`. The F7 median cut is READ from the frozen
`R2_READOUT.json` rather than recomputed, so membership is bit-identical to R2's by
construction. Gate g5 proves the whole loader by reproducing all 33 banked clair-puct
per-category means.

⚠️ THE MAGNITUDE FENCE. `R_champ^T1` is reported as a MAP, never as a size, and is never
compared to `R_champ^clair` as a magnitude. The tier1-greedy judge is weaker, ~1.8x noisier
and carries its own bias. Only SIGNS are read (F4_PREREG §4.2).
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

_R2_DIR = Path(__file__).resolve().parent.parent / "evloss_autopsy_r2"
if str(_R2_DIR) not in sys.path:
    sys.path.insert(0, str(_R2_DIR))

from r2_estimator import (                                        # noqa: E402
    Z95, cluster_sandwich, contrast_cluster, hajek, holm, load_leg, norm_sf, wsd,
)
import r2_taxonomy as RT                                          # noqa: E402

SCHEMA = "carcassonne-evloss-autopsy-f4-readout/v1"
ARMS = RT.ARMS                              # ("leaf","sib2","sib3","sib4")
BAR = RT.BAR                                # +0.5 pts, PLAN.md §7
Z_ONE_SIDED = 1.6448536269514722            # alpha = 0.05, one-sided (F4_PREREG §4.6)
POOLED_Z_GATE = 2.0                         # F4_PREREG §5, FUNNEL-CLOSED-BY-F4
RECON_TOL_POOLED = 1e-12
RECON_TOL_CATEGORY = 1e-9

# F4_PREREG §4.7 — the leaf-computable-predicate table, pre-stated.
LEAF_COMPUTABLE = {
    "phase_third=opening": True, "phase_third=middle": True, "phase_third=endgame": True,
    "structure=DEG": True, "structure=FARM": True, "structure=CLOISTER": True,
    "structure=CITY": True, "structure=ROAD": True, "structure=NEUTRAL": True,
    "decision_type=tile": True, "decision_type=meeple": True,
    "move_kind=farm": True, "move_kind=cloister": True, "move_kind=city": True,
    "move_kind=road": True, "move_kind=pass": True,
    "commit_direction=spend": True, "commit_direction=hold": True,
    "contest=contested_best": True, "contest=contested_played": True,
    "contest=reinforce_losing_contest_best": True,
    "contest=reinforce_losing_contest_played": True,
    "contest=tie_force_join_best": True, "contest=tie_force_join_played": True,
    # F7 is a property of the CHAMPION'S OWN SEARCH (cross-world argmax spread), not of the
    # afterstate: a static leaf term cannot compute it without running the search.
    "f7_cross_world_spread=low": False, "f7_cross_world_spread=high": False,
    "H2_STEAL_AVAILABLE": True, "H2_STEAL_TAKEN": True, "H2_STEAL_FOREGONE": True,
    "H2_REINFORCE_LOSING": True, "H4_LATE_FARM": True, "H4_DECISIVE_FARM": True,
    "H2xH4_FARM_STEAL": True,
}


# --------------------------------------------------------------------------- #
# 1. LOADING — two judges, one rid set                                        #
# --------------------------------------------------------------------------- #
def _mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def build_f4_rows(positions_dir: Path, judge_clair: Path, judge_t1: Path,
                  split_at: int | None = None):
    """One row per rid scored by BOTH judges. Returns (rows, n_by_leg_clair, n_by_leg_t1).

    `R_champ` / `G_search` / `deltas` / `d_rnd` reproduce `r2_taxonomy.build_rows` exactly
    (that is gate g5's whole point). Everything prefixed `t1_` / `witness` / `split` is new.
    """
    meta = {}
    for line in (positions_dir / "positions_meta.jsonl").read_text().splitlines():
        if line.strip():
            m = json.loads(line)
            meta[m["rid"]] = m

    legsC = {leg: load_leg(judge_clair, leg) for leg in (*ARMS, "rnd")}
    legsT = {leg: load_leg(judge_t1, leg) for leg in (*ARMS, "rnd")}
    n_by_leg_C = {k: len(v) for k, v in legsC.items()}
    n_by_leg_T = {k: len(v) for k, v in legsT.items()}

    rows = []
    for rid, m in meta.items():
        dsC = {leg: legsC[leg][rid]["delta"] for leg in ARMS if rid in legsC[leg]}
        if not dsC:
            continue
        arm, dmax = max(dsC.items(), key=lambda kv: kv[1])
        d_leaf = dsC.get("leaf", 0.0)                    # A6: absent => leaf == played => 0
        row = {
            "rid": rid, "game_id": m["game_id"], "ply": m["ply"],
            "w": m["ht_weight"] or 1.0,
            "R_champ": max(0.0, dmax),
            "G_search": -d_leaf,
            "argmax_arm": (arm if dmax > 0 else "played"),
            "n_arms_scored": len(dsC),
            "leaf_leg_present": "leaf" in dsC,
            "d_rnd": (legsC["rnd"][rid]["delta"] if rid in legsC["rnd"] else None),
            "deltas": dsC,
            "tax": m["taxonomy"],
        }
        # ---- the F4 side ---------------------------------------------------- #
        dsT = {leg: legsT[leg][rid]["delta"] for leg in ARMS if rid in legsT[leg]}
        A = sorted(set(dsC) & set(dsT))
        row["t1_deltas"] = dsT
        row["arms_both"] = A
        row["arms_match"] = sorted(dsC) == sorted(dsT)
        row["t1_d_rnd"] = (legsT["rnd"][rid]["delta"] if rid in legsT["rnd"] else None)
        if A:
            a_star = max(A, key=lambda a: dsC[a])        # in-family preferred arm
            a_starT = max(A, key=lambda a: dsT[a])
            row["a_star_clair"] = a_star
            row["a_star_t1"] = a_starT
            row["witness"] = dsT[a_star]                 # §4.1 — THE PRIMARY, unclipped
            row["R_champ_t1"] = max(0.0, max(dsT[a] for a in A))    # §4.2
            row["argmax_concordant"] = float(a_star == a_starT)     # §4.5
            row["arm_pairs"] = [(dsC[a], dsT[a]) for a in A]
            # ---- §4.3 half-split, selection-unbiased ------------------------ #
            pwC = {a: (legsC[a][rid].get("per_world_delta") or []) for a in A}
            pwT = {a: (legsT[a][rid].get("per_world_delta") or []) for a in A}
            ms = {len(pwC[a]) for a in A} | {len(pwT[a]) for a in A}
            if len(ms) == 1 and ms.pop() >= 2:
                M = len(pwC[A[0]])
                h = split_at if split_at is not None else M // 2
                a_dag = max(A, key=lambda a: _mean(pwC[a][:h]))
                row["a_dag"] = a_dag
                row["witness_split"] = _mean(pwT[a_dag][h:])
            else:
                row["a_dag"], row["witness_split"] = None, None
        else:
            for k in ("a_star_clair", "a_star_t1", "witness", "R_champ_t1",
                      "argmax_concordant", "a_dag", "witness_split"):
                row[k] = None
            row["arm_pairs"] = []
        rows.append(row)
    rows.sort(key=lambda r: (int(r["game_id"]), int(r["ply"])))
    return rows, n_by_leg_C, n_by_leg_T


# --------------------------------------------------------------------------- #
# 2. THE F4 ARITHMETIC (F4_PREREG §4)                                          #
# --------------------------------------------------------------------------- #
def _hz(vals, wts, groups, centre=0.0):
    """(hajek mean, cluster-robust se, z vs `centre`) — the house triple."""
    if not vals:
        return None, None, float("nan")
    mu = hajek(vals, wts)
    se, _deff, G = cluster_sandwich(vals, wts, groups)
    ok = se == se and se > 0 and G >= 2
    return mu, (se if ok else None), ((mu - centre) / se if ok else float("nan"))


def _binom_p_one_sided(k: int, n: int) -> float:
    """P(X >= k | Bin(n, 0.5)) — the 2026-07-28 precedent's form, reported beside the
    clustered z, never as the verdict."""
    if n <= 0:
        return float("nan")
    tot = sum(math.comb(n, i) for i in range(k, n + 1))
    return tot / (2.0 ** n)


def _pearson(xs, ys):
    if len(xs) < 3:
        return None
    try:
        return statistics.correlation(xs, ys)
    except Exception:                                              # noqa: BLE001
        return None


def f4_category_stats(rows, member):
    """Every §4 statistic for one category."""
    sub = [r for r, m in zip(rows, member) if m]
    out = {"n": len(sub), "n_games": len({r["game_id"] for r in sub}),
           "sum_w": sum(r["w"] for r in sub)}
    scored = [r for r in sub if r.get("witness") is not None]
    out["n_scored_both"] = len(scored)
    if not scored:
        out.update({k: None for k in
                    ("witness", "witness_se", "witness_z", "witness_p_one_sided",
                     "witness_split", "witness_split_se", "witness_split_z",
                     "R_champ_t1", "R_champ_t1_se", "R_champ_t1_z_vs_0",
                     "R_champ_t1_z_vs_bar", "R_champ_t1_UB95",
                     "sign_agreement_rate", "sign_agreement_z", "sign_agreement_binom_p",
                     "argmax_concordance", "arm_sign_agreement", "arm_sign_z",
                     "arm_pearson_r", "verdict")})
        out["verdict"] = "F4-UNESTIMABLE"
        return out

    w = [r["w"] for r in scored]
    g = [r["game_id"] for r in scored]

    # --- §4.1 primary witness ------------------------------------------------ #
    mu, se, z = _hz([r["witness"] for r in scored], w, g)
    out["witness"], out["witness_se"], out["witness_z"] = mu, se, (z if z == z else None)
    out["witness_p_one_sided"] = norm_sf(z) if z == z else float("nan")

    # --- §4.3 half-split, selection-unbiased --------------------------------- #
    sp = [r for r in scored if r.get("witness_split") is not None]
    if sp:
        smu, sse, sz = _hz([r["witness_split"] for r in sp],
                           [r["w"] for r in sp], [r["game_id"] for r in sp])
        out["witness_split"], out["witness_split_se"] = smu, sse
        out["witness_split_z"] = sz if sz == sz else None
        out["n_split"] = len(sp)
    else:
        out["witness_split"] = out["witness_split_se"] = out["witness_split_z"] = None
        out["n_split"] = 0

    # --- §4.2 the tier1 map (NOT a test) ------------------------------------- #
    rmu, rse, rz = _hz([r["R_champ_t1"] for r in scored], w, g)
    out["R_champ_t1"] = rmu
    out["R_champ_t1_se"] = rse
    out["R_champ_t1_z_vs_0"] = rz if rz == rz else None
    out["R_champ_t1_z_vs_bar"] = ((rmu - BAR) / rse) if rse else None
    out["R_champ_t1_UB95"] = (rmu + Z95 * rse) if rse else None
    out["R_champ_t1_sd_per_position"] = wsd([r["R_champ_t1"] for r in scored], w)
    # bucket-vs-complement contrast, R2's own form, on the tier1 map
    allsc = [r for r in rows if r.get("R_champ_t1") is not None]
    mem = [bool(m) for r, m in zip(rows, member) if r.get("R_champ_t1") is not None]
    th, cse, cz = contrast_cluster([r["R_champ_t1"] for r in allsc],
                                   [r["w"] for r in allsc],
                                   [r["game_id"] for r in allsc], mem)
    out["t1_contrast_theta"] = th if th == th else None
    out["t1_contrast_se"] = cse if cse == cse else None
    out["t1_contrast_z"] = cz if cz == cz else None

    # --- §4.4 per-position sign-agreement rate ------------------------------- #
    pos = [r for r in scored if r["R_champ"] > 0]
    if pos:
        ag = [1.0 if r["witness"] > 0 else 0.0 for r in pos]
        amu, ase, az = _hz(ag, [r["w"] for r in pos], [r["game_id"] for r in pos],
                           centre=0.5)
        out["sign_agreement_rate"] = amu
        out["sign_agreement_se"] = ase
        out["sign_agreement_z"] = az if az == az else None
        out["sign_agreement_n"] = len(pos)
        out["sign_agreement_k"] = int(sum(ag))
        out["sign_agreement_binom_p"] = _binom_p_one_sided(int(sum(ag)), len(pos))
    else:
        for k in ("sign_agreement_rate", "sign_agreement_se", "sign_agreement_z",
                  "sign_agreement_binom_p"):
            out[k] = None
        out["sign_agreement_n"] = out["sign_agreement_k"] = 0

    # --- §4.5 selection-free arm-level agreement ----------------------------- #
    cc = [(r["argmax_concordant"], r["w"]) for r in scored
          if r["argmax_concordant"] is not None]
    out["argmax_concordance"] = (hajek([c for c, _ in cc], [x for _, x in cc])
                                 if cc else None)
    pv, pw, pg, xs, ys = [], [], [], [], []
    for r in scored:
        for dc, dt in r["arm_pairs"]:
            xs.append(dc); ys.append(dt)
            if dc != 0.0 and dt != 0.0:
                pv.append(1.0 if (dc > 0) == (dt > 0) else 0.0)
                pw.append(r["w"]); pg.append(r["game_id"])
    if pv:
        amu, ase, az = _hz(pv, pw, pg, centre=0.5)
        out["arm_sign_agreement"] = amu
        out["arm_sign_z"] = az if az == az else None
        out["arm_pairs_n"] = len(pv)
    else:
        out["arm_sign_agreement"] = out["arm_sign_z"] = None
        out["arm_pairs_n"] = 0
    out["arm_pearson_r"] = _pearson(xs, ys)

    # --- §4.6 the per-category verdict, first match wins --------------------- #
    out["verdict"] = category_verdict(out)
    return out


def category_verdict(st: dict) -> str:
    """F4_PREREG §4.6, first match wins."""
    mu = st.get("witness")
    if mu is None:
        return "F4-UNESTIMABLE"
    if mu <= 0:
        return "F4-REFUTED"
    z = st.get("witness_z")
    sp = st.get("witness_split")
    if z is not None and z >= Z_ONE_SIDED and sp is not None and sp > 0:
        return "F4-CONFIRMED"
    return "F4-DIRECTIONAL"


def funnel_verdict(gates_ok: bool, pooled_mu, pooled_z, winner_verdicts: dict,
                   rung: str) -> tuple[str, str]:
    """F4_PREREG §5, first match wins. Returns (verdict, consequence)."""
    if not gates_ok:
        return ("F4-BROKEN",
                "An instrument gate failed. NOTHING downstream is read; the leg is "
                "re-run or the defect is fixed first.")
    if pooled_mu is None or pooled_mu <= 0 or pooled_z != pooled_z \
            or pooled_z < POOLED_Z_GATE:
        v = ("FUNNEL-CLOSED-BY-F4",
             "CLOSE. The out-of-family tier1-greedy judge does not corroborate the "
             "champion's oracle headroom anywhere, so the R1/R2 map is not "
             "distinguishable from same-family self-preference. NO leaf-term work is "
             "licensed. Deliverable = the refutation.")
    else:
        vals = set(winner_verdicts.values())
        if "F4-CONFIRMED" in vals:
            v = ("FUNNEL-OPEN-F4-CONFIRMED",
                 "The funnel is open on the CONFIRMED set only (named in "
                 "`confirmed_categories`). A term hypothesis there is licensed, still as a "
                 "GLOBALLY-ACTIVE leaf term measured globally at an n=800 deck-paired "
                 "deploy-budget cell. No bucket-gated deployment, ever.")
        elif "F4-DIRECTIONAL" in vals and "F4-REFUTED" not in vals:
            v = ("FUNNEL-OPEN-F4-DIRECTIONAL",
                 "Owner call; default = DO NOT fund a term. The out-of-family sign is not "
                 "contradicted but is not established at 1.645 one-sided. The honest next "
                 "purchase is POWER on this leg, not a leaf term.")
        elif vals and vals <= {"F4-REFUTED"}:
            v = ("FUNNEL-CLOSED-BY-F4-REFUTED",
                 "CLOSE. Every F1&F2&F3 winner is refuted out of family.")
        else:
            v = ("FUNNEL-F4-INCONCLUSIVE",
                 "Owner call; default = DO NOT fund a term. The per-category table is the "
                 "deliverable.")
    if rung == "L3":
        return (f"F4-PARTIAL/{v[0]}",
                "RUNG L3 (witness-only) was run: R_champ^T1, the half-split witness and "
                "every selection-free arm-level statistic are UNAVAILABLE, and "
                "F4-CONFIRMED is unreachable by construction. " + v[1])
    return v


# --------------------------------------------------------------------------- #
# 3. GATES (F4_PREREG §6)                                                      #
# --------------------------------------------------------------------------- #
def crn_cross_judge_witness(judge_clair: Path, judge_t1: Path, legs=(*ARMS, "rnd")):
    """g4 — same rid, same salt => bit-identical world seeds AND afterstates across the two
    judges. Only the CONTINUATION may differ."""
    checked, bad = 0, []
    for leg in legs:
        dC, dT = judge_clair / leg / "records", judge_t1 / leg / "records"
        if not (dC.is_dir() and dT.is_dir()):
            continue
        for p in sorted(dT.glob("*.json")):
            q = dC / p.name
            if not q.exists():
                continue
            a, b = json.loads(p.read_text()), json.loads(q.read_text())
            checked += 1
            for f in ("world_seeds", "afterstate_deck_hash_a", "afterstate_deck_hash_b",
                      "pick_a", "pick_b", "world_seed_salt"):
                if a.get(f) != b.get(f):
                    bad.append({"leg": leg, "rid": a.get("rid"), "field": f})
                    break
    return {"cross_judge_comparisons": checked, "mismatches": len(bad),
            "examples": bad[:5], "ok": len(bad) == 0}


def record_gates(judge_t1: Path, legs) -> dict:
    """g1 + g3 over the tier1 tree."""
    out, ok = {}, True
    for leg in legs:
        d = judge_t1 / leg / "records"
        n = nok = ncrn = ncap = 0
        prof, salt = set(), set()
        for p in (sorted(d.glob("*.json")) if d.is_dir() else []):
            r = json.loads(p.read_text())
            n += 1
            nok += bool(r.get("ok") is True)
            ncrn += bool(r.get("crn_verified") is True)
            ncap += bool("wall cap" in str(r.get("error") or ""))
            prof.add(r.get("rules_profile"))
            salt.add(r.get("world_seed_salt"))
        leg_ok = bool(n and nok == n and ncrn == n and ncap == 0
                      and prof <= {"walled"} and salt <= {"evloss-autopsy-20260824-v1"})
        ok &= leg_ok
        out[leg] = {"n": n, "ok_records": nok, "crn_verified": ncrn,
                    "wall_capped": ncap, "rules_profiles": sorted(map(str, prof)),
                    "salts": sorted(map(str, salt)), "ok": leg_ok}
    out["all_ok"] = bool(ok)
    return out


def manifest_gates(judge_t1: Path, legs) -> dict:
    """g2 — the judge really is tier1-greedy on python.

    ⚠️ FIELD NAMES VERIFIED AGAINST A REAL MANIFEST (D-F4-10), not guessed:
    `oracle_score_pilot.build_manifest` writes the policy at `oracle.policy` (NOT a
    top-level `oracle_policy` — that name exists only in the per-position RECORD) and the
    engine at `execution.backend`. Both spellings are accepted so a future manifest revision
    that promotes either key still passes, but a manifest carrying NEITHER fails.
    """
    out, ok = {}, True
    for leg in legs:
        m = judge_t1 / leg / "manifest.json"
        if not m.exists():
            out[leg] = {"ok": False, "reason": "missing manifest.json"}
            ok = False
            continue
        d = json.loads(m.read_text())
        pol = (d.get("oracle") or {}).get("policy") or d.get("oracle_policy")
        ex = d.get("execution") or {}
        be = ex.get("backend_resolved") or ex.get("backend")
        # the harness's own out-of-family attestation, stamped by ORACLE_POLICIES
        fam = (d.get("oracle") or {}).get("policy_family") or ""
        leg_ok = bool(pol == "tier1-greedy" and be == "python"
                      and fam.startswith("OUT-OF-FAMILY"))
        ok &= leg_ok
        out[leg] = {"oracle_policy": pol, "backend": be,
                    "policy_family_out_of_family": bool(fam.startswith("OUT-OF-FAMILY")),
                    "ok": leg_ok}
    out["all_ok"] = bool(ok)
    return out


def reconcile(rows, members, r2_readout: dict) -> dict:
    """g5 — the clair-puct side must reproduce the frozen R2 map exactly."""
    v = [r["R_champ"] for r in rows]
    w = [r["w"] for r in rows]
    g = [r["game_id"] for r in rows]
    mu = hajek(v, w)
    pooled_ref = r2_readout["pooled"]["R_champ"]
    d_pooled = abs(mu - pooled_ref)
    cats, worst, worst_b = {}, 0.0, None
    for b, ref in r2_readout["categories"].items():
        if ref.get("R_champ") is None or b not in members:
            continue
        sub = [r for r, m in zip(rows, members[b]) if m]
        if not sub:
            continue
        got = hajek([r["R_champ"] for r in sub], [r["w"] for r in sub])
        d = abs(got - ref["R_champ"])
        cats[b] = {"got": got, "ref": ref["R_champ"], "abs_diff": d,
                   "ok": d <= RECON_TOL_CATEGORY}
        if d > worst:
            worst, worst_b = d, b
    ok = bool(d_pooled <= RECON_TOL_POOLED
              and all(c["ok"] for c in cats.values()) and cats)
    _se, _deff, G = cluster_sandwich(v, w, g)
    return {"pooled_got": mu, "pooled_ref": pooled_ref, "pooled_abs_diff": d_pooled,
            "pooled_ok": bool(d_pooled <= RECON_TOL_POOLED),
            "n_positions": len(rows), "n_games": G,
            "n_categories_checked": len(cats),
            "worst_category": worst_b, "worst_abs_diff": worst,
            "tol_pooled": RECON_TOL_POOLED, "tol_category": RECON_TOL_CATEGORY,
            "categories": cats, "ok": ok}


# --------------------------------------------------------------------------- #
# 4. DRIVER                                                                    #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--share", default="/mnt/c/carc-shared/evloss_autopsy_20260824")
    ap.add_argument("--positions-dir", default=None)
    ap.add_argument("--judge-root-clair", default=None)
    ap.add_argument("--judge-root-t1", default=None)
    ap.add_argument("--r2-readout", default=None)
    ap.add_argument("--rung", choices=("L1", "L2", "L3"), default="L1")
    ap.add_argument("--out", default=None)
    ap.add_argument("--blind-stamp", required=True,
                    help="git commit hash of the blind prereg+code commit")
    ap.add_argument("--allow-broken", action="store_true",
                    help="still write the readout when a gate fails (verdict F4-BROKEN)")
    args = ap.parse_args(argv)

    share = Path(args.share)
    positions_dir = Path(args.positions_dir or (share / "positions"))
    judge_clair = Path(args.judge_root_clair or (share / "judge"))
    judge_t1 = Path(args.judge_root_t1 or (share / "judge_f4_tier1greedy"))
    r2_path = Path(args.r2_readout
                   or (Path(__file__).resolve().parent.parent
                       / "evloss_autopsy_r2" / "R2_READOUT.json"))
    r2 = json.loads(r2_path.read_text())
    out_path = Path(args.out or (Path(__file__).resolve().parent / "F4_READOUT.json"))

    rows, n_by_leg_C, n_by_leg_T = build_f4_rows(positions_dir, judge_clair, judge_t1)
    print(f"[load] {len(rows)} positions | clair {n_by_leg_C} | tier1 {n_by_leg_T}",
          flush=True)

    # membership: the FROZEN F7 cut, so labels are bit-identical to R2's
    f7_median = r2["coverage"]["f7_median_cut"]
    labels = [RT.classify(r["tax"], f7_median) for r in rows]
    names = list(labels[0].keys()) if labels else []
    members = {b: [lab[b] for lab in labels] for b in names}

    legs_expected = {"L1": (*ARMS, "rnd"), "L2": ARMS, "L3": ("argmax",)}[args.rung]
    gates = {
        "g1_g3_records": record_gates(judge_t1, legs_expected),
        "g2_manifests": manifest_gates(judge_t1, legs_expected),
        "g4_cross_judge_crn": crn_cross_judge_witness(judge_clair, judge_t1),
        "g5_reconciliation": reconcile(rows, members, r2),
        "g7_arms_match": {
            "n_rows": len(rows),
            "n_mismatched": sum(1 for r in rows if not r["arms_match"]),
            "examples": [r["rid"] for r in rows if not r["arms_match"]][:5],
        },
    }
    gates["g7_arms_match"]["ok"] = gates["g7_arms_match"]["n_mismatched"] == 0

    # g6 — R_rnd > R_champ under the TIER1 judge (L1 only)
    rsub = [r for r in rows if r.get("t1_d_rnd") is not None and r.get("R_champ_t1") is not None]
    if rsub:
        rr = [max([0.0] + [r["t1_deltas"][a] for a in r["arms_both"]] + [r["t1_d_rnd"]])
              - r["t1_d_rnd"] for r in rsub]
        rc = [r["R_champ_t1"] for r in rsub]
        ww = [r["w"] for r in rsub]
        gates["g6_r_rnd"] = {"n": len(rsub), "R_rnd_t1": hajek(rr, ww),
                            "R_champ_t1_on_subset": hajek(rc, ww)}
        gates["g6_r_rnd"]["ok"] = bool(gates["g6_r_rnd"]["R_rnd_t1"]
                                       > gates["g6_r_rnd"]["R_champ_t1_on_subset"])
    else:
        gates["g6_r_rnd"] = {"n": 0, "ok": None,
                             "note": "no rnd leg under the tier1 judge (rung L2/L3)"}

    gates_ok = bool(gates["g1_g3_records"]["all_ok"] and gates["g2_manifests"]["all_ok"]
                    and gates["g4_cross_judge_crn"]["ok"]
                    and gates["g5_reconciliation"]["ok"]
                    and gates["g7_arms_match"]["ok"]
                    and (gates["g6_r_rnd"]["ok"] is not False))
    gates["all_ok"] = gates_ok

    if not gates_ok and not args.allow_broken:
        print("[F4-BROKEN] instrument gates failed; nothing is read.", file=sys.stderr)
        print(json.dumps({k: (v if not isinstance(v, dict) else
                              {kk: vv for kk, vv in v.items() if kk != "categories"})
                          for k, v in gates.items()}, indent=2)[:6000], file=sys.stderr)
        return 3

    # ---- pooled + per-category ---------------------------------------------- #
    pooled = f4_category_stats(rows, [True] * len(rows))
    cats = {b: f4_category_stats(rows, members[b]) for b in names}

    winners = list(r2["funnel_gate"]["winners"])
    winner_verdicts = {b: cats[b]["verdict"] for b in winners if b in cats}
    # Holm across the 7 winners on the one-sided p (SECONDARY, §4.6)
    pv = {b: cats[b]["witness_p_one_sided"] for b in winners
          if b in cats and cats[b].get("witness_p_one_sided") is not None}
    hol = holm(pv, alpha=0.05)
    for b, h in hol.items():
        cats[b]["F4_confirmed_holm"] = bool(
            h["reject"] and (cats[b].get("witness") or 0) > 0
            and (cats[b].get("witness_split") or 0) > 0)
        cats[b]["p_holm_one_sided"] = h["p_holm"]

    pooled_z = pooled.get("witness_z")
    verdict, consequence = funnel_verdict(
        gates_ok, pooled.get("witness"),
        (pooled_z if pooled_z is not None else float("nan")),
        winner_verdicts, args.rung)

    predicate = {b: LEAF_COMPUTABLE.get(b) for b in winners}
    out = {
        "schema": SCHEMA,
        "blind_stamp_commit": args.blind_stamp,
        "prereg": "measurement/evloss_autopsy_f4/F4_PREREG.md",
        "deviations": "measurement/evloss_autopsy_f4/DEVIATIONS.md",
        "parent_readout": str(r2_path),
        "parent_blind_stamp": r2.get("blind_stamp_commit"),
        "rung": args.rung,
        "judge": {
            "oracle_policy": "tier1-greedy",
            "backend": "python",
            "family": "OUT-OF-FAMILY: no search (1-ply argmax) and the v1 OBJECT "
                      "virtual_score leaf, not curve125",
            "continuation_agent": "oracle_score_pilot._GreedyContinuation "
                                  "(carcassonne_ai.rule_based_player.RuleBasedPlayer)",
            "m": 32, "salt": "evloss-autopsy-20260824-v1", "rules_profile": "walled",
        },
        "corpus": {"share": str(share), "positions_dir": str(positions_dir),
                   "judge_root_clair": str(judge_clair), "judge_root_t1": str(judge_t1),
                   "n_by_leg_clair": n_by_leg_C, "n_by_leg_tier1": n_by_leg_T,
                   "n_positions": len(rows),
                   "record_filter": "ok is True and crn_verified is True"},
        "gates": gates,
        "pooled": pooled,
        "categories": cats,
        "funnel_F4": {
            "verdict": verdict,
            "consequence": consequence,
            "winners_from_R2": winners,
            "winner_verdicts": winner_verdicts,
            "confirmed_categories": [b for b, v in winner_verdicts.items()
                                     if v == "F4-CONFIRMED"],
            "directional_categories": [b for b, v in winner_verdicts.items()
                                       if v == "F4-DIRECTIONAL"],
            "refuted_categories": [b for b, v in winner_verdicts.items()
                                   if v == "F4-REFUTED"],
            "leaf_computable_predicate": predicate,
            "conditions": {
                "primary_statistic": "same-arm cross-judge witness delta_i = "
                                     "D^T1(i, argmax_a D^clair(i,a)); NOT clipped at 0",
                "category_pass": "witness > 0 AND one-sided cluster-robust z >= 1.645 "
                                 "AND half-split (selection-unbiased) witness > 0",
                "pooled_gate": "pooled witness > 0 and one-sided z >= 2.0",
            },
        },
        "read_fence": (
            "0 evaluation games. No elo, no band-confirmatory use, no results.csv row, no "
            "CL, PRODUCTION.yaml untouched. NO bucket-gated deployment, ever. SIGN CHECK "
            "ONLY: never quote a tier1-greedy mean as a magnitude — the judge is weaker "
            "and ~1.8x noisier by construction and carries its own bias."),
    }
    out_path.write_text(json.dumps(out, indent=2))

    print("=== F4 READ-OUT ===")
    print(f"pooled witness = {pooled['witness']:+.4f}  se {pooled['witness_se']}  "
          f"z {pooled['witness_z']}")
    print(f"pooled half-split witness = {pooled['witness_split']}  "
          f"z {pooled['witness_split_z']}")
    for b in winners:
        c = cats.get(b, {})
        print(f"  {b:34s} n={c.get('n')!s:>4} witness={c.get('witness')} "
              f"z={c.get('witness_z')} split={c.get('witness_split')} "
              f"-> {c.get('verdict')}")
    print(f"\nFUNNEL F4 VERDICT: {verdict}\n  {consequence}")
    print(f"-> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
