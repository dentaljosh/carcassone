#!/usr/bin/env python3
"""JCZ DISAGREEMENT MINING — the analysis, exactly as pre-registered.

Pre-registration: measurement/jcz_mining_20260809/MINING_PREREG.md §§4-8,
committed BEFORE any scoring ran. This module implements the decision map
LITERALLY and nothing adjacent — no post-hoc stratum, no one-sided test, no
branch reordering.

SIGN CONVENTION (load-bearing, repeated at every place it matters):
`oracle_score_pilot.position_delta` returns ``delta = mean(V_B - V_A)``.
Positions are emitted with `pick_a` = OUR leaf-argmax pick and `pick_b` = JCZ's
PLAYED pick (MINING_PREREG.md §5 "Statistic"). Therefore:

    delta > 0  =>  JCZ's pick was better than ours (their evaluator out-earned ours)
    delta < 0  =>  our pick was better (vindicates our leaf on this ply)

Every stat below, every branch name, and every verdict string is written to stay
consistent with that. TWO-SIDED z throughout — a negative result is informative
here (PREREG §7 rider 1: it is the CONSERVATIVE direction to trust given the
in-family judge's bias), so the test must be able to see it.

Cluster-robust SE is CR1 on `root_id` (the pre-registered statistic); `game_label`
is reported as a sensitivity. By the one-position-per-game design (PREREG §4)
these should coincide exactly with `sd/sqrt(n)` — `cluster_consistency_ok` checks
that and flags divergence as a BUG SIGNAL, not a result (never reinterpreted as a
design-effect finding, unlike farm-war's *cross*-ply clustering).

STRATA.json JOIN. `oracle_score_pilot`'s own per-position record does NOT carry
`ply_class` / `our_leaf_gap` / `search_pick` / `merge_exposure_differs` /
`jcz_seat` (its `_process` only passes through a fixed field allowlist — see
`scripts/measurement_infra/oracle_score_pilot.py`, a banked instrument this
module does not edit). Those fields are recovered by joining each record back to
`STRATA.json["rows"]` by `rid` — see `join_records`.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SCHEMA = "carcassonne-jcz-mining-verdict/v1"

#: |z| at which the pre-registration's per-stratum/global branches fire.
Z_GATE = 2.0
#: Two-sided 95% normal quantile, for the reported CI.
Z_95 = 1.959963984540054
#: Bonferroni-2 threshold, reported alongside every primary z (NOT the gate — PREREG §6).
Z_BONF2 = 2.2414

STRATA_LETTERS = ("A", "B", "C")

#: PREREG §6 "Mapping to the candidates".
CANDIDATE_MAP = {
    "A": "S1 stranded-meeple penalty + S4 category-convex lock-up (JOINTLY — this "
         "stratum cannot separate them)",
    "B": "S2 deck-graded closure probability",
}


# --------------------------------------------------------------------------- #
# Small stats primitives — cluster_se/stratum_stats/sign_agreement/load_records #
# copied+adapted from scripts/analyzer/farmwar_analyze.py (a banked instrument   #
# this module does not import-and-mutate; see the assignment brief).            #
# --------------------------------------------------------------------------- #
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
    """CR1 cluster-robust standard error of a MEAN — identical construction to
    farmwar_analyze.cluster_se. With one observation per cluster it collapses
    exactly to the naive `sd/sqrt(n)` (up to the small-G correction), which is
    what makes the root-clustered number a statement rather than a manipulation."""
    n = len(values)
    if n < 2:
        return {"se": float("nan"), "n_clusters": len(set(clusters)), "design_effect": None}
    ybar = _mean(values)
    per: dict = {}
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
    """n / mean / se / two-sided z / 95% CI for one stratum, both clusterings, the
    Bonferroni-2 flag, and the cluster-consistency BUG SIGNAL."""
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
    consistency_ok = bool(
        se == se and game["se"] == game["se"]
        and math.isclose(se, game["se"], rel_tol=1e-6, abs_tol=1e-9))
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
        "cluster_consistency_ok": consistency_ok,
        "z_two_sided": z,
        "z_bonf_threshold": Z_BONF2,
        "passes_bonferroni2": bool(z == z and abs(z) >= Z_BONF2),
        "ci95_lo": mean - Z_95 * se,
        "ci95_hi": mean + Z_95 * se,
        "ci95_covers_zero": bool((mean - Z_95 * se) <= 0.0 <= (mean + Z_95 * se)),
        "n_positive": sum(1 for v in vals if v > 0),
        "n_negative": sum(1 for v in vals if v < 0),
        "n_zero": sum(1 for v in vals if v == 0),
    }


def sign_agreement(primary: list, secondary: list) -> dict:
    """Per-position SIGN agreement between the primary and Tier-1 judges, exact
    two-sided binomial p against 50/50. SIGN ONLY — PREREG §5 forbids comparing
    the Tier-1 magnitude to the primary's."""
    a = {r["rid"]: float(r["delta"]) for r in primary if r.get("ok")}
    b = {r["rid"]: float(r["delta"]) for r in secondary if r.get("ok")}
    shared = sorted(set(a) & set(b))
    both_nonzero = [r for r in shared if a[r] != 0 and b[r] != 0]
    agree = sum(1 for r in both_nonzero if (a[r] > 0) == (b[r] > 0))
    n = len(both_nonzero)
    p = None
    if n:
        tail = sum(math.comb(n, k) for k in range(0, n + 1)
                   if abs(k - n / 2) >= abs(agree - n / 2)) / (2.0 ** n)
        p = min(1.0, tail)
    return {"n_shared": len(shared), "n_scored": n, "n_agree": agree,
            "agreement_rate": (agree / n if n else None),
            "binomial_p_two_sided": p,
            "primary_mean": _mean(a[r] for r in shared),
            "secondary_mean_SIGN_ONLY": _mean(b[r] for r in shared)}


