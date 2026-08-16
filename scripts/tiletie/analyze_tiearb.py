#!/usr/bin/env python3
"""Adjudicate measurement/tiearb_20260816/READ_RULE.md — TERMINAL-GROUNDED TIE
ARBITRATION (Stage 1, offline).

Joins the two judges' CRN-paired records on the 733-position tile-tie pricing
corpus:

  * `IF`  = `clair-puct`   — the pricing oracle (DESIGN §4 `V^IF`);
  * `ARB` = `tier1-greedy` — the arbitration policy (DESIGN §4 `V^ARB`),
                             the OOF run's DEV records + this run's HOLDOUT ones.

and computes, per position, on the parity cross-fit of DESIGN §4.1 (both folds,
symmetrized — `escalation_ladder.honest_regret`'s convention):

    a_arb   = argmax_a mean_{j∈sel} V^ARB[a,j]      # ARBITRATION (tier1-greedy)
    arb[p]  = mean_{j∈eva} V^IF[a_arb] − mean_{j∈eva} V^IF[champ]     # PRICED BY IF
    a_ora   = argmax_a mean_{j∈sel} V^IF [a,j]
    ora[p]  = mean_{j∈eva} V^IF[a_ora] − mean_{j∈eva} V^IF[champ]     # THE HEADROOM

plus the mandatory companions of DESIGN §4.3 (`C-RND`, `C-ARM0`, `SEC-ARB`,
`R_holdout`, `H_IF_holdout`, `PICKCHG`), the §4.5 sign check, the §4.3 bound
chain, and the mechanical READ_RULE §3/§4 adjudication.

It computes NO estimator that already exists: `parity_indices`,
`crossfit_regret`, `cluster_robust`, `bootstrap_roots`, `aggregate`,
`zero_rates`, `load_plan`, `discover_records`, `pts_to_elo`, `bound_block` and
the constants all come from `analyze_tiletie`, imported UNMODIFIED.

⚠️ `ora[p]` IS `analyze_tiletie.crossfit_regret(matrix_if, sel, eva, champ_pos)`
symmetrized over the two folds — there is literally one implementation, and
`a_arb` is likewise `crossfit_regret(matrix_arb, …)`'s own `a_plus`, so the
argmax tie-break convention `max(range(A), key=(mean, -i))` is shared by
construction rather than re-typed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import analyze_tiletie as AT                                        # noqa: E402

# ---- READ_RULE §2 committed constants -------------------------------------- #
RATIO_BAR = 0.35          # E-FLAT / W-FLAT's own fund bar, verbatim
Z_BAR = 2.0               # likewise theirs (== AT.Z_CONVICTION)
FIXED_DENOM = 0.2803      # the published honest base-rung regret (LADDER_READOUT)
FIXED_DENOM_SE = 0.0708   # ±, reported beside it; NOT propagated (it is a constant)
GBOOT_BAR = 0.05          # G-BOOT: >5% of reps with denominator ≤ 0 voids F
N_FLOOR_POOLED = 650      # G-N
N_FLOOR_HOLDOUT = 158     # G-N (3 of 4 chunks)
ARMSET_MAX_FRAC = 0.05    # G-ARMSET
BOOT_REPS = AT.BOOTSTRAP_REPS      # 20,000
PARITY_BASE = 1           # the primary's realized I1-parity-base choice
M_EXPECTED = 32           # DESIGN §3.3 — load-bearing, must NOT be raised

DESIGN_DOC = "measurement/tiearb_20260816/DESIGN.md"
READ_RULE = "measurement/tiearb_20260816/READ_RULE.md"
SCHEMA = "carcassonne-tiearb-readout/v1"

# E4 autopsy committed benchmarks (analyze_autopsy.sign_agreement), verbatim.
BENCH = ("80% at p 0.0012 = corroboration (2026-07-28 precedent); "
         "61.9% at p 0.38 = NOT corroboration (farm-war). "
         "The E4 autopsy's own Tier-1 leg: 62.1% at p 2.8e-05 with the "
         "aggregate sign NEGATIVE => PARTIAL.")

SCOPE_SENTENCE_F_FLAT = (
    "This is a FUNDING verdict, not an exclusion — the same scope W-FLAT carried. "
    "DESIGN §4.4 states before the run that this design resolves F_fixed only to "
    "±0.46–0.81 at 2σ, so a capture in the 0.18–0.30 band E-FLAT and W-FLAT saw is "
    "NOT excluded by this null; the honest claim is 'terminal-grounded tie arbitration "
    "did not fire at a mechanism-sized bar on the whole 733-position corpus', NOT "
    "'terminal grounding is worth nothing'.")

OPERATIVE_AXIS_STATEMENT = (
    "neither static afterstate functions, nor deeper same-shape search, nor wider "
    "determinization, nor terminal-grounded arbitration at the tied ply expresses the "
    "+0.252 pts/ply — while the out-of-family re-pricing says the headroom is real. "
    "The axis has no remaining named mechanism.")

BRANCH_TEXT = {
    "A-CAPTURE": (
        "TERMINAL-GROUNDED TIE ARBITRATION CAPTURES THE HEADROOM.",
        "An arm chosen by CRN-paired greedy playouts to terminal, on worlds disjoint from "
        "the ones it is priced on, is worth ≥ 35% of the oracle headroom at the identical "
        "bar and in the identical currency that E-FLAT (0.00/0.18/0.18) and W-FLAT "
        "(0.11/0.26/0.09/0.09/0.30) failed — and it convicts at 2σ, with the "
        "never-before-opened holdout not pointing the other way. LICENSES (does NOT fund) "
        "exactly one thing: a fresh Stage-2 pre-registration of a deck-paired GAME cell "
        "testing a BUDGET-MATCHED deployable form of the arbiter. That prereg must (a) name "
        "and price the budget-matched form — DESIGN §2.3 measures the honest shape at "
        "100–200× the champion's per-move budget, so a Stage-2 that does not solve cost is "
        "not fundable; (b) carry a matched-wall-clock control arm; (c) carry DESIGN §7.1 "
        "verbatim (both judges are terminal-grounded, so this is not yet a deploy-elo "
        "claim); (d) if the §4.5 sign check reads NO CORROBORATION, carry that verdict "
        "verbatim. ⛔ It does NOT license a game outside that prereg, a band, a deploy, a "
        "PRODUCTION.yaml change, a leaf term (CL-065 + two dead menus + the 38% reach bound "
        "stand), or a claim id."),
    "P-PARTIAL": (
        "PRESENT AT THE MECHANISM BAR BUT NOT CONVICTED — UNRESOLVED.",
        "At least one ratio reading clears 0.35 but the conjunction fails (the z bar, or the "
        "two ratio readings straddle, or the blind holdout leans negative). NOTHING CLOSES "
        "AND NOTHING IS LICENSED — in particular this does NOT close the mechanism and does "
        "NOT fund a Stage-2."),
    "F-FLAT": (
        "THE MECHANISM DID NOT FIRE AT A MECHANISM-SIZED BAR ON 733 POSITIONS.",
        "Neither ratio reading reaches 0.35 and the mean is not convicted."),
    "U-UNREADABLE": (
        "UNREADABLE — a §3 precondition failed.",
        "Report cost, integrity, and whichever gate failed. Nothing closes, nothing is "
        "licensed, nothing is re-labelled."),
}


# --------------------------------------------------------------------------- #
# record loading                                                               #
# --------------------------------------------------------------------------- #
def resolve_records_root(p) -> Path:
    """Accept either the parent of a `tier1-greedy/` dir or that dir itself."""
    p = Path(p)
    cand = p / "tier1-greedy"
    if cand.is_dir():
        return cand
    return p


def merge_arb_records(roots) -> tuple:
    """`discover_records` once per root, merged with an EXPLICIT duplicate check.

    `analyze_tiletie.discover_records` raises on a duplicate rid/leg WITHIN a
    root; a duplicate rid ACROSS roots is this function's hard error (the DEV and
    HOLDOUT legs are disjoint by construction, so an overlap means the wrong root
    was passed).
    """
    by_rid, present, not_ok, srcs = {}, defaultdict(int), [], {}
    resolved = []
    for r in roots:
        root = resolve_records_root(r)
        resolved.append(str(root))
        b, p, nk = AT.discover_records(root)
        dupes = sorted(set(b) & set(by_rid))
        if dupes:
            raise SystemExit(
                f"REFUSING: duplicate rid(s) across --arb-records roots "
                f"({srcs.get(dupes[0])} vs {root}): {dupes[:5]}")
        for rid, legs in b.items():
            by_rid[rid] = legs
            srcs[rid] = str(root)
        for k, v in p.items():
            present[f"{root}::{k}"] += v
        not_ok.extend(nk)
    return by_rid, dict(present), not_ok, resolved


# --------------------------------------------------------------------------- #
# the C-RND draw (DESIGN §4.3) — deterministic in (rid, seed), nothing else     #
# --------------------------------------------------------------------------- #
def rnd_arm_position(rid: str, n_arms: int, seed: int) -> int:
    """`random.Random(sha256(rid|seed)[:16]).randrange(n_arms)` — the SAME arm in
    both folds, so C-RND measures the arbiter's null LEVEL (mean-over-arms minus
    champ), not a second selection effect."""
    h = hashlib.sha256(f"{rid}|{seed}".encode()).hexdigest()[:16]
    return random.Random(int(h, 16)).randrange(n_arms)


# --------------------------------------------------------------------------- #
# per-position assembly (mirrors analyze_tiletie.build_positions)               #
# --------------------------------------------------------------------------- #
def build_positions(arms_index: dict, if_by_rid: dict, arb_by_rid: dict, rates: dict,
                    holdout_roots: set, rnd_seed: int, parity_base: int = PARITY_BASE):
    """Assemble matrix_if / matrix_arb per position and evaluate every §4 statistic.

    `include_partial_arms=False` semantics are inherited verbatim from
    `analyze_tiletie.build_positions`: a position missing any PLANNED leg in
    either judge is EXCLUDED and counted.
    """
    rows = []
    integ = {j: {"values_a_drift": 0, "seed_drift": 0, "crn_unverified": 0,
                 "checksum_failed": 0, "arm_index_mismatch": 0,
                 "zero_distinct_afterstates": 0} for j in ("if", "arb")}
    cross = {"compared_legs": 0, "crn_cross_mismatch": 0, "seed_cross_mismatch": 0,
             "arm_cross_mismatch": 0, "examples": []}
    counts = {"planned": 0, "absent_if": 0, "absent_arb": 0, "armset_mismatch": 0,
              "partial": 0, "champ_arm_absent": 0, "analysed": 0,
              "armset_mismatch_rids": [], "champ_absent_rids": []}

    for rid, meta in sorted(arms_index.items()):
        counts["planned"] += 1
        n_arms = len(meta["arms"])
        need = list(range(1, n_arms))
        if_legs = if_by_rid.get(rid, {})
        arb_legs = arb_by_rid.get(rid, {})
        have_if = sorted(k for k in if_legs if k in need)
        have_arb = sorted(k for k in arb_legs if k in need)
        if not have_if:
            counts["absent_if"] += 1
            continue
        if not have_arb:
            counts["absent_arb"] += 1
            continue
        # G-ARMSET: the two judges' scored arm_order must be IDENTICAL.
        if have_if != have_arb:
            counts["armset_mismatch"] += 1
            if len(counts["armset_mismatch_rids"]) < 20:
                counts["armset_mismatch_rids"].append(rid)
            continue
        # include_partial_arms=False (analyze_tiletie's own default).
        if [r for r in need if r not in if_legs]:
            counts["partial"] += 1
            continue

        arm_order = [0] + have_if
        champ_idx = meta.get("champ_arm_index")
        if champ_idx not in arm_order:
            counts["champ_arm_absent"] += 1
            if len(counts["champ_absent_rids"]) < 20:
                counts["champ_absent_rids"].append(rid)
            continue
        champ_pos = arm_order.index(champ_idx)

        # ---- integrity, per judge (analyze_tiletie §2.1 witnesses) -----------
        mats = {}
        for jname, legs in (("if", if_legs), ("arb", arb_legs)):
            ref = legs[have_if[0]]
            va0 = ref["values_a"]
            for r in have_if:
                rec = legs[r]
                if rec["values_a"] != va0:
                    integ[jname]["values_a_drift"] += 1
                if (rec["world_seeds"] != ref["world_seeds"]
                        or rec["playout_seeds"] != ref["playout_seeds"]):
                    integ[jname]["seed_drift"] += 1
                if not rec.get("crn_verified"):
                    integ[jname]["crn_unverified"] += 1
                if rec.get("checksum_ok") is False:
                    integ[jname]["checksum_failed"] += 1
                if (rec.get("pick_a") != meta["arms"][0]
                        or rec.get("pick_b") != meta["arms"][r]):
                    integ[jname]["arm_index_mismatch"] += 1
                if rec.get("distinct_afterstates") == 0:
                    integ[jname]["zero_distinct_afterstates"] += 1
            mats[jname] = [list(va0)] + [list(legs[r]["values_b"]) for r in have_if]

        # ---- the CROSS-JUDGE CRN witness (G-CRN, DESIGN §6) ------------------
        for r in have_if:
            irec, arec = if_legs[r], arb_legs[r]
            cross["compared_legs"] += 1
            if list(irec["world_seeds"]) != list(arec["world_seeds"]):
                cross["crn_cross_mismatch"] += 1
                if len(cross["examples"]) < 5:
                    cross["examples"].append(f"{rid} leg{r} world_seeds")
            if list(irec["playout_seeds"]) != list(arec["playout_seeds"]):
                cross["seed_cross_mismatch"] += 1
                if len(cross["examples"]) < 5:
                    cross["examples"].append(f"{rid} leg{r} playout_seeds")
            if (irec.get("pick_a"), irec.get("pick_b")) != (arec.get("pick_a"),
                                                            arec.get("pick_b")):
                cross["arm_cross_mismatch"] += 1

        matrix_if, matrix_arb = mats["if"], mats["arb"]
        m = len(matrix_if[0])

        # ---- DESIGN §4.1: both parity folds, symmetrized ---------------------
        folds = (AT.parity_indices(m, base=parity_base, swap=False),
                 AT.parity_indices(m, base=parity_base, swap=True))
        a_rnd = rnd_arm_position(rid, len(arm_order), rnd_seed)

        arb_f, ora_f, rnd_f, arm0_f, sec_f = [], [], [], [], []
        a_arbs, a_oras = [], []
        for sel, eva in folds:
            # SEC-ARB and the arbiter's own argmax are ONE call: crossfit_regret
            # returns (headroom, a_plus) and a_plus IS `a_arb` by definition.
            # ⚠️ AUDIT-ONLY / CIRCULAR: `sec` is the arbiter's picks priced by the
            # ARB judge itself, i.e. exactly the ARB judge's own cross-fit
            # headroom (`h_arb`), so its capture fraction against that headroom is
            # 1 BY CONSTRUCTION. Never a branch input.
            sec, a_arb = AT.crossfit_regret(matrix_arb, sel, eva, champ_pos)
            ora, a_ora = AT.crossfit_regret(matrix_if, sel, eva, champ_pos)
            eva_champ = AT._sub_mean(matrix_if[champ_pos], eva)
            arb_f.append(AT._sub_mean(matrix_if[a_arb], eva) - eva_champ)
            arm0_f.append(AT._sub_mean(matrix_if[a_arb], eva)
                          - AT._sub_mean(matrix_if[0], eva))
            rnd_f.append(AT._sub_mean(matrix_if[a_rnd], eva) - eva_champ)
            sec_f.append(sec)
            ora_f.append(ora)
            a_arbs.append(a_arb)
            a_oras.append(a_ora)

        def sym(xs):
            return (xs[0] + xs[1]) / 2.0

        stratum = meta["stratum"]
        sc = rates["by_stratum"].get(stratum, {"scale_all": 1.0, "scale_strict": 1.0})
        arb_v, ora_v, rnd_v = sym(arb_f), sym(ora_f), sym(rnd_f)
        sec_v = sym(sec_f)
        rows.append({
            "rid": rid, "root_id": meta["root_id"], "stratum": stratum,
            "rules_profile": meta["rules_profile"],
            "phase_bucket": meta.get("phase_bucket"),
            "capped": bool(meta.get("capped")), "ply": meta.get("ply"),
            "slice": "holdout" if meta["root_id"] in holdout_roots else "dev",
            "m": m, "n_arms_planned": n_arms, "n_arms_scored": len(arm_order),
            "champ_pos": champ_pos, "arm_order": arm_order,
            # --- the statistics (DESIGN §4.1) ---------------------------------
            "arb": arb_v, "ora": ora_v,
            "arb_p1": arb_f[0], "ora_p1": ora_f[0],
            "rnd": rnd_v, "arb_minus_rnd": arb_v - rnd_v,
            "arm0": sym(arm0_f),
            "sec": sec_v, "h_arb": sec_v,          # identical by construction
            # --- diagnostics ---------------------------------------------------
            "a_arb_folds": a_arbs, "a_ora_folds": a_oras, "a_rnd": a_rnd,
            "pickchg": bool(any(a != champ_pos for a in a_arbs)),
            "sel_agree": bool(all(a == b for a, b in zip(a_arbs, a_oras))),
            # --- the §0.A analytic-zero weights (INTERPRETATIONS I2/I3) --------
            "scale_all": sc["scale_all"], "scale_strict": sc["scale_strict"],
        })
        counts["analysed"] += 1

    denom = counts["analysed"] + counts["armset_mismatch"]
    counts["armset_mismatch_frac"] = (counts["armset_mismatch"] / denom) if denom else 0.0
    counts["armset_frac_note"] = ("denominator = positions where BOTH judges had at least "
                                  "one scored leg, i.e. analysed + armset-mismatched.")
    return rows, integ, cross, counts


# --------------------------------------------------------------------------- #
# the paired ratio bootstrap (READ_RULE §2)                                     #
# --------------------------------------------------------------------------- #
def paired_ratio_bootstrap(num_vals, den_vals, roots, n_boot=BOOT_REPS, seed=20260816):
    """95% CI for mean(num)/mean(den) by resampling ROOTS, BOTH recomputed per rep.

    `bootstrap_roots`'s convention (sum/count inside the replicate, so roots
    contributing several positions carry their weight), extended to carry two
    value vectors sharing one root vector — numerator and denominator are the
    SAME positions in the SAME order, so a replicate resamples a root and takes
    both terms together, which is what prices their positive correlation.

    Returns (median, lo95, hi95, n_finite_reps, frac_denominator_le_0).
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
    frac_den_le_0 = float((dens <= 0.0).sum()) / n_boot
    fin = out[np.isfinite(out)]
    if fin.size < 100:
        nan = float("nan")
        return nan, nan, nan, float(fin.size), frac_den_le_0
    fin.sort()
    return (float(np.median(fin)), float(fin[int(0.025 * fin.size)]),
            float(fin[min(fin.size - 1, int(0.975 * fin.size))]),
            float(fin.size), frac_den_le_0)


