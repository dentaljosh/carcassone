#!/usr/bin/env python3
"""E-1b — THE ADJUDICATOR (aggregate + gates + the READ_RULE executor).

Two jobs, in this order and never the other way round:

  1. **THE GATES.** Every gate below must PASS or the read is
     `E1B-VOID-INSTRUMENT`. `ABSENT` is `FAIL` at every one of them — never a
     skip, never a default — and each gate prints the ADDRESS that answered it.
     A void is not a null and may never be quoted as one.
  2. **THE READ RULE.** Holm step-down over the family of exactly two
     {PRIMARY, SECONDARY-A}, two-sided, family alpha = 0.05, then the frozen
     branch map. The bars are in `PREREG.md` §4 and are restated here as code
     constants; where this file and `PREREG.md` disagree, PREREG wins and this
     file is the defect.

THE ESTIMATOR is E-1a's, unchanged: a ply's price is the mean of its landed CRN
worlds' `delta_pts_mover`; a stratum's price is the unweighted mean over its
plies with a cluster-robust SE clustered on GAME; the PRIMARY is
`invasion - control`, whose SE is built from per-game influence contributions of
the DIFFERENCE so a shared game is a paired, not an independent, observation.

⭐ NEW IN E-1b: the FAMILY-PAIRED leg. Every E-1b world has an E-1a sibling on
the identical root and the identical world (proven by `G-ROOT`), so the price
difference between the two continuation families is itself a CRN-paired
statistic on the same 91 plies. SECONDARY-A is that difference applied to the
PRIMARY contrast — a difference-in-differences.

No judged quantity appears anywhere: every number here is a difference of
REALIZED final scores.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))

SCHEMA = "e1b-armed-continuation/v1"

# --- the frozen bars (PREREG.md §4) ---------------------------------------- #
BAR_REOPEN = 3.5            # pts/ply on invasion - control; see PREREG §4.1
HOLM_STEP1 = 2.2414         # alpha/2 = 0.025 two-sided
HOLM_STEP2 = 1.9600         # alpha   = 0.05  two-sided
CI_Z = 1.9600

# --- the frozen instrument identity ---------------------------------------- #
N_TARGET_PLIES = 91
M_WORLDS = 8
N_TARGET_UNITS = N_TARGET_PLIES * M_WORLDS          # 728
MIN_WORLD_LANDING_RATE = 0.95
ARM_DOSE, ARM_MASK, ARM_SCOPE = 0.25, 31, "opp"
PINNED_K_DETS, PINNED_SIMS_PER_DET, PINNED_EXACT_K = 8, 1376, 2
LEAF_HASH_OF_RECORD = "a36d2e15a3b3d71d"
STRATA = ("control", "defense", "farm_capture", "invasion")

# The E-1a verdict of record, quoted for the readout (already public: it is the
# adjudicated `CONTINUATION.json`, PRIMARY NULL -1.8655 +/- 1.8822, z -0.991).
E1A = {"primary_diff": -1.8654761904761905, "primary_se": 1.8821924940153008,
       "primary_z": -0.9911187067251293,
       "invasion": -1.3988095238095237, "control": 0.4666666666666667,
       "defense": 0.2857142857142857, "farm_capture": 2.53125}


# --------------------------------------------------------------------------- #
# the estimator (E-1a's, verbatim in shape)                                     #
# --------------------------------------------------------------------------- #
def collapse_worlds(rows):
    """(game, ply) -> one priced ply, the mean over its landed CRN worlds.

    ⭐ `price_e1a` is the E-1a price over the **same landed world set**, never
    over E-1a's full 8: a world E-1b voided must not enter one side of a paired
    difference and not the other."""
    by = collections.OrderedDict()
    for r in rows:
        by.setdefault((r["game"], r["ply"]), []).append(r)
    out = []
    for (game, ply), rs in by.items():
        ok = [x for x in rs if (x.get("pair") or {}).get("status") == "OK"]
        void = [x for x in rs if (x.get("pair") or {}).get("status") != "OK"]
        h = rs[0]
        base_ok = [x for x in ok if (x.get("baseline_e1a") or {}).get(
            "delta_pts_mover") is not None]
        rec = {"game": game, "ply": ply, "stratum": h["stratum"],
               "actor": int(h["actor"]), "k": h.get("k"),
               "ply_frac": h.get("ply_frac"),
               "m_worlds_ok": len(ok), "m_worlds_void": len(void),
               "void_reasons": sorted({(x.get("pair") or {}).get("reason")
                                       for x in void} - {None}),
               "price": (statistics.fmean(x["pair"]["delta_pts_mover"] for x in ok)
                         if ok else None),
               "world_deltas": [x["pair"]["delta_pts_mover"] for x in ok],
               "worlds_ok": sorted(x["world"] for x in ok),
               "price_e1a": (statistics.fmean(
                   x["baseline_e1a"]["delta_pts_mover"] for x in base_ok)
                   if base_ok and len(base_ok) == len(ok) else None)}
        rec["price_delta_family"] = (
            None if rec["price"] is None or rec["price_e1a"] is None
            else rec["price"] - rec["price_e1a"])
        out.append(rec)
    return out


def _influence(plies, sign=1.0, field="price"):
    n = len(plies)
    if n == 0:
        return {}, 0.0
    mu = statistics.fmean(p[field] for p in plies)
    contrib = collections.defaultdict(float)
    for p in plies:
        contrib[p["game"]] += sign * (p[field] - mu) / n
    return dict(contrib), mu


def cluster_stats(plies, field="price"):
    """Mean + SE clustered on GAME."""
    plies = [p for p in plies if p.get(field) is not None]
    n = len(plies)
    if n == 0:
        return {"n": 0, "n_clusters": 0, "mean": None, "se": None, "z": None}
    contrib, mu = _influence(plies, field=field)
    g = len(contrib)
    var = sum(v * v for v in contrib.values())
    if g > 1:
        var *= g / (g - 1.0)
    se = math.sqrt(var)
    return {"n": n, "n_clusters": g, "mean": mu, "se": se,
            "z": (mu / se if se > 0 else None), "total": mu * n,
            "sd_plies": (statistics.stdev([p[field] for p in plies])
                         if n > 1 else None)}


def contrast(a, b, field="price"):
    """`mean(a) - mean(b)` with a cluster-robust SE that shares game clusters."""
    a = [p for p in a if p.get(field) is not None]
    b = [p for p in b if p.get(field) is not None]
    if not a or not b:
        return {"n_a": len(a), "n_b": len(b), "diff": None, "se": None, "z": None}
    ca, ma = _influence(a, 1.0, field)
    cb, mb = _influence(b, -1.0, field)
    keys = set(ca) | set(cb)
    var = sum((ca.get(k, 0.0) + cb.get(k, 0.0)) ** 2 for k in keys)
    g = len(keys)
    if g > 1:
        var *= g / (g - 1.0)
    se = math.sqrt(var)
    return {"n_a": len(a), "n_b": len(b), "mean_a": ma, "mean_b": mb,
            "diff": ma - mb, "se": se, "z": (ma - mb) / se if se > 0 else None,
            "n_clusters": g, "n_shared_clusters": len(set(ca) & set(cb))}


def recon_primary(rows):
    """`RECON` — the primary recomputed by a DELIBERATELY DIFFERENT path.

    Flat, sorted, `math.fsum`, no shared helper. A witness that shares the
    estimator's code path agrees by construction and witnesses nothing. RECON
    can only VOID a number, never move it."""
    per = {}
    for r in sorted(rows, key=lambda r: (r["game"], r["ply"], r["world"])):
        p = r.get("pair") or {}
        if p.get("status") != "OK":
            continue
        per.setdefault((r["stratum"], r["game"], r["ply"]), []).append(
            float(p["delta_pts_mover"]))
    prices = {k: math.fsum(v) / len(v) for k, v in sorted(per.items())}
    inv = [v for k, v in sorted(prices.items()) if k[0] == "invasion"]
    ctl = [v for k, v in sorted(prices.items()) if k[0] == "control"]
    if not inv or not ctl:
        return None
    return math.fsum(inv) / len(inv) - math.fsum(ctl) / len(ctl)


# --------------------------------------------------------------------------- #
# THE GATES — ABSENT is FAIL; each prints the address that answered it          #
# --------------------------------------------------------------------------- #
def _g(name, ok, addr, says, note=""):
    return {"gate": name, "status": "PASS" if ok else "FAIL",
            "address": addr, "says": says, "note": note}


def gate_manifest(man, man_path):
    """`G-MANIFEST` — the manifest exists, is this schema, and its FROZEN
    fields are the ones this adjudicator was written against."""
    if not man:
        return _g("G-MANIFEST", False, str(man_path), "ABSENT",
                  "no manifest.json — config may not be quoted from a dirname")
    bad = []
    if man.get("schema") != SCHEMA:
        bad.append(f"schema={man.get('schema')!r}")
    if int(man.get("m_worlds", -1)) != M_WORLDS:
        bad.append(f"m_worlds={man.get('m_worlds')!r}")
    a = man.get("arming") or {}
    if (float(a.get("dose", -1)) != ARM_DOSE or int(a.get("mask", -1)) != ARM_MASK
            or str(a.get("scope")) != ARM_SCOPE):
        bad.append(f"arming={a}")
    b = man.get("budget_pin") or {}
    if (int(b.get("k_dets", -1)) != PINNED_K_DETS
            or int(b.get("sims_per_det", -1)) != PINNED_SIMS_PER_DET
            or int(b.get("exact_max_k", -1)) != PINNED_EXACT_K):
        bad.append(f"budget_pin={b}")
    if not man.get("targets_sha256") or not man.get("crn_baseline_sha256"):
        bad.append("targets/baseline sha absent")
    return _g("G-MANIFEST", not bad, f"{man_path}::schema,arming,budget_pin",
              "frozen config matches the adjudicator" if not bad
              else f"MISMATCH {bad}")


def gate_leaf(man, man_path):
    """`G-LEAF` — ⭐ INVERTED: the verified leaf hash EQUALS the leaf of record
    and the resolved leaf is the curve125 / cap-8 champion leaf. A MOVED hash
    means a leaf change was smuggled in; surface B moves no leaf hash, so a
    moved one here is never this round's doing."""
    lm = (man or {}).get("leaf_manifest") or {}
    hashes = {str(v) for v in (lm.get("leaf_hashes") or {}).values()}
    leaf = lm.get("leaf") or {}
    ok = (LEAF_HASH_OF_RECORD in hashes
          and float(leaf.get("bonus_cap", -1)) == 8.0
          and float(leaf.get("opp_bonus_cap", -1)) == 8.0
          and float(leaf.get("value_blend", -1)) == 0.0)
    return _g("G-LEAF", ok, f"{man_path}::leaf_manifest",
              f"hashes={sorted(hashes)} leaf={leaf}")


