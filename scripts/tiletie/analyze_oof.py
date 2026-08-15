#!/usr/bin/env python3
"""Adjudicate measurement/tiletie_oof_20260814/READ_RULE.md.

Joins the two judges' `analyze_tiletie.py` outputs -- IN-FAMILY `clair-puct`
(the pricing corpus's own records, filename-filtered to the dev slice) and
OUT-OF-FAMILY `tier1-greedy` (this run's records) -- computed by the SAME
unmodified estimator on the SAME positions, and emits:

  * both pre-registered statistics (S1a spread, S2 headroom) side by side;
  * `R = H_OOF / H_IF` with a PAIRED root bootstrap (both judges recomputed
    inside every replicate, so the CRN cross-judge correlation is priced);
  * `R_norm`, the noise-normalised companion (READ_RULE §2);
  * `G-CAL`, the free cross-judge cross-parity blind-ruler control (DESIGN §4.5);
  * the pricing §5 sign check in the E4 autopsy's committed taxonomy;
  * the integrity gates, and the branch.

It computes NO new estimator: S1a / S2 / the scales / the elo chain all come
from `analyze_tiletie`, imported unmodified.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _p in (str(HERE), str(REPO / "scripts" / "analyzer")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import analyze_tiletie as AT                                       # noqa: E402

# ---- READ_RULE §2 committed constants ------------------------------------- #
RATIO_BAR = 0.50          # half the in-family headroom == the +-17 elo bar
Z_BAR = 2.0               # ELO/ z conviction bar (analyze_tiletie.Z_CONVICTION)
GCAL_Z_BAR = 2.0
GCAL_QUANTILE = 0.75      # top quartile of |primary selection-half arm delta|
N_FLOOR = 250             # G-N
BOOT_REPS = 20000
BOOT_SEED = 20260814      # READ_RULE §2 -- this run's own seed
PARITY_BASE = 1           # the primary's realized choice (I1-parity-base)

# E4 autopsy committed benchmarks (analyze_autopsy.sign_agreement)
BENCH = ("80% at p 0.0012 = corroboration (2026-07-28 precedent); "
         "61.9% at p 0.38 = NOT corroboration (farm-war). "
         "The E4 autopsy's own Tier-1 leg: 62.1% at p 2.8e-05 with the "
         "secondary's aggregate sign NEGATIVE => PARTIAL.")


# --------------------------------------------------------------------------- #
def load_per_position(path) -> dict:
    out = {}
    for line in Path(path).read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["rid"]] = r
    return out


def paired_ratio_bootstrap(num_vals, den_vals, roots, n_boot=BOOT_REPS, seed=BOOT_SEED):
    """CI for mean(num)/mean(den) by resampling ROOTS, both recomputed per rep.

    Numerator and denominator are the SAME positions in the SAME order, so a
    replicate resamples a root and takes both judges' contributions together --
    which is what prices the CRN cross-judge correlation.
    """
    nsum, dsum, cnt = defaultdict(float), defaultdict(float), defaultdict(int)
    for a, b, r in zip(num_vals, den_vals, roots):
        nsum[r] += a
        dsum[r] += b
        cnt[r] += 1
    keys = sorted(cnt)
    g = len(keys)
    if g < 2:
        nan = float("nan")
        return nan, nan, nan, nan, nan
    n_arr = np.array([nsum[k] for k in keys], dtype=np.float64)
    d_arr = np.array([dsum[k] for k in keys], dtype=np.float64)
    c_arr = np.array([cnt[k] for k in keys], dtype=np.float64)
    rng = np.random.default_rng(seed)
    out = np.empty(n_boot, dtype=np.float64)
    dens = np.empty(n_boot, dtype=np.float64)
    done = 0
    while done < n_boot:
        b = min(2000, n_boot - done)
        idx = rng.integers(0, g, size=(b, g))
        c = c_arr[idx].sum(axis=1)
        num = n_arr[idx].sum(axis=1) / c
        den = d_arr[idx].sum(axis=1) / c
        dens[done:done + b] = den
        with np.errstate(divide="ignore", invalid="ignore"):
            out[done:done + b] = np.where(den != 0.0, num / den, np.nan)
        done += b
    # A denominator that can cross zero makes a ratio percentile interval bimodal
    # and misleading; report the rate so the reader can see whether it is material.
    frac_den_le_0 = float((dens <= 0.0).sum()) / n_boot
    fin = out[np.isfinite(out)]
    if fin.size < 100:
        nan = float("nan")
        return nan, nan, nan, float(fin.size), frac_den_le_0
    fin.sort()
    return (float(np.median(fin)), float(fin[int(0.025 * fin.size)]),
            float(fin[min(fin.size - 1, int(0.975 * fin.size))]),
            float(fin.size), frac_den_le_0)


def binom_two_sided(agree: int, n: int) -> float:
    """Exact two-sided binomial p at p0=0.5 -- analyze_autopsy.sign_agreement's form."""
    if n == 0:
        return float("nan")
    half = n / 2.0
    d = abs(agree - half)
    tail = sum(math.comb(n, k) for k in range(0, n + 1) if abs(k - half) >= d)
    return tail / (2.0 ** n)


