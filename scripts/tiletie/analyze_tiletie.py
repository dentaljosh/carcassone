#!/usr/bin/env python3
"""READ-OUT for the tile-tie pricing run -- the PRE-REGISTERED DESIGN.md §4 estimators.

    measurement/tiletie_pricing_20260812/DESIGN.md

This file implements exactly what §4 pre-registered and NOTHING ELSE. Every estimator
below is named with its DESIGN section; where DESIGN was ambiguous the choice is recorded
in `INTERPRETATIONS` and echoed into the verdict artifact rather than silently taken.

Sign convention: `V[p,a,j]` = terminal margin in FINAL-SCORE POINTS, root player's seat,
at position `p`, arm `a`, CRN world `j`. Higher = better for the side to move. Arm 0 is
the leaf's own tie-break of record (lowest action index in the exact-tie set).

The statistics (DESIGN §4):

  S1a  sigma2_arm[p] = (MS_arm[p] - MS_resid[p]) / M          -- PRIMARY (§4.6: cap-invariant)
  S1b  cross-fit best-minus-worst gap G[p]                    -- interpretable spread
  S2   headroom[p] = -R[p], R = mean_odd V[champ] - mean_odd V[a+]
  S2b  the same with arm 0 in place of the champion           -- greedy-leaf companion

All four are unbiased-under-the-null. Naive (non-cross-fit) companions are computed and
PRINTED so the size of the winner's-curse correction is auditable; DESIGN §4.2 forbids
quoting them as results and this file labels them `never_quote: true`.

Everything clusters on `root_id` (DESIGN §4.4): cluster-robust sandwich se + a
root-resampling bootstrap, 20,000 reps, seed 20260812.

    analyze_tiletie.py --records-root /mnt/c/carc-shared/tiletie_pricing_20260812/clair-puct \
                       --plan-dir measurement/tiletie_pricing_20260812/positions_stageA \
                       --out-dir  measurement/tiletie_pricing_20260812/readout
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------- #
# PRE-REGISTERED CONSTANTS -- every one carries its DESIGN.md section.          #
# Nothing here may be tuned after seeing a number.                              #
# --------------------------------------------------------------------------- #
CAP_J = 4                       # §4.6 -- the adopted cap
FULLSET_EXTRAP = 1.40           # §4.6 -- E[max of K]/E[max of J]: a_8.55/a_4 = 1.44/1.03
ORDER_STAT_A = {"2": 0.56, "4": 1.03, "8.55": 1.44}   # §4.6, the extrapolation's provenance

TIED_TILE_PLIES_PER_GAME = 22.96   # §7.2 -- MEASURED by the census (597 tied plies / 26 games)
NON_ADDITIVITY = 3.2               # §4.3 -- n=1, calibrated at the TOP of the budget ladder
NON_ADDITIVITY_LOW_END = 5.23      # §4.3 -- the memo's range-consistent low-end divisor
SIGMA_GAME_FIXED_V1 = 20.4         # §4.3 -- headline
SIGMA_GAME_WALLED = 22.2           # §4.3 -- reported as a sensitivity
NORMAL_PDF0 = 0.3989422804014327
KELO_REFERENCE = 97.5              # §7.2 -- elo per pt per tied tile ply (linearised check)

ELO_CLOSE_BAR = 17.0            # §4.4 -- +-17 elo ~ 1sigma at n=400
ELO_REOPEN_BAR = 35.0           # §4.4 -- the 2sigma re-open bar
Z_CONVICTION = 2.0              # §4.4 read-rule -- |z| < 2 is no conviction

BOOTSTRAP_REPS = 20000          # §4.4
BOOTSTRAP_SEED = 20260812       # §4.4

DESIGN_DOC = "measurement/tiletie_pricing_20260812/DESIGN.md"
SCHEMA = "carcassonne-tiletie-readout/v1"

# --------------------------------------------------------------------------- #
# WHERE DESIGN WAS AMBIGUOUS. These are surfaced in VERDICT.json/.md verbatim.  #
# --------------------------------------------------------------------------- #
INTERPRETATIONS = [
    {
        "id": "I1-parity-base",
        "where": "§4.1 'even j = SELECTION half, odd j = EVALUATION half'",
        "ambiguity": (
            "§4 notation declares worlds j = 1..M (ONE-based), so 'even j' is read as the "
            "one-based even labels, i.e. ZERO-based indices 1,3,5,... Nothing in DESIGN "
            "restates the base at the split."
        ),
        "resolution": (
            "Implemented one-based-literal (default --parity-base 1). The choice cannot "
            "change validity -- both halves are exchangeable and E[G]=E[R]=0 under the null "
            "either way -- only the realized draw. The swapped split is computed and "
            "reported as `parity_swap` so the reader can see it is not a lever."
        ),
    },
    {
        "id": "I2-zero-addback-weighting",
        "where": "§0.A / §6 'the analyser MUST add them back as exact zeros'",
        "ambiguity": (
            "DROPPED_ALL_TRANSPOSITION.json holds 374 rows over the FULL 1,427-position "
            "supply, but Stage A scores a 340-position SAMPLE of the 1,053 built. Literally "
            "concatenating 374 zero rows onto 340 scored rows would mis-weight the mixture "
            "by ~3x."
        ),
        "resolution": (
            "The zeros enter as their POPULATION SHARE, per stratum, not as literal rows: "
            "mean over (discriminable + analytic zeros) = (1 - p_drop) * mean(discriminable) "
            "exactly, because the zeros have zero value AND zero variance and their count is "
            "known. Applied as a per-position multiplier inside the bootstrap, so the CI "
            "scales exactly too. This reproduces DESIGN §6's own "
            "`headroom_all = 0.74 * headroom_discriminable`."
        ),
    },
    {
        "id": "I3-the-72-outside-tieset",
        "where": "§0.A '72 of the 374 have the played action OUTSIDE the tie set'",
        "ambiguity": (
            "For those rows the analytic zero covers the TIE-SET ARMS only, so it is a valid "
            "zero for the spread statistics and for S2b (arm 0 is inside the set) but NOT "
            "necessarily for S2 (champion vs tie set)."
        ),
        "resolution": (
            "Two zero-rates are carried. Spread (S1a/S1b) and S2b use ALL 374 rows as zeros. "
            "S2 (headroom) reports a headline using all 374 AND a per-row sensitivity "
            "`zeros_strict` that counts only the 302 rows whose played action is inside the "
            "tie set, leaving the 72 imputed at the discriminable mean. `zeros_strict` is the "
            "LARGER magnitude, i.e. the conservative-against-closure direction. It is a "
            "sensitivity row, never the headline."
        ),
    },
    {
        "id": "I4-branch-3-unreachable",
        "where": "§4.4 'branch precedence 1 -> 2 -> 3 -> 4, first match wins'",
        "ambiguity": (
            "Branch 3's condition is `sigma2_arm CI excludes 0 AND elo(headroom_CI_hi) < +17`. "
            "Its second conjunct IS branch 1's whole condition, so under strict first-match "
            "precedence branch 3 can NEVER fire. This is an internal inconsistency in the "
            "pre-registration, not a judgement call."
        ),
        "resolution": (
            "Precedence is honoured EXACTLY as written (branch 1 fires), and the verdict "
            "additionally carries `branch_3_condition_also_met` plus this note. The reader "
            "gets both the literal pre-registered branch and the fact that the more specific "
            "reading ('the leaf is blind but the search is not') also holds. No silent "
            "re-ordering."
        ),
    },
    {
        "id": "I5-pooled-weighting",
        "where": "§4.4 'the pooled estimate is primary'",
        "ambiguity": (
            "DESIGN does not say whether 'pooled' is position-weighted over the SAMPLE or "
            "re-weighted to the population. Stage A's sample (280 selfplay / 60 e4) is "
            "deliberately NOT proportional to supply (932 / 495)."
        ),
        "resolution": (
            "Pooled = the unweighted mean over all scored positions (the farm-war reading, "
            "and what 'pooled' means everywhere else in this project). Per-stratum reads are "
            "always emitted beside it, and §4.4's no-pooling-on-sign-disagreement rule is "
            "enforced mechanically."
        ),
    },
    {
        "id": "I6-fullset-extrapolation-scope",
        "where": "§4.6 'the full-set ceiling is ~= 1.40x the J=4 measured headroom'",
        "ambiguity": (
            "The 1.40x is derived from mean K = 8.55 vs J = 4, but is stated as a GLOBAL "
            "multiplier. Positions that were never capped (K <= 4) need no extrapolation at "
            "all -- best-of-J IS best-of-K there."
        ),
        "resolution": (
            "Applied GLOBALLY exactly as written (so the cap cannot manufacture a closure), "
            "and the realized capped fraction is reported beside it so the reader can see how "
            "conservative that is. §4.6's own assumption-free check -- branch arithmetic on "
            "the UNCAPPED subset alone -- is emitted as a separate block."
        ),
    },
]


# --------------------------------------------------------------------------- #
# small numerics                                                                #
# --------------------------------------------------------------------------- #
def _now_utc():
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def _var(xs, ddof=1):
    xs = list(xs)
    n = len(xs)
    if n - ddof <= 0:
        return float("nan")
    mu = _mean(xs)
    return sum((x - mu) ** 2 for x in xs) / (n - ddof)


def _sd(xs, ddof=1):
    v = _var(xs, ddof)
    return math.sqrt(v) if v == v and v >= 0 else float("nan")


# --------------------------------------------------------------------------- #
# DESIGN §4.1 S1a -- variance components on the arms x worlds layout            #
# --------------------------------------------------------------------------- #
def variance_components(matrix):
    """Two-way layout without replication, blocked on the CRN world (DESIGN §4.1).

    `matrix` is A x M: rows are arms (row 0 = the leaf's tie-break of record), columns
    are CRN worlds. Returns MS_arm, MS_resid and

        sigma2_arm = (MS_arm - MS_resid) / M          [pts^2]

    whose expectation is EXACTLY 0 under the null that all arms are equal in value.
    The SIGNED value is kept, negatives included -- truncating at 0 would reintroduce
    precisely the upward bias the estimator exists to remove (§4.1).
    """
    a = len(matrix)
    if a < 2:
        raise ValueError("variance_components needs >= 2 arms")
    m = len(matrix[0])
    if m < 2:
        raise ValueError("variance_components needs >= 2 worlds")
    if any(len(r) != m for r in matrix):
        raise ValueError("ragged arms x worlds matrix")

    row_means = [_mean(r) for r in matrix]
    col_means = [_mean(matrix[i][j] for i in range(a)) for j in range(m)]
    grand = _mean(x for r in matrix for x in r)

    ms_arm = m * sum((rm - grand) ** 2 for rm in row_means) / (a - 1)
    ss_resid = 0.0
    for i in range(a):
        for j in range(m):
            e = matrix[i][j] - row_means[i] - col_means[j] + grand
            ss_resid += e * e
    ms_resid = ss_resid / ((a - 1) * (m - 1))
    return {
        "n_arms": a,
        "m": m,
        "ms_arm": ms_arm,
        "ms_resid": ms_resid,
        "sigma2_arm": (ms_arm - ms_resid) / m,
    }


# --------------------------------------------------------------------------- #
# DESIGN §4.1/§4.2 -- the parity cross-fit                                      #
# --------------------------------------------------------------------------- #
def parity_indices(m, base=1, swap=False):
    """§4.1: 'even j = SELECTION half, odd j = EVALUATION half'.

    §4 declares j = 1..M, so `base=1` reads the parity off the ONE-based label
    (zero-based indices 1,3,5,... select). See INTERPRETATIONS I1. `base=0` reads it
    off the zero-based index; `swap` exchanges the two halves. Validity is identical
    under all four -- only the realized draw differs.
    """
    sel = [j for j in range(m) if (j + base) % 2 == 0]
    eva = [j for j in range(m) if (j + base) % 2 == 1]
    if swap:
        sel, eva = eva, sel
    return sel, eva


def _sub_mean(row, idx):
    return sum(row[j] for j in idx) / len(idx)


def crossfit_gap(matrix, sel, eva):
    """S1b (§4.1) -- cross-fit best-minus-worst gap.

    a+ / a- are chosen on the SELECTION worlds, scored on the disjoint EVALUATION
    worlds. E[G] = 0 under the null; otherwise E[G] <= the true range, i.e. G is a
    DOWNWARD-BIASED estimate of the true range and an UNBIASED test of the null --
    that sentence travels with every quotation of it (§4.1).
    """
    sel_means = [_sub_mean(r, sel) for r in matrix]
    a_plus = max(range(len(matrix)), key=lambda i: (sel_means[i], -i))
    a_minus = min(range(len(matrix)), key=lambda i: (sel_means[i], i))
    return _sub_mean(matrix[a_plus], eva) - _sub_mean(matrix[a_minus], eva), a_plus, a_minus


def crossfit_regret(matrix, sel, eva, comparator):
    """S2 (§4.2) -- regret of `comparator` against the cross-fit-selected best arm.

        R = mean_eva V[comparator] - mean_eva V[a+]       (<= 0 means the search missed)
        headroom = -R                                     [pts per tied tile ply]

    a+ is selected on the SELECTION worlds from a pool that INCLUDES `comparator`,
    which is what makes E[R] = 0 exactly under the null (§4.2).
    """
    sel_means = [_sub_mean(r, sel) for r in matrix]
    a_plus = max(range(len(matrix)), key=lambda i: (sel_means[i], -i))
    r = _sub_mean(matrix[comparator], eva) - _sub_mean(matrix[a_plus], eva)
    return -r, a_plus


def naive_gap(matrix):
    """§4.2: computed and printed for audit of the winner's-curse size. NEVER quoted.

    This is exactly the range statistic §4.1 declares INADMISSIBLE as a headline
    (biased ~0.8 sigma positive under the null even at K=2)."""
    means = [_mean(r) for r in matrix]
    return max(means) - min(means)


def naive_regret(matrix, comparator):
    """§4.2 naive companion of S2 -- selection and evaluation on the SAME worlds.
    Computed for audit only. NEVER quoted."""
    means = [_mean(r) for r in matrix]
    a_plus = max(range(len(matrix)), key=lambda i: (means[i], -i))
    return -(means[comparator] - means[a_plus])


# --------------------------------------------------------------------------- #
# DESIGN §4.3 -- the bound chain (identical arithmetic to the budget-headroom memo) #
# --------------------------------------------------------------------------- #
def pts_to_elo(pts_per_tied_ply, sigma_game=SIGMA_GAME_FIXED_V1,
               non_additivity=NON_ADDITIVITY, plies=TIED_TILE_PLIES_PER_GAME):
    """§4.3, verbatim:

        pts_game = headroom * tied_tile_plies_per_game / NON_ADDITIVITY
        wr       = 0.5 + (pts_game / SIGMA_GAME) * phi(0)
        elo      = 400 * log10(wr / (1 - wr))

    ⚠️ Every §4.3 caveat is inherited: NON_ADDITIVITY = 3.2 is n = 1, calibrated at the
    TOP of the ladder; a range-consistent low-end divisor is ~5.23; the divisor enters
    LINEARLY, so any bound through this chain is quoted with a ~1.6x bracket, not as a
    point. The linear-phi step degrades above ~1 sigma.
    """
    pts_game = pts_per_tied_ply * plies / non_additivity
    wr = 0.5 + (pts_game / sigma_game) * NORMAL_PDF0
    wr = min(max(wr, 1e-9), 1 - 1e-9)
    return 400.0 * math.log10(wr / (1.0 - wr))


def elo_to_pts(elo, sigma_game=SIGMA_GAME_FIXED_V1,
               non_additivity=NON_ADDITIVITY, plies=TIED_TILE_PLIES_PER_GAME):
    """Inverse of `pts_to_elo` -- used for the §4.4 branch-4 sizing statement."""
    ratio = 10.0 ** (elo / 400.0)
    wr = ratio / (1.0 + ratio)
    pts_game = (wr - 0.5) * sigma_game / NORMAL_PDF0
    return pts_game * non_additivity / plies


# --------------------------------------------------------------------------- #
# clustering (DESIGN §4.4 -- everything clusters on root_id)                     #
# --------------------------------------------------------------------------- #
def cluster_robust(values, roots):
    """Sandwich se for the MEAN, clustered on root, with the G/(G-1) finite-cluster
    correction (the house estimator, `analyze_kwidth_oracle.cluster_robust`)."""
    n = len(values)
    if n == 0:
        return float("nan"), float("nan"), 0, 0
    ybar = _mean(values)
    by_root = defaultdict(float)
    for v, r in zip(values, roots):
        by_root[r] += v - ybar
    g = len(by_root)
    meat = sum(s * s for s in by_root.values())
    var = (meat / (n ** 2)) * (g / (g - 1)) if g > 1 else float("nan")
    return ybar, (math.sqrt(var) if var == var and var >= 0 else float("nan")), n, g


def bootstrap_roots(values, roots, n_boot=BOOTSTRAP_REPS, seed=BOOTSTRAP_SEED,
                    chunk=2000):
    """§4.4: resample ROOTS with replacement, 20,000 reps, seed 20260812.

    The record-weighted mean is recomputed inside each resample as
    sum(values)/count, so roots contributing several positions carry their weight --
    the same convention as `analyze_kwidth_oracle.bootstrap_roots`'s `rec_means`.
    Returns (boot_mean, lo95, hi95, se_boot, frac_le_0).
    """
    if not values:
        nan = float("nan")
        return nan, nan, nan, nan, nan
    sums = defaultdict(float)
    cnts = defaultdict(int)
    for v, r in zip(values, roots):
        sums[r] += v
        cnts[r] += 1
    keys = sorted(sums)
    g = len(keys)
    if g < 2:
        nan = float("nan")
        return _mean(values), nan, nan, nan, nan
    s_arr = np.array([sums[k] for k in keys], dtype=np.float64)
    c_arr = np.array([cnts[k] for k in keys], dtype=np.float64)
    rng = np.random.default_rng(seed)
    out = np.empty(n_boot, dtype=np.float64)
    done = 0
    while done < n_boot:
        b = min(chunk, n_boot - done)
        idx = rng.integers(0, g, size=(b, g))
        out[done:done + b] = s_arr[idx].sum(axis=1) / c_arr[idx].sum(axis=1)
        done += b
    out.sort()
    lo = float(out[int(0.025 * n_boot)])
    hi = float(out[min(n_boot - 1, int(0.975 * n_boot))])
    return (float(out.mean()), lo, hi, float(out.std(ddof=1)),
            float((out <= 0).sum()) / n_boot)


def aggregate(rows, key, scale_key=None, n_boot=BOOTSTRAP_REPS, seed=BOOTSTRAP_SEED):
    """Point estimate + cluster-robust se + root bootstrap CI for one statistic.

    `scale_key`, when given, is a per-position multiplier applied BEFORE aggregation.
    That is how the analytic zeros of §0.A enter (INTERPRETATIONS I2): the mean over
    (discriminable + known-count zeros) equals (1 - p_drop) * mean(discriminable)
    exactly, and multiplying each position's value by its stratum's (1 - p_drop)
    reproduces that identity while letting the bootstrap propagate the CI exactly.
    """
    use = [r for r in rows if r.get(key) is not None and r[key] == r[key]]
    if not use:
        return {"n": 0, "n_roots": 0, "mean": None, "se_cluster": None,
                "boot_lo": None, "boot_hi": None, "se_boot": None,
                "z": None, "sd_positions": None, "frac_boot_le_0": None}
    vals = [r[key] * (r[scale_key] if scale_key else 1.0) for r in use]
    roots = [r["root_id"] for r in use]
    mean, se_cr, n, g = cluster_robust(vals, roots)
    bmean, lo, hi, se_boot, frac = bootstrap_roots(vals, roots, n_boot, seed)
    z = mean / se_cr if se_cr and se_cr == se_cr and se_cr > 0 else float("nan")
    return {
        "n": n, "n_roots": g, "mean": mean, "se_cluster": se_cr,
        "boot_mean": bmean, "boot_lo": lo, "boot_hi": hi, "se_boot": se_boot,
        "z": z, "sd_positions": _sd(vals), "frac_boot_le_0": frac,
    }


# --------------------------------------------------------------------------- #
# LOADING                                                                       #
# --------------------------------------------------------------------------- #
def _load_json(p):
    with open(p) as fh:
        return json.load(fh)


def load_plan(plan_dir):
    """POSITIONS_PLAN.json + ARMS.json + DROPPED_ALL_TRANSPOSITION.json."""
    plan_dir = Path(plan_dir)
    plan = _load_json(plan_dir / "POSITIONS_PLAN.json")
    arms = _load_json(plan_dir / "ARMS.json")
    dropped = _load_json(plan_dir / "DROPPED_ALL_TRANSPOSITION.json")
    ded = plan.get("afterstate_dedupe") or {}
    if not ded.get("applied"):
        raise SystemExit(
            f"REFUSING: {plan_dir}/POSITIONS_PLAN.json was built without the §0.A "
            "afterstate dedupe; the analytic-zero population is undefined for it.")
    return {"dir": str(plan_dir), "plan": plan, "arms": arms, "dropped": dropped}


_LEG_RE = re.compile(r"^leg(\d+)$")


def discover_records(records_root, only_profiles=None):
    """Walk <root>/<profile>/leg<r>/records/*.json -> {rid: {leg: record}} + an index."""
    records_root = Path(records_root)
    by_rid = defaultdict(dict)
    present = defaultdict(int)
    not_ok = []
    if not records_root.is_dir():
        raise SystemExit(f"REFUSING: records root does not exist: {records_root}")
    for prof in sorted(os.listdir(records_root)):
        if only_profiles and prof not in only_profiles:
            continue
        pdir = records_root / prof
        if not pdir.is_dir():
            continue
        for legname in sorted(os.listdir(pdir)):
            mm = _LEG_RE.match(legname)
            if not mm:
                continue
            leg = int(mm.group(1))
            rdir = pdir / legname / "records"
            if not rdir.is_dir():
                continue
            for f in sorted(glob.glob(str(rdir / "*.json"))):
                rec = _load_json(f)
                rid = rec["rid"]
                if leg in by_rid[rid]:
                    raise SystemExit(f"REFUSING: duplicate record for {rid} leg{leg}")
                by_rid[rid][leg] = rec
                present[f"{prof}/leg{leg}"] += 1
                if not rec.get("ok", False):
                    not_ok.append({"rid": rid, "leg": leg, "profile": prof})
    return dict(by_rid), dict(present), not_ok


def zero_rates(plan_bundle, full_supply_plan_path=None):
    """The population share of ANALYTIC-ZERO (all-transposition) positions, per stratum.

    DESIGN §0.A/§6: the 374 dropped positions are exact zeros with zero variance, and
    the analyser MUST put them back. They enter as a population SHARE (INTERPRETATIONS
    I2), so the rate needs the FULL-SUPPLY built counts, not Stage A's sample counts.

    Returns per-stratum {p_all, p_strict, scale_all, scale_strict, ...} plus the
    provenance of the counts, which is stated loudly when it had to fall back.
    """
    ded = plan_bundle["plan"]["afterstate_dedupe"]
    dropped_rows = plan_bundle["dropped"]["rows"]
    n_dropped = defaultdict(int)
    n_dropped_inside = defaultdict(int)
    for r in dropped_rows:
        n_dropped[r["stratum"]] += 1
        if not r.get("action_played_outside_tieset"):
            n_dropped_inside[r["stratum"]] += 1

    built = None
    source = None
    if full_supply_plan_path is None:
        guess = Path(plan_bundle["dir"]).parent / "positions" / "POSITIONS_PLAN.json"
        if guess.is_file():
            full_supply_plan_path = guess
    if full_supply_plan_path and Path(full_supply_plan_path).is_file():
        fp = _load_json(full_supply_plan_path)
        cand = fp.get("counts_by_stratum")
        # only trust it if it is the FULL supply, i.e. built + dropped == qualifying
        if cand and sum(cand.values()) + sum(n_dropped.values()) == ded.get(
                "n_qualifying_before_drop"):
            built = dict(cand)
            source = (f"per-stratum, from the full-supply plan "
                      f"{Path(full_supply_plan_path).as_posix()} + the dropped index")
    if built is None:
        # POOLED FALLBACK -- loudly labelled, applied uniformly to every stratum.
        source = ("POOLED FALLBACK: full-supply per-stratum built counts unavailable, so "
                  "the single pooled drop rate n_dropped/n_qualifying is applied to every "
                  "stratum. Per-stratum rates differ (e4 ~23%, selfplay ~28%) so this is "
                  "an approximation -- state it with any number derived from it.")
        q = ded["n_qualifying_before_drop"]
        d = ded["n_dropped_all_transposition"]
        inside = d - ded.get("n_dropped_with_action_played_outside_tieset", 0)
        pooled = {"p_all": d / q, "p_strict": inside / q}
        strata = sorted(set(r["stratum"] for r in dropped_rows))
        out = {s: dict(pooled, n_dropped=n_dropped[s],
                       n_dropped_inside_tieset=n_dropped_inside[s],
                       n_built=None, n_qualifying=None) for s in strata}
    else:
        out = {}
        for s, nb in built.items():
            q = nb + n_dropped[s]
            out[s] = {
                "n_built": nb, "n_dropped": n_dropped[s],
                "n_dropped_inside_tieset": n_dropped_inside[s],
                "n_qualifying": q,
                # p_all      -- every dropped position counts as an analytic zero
                # p_strict   -- ONLY the rows whose PLAYED action is inside the tie set,
                #               i.e. the rows for which the zero is valid for S2 as well
                #               (INTERPRETATIONS I3)
                "p_all": n_dropped[s] / q,
                "p_strict": n_dropped_inside[s] / q,
            }
    for s, d in out.items():
        d["scale_all"] = 1.0 - d["p_all"]
        d["scale_strict"] = 1.0 - d["p_strict"]
    return {"by_stratum": out, "source": source}


# --------------------------------------------------------------------------- #
# ASSEMBLY: records -> per-position statistics                                   #
# --------------------------------------------------------------------------- #
def build_positions(plan_bundle, by_rid, rates, parity_base=1,
                    include_partial_arms=False, only_strata=None):
    """Assemble the A x M matrix per position and evaluate every §4 statistic on it.

    Integrity (DESIGN §2.1): the reference arm is re-scored in EVERY leg under identical
    (world, playout) seeds, so `values_a` MUST be bit-identical across all legs of a
    position. Any drift means the harness is not deterministic and the run is void.
    """
    arms_index = plan_bundle["arms"]
    rows = []
    integrity = {"values_a_drift": [], "seed_drift": [], "crn_unverified": [],
                 "checksum_failed": [], "arm_index_mismatch": [],
                 "zero_distinct_afterstates": []}
    completion = {"planned_positions": 0, "scored_complete": 0, "scored_partial": 0,
                  "absent": 0, "by_stratum": defaultdict(lambda: defaultdict(int)),
                  "by_profile": defaultdict(lambda: defaultdict(int)),
                  "partial_rids": [], "absent_rids": []}

    for rid, meta in sorted(arms_index.items()):
        stratum = meta["stratum"]
        profile = meta["rules_profile"]
        if only_strata and stratum not in only_strata:
            continue
        n_arms = len(meta["arms"])
        need = list(range(1, n_arms))            # leg r scores arms[0] vs arms[r]
        completion["planned_positions"] += 1
        legs = by_rid.get(rid, {})
        have = sorted(k for k in legs if k in need)
        missing = [r for r in need if r not in legs]
        cs = completion["by_stratum"][stratum]
        cp = completion["by_profile"][profile]
        cs["planned"] += 1
        cp["planned"] += 1
        if not have:
            completion["absent"] += 1
            cs["absent"] += 1
            cp["absent"] += 1
            completion["absent_rids"].append(rid)
            continue
        if missing:
            completion["scored_partial"] += 1
            cs["partial"] += 1
            cp["partial"] += 1
            completion["partial_rids"].append(
                {"rid": rid, "have_legs": have, "missing_legs": missing})
            if not include_partial_arms:
                continue
        else:
            completion["scored_complete"] += 1
            cs["complete"] += 1
            cp["complete"] += 1

        # ---- integrity + matrix assembly -------------------------------------
        ref = legs[have[0]]
        m = ref["m"]
        va0 = ref["values_a"]
        for r in have:
            rec = legs[r]
            if rec["values_a"] != va0:
                integrity["values_a_drift"].append({"rid": rid, "leg": r})
            if (rec["world_seeds"] != ref["world_seeds"]
                    or rec["playout_seeds"] != ref["playout_seeds"]):
                integrity["seed_drift"].append({"rid": rid, "leg": r})
            if not rec.get("crn_verified"):
                integrity["crn_unverified"].append({"rid": rid, "leg": r})
            if rec.get("checksum_ok") is False:
                integrity["checksum_failed"].append({"rid": rid, "leg": r})
            if rec.get("pick_a") != meta["arms"][0] or rec.get("pick_b") != meta["arms"][r]:
                integrity["arm_index_mismatch"].append({"rid": rid, "leg": r})
            if rec.get("distinct_afterstates") == 0:
                integrity["zero_distinct_afterstates"].append({"rid": rid, "leg": r})

        arm_order = [0] + have                    # scored arm indices, arm 0 first
        matrix = [list(va0)] + [list(legs[r]["values_b"]) for r in have]

        vc = variance_components(matrix)
        sel, eva = parity_indices(m, base=parity_base)
        sel_s, eva_s = parity_indices(m, base=parity_base, swap=True)
        gap, a_plus_g, a_minus_g = crossfit_gap(matrix, sel, eva)
        gap_swap, _, _ = crossfit_gap(matrix, sel_s, eva_s)

        champ_idx = meta.get("champ_arm_index")
        champ_pos = arm_order.index(champ_idx) if champ_idx in arm_order else None
        head_champ = head_champ_swap = head_champ_naive = None
        if champ_pos is not None:
            head_champ, _ = crossfit_regret(matrix, sel, eva, champ_pos)
            head_champ_swap, _ = crossfit_regret(matrix, sel_s, eva_s, champ_pos)
            head_champ_naive = naive_regret(matrix, champ_pos)
        head_leaf, _ = crossfit_regret(matrix, sel, eva, 0)
        head_leaf_swap, _ = crossfit_regret(matrix, sel_s, eva_s, 0)

        sc = rates["by_stratum"].get(stratum, {"scale_all": 1.0, "scale_strict": 1.0})
        rows.append({
            "rid": rid, "root_id": meta["root_id"], "stratum": stratum,
            "rules_profile": profile, "phase_bucket": meta.get("phase_bucket"),
            "tercile": meta.get("tercile"), "capped": bool(meta.get("capped")),
            "tie_size_exact": meta.get("tie_size_exact"),
            "n_distinct_afterstates": meta.get("n_distinct_afterstates"),
            "champ_outside_tieset": bool(meta.get("champ_outside_tieset")),
            "ply": meta.get("ply"),
            "n_arms_planned": n_arms, "n_arms_scored": len(arm_order),
            "missing_legs": missing, "m": m,
            # --- S1a (PRIMARY) -------------------------------------------------
            "sigma2_arm": vc["sigma2_arm"], "ms_arm": vc["ms_arm"],
            "ms_resid": vc["ms_resid"],
            # --- S1b -----------------------------------------------------------
            "gap_G": gap, "gap_G_parity_swap": gap_swap, "gap_naive": naive_gap(matrix),
            "a_plus_gap": arm_order[a_plus_g], "a_minus_gap": arm_order[a_minus_g],
            # --- S2 / S2b ------------------------------------------------------
            "headroom_champ": head_champ, "headroom_champ_parity_swap": head_champ_swap,
            "headroom_champ_naive": head_champ_naive,
            "headroom_leaf": head_leaf, "headroom_leaf_parity_swap": head_leaf_swap,
            "headroom_leaf_naive": naive_regret(matrix, 0),
            "champ_scored": champ_pos is not None,
            # --- the §0.A analytic-zero weights (INTERPRETATIONS I2/I3) ---------
            "scale_all": sc["scale_all"], "scale_strict": sc["scale_strict"],
        })

    completion["by_stratum"] = {k: dict(v) for k, v in completion["by_stratum"].items()}
    completion["by_profile"] = {k: dict(v) for k, v in completion["by_profile"].items()}
    return rows, integrity, completion


# --------------------------------------------------------------------------- #
# DESIGN §4.4 -- the decision map                                               #
# --------------------------------------------------------------------------- #
BRANCH_TEXT = {
    1: ("CLOSED WITH A BOUND",
        "A perfect oracle tie-break over the leaf's exact-tie tile sets is worth less than "
        "+17 elo at deploy budget; the tie-break term axis is closed at the project's own "
        "1-sigma resolution. ⚠️ SCOPE (DESIGN §5): this closes 'spread visible to a deep "
        "clairvoyant search over THIS leaf', NOT 'spread in truth'. It does NOT license "
        "'ties don't matter', and it does not speak to near-tie (eps > 0) sets beyond §4.5."),
    2: ("HEADROOM IS REAL AND RESOLVED",
        "A hand-crafted tie-break term is warranted. Next step is NOT to build one blind: "
        "mine WHICH feature separates a+ from arm 0 inside the tied sets. ⚠️ CL-065 forbids "
        "the learned route; the term must be hand-crafted, and must then be shown to add "
        "value on top of an optimally-scaled leaf (CL-078)."),
    3: ("THE LEAF IS BLIND BUT THE SEARCH IS NOT",
        "11008 sims already recover the spread. Closes the DESKTOP term and opens the "
        "strictly narrower low-budget question (priors, the mobile k4x688 profile), where "
        "S2b is the relevant statistic. Does NOT license a desktop leaf change."),
    4: ("INCONCLUSIVE",
        "Report the estimate and its CI; promote nothing. The realized sd and the n required "
        "for a +-17-elo bound are stated below so the extension decision is arithmetic."),
}


def decide_branch(elo_hi, elo_lo, sigma2_lo, sigma2_hi, sigma2_se=None):
    """§4.4, precedence 1 -> 2 -> 3 -> 4, FIRST MATCH WINS -- implemented literally.

    ⚠️ See INTERPRETATIONS I4: branch 3's second conjunct IS branch 1's condition, so
    under strict precedence branch 3 is unreachable. We honour the precedence as written
    and report `branch_3_condition_also_met` separately.

    `sigma2_se` guards the degenerate case: a zero-width interval carries no inferential
    content, so an all-identical corpus must NOT be reported as 'the spread CI excludes 0'
    on float dust. A non-finite / non-positive se disqualifies the spread claim.
    """
    se_ok = (sigma2_se is None
             or (sigma2_se == sigma2_se and sigma2_se > 0))
    spread_excludes_zero = (se_ok and sigma2_lo is not None and sigma2_hi is not None
                            and (sigma2_lo > 0 or sigma2_hi < 0))
    b3 = bool(spread_excludes_zero and elo_hi is not None and elo_hi < ELO_CLOSE_BAR)
    if elo_hi is not None and elo_hi < ELO_CLOSE_BAR:
        return 1, b3, spread_excludes_zero
    if elo_lo is not None and elo_lo > ELO_CLOSE_BAR:
        return 2, b3, spread_excludes_zero
    if b3:
        return 3, b3, spread_excludes_zero
    return 4, b3, spread_excludes_zero


def bound_block(point, lo, hi, sigma_game, label):
    """The MANDATORY bound statement (§4.3/§4.4/§1): pts per tied tile ply AND elo,
    always with the +-1.6x NON_ADDITIVITY bracket. A null MUST ship this; the sentence
    'ties don't matter' is never an acceptable substitute."""
    def e(x, na=NON_ADDITIVITY):
        return None if x is None else pts_to_elo(x, sigma_game=sigma_game, non_additivity=na)
    return {
        "label": label,
        "sigma_game": sigma_game,
        "pts_per_tied_tile_ply": {"point": point, "ci95_lo": lo, "ci95_hi": hi},
        "elo": {"point": e(point), "ci95_lo": e(lo), "ci95_hi": e(hi)},
        "elo_low_end_divisor_5.23": {
            "point": e(point, NON_ADDITIVITY_LOW_END),
            "ci95_lo": e(lo, NON_ADDITIVITY_LOW_END),
            "ci95_hi": e(hi, NON_ADDITIVITY_LOW_END)},
        # §4.3: 'sigma 20.4 (fixed_v1), 22.2 (walled) reported as sensitivity'.
        # elo scales as 1/sigma_game, so the SMALLER sigma is the LARGER (conservative
        # against closure) bound.
        "elo_sigma_sensitivity": {
            str(s): (None if hi is None else
                     pts_to_elo(hi, sigma_game=s, non_additivity=NON_ADDITIVITY))
            for s in (SIGMA_GAME_FIXED_V1, SIGMA_GAME_WALLED)},
        "kelo_linear_check": KELO_REFERENCE,
        "caveat": ("§4.3 inherited verbatim: NON_ADDITIVITY = 3.2 is n = 1 and is calibrated "
                   "at the TOP of the budget ladder; the memo's range-consistent low-end "
                   "divisor is 5.23. The divisor enters LINEARLY, so this bound is quoted "
                   "with a ~1.6x bracket, never as a point. The linear-phi step degrades "
                   "above ~1 sigma."),
    }


# --------------------------------------------------------------------------- #
# THE READ-OUT                                                                  #
# --------------------------------------------------------------------------- #
def analyse(rows, rates, args, completion, integrity, plan_bundle):
    boot = (args.bootstrap, args.seed)

    def agg(rs, key, scale=None):
        return aggregate(rs, key, scale_key=scale, n_boot=boot[0], seed=boot[1])

    def subsets(rs):
        out = {"pooled": rs}
        for s in sorted(set(r["stratum"] for r in rs)):
            out[f"stratum:{s}"] = [r for r in rs if r["stratum"] == s]
        for p in sorted(set(r["rules_profile"] for r in rs)):
            out[f"profile:{p}"] = [r for r in rs if r["rules_profile"] == p]
        for ph in ("early", "mid", "late"):
            sub = [r for r in rs if r["phase_bucket"] == ph]
            if sub:
                out[f"phase:{ph}"] = sub
        unc = [r for r in rs if not r["capped"]]
        if unc:
            out["uncapped_only"] = unc
        cap = [r for r in rs if r["capped"]]
        if cap:
            out["capped_only"] = cap
        return out

    champ_rows = [r for r in rows if r["champ_scored"]]
    blocks = {}
    for name, rs in subsets(rows).items():
        crs = [r for r in rs if r["champ_scored"]]
        blocks[name] = {
            "n_positions": len(rs),
            "n_positions_with_champ_arm": len(crs),
            "n_roots": len(set(r["root_id"] for r in rs)),
            # ---- S1a PRIMARY -------------------------------------------------
            "S1a_sigma2_arm_discriminable": agg(rs, "sigma2_arm"),
            "S1a_sigma2_arm_all": agg(rs, "sigma2_arm", "scale_all"),
            # ---- S1b ---------------------------------------------------------
            "S1b_gap_discriminable": agg(rs, "gap_G"),
            "S1b_gap_all": agg(rs, "gap_G", "scale_all"),
            "S1b_gap_parity_swap": agg(rs, "gap_G_parity_swap"),
            # ---- S2 ----------------------------------------------------------
            "S2_headroom_J4_discriminable": agg(crs, "headroom_champ"),
            "S2_headroom_J4_all": agg(crs, "headroom_champ", "scale_all"),
            "S2_headroom_J4_all_zeros_strict": agg(crs, "headroom_champ", "scale_strict"),
            "S2_headroom_parity_swap": agg(crs, "headroom_champ_parity_swap"),
            # ---- S2b ---------------------------------------------------------
            "S2b_headroom_leaf_discriminable": agg(rs, "headroom_leaf"),
            "S2b_headroom_leaf_all": agg(rs, "headroom_leaf", "scale_all"),
            # ---- naive companions: AUDIT ONLY, never quoted (§4.2) ------------
            "NAIVE_never_quote": {
                "note": ("§4.1 declares the naive range INADMISSIBLE as a headline (biased "
                         "~+0.8 sigma under the null even at K=2); §4.2 allows it printed "
                         "ONLY so the winner's-curse correction is auditable."),
                "gap_naive": agg(rs, "gap_naive"),
                "headroom_champ_naive": agg(crs, "headroom_champ_naive"),
                "headroom_leaf_naive": agg(rs, "headroom_leaf_naive"),
            },
        }

    # ------------------------------------------------------------------ #
    # §4.6 the headline composite: measured J=4 -> full-set -> +zeros      #
    # ------------------------------------------------------------------ #
    sigma_game = args.sigma_game
    head = blocks["pooled"]["S2_headroom_J4_all"]

    def compose(a):
        if a["mean"] is None:
            return None
        return {k: (None if a[k] is None else a[k] * FULLSET_EXTRAP)
                for k in ("mean", "boot_lo", "boot_hi", "se_cluster", "se_boot")}

    composites = {}
    for name, blk in blocks.items():
        for src, tag in (("S2_headroom_J4_all", "headline"),
                         ("S2_headroom_J4_all_zeros_strict", "zeros_strict"),
                         ("S2_headroom_J4_discriminable", "discriminable")):
            c = compose(blk[src])
            if c is None:
                continue
            composites.setdefault(name, {})[tag] = {
                "source_statistic": src,
                "fullset_extrapolation_factor": FULLSET_EXTRAP,
                "extrapolation_label": (
                    "EXTRAPOLATION, NOT A MEASUREMENT (§4.6): headroom_fullset ~= 1.40 x "
                    "headroom_J4, via the S1a spread estimate and the order statistics "
                    f"a_n = {ORDER_STAT_A}. §4.4's branch thresholds are applied to this "
                    "extrapolated figure so the cap cannot manufacture a closure."),
                "pts": c,
                "bound": bound_block(c["mean"], c["boot_lo"], c["boot_hi"],
                                     sigma_game, f"{name}/{tag}"),
                "z": (blk[src]["z"]),
            }

    # ------------------------------------------------------------------ #
    # §4.4 branch                                                         #
    # ------------------------------------------------------------------ #
    pooled_head = composites.get("pooled", {}).get("headline")
    s1a = blocks["pooled"]["S1a_sigma2_arm_all"]
    if pooled_head:
        b = pooled_head["bound"]["elo"]
        branch, b3, spread_nonzero = decide_branch(
            b["ci95_hi"], b["ci95_lo"], s1a["boot_lo"], s1a["boot_hi"],
            sigma2_se=s1a["se_cluster"])
    else:
        branch, b3, spread_nonzero = 4, False, False

    # §4.4 branch 4 (and good practice everywhere): the sizing statement.
    sizing = None
    src = blocks["pooled"]["S2_headroom_J4_all"]
    if (src["mean"] is not None and src["se_cluster"] == src["se_cluster"]
            and src["se_cluster"] > 0):
        need_pts = elo_to_pts(ELO_CLOSE_BAR, sigma_game=sigma_game)
        need_pts35 = elo_to_pts(ELO_REOPEN_BAR, sigma_game=sigma_game)
        se_comp = src["se_cluster"] * FULLSET_EXTRAP
        sizing = {
            "realized_sd_positions_pts": src["sd_positions"],
            "realized_se_cluster_pts": src["se_cluster"],
            "realized_se_composite_pts": se_comp,
            "n_realized": src["n"],
            "n_roots_realized": src["n_roots"],
            "pts_2se_needed_for_17elo": need_pts,
            "pts_2se_needed_for_35elo": need_pts35,
            "n_required_17elo": (src["n"] * (2 * se_comp / need_pts) ** 2
                                 if need_pts > 0 else None),
            "n_required_35elo": (src["n"] * (2 * se_comp / need_pts35) ** 2
                                 if need_pts35 > 0 else None),
            "note": ("n scales the realized CLUSTER-ROBUST se (design effect included), not "
                     "the naive per-position sd. §7.2's own table (sd 3.0 -> n 1,185 for "
                     "+-17 elo) is the planning-time analogue."),
        }

    # §4.4 stratum rule: no pooling if the strata disagree in SIGN.
    strat_means = {k.split(":", 1)[1]: v["S2_headroom_J4_all"]["mean"]
                   for k, v in blocks.items() if k.startswith("stratum:")
                   and v["S2_headroom_J4_all"]["mean"] is not None}
    strat_n = {k.split(":", 1)[1]: v["S2_headroom_J4_all"]["n"]
               for k, v in blocks.items() if k.startswith("stratum:")}
    strat_z = {k.split(":", 1)[1]: v["S2_headroom_J4_all"]["z"]
               for k, v in blocks.items() if k.startswith("stratum:")}
    signs = {s: (0 if m == 0 else (1 if m > 0 else -1)) for s, m in strat_means.items()}
    sign_disagreement = len(set(signs.values())) > 1 and len(signs) > 1
    verdict_txt = ("§4.4 FORBIDS pooling: the strata disagree in sign. Read them "
                   "separately." if sign_disagreement else
                   "Strata agree in sign (or only one is present); the pooled estimate is "
                   "primary per §4.4.")
    # §4.4: 'per-stratum reads are expected to be underpowered on their own and are
    # labelled as such'. A sign flip driven by a handful of positions is a coin, not a
    # disagreement -- say so rather than letting the mechanical rule read as evidence.
    thin = {s: n for s, n in strat_n.items() if n is not None and n < 30}
    if sign_disagreement and thin:
        verdict_txt += (f" ⚠️ BUT the sign flip involves stratum(s) {sorted(thin)} at "
                        f"n = {thin} -- far below any resolving n. The rule is applied "
                        "mechanically as pre-registered; the flip is NOT evidence of a "
                        "real stratum difference at this n.")
    pooling_rule = {
        "stratum_means_pts": strat_means, "stratum_n": strat_n, "stratum_z": strat_z,
        "sign_disagreement": sign_disagreement,
        "underpowered_strata_n_lt_30": thin,
        "verdict": verdict_txt,
    }

    # §4.5 the epsilon band, as an EXTRAPOLATION off the census rates.
    eps = eps_band_extrapolation(args.census_summary, pooled_head)

    read_rules = {
        "z_conviction_bar": Z_CONVICTION,
        "S1a_z": s1a["z"],
        "S2_z": src["z"],
        "S1a_has_conviction": (s1a["z"] is not None and s1a["z"] == s1a["z"]
                               and abs(s1a["z"]) >= Z_CONVICTION),
        "S2_has_conviction": (src["z"] is not None and src["z"] == src["z"]
                              and abs(src["z"]) >= Z_CONVICTION),
        "rule": ("|z| < 2 is NO CONVICTION -- report the interval, promote nothing. A null "
                 "MUST ship the explicit pts/ply AND elo bound above; 'ties don't matter' is "
                 "never an acceptable read-out (§1)."),
    }

    return {
        "blocks": blocks, "composites": composites, "branch": branch,
        "branch_3_condition_also_met": b3, "spread_ci_excludes_zero": spread_nonzero,
        "sizing": sizing, "pooling_rule": pooling_rule, "eps_band": eps,
        "read_rules": read_rules, "sigma_game": sigma_game,
    }


def eps_band_extrapolation(census_summary_path, pooled_head):
    """§4.5: the eps-band headroom bound = exact bound x r_eps / r_0, LABELLED an
    extrapolation, not a measurement. The scored run scores the exact-tie set only."""
    if not census_summary_path or not Path(census_summary_path).is_file():
        return {"available": False,
                "note": "census summary not supplied; §4.5's secondary read is omitted."}
    s = _load_json(census_summary_path)
    tot = defaultdict(lambda: [0, 0])
    for grp in (s.get("groups") or {}).values():
        for e, d in (grp.get("by_eps") or {}).items():
            tot[e][0] += d["k"]
            tot[e][1] += d["n"]
    rates = {e: (k / n if n else None) for e, (k, n) in sorted(tot.items(),
                                                              key=lambda kv: float(kv[0]))}
    r0 = rates.get("0.0")
    out = {"available": True, "tie_rate_by_eps": rates, "r0": r0,
           "label": ("EXTRAPOLATION, NOT A MEASUREMENT (§4.5): the scored run scores the "
                     "EXACT-tie set only; the eps bands are a census result used to say how "
                     "far the exact bound stretches.")}
    if r0 and pooled_head:
        hi = pooled_head["bound"]["elo"]["ci95_hi"]
        out["elo_ci_hi_stretched"] = {e: (None if (r is None or hi is None) else hi * r / r0)
                                      for e, r in rates.items()}
    return out


# --------------------------------------------------------------------------- #
# RENDERING                                                                     #
# --------------------------------------------------------------------------- #
def _f(x, nd=4):
    if x is None:
        return "n/a"
    if isinstance(x, float) and x != x:
        return "nan"
    return f"{x:+.{nd}f}" if isinstance(x, float) else str(x)


def _stat_line(name, a):
    if a["mean"] is None:
        return f"| {name} | 0 | — | — | — | — |"
    return (f"| {name} | {a['n']} | {_f(a['mean'])} | {_f(a['se_cluster'])} | "
            f"[{_f(a['boot_lo'])}, {_f(a['boot_hi'])}] | {_f(a['z'], 2)} |")


def render_md(v):
    res = v["results"]
    blocks, comps = res["blocks"], res["composites"]
    L = []
    A = L.append
    partial = v["completion"]["partial"]
    A(f"# TILE-TIE PRICING — READ-OUT{' (PARTIAL)' if partial else ''}")
    A("")
    A(f"**Status: {v['status_banner']}**")
    A("")
    A(f"Pre-registration: [DESIGN.md]({v['design_doc_relpath']}) — every estimator below is "
      f"§4, implemented before any record was read. Generated `{v['generated_utc']}`.")
    A("")
    if partial:
        A("> ⚠️ **PARTIAL CORPUS.** This is a per-stratum read on the arms that have "
          "finished. It is not the Stage A verdict and mints nothing. See the completion "
          "accounting below for exactly what is missing.")
        A("")

    # ---------------- completion ----------------
    A("## 1. Completion accounting")
    A("")
    c = v["completion"]
    A(f"- planned positions in scope: **{c['planned_positions']}** · "
      f"fully scored: **{c['scored_complete']}** · partially scored: "
      f"**{c['scored_partial']}** · absent: **{c['absent']}**")
    A(f"- positions ENTERING the statistics: **{c['n_analysed']}** "
      f"(`include_partial_arms={v['args']['include_partial_arms']}`)")
    A("")
    A("| profile | planned | complete | partial | absent |")
    A("|---|---|---|---|---|")
    for p, d in sorted(c["by_profile"].items()):
        A(f"| {p} | {d.get('planned', 0)} | {d.get('complete', 0)} | "
          f"{d.get('partial', 0)} | {d.get('absent', 0)} |")
    A("")
    A("| stratum | planned | complete | partial | absent |")
    A("|---|---|---|---|---|")
    for p, d in sorted(c["by_stratum"].items()):
        A(f"| {p} | {d.get('planned', 0)} | {d.get('complete', 0)} | "
          f"{d.get('partial', 0)} | {d.get('absent', 0)} |")
    A("")
    if c["missing_legs_by_profile_leg"]:
        A("**Missing leg records (planned − present):**")
        A("")
        A("| profile/leg | planned | present | missing |")
        A("|---|---|---|---|")
        for k, d in sorted(c["missing_legs_by_profile_leg"].items()):
            A(f"| {k} | {d['planned']} | {d['present']} | **{d['missing']}** |")
        A("")
    A(f"**What is missing, stated loudly:** {c['missing_statement']}")
    A("")

    # ---------------- analytic zeros ----------------
    A("## 2. The §0.A analytic zeros (all-transposition positions)")
    A("")
    z = v["zero_rates"]
    A(f"Count source: {z['source']}")
    A("")
    A("| stratum | qualifying | built | dropped (analytic 0) | of which played-action "
      "INSIDE tie set | p_drop | scale = 1−p_drop | scale (zeros_strict) |")
    A("|---|---|---|---|---|---|---|---|")
    for s, d in sorted(z["by_stratum"].items()):
        A(f"| {s} | {d.get('n_qualifying', '—')} | {d.get('n_built', '—')} | "
          f"{d['n_dropped']} | {d['n_dropped_inside_tieset']} | {d['p_all']:.4f} | "
          f"{d['scale_all']:.4f} | {d['scale_strict']:.4f} |")
    A("")
    A("Every all-transposition position contributes **exactly 0 with zero variance** "
      "(§6 threat 3), so the population mean is `(1 − p_drop) × mean(discriminable)` "
      "exactly. ⚠️ On the rows whose played action lies OUTSIDE the tie set the analytic "
      "zero covers the **tie-set arms only**, so S2 carries `zeros_strict` as a per-row "
      "sensitivity (see §6 of this read-out); spread and S2b are unaffected.")
    A("")

    # ---------------- integrity ----------------
    A("## 3. Integrity (§2.1 CRN witness)")
    A("")
    it = v["integrity"]
    for k, lst in it.items():
        A(f"- `{k}`: **{len(lst)}**" + ("" if not lst else f" ⚠️ {lst[:5]}"))
    A("")
    A("`values_a_drift == 0` is the §2.1 witness: the reference arm is re-scored in every "
      "leg under identical (world, playout) seeds, so any drift would VOID the run.")
    A("")

    # ---------------- the statistics ----------------
    A("## 4. The pre-registered statistics")
    A("")
    A("All estimates are **pts** (S1b/S2/S2b) or **pts²** (S1a), cluster-robust on "
      "`root_id`; CIs are root-resampling bootstrap, "
      f"{v['args']['bootstrap']:,} reps, seed {v['args']['seed']}.")
    A("")
    for name in ["pooled"] + sorted(k for k in blocks if k != "pooled"):
        blk = blocks[name]
        A(f"### {name}  (n={blk['n_positions']} positions, {blk['n_roots']} roots, "
          f"champ arm scored on {blk['n_positions_with_champ_arm']})")
        A("")
        A("| statistic | n | mean | se (cluster) | 95% CI (boot) | z |")
        A("|---|---|---|---|---|---|")
        for key, lbl in [
                ("S1a_sigma2_arm_discriminable", "S1a σ²_arm — discriminable [pts²] ⭐PRIMARY"),
                ("S1a_sigma2_arm_all", "S1a σ²_arm — all (zeros added) [pts²]"),
                ("S1b_gap_discriminable", "S1b cross-fit gap G — discriminable [pts]"),
                ("S1b_gap_all", "S1b cross-fit gap G — all [pts]"),
                ("S2_headroom_J4_discriminable", "S2 headroom_J4 — discriminable [pts]"),
                ("S2_headroom_J4_all", "S2 headroom_J4 — all [pts] ⭐DELIVERABLE"),
                ("S2_headroom_J4_all_zeros_strict", "S2 headroom_J4 — all, zeros_strict"),
                ("S2b_headroom_leaf_discriminable", "S2b leaf regret — discriminable [pts]"),
                ("S2b_headroom_leaf_all", "S2b leaf regret — all [pts]")]:
            A(_stat_line(lbl, blk[key]))
        A(_stat_line("*(audit only, never quoted)* naive range",
                     blk["NAIVE_never_quote"]["gap_naive"]))
        A(_stat_line("*(audit only, never quoted)* naive champ regret",
                     blk["NAIVE_never_quote"]["headroom_champ_naive"]))
        A(_stat_line("*(diagnostic)* S1b parity-swapped", blk["S1b_gap_parity_swap"]))
        A(_stat_line("*(diagnostic)* S2 parity-swapped", blk["S2_headroom_parity_swap"]))
        A("")
    A("⚠️ **S1b carries its sentence (§4.1):** `G` is a *downward-biased estimate of the "
      "true range and an unbiased test of the null*. The naive rows are printed ONLY so the "
      "winner's-curse correction is auditable (§4.2) and are never results.")
    A("")

    # ---------------- the bound ----------------
    A("## 5. The bound chain (§4.3) — the mandatory statement")
    A("")
    for name in ["pooled"] + sorted(k for k in comps if k != "pooled"):
        if name not in comps:
            continue
        A(f"### {name}")
        A("")
        A("| variant | headroom_fullset [pts/tied tile ply] | 95% CI | elo (÷3.2) | "
          "elo 95% CI | elo (÷5.23 low-end) |")
        A("|---|---|---|---|---|---|")
        for tag, c in comps[name].items():
            b = c["bound"]
            A(f"| {tag} | {_f(c['pts']['mean'])} | [{_f(c['pts']['boot_lo'])}, "
              f"{_f(c['pts']['boot_hi'])}] | {_f(b['elo']['point'], 2)} | "
              f"[{_f(b['elo']['ci95_lo'], 2)}, {_f(b['elo']['ci95_hi'], 2)}] | "
              f"{_f(b['elo_low_end_divisor_5.23']['point'], 2)} |")
        A("")
    ph = comps.get("pooled", {}).get("headline")
    if ph:
        ss = ph["bound"]["elo_sigma_sensitivity"]
        A("**σ_game sensitivity (§4.3)** on the headline elo CI-hi: "
          + " · ".join(f"σ={k} → {_f(x, 2)} elo" for k, x in ss.items())
          + ". elo scales as 1/σ_game, so the SMALLER σ is the larger, "
            "conservative-against-closure bound.")
        A("")
    A(f"σ_game = **{res['sigma_game']}** (§4.3: 20.4 `fixed_v1` / 22.2 `walled`); "
      f"tied tile plies/game = **{TIED_TILE_PLIES_PER_GAME}** (census-measured); "
      f"`Kelo` linear check = **{KELO_REFERENCE}** elo per pt per tied tile ply.")
    A("")
    A(f"⚠️ **§4.6 extrapolation, labelled:** the headline multiplies the measured "
      f"`headroom_J4` by **{FULLSET_EXTRAP}** to reach the full-set ceiling "
      f"(order statistics a_n = {ORDER_STAT_A}). That is an **extrapolation through the "
      f"S1a spread estimate, never a measurement**. §4.4's thresholds are applied to the "
      f"extrapolated figure so the cap cannot manufacture a closure. "
      f"Realized capped fraction: **{v['capped_fraction']:.1%}** of scored positions.")
    A("")
    A("⚠️ **§4.3 caveats, inherited verbatim:** `NON_ADDITIVITY = 3.2` is **n = 1**, is "
      "calibrated at the TOP of the ladder, and the memo's range-consistent low-end divisor "
      "is ≈5.23. The divisor enters **linearly**, so this bound is quoted with a ±1.6× "
      "bracket, not as a point. The linear-φ step degrades above ~1σ.")
    A("")

    # ---------------- branch ----------------
    A("## 6. §4.4 branch")
    A("")
    bt = BRANCH_TEXT[res["branch"]]
    A(f"### BRANCH {res['branch']} — {bt[0]}")
    A("")
    A(bt[1])
    A("")
    rr = res["read_rules"]
    A(f"- read-rule: `|z| < {Z_CONVICTION}` is **no conviction**. "
      f"S1a z = **{_f(rr['S1a_z'], 2)}** ({'conviction' if rr['S1a_has_conviction'] else 'NO conviction'}) · "
      f"S2 z = **{_f(rr['S2_z'], 2)}** ({'conviction' if rr['S2_has_conviction'] else 'NO conviction'}).")
    A(f"- `branch_3_condition_also_met` = **{res['branch_3_condition_also_met']}** "
      f"(spread CI excludes 0: {res['spread_ci_excludes_zero']}). "
      "⚠️ See interpretation **I4** — branch 3 is unreachable under the pre-registered "
      "precedence; the flag is reported rather than the precedence silently re-ordered.")
    A(f"- §4.4 stratum rule: {res['pooling_rule']['verdict']} "
      f"(stratum means {res['pooling_rule']['stratum_means_pts']}, "
      f"n {res['pooling_rule']['stratum_n']})")
    A("")
    if res["sizing"]:
        s = res["sizing"]
        A("**Sizing (mandatory on branch 4, reported always):** realized per-position sd = "
          f"**{_f(s['realized_sd_positions_pts'])} pts**, cluster-robust se = "
          f"**{_f(s['realized_se_cluster_pts'])} pts** at n = {s['n_realized']} over "
          f"{s['n_roots_realized']} roots. A ±17-elo bound needs 2·se ≤ "
          f"{_f(s['pts_2se_needed_for_17elo'])} pts ⇒ **n ≈ "
          f"{s['n_required_17elo']:.0f}**; a ±35-elo bound ⇒ **n ≈ "
          f"{s['n_required_35elo']:.0f}** (composite scale included).")
        A("")
    if res["eps_band"].get("available"):
        e = res["eps_band"]
        A("**§4.5 epsilon band (secondary, EXTRAPOLATION):** census tie rates "
          + ", ".join(f"eps={k} → {r:.3f}" for k, r in e["tie_rate_by_eps"].items() if r)
          + ". Stretched elo CI-hi: "
          + ", ".join(f"{k} → {_f(x, 2)}"
                      for k, x in (e.get("elo_ci_hi_stretched") or {}).items()) + ".")
        A("")

    # ---------------- scope + interpretations ----------------
    A("## 7. Scope, threats and where DESIGN was ambiguous")
    A("")
    A("**§5 scope sentence, mandatory on any null:** a null through `clair-puct` closes "
      "*\"spread visible to a deep clairvoyant search over THIS leaf\"*, **not** *\"spread "
      "in truth\"*. The judge uses the leaf under test at its own leaves; systematic leaf "
      "blindness would make it UNDER-report the true spread. The out-of-family "
      "`tier1-greedy` sign leg (n=80, §5/§7.3) is the check, and it is bought only if the "
      "primary does not branch-1-close.")
    A("")
    A("Other pre-stated threats that travel with every number here: chain-granularity on "
      "the TILE class (§6.2 — neither arm gets the meeple its chain value assumed); "
      "\"exact tie\" is a **lattice** property, not an indifference proof (§6.4); selection "
      "on ties makes regression to the mean push the measured spread toward 0 (§6.5 — this "
      "protects branch 2 and threatens branch 1); the scored population is the **≤12-way** "
      "tied set (§7.3); the self-play champion pick is *a* champion pick, not *the* one "
      "(§6.9); rules-epoch confound between strata (§6.6).")
    A("")
    A("| id | where | resolution |")
    A("|---|---|---|")
    for i in v["interpretations"]:
        A(f"| **{i['id']}** | {i['where']} | {i['resolution']} |")
    A("")
    A("## 8. Governance")
    A("")
    A("Measurement only (§8): `governance/PRODUCTION.yaml` untouched, **no "
      "`experiments/results.csv` row** (0 games played), no band claim. A claim id is "
      "minted only on branch 1, 2 or 3 — and never off a PARTIAL corpus.")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- #
# MAIN                                                                          #
# --------------------------------------------------------------------------- #
def build_verdict(rows, integrity, completion, rates, res, args, plan_bundle,
                  present_counts, not_ok, design_doc_relpath=DESIGN_DOC):
    plan = plan_bundle["plan"]
    planned_legs = plan.get("counts_by_profile_leg", {})
    missing_legs = {}
    for k, n in sorted(planned_legs.items()):
        prof = k.split("/")[0]
        if args.only_profiles and prof not in args.only_profiles:
            continue
        got = present_counts.get(k, 0)
        if got != n:
            missing_legs[k] = {"planned": n, "present": got, "missing": n - got}
    partial = bool(missing_legs) or completion["absent"] > 0 or completion["scored_partial"] > 0
    if missing_legs:
        stmt = ("INCOMPLETE — " + "; ".join(
            f"{k}: {d['present']}/{d['planned']} records ({d['missing']} missing)"
            for k, d in sorted(missing_legs.items())))
    else:
        stmt = "COMPLETE for the profiles in scope — every planned leg record is present."
    if args.only_profiles:
        stmt += (f" ⚠️ SCOPE RESTRICTED to profiles {sorted(args.only_profiles)}: the "
                 "other arms of the plan are NOT in this read-out at all.")

    completion = dict(completion)
    completion["n_analysed"] = len(rows)
    completion["missing_legs_by_profile_leg"] = missing_legs
    completion["missing_statement"] = stmt
    completion["partial"] = partial
    completion["records_not_ok"] = not_ok
    completion["present_by_profile_leg"] = present_counts

    banner = ("⚠️ PRELIMINARY / PARTIAL — a per-stratum read on a corpus that is still "
              "being scored. NOT the Stage A verdict; mints nothing."
              if partial else "COMPLETE for the scope declared below.")
    if args.label:
        banner = f"{args.label} — {banner}"

    capped_frac = (sum(1 for r in rows if r["capped"]) / len(rows)) if rows else float("nan")
    return {
        "schema": SCHEMA,
        "design_doc": DESIGN_DOC,
        "design_doc_relpath": design_doc_relpath,
        "generated_utc": _now_utc(),
        "status_banner": banner,
        "args": vars(args) | {"only_profiles": sorted(args.only_profiles)
                              if args.only_profiles else None,
                              "only_strata": sorted(args.only_strata)
                              if args.only_strata else None},
        "plan_dir": plan_bundle["dir"],
        "completion": completion,
        "integrity": {k: v for k, v in integrity.items()},
        "zero_rates": rates,
        "capped_fraction": capped_frac,
        "constants": {
            "cap_J": CAP_J, "fullset_extrapolation": FULLSET_EXTRAP,
            "order_statistics_a_n": ORDER_STAT_A,
            "tied_tile_plies_per_game": TIED_TILE_PLIES_PER_GAME,
            "non_additivity": NON_ADDITIVITY,
            "non_additivity_low_end": NON_ADDITIVITY_LOW_END,
            "sigma_game_used": args.sigma_game,
            "kelo_reference": KELO_REFERENCE,
            "elo_close_bar": ELO_CLOSE_BAR, "elo_reopen_bar": ELO_REOPEN_BAR,
            "z_conviction_bar": Z_CONVICTION,
            "bootstrap_reps": args.bootstrap, "bootstrap_seed": args.seed,
        },
        "interpretations": INTERPRETATIONS,
        "results": res,
        "governance": ("Measurement only (§8): PRODUCTION.yaml untouched, NO results.csv "
                       "row (0 games), no band claim. A claim id is minted only on branch "
                       "1/2/3 and never off a PARTIAL corpus."),
    }


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--records-root",
                    default="/mnt/c/carc-shared/tiletie_pricing_20260812/clair-puct")
    ap.add_argument("--plan-dir",
                    default=str(REPO / "measurement/tiletie_pricing_20260812/positions_stageA"))
    ap.add_argument("--full-supply-plan", default=None,
                    help="POSITIONS_PLAN.json of the FULL supply, for the per-stratum "
                         "analytic-zero rates (auto-discovered next to --plan-dir).")
    ap.add_argument("--census-summary",
                    default=str(REPO / "measurement/tiletie_pricing_20260812/census/summary.json"))
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--only-profiles", nargs="*", default=None)
    ap.add_argument("--only-strata", nargs="*", default=None)
    ap.add_argument("--bootstrap", type=int, default=BOOTSTRAP_REPS)
    ap.add_argument("--seed", type=int, default=BOOTSTRAP_SEED)
    ap.add_argument("--parity-base", type=int, choices=(0, 1), default=1,
                    help="§4.1 world-parity base; 1 = the DESIGN-literal one-based reading.")
    ap.add_argument("--sigma-game", type=float, default=SIGMA_GAME_FIXED_V1)
    ap.add_argument("--include-partial-arms", action="store_true",
                    help="Include positions whose planned arm complement is incomplete. OFF "
                         "by default: the missing legs are the HIGH action indices, which is "
                         "not the seeded uniform draw §4.6's cap-invariance argument needs.")
    ap.add_argument("--label", default=None)
    a = ap.parse_args(argv)
    a.only_profiles = set(a.only_profiles) if a.only_profiles else None
    a.only_strata = set(a.only_strata) if a.only_strata else None
    return a


def main(argv=None) -> int:
    args = parse_args(argv)
    plan_bundle = load_plan(args.plan_dir)
    by_rid, present, not_ok = discover_records(args.records_root, args.only_profiles)
    rates = zero_rates(plan_bundle, args.full_supply_plan)
    if args.only_profiles:
        keep = args.only_profiles
        plan_bundle = dict(plan_bundle)
        plan_bundle["arms"] = {k: v for k, v in plan_bundle["arms"].items()
                               if v["rules_profile"] in keep}
    rows, integrity, completion = build_positions(
        plan_bundle, by_rid, rates, parity_base=args.parity_base,
        include_partial_arms=args.include_partial_arms, only_strata=args.only_strata)
    if not rows:
        print("REFUSING: no scored positions in scope.", file=sys.stderr)
        return 2
    res = analyse(rows, rates, args, completion, integrity, plan_bundle)
    out = Path(args.out_dir) if args.out_dir else Path(args.plan_dir).parent / "readout"
    out.mkdir(parents=True, exist_ok=True)
    try:
        rel = os.path.relpath(REPO / DESIGN_DOC, out.resolve())
    except ValueError:                       # different drive / unrelated tree
        rel = DESIGN_DOC
    verdict = build_verdict(rows, integrity, completion, rates, res, args, plan_bundle,
                            present, not_ok, design_doc_relpath=rel)
    (out / "VERDICT.json").write_text(json.dumps(verdict, indent=1, default=str))
    (out / "VERDICT.md").write_text(render_md(verdict))
    (out / "per_position.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows))
    print(render_md(verdict))
    print(f"\n[wrote] {out/'VERDICT.json'}\n[wrote] {out/'VERDICT.md'}\n"
          f"[wrote] {out/'per_position.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