def gate_negctrl(man, man_path):
    """`G-NEGCTRL` — the play-derived census is DOSE-GATED.

    Without this, a nonzero `boosted` in the armed cells could in principle be
    champion traffic the wheel counts unconditionally, and `G-WITNESS` would
    prove nothing. The control asserts BOTH directions on the same opening:
    dose 0 -> all-zero census, dose d* -> boosted > 0."""
    nc = (man or {}).get("negative_control") or {}
    z = (nc.get("unarmed_dose0") or {}).get("census") or {}
    p = (nc.get("armed_dose_dstar") or {}).get("census") or {}
    ok = bool(nc.get("ok")) and all(int(z.get(k, -1)) == 0
                                    for k in ("total", "own_mover", "boosted")) \
        and int(p.get("boosted", 0)) > 0
    return _g("G-NEGCTRL", ok, f"{man_path}::negative_control",
              f"dose0={z} dose_dstar={p}")


def gate_witness(rows):
    """⭐⭐ `G-WITNESS` — the PLAY-DERIVED proof that the scope knob BOUND, on
    EVERY landed arm. A resolved `scope` in a manifest is a CONFIG ECHO; an arm
    whose knob never bound is champion-vs-champion wearing this round's name and
    reads as a clean, credible null.

    HARD: every OK arm carries an integer `jr_expansions` census with
    `total > 0`, `0 <= own_mover <= total`, `boosted > 0`, and
    `boosted <= denominator(scope)`.
    ADVISORY (flags, never voids): mean coverage below 0.5."""
    arms = [a for r in rows for a in (r.get("arms") or {}).values()
            if a.get("status") == "OK"]
    bad, cov, exact = [], [], 0
    for a in arms:
        sw = a.get("scope_witness") or {}
        if not sw or not sw.get("ok"):
            bad.append({"arm": a.get("arm"),
                        "failures": sw.get("failures", ["scope_witness_absent"]),
                        "census": a.get("jr_expansions")})
        if sw.get("coverage") is not None:
            cov.append(float(sw["coverage"]))
        if sw.get("exact_partition"):
            exact += 1
    mean_cov = statistics.fmean(cov) if cov else None
    g = _g("G-WITNESS", (not bad) and bool(arms),
           "unit_*.json::arms[*].scope_witness",
           f"{len(arms) - len(bad)}/{len(arms)} armed arms expressed in play; "
           f"mean coverage {None if mean_cov is None else round(mean_cov, 4)}; "
           f"exact partition on {exact}/{len(arms)}",
           "" if not bad else f"FAILURES {bad[:3]}")
    g["advisory_low_coverage"] = bool(mean_cov is not None and mean_cov < 0.5)
    g["mean_coverage"] = mean_cov
    g["n_arms"] = len(arms)
    return g