def sign_check(if_rows: dict, oof_rows: dict, key: str, scale_key: str) -> dict:
    """The pricing §5 sign check, E4-autopsy taxonomy, unchanged."""
    shared = sorted(set(if_rows) & set(oof_rows))
    a = {r: if_rows[r][key] * if_rows[r][scale_key] for r in shared}
    b = {r: oof_rows[r][key] * oof_rows[r][scale_key] for r in shared}
    both = [r for r in shared if a[r] != 0 and b[r] != 0]
    agree = sum(1 for r in both if (a[r] > 0) == (b[r] > 0))
    n = len(both)
    rate = (agree / n) if n else float("nan")
    p = binom_two_sided(agree, n)
    pm = AT._mean([a[r] for r in shared]) if shared else float("nan")
    sm = AT._mean([b[r] for r in shared]) if shared else float("nan")
    ps = 1 if pm > 0 else -1
    ss = 1 if sm > 0 else -1
    if n and rate > 0.5 and p < 0.05 and ps == ss:
        verdict = "CORROBORATES"
    elif n and rate > 0.5 and p < 0.05:
        verdict = ("PARTIAL -- per-position signs agree above chance, but the "
                   "out-of-family judge's own aggregate sign is OPPOSITE the "
                   "primary's, so it does not corroborate the DIRECTION.")
    else:
        verdict = "NO CORROBORATION -- sign agreement is not distinguishable from chance"
    return {"n_shared": len(shared), "n_both_nonzero": n, "n_agree": agree,
            "agreement_rate": rate, "binomial_p_two_sided": p,
            "primary_mean_sign_only": ps, "secondary_mean_sign_only": ss,
            "corroboration": verdict, "benchmarks": BENCH}


# --------------------------------------------------------------------------- #
# G-CAL (DESIGN §4.5) -- cross-judge, cross-parity, zero extra compute          #
# --------------------------------------------------------------------------- #
def _records_by_rid(records_root, keep):
    """{rid: {leg: record}} restricted BY FILENAME to `keep` (holdout firewall)."""
    by = defaultdict(dict)
    for f in sorted(glob.glob(os.path.join(str(records_root), "*", "leg*", "records",
                                           "*.json"))):
        rid = Path(f).stem
        if rid not in keep:
            continue
        leg = int(Path(f).parents[1].name[3:])
        by[rid][leg] = json.loads(Path(f).read_text())
    return dict(by)