def sign_corroborates(sc: dict | None) -> bool:
    """A CONVICT needs the Tier-1 sign check to actually corroborate, not merely
    run. Corroboration threshold — this module's choice; the prereg names the
    farm-war precedent's SCALE (80% agreement / p 0.0012 corroborated, 61.9% /
    p 0.38 did not) but not an exact cutoff, so this uses the standard two-sided
    p<0.05 significance test on agreement strictly above chance."""
    if not sc or not sc.get("n_scored"):
        return False
    p = sc.get("binomial_p_two_sided")
    rate = sc.get("agreement_rate")
    return bool(p is not None and p < 0.05 and rate is not None and rate > 0.5)


class EmptyRecordsError(RuntimeError):
    """A records path yielded nothing. Loading zero records must never proceed
    to a verdict: `Path(dir).glob` on a nonexistent path — or on a FILE, which
    is how the 2026-08-09 n=0 non-verdict happened — returns an empty iterator,
    and every downstream gate then reads as INCONCLUSIVE-BY-CONSTRUCTION
    instead of as the caller error it is."""


def load_records(dirs: list) -> list:
    rows = []
    for d in dirs:
        p = Path(d)
        if p.is_file():
            if p.suffix != ".json":
                raise EmptyRecordsError(f"records path {d} is a non-json file")
            rows.append(json.loads(p.read_text()))
            continue
        if not p.is_dir():
            raise EmptyRecordsError(f"records path {d} does not exist")
        found = sorted(p.glob("*.json"))
        if not found:
            raise EmptyRecordsError(f"records dir {d} contains no *.json")
        for f in found:
            rows.append(json.loads(f.read_text()))
    if dirs and not rows:
        raise EmptyRecordsError(f"no records loaded from {dirs}")
    return rows


# --------------------------------------------------------------------------- #
# STRATA.json join                                                              #
# --------------------------------------------------------------------------- #
#: Metadata fields recovered from STRATA.json["rows"] that oracle_score_pilot's
#: own record does not carry (see module docstring "STRATA.json JOIN").
_JOIN_KEYS = ("stratum", "ply_class", "our_leaf_gap", "k_remaining", "search_pick",
             "merge_exposure_differs", "jcz_seat", "game_label", "root_id",
             "rules_profile")


#: Every spelling the extractor (or a future revision of it) might use for a
#: stratum label, mapped to this module's internal "A"/"B"/"C". The real
#: STRATA.json (2026-08-09 extraction) uses "STRAT_A"/"STRAT_B"/"STRAT_C"
#: throughout (both `rows[*]["stratum"]` and the `strata["strata"]` summary
#: block keys) — matched case-insensitively so "A", "STRAT_A" and "strat_a"
#: all land the same place.
_LABEL_MAP = {"A": "A", "B": "B", "C": "C",
             "STRAT_A": "A", "STRAT_B": "B", "STRAT_C": "C"}