def gate_arming(rows):
    """`G-ARMING` — the RESOLVED knobs on every landed arm are exactly
    (dose 0.25, mask 31, scope 'opp'), read off the RUST side's own stats, never
    off what the launcher asked for."""
    bad = []
    for r in rows:
        for a in (r.get("arms") or {}).values():
            if a.get("status") != "OK":
                continue
            g = a.get("arming_resolved") or {}
            if (abs(float(g.get("dose", -1)) - ARM_DOSE) > 1e-12
                    or int(g.get("mask", -1)) != ARM_MASK
                    or str(g.get("scope")) != ARM_SCOPE):
                bad.append({"game": r["game"], "ply": r["ply"], "resolved": g})
    return _g("G-ARMING", not bad, "unit_*.json::arms[*].arming_resolved",
              f"dose {ARM_DOSE} / mask {ARM_MASK} / scope {ARM_SCOPE} on every arm"
              if not bad else f"DRIFT {bad[:3]}")


def gate_budget(rows):
    """`G-BUDGET` — every arm resolved k8 x 1376 = 11008 and exact-K 2, i.e.
    E-1a's budget. An arm at today's YAML k16 would change the continuation
    family AND the budget at once and could not be contrasted with -1.87."""
    bad = []
    for r in rows:
        for a in (r.get("arms") or {}).values():
            if a.get("status") != "OK":
                continue
            g = a.get("arming_resolved") or {}
            if (int(g.get("k_dets", -1)) != PINNED_K_DETS
                    or int(g.get("sims_per_det", -1)) != PINNED_SIMS_PER_DET
                    or int(g.get("exact_max_k", -1)) != PINNED_EXACT_K):
                bad.append({"game": r["game"], "ply": r["ply"], "resolved": g})
    return _g("G-BUDGET", not bad, "unit_*.json::arms[*].arming_resolved",
              f"k{PINNED_K_DETS}x{PINNED_SIMS_PER_DET} exact-K{PINNED_EXACT_K} "
              f"on every arm" if not bad else f"DRIFT {bad[:3]}")


def gate_root(rows):
    """`G-ROOT` — ⭐ THE SINGLE-VARIABLE PROOF. Every unit's CRN witness equals
    its E-1a sibling's, on all seven fields. Those fields describe the ROOT and
    the WORLD and carry no continuation-policy term, so a mismatch means E-1b is
    not pricing what E-1a priced. A BUG SIGNAL, never attrition."""
    bad, seen = [], 0
    for r in rows:
        if r.get("baseline_e1a") is None:
            bad.append({"game": r["game"], "ply": r["ply"], "world": r["world"],
                        "why": "no E-1a sibling carried on the row"})
            continue
        p = r.get("pair") or {}
        if p.get("status") == "VOID" and p.get("reason") == "root_identity_mismatch":
            bad.append({"game": r["game"], "ply": r["ply"], "world": r["world"],
                        "fields": p.get("fields")})
        elif p.get("status") == "OK":
            if not p.get("root_identity_ok"):
                bad.append({"game": r["game"], "ply": r["ply"],
                            "world": r["world"], "why": "not asserted"})
            seen += 1
    return _g("G-ROOT", not bad, "unit_*.json::pair.root_identity_ok",
              f"{seen} priced worlds sit on E-1a's exact roots and worlds"
              if not bad else f"MISMATCH {bad[:3]}")