def g_cal(if_recs: dict, oof_recs: dict, arms: dict, m: int,
          quantile=GCAL_QUANTILE, parity_base=PARITY_BASE) -> dict:
    """Select arm pairs on the PRIMARY's selection half; evaluate on the
    OUT-OF-FAMILY judge's EVALUATION half. Different judges AND disjoint worlds,
    so neither dimension carries a winner's curse."""
    sel, eva = AT.parity_indices(m, parity_base, swap=False)
    cand = []
    for rid in sorted(set(if_recs) & set(oof_recs)):
        for leg, rec in sorted(if_recs[rid].items()):
            orec = oof_recs[rid].get(leg)
            if orec is None or not rec.get("ok") or not orec.get("ok"):
                continue
            d_if = AT._sub_mean(rec["values_b"], sel) - AT._sub_mean(rec["values_a"], sel)
            d_oof = AT._sub_mean(orec["values_b"], eva) - AT._sub_mean(orec["values_a"], eva)
            cand.append({"rid": rid, "leg": leg, "root_id": arms[rid]["root_id"],
                         "d_if_sel": d_if, "d_oof_eva": d_oof})
    if not cand:
        return {"ok": False, "reason": "no paired legs", "pass": False}
    mags = sorted(abs(c["d_if_sel"]) for c in cand)
    thr = mags[int(quantile * (len(mags) - 1))]
    top = [c for c in cand if abs(c["d_if_sel"]) >= thr and c["d_if_sel"] != 0.0]
    aligned = [math.copysign(1.0, c["d_if_sel"]) * c["d_oof_eva"] for c in top]
    roots = [c["root_id"] for c in top]
    mean, se, n, g = AT.cluster_robust(aligned, roots)
    z = mean / se if se and se == se and se > 0 else float("nan")
    return {"ok": True, "n_legs_all": len(cand), "n_selected": n, "n_roots": g,
            "quantile": quantile, "threshold_abs_d_if_sel": thr,
            "mean_sign_aligned_d_oof": mean, "se_cluster": se, "z": z,
            "bar": GCAL_Z_BAR, "pass": bool(z == z and z >= GCAL_Z_BAR),
            "note": "selection on the PRIMARY's selection-half worlds, evaluation on "
                    "the OUT-OF-FAMILY judge's DISJOINT evaluation-half worlds."}


# --------------------------------------------------------------------------- #
# integrity                                                                    #
# --------------------------------------------------------------------------- #
def crn_identity(if_recs: dict, oof_recs: dict) -> dict:
    out = {"world_seed_mismatch": 0, "playout_seed_mismatch": 0,
           "crn_unverified": 0, "checksum_failed": 0, "arm_mismatch": 0,
           "compared_legs": 0, "examples": []}
    for rid in sorted(set(if_recs) & set(oof_recs)):
        for leg, orec in sorted(oof_recs[rid].items()):
            irec = if_recs[rid].get(leg)
            if irec is None:
                continue
            out["compared_legs"] += 1
            if list(irec["world_seeds"]) != list(orec["world_seeds"]):
                out["world_seed_mismatch"] += 1
                out["examples"].append(f"{rid} leg{leg} world_seeds")
            if list(irec["playout_seeds"]) != list(orec["playout_seeds"]):
                out["playout_seed_mismatch"] += 1
            if not orec.get("crn_verified"):
                out["crn_unverified"] += 1
            if orec.get("checksum_ok") is False:
                out["checksum_failed"] += 1
            if (orec["pick_a"], orec["pick_b"]) != (irec["pick_a"], irec["pick_b"]):
                out["arm_mismatch"] += 1
    out["examples"] = out["examples"][:5]
    out["ok"] = all(out[k] == 0 for k in ("world_seed_mismatch", "playout_seed_mismatch",
                                          "crn_unverified", "checksum_failed",
                                          "arm_mismatch"))
    return out


# --------------------------------------------------------------------------- #
def stat_block(rows: dict, label: str) -> dict:
    rl = list(rows.values())
    out = {}
    for name, key, scale in (
            ("S1a_sigma2_arm_discriminable", "sigma2_arm", None),
            ("S1a_sigma2_arm_all", "sigma2_arm", "scale_all"),
            ("S1b_gap_G_discriminable", "gap_G", None),
            ("S1b_gap_G_all", "gap_G", "scale_all"),
            ("S2_headroom_discriminable", "headroom_champ", None),
            ("S2_headroom_all", "headroom_champ", "scale_all"),
            ("S2_headroom_all_zeros_strict", "headroom_champ", "scale_strict"),
            ("S2b_leaf_regret_discriminable", "headroom_leaf", None),
            ("S2b_leaf_regret_all", "headroom_leaf", "scale_all"),
            ("S1b_gap_G_parity_swap", "gap_G_parity_swap", "scale_all"),
            ("S2_headroom_parity_swap", "headroom_champ_parity_swap", "scale_all"),
            ("NAIVE_range_AUDIT_ONLY", "gap_naive", "scale_all"),
            ("NAIVE_champ_regret_AUDIT_ONLY", "headroom_champ_naive", "scale_all")):
        out[name] = AT.aggregate(rl, key, scale, n_boot=BOOT_REPS, seed=BOOT_SEED)
    out["_label"] = label
    return out