class UnknownStratumLabelError(ValueError):
    """A stratum label was seen that this module cannot map to A/B/C. Raised
    rather than silently dropped: a silently-dropped row reads as a smaller n
    and is indistinguishable from a real min_n_gate failure."""


def normalize_stratum_label(label) -> str:
    if label is None:
        raise UnknownStratumLabelError("stratum label is None")
    key = str(label).strip().upper()
    if key in _LABEL_MAP:
        return _LABEL_MAP[key]
    raise UnknownStratumLabelError(
        f"unrecognized stratum label {label!r} — expected one of "
        f"{sorted(_LABEL_MAP)} (case-insensitive)")


class UnmatchedRecordsError(RuntimeError):
    """One or more `ok` oracle_score_pilot records could not be joined to a
    STRATA.json row by rid. A partial join is the same silent-failure class as
    a stratum being incorrectly gated — it must never pass quietly (a missing
    row makes a stratum's n look smaller than it really is, indistinguishable
    from a real min_n_gate failure)."""


def index_strata_rows(strata: dict) -> dict:
    """rid -> row, from STRATA.json['rows'] in EITHER shape the extractor might
    emit: a flat list of rows, or a dict-of-lists keyed by stratum (as the real
    2026-08-09 extraction does: {"STRAT_A": [...], "STRAT_B": [...], "STRAT_C":
    [...]}). Every row's own `stratum` field is normalised in place (on a COPY —
    the input dict/list is never mutated) to this module's "A"/"B"/"C", so every
    downstream consumer sees one spelling regardless of the extractor's."""
    raw = strata.get("rows", [])
    flat = ([row for rows in raw.values() for row in rows]
           if isinstance(raw, dict) else list(raw))
    out = {}
    for row in flat:
        r = dict(row)
        if r.get("stratum") is not None:
            r["stratum"] = normalize_stratum_label(r["stratum"])
        out[r["rid"]] = r
    return out


def join_records(records: list, strata_rows: dict) -> tuple[list, list]:
    """Keep `ok` records and stamp the STRATA.json metadata onto them. A record
    whose rid is missing from strata['rows'] is DROPPED and reported by rid,
    never silently included with an undefined stratum — that would put it
    nowhere and would be invisible in every stratum's n. Callers MUST check the
    returned unmatched list (`assert_full_join`) rather than ignore it."""
    joined, unmatched = [], []
    for r in records:
        if not r.get("ok"):
            continue
        srow = strata_rows.get(r.get("rid"))
        if srow is None:
            unmatched.append(r.get("rid"))
            continue
        j = dict(r)
        for k in _JOIN_KEYS:
            if k in srow:
                j[k] = srow[k]
        joined.append(j)
    return joined, unmatched


def assert_full_join(unmatched: list, label: str) -> None:
    """Fail LOUDLY on a partial join — see UnmatchedRecordsError."""
    if unmatched:
        raise UnmatchedRecordsError(
            f"{len(unmatched)} {label} record(s) with ok=true had no matching "
            "STRATA.json row (by rid). A partial join is indistinguishable "
            "from a real min_n_gate failure and must not pass silently. "
            f"Unmatched rids (up to 10 shown): {unmatched[:10]}")


# --------------------------------------------------------------------------- #
# Reported-but-not-decisive helpers                                             #
# --------------------------------------------------------------------------- #
def ply_class_breakdown(rows: list) -> dict:
    out: dict = {}
    for cls in ("TILE", "MEEPLE"):
        sub = [r for r in rows if r.get("ply_class") == cls]
        vals = [float(r["delta"]) for r in sub]
        out[cls] = {"n": len(vals), "mean_delta_pts": _mean(vals)}
    total = sum(out[c]["n"] for c in out)
    dominant = max((out[c]["n"] for c in out), default=0)
    out["class_dominated"] = bool(total > 0 and dominant / total > 0.8)
    return out


def pearson(xs: list, ys: list):
    n = len(xs)
    if n < 2:
        return None
    mx, my = _mean(xs), _mean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


#: Plausible locations for the extractor's own disagreement-rate diagnostic —
#: STRATA.json's exact shape is the sibling extractor's choice, so this scans a
#: few likely paths rather than assuming one, and reports which (if any) hit.
_DISAGREEMENT_RATE_PATHS = (
    ("disagreement_rate",),
    ("meta", "disagreement_rate"),
    ("match_quality", "disagreement_rate"),
    ("diagnostics", "disagreement_rate"),
    ("extractor_meta", "disagreement_rate"),
)


