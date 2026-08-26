#!/usr/bin/env python3
"""R2 — the TAXONOMY read of the champion EV-loss autopsy.

Implements `R2_PREREG.md` (committed blind, before any per-category number existed) on the
banked R1 judged corpus. Adds NO compute to the corpus: it reads
`positions/positions_meta.jsonl` (the A4 covariate side file) and
`judge/<leg>/records/*.json`, and reuses R1's estimator arithmetic verbatim from
`r2_estimator.py`.

    D_arm(i)     = record["delta"]  = V*(arm) - V*(played)
    R_champ(i)   = max(0, D_leaf, D_sib2, D_sib3, D_sib4)     # PLAN.md §1
    G_search(i)  = R_leaf(i) - R_champ(i) = -D_leaf(i)        # identity, prereg §2
                                                              # missing leaf leg => 0 (A6)

Everything is HT-reweighted by `1/pi_s` (Hajek) and clustered on `game_id`.

MANDATORY reconciliation (fails loudly, prereg §6): the pooled read must reproduce R1's
`R_champ.mean_hajek` exactly, and every partition axis must recombine to it.

Writes NOTHING into the R0/R1 artifact tree; output goes to `--out-dir`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r2_estimator import (  # noqa: E402
    Z95, cluster_sandwich, contrast_cluster, hajek, holm, load_leg, two_sided_p, wsd,
)

SCHEMA = "carcassonne-evloss-autopsy-r2-readout/v1"
ARMS = ("leaf", "sib2", "sib3", "sib4")
BAR = 0.5                      # PLAN.md §7 B-CEILING bar; the R2 primary bar
STAR_GSEARCH_Z = 2.0           # SCOPE §4: G_search "not significantly > 0"
HOLDOUT_SEED = 20260826
PERM_REPS = 10000
PERM_SEED = 20260826

#: R1_READOUT.json values that the pooled reconciliation must reproduce.
R1_EXPECT = {
    "mean_hajek": 1.4928485121941815,
    "se_cluster_robust": 0.07179985263453552,
    "n_positions_scored": 800,
    "n_games": 498,
    "n_by_leg": {"leaf": 323, "sib2": 800, "sib3": 800, "sib4": 715, "rnd": 200},
}

# --------------------------------------------------------------------------- #
# 1. THE CLASSIFIER — R2_PREREG.md §3 and §4                                   #
#    Pure functions of the `taxonomy` covariate block. No judged value is in    #
#    scope here, by construction: nothing in this section can see an outcome.   #
# --------------------------------------------------------------------------- #
STRATUM_BUCKETS = ("DEG", "FARM", "CLOISTER", "CITY", "ROAD", "NEUTRAL")
DECISION_BUCKETS = ("tile", "meeple")
PHASE_BUCKETS = ("opening", "middle", "endgame")
MOVE_KIND_BUCKETS = ("farm", "cloister", "city", "road", "pass")
COMMIT_BUCKETS = ("spend", "hold")
CONTEST_FLAGS = ("contested_best", "contested_played",
                 "reinforce_losing_contest_best", "reinforce_losing_contest_played",
                 "tie_force_join_best", "tie_force_join_played")
F7_BUCKETS = ("low", "high")

EXPLOIT_BUCKETS = ("H2_STEAL_AVAILABLE", "H2_STEAL_TAKEN", "H2_STEAL_FOREGONE",
                   "H2_REINFORCE_LOSING", "H4_LATE_FARM", "H4_DECISIVE_FARM",
                   "H2xH4_FARM_STEAL")

#: axis -> (is_partition, domain_predicate_name). Used by the reconciliation.
PARTITION_AXES = {
    "structure": None,          # over all 800
    "decision_type": None,      # over all 800
    "phase_third": None,        # over all 800
    "f7_cross_world_spread": None,   # over all 800 (median split)
    "move_kind": "meeple",      # over the meeple subset only
}

DECISIVE_FARM_SHARE = 0.5


def _truthy_list(v):
    return bool(v) if isinstance(v, (list, tuple, set)) else bool(v)


def farm_engaged(tax: dict) -> bool:
    """R2_PREREG.md §4: any farm engagement by either arm at this ply."""
    if tax.get("stratum") == "FARM" or tax.get("structure") == "farm":
        return True
    if tax.get("move_kind_best") == "farm" or tax.get("move_kind_played") == "farm":
        return True
    for key in ("contested_best", "contested_played"):
        if "farm" in (tax.get(key) or ()):
            return True
    return False


def exploit_labels(tax: dict) -> dict:
    """The owner's H2/H4 categories as conjunctions of pre-registered covariates."""
    tfj_b = bool(tax.get("tie_force_join_best"))
    tfj_p = bool(tax.get("tie_force_join_played"))
    rlc_p = bool(tax.get("reinforce_losing_contest_played"))
    late_farm = (tax.get("phase_third") == "endgame") and farm_engaged(tax)
    share = tax.get("farm_share")
    decisive = bool(late_farm and share is not None
                    and float(share) >= DECISIVE_FARM_SHARE)
    return {
        "H2_STEAL_AVAILABLE": tfj_b,
        "H2_STEAL_TAKEN": tfj_p,
        "H2_STEAL_FOREGONE": bool(tfj_b and not tfj_p),
        "H2_REINFORCE_LOSING": rlc_p,
        "H4_LATE_FARM": bool(late_farm),
        "H4_DECISIVE_FARM": decisive,
        "H2xH4_FARM_STEAL": bool(tfj_b and "farm" in (tax.get("contested_best") or ())),
    }