# --------------------------------------------------------------------------- #
# the §4.5 sign check                                                          #
# --------------------------------------------------------------------------- #
def binom_two_sided(agree: int, n: int) -> float:
    """Exact two-sided binomial p at p0=0.5. scipy when present, else math.comb —
    the two agree to float precision; the fallback is analyze_oof's own form."""
    if n == 0:
        return float("nan")
    try:
        from scipy.stats import binomtest            # noqa: WPS433
        return float(binomtest(agree, n, 0.5, alternative="two-sided").pvalue)
    except Exception:
        half = n / 2.0
        d = abs(agree - half)
        tail = sum(math.comb(n, k) for k in range(0, n + 1) if abs(k - half) >= d)
        return tail / (2.0 ** n)


def sign_check(rows: list, aggregate_mean: float, scale_key="scale_all") -> dict:
    """DESIGN §4.5 — over the positions where the arbiter CHANGES the champion's
    pick in at least one fold (the positions where the mechanism does anything).

    `agreement_rate` = fraction with arb[p] > 0; exact two-sided binomial p vs
    0.5; the aggregate sign is the POOLED headline mean(arb) (the number the
    branch reads), and the sub-mean over the pick-change positions is reported
    beside it. Adjudicated in the E4 autopsy's committed taxonomy.
    ⚠️ MANDATORY REPORTING; NEVER A BRANCH INPUT.
    """
    sub = [r for r in rows if r["pickchg"]]
    vals = [r["arb"] * r[scale_key] for r in sub]
    nz = [v for v in vals if v != 0.0]
    n = len(nz)
    agree = sum(1 for v in nz if v > 0)
    rate = (agree / n) if n else float("nan")
    p = binom_two_sided(agree, n)
    sub_mean = AT._mean(vals) if vals else float("nan")
    agg_sign = 0 if (aggregate_mean != aggregate_mean or aggregate_mean == 0) else (
        1 if aggregate_mean > 0 else -1)
    maj_sign = 0 if (rate != rate) else (1 if rate > 0.5 else -1)
    if n and rate > 0.5 and p < 0.05 and agg_sign == 1:
        verdict = "CORROBORATES"
    elif n and rate > 0.5 and p < 0.05:
        verdict = ("PARTIAL -- per-position signs agree above chance, but the aggregate "
                   "sign is OPPOSITE the per-position majority, so it does not corroborate "
                   "the DIRECTION.")
    else:
        verdict = "NO CORROBORATION -- sign agreement is not distinguishable from chance"
    return {"n_pickchg": len(sub), "n_nonzero": n, "n_agree": agree,
            "agreement_rate": rate, "binomial_p_two_sided": p,
            "aggregate_mean_pooled": aggregate_mean, "aggregate_sign": agg_sign,
            "per_position_majority_sign": maj_sign,
            "mean_over_pickchg_positions": sub_mean,
            "corroboration": verdict, "benchmarks": BENCH,
            "note": "Mandatory on every branch; NEVER a branch input (the OOF precedent: "
                    "57.1% at p 0.0547 = NO CORROBORATION while the mean convicted at "
                    "z +4.32)."}