def find_disagreement_rate(strata: dict):
    for path in _DISAGREEMENT_RATE_PATHS:
        node = strata
        ok = True
        for k in path:
            if isinstance(node, dict) and k in node:
                node = node[k]
            else:
                ok = False
                break
        if ok and isinstance(node, (int, float)) and not isinstance(node, bool):
            return float(node), ".".join(path)
    return None, None


def scoring_health(records_all: list) -> dict:
    ok = [r for r in records_all if r.get("ok")]
    return {
        "n_attempted": len(records_all),
        "n_ok": len(ok),
        "n_failed": len(records_all) - len(ok),
        "failures": [{"rid": r.get("rid"), "error": r.get("error")}
                     for r in records_all if not r.get("ok")],
        "crn_verified_all": (all(r.get("crn_verified") for r in ok) if ok else None),
        "distinct_afterstates_min": min((r.get("distinct_afterstates", 0) for r in ok),
                                        default=None),
        "m_worlds": sorted({r.get("m") for r in ok if r.get("m") is not None}),
    }


# --------------------------------------------------------------------------- #
# Decision map — PREREG §6, literal, first-match-wins                          #
# --------------------------------------------------------------------------- #
def _sig(z) -> bool:
    return bool(z == z and abs(z) >= Z_GATE)


def _below(z) -> bool:
    return bool(z == z and abs(z) < Z_GATE)


def _stratum_verdict(x_stats: dict, c_stats: dict) -> tuple:
    """CONVICT / EXONERATE / INCONCLUSIVE for stratum X in {A, B}, PREREG §6 table."""
    mean_x = x_stats.get("mean_delta_pts", float("nan"))
    z_x = x_stats.get("z_two_sided", float("nan"))
    mean_c = c_stats.get("mean_delta_pts", float("nan"))
    sig_x = _sig(z_x)
    convict_sub_ci = bool(c_stats.get("ci95_covers_zero"))
    convict_sub_half = bool(mean_c == mean_c and mean_x == mean_x and mean_c < 0.5 * mean_x)
    convict = bool(mean_x == mean_x and mean_x > 0 and sig_x
                   and (convict_sub_ci or convict_sub_half))
    exonerate = bool(mean_x == mean_x and mean_x <= 0 and sig_x)
    verdict = "CONVICT" if convict else ("EXONERATE" if exonerate else "INCONCLUSIVE")
    preds = {
        "mean_gt_0": bool(mean_x == mean_x and mean_x > 0),
        "abs_z_ge_gate": sig_x,
        "convict_sub_control_ci_covers_zero": convict_sub_ci,
        "convict_sub_control_mean_lt_half": convict_sub_half,
        "convict_raw": convict,
        "exonerate_raw": exonerate,
    }
    return verdict, preds