def classify(tax: dict, f7_median: float | None) -> dict:
    """Full pre-registered bucket membership for one position. -> {bucket_name: bool}"""
    out: dict[str, bool] = {}

    strat = tax.get("stratum")
    for b in STRATUM_BUCKETS:
        out[f"structure={b}"] = (strat == b)

    dt = tax.get("decision_type")
    for b in DECISION_BUCKETS:
        out[f"decision_type={b}"] = (dt == b)

    ph = tax.get("phase_third")
    for b in PHASE_BUCKETS:
        out[f"phase_third={b}"] = (ph == b)

    mk = tax.get("move_kind_played")
    for b in MOVE_KIND_BUCKETS:
        out[f"move_kind={b}"] = (dt == "meeple" and mk == b)

    cd = tax.get("commit_direction")
    for b in COMMIT_BUCKETS:
        out[f"commit_direction={b}"] = (cd == b)

    for f in CONTEST_FLAGS:
        out[f"contest={f}"] = _truthy_list(tax.get(f))

    sp = tax.get("cross_world_spread")
    ok7 = (tax.get("cross_world_spread_status") == "ok_per_world_routeb"
           and sp is not None and f7_median is not None)
    out["f7_cross_world_spread=low"] = bool(ok7 and float(sp) <= f7_median)
    out["f7_cross_world_spread=high"] = bool(ok7 and float(sp) > f7_median)

    out.update(exploit_labels(tax))
    return out


def axis_of(bucket: str) -> str:
    return bucket.split("=", 1)[0] if "=" in bucket else "exploit"


# --------------------------------------------------------------------------- #
# 2. LOADING                                                                   #
# --------------------------------------------------------------------------- #
def build_rows(positions_dir: Path, judge_root: Path):
    meta = {}
    for line in (positions_dir / "positions_meta.jsonl").read_text().splitlines():
        if line.strip():
            m = json.loads(line)
            meta[m["rid"]] = m

    legs = {leg: load_leg(judge_root, leg) for leg in (*ARMS, "rnd")}
    n_by_leg = {k: len(v) for k, v in legs.items()}

    rows = []
    for rid, m in meta.items():
        ds = {leg: legs[leg][rid]["delta"] for leg in ARMS if rid in legs[leg]}
        if not ds:
            continue
        arm, dmax = max(ds.items(), key=lambda kv: kv[1])
        d_leaf = ds.get("leaf", 0.0)          # A6: absent => leaf argmax == played => 0
        rows.append({
            "rid": rid, "game_id": m["game_id"], "ply": m["ply"],
            "w": m["ht_weight"] or 1.0,
            "R_champ": max(0.0, dmax),
            "G_search": -d_leaf,
            "argmax_arm": (arm if dmax > 0 else "played"),
            "n_arms_scored": len(ds),
            "leaf_leg_present": "leaf" in ds,
            "d_rnd": (legs["rnd"][rid]["delta"] if rid in legs["rnd"] else None),
            "deltas": ds,
            "tax": m["taxonomy"],
            "per_world_ok": all(
                len(legs[leg][rid].get("per_world_delta") or []) == legs[leg][rid].get("m")
                for leg in ds),
        })
    rows.sort(key=lambda r: (int(r["game_id"]), int(r["ply"])))
    return rows, n_by_leg, meta