# --------------------------------------------------------------------------- #
# READ_RULE §3 + §4 — fully mechanical, pure function of emitted numbers        #
# --------------------------------------------------------------------------- #
def _ge(x, bar):
    """`x >= bar` with NaN treated as NOT satisfying (a missing number never
    fires a branch conjunct)."""
    try:
        return bool(x == x and x >= bar)
    except TypeError:
        return False


def decide_branch(z_arb, F, F_fixed, arb_holdout, g_boot_fired, preconditions: dict) -> dict:
    """READ_RULE §3 (preconditions, evaluated FIRST) then §4.

        C_z    ≡ z_arb ≥ +2.0
        RBAR   ≡ (F_fixed ≥ 0.35) ∧ ((F ≥ 0.35) ∨ G-BOOT fired)
        ANY_R  ≡ (F_fixed ≥ 0.35) ∨ ((F ≥ 0.35) ∧ ¬G-BOOT)
        C_h    ≡ arb_holdout ≥ 0.0

        A-CAPTURE  = C_z ∧ RBAR ∧ C_h
        P-PARTIAL  = ¬A-CAPTURE ∧ ANY_R
        F-FLAT     = ¬A-CAPTURE ∧ ¬ANY_R

    Exclusive and exhaustive by construction (READ_RULE §4.1); `U-UNREADABLE`
    pre-empts everything. Takes ONLY numbers, so a test can sweep it.
    """
    failed = sorted(k for k, ok in preconditions.items() if not ok)
    if failed:
        return {"branch": "U-UNREADABLE", "failed_preconditions": failed,
                "C_z": None, "RBAR": None, "ANY_R": None, "C_h": None,
                "F_ge_bar": None, "F_fixed_ge_bar": None,
                "g_boot_fired": bool(g_boot_fired),
                "read": BRANCH_TEXT["U-UNREADABLE"][1]}
    gb = bool(g_boot_fired)
    c_z = _ge(z_arb, Z_BAR)
    f_ok = _ge(F, RATIO_BAR)
    ff_ok = _ge(F_fixed, RATIO_BAR)
    rbar = ff_ok and (f_ok or gb)
    any_r = ff_ok or (f_ok and not gb)
    c_h = _ge(arb_holdout, 0.0)
    if c_z and rbar and c_h:
        br = "A-CAPTURE"
    elif any_r:
        br = "P-PARTIAL"
    else:
        br = "F-FLAT"
    return {"branch": br, "failed_preconditions": [],
            "C_z": c_z, "RBAR": rbar, "ANY_R": any_r, "C_h": c_h,
            "F_ge_bar": f_ok, "F_fixed_ge_bar": ff_ok, "g_boot_fired": gb,
            "read": BRANCH_TEXT[br][1]}


def failed_conjuncts(adj: dict) -> list:
    """P-PARTIAL must say EXACTLY which conjunct failed (READ_RULE §4)."""
    out = []
    if adj.get("C_z") is False:
        out.append("C_z (z_arb >= +2.0)")
    if adj.get("RBAR") is False:
        out.append("RBAR ((F_fixed >= 0.35) and ((F >= 0.35) or G-BOOT fired))")
    if adj.get("C_h") is False:
        out.append("C_h (arb_holdout >= 0.0 — the blind holdout leans negative)")
    return out


# --------------------------------------------------------------------------- #
# aggregation                                                                  #
# --------------------------------------------------------------------------- #
STAT_KEYS = (
    ("arb", "arb"), ("ora", "ora"), ("rnd", "rnd"), ("arb_minus_rnd", "arb_minus_rnd"),
    ("arm0", "arm0"), ("sec", "sec"), ("h_arb", "h_arb"),
    ("arb_parity_base1", "arb_p1"), ("ora_parity_base1", "ora_p1"),
)