def decide(strata_stats: dict, min_n_gate: int, sign_checks: dict | None = None) -> dict:
    """Global + per-stratum decision map, PREREG §6, literal, first-match-wins.

    `strata_stats` = {"A": stratum_stats(...)-shaped dict, "B": ..., "C": ...}
    `sign_checks`  = {"A": sign_agreement(...)-shaped dict or None, "B": ...} —
                     Tier-1, A and B only (PREREG §6 "Tier-1 sign check").
    """
    sign_checks = sign_checks or {}
    gate = {L: bool(strata_stats[L].get("n", 0) >= min_n_gate) for L in STRATA_LETTERS}
    predicates: dict = {f"gate_{L}_ok": gate[L] for L in STRATA_LETTERS}

    # ---- G0 — GATE FAIL (both A and B) ----------------------------------- #
    if not gate["A"] and not gate["B"]:
        per_stratum = {L: ("INCONCLUSIVE_BY_CONSTRUCTION" if not gate[L] else "NOT READ (G0)")
                       for L in STRATA_LETTERS}
        per_stratum["S3"] = "NOT TESTED BY THIS DESIGN"
        predicates["global_branch"] = "G0"
        return {
            "global_branch": "G0",
            "verdict": "INCONCLUSIVE BY CONSTRUCTION — both STRAT-A and STRAT-B "
                       f"fell under the pre-registered n>={min_n_gate} gate. Stop; "
                       "do not reinterpret; do not read C on its own.",
            "predicates": predicates,
            "per_stratum": per_stratum,
            "candidate_mapping": {},
            "mints_claim_id": False,
            "z_gate": Z_GATE, "z_bonf_threshold": Z_BONF2,
        }

    A, B, C = strata_stats["A"], strata_stats["B"], strata_stats["C"]
    zA, zB, zC = (A.get("z_two_sided", float("nan")), B.get("z_two_sided", float("nan")),
                 C.get("z_two_sided", float("nan")))
    mA, mB, mC = (A.get("mean_delta_pts", float("nan")), B.get("mean_delta_pts", float("nan")),
                 C.get("mean_delta_pts", float("nan")))

    # ---- G1 — ALL WASH ----------------------------------------------------- #
    g1 = bool(_below(zA) and _below(zB) and _below(zC))
    # ---- G2 — NOT LOCALISED (only evaluated/reported when G1 does not fire,   #
    # branch precedence is first-match-wins: G1 -> G2 -> G3) ----------------- #
    means_finite = mA == mA and mB == mB and mC == mC
    g2 = bool((not g1) and _sig(zA) and _sig(zB) and _sig(zC) and means_finite
              and mA > 0 and mB > 0 and mC > 0 and mC >= 0.5 * min(mA, mB))

    predicates.update({
        "z_A": zA, "z_B": zB, "z_C": zC, "mean_A": mA, "mean_B": mB, "mean_C": mC,
        "g1_all_wash": g1, "g2_not_localised": g2,
    })

    candidate_mapping: dict = {}
    mints = False

    if g1:
        branch = "G1"
        verdict = ("CONVERGENT EVOLUTION CONFIRMED AT THE MOVE LEVEL — the two "
                   "evaluators disagree on a measurable fraction of real plies but "
                   "neither pick is detectably better on strata A, B or C at this "
                   "power. No term is funded.")
        per_stratum = {"A": "WASH", "B": "WASH", "C": "WASH"}
    elif g2:
        branch = "G2"
        verdict = ("NOT LOCALISED — JCZ's evaluator out-earns ours including on "
                   "the stratum built to be neutral (C). Convict nothing. "
                   "Mandatory next step: the frame audit (mine ~30 champion-actor "
                   "plies with the JVM under the same judge and check the sign) "
                   "BEFORE any build.")
        per_stratum = {"A": "NOT_CONVICTED (G2)", "B": "NOT_CONVICTED (G2)",
                       "C": "NOT_CONVICTED (G2)"}
        mints = True
    else:
        branch = "G3"
        per_stratum = {}
        for L in ("A", "B"):
            if not gate[L]:
                per_stratum[L] = "INCONCLUSIVE_BY_CONSTRUCTION"
                continue
            v, preds = _stratum_verdict(strata_stats[L], C)
            for k, val in preds.items():
                predicates[f"{L}_{k}"] = val
            raw_convict = (v == "CONVICT")
            if raw_convict:
                sc = sign_checks.get(L)
                corroborated = sign_corroborates(sc)
                predicates[f"{L}_tier1_corroborated"] = corroborated
                if not corroborated:
                    v = "CONVICTED_UNCORROBORATED"
                mints = True
                candidate_mapping[L] = CANDIDATE_MAP[L]
            per_stratum[L] = v
        per_stratum["C"] = "CONTROL — no independent verdict"
        verdict = f"LOCALISED — A={per_stratum['A']}, B={per_stratum['B']}."

    # Uniform gate override (applies to every branch above, incl. C, incl. any
    # A/B verdict computed before its gate status was checked): PREREG §6's gate
    # rule is general ("a stratum with n < min_n_gate is INCONCLUSIVE_BY_
    # CONSTRUCTION"), not scoped to G0.
    for L in STRATA_LETTERS:
        if not gate[L]:
            per_stratum[L] = "INCONCLUSIVE_BY_CONSTRUCTION"
            candidate_mapping.pop(L, None)
    per_stratum["S3"] = "NOT TESTED BY THIS DESIGN"

    predicates["global_branch"] = branch
    return {
        "global_branch": branch,
        "verdict": verdict,
        "predicates": predicates,
        "per_stratum": per_stratum,
        "candidate_mapping": candidate_mapping,
        "mints_claim_id": mints,
        "z_gate": Z_GATE, "z_bonf_threshold": Z_BONF2,
    }