def gate_n(plies, rows):
    """`G-N` — every one of the 91 frozen target plies is PRICED (>= 1 landed
    CRN world) AND at least 95% of the 728 requested worlds landed."""
    priced = [p for p in plies if p["price"] is not None]
    ok_worlds = sum(p["m_worlds_ok"] for p in plies)
    rate = ok_worlds / N_TARGET_UNITS
    ok = len(priced) == N_TARGET_PLIES and rate >= MIN_WORLD_LANDING_RATE
    return _g("G-N", ok, "unit_*.json (collapsed)",
              f"{len(priced)}/{N_TARGET_PLIES} plies priced; "
              f"{ok_worlds}/{N_TARGET_UNITS} worlds landed "
              f"({rate:.4f} vs floor {MIN_WORLD_LANDING_RATE})")


def gate_decks(plies, targets):
    """`G-DECKS` — the priced (game, ply) set is EXACTLY the frozen 91 targets
    (no strays, none missing) and every world index lies in [0, 8)."""
    want = {(t["game"], int(t["ply"])) for t in targets}
    have = {(p["game"], p["ply"]) for p in plies}
    badw = [(p["game"], p["ply"], w) for p in plies for w in p["worlds_ok"]
            if not (0 <= int(w) < M_WORLDS)]
    ok = (want == have) and not badw
    return _g("G-DECKS", ok, "targets_continuation.jsonl vs unit_*.json",
              f"priced set == frozen target set ({len(have)}); world indices in "
              f"[0,{M_WORLDS})" if ok else
              f"missing {sorted(want - have)[:3]} stray {sorted(have - want)[:3]} "
              f"bad_world {badw[:3]}")


def gate_rules(rows, targets):
    """`G-RULES` — every row's rules profile was RESOLVED FROM THE ARCHIVE and
    agrees with the frozen target's stamp, and the R9 import latch was observed
    equal to expected. argparse defaults and dirnames answer nothing here."""
    tp = {(t["game"], int(t["ply"])): t["profile"] for t in targets}
    bad = []
    for r in rows:
        e = r.get("r9_env") or {}
        if r.get("profile") != tp.get((r["game"], r["ply"])):
            bad.append({"game": r["game"], "ply": r["ply"],
                        "profile": r.get("profile")})
        elif e.get("r9_env_expected") is None or \
                e.get("r9_env_expected") != e.get("r9_env_observed"):
            bad.append({"game": r["game"], "ply": r["ply"], "r9": e})
    return _g("G-RULES", not bad, "unit_*.json::profile,r9_env",
              "profile resolved from the archive == the frozen stamp; R9 latch "
              "observed == expected" if not bad else f"DRIFT {bad[:3]}")


def gate_void(plies, rows):
    """`G-VOID` — void worlds at or below 10% overall, and NO void carries a
    correctness reason (`crn_witness_mismatch`, `root_identity_mismatch`,
    `arm_witness_failed`). Those are guards, not attrition: one is enough."""
    reasons = collections.Counter(
        (r.get("pair") or {}).get("reason") for r in rows
        if (r.get("pair") or {}).get("status") != "OK")
    reasons.pop(None, None)
    fatal = {k: v for k, v in reasons.items()
             if k in ("crn_witness_mismatch", "root_identity_mismatch",
                      "arm_witness_failed")}
    n_void = sum(p["m_worlds_void"] for p in plies)
    rate = n_void / max(1, n_void + sum(p["m_worlds_ok"] for p in plies))
    ok = (not fatal) and rate <= 0.10
    return _g("G-VOID", ok, "unit_*.json::pair.status/reason",
              f"void {n_void} ({rate:.4f}) reasons {dict(reasons)}"
              + (f" ⛔ CORRECTNESS VOIDS {fatal}" if fatal else ""))


def gate_recon(rows, primary):
    """`RECON` — the primary reproduces from the raw rows by a different code
    path. It can only VOID, never move, a number."""
    r = recon_primary(rows)
    ok = (r is not None and primary.get("diff") is not None
          and abs(r - primary["diff"]) < 1e-9)
    return _g("RECON", ok, "unit_*.json (independent fsum path)",
              f"recon {r!r} vs estimator {primary.get('diff')!r}")


GATES_ORDER = ("G-MANIFEST", "G-LEAF", "G-NEGCTRL", "G-WITNESS", "G-ARMING",
               "G-BUDGET", "G-ROOT", "G-N", "G-DECKS", "G-RULES", "G-VOID",
               "RECON")


def run_gates(rows, plies, targets, man, man_path, primary):
    return [gate_manifest(man, man_path), gate_leaf(man, man_path),
            gate_negctrl(man, man_path), gate_witness(rows), gate_arming(rows),
            gate_budget(rows), gate_root(rows), gate_n(plies, rows),
            gate_decks(plies, targets), gate_rules(rows, targets),
            gate_void(plies, rows), gate_recon(rows, primary)]