def agg_block(rows: list, seed: int) -> dict:
    out = {"n": len(rows), "n_roots": len({r["root_id"] for r in rows})}
    for name, key in STAT_KEYS:
        out[f"{name}_all"] = AT.aggregate(rows, key, "scale_all",
                                          n_boot=BOOT_REPS, seed=seed)
        out[f"{name}_discriminable"] = AT.aggregate(rows, key, None,
                                                    n_boot=BOOT_REPS, seed=seed)
    return out


def cut_blocks(rows: list) -> dict:
    """Per-stratum / per-profile / per-phase / capped cuts. NEVER a branch input."""
    cuts = defaultdict(lambda: {"arb": [], "ora": [], "roots": []})
    for r in rows:
        for nm in (f"stratum:{r['stratum']}", f"profile:{r['rules_profile']}",
                   f"phase:{r['phase_bucket']}",
                   "capped_only" if r["capped"] else "uncapped_only"):
            cuts[nm]["arb"].append(r["arb"] * r["scale_all"])
            cuts[nm]["ora"].append(r["ora"] * r["scale_all"])
            cuts[nm]["roots"].append(r["root_id"])
    out = {}
    for nm, d in sorted(cuts.items()):
        ma, sa, n, g = AT.cluster_robust(d["arb"], d["roots"])
        mo, so, _, _ = AT.cluster_robust(d["ora"], d["roots"])
        out[nm] = {"n": n, "n_roots": g,
                   "arb": ma, "se_arb": sa, "z_arb": (ma / sa) if sa else float("nan"),
                   "ora": mo, "se_ora": so, "z_ora": (mo / so) if so else float("nan"),
                   "F_point": (ma / mo) if mo else float("nan"),
                   "F_fixed_point": ma / FIXED_DENOM}
    return out


# --------------------------------------------------------------------------- #
# side artifacts (cost / G-REPRO) — read if present, never required             #
# --------------------------------------------------------------------------- #
def cost_block(out_dir: Path) -> dict:
    """Realized c_tier1 on THIS run's chunks, plus the pilot's G-REPRO count.

    Read from artifacts the runners already write (RUN_MANIFEST_chunk*.json,
    PILOT.json). Absent => reported as unavailable, never invented.
    """
    out = {"c_tier1_worker_s_per_playout": None, "sum_elapsed_secs": None,
           "playouts": None, "source": None, "g_repro": None, "co_tenant": None,
           "note": "READ_RULE §4.2 items 9 and 10; absent artifacts are reported as null."}
    pilot = out_dir / "PILOT.json"
    if pilot.is_file():
        try:
            d = json.loads(pilot.read_text())
            out["g_repro"] = d.get("g_repro") or d.get("integrity", {})
            out["co_tenant"] = d.get("co_tenant")
        except Exception as exc:                       # pragma: no cover - defensive
            out["g_repro"] = f"unreadable: {exc}"
    legs = 0.0
    playouts = 0
    found = []
    for mf in sorted(out_dir.glob("RUN_MANIFEST_chunk*.json")):
        try:
            d = json.loads(mf.read_text())
        except Exception:                              # pragma: no cover - defensive
            continue
        found.append(mf.name)
        for leg in (d.get("legs") or []):
            if isinstance(leg, dict):
                legs += float(leg.get("elapsed_secs") or 0.0)
                playouts += int(leg.get("playouts") or 0)
    if found:
        out["source"] = found
        out["sum_elapsed_secs"] = legs
        out["playouts"] = playouts or None
        if playouts:
            out["c_tier1_worker_s_per_playout"] = legs / playouts
    return out


def realized_c_from_records(arb_by_rid: dict, rids: set) -> dict:
    """Fallback for item 9: c = Σ elapsed_secs / playouts over the holdout legs."""
    tot, legs = 0.0, 0
    m = 0
    for rid in rids:
        for rec in (arb_by_rid.get(rid) or {}).values():
            e = rec.get("elapsed_secs")
            if e is None:
                continue
            tot += float(e)
            legs += 1
            m = int(rec.get("m") or m)
    playouts = legs * 2 * (m or M_EXPECTED)
    return {"legs": legs, "playouts": playouts, "sum_elapsed_secs": tot,
            "c_tier1_worker_s_per_playout": (tot / playouts) if playouts else None,
            "note": "computed from the ARB records' own elapsed_secs on the holdout legs."}


# --------------------------------------------------------------------------- #
# MAIN                                                                          #
# --------------------------------------------------------------------------- #
DEFAULT_ARB_ROOTS = ["/mnt/c/carc-shared/tiletie_oof_20260814/merged",
                     "/mnt/c/carc-shared/tiletie_oof_20260814/pilot",
                     "/mnt/c/carc-shared/tiearb_20260816/merged"]


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--if-records",
                    default="/mnt/c/carc-shared/tiletie_pricing_20260812/clair-puct",
                    help="clair-puct (IF) records root")
    ap.add_argument("--arb-records", action="append", default=None,
                    help="repeatable; roots holding tier1-greedy (ARB) records. Either the "
                         "parent of a tier1-greedy/ dir or that dir itself.")
    ap.add_argument("--plan-dir",
                    default=str(REPO / "measurement/tiletie_pricing_20260812/positions_pooled"))
    ap.add_argument("--full-supply-plan",
                    default=str(REPO / "measurement/tiletie_pricing_20260812/"
                                       "positions/POSITIONS_PLAN.json"))
    ap.add_argument("--holdout-roots",
                    default=str(REPO / "measurement/tiletie_mining_20260814/"
                                       "HOLDOUT_ROOTS.json"))
    ap.add_argument("--out-dir", default=str(REPO / "measurement/tiearb_20260816"))
    ap.add_argument("--boot-seed", type=int, default=20260816)
    ap.add_argument("--rnd-seed", type=int, default=20260816)
    ap.add_argument("--parity-base", type=int, choices=(0, 1), default=PARITY_BASE)
    ap.add_argument("--sigma-game", type=float, default=AT.SIGMA_GAME_FIXED_V1)
    a = ap.parse_args(argv)
    if not a.arb_records:
        a.arb_records = list(DEFAULT_ARB_ROOTS)
    return a