# --------------------------------------------------------------------------- #
# 3. PER-CATEGORY STATISTICS                                                   #
# --------------------------------------------------------------------------- #
def category_stats(rows, member, bar=BAR):
    sub = [r for r, m in zip(rows, member) if m]
    n = len(sub)
    out = {"n": n, "sum_w": sum(r["w"] for r in sub),
           "n_games": len({r["game_id"] for r in sub})}
    if n == 0:
        out.update({k: None for k in
                    ("R_champ", "se", "z_vs_0", "z_vs_bar", "ci95_lo", "UB95",
                     "G_search", "G_se", "G_z", "star_cell",
                     "contrast_theta", "contrast_se", "contrast_z", "deff")})
        return out
    v = [r["R_champ"] for r in sub]
    w = [r["w"] for r in sub]
    g = [r["game_id"] for r in sub]
    mu = hajek(v, w)
    se, deff, G = cluster_sandwich(v, w, g)
    gv = [r["G_search"] for r in sub]
    gmu = hajek(gv, w)
    gse, _, _ = cluster_sandwich(gv, w, g)
    theta, cse, cz = contrast_cluster([r["R_champ"] for r in rows],
                                      [r["w"] for r in rows],
                                      [r["game_id"] for r in rows], member)
    ok = se == se and se > 0
    gok = gse == gse and gse > 0
    z0 = mu / se if ok else float("nan")
    gz = gmu / gse if gok else float("nan")
    out.update({
        "R_champ": mu,
        "se": se if ok else None,
        "z_vs_0": z0 if ok else None,
        "z_vs_bar": ((mu - bar) / se) if ok else None,
        "ci95_lo": (mu - Z95 * se) if ok else None,
        "UB95": (mu + Z95 * se) if ok else None,
        "deff": deff if deff == deff else None,
        "G_search": gmu,
        "G_se": gse if gok else None,
        "G_z": gz if gok else None,
        "star_cell": bool(ok and gok and z0 >= 2.0 and gz < STAR_GSEARCH_Z),
        "contrast_theta": theta if theta == theta else None,
        "contrast_se": cse if cse == cse else None,
        "contrast_z": cz if cz == cz else None,
        "sd_per_position": wsd(v, w),
    })
    # R_rnd diagnostic (prereg §5.2) — n=200 subset, diagnostic only
    rsub = [r for r in sub if r["d_rnd"] is not None]
    if rsub:
        rr = [max([0.0] + list(r["deltas"].values()) + [r["d_rnd"]]) - r["d_rnd"]
              for r in rsub]
        out["R_rnd_diag"] = {"n": len(rsub), "R_rnd": hajek(rr, [r["w"] for r in rsub])}
    else:
        out["R_rnd_diag"] = {"n": 0, "R_rnd": None}
    return out