# --------------------------------------------------------------------------- #
# THE READ RULE                                                                 #
# --------------------------------------------------------------------------- #
def holm(legs):
    """Two-sided Holm step-down over a family of exactly two.

    The LARGER |z| is tested at 2.2414 (alpha/2); only if it clears is the
    smaller tested at 1.9600 (alpha). A leg that does not clear fires nothing."""
    order = sorted(legs, key=lambda kv: -abs(kv[1].get("z") or 0.0))
    out, prev_cleared = {}, True
    for i, (name, leg) in enumerate(order):
        thr = HOLM_STEP1 if i == 0 else HOLM_STEP2
        z = leg.get("z")
        cleared = bool(prev_cleared and z is not None and abs(z) >= thr)
        out[name] = {"threshold": thr, "z": z, "clears": cleared,
                     "rank": i + 1}
        prev_cleared = cleared
    return out


def read_rule(gates, primary, secondary_a):
    fails = [g["gate"] for g in gates if g["status"] != "PASS"]
    if fails:
        return {"branch": "E1B-VOID-INSTRUMENT", "failed_gates": fails,
                "licenses": "NOTHING. A void is not a null and may never be "
                            "quoted as one. Fix, re-run, read again; the voided "
                            "artefacts stay on disk unmodified."}
    h = holm([("PRIMARY", primary), ("SECONDARY_A", secondary_a)])
    d, se = primary.get("diff"), primary.get("se")
    ub = None if d is None or se is None else d + CI_Z * se
    res = {"holm": h, "primary_ci95_upper": ub, "bar_reopen": BAR_REOPEN}
    if h["PRIMARY"]["clears"] and d is not None and d > 0:
        if d >= BAR_REOPEN:
            res.update(branch="E1B-POSITIVE", licenses=(
                "The per-ply route REOPENS under an exploit-aware continuation. "
                "CL-083's headline clause must carry the policy-conditional "
                "qualifier as a LIVE limitation, not a conceded one. Licenses a "
                "CONFIRM on FRESH plies (never a re-read of these 91) — the "
                "selecting observation is never pooled with the confirming one."))
        else:
            res.update(branch="E1B-POSITIVE-SUBTHRESHOLD", licenses=(
                "The armed price is statistically nonzero but BELOW the effect "
                "size the decision cares about. Licenses the policy-conditional "
                "clause; does NOT reopen the per-ply route."))
    elif h["PRIMARY"]["clears"] and d is not None and d < 0:
        res.update(branch="E1B-NEGATIVE", licenses=(
            "Under an exploit-aware continuation the divergent invasion plies "
            "are worth LESS than ordinary champion-divergences. Strengthens the "
            "per-ply null; report the magnitude, do not narrate a mechanism."))
    elif h["SECONDARY_A"]["clears"]:
        res.update(branch="E1B-FAMILY-SENSITIVE", licenses=(
            "The divergence price IS policy-conditional: swapping the "
            "continuation family MOVES it. CL-083 amendment clause 1 becomes "
            "MANDATORY rather than prudent. No per-ply route reopens."))
    elif ub is not None and ub < BAR_REOPEN:
        res.update(branch="E1B-NULL-BOUNDED", licenses=(
            "The per-ply null SURVIVES an exploit-aware continuation, bounded "
            f"above at {ub:.2f} < {BAR_REOPEN} pts/ply. CL-083 gains one "
            "genuinely new evidence axis and its clause-1 concession may be "
            "stated as MEASURED AND BOUNDED rather than UNPRICED. ⛔ Quote the "
            "bound; 'killed/dead/does nothing' remain forbidden readings."))
    else:
        res.update(branch="E1B-UNRESOLVED", licenses=(
            "NOTHING beyond the achieved bound. Pre-registered as the modal "
            "outcome under a true null (~50%, PREREG §4.3) — the instrument "
            "cannot exclude the reopen bar from a centred null at n=91. More "
            "WORLDS cannot help (SYNTHESIS §2.2); only more PLIES can."))
    return res