def build_readout(args) -> dict:
    plan_bundle = AT.load_plan(args.plan_dir)
    arms = plan_bundle["arms"]
    rates = AT.zero_rates(plan_bundle, args.full_supply_plan)
    holdout_roots = set(json.loads(Path(args.holdout_roots).read_text())["holdout_roots"])

    if_root = resolve_records_root(args.if_records)
    if if_root.name != "clair-puct" and (Path(args.if_records) / "clair-puct").is_dir():
        if_root = Path(args.if_records) / "clair-puct"
    if_by_rid, if_present, if_not_ok = AT.discover_records(if_root)
    arb_by_rid, arb_present, arb_not_ok, arb_roots = merge_arb_records(args.arb_records)

    rows, integ, cross, counts = build_positions(
        arms, if_by_rid, arb_by_rid, rates, holdout_roots,
        rnd_seed=args.rnd_seed, parity_base=args.parity_base)
    if not rows:
        raise SystemExit("REFUSING: no position had BOTH judges' complete records.")

    dev = [r for r in rows if r["slice"] == "dev"]
    hold = [r for r in rows if r["slice"] == "holdout"]
    blocks = {"pooled": agg_block(rows, args.boot_seed),
              "dev": agg_block(dev, args.boot_seed) if dev else None,
              "holdout": agg_block(hold, args.boot_seed) if hold else None}

    P = blocks["pooled"]
    arb_mean = P["arb_all"]["mean"]
    ora_mean = P["ora_all"]["mean"]
    se_arb = P["arb_all"]["se_cluster"]
    z_arb = P["arb_all"]["z"]
    z_ora = P["ora_all"]["z"]

    roots_v = [r["root_id"] for r in rows]
    num = [r["arb"] * r["scale_all"] for r in rows]
    den = [r["ora"] * r["scale_all"] for r in rows]
    F_med, F_lo, F_hi, F_fin, g_boot = paired_ratio_bootstrap(
        num, den, roots_v, n_boot=BOOT_REPS, seed=args.boot_seed)
    F = (arb_mean / ora_mean) if (ora_mean not in (None, 0)
                                  and arb_mean is not None) else float("nan")
    g_boot_fired = bool(g_boot == g_boot and g_boot > GBOOT_BAR)

    F_fixed = (arb_mean / FIXED_DENOM) if arb_mean is not None else float("nan")
    F_fixed_lo = (P["arb_all"]["boot_lo"] / FIXED_DENOM
                  if P["arb_all"]["boot_lo"] is not None else float("nan"))
    F_fixed_hi = (P["arb_all"]["boot_hi"] / FIXED_DENOM
                  if P["arb_all"]["boot_hi"] is not None else float("nan"))

    # R_holdout = H_ARB / H_IF on the holdout only (DESIGN §4.3) — free OOS
    # replication of C-CONFIRM. Reported; ADJUDICATES NOTHING.
    if hold:
        h_num = [r["h_arb"] * r["scale_all"] for r in hold]
        h_den = [r["ora"] * r["scale_all"] for r in hold]
        h_roots = [r["root_id"] for r in hold]
        Rh_med, Rh_lo, Rh_hi, Rh_fin, Rh_gboot = paired_ratio_bootstrap(
            h_num, h_den, h_roots, n_boot=BOOT_REPS, seed=args.boot_seed)
        Rh = (blocks["holdout"]["h_arb_all"]["mean"]
              / blocks["holdout"]["ora_all"]["mean"]) if blocks["holdout"][
                  "ora_all"]["mean"] else float("nan")
        arb_holdout = blocks["holdout"]["arb_all"]["mean"]
    else:
        Rh = Rh_med = Rh_lo = Rh_hi = Rh_fin = Rh_gboot = float("nan")
        arb_holdout = float("nan")

    pre = {
        "G-CRN": bool(cross["crn_cross_mismatch"] == 0 and cross["seed_cross_mismatch"] == 0
                      and integ["arb"]["crn_unverified"] == 0
                      and integ["arb"]["checksum_failed"] == 0
                      and integ["if"]["crn_unverified"] == 0
                      and integ["if"]["checksum_failed"] == 0),
        "G-ARM": bool(integ["if"]["arm_index_mismatch"] == 0
                      and integ["arb"]["arm_index_mismatch"] == 0
                      and cross["arm_cross_mismatch"] == 0),
        "G-VA": bool(integ["if"]["values_a_drift"] == 0
                     and integ["arb"]["values_a_drift"] == 0),
        "G-SLICE": bool(all(r["root_id"] in holdout_roots for r in hold)
                        and not any(r["root_id"] in holdout_roots for r in dev)),
        "G-ARMSET": bool(counts["armset_mismatch_frac"] <= ARMSET_MAX_FRAC),
        "G-N": bool(len(rows) >= N_FLOOR_POOLED and len(hold) >= N_FLOOR_HOLDOUT),
        "G-DENOM": bool(ora_mean is not None and ora_mean > 0
                        and z_ora == z_ora and z_ora >= Z_BAR),
    }

    adj = decide_branch(z_arb, F, F_fixed, arb_holdout, g_boot_fired, pre)
    adj["failed_conjuncts"] = failed_conjuncts(adj)
    adj["branch_headline"] = BRANCH_TEXT[adj["branch"]][0]
    if adj["branch"] == "F-FLAT":
        adj["mandatory_scope_sentence"] = SCOPE_SENTENCE_F_FLAT
        adj["operative_axis_statement"] = OPERATIVE_AXIS_STATEMENT
        adj["rider_half_capture_excluded"] = bool(F_fixed_hi == F_fixed_hi
                                                  and F_fixed_hi < RATIO_BAR)

    # ---- the §4.3 bound chain (×1.40 full-set, ÷3.2 with the ÷5.23 bracket) ---
    def bound(a, label):
        if a is None or a["mean"] is None:
            return None
        return AT.bound_block(a["mean"] * AT.FULLSET_EXTRAP,
                              (a["boot_lo"] or 0.0) * AT.FULLSET_EXTRAP,
                              (a["boot_hi"] or 0.0) * AT.FULLSET_EXTRAP,
                              args.sigma_game, label)

    # ---- resolution / sizing --------------------------------------------------
    two_sigma = 2 * se_arb if (se_arb and se_arb == se_arb) else float("nan")
    n_for_pm = (len(rows) * (two_sigma / (RATIO_BAR * FIXED_DENOM)) ** 2
                if two_sigma == two_sigma and two_sigma > 0 else None)

    sign = sign_check(rows, arb_mean)

    return {
        "schema": SCHEMA, "design_doc": DESIGN_DOC, "read_rule": READ_RULE,
        "generated_utc": AT._now_utc(),
        "judges": {
            "IF": "clair-puct (production curve125 leaf, leaf hash a36d2e15a3b3d71d, "
                  "PUCT @ 100 clairvoyant sims, played to terminal on a known deck)",
            "ARB": "tier1-greedy (RuleBasedPlayer, v1 OBJECT leaf virtual_score_inplace, "
                   "1-ply argmax, no search, python-only, played to terminal)"},
        "args": {"if_records": str(if_root), "arb_records": arb_roots,
                 "plan_dir": args.plan_dir, "full_supply_plan": args.full_supply_plan,
                 "holdout_roots": args.holdout_roots, "out_dir": args.out_dir,
                 "boot_seed": args.boot_seed, "rnd_seed": args.rnd_seed,
                 "parity_base": args.parity_base, "sigma_game": args.sigma_game,
                 "bootstrap_reps": BOOT_REPS},
        "constants": {"ratio_bar": RATIO_BAR, "z_bar": Z_BAR,
                      "fixed_denominator": FIXED_DENOM,
                      "fixed_denominator_se": FIXED_DENOM_SE,
                      "g_boot_bar": GBOOT_BAR, "m_expected": M_EXPECTED,
                      "n_floor_pooled": N_FLOOR_POOLED,
                      "n_floor_holdout": N_FLOOR_HOLDOUT,
                      "fullset_extrapolation": AT.FULLSET_EXTRAP,
                      "tied_tile_plies_per_game": AT.TIED_TILE_PLIES_PER_GAME,
                      "non_additivity": AT.NON_ADDITIVITY,
                      "non_additivity_low_end": AT.NON_ADDITIVITY_LOW_END,
                      "sigma_game_fixed_v1": AT.SIGMA_GAME_FIXED_V1,
                      "sigma_game_walled": AT.SIGMA_GAME_WALLED},
        "completion": {
            "planned_positions": counts["planned"],
            "n_analysed": len(rows), "n_roots": len({r["root_id"] for r in rows}),
            "n_dev": len(dev), "n_holdout": len(hold),
            "m_realized": sorted({r["m"] for r in rows}),
            "m_matches_design": bool({r["m"] for r in rows} == {M_EXPECTED}),
            "planned_holdout": 211,
            "holdout_completion_frac": len(hold) / 211.0,
            "excluded": {k: counts[k] for k in ("absent_if", "absent_arb",
                                                "armset_mismatch", "partial",
                                                "champ_arm_absent")},
            "armset_mismatch_frac": counts["armset_mismatch_frac"],
            "armset_frac_note": counts["armset_frac_note"],
            "armset_mismatch_rids": counts["armset_mismatch_rids"],
            "champ_absent_rids": counts["champ_absent_rids"],
            "records_not_ok": {"if": len(if_not_ok), "arb": len(arb_not_ok)},
            "composition": composition(rows),
        },
        "integrity": {"per_judge": integ, "cross_judge_G_CRN": cross},
        "preconditions": pre,
        "statistics": blocks,
        "primary": {
            "arb": arb_mean, "se_arb": se_arb, "z_arb": z_arb,
            "arb_boot_lo": P["arb_all"]["boot_lo"], "arb_boot_hi": P["arb_all"]["boot_hi"],
            "ora": ora_mean, "se_ora": P["ora_all"]["se_cluster"], "z_ora": z_ora,
            "ora_boot_lo": P["ora_all"]["boot_lo"], "ora_boot_hi": P["ora_all"]["boot_hi"],
            "F": F, "F_lo": F_lo, "F_hi": F_hi, "F_boot_median": F_med,
            "F_boot_finite_reps": F_fin,
            "G-BOOT": g_boot, "G-BOOT_fired": g_boot_fired,
            "F_fixed": F_fixed, "F_fixed_lo": F_fixed_lo, "F_fixed_hi": F_fixed_hi,
            "arb_holdout": arb_holdout,
            "coverage": 1.0,
            "coverage_note": "1.0 BY CONSTRUCTION — the arbiter selects only from the "
                             "scored arm set. Reported as a witness, not a conjunct.",
        },
        "companions": {
            "C-RND": P["rnd_all"], "arb_minus_rnd": P["arb_minus_rnd_all"],
            "C-ARM0": P["arm0_all"],
            "SEC-ARB": dict(P["sec_all"], label=(
                "⚠️ AUDIT-ONLY, CIRCULAR: the arbiter's picks priced by tier1-greedy ITSELF. "
                "Its capture fraction against its own headroom is 1 BY CONSTRUCTION "
                "(self-arbitration priced by the self-judge IS the cross-fit headroom). "
                "NEVER a branch input.")),
            "R_holdout": {"R": Rh, "boot_median": Rh_med, "lo": Rh_lo, "hi": Rh_hi,
                          "finite_reps": Rh_fin, "frac_denominator_le_0": Rh_gboot,
                          "H_ARB": (blocks["holdout"]["h_arb_all"] if hold else None),
                          "H_IF": (blocks["holdout"]["ora_all"] if hold else None),
                          "note": "The OOF run's retention ratio recomputed on positions it "
                                  "never opened — a FREE out-of-sample replication of "
                                  "C-CONFIRM (R = 1.827, CI [+0.913, +3.995]). Reported; "
                                  "ADJUDICATES NOTHING (the OOF read-rule is spent)."},
            "H_IF_holdout": (blocks["holdout"]["ora_all"] if hold else None),
            "PICKCHG": {
                "frac_pick_changed": AT._mean([1.0 if r["pickchg"] else 0.0 for r in rows]),
                "frac_selector_agreement": AT._mean(
                    [1.0 if r["sel_agree"] else 0.0 for r in rows]),
                "frac_pick_changed_fold1": AT._mean(
                    [1.0 if r["a_arb_folds"][0] != r["champ_pos"] else 0.0 for r in rows]),
                "frac_pick_changed_fold2": AT._mean(
                    [1.0 if r["a_arb_folds"][1] != r["champ_pos"] else 0.0 for r in rows]),
                "note": "the E-FLAT / W-FLAT diagnostic — 'moves picks at tied plies without "
                        "IMPROVING them' is read off this beside `arb`.",
            },
        },
        "sign_check": sign,
        "bounds": {"arb": bound(P["arb_all"], "pooled/arb"),
                   "ora": bound(P["ora_all"], "pooled/ora"),
                   "note": "×1.40 full-set extrapolation and the ÷3.2 chain applied "
                           "IDENTICALLY to numerator and denominator, so they CANCEL OUT "
                           "OF F. Every §4.3 caveat inherited verbatim: NON_ADDITIVITY=3.2 "
                           "is n=1 with a ÷5.23 low-end bracket — a ±1.6× bracket, not a "
                           "point. The linear-φ step degrades above ~1σ."},
        "resolution": {
            "sd_positions_arb": P["arb_all"]["sd_positions"],
            "two_sigma_pts": two_sigma,
            "two_sigma_elo": (AT.pts_to_elo(two_sigma * AT.FULLSET_EXTRAP,
                                            sigma_game=args.sigma_game)
                              if two_sigma == two_sigma else None),
            "two_sigma_in_F_fixed_units": (two_sigma / FIXED_DENOM
                                           if two_sigma == two_sigma else None),
            "n_for_F_fixed_pm_0.35": n_for_pm,
            "note": "DESIGN §4.4 projected ≈2,200 positions to resolve F_fixed to ±0.35 "
                    "against a total deduped supply of 733. n scales the realized "
                    "CLUSTER-ROBUST se (design effect included).",
        },
        "cost": cost_block(Path(args.out_dir)),
        "cost_from_records": realized_c_from_records(
            arb_by_rid, {r["rid"] for r in hold}),
        "cuts_never_adjudicated": cut_blocks(rows),
        "adjudication": adj,
        "governance": (
            "Measurement only. 0 games on EVERY branch. No experiments/results.csv row, no "
            "band, no governance/BAND_REGISTRY.csv entry, no claim id minted, "
            "governance/PRODUCTION.yaml untouched. ⚠️ THIS RUN SPENDS THE HOLDOUT (120 "
            "roots / 211 positions): it is burned and is no longer an unburned reserve, on "
            "every branch."),
        "_rows": rows,
    }


