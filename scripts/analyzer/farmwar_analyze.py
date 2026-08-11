#!/usr/bin/env python3
"""FARM-WAR DISCRIMINATOR — the analysis, exactly as pre-registered.

Pre-registration: measurement/analyzer_evloss_20260805/FARMWAR_PREREG.md (committed
226a676, BEFORE any cell ran). This module implements its decision map and NOTHING
adjacent: no post-hoc stratum, no one-sided test, no pooling the epochs when they
disagree in sign.

  * Statistic per ply: Δ = V(played) − V(best) in engine points, Joshua's seat. It is
    the scorer's `delta` field verbatim — `position_delta` returns mean(V_B − V_A) and the
    positions were emitted with pick_a = the champion's pick, pick_b = his.
  * TWO-SIDED z throughout ("a negative result is informative here — it vindicates the
    leaf").
  * Branch precedence 1 -> 2 -> 3 -> 4, FIRST MATCH WINS.
  * Cluster-robust se on ROOT POSITION. Each E4 ply is its own root, so the root-clustered
    se equals the naive one by construction; that is reported as a fact, not hidden. A
    GAME-clustered se is computed as well — six games contribute many plies each, which is
    the correlation the pre-registration's "design effect lesson" is actually about — and
    is reported as a SENSITIVITY beside the pre-registered number, never in place of it.
  * The Tier-1 leg is read for SIGN ONLY (prereg §Judges); its magnitude is never compared
    to the primary's.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SCHEMA = "carcassonne-analyzer-farmwar-verdict/v1"

#: |z| at which the pre-registration's branches fire.
Z_GATE = 2.0
#: Two-sided 95% normal quantile, for the reported CI.
Z_95 = 1.959963984540054


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def _sd(xs):
    xs = list(xs)
    if len(xs) < 2:
        return float("nan")
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def cluster_se(values: list, clusters: list) -> dict:
    """CR1 cluster-robust standard error of a MEAN.

    For the mean-only model the sandwich reduces to
    ``se = sqrt(c * sum_g (sum_{i in g} e_i)^2) / n`` with residuals ``e_i = y_i - ybar``
    and the usual small-G correction ``c = G/(G-1)``. With one observation per cluster it
    collapses to the naive se (up to that correction), which is exactly what makes the
    root-clustered number here a statement rather than a manipulation.
    """
    n = len(values)
    if n < 2:
        return {"se": float("nan"), "n_clusters": len(set(clusters)), "design_effect": None}
    ybar = _mean(values)
    per = {}
    for y, g in zip(values, clusters):
        per[g] = per.get(g, 0.0) + (y - ybar)
    G = len(per)
    if G < 2:
        return {"se": float("nan"), "n_clusters": G, "design_effect": None}
    meat = sum(s * s for s in per.values()) * (G / (G - 1.0))
    se = math.sqrt(meat) / n
    naive = _sd(values) / math.sqrt(n)
    return {"se": se, "n_clusters": G,
            "design_effect": (se / naive) ** 2 if naive > 0 else None}


def stratum_stats(rows: list, name: str) -> dict:
    """n / mean / se / two-sided z / 95% CI for one stratum, with both clusterings."""
    vals = [float(r["delta"]) for r in rows]
    n = len(vals)
    if n == 0:
        return {"stratum": name, "n": 0}
    mean = _mean(vals)
    sd = _sd(vals)
    naive_se = sd / math.sqrt(n) if n > 1 else float("nan")
    root = cluster_se(vals, [r["root_id"] for r in rows])
    game = cluster_se(vals, [r.get("game_label", r["root_id"]) for r in rows])
    se = root["se"]                      # the PRE-REGISTERED se
    z = mean / se if se and se == se and se > 0 else float("nan")
    return {
        "stratum": name,
        "n": n,
        "mean_delta_pts": mean,
        "sd_pts": sd,
        "se_naive": naive_se,
        "se_cluster_root": root["se"],
        "n_root_clusters": root["n_clusters"],
        "root_design_effect": root["design_effect"],
        "se_cluster_game": game["se"],
        "n_game_clusters": game["n_clusters"],
        "game_design_effect": game["design_effect"],
        "z_two_sided": z,
        "z_cluster_game": (mean / game["se"]
                           if game["se"] and game["se"] == game["se"] and game["se"] > 0
                           else float("nan")),
        "ci95_lo": mean - Z_95 * se,
        "ci95_hi": mean + Z_95 * se,
        "ci95_covers_zero": bool((mean - Z_95 * se) <= 0.0 <= (mean + Z_95 * se)),
        "n_positive": sum(1 for v in vals if v > 0),
        "n_negative": sum(1 for v in vals if v < 0),
        "n_zero": sum(1 for v in vals if v == 0),
        "mean_within_var": _mean(float(r["within_var"]) for r in rows
                                 if r.get("within_var") is not None),
    }


def decide(farm: dict, control: dict) -> dict:
    """The pre-registered decision map. Branch precedence 1 -> 2 -> 3 -> 4, first match
    wins; every branch's predicate is evaluated and reported so the precedence is auditable
    rather than asserted."""
    fz = farm.get("z_two_sided", float("nan"))
    cz = control.get("z_two_sided", float("nan"))
    fm = farm.get("mean_delta_pts", float("nan"))
    cm = control.get("mean_delta_pts", float("nan"))
    f_sig = abs(fz) >= Z_GATE if fz == fz else False
    c_sig = abs(cz) >= Z_GATE if cz == cz else False

    b1 = bool(fm > 0 and f_sig
              and (control.get("ci95_covers_zero") or cm < 0.5 * fm))
    b2 = bool(fm <= 0 and f_sig)
    b3 = bool(fm > 0 and f_sig and cm > 0 and c_sig)

    if b1:
        branch, verdict = 1, ("H1 FIRES: the champion's leaf mis-prices contested farm "
                              "wars. Localized evaluation defect, human-found. NOT a "
                              "statement that the champion is weak.")
    elif b2:
        branch, verdict = 2, ("H2: the champion's picks really are better. His moves are "
                              "genuinely worse; the EV-loss readouts stand as written.")
    elif b3:
        branch, verdict = 3, ("H3: general same-family self-preference in the grader. A "
                              "statement about the instrument, not about farms.")
    else:
        branch, verdict = 4, ("INCONCLUSIVE. Report the estimate and its CI; promote "
                              "nothing. Default next step is MORE E4 GAMES, not more "
                              "compute on n=6.")
    return {
        "branch": branch,
        "verdict": verdict,
        "z_gate": Z_GATE,
        "predicates": {
            "branch1_farm_pos_sig_and_control_null_or_half": b1,
            "branch2_farm_nonpos_sig": b2,
            "branch3_both_pos_sig": b3,
            "farm_mean_gt_0": bool(fm > 0),
            "farm_abs_z_ge_gate": f_sig,
            "control_ci_covers_zero": bool(control.get("ci95_covers_zero")),
            "control_mean_lt_half_farm": bool(cm < 0.5 * fm) if fm == fm else None,
            "control_abs_z_ge_gate": c_sig,
        },
        "mints_claim_id": branch in (1, 3),
    }


def load_records(dirs: list) -> list:
    rows = []
    for d in dirs:
        for p in sorted(Path(d).glob("*.json")):
            rows.append(json.loads(p.read_text()))
    return rows


def sign_agreement(primary: list, secondary: list) -> dict:
    """Per-position SIGN agreement between the two judges. Sign only — the prereg forbids
    comparing the Tier-1 magnitude to the primary's."""
    a = {r["rid"]: float(r["delta"]) for r in primary if r.get("ok")}
    b = {r["rid"]: float(r["delta"]) for r in secondary if r.get("ok")}
    shared = sorted(set(a) & set(b))
    both_nonzero = [r for r in shared if a[r] != 0 and b[r] != 0]
    agree = sum(1 for r in both_nonzero
                if (a[r] > 0) == (b[r] > 0))
    n = len(both_nonzero)
    # exact two-sided binomial p against 50/50
    def _c(nn, kk):
        return math.comb(nn, kk)
    p = None
    if n:
        tail = sum(_c(n, k) for k in range(0, n + 1)
                   if abs(k - n / 2) >= abs(agree - n / 2)) / (2.0 ** n)
        p = min(1.0, tail)
    return {"n_shared": len(shared), "n_scored": n, "n_agree": agree,
            "agreement_rate": (agree / n if n else None),
            "binomial_p_two_sided": p,
            "primary_mean": _mean(a[r] for r in shared),
            "secondary_mean_SIGN_ONLY": _mean(b[r] for r in shared)}