# --------------------------------------------------------------------------- #
# main                                                                          #
# --------------------------------------------------------------------------- #
def analyse(rows, targets, man, man_path):
    plies = collapse_worlds(rows)
    priced = [p for p in plies if p["price"] is not None]
    by_s = collections.defaultdict(list)
    for p in priced:
        by_s[p["stratum"]].append(p)

    primary = contrast(by_s.get("invasion", []), by_s.get("control", []))
    secondary_a = contrast(by_s.get("invasion", []), by_s.get("control", []),
                           field="price_delta_family")
    gates = run_gates(rows, plies, targets, man, man_path, primary)
    verdict = read_rule(gates, primary, secondary_a)

    out = {
        "schema": SCHEMA,
        "n_unit_files": len(rows), "n_units": len(rows),
        "n_target_plies": N_TARGET_PLIES,
        "n_plies_with_units": len(plies), "n_plies_priced": len(priced),
        "n_plies_missing": sorted(
            {(t["game"], int(t["ply"])) for t in targets}
            - {(p["game"], p["ply"]) for p in plies}),
        "worlds": {
            "requested_per_ply": max((p["m_worlds_ok"] + p["m_worlds_void"]
                                      for p in plies), default=0),
            "ok": sum(p["m_worlds_ok"] for p in plies),
            "void": sum(p["m_worlds_void"] for p in plies),
            "void_reasons": dict(collections.Counter(
                r for p in plies for r in p["void_reasons"])),
        },
        "arm_status": dict(collections.Counter(
            a.get("status") for r in rows for a in (r.get("arms") or {}).values())),
        "GATES": gates,
        "gates_all_pass": all(g["status"] == "PASS" for g in gates),
        "by_stratum": {s: {**cluster_stats(v),
                           "family_delta": cluster_stats(
                               v, field="price_delta_family"),
                           "e1a_mean": E1A.get(s),
                           "mean_m_worlds_ok": round(
                               statistics.fmean(p["m_worlds_ok"] for p in v), 2)}
                       for s, v in sorted(by_s.items())},
        "PRIMARY_invasion_minus_control": primary,
        "SECONDARY_A_family_delta_of_primary": secondary_a,
        "secondary": {
            "farm_capture_minus_control": contrast(by_s.get("farm_capture", []),
                                                   by_s.get("control", [])),
            "defense_read_separately": cluster_stats(by_s.get("defense", [])),
            "defense_family_delta": cluster_stats(by_s.get("defense", []),
                                                  field="price_delta_family"),
        },
        "E1A_banked_for_reference": E1A,
        "VERDICT": verdict,
        "descriptive": {
            "followup_agrees_with_archive_rate": (
                round(statistics.fmean(
                    [1.0 if r.get("followup_agrees_with_archive") else 0.0
                     for r in rows
                     if r.get("followup_agrees_with_archive") is not None]), 4)
                if any(r.get("followup_agrees_with_archive") is not None
                       for r in rows) else None),
            "mean_s_per_decision": round(statistics.fmean(
                [a["s_per_decision"] for r in rows
                 for a in (r.get("arms") or {}).values()
                 if a.get("s_per_decision")]), 4) if rows else None,
            "mean_arm_s": round(statistics.fmean(
                [a["arm_s"] for r in rows for a in (r.get("arms") or {}).values()
                 if a.get("arm_s")]), 2) if rows else None,
            "jr_expansions_totals": {
                k: sum(int(((a.get("jr_expansions") or {}).get(k)) or 0)
                       for r in rows for a in (r.get("arms") or {}).values()
                       if a.get("status") == "OK")
                for k in ("total", "own_mover", "boosted")},
            "budget_notes": dict(collections.Counter(
                str(r.get("budget_note")) for r in rows)),
            "profiles": dict(collections.Counter(r["profile"] for r in rows)),
        },
        "plies": sorted(priced, key=lambda p: (p["stratum"], p["game"], p["ply"])),
        "caveat": "Every price is a difference of REALIZED final scores over "
                  "CRN-paired continuations under S1-ARMED (dose 0.25, mask 31, "
                  "scope=opp) play by BOTH seats, at E-1a's pinned k8x1376 "
                  "budget. No judge, no evaluation function, no search score. "
                  "It prices the TARGET PLY ONLY: every later move, including "
                  "the meeple follow-up, is the continuation policy's.",
    }
    return out


def load_rows(dirs):
    rows = []
    for d in dirs:
        for f in sorted(Path(d).glob("unit_*.json")):
            rows.append(json.loads(f.read_text()))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--units", nargs="*", default=[],
                    help="directories of unit_*.json")
    ap.add_argument("--targets", default=str(DIR / "targets_continuation.jsonl"))
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--smoke", action="store_true",
                    help="adjudicate a SMOKE_ cell from its OWN emitted manifest; "
                         "exits NONZERO on an empty cell or a failed witness")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if not args.units:
        raise SystemExit("--units is required")
    rows = load_rows(args.units)
    targets = [json.loads(l) for l in Path(args.targets).open()]
    # the manifest lives INSIDE the out-dir the units came from, beside them
    man_path = args.manifest or str(Path(args.units[0]) / "manifest.json")
    man = (json.loads(Path(man_path).read_text())
           if Path(man_path).exists() else None)

    if args.smoke:
        return smoke_adjudicate(rows, man, man_path, out=args.out)

    out = analyse(rows, targets, man, man_path)
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "plies"}, indent=1))
    if not out["gates_all_pass"]:
        raise SystemExit(2)