def composition(rows: list) -> dict:
    out = {}
    for sl in ("pooled", "dev", "holdout"):
        sub = rows if sl == "pooled" else [r for r in rows if r["slice"] == sl]
        d = {"n": len(sub), "n_roots": len({r["root_id"] for r in sub}),
             "by_stratum": defaultdict(int), "by_profile": defaultdict(int),
             "by_phase": defaultdict(int), "capped": 0}
        for r in sub:
            d["by_stratum"][r["stratum"]] += 1
            d["by_profile"][r["rules_profile"]] += 1
            d["by_phase"][str(r["phase_bucket"])] += 1
            d["capped"] += 1 if r["capped"] else 0
        out[sl] = {k: (dict(v) if isinstance(v, defaultdict) else v) for k, v in d.items()}
    return out


# --------------------------------------------------------------------------- #
# RENDERING — READ_RULE §4.2's mandatory list 1..12, in that order              #
# --------------------------------------------------------------------------- #
def _f(x, nd=4):
    if x is None:
        return "n/a"
    try:
        if x != x:
            return "nan"
        return f"{x:+.{nd}f}"
    except (TypeError, ValueError):
        return str(x)


def _row(name, a):
    if a is None or a.get("mean") is None:
        return f"| {name} | 0 | — | — | — | — |"
    return (f"| {name} | {a['n']} | {_f(a['mean'])} | {_f(a['se_cluster'])} | "
            f"[{_f(a['boot_lo'])}, {_f(a['boot_hi'])}] | {_f(a['z'], 2)} |")