def cut_blocks(if_rows, oof_rows, key="headroom_champ", scale="scale_all"):
    """Per-stratum / per-profile / per-phase / capped cuts, both judges. Never a branch input."""
    cuts = defaultdict(lambda: {"if": [], "oof": [], "roots": []})
    for rid, ir in sorted(if_rows.items()):
        orr = oof_rows.get(rid)
        if orr is None:
            continue
        names = [f"stratum:{ir['stratum']}", f"profile:{ir['rules_profile']}",
                 f"phase:{ir['phase_bucket']}",
                 "capped_only" if ir.get("capped") else "uncapped_only"]
        for nm in names:
            cuts[nm]["if"].append(ir[key] * ir[scale])
            cuts[nm]["oof"].append(orr[key] * orr[scale])
            cuts[nm]["roots"].append(ir["root_id"])
    out = {}
    for nm, d in sorted(cuts.items()):
        mi, si, n, g = AT.cluster_robust(d["if"], d["roots"])
        mo, so, _, _ = AT.cluster_robust(d["oof"], d["roots"])
        out[nm] = {"n": n, "n_roots": g,
                   "H_IF": mi, "se_IF": si, "z_IF": (mi / si) if si else float("nan"),
                   "H_OOF": mo, "se_OOF": so, "z_OOF": (mo / so) if so else float("nan"),
                   "R_point": (mo / mi) if mi else float("nan")}
    return out