def smoke_adjudicate(rows, man, man_path, out=None):
    """⛔ THE SMOKE IS ADJUDICATED FROM ITS OWN EMITTED DOCUMENTS, and it EXITS
    NONZERO on an EMPTY CELL — the launch-blocking defect class (a smoke that
    "passes" because it measured nothing).

    It asserts, on the cell it actually played:
      * at least one unit exists and at least one PRICED pair landed;
      * `G-MANIFEST` / `G-LEAF` / `G-NEGCTRL` on the emitted manifest;
      * `G-WITNESS` / `G-ARMING` / `G-BUDGET` / `G-ROOT` on the emitted units;
      * `G-VOID` (no correctness voids).
    `G-N` / `G-DECKS` are DELIBERATELY not run: a smoke is a subset by design,
    and a gate written to the wrong scope is the PG-A1 defect."""
    fails = []
    if not rows:
        fails.append("EMPTY CELL: no unit_*.json was produced")
    priced = [r for r in rows if (r.get("pair") or {}).get("status") == "OK"]
    if not priced:
        fails.append(f"NO PRICED PAIR landed ({len(rows)} units on disk)")
    plies = collapse_worlds(rows)
    gates = [gate_manifest(man, man_path), gate_leaf(man, man_path),
             gate_negctrl(man, man_path), gate_witness(rows), gate_arming(rows),
             gate_budget(rows), gate_root(rows), gate_void(plies, rows)]
    fails += [g["gate"] for g in gates if g["status"] != "PASS"]
    rep = {"schema": SCHEMA, "smoke": True, "n_units": len(rows),
           "n_priced": len(priced),
           "n_plies": len({(r["game"], r["ply"]) for r in rows}),
           "strata": dict(collections.Counter(r["stratum"] for r in rows)),
           "manifest": man_path,
           "GATES": gates, "failures": fails, "PASS": not fails,
           "prices": [{"game": r["game"], "ply": r["ply"], "world": r["world"],
                       "stratum": r["stratum"],
                       "delta_pts_mover": r["pair"]["delta_pts_mover"],
                       "e1a_delta": (r.get("baseline_e1a") or {}).get(
                           "delta_pts_mover"),
                       "coverage": (r["arms"]["arm_owner"].get("scope_witness")
                                    or {}).get("coverage")}
                      for r in priced],
           "jr_expansions_totals": {
               k: sum(int(((a.get("jr_expansions") or {}).get(k)) or 0)
                      for r in rows for a in (r.get("arms") or {}).values()
                      if a.get("status") == "OK")
               for k in ("total", "own_mover", "boosted")}}
    # ⛔ The artifact is written HERE, never by a shell `| tee`: a pipeline's
    # exit status is tee's, so `--smoke | tee f || DIE` would swallow the
    # nonzero exit this whole function exists to produce — and the human-readable
    # trailer would corrupt the JSON. The banner therefore goes to STDERR.
    if out:
        Path(out).write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))
    if fails:
        print(f"⛔ SMOKE FAILED: {fails}", file=sys.stderr)
        raise SystemExit(3)
    print("✅ SMOKE PASS", file=sys.stderr)
    return 0


# --------------------------------------------------------------------------- #
# --selftest — every branch reachable, every named defect fires its own gate    #
# --------------------------------------------------------------------------- #
def _jitter(i, k):
    """Deterministic, small, ZERO-MEAN spread. Without it every ply in a stratum
    carries the identical price, the cluster SE is exactly 0, and the branch
    grid could not distinguish "clears" from "degenerate"."""
    return ((i * 7 + k * 3) % 5 - 2) * 0.4


def _shaped(diff_inv, diff_ctl, e1a_inv=0.0, e1a_ctl=0.0, n_games=20):
    """A synthetic but SHAPE-FAITHFUL cell: the real emitter's nesting, the
    real key names, the real witness blocks."""
    rows, targets = [], []
    census = {"total": 1000, "own_mover": 600, "boosted": 400}
    for i in range(n_games):
        for si, (stratum, val, e1a) in enumerate(
                (("invasion", diff_inv, e1a_inv), ("control", diff_ctl, e1a_ctl))):
            val = val + _jitter(i, si)
            e1a = e1a + _jitter(i, si + 2)
            game, ply = f"g{i}.json", 10 if stratum == "invasion" else 20
            targets.append({"game": game, "ply": ply, "stratum": stratum,
                            "profile": "fixed_v1", "actor": 0})
            for w in range(M_WORLDS):
                wit = {"root_repr_sha": f"R{i}{stratum}{w}",
                       "world_deck_sha": f"W{i}{stratum}{w}",
                       "world_deck_len": 30, "n_drawn_prefix": 40,
                       "n_legal_root": 12, "det_seed_base_at_root": 999,
                       "move_idx_at_root": ply}
                arm = {"status": "OK", "arm": "arm_owner",
                       "margin_p0_minus_p1": 0, "witness": wit,
                       "jr_expansions": dict(census),
                       "arming_resolved": {"dose": ARM_DOSE, "mask": ARM_MASK,
                                           "scope": ARM_SCOPE,
                                           "k_dets": PINNED_K_DETS,
                                           "sims_per_det": PINNED_SIMS_PER_DET,
                                           "exact_max_k": PINNED_EXACT_K,
                                           "threads": 1, "seed": 0},
                       "scope_witness": scope_witness_local(census, ARM_SCOPE),
                       "s_per_decision": 1.2, "arm_s": 100.0}
                rows.append({
                    "game": game, "ply": ply, "world": w, "stratum": stratum,
                    "profile": "fixed_v1", "actor": 0, "phase": "tiles", "k": 30,
                    "r9_env": {"CARCASSONNE_FIX_R9": "1",
                               "r9_env_expected": True, "r9_env_observed": True},
                    "arms": {"arm_owner": arm, "arm_cf": dict(arm, arm="arm_cf")},
                    "pair": {"status": "OK", "margin_owner": 0, "margin_cf": 0,
                             "delta_pts_mover": val, "crn_witness": wit,
                             "root_identity_ok": True},
                    "baseline_e1a": {"delta_pts_mover": e1a, "margin_owner": 0,
                                     "margin_cf": 0},
                    "followup_agrees_with_archive": True})
    seen, tt = set(), []
    for t in targets:
        if (t["game"], t["ply"]) in seen:
            continue
        seen.add((t["game"], t["ply"]))
        tt.append(t)
    return rows, tt


_CA = None


def _continue_armed():
    """The runner module, loaded by PATH so the adjudicator and the emitter can
    never drift on the witness definition (S1's `screen_lib_g3` discipline)."""
    global _CA
    if _CA is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "continue_armed", DIR / "continue_armed.py")
        _CA = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_CA)
    return _CA


def scope_witness_local(census, scope):
    return _continue_armed().scope_witness(census, scope)