# --------------------------------------------------------------------------- #
# 4. LABEL-PERMUTATION NULL (prereg §5.3 + D-R2-2)                             #
# --------------------------------------------------------------------------- #
def permutation_null(rows, members, names, reps=PERM_REPS, seed=PERM_SEED, mode="game_block"):
    """max_b |z_b| under label permutation. `mode`:

      game_block  — permute whole GAME label-blocks among games of equal size (primary;
                    D-R2-2: the prereg's within-game permutation is near-degenerate at
                    cap 2 positions/game).
      within_game — the prereg's literal variant, reported beside it.
    """
    import numpy as np

    R = np.asarray([r["R_champ"] for r in rows], dtype=float)
    W = np.asarray([r["w"] for r in rows], dtype=float)
    M0 = np.asarray([[members[b][i] for b in names] for i in range(len(rows))], dtype=bool)

    gids = [r["game_id"] for r in rows]
    starts, blocks = [], []
    for i, g in enumerate(gids):
        if i == 0 or g != gids[i - 1]:
            starts.append(i)
    starts_a = np.asarray(starts)
    for j, s in enumerate(starts):
        e = starts[j + 1] if j + 1 < len(starts) else len(gids)
        blocks.append((s, e))
    G = len(blocks)

    by_size = defaultdict(list)
    for bi, (s, e) in enumerate(blocks):
        by_size[e - s].append(bi)

    def stat(M):
        Wa = (W[:, None] * M).sum(0)
        Wb = (W[:, None] * ~M).sum(0)
        good = (Wa > 0) & (Wb > 0)
        wa = W[:, None] * M
        wb = W[:, None] * ~M
        with np.errstate(invalid="ignore", divide="ignore"):
            mua = (wa * R[:, None]).sum(0) / Wa
            mub = (wb * R[:, None]).sum(0) / Wb
            e = wa * (R[:, None] - mua) / Wa - wb * (R[:, None] - mub) / Wb
            S = np.add.reduceat(e, starts_a, axis=0)
            var = (G / (G - 1.0)) * (S * S).sum(0)
            se = np.sqrt(np.maximum(var, 0.0))
            z_contrast = np.where(good & (se > 0), (mua - mub) / se, np.nan)
            # bucket-level z vs the +0.5 bar
            e2 = wa * (R[:, None] - mua)
            S2 = np.add.reduceat(e2, starts_a, axis=0)
            nb_games = (np.add.reduceat(M.astype(float), starts_a, axis=0) > 0).sum(0)
            corr = np.where(nb_games > 1, nb_games / np.maximum(nb_games - 1.0, 1e-9), np.nan)
            var2 = corr * (S2 * S2).sum(0) / np.maximum(Wa * Wa, 1e-30)
            se2 = np.sqrt(np.maximum(var2, 0.0))
            z_bar = np.where((Wa > 0) & (se2 > 0), (mua - BAR) / se2, np.nan)
        return z_contrast, z_bar

    obs_c, obs_b = stat(M0)
    obs = {"max_abs_z_contrast": float(np.nanmax(np.abs(obs_c))),
           "max_z_vs_bar": float(np.nanmax(obs_b))}

    rng = np.random.default_rng(seed)
    idx = np.arange(len(rows))
    hits_c = hits_b = 0
    dist_c, dist_b = [], []
    for _ in range(reps):
        perm = idx.copy()
        if mode == "within_game":
            for s, e in blocks:
                if e - s > 1:
                    perm[s:e] = rng.permutation(perm[s:e])
        else:
            for size, bis in by_size.items():
                order = rng.permutation(len(bis))
                for k, bi in enumerate(bis):
                    s0, e0 = blocks[bi]
                    s1, e1 = blocks[bis[order[k]]]
                    perm[s0:e0] = np.arange(s1, e1)
        zc, zb = stat(M0[perm])
        mc = float(np.nanmax(np.abs(zc))) if np.isfinite(zc).any() else float("nan")
        mb = float(np.nanmax(zb)) if np.isfinite(zb).any() else float("nan")
        dist_c.append(mc)
        dist_b.append(mb)
        if mc == mc and mc >= obs["max_abs_z_contrast"]:
            hits_c += 1
        if mb == mb and mb >= obs["max_z_vs_bar"]:
            hits_b += 1

    def pct(d, p):
        d = sorted(x for x in d if x == x)
        if not d:
            return None
        return d[min(len(d) - 1, max(0, int(round(p * (len(d) - 1)))))]

    return {
        "mode": mode, "reps": reps, "seed": seed, "n_buckets_in_family": len(names),
        "observed_max_abs_z_contrast": obs["max_abs_z_contrast"],
        "p_max_abs_z_contrast": (hits_c + 1) / (reps + 1),
        "null_p95_max_abs_z_contrast": pct(dist_c, 0.95),
        "null_median_max_abs_z_contrast": pct(dist_c, 0.5),
        "observed_max_z_vs_bar": obs["max_z_vs_bar"],
        "p_max_z_vs_bar": (hits_b + 1) / (reps + 1),
        "null_p95_max_z_vs_bar": pct(dist_b, 0.95),
        "null_median_max_z_vs_bar": pct(dist_b, 0.5),
    }