# --------------------------------------------------------------------------- #
def adjudicate(v: dict) -> dict:
    """READ_RULE §3-§4. Mechanical; mutually exclusive by construction."""
    pre = v["preconditions"]
    fails = [k for k, ok in pre.items() if not ok]
    if fails:
        return {"branch": "U-UNREADABLE", "failed_preconditions": fails,
                "read": "Report cost, integrity and the failed gate. Nothing closes, "
                        "nothing is licensed, nothing is re-labelled. Holdout unburned."}
    z = v["z_OOF"]
    R, R_lo, R_hi = v["R"], v["R_lo"], v["R_hi"]
    Rn = v["R_norm"]
    zsw = v["z_swap_OOF"]
    cal = bool(v["g_cal"]["pass"])

    C = bool(z == z and z >= Z_BAR)
    K = bool(R_hi == R_hi and R_hi < RATIO_BAR and Rn == Rn and Rn < RATIO_BAR and cal)

    if C and (R == R and R >= RATIO_BAR) and (Rn == Rn and Rn >= RATIO_BAR) \
            and (zsw == zsw and zsw > 0):
        br = "C-CONFIRM"
    elif (not C) and K:
        br = "X-COLLAPSE"
    elif (not C) and (not K) and (R_lo == R_lo and R_lo <= 0.0):
        br = "P-BLIND"
    else:
        br = "B-PARTIAL"
    return {"branch": br, "C_z_ge_2": C, "K_collapse_conjunct": K,
            "g_cal_pass": cal, "failed_preconditions": []}


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--if-per-position", required=True)
    ap.add_argument("--oof-per-position", required=True)
    ap.add_argument("--if-records", required=True)
    ap.add_argument("--oof-records", required=True)
    ap.add_argument("--plan-dir", required=True)
    ap.add_argument("--if-verdict", required=True,
                    help="analyze_tiletie VERDICT.json for the IN-FAMILY leg (integrity)")
    ap.add_argument("--oof-verdict", required=True,
                    help="analyze_tiletie VERDICT.json for the OUT-OF-FAMILY leg")
    ap.add_argument("--holdout", default=str(REPO / "measurement/tiletie_mining_20260814/"
                                                    "HOLDOUT_ROOTS.json"))
    ap.add_argument("--pilot-rids", default=str(REPO / "measurement/tiletie_oof_20260814/"
                                                       "PILOT_RIDS.json"))
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--planned-n", type=int, default=502)
    ap.add_argument("--sigma-game", type=float, default=AT.SIGMA_GAME_FIXED_V1)
    a = ap.parse_args(argv)

    if_rows = load_per_position(a.if_per_position)
    oof_rows = load_per_position(a.oof_per_position)
    shared = sorted(set(if_rows) & set(oof_rows))
    if_rows = {r: if_rows[r] for r in shared}
    oof_rows = {r: oof_rows[r] for r in shared}

    arms = json.loads((Path(a.plan_dir) / "ARMS.json").read_text())
    holdout = set(json.loads(Path(a.holdout).read_text())["holdout_roots"])
    pilot = set(json.loads(Path(a.pilot_rids).read_text())["rids"])
    m = int(json.loads((Path(a.plan_dir) / "POSITIONS_PLAN.json").read_text())["m_worlds"])

    if_recs = _records_by_rid(a.if_records, set(shared))
    oof_recs = _records_by_rid(a.oof_records, set(shared))
    crn = crn_identity(if_recs, oof_recs)
    cal = g_cal(if_recs, oof_recs, arms, m)

    ifb = stat_block(if_rows, "clair-puct (IN-FAMILY)")
    oofb = stat_block(oof_rows, "tier1-greedy (OUT-OF-FAMILY)")

    H_IF = ifb["S2_headroom_all"]["mean"]
    H_OOF = oofb["S2_headroom_all"]["mean"]
    z_IF = ifb["S2_headroom_all"]["z"]
    z_OOF = oofb["S2_headroom_all"]["z"]
    S1_IF = ifb["S1a_sigma2_arm_all"]["mean"]
    S1_OOF = oofb["S1a_sigma2_arm_all"]["mean"]

    num = [oof_rows[r]["headroom_champ"] * oof_rows[r]["scale_all"] for r in shared]
    den = [if_rows[r]["headroom_champ"] * if_rows[r]["scale_all"] for r in shared]
    roots = [if_rows[r]["root_id"] for r in shared]
    R_med, R_lo, R_hi, n_fin, frac_den_le_0 = paired_ratio_bootstrap(num, den, roots)
    R = (H_OOF / H_IF) if H_IF else float("nan")
    if S1_IF is not None and S1_IF > 0:
        norm_if = H_IF / math.sqrt(S1_IF)
        norm_oof = (H_OOF / math.sqrt(S1_OOF)) if (S1_OOF is not None and S1_OOF > 0) else 0.0
        R_norm = norm_oof / norm_if if norm_if else float("nan")
    else:
        R_norm = float("nan")

    holdout_leak = sorted(r for r in shared if arms[r]["root_id"] in holdout)
    pilot_leak = sorted(set(shared) & pilot)

    # analyze_tiletie's own per-judge §2.1 witnesses (values_a bit-identity across
    # legs, seed drift, CRN, checksum, arm index, degenerate afterstates).
    per_judge_integrity = {}
    for name, path in (("in_family", a.if_verdict), ("out_of_family", a.oof_verdict)):
        blk = json.loads(Path(path).read_text()).get("integrity", {})
        per_judge_integrity[name] = {k: len(vv) if isinstance(vv, list) else vv
                                     for k, vv in blk.items()}
    ga = all(v == 0 for j in per_judge_integrity.values() for v in j.values())

    pre = {
        "G-CRN": bool(crn["ok"]),
        "G-ARM": crn["arm_mismatch"] == 0,
        "G-VA": bool(ga),
        "G-HOLDOUT": not holdout_leak,
        "G-PILOT": not pilot_leak,
        "G-N": len(shared) >= N_FLOOR,
        "G-DENOM": bool(H_IF is not None and H_IF > 0
                        and z_IF == z_IF and z_IF >= Z_BAR
                        and S1_IF is not None and S1_IF > 0),
    }

    verdict = {
        "schema": "carcassonne-tiletie-oof-readout/v1",
        "design_doc": "measurement/tiletie_oof_20260814/DESIGN.md",
        "read_rule": "measurement/tiletie_oof_20260814/READ_RULE.md",
        "judges": {"in_family": "clair-puct (production curve125 leaf, "
                                "leaf hash a36d2e15a3b3d71d, PUCT @ 100 clairvoyant sims)",
                   "out_of_family": "tier1-greedy (RuleBasedPlayer, v1 OBJECT leaf "
                                    "virtual_score_inplace, 1-ply argmax, no search, "
                                    "python-only)"},
        "n_positions": len(shared), "n_roots": len(set(roots)),
        "planned_n": a.planned_n,
        "completion_frac": len(shared) / a.planned_n if a.planned_n else None,
        "H_IF": H_IF, "se_IF": ifb["S2_headroom_all"]["se_cluster"], "z_IF": z_IF,
        "H_OOF": H_OOF, "se_OOF": oofb["S2_headroom_all"]["se_cluster"], "z_OOF": z_OOF,
        "z_swap_OOF": oofb["S2_headroom_parity_swap"]["z"],
        "S1a_IF_all": S1_IF, "S1a_OOF_all": S1_OOF,
        "S1a_ratio": (S1_OOF / S1_IF) if S1_IF else float("nan"),
        "R": R, "R_boot_median": R_med, "R_lo": R_lo, "R_hi": R_hi,
        "R_boot_finite_reps": n_fin, "R_norm": R_norm,
        "R_boot_frac_denominator_le_0": frac_den_le_0,
        "ratio_bar": RATIO_BAR, "z_bar": Z_BAR,
        "g_cal": cal,
        "sign_check": sign_check(if_rows, oof_rows, "headroom_champ", "scale_all"),
        "crn_integrity": crn,
        "per_judge_integrity": per_judge_integrity,
        "holdout_leak": holdout_leak, "pilot_leak": pilot_leak,
        "preconditions": pre,
        "statistics": {"in_family": ifb, "out_of_family": oofb},
        "cuts_never_adjudicated": cut_blocks(if_rows, oof_rows),
        "elo": {
            "IF": AT.pts_to_elo(H_IF * AT.FULLSET_EXTRAP, sigma_game=a.sigma_game)
            if H_IF is not None else None,
            "OOF": AT.pts_to_elo(H_OOF * AT.FULLSET_EXTRAP, sigma_game=a.sigma_game)
            if H_OOF is not None else None,
            "note": "x1.40 full-set extrapolation and the /3.2 chain applied IDENTICALLY "
                    "to both judges, so they cancel out of R. Every pricing §4.3 caveat "
                    "is inherited verbatim: NON_ADDITIVITY=3.2 is n=1 with a /5.23 "
                    "low-end bracket (a +-1.6x bracket, not a point).",
        },
        "resolution": {
            "sd_positions_OOF": oofb["S2_headroom_all"]["sd_positions"],
            "two_sigma_pts": (2 * oofb["S2_headroom_all"]["se_cluster"])
            if oofb["S2_headroom_all"]["se_cluster"] else None,
            "two_sigma_elo": AT.pts_to_elo(
                2 * oofb["S2_headroom_all"]["se_cluster"] * AT.FULLSET_EXTRAP,
                sigma_game=a.sigma_game)
            if oofb["S2_headroom_all"]["se_cluster"] else None,
        },
        "governance": ("Measurement only. 0 games. No experiments/results.csv row, no "
                       "band, no governance/BAND_REGISTRY.csv entry, no claim id, "
                       "governance/PRODUCTION.yaml untouched -- on EVERY branch. The "
                       "holdout (120 roots / 211 positions) was never read."),
    }
    # n that would resolve R to +-0.25 at the realized dispersion
    half = (R_hi - R_lo) / 2.0 if (R_hi == R_hi and R_lo == R_lo) else float("nan")
    verdict["resolution"]["R_half_width"] = half
    verdict["resolution"]["n_for_R_pm_0.25"] = (
        len(shared) * (half / 0.25) ** 2 if half == half else None)
    verdict["resolution"]["note"] = (
        "n scaling assumes se ~ 1/sqrt(n) at the realized cluster structure; the dev "
        "supply is capped at 522 positions and the 211-position holdout is NOT "
        "available to extend it.")

    verdict["adjudication"] = adjudicate(verdict)

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "READOUT.json").write_text(json.dumps(verdict, indent=1, default=str))
    (out / "READOUT.md").write_text(render(verdict))
    print(render(verdict))
    print(f"\n[wrote] {out/'READOUT.json'}\n[wrote] {out/'READOUT.md'}")
    return 0