def _man(**over):
    m = {"schema": SCHEMA, "m_worlds": M_WORLDS,
         "arming": {"dose": ARM_DOSE, "mask": ARM_MASK, "scope": ARM_SCOPE},
         "budget_pin": {"k_dets": PINNED_K_DETS,
                        "sims_per_det": PINNED_SIMS_PER_DET,
                        "exact_max_k": PINNED_EXACT_K},
         "targets_sha256": "x" * 64, "crn_baseline_sha256": "y" * 64,
         "leaf_manifest": {"leaf_hashes": {"harness": LEAF_HASH_OF_RECORD},
                           "leaf": {"bonus_cap": 8.0, "opp_bonus_cap": 8.0,
                                    "value_blend": 0.0}},
         "negative_control": {"ok": True,
                              "unarmed_dose0": {"census": {"total": 0,
                                                           "own_mover": 0,
                                                           "boosted": 0}},
                              "armed_dose_dstar": {"census": {"total": 10,
                                                              "own_mover": 6,
                                                              "boosted": 4}}}}
    m.update(over)
    return m


def selftest():
    """Every branch reachable; every named defect fires its OWN gate."""
    fails = []

    def branch_of(rows, targets, man=None):
        return analyse(rows, targets, man or _man(), "MEM")["VERDICT"]["branch"]

    # ⚠️ the shaped cells use n=20 games/stratum, so G-N and G-DECKS (which are
    # written to the REAL 91/728 cell) are expected to fail; the branch grid is
    # exercised through read_rule directly so a shape gate cannot mask it.
    def branch_direct(inv, ctl, e1a_inv=0.0, e1a_ctl=0.0):
        rows, targets = _shaped(inv, ctl, e1a_inv, e1a_ctl)
        out = analyse(rows, targets, _man(), "MEM")
        return read_rule([g for g in out["GATES"]
                          if g["gate"] not in ("G-N", "G-DECKS")],
                         out["PRIMARY_invasion_minus_control"],
                         out["SECONDARY_A_family_delta_of_primary"])["branch"]

    cases = [
        ("E1B-POSITIVE", branch_direct(8.0, 0.0)),
        ("E1B-POSITIVE-SUBTHRESHOLD", branch_direct(2.0, 0.0)),
        ("E1B-NEGATIVE", branch_direct(-8.0, 0.0)),
        ("E1B-FAMILY-SENSITIVE", branch_direct(0.0, 0.0, -8.0, 0.0)),
        ("E1B-NULL-BOUNDED", branch_direct(0.0, 0.0)),
    ]
    for want, got in cases:
        if got != want:
            fails.append(f"branch grid: expected {want}, got {got}")

    # every named defect fires its OWN gate and voids the round
    rows, targets = _shaped(0.0, 0.0)
    defects = {
        "G-WITNESS": lambda rs: [rs[0]["arms"]["arm_owner"].update(
            jr_expansions={"total": 10, "own_mover": 6, "boosted": 0},
            scope_witness={"ok": False, "failures": ["boosted_not_positive"]})],
        "G-ARMING": lambda rs: [rs[0]["arms"]["arm_owner"]["arming_resolved"]
                                .update(scope="all")],
        "G-BUDGET": lambda rs: [rs[0]["arms"]["arm_owner"]["arming_resolved"]
                                .update(k_dets=16)],
        "G-ROOT": lambda rs: [rs[0]["pair"].update(root_identity_ok=False)],
        "G-RULES": lambda rs: [rs[0]["r9_env"].update(r9_env_observed=False)],
        "G-VOID": lambda rs: [rs[0]["pair"].update(
            status="VOID", reason="root_identity_mismatch")],
    }
    for gate, mutate in defects.items():
        import copy
        rs = copy.deepcopy(rows)
        mutate(rs)
        out = analyse(rs, targets, _man(), "MEM")
        got = {g["gate"] for g in out["GATES"] if g["status"] != "PASS"}
        if gate not in got:
            fails.append(f"defect for {gate} did not fire it (fired {got})")
        if out["VERDICT"]["branch"] != "E1B-VOID-INSTRUMENT":
            fails.append(f"defect for {gate} did not void the round")

    manifest_defects = {
        "G-MANIFEST": _man(arming={"dose": 1.0, "mask": 31, "scope": "opp"}),
        "G-LEAF": _man(leaf_manifest={"leaf_hashes": {"harness": "deadbeef"},
                                      "leaf": {"bonus_cap": 8.0,
                                               "opp_bonus_cap": 8.0,
                                               "value_blend": 0.0}}),
        "G-NEGCTRL": _man(negative_control={"ok": True,
                                            "unarmed_dose0": {
                                                "census": {"total": 5,
                                                           "own_mover": 3,
                                                           "boosted": 2}},
                                            "armed_dose_dstar": {
                                                "census": {"total": 10,
                                                           "own_mover": 6,
                                                           "boosted": 4}}}),
    }
    for gate, man in manifest_defects.items():
        out = analyse(rows, targets, man, "MEM")
        got = {g["gate"] for g in out["GATES"] if g["status"] != "PASS"}
        if gate not in got:
            fails.append(f"manifest defect for {gate} did not fire it ({got})")
    out = analyse(rows, targets, None, "MEM")
    if "G-MANIFEST" not in {g["gate"] for g in out["GATES"]
                            if g["status"] != "PASS"}:
        fails.append("an ABSENT manifest did not FAIL G-MANIFEST")

    print(json.dumps({"selftest": "e1b adjudicator", "failures": fails,
                      "PASS": not fails}, indent=1))
    if fails:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    main()