# --------------------------------------------------------------------------- #
# 5. MAIN                                                                      #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--share", default="/mnt/c/carc-shared/evloss_autopsy_20260824")
    ap.add_argument("--positions-dir", default=None)
    ap.add_argument("--judge-root", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--blind-stamp", required=True,
                    help="git commit hash of the blind classifier+prereg commit")
    ap.add_argument("--perm-reps", type=int, default=PERM_REPS)
    ap.add_argument("--copy-to", default=None, help="second location for R2_READOUT.json")
    args = ap.parse_args(argv)

    share = Path(args.share)
    positions_dir = Path(args.positions_dir or (share / "positions"))
    judge_root = Path(args.judge_root or (share / "judge"))
    out_dir = Path(args.out_dir or share)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows, n_by_leg, meta = build_rows(positions_dir, judge_root)
    print(f"[load] {len(rows)} positions, legs {n_by_leg}", flush=True)

    # ---- F7 median cut (covariate-only) ------------------------------------ #
    spreads = [r["tax"].get("cross_world_spread") for r in rows
               if r["tax"].get("cross_world_spread_status") == "ok_per_world_routeb"
               and r["tax"].get("cross_world_spread") is not None]
    f7_median = statistics.median(spreads) if spreads else None

    labels = [classify(r["tax"], f7_median) for r in rows]
    names = list(labels[0].keys()) if labels else []
    members = {b: [lab[b] for lab in labels] for b in names}

    # ---- (A) MANDATORY pooled reconciliation ------------------------------- #
    v = [r["R_champ"] for r in rows]
    w = [r["w"] for r in rows]
    g = [r["game_id"] for r in rows]
    pooled_mu = hajek(v, w)
    pooled_se, pooled_deff, pooled_G = cluster_sandwich(v, w, g)
    recon_pooled = {
        "R1_mean_hajek": R1_EXPECT["mean_hajek"],
        "R2_mean_hajek": pooled_mu,
        "delta_mean": pooled_mu - R1_EXPECT["mean_hajek"],
        "R1_se": R1_EXPECT["se_cluster_robust"],
        "R2_se": pooled_se,
        "delta_se": pooled_se - R1_EXPECT["se_cluster_robust"],
        "n_positions": len(rows), "n_positions_expected": R1_EXPECT["n_positions_scored"],
        "n_games": pooled_G, "n_games_expected": R1_EXPECT["n_games"],
        "n_by_leg": n_by_leg, "n_by_leg_expected": R1_EXPECT["n_by_leg"],
    }
    hard_fail = []
    if len(rows) != R1_EXPECT["n_positions_scored"]:
        hard_fail.append(f"n_positions {len(rows)} != {R1_EXPECT['n_positions_scored']}")
    if pooled_G != R1_EXPECT["n_games"]:
        hard_fail.append(f"n_games {pooled_G} != {R1_EXPECT['n_games']}")
    if n_by_leg != R1_EXPECT["n_by_leg"]:
        hard_fail.append(f"n_by_leg {n_by_leg} != {R1_EXPECT['n_by_leg']}")
    if abs(pooled_mu - R1_EXPECT["mean_hajek"]) > 1e-12:
        hard_fail.append(f"pooled mean delta {pooled_mu - R1_EXPECT['mean_hajek']:.3e}")
    if abs(pooled_se - R1_EXPECT["se_cluster_robust"]) > 1e-12:
        hard_fail.append(f"pooled se delta {pooled_se - R1_EXPECT['se_cluster_robust']:.3e}")
    recon_pooled["ok"] = not hard_fail
    recon_pooled["failures"] = hard_fail
    if hard_fail:
        print("[FATAL] R1 pooled reconciliation FAILED:", file=sys.stderr)
        for f in hard_fail:
            print("   " + f, file=sys.stderr)
        (out_dir / "FAILED_R2_reconciliation").write_text(
            "R1 pooled reconciliation failed\n" + "\n".join(hard_fail) + "\n")
        return 3
    print(f"[recon] pooled R_champ = {pooled_mu:.13f} == R1  ✓", flush=True)

    # ---- (B) per-category table -------------------------------------------- #
    table = {b: category_stats(rows, members[b]) for b in names}

    # ---- (C) partition recombination --------------------------------------- #
    recon_axes = {}
    for axis, domain in PARTITION_AXES.items():
        bs = [b for b in names if axis_of(b) == axis]
        if domain == "meeple":
            dom = [r["tax"].get("decision_type") == "meeple" for r in rows]
        else:
            dom = [True] * len(rows)
        dv = [r["R_champ"] for r, d in zip(rows, dom) if d]
        dw = [r["w"] for r, d in zip(rows, dom) if d]
        target = hajek(dv, dw) if dv else float("nan")
        num = sum(table[b]["sum_w"] * table[b]["R_champ"]
                  for b in bs if table[b]["n"] > 0)
        den = sum(table[b]["sum_w"] for b in bs if table[b]["n"] > 0)
        got = num / den if den else float("nan")
        cover = sum(table[b]["n"] for b in bs)
        recon_axes[axis] = {
            "buckets": bs, "domain": domain or "all",
            "n_domain": sum(1 for d in dom if d), "n_covered": cover,
            "target_mean": target, "recombined_mean": got,
            "delta": got - target,
            "ok": bool(cover == sum(1 for d in dom if d) and abs(got - target) < 1e-9),
        }
    recon_axes_ok = all(a["ok"] for a in recon_axes.values())

    # ---- (D) coverage / multi-label ---------------------------------------- #
    n_lab = [sum(1 for b in names if members[b][i]) for i in range(len(rows))]
    n_exp = [sum(1 for b in EXPLOIT_BUCKETS if members[b][i]) for i in range(len(rows))]
    coverage = {
        "n_positions": len(rows),
        "family_size": len(names),
        "labels_per_position": {"min": min(n_lab), "max": max(n_lab),
                                "mean": sum(n_lab) / len(n_lab),
                                "hist": dict(sorted(Counter(n_lab).items()))},
        "exploit_labels_per_position": {
            "n_with_zero": sum(1 for x in n_exp if x == 0),
            "n_with_at_least_one": sum(1 for x in n_exp if x >= 1),
            "hist": dict(sorted(Counter(n_exp).items()))},
        "n_multi_label_overall": sum(1 for x in n_lab if x > 1),
        "every_position_on_every_partition_axis": recon_axes_ok,
        "f7_median_cut": f7_median,
        "f7_unavailable": sum(1 for r in rows
                              if r["tax"].get("cross_world_spread_status")
                              != "ok_per_world_routeb"),
    }

    # ---- (E) multiplicity family + Holm ------------------------------------ #
    family = [b for b in names if table[b]["n"] > 0 and table[b]["n_games"] >= 2
              and table[b]["se"] is not None]
    excluded = [{"bucket": b, "n": table[b]["n"], "n_games": table[b]["n_games"],
                 "reason": "unestimable: n_games < 2 or zero-n"}
                for b in names if b not in family]
    pvals = {b: two_sided_p(table[b]["z_vs_bar"]) for b in family}
    holm_res = holm(pvals, alpha=0.05)
    for b in family:
        table[b]["p_vs_bar"] = holm_res[b]["p"]
        table[b]["p_holm_vs_bar"] = holm_res[b]["p_holm"]
        table[b]["holm_reject_vs_bar"] = holm_res[b]["reject"]
        table[b]["in_family"] = True
    for b in names:
        table[b].setdefault("in_family", False)

    # ---- (F) label-permutation null ---------------------------------------- #
    print(f"[perm] {args.perm_reps} reps x 2 modes over {len(family)} buckets …",
          flush=True)
    perm_primary = permutation_null(rows, members, family, reps=args.perm_reps,
                                    mode="game_block")
    perm_literal = permutation_null(rows, members, family, reps=args.perm_reps,
                                    mode="within_game")

    # ---- (G) the funnel gate ----------------------------------------------- #
    f3_pass = perm_primary["p_max_abs_z_contrast"] < 0.05
    gate_rows = []
    for b in family:
        t = table[b]
        weak = (b == "commit_direction=spend")
        f1 = bool(t["star_cell"])
        f2 = bool(t["holm_reject_vs_bar"] and (t["z_vs_bar"] or 0) > 0)
        gate_rows.append({
            "bucket": b, "n": t["n"], "n_games": t["n_games"],
            "R_champ": t["R_champ"], "se": t["se"],
            "z_vs_0": t["z_vs_0"], "z_vs_bar": t["z_vs_bar"],
            "G_search": t["G_search"], "G_z": t["G_z"],
            "F1_star_cell": f1, "F2_holm_2sigma_vs_bar": f2, "F3_permutation": f3_pass,
            "pre_declared_weak": weak,
            "passes_F1F2F3": bool(f1 and f2 and f3_pass and not weak),
        })
    winners = [r for r in gate_rows if r["passes_F1F2F3"]]
    winners.sort(key=lambda r: -(r["z_vs_bar"] or 0))

    if not f3_pass:
        verdict = "FUNNEL-BLOCKED"
        consequence = ("The family's max_b |z_b| does not beat the label-permutation "
                       "null at p<0.05: this taxonomy is indistinguishable from a random "
                       "taxonomy of the same shape. NO category may be read, whatever "
                       "its own z. Deliverable = the map of bounds.")
    elif winners:
        verdict = "FUNNEL-OPEN-PENDING-SIGN"
        consequence = (f"{len(winners)} pre-registered categor"
                       f"{'y' if len(winners) == 1 else 'ies'} satisfy F1 (star cell) & "
                       "F2 (Holm 2sigma vs the +0.5 bar) & F3 (permutation). F4's "
                       "out-of-family `tier1-greedy` SIGN CHECK is NOT computable from "
                       "the banked corpus (no such leg was run) and is OWED before any "
                       "term dollar: one python-only clair-marginalized tier1-greedy leg "
                       "over the same rids. This is the strongest verdict the banked "
                       "corpus can support.")
    else:
        verdict = "FUNNEL-CLOSED"
        consequence = ("No pre-registered category satisfies F1&F2&F3. Deliverable = the "
                       "map of bounds (per-category UB95 on R_champ, HT-reweighted to "
                       "the eligible-ply population), which sizes every future term "
                       "proposal.")

    # ---- (H) stage-1 screen feasibility + the pre-registered holdout ------- #
    game_ids = sorted({r["game_id"] for r in rows})
    rng = random.Random(HOLDOUT_SEED)
    shuffled = list(game_ids)
    rng.shuffle(shuffled)
    half = len(shuffled) // 2
    split = {str(gid): ("train" if i < half else "holdout")
             for i, gid in enumerate(shuffled)}
    split_doc = {
        "schema": "carcassonne-evloss-autopsy-r2-funnel-holdout/v1",
        "purpose": ("MANDATORY holdout for the leaf-reweight screening funnel stage 1 "
                    "(corpus-arithmetic screen). Pre-registered here so it predates any "
                    "weight grid. Function of game_id and HOLDOUT_SEED only — never of "
                    "any judged value."),
        "seed": HOLDOUT_SEED, "cluster": "game_id",
        "n_games": len(game_ids), "n_train_games": half,
        "n_holdout_games": len(shuffled) - half,
        "split": split,
    }
    split_path = out_dir / "funnel_holdout_split.json"
    split_path.write_text(json.dumps(split_doc, indent=2))
    split_sha = hashlib.sha256(split_path.read_bytes()).hexdigest()

    n_train_pos = sum(1 for r in rows if split[str(r["game_id"])] == "train")
    screen = {
        "n_positions_with_ge2_scored_arms": sum(1 for r in rows if r["n_arms_scored"] >= 2),
        "n_positions_with_ge3_scored_arms": sum(1 for r in rows if r["n_arms_scored"] >= 3),
        "n_arms_scored_hist": dict(sorted(Counter(r["n_arms_scored"] for r in rows).items())),
        "n_positions_per_world_values_complete": sum(1 for r in rows if r["per_world_ok"]),
        "n_train_positions": n_train_pos,
        "n_holdout_positions": len(rows) - n_train_pos,
        "holdout_split_file": str(split_path),
        "holdout_split_sha256": split_sha,
        "note": ("Every scored arm carries its 32 CRN-paired per-world oracle values, so a "
                 "leaf variant's move ordering over the stored arm set is pure arithmetic "
                 "— no engine, no judge. The arm set is 2-5 wide (played + up to 4), so "
                 "the screen prices RE-RANKING WITHIN the champion's own top arms, not "
                 "over all legal moves. State that limit whenever the screen is quoted."),
    }

    # ---- (I) emit ----------------------------------------------------------- #
    out = {
        "schema": SCHEMA,
        "blind_stamp_commit": args.blind_stamp,
        "prereg": "measurement/evloss_autopsy_r2/R2_PREREG.md",
        "deviations": "measurement/evloss_autopsy_r2/DEVIATIONS.md",
        "generated_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "corpus_provenance": {
            "share": str(share), "positions_dir": str(positions_dir),
            "judge_root": str(judge_root),
            "n_positions": len(rows), "n_games": pooled_G,
            "n_by_leg": n_by_leg,
            "record_filter": "ok is True and crn_verified is True (05_analyze_r1.load_leg)",
            "quarantine_excluded": ("laptop-side quarantine_D-L1_20260825_211224/ never "
                                    "enters this path; the banked corpus is the clean "
                                    "post-D-L1 rebuild R1 was read from, proven by the "
                                    "pooled reconciliation below"),
            "R0_readout": str(positions_dir / "R0_READOUT.json"),
            "R1_readout": str(share / "R1_READOUT.json"),
        },
        "estimator": {
            "source": "r2_estimator.py — verbatim copy of 05_analyze_r1.py",
            "weighting": "Hajek, w = ht_weight = 1/pi_s",
            "cluster": "game_id (= deck_seed)",
            "bar": BAR,
            "G_search_identity": "G_search = R_leaf - R_champ = -D_leaf (missing leg => 0, A6)",
        },
        "pooled": {
            "R_champ": pooled_mu, "se": pooled_se, "z_vs_0": pooled_mu / pooled_se,
            "z_vs_bar": (pooled_mu - BAR) / pooled_se,
            "design_effect": pooled_deff, "n": len(rows), "n_games": pooled_G,
            "G_search": hajek([r["G_search"] for r in rows], w),
            "sd_per_position": wsd(v, w),
        },
        "reconciliation": {
            "pooled_vs_R1": recon_pooled,
            "partition_axes": recon_axes,
            "all_axes_ok": recon_axes_ok,
        },
        "coverage": coverage,
        "categories": table,
        "multiplicity": {
            "family": family, "family_size": len(family),
            "excluded_from_family": excluded,
            "method": "Holm-Bonferroni, two-sided alpha=0.05, on z_vs_bar (+0.5 pt bar)",
            "n_holm_reject": sum(1 for b in family if table[b]["holm_reject_vs_bar"]),
        },
        "permutation_null": {"primary_game_block": perm_primary,
                             "prereg_literal_within_game": perm_literal},
        "funnel_gate": {
            "verdict": verdict,
            "consequence": consequence,
            "conditions": {
                "F1": "star cell: z(R_champ) >= 2 and z(G_search) < 2",
                "F2": "Holm-adjusted two-sided 2sigma on z_vs_bar (+0.5), cluster-robust",
                "F3": "family max_b |z_b| beats the label-permutation null at p<0.05",
                "F4": "tier1-greedy out-of-family SIGN CHECK — NOT COMPUTABLE from the "
                      "banked corpus (no such leg exists); leaf-computable-predicate half "
                      "is satisfied by every pre-registered bucket by construction",
            },
            "F3_pass": f3_pass,
            "rows": gate_rows,
            "winners": [r["bucket"] for r in winners],
        },
        "funnel_stage1_screen_feasibility": screen,
        "read_fence": ("0 evaluation games. No elo, no band-confirmatory use, no "
                       "results.csv row, no CL, PRODUCTION.yaml untouched. NO "
                       "bucket-gated deployment, ever (everyply DESIGN §4.5). A category "
                       "finding may license only a GLOBALLY-ACTIVE leaf-term hypothesis, "
                       "measured at an n=800 deck-paired deploy-budget cell. Reach "
                       "ceiling: a static leaf term addresses at most 62.2% of the "
                       "oracle spread (tiletie_mining_20260814)."),
    }
    dest = out_dir / "R2_READOUT.json"
    dest.write_text(json.dumps(out, indent=2))
    print(f"[write] {dest}")
    if args.copy_to:
        Path(args.copy_to).write_text(json.dumps(out, indent=2))
        print(f"[write] {args.copy_to}")

    # ---- console table ------------------------------------------------------ #
    print("\n=== R2 PER-CATEGORY TABLE (R_champ, pts/ply; bar = +0.50) ===")
    hdr = f"{'bucket':38s} {'n':>4s} {'ng':>4s} {'R_champ':>8s} {'se':>6s} " \
          f"{'z0':>6s} {'z.5':>6s} {'UB95':>7s} {'G_srch':>7s} {'zG':>6s} {'star':>5s}"
    print(hdr)
    print("-" * len(hdr))
    for b in names:
        t = table[b]
        if t["n"] == 0:
            print(f"{b:38s} {0:4d}    -        -      -      -      -       -       -      -     -")
            continue
        print(f"{b:38s} {t['n']:4d} {t['n_games']:4d} {t['R_champ']:8.4f} "
              f"{(t['se'] or float('nan')):6.4f} {(t['z_vs_0'] or float('nan')):6.2f} "
              f"{(t['z_vs_bar'] or float('nan')):6.2f} {(t['UB95'] or float('nan')):7.4f} "
              f"{t['G_search']:7.4f} {(t['G_z'] or float('nan')):6.2f} "
              f"{'YES' if t['star_cell'] else '.':>5s}")
    print(f"\nreconciliation: pooled delta {recon_pooled['delta_mean']:+.3e}  "
          f"axes_ok={recon_axes_ok}")
    print(f"permutation (game_block): observed max|z| "
          f"{perm_primary['observed_max_abs_z_contrast']:.3f}  "
          f"p={perm_primary['p_max_abs_z_contrast']:.4f}  "
          f"null p95={perm_primary['null_p95_max_abs_z_contrast']:.3f}")
    print(f"\nFUNNEL GATE: {verdict}")
    print(f"  {consequence}")
    if winners:
        print("  winners: " + ", ".join(r["bucket"] for r in winners))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