def render(v: dict) -> str:
    L = []
    A = L.append
    adj = v["adjudication"]
    p = v["primary"]
    c = v["completion"]
    A("# TERMINAL-GROUNDED TIE ARBITRATION — READ-OUT (Stage 1, offline)")
    A("")
    A(f"**Branch: `{adj['branch']}` — {adj['branch_headline']}** — adjudicated mechanically "
      f"by [READ_RULE.md](READ_RULE.md), committed before any number existed.")
    A("")
    A(adj["read"])
    A("")
    if adj["branch"] == "P-PARTIAL" and adj.get("failed_conjuncts"):
        A(f"**Conjunct(s) that failed:** {', '.join(adj['failed_conjuncts'])}.")
        A("")
    if adj["branch"] == "F-FLAT":
        A(f"> ⚠️ **MANDATORY SCOPE SENTENCE, never separated from the verdict:** "
          f"*\"{adj['mandatory_scope_sentence']}\"*")
        A("")
        if adj.get("rider_half_capture_excluded"):
            A("> **Rider (applies):** `F_fixed_hi` < 0.35, so **half-capture IS excluded at "
              "95%** and the scope sentence above is superseded in that one respect.")
            A("")
        A(f"**Operative statement of the tile-tie axis, recorded on this branch:** "
          f"*{adj['operative_axis_statement']}*")
        A("")
    if adj["branch"] == "A-CAPTURE" and v["sign_check"]["corroboration"].startswith("NO"):
        A("> ⚠️ The §4.5 sign check reads **NO CORROBORATION**. READ_RULE §4 requires the "
          "licensed Stage-2 prereg to carry that verdict **verbatim**.")
        A("")
    A(f"- IF judge: {v['judges']['IF']}")
    A(f"- ARB judge: {v['judges']['ARB']}")
    A(f"- n = **{c['n_analysed']}** positions / {c['n_roots']} roots "
      f"(dev {c['n_dev']} · holdout {c['n_holdout']} = "
      f"{100.0*c['holdout_completion_frac']:.1f}% of the planned 211); "
      f"M = {c['m_realized']} CRN worlds, salt `tiletie-v1`, "
      f"**bit-identical between the two judges**")
    if not c["m_matches_design"]:
        A("")
        A(f"> ⚠️ **`M` DOES NOT MATCH THE DESIGN.** DESIGN §3.3 locks `M = "
          f"{v['constants']['m_expected']}` and states it is load-bearing (the cross-fit "
          f"selects on M/2 and evaluates on M/2, so a larger M makes the estimand LARGER). "
          f"Realized: {c['m_realized']}.")
    A("")
    A("> ⚠️ **THE BRANCH INPUT IS THE POOLED n = 733 READ, NOT THE HOLDOUT ALONE** — a "
      "**declared deviation from the funding brief** (DESIGN §4.4: n = 211 cannot convict "
      "even a 100% capture). The holdout enters `A-CAPTURE` only as the blind "
      "sign-consistency conjunct `C_h`.")
    A("")
    A("> ⚠️ **THIS RUN SPENDS THE HOLDOUT**, on every branch. It is burned and is no longer "
      "an unburned reserve.")
    A("")

    # ---- 1 ---------------------------------------------------------------- #
    A("## 1. The primary statistics — pooled / DEV / HOLDOUT, both scalings")
    A("")
    A(f"- **`arb` = {_f(p['arb'])}** pts/tied tile ply (se {_f(p['se_arb'])}, "
      f"**z {_f(p['z_arb'],2)}**), boot CI [{_f(p['arb_boot_lo'])}, {_f(p['arb_boot_hi'])}]")
    A(f"- **`ora` = {_f(p['ora'])}** pts/tied tile ply (se {_f(p['se_ora'])}, "
      f"z {_f(p['z_ora'],2)}), boot CI [{_f(p['ora_boot_lo'])}, {_f(p['ora_boot_hi'])}]")
    A(f"- **`F  = arb/ora` = {_f(p['F'],3)}**, paired-root-bootstrap 95% CI "
      f"**[{_f(p['F_lo'],3)}, {_f(p['F_hi'],3)}]** (median {_f(p['F_boot_median'],3)}, "
      f"{_f(p['F_boot_finite_reps'],0)} finite reps)")
    A(f"- **`F_fixed = arb/{FIXED_DENOM}` = {_f(p['F_fixed'],3)}**, CI "
      f"**[{_f(p['F_fixed_lo'],3)}, {_f(p['F_fixed_hi'],3)}]** — the cross-programme "
      f"currency E-FLAT (0.00/0.18/0.18) and W-FLAT (0.11/0.26/0.09/0.09/0.30) were graded "
      f"in. The denominator is the fixed published +{FIXED_DENOM} ± {FIXED_DENOM_SE} "
      f"pts/ply with **no holdout noise**.")
    A(f"- `G-BOOT` (fraction of reps with denominator ≤ 0) = **{_f(p['G-BOOT'],4)}** "
      f"vs bar {GBOOT_BAR} ⇒ "
      f"**{'FIRED — F is VOID as a branch input; the ratio conjunct rests on F_fixed alone' if p['G-BOOT_fired'] else 'not fired'}**")
    A(f"- `arb_holdout` (the blind sign-consistency conjunct `C_h`) = "
      f"**{_f(p['arb_holdout'])}**")
    A(f"- bars: ratio **{RATIO_BAR}**, z **+{Z_BAR}** — *not new constants*: both are "
      f"E-FLAT's and W-FLAT's own committed fund bar, verbatim.")
    A("")
    A("⚠️ Declared difference inherited from DESIGN §4.2: the ladders' numerators are "
      "full-M mean differences (their selector is independent of the oracle values); ours "
      "is a cross-fit half-M difference — unbiased for the same estimand, **noisier**, "
      "never *larger* in expectation.")
    A("")
    for sl in ("pooled", "dev", "holdout"):
        blk = v["statistics"].get(sl)
        if not blk:
            continue
        A(f"### {sl}  (n = {blk['n']} positions, {blk['n_roots']} roots)")
        A("")
        A("| statistic | n | mean | se (cluster) | 95% CI (boot) | z |")
        A("|---|---|---|---|---|---|")
        for name, _k in STAT_KEYS:
            A(_row(f"`{name}` — all (`scale_all`)", blk[f"{name}_all"]))
            A(_row(f"`{name}` — discriminable", blk[f"{name}_discriminable"]))
        A("")

    # ---- 2 ---------------------------------------------------------------- #
    A("## 2. The single-fold `parity_base=1` readings (the `I1` diagnostic)")
    A("")
    A("| slice | `arb` symmetrized | `arb` parity_base=1 | `ora` symmetrized | "
      "`ora` parity_base=1 |")
    A("|---|---|---|---|---|")
    for sl in ("pooled", "dev", "holdout"):
        blk = v["statistics"].get(sl)
        if not blk:
            continue
        A(f"| {sl} | {_f(blk['arb_all']['mean'])} | {_f(blk['arb_parity_base1_all']['mean'])} "
          f"| {_f(blk['ora_all']['mean'])} | {_f(blk['ora_parity_base1_all']['mean'])} |")
    A("")
    A("Both headline statistics are **symmetrized over the two parity folds** "
      "(`escalation_ladder.honest_regret`'s convention), so the pricing run's `I1` "
      "parity-base ambiguity cannot be a lever.")
    A("")

    # ---- 3 ---------------------------------------------------------------- #
    A("## 3. Mandatory companions (DESIGN §4.3) — reported, never a branch input")
    A("")
    comp = v["companions"]
    A("| companion | n | mean | se | 95% CI | z |")
    A("|---|---|---|---|---|---|")
    A(_row("`C-RND` — random-arm arbiter (the NULL LEVEL)", comp["C-RND"]))
    A(_row("**`arb − rnd`** — the mechanism net of the null level",
           comp["arb_minus_rnd"]))
    A(_row("`C-ARM0` — arm-0 comparator (`headroom_leaf` currency)", comp["C-ARM0"]))
    A(_row("`SEC-ARB` ⚠️ AUDIT-ONLY, CIRCULAR", comp["SEC-ARB"]))
    A("")
    A("⚠️ **`SEC-ARB` is CIRCULAR by construction**: it is the arbiter's picks priced by "
      "`tier1-greedy` *itself*, i.e. the ARB judge's own cross-fit headroom, so its capture "
      "fraction against that headroom is **exactly 1**. It is reported in pts with its `z` "
      "and is **never a branch input**.")
    A("")
    A("**DESIGN §7.3 threat, mandatory when it applies:** `arb` under an *uninformative* "
      "arbiter is `mean-over-arms − champ`, not 0. If `C-RND` is materially positive, part "
      f"of `arb` is not the mechanism — hence `arb − rnd` = "
      f"**{_f(comp['arb_minus_rnd']['mean'])}** is printed beside it. Reported, never "
      "adjudicated on.")
    A("")

    # ---- 4 ---------------------------------------------------------------- #
    A("## 4. `R_holdout` and `H_IF_holdout` — the free out-of-sample replication")
    A("")
    rh = comp["R_holdout"]
    A(f"- **`R_holdout = H_ARB/H_IF` (holdout only) = {_f(rh['R'],3)}**, paired-root-boot "
      f"95% CI **[{_f(rh['lo'],3)}, {_f(rh['hi'],3)}]** (median {_f(rh['boot_median'],3)}; "
      f"reps with denominator ≤ 0: {_f(rh['frac_denominator_le_0'],4)})")
    if rh["H_ARB"]:
        A(f"- `H_ARB` (holdout) = {_f(rh['H_ARB']['mean'])} (se {_f(rh['H_ARB']['se_cluster'])}, "
          f"z {_f(rh['H_ARB']['z'],2)}) · `H_IF` (holdout) = {_f(rh['H_IF']['mean'])} "
          f"(se {_f(rh['H_IF']['se_cluster'])}, **z {_f(rh['H_IF']['z'],2)}**)")
    A(f"- {rh['note']}")
    A("")
    A(f"**`H_IF_holdout`** is the in-family headroom on the {c['n_holdout']} realized "
      f"holdout positions (of 211 planned) that no programme had ever opened — a free "
      f"out-of-sample confirmation of the +0.252 itself. Reported; "
      f"**adjudicates nothing.**")
    A("")

    # ---- 5 ---------------------------------------------------------------- #
    A("## 5. `PICKCHG` — the E-FLAT / W-FLAT diagnostic")
    A("")
    pc = comp["PICKCHG"]
    A(f"- fraction of positions where `a_arb ≠ champ` (either fold): "
      f"**{_f(pc['frac_pick_changed'],3)}** "
      f"(fold 1 {_f(pc['frac_pick_changed_fold1'],3)} · fold 2 "
      f"{_f(pc['frac_pick_changed_fold2'],3)})")
    A(f"- fraction where the arbiter and the oracle select the SAME arm in both folds "
      f"(`a_arb = a_ora`): **{_f(pc['frac_selector_agreement'],3)}**")
    A(f"- coverage = **{p['coverage']:.1f}** — {p['coverage_note']}")
    A(f"- {pc['note']}")
    A("")

    # ---- 6 ---------------------------------------------------------------- #
    A("## 6. The §4.5 sign check (E4 autopsy taxonomy, unchanged)")
    A("")
    s = v["sign_check"]
    A(f"- over the **{s['n_pickchg']}** positions where the arbiter changes the champion's "
      f"pick in at least one fold: {s['n_agree']}/{s['n_nonzero']} = "
      f"**{_f(s['agreement_rate'],3)}** with `arb[p] > 0`, exact two-sided binomial "
      f"**p {s['binomial_p_two_sided']:.3g}**")
    A(f"- aggregate sign (pooled headline `mean(arb)` = {_f(s['aggregate_mean_pooled'])}): "
      f"**{s['aggregate_sign']:+d}** · per-position majority sign "
      f"{s['per_position_majority_sign']:+d} · mean over the pick-change positions "
      f"{_f(s['mean_over_pickchg_positions'])}")
    A(f"- **{s['corroboration']}**")
    A(f"- benchmarks: {s['benchmarks']}")
    A(f"- {s['note']}")
    A("")

    # ---- 7 ---------------------------------------------------------------- #
    A("## 7. The §4.3 bound chain — pts and elo, with the ±1.6× bracket")
    A("")
    A("| term | pts/tied tile ply (×1.40 full-set) | 95% CI | elo (÷3.2) | elo 95% CI | "
      "elo (÷5.23 low-end) |")
    A("|---|---|---|---|---|---|")
    for nm in ("arb", "ora"):
        b = v["bounds"].get(nm)
        if not b:
            continue
        A(f"| `{nm}` | {_f(b['pts_per_tied_tile_ply']['point'])} | "
          f"[{_f(b['pts_per_tied_tile_ply']['ci95_lo'])}, "
          f"{_f(b['pts_per_tied_tile_ply']['ci95_hi'])}] | "
          f"{_f(b['elo']['point'],2)} | [{_f(b['elo']['ci95_lo'],2)}, "
          f"{_f(b['elo']['ci95_hi'],2)}] | "
          f"{_f(b['elo_low_end_divisor_5.23']['point'],2)} |")
    A("")
    ba = v["bounds"].get("arb")
    if ba:
        A("**σ_game sensitivity** on `arb`'s CI-hi: "
          + " · ".join(f"σ={k} → {_f(x,2)} elo"
                       for k, x in ba["elo_sigma_sensitivity"].items())
          + ". elo scales as 1/σ_game, so the SMALLER σ is the larger, "
            "conservative-against-closure bound.")
        A("")
    A(f"⚠️ {v['bounds']['note']}")
    A("")

    # ---- 8 ---------------------------------------------------------------- #
    A("## 8. Realized `n`, roots and composition of what completed")
    A("")
    A(f"- planned positions in the corpus: **{c['planned_positions']}** · analysed: "
      f"**{c['n_analysed']}** over {c['n_roots']} roots")
    A(f"- HOLDOUT: **{c['n_holdout']} / 211** = **{100.0*c['holdout_completion_frac']:.1f}%** "
      f"of the planned holdout finished · DEV: **{c['n_dev']}**")
    A(f"- excluded and counted: {c['excluded']} "
      f"(`G-ARMSET` mismatch fraction {_f(c['armset_mismatch_frac'],4)}; "
      f"{c['armset_frac_note']})")
    A("")
    A("| slice | n | roots | stratum | profile | phase | capped |")
    A("|---|---|---|---|---|---|---|")
    for sl, d in v["completion"]["composition"].items():
        A(f"| {sl} | {d['n']} | {d['n_roots']} | {d['by_stratum']} | {d['by_profile']} | "
          f"{d['by_phase']} | {d['capped']} |")
    A("")

    # ---- 9 ---------------------------------------------------------------- #
    A("## 9. Cost and the process census")
    A("")
    cf = v["cost_from_records"]
    A(f"- realized `c_tier1` on the holdout legs (from the records' own `elapsed_secs`): "
      f"**{_f(cf['c_tier1_worker_s_per_playout'],4)}** worker-s/playout "
      f"({cf['legs']} legs, {cf['playouts']} playouts, Σ {_f(cf['sum_elapsed_secs'],1)} s)")
    cb = v["cost"]
    A(f"- from `RUN_MANIFEST_chunk*.json`: "
      f"{_f(cb['c_tier1_worker_s_per_playout'],4)} worker-s/playout "
      f"(source {cb['source']})")
    A(f"- co-tenant found by the process census: **{cb['co_tenant'] or 'none recorded'}** "
      f"— DESIGN §7.8: no value depends on wall-clock.")
    A("")

    # ---- 10 --------------------------------------------------------------- #
    A("## 10. Every §3 gate and every DESIGN §6 integrity counter")
    A("")
    A("| precondition | result |")
    A("|---|---|")
    for k, ok in v["preconditions"].items():
        A(f"| `{k}` | {'PASS' if ok else '**FAIL**'} |")
    A("")
    A("**Per-judge `analyze_tiletie` §2.1 witnesses:**")
    A("")
    for j, blk in v["integrity"]["per_judge"].items():
        A(f"- `{j}`: " + " · ".join(f"{k} {val}" for k, val in sorted(blk.items())))
    A("")
    cr = v["integrity"]["cross_judge_G_CRN"]
    A("**Cross-judge CRN witness (`G-CRN`)** — the ARB record's `world_seeds` / "
      "`playout_seeds` must be **bit-identical** to the `clair-puct` record for the same "
      "rid+leg, and `pick_a`/`pick_b` must match:")
    A("")
    for k in ("compared_legs", "crn_cross_mismatch", "seed_cross_mismatch",
              "arm_cross_mismatch"):
        A(f"- `{k}`: **{cr[k]}**")
    if cr["examples"]:
        A(f"- ⚠️ examples: {cr['examples']}")
    A("")
    A(f"- `G-REPRO` (the 43/43 bit-reproduction of the OOF pilot records, a PRE-LAUNCH "
      f"abort): **{v['cost']['g_repro'] if v['cost']['g_repro'] is not None else 'not recorded in PILOT.json'}**")
    A(f"- `G-LEAF` (harness leaf hash `a36d2e15a3b3d71d`) is likewise a pre-launch abort, "
      f"witnessed by `GATE_BACKEND_RECHECK_*.json`, not by this analyser.")
    A("")

    # ---- 11 --------------------------------------------------------------- #
    A("## 11. Realized resolution and the `n` that would resolve `F_fixed`")
    A("")
    r = v["resolution"]
    A(f"- realized per-position sd of `arb` = {_f(r['sd_positions_arb'])} pts "
      f"(DESIGN §4.4 projected 1.74–3.09)")
    A(f"- realized **2σ resolution = {_f(r['two_sigma_pts'])} pts** = "
      f"{_f(r['two_sigma_elo'],2)} elo = **{_f(r['two_sigma_in_F_fixed_units'],3)}** in "
      f"`F_fixed` units")
    A(f"- `n` that would resolve `F_fixed` to ±0.35 at the realized dispersion: "
      f"**≈ {('%.0f' % r['n_for_F_fixed_pm_0.35']) if r.get('n_for_F_fixed_pm_0.35') else 'n/a'}** "
      f"positions, against a total deduped supply of **733**")
    A(f"- {r['note']}")
    A("")

    # ---- 12 --------------------------------------------------------------- #
    A("## 12. Cuts — emitted beside the pooled read, ⚠️ UNDERPOWERED, NEVER adjudicated on")
    A("")
    A("| cut | n | roots | `arb` | z | `ora` | z | `F` | `F_fixed` |")
    A("|---|---|---|---|---|---|---|---|---|")
    for nm, d in v["cuts_never_adjudicated"].items():
        A(f"| {nm} | {d['n']} | {d['n_roots']} | {_f(d['arb'])} | {_f(d['z_arb'],2)} | "
          f"{_f(d['ora'])} | {_f(d['z_ora'],2)} | {_f(d['F_point'],3)} | "
          f"{_f(d['F_fixed_point'],3)} |")
    A("")
    A("Per-stratum / per-profile / per-phase / capped reads are **underpowered on their "
      "own and are labelled as such**; **no branch is ever adjudicated on a cut** "
      "(DESIGN §4.3). The 94% `walled` self-play / 6% E4 rules-epoch confound of pricing "
      "§6.6 is inherited unchanged.")
    A("")

    # ---- governance ------------------------------------------------------- #
    A("## Governance")
    A("")
    A(v["governance"])
    A("")
    A("**DESIGN §7.1, which travels with every number above:** the arbiter and the pricing "
      "judge are *both terminal-grounded*. A positive here is evidence that terminal "
      "grounding at ties is worth points **as measured by a terminal-grounded ruler** — it "
      "is **NOT yet evidence of deploy elo**. DESIGN §7.2: positions were selected on a "
      "*leaf* property, so regression to the mean cuts **toward the null** — a positive read "
      "is conservative.")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    args = parse_args(argv)
    v = build_readout(args)
    rows = v.pop("_rows")
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "READOUT.json").write_text(json.dumps(v, indent=1, default=str))
    (out / "READOUT.md").write_text(render(v))
    (out / "per_position.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows))
    print(render(v))
    print(f"\n[wrote] {out/'READOUT.json'}\n[wrote] {out/'READOUT.md'}\n"
          f"[wrote] {out/'per_position.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