def per_epoch(rows: list) -> dict:
    out = {}
    for prof in sorted({r.get("rules_profile") for r in rows if r.get("rules_profile")}):
        sub = [r for r in rows if r.get("rules_profile") == prof]
        vals = [float(r["delta"]) for r in sub]
        out[prof] = {"n": len(vals), "mean_delta_pts": _mean(vals),
                     "sd_pts": _sd(vals),
                     "se_naive": (_sd(vals) / math.sqrt(len(vals)) if len(vals) > 1
                                  else float("nan")),
                     "sign": (0 if not vals or _mean(vals) == 0
                              else (1 if _mean(vals) > 0 else -1))}
    signs = {v["sign"] for v in out.values() if v["n"] > 0}
    out["_epochs_agree_in_sign"] = bool(len(signs - {0}) <= 1)
    out["_pooling_licensed"] = out["_epochs_agree_in_sign"]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--strata", required=True)
    ap.add_argument("--primary-records", nargs="+", required=True)
    ap.add_argument("--secondary-records", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    strata = json.loads(Path(a.strata).read_text())
    primary = [r for r in load_records(a.primary_records)]
    secondary = [r for r in load_records(a.secondary_records)] if a.secondary_records else []

    ok = [r for r in primary if r.get("ok")]
    farm_rows = [r for r in ok if r.get("stratum") == "FARM"]
    ctrl_rows = [r for r in ok if r.get("stratum") == "CONTROL"]
    farm = stratum_stats(farm_rows, "FARM")
    control = stratum_stats(ctrl_rows, "CONTROL")

    gate_ok = farm.get("n", 0) >= strata["min_n_gate"] and control.get("n", 0) >= strata["min_n_gate"]
    dec = (decide(farm, control) if gate_ok else
           {"branch": None,
            "verdict": "INCONCLUSIVE BY CONSTRUCTION — a stratum fell under the "
                       "pre-registered n>=10 floor after scoring failures.",
            "mints_claim_id": False})

    sec_ok = [r for r in secondary if r.get("ok")]
    out = {
        "schema": SCHEMA,
        "prereg": "measurement/analyzer_evloss_20260805/FARMWAR_PREREG.md",
        "statistic": "delta = V(played) - V(best), engine points, Joshua's seat "
                     "(pick_a = champion, pick_b = human; position_delta returns B - A)",
        "stratifier_rule": strata.get("stratifier_rule"),
        "n_gate": {"min_n": strata["min_n_gate"], "gate_ok_at_stratify": strata["gate_ok"],
                   "gate_ok_after_scoring": bool(gate_ok)},
        "scoring_health": {
            "n_attempted": len(primary),
            "n_ok": len(ok),
            "n_failed": len(primary) - len(ok),
            "failures": [{"rid": r["rid"], "error": r.get("error")}
                         for r in primary if not r.get("ok")],
            "crn_verified_all": all(r.get("crn_verified") for r in ok),
            "distinct_afterstates_min": min((r.get("distinct_afterstates", 0) for r in ok),
                                            default=None),
            "m_worlds": sorted({r.get("m") for r in ok}),
        },
        "FARM": farm,
        "CONTROL": control,
        "decision": dec,
        "per_epoch": {"FARM": per_epoch(farm_rows), "CONTROL": per_epoch(ctrl_rows)},
        "per_game_FARM": {
            g: {"n": sum(1 for r in farm_rows if r.get("game_label") == g),
                "mean_delta_pts": _mean(float(r["delta"]) for r in farm_rows
                                        if r.get("game_label") == g)}
            for g in sorted({r.get("game_label") for r in farm_rows})},
        "tier1_sign_check": (
            {"note": "SIGN ONLY — the Tier-1 judge is 1.83x noisier and has no curve125; "
                     "its magnitude is never comparable to the primary's.",
             "FARM": sign_agreement([r for r in ok if r.get("stratum") == "FARM"],
                                    [r for r in sec_ok if r.get("stratum") == "FARM"]),
             "CONTROL": sign_agreement([r for r in ok if r.get("stratum") == "CONTROL"],
                                       [r for r in sec_ok if r.get("stratum") == "CONTROL"]),
             "FARM_stratum_mean_sign_secondary": (
                 1 if _mean(float(r["delta"]) for r in sec_ok
                            if r.get("stratum") == "FARM") > 0 else -1),
             "secondary_FARM": stratum_stats(
                 [r for r in sec_ok if r.get("stratum") == "FARM"], "FARM/tier1"),
             "secondary_CONTROL": stratum_stats(
                 [r for r in sec_ok if r.get("stratum") == "CONTROL"], "CONTROL/tier1"),
             }
            if sec_ok else {"ran": False}),
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in
                      ("n_gate", "FARM", "CONTROL", "decision")}, indent=2))
    print(f"[analyze] -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