def _f(x, nd=4):
    if x is None:
        return "n/a"
    try:
        if x != x:
            return "nan"
        return f"{x:+.{nd}f}"
    except (TypeError, ValueError):
        return str(x)


def render(v: dict) -> str:
    L = []
    A = L.append
    A("# TILE-TIE OUT-OF-FAMILY RE-PRICING — READ-OUT")
    A("")
    A(f"**Branch: `{v['adjudication']['branch']}`** — adjudicated mechanically by "
      f"[READ_RULE.md](READ_RULE.md), committed before any number existed.")
    A("")
    A(f"- in-family judge: {v['judges']['in_family']}")
    A(f"- out-of-family judge: {v['judges']['out_of_family']}")
    A(f"- n = **{v['n_positions']}** positions / {v['n_roots']} roots "
      f"({100.0*(v['completion_frac'] or 0):.1f}% of the planned {v['planned_n']}); "
      f"M = 32 CRN worlds, salt `tiletie-v1`, **shared bit-for-bit with the primary**")
    A("")
    A("## 1. The two pre-registered statistics, both judges, same positions")
    A("")
    A("| statistic | IN-FAMILY `clair-puct` | z | OUT-OF-FAMILY `tier1-greedy` | z | OOF/IF |")
    A("|---|---|---|---|---|---|")
    ifb, oofb = v["statistics"]["in_family"], v["statistics"]["out_of_family"]
    for k in ifb:
        if k.startswith("_"):
            continue
        i, o = ifb[k], oofb[k]
        ratio = (o["mean"] / i["mean"]) if (i["mean"] not in (None, 0)
                                            and o["mean"] is not None) else float("nan")
        star = " ⭐" if k == "S2_headroom_all" else (
            " ⭐" if k == "S1a_sigma2_arm_all" else "")
        note = " *(audit only, never quoted)*" if "NAIVE" in k else (
            " *(diagnostic)*" if "parity_swap" in k else "")
        A(f"| `{k}`{star}{note} | {_f(i['mean'])} "
          f"[{_f(i['boot_lo'])}, {_f(i['boot_hi'])}] | {_f(i['z'],2)} | "
          f"{_f(o['mean'])} [{_f(o['boot_lo'])}, {_f(o['boot_hi'])}] | {_f(o['z'],2)} | "
          f"{_f(ratio,3)} |")
    A("")
    A("⚠️ S1b carries its pricing §4.1 sentence: `G` is a *downward-biased estimate of "
      "the true range and an unbiased test of the null*. The naive rows exist only so "
      "the winner's-curse correction is auditable and are **never results**.")
    A("")
    A("## 2. The retention ratio R (READ_RULE §2)")
    A("")
    A(f"- `H_IF`  = **{_f(v['H_IF'])}** pts/tied tile ply (se {_f(v['se_IF'])}, "
      f"z {_f(v['z_IF'],2)})")
    A(f"- `H_OOF` = **{_f(v['H_OOF'])}** pts/tied tile ply (se {_f(v['se_OOF'])}, "
      f"z {_f(v['z_OOF'],2)}); parity-swap z {_f(v['z_swap_OOF'],2)}")
    A(f"- **`R = H_OOF / H_IF` = {_f(v['R'],3)}**, paired-root-bootstrap 95% CI "
      f"**[{_f(v['R_lo'],3)}, {_f(v['R_hi'],3)}]** "
      f"(median {_f(v['R_boot_median'],3)}, {_f(v['R_boot_finite_reps'],0)} finite reps)")
    A(f"- `R_norm` (noise-normalised companion) = **{_f(v['R_norm'],3)}**  "
      f"[S1a_OOF {_f(v['S1a_OOF_all'])} / S1a_IF {_f(v['S1a_IF_all'])} = "
      f"{_f(v['S1a_ratio'],3)}]")
    A(f"- bar = **{v['ratio_bar']:.2f}** (half the in-family headroom ≈ the project's "
      f"±17-elo resolution bar)")
    A(f"- bootstrap reps whose DENOMINATOR crossed 0: "
      f"**{_f(v.get('R_boot_frac_denominator_le_0'),4)}** — a material rate would make "
      f"the ratio percentile interval bimodal and is reported so it cannot hide.")
    A("")
    A(f"Elo through the identical ÷3.2 chain (×1.40 full-set extrapolation applied to "
      f"both, so it cancels out of R): IF **{_f(v['elo']['IF'],2)}** · "
      f"OOF **{_f(v['elo']['OOF'],2)}**. {v['elo']['note']}")
    A("")
    A("## 3. `G-CAL` — the blind-ruler control (DESIGN §4.5)")
    A("")
    c = v["g_cal"]
    A(f"- selected the top {c.get('quantile')} quantile of |primary selection-half arm "
      f"delta| ⇒ **{c.get('n_selected')}** legs over {c.get('n_roots')} roots "
      f"(of {c.get('n_legs_all')} paired legs; threshold {_f(c.get('threshold_abs_d_if_sel'))})")
    A(f"- sign-aligned out-of-family evaluation-half mean = "
      f"**{_f(c.get('mean_sign_aligned_d_oof'))}** pts, se {_f(c.get('se_cluster'))}, "
      f"**z {_f(c.get('z'),2)}** vs bar +{c.get('bar')} ⇒ "
      f"**{'PASS' if c.get('pass') else 'FAIL'}**")
    A(f"- {c.get('note','')}")
    A("")
    A("## 4. The pricing §5 sign check (E4 autopsy taxonomy, unchanged)")
    A("")
    s = v["sign_check"]
    A(f"- {s['n_agree']}/{s['n_both_nonzero']} = **{_f(s['agreement_rate'],3)}** sign "
      f"agreement, exact two-sided binomial **p {s['binomial_p_two_sided']:.3g}**; "
      f"primary aggregate sign {s['primary_mean_sign_only']:+d}, out-of-family "
      f"aggregate sign {s['secondary_mean_sign_only']:+d}")
    A(f"- **{s['corroboration']}**")
    A(f"- benchmarks: {s['benchmarks']}")
    A("")
    A("## 5. Integrity")
    A("")
    for k, val in sorted(v["crn_integrity"].items()):
        if k in ("examples", "ok"):
            continue
        A(f"- `{k}`: **{val}**")
    A(f"- holdout leak: **{len(v['holdout_leak'])}** · pilot leak: "
      f"**{len(v['pilot_leak'])}**")
    for jn, blk in v.get("per_judge_integrity", {}).items():
        A(f"- `{jn}` analyze_tiletie §2.1 witnesses: "
          + " · ".join(f"{k} {val}" for k, val in sorted(blk.items())))
    A("")
    A("| precondition | result |")
    A("|---|---|")
    for k, ok in v["preconditions"].items():
        A(f"| `{k}` | {'PASS' if ok else '**FAIL**'} |")
    A("")
    A("## 6. Resolution and sizing")
    A("")
    r = v["resolution"]
    A(f"- realized out-of-family per-position sd = {_f(r['sd_positions_OOF'])} pts")
    A(f"- realized 2σ resolution = {_f(r['two_sigma_pts'])} pts "
      f"= {_f(r['two_sigma_elo'],2)} elo")
    A(f"- R half-width = {_f(r['R_half_width'],3)}; n for R to ±0.25 ≈ "
      f"{('%.0f' % r['n_for_R_pm_0.25']) if r.get('n_for_R_pm_0.25') else 'n/a'}")
    A("")
    A("## 7. Cuts (emitted beside the pooled read, NEVER adjudicated on)")
    A("")
    A("| cut | n | H_IF | z_IF | H_OOF | z_OOF | R |")
    A("|---|---|---|---|---|---|---|")
    for nm, d in v["cuts_never_adjudicated"].items():
        A(f"| {nm} | {d['n']} | {_f(d['H_IF'])} | {_f(d['z_IF'],2)} | "
          f"{_f(d['H_OOF'])} | {_f(d['z_OOF'],2)} | {_f(d['R_point'],3)} |")
    A("")
    A("Per-stratum / per-profile / per-phase reads are underpowered on their own and "
      "are labelled as such; **no branch is adjudicated on a cut**.")
    A("")
    A("## 8. Governance")
    A("")
    A(v["governance"])
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