# --------------------------------------------------------------------------- #
# Driver                                                                        #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="JCZ disagreement-mining analyzer — implements MINING_PREREG.md "
                    "§6's decision map literally over scored oracle_score_pilot "
                    "records joined against STRATA.json.")
    ap.add_argument("--strata", required=True)
    ap.add_argument("--primary-records", nargs="+", required=True,
                    help="directories of *.json per-position records from the "
                         "clair-puct (primary) leg, e.g. <out_root>/clair-puct/records/")
    ap.add_argument("--secondary-records", nargs="*", default=[],
                    help="directories of *.json per-position records from the "
                         "tier1-greedy (secondary) leg")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    strata = json.loads(Path(a.strata).read_text())
    strata_rows = index_strata_rows(strata)
    min_n_gate = strata.get("min_n_gate")

    primary_all = load_records(a.primary_records)
    secondary_all = load_records(a.secondary_records) if a.secondary_records else []

    primary, primary_unmatched = join_records(primary_all, strata_rows)
    secondary, secondary_unmatched = join_records(secondary_all, strata_rows)
    assert_full_join(primary_unmatched, "primary")
    assert_full_join(secondary_unmatched, "secondary")

    strat_stats = {L: stratum_stats([r for r in primary if r.get("stratum") == L], L)
                  for L in STRATA_LETTERS}

    pri_by_stratum = {L: [r for r in primary if r.get("stratum") == L] for L in ("A", "B")}
    sec_by_stratum = {L: [r for r in secondary if r.get("stratum") == L] for L in ("A", "B")}
    sign_checks = {L: (sign_agreement(pri_by_stratum[L], sec_by_stratum[L])
                       if sec_by_stratum[L] else None)
                  for L in ("A", "B")}

    dec = decide(strat_stats, min_n_gate, sign_checks)

    cls_breakdown = {L: ply_class_breakdown([r for r in primary if r.get("stratum") == L])
                     for L in STRATA_LETTERS}

    disagreement_rate, disagreement_rate_source = find_disagreement_rate(strata)

    leaf_gap_pairs = [(r["our_leaf_gap"], r["delta"]) for r in primary
                      if r.get("our_leaf_gap") is not None]
    pearson_r = pearson([x for x, _ in leaf_gap_pairs], [y for _, y in leaf_gap_pairs])

    search_pick_rows = [r for r in primary if r.get("search_pick") is not None]
    frac_search_eq_pick_b = (
        sum(1 for r in search_pick_rows if r["search_pick"] == r.get("pick_b"))
        / len(search_pick_rows) if search_pick_rows else None)

    def _sign(vals):
        m = _mean(vals)
        return None if not vals else (0 if m == 0 else (1 if m > 0 else -1))

    out = {
        "schema": SCHEMA,
        "prereg": "measurement/jcz_mining_20260809/MINING_PREREG.md",
        "statistic": "delta = mean(V_B - V_A) = V(JCZ pick) - V(our pick); "
                     "pick_a = ours, pick_b = JCZ's; delta > 0 means JCZ's pick "
                     "was better",
        "min_n_gate": min_n_gate,
        "k_late": strata.get("k_late"),
        "n_target": strata.get("n_target"),
        "join": {
            "primary_unmatched_rids": primary_unmatched,
            "secondary_unmatched_rids": secondary_unmatched,
        },
        "A": strat_stats["A"], "B": strat_stats["B"], "C": strat_stats["C"],
        "decision": dec,
        "tier1_sign_check": {
            "note": "SIGN ONLY — the Tier-1 judge is out-of-family and noisier; "
                   "its MAGNITUDE is never compared to the primary's. "
                   "'secondary_mean_sign' below is the sign of the secondary's "
                   "own per-stratum mean, not its size.",
            "A": sign_checks["A"], "B": sign_checks["B"],
            "secondary_mean_sign": {
                L: _sign([float(r["delta"]) for r in sec_by_stratum[L]])
                for L in ("A", "B")},
        },
        "reported_not_decisive": {
            "ply_class": cls_breakdown,
            "disagreement_rate": disagreement_rate,
            "disagreement_rate_source": disagreement_rate_source,
            "pearson_r_leaf_gap_vs_delta": pearson_r,
            "n_leaf_gap_pairs": len(leaf_gap_pairs),
            "fraction_search_pick_eq_pick_b": frac_search_eq_pick_b,
            "n_search_pick_rows": len(search_pick_rows),
        },
        "scoring_health": {
            "primary": scoring_health(primary_all),
            "secondary": scoring_health(secondary_all) if secondary_all else None,
        },
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("min_n_gate", "A", "B", "C", "decision")}, indent=2))
    print(f"[analyze_mining] -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
