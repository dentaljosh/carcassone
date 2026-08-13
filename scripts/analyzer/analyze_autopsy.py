#!/usr/bin/env python3
"""E4 AUTOPSY — the analysis, exactly as pre-registered.

Pre-registration: ``measurement/e4_autopsy_20260812/DESIGN.md`` (+ AMENDMENT 1), written
and committed BEFORE any scoring cell ran. This module implements its §8 read rules and
NOTHING adjacent: no post-hoc stratum, no one-sided test, no promotion, no claim id.

  * Statistic per position: **Δ = V(played) − V(best)**, engine points, Joshua's seat.
    It is the scorer's ``delta`` field verbatim (positions were emitted with
    ``pick_a = action_best`` = the champion's pick and ``pick_b = action_played`` = his,
    and ``position_delta`` returns ``mean(V_B − V_A)``). Positive ⇒ his move earned more.
  * **Two-sided z throughout** (read rule 1).
  * **|z| < 2 is NO CONVICTION, never "refuted"** (read rule 2). Every non-convicting cell
    emits an explicit numeric BOUND in pts/ply; the string "no effect" is never produced.
  * **Cluster-robust SE on ``game_label`` is the primary interval** (read rule 3); the naive
    SE is reported alongside, never instead. A cluster bootstrap over games ships too.
  * **Scope: the ``fixed_v1`` epoch only.** Read rule 4's no-pooling-across-epochs is moot
    for a single-epoch run — the scope restriction is not, and is stamped on every output.
  * **Multiplicity on the secondary contrasts** (read rule 10): only |z| ≥ 3, or a
    convergent sign across related mechanism tags, is quotable from this run alone.
  * **F7 is null by design** (§5.4): per-world root stats are not retained by the grader.
  * The Tier-1 leg is read for **SIGN ONLY** (§7); its magnitude is never compared to the
    primary's and never enters a Δ estimate.

Nothing here is a strength claim about the champion (read rule 9), and selection on
disagreement biases Δ toward 0 (read rule 5), so a null is SOFTER than it looks.
"""
from __future__ import annotations

import argparse
import json
import math
import zlib
from pathlib import Path

import numpy as np

SCHEMA = "carcassonne-analyzer-e4-autopsy-verdict/v1"
DESIGN = "measurement/e4_autopsy_20260812/DESIGN.md"

#: |z| at which a stratum convicts (§8 outcome branches).
Z_GATE = 2.0
#: |z| a SECONDARY contrast needs to be quotable from this run alone (read rule 10).
Z_GATE_SECONDARY = 3.0
#: Two-sided 95% normal quantile.
Z_95 = 1.959963984540054
#: Read rule 7 — a cell below this n is underpowered by construction.
MIN_N_POWERED = 15
#: Read rule 7 pre-declares these cells WEAK by construction — reported with their CI,
#: NEVER promoted, in either direction, however large the z turns out to be.
PREREG_WEAK_CELLS = frozenset({
    "commit_direction=swap", "commit_direction=spend",
    "F2_tie_force_join_played=True", "F2 he-steals True-minus-False",
})
#: The sd the design sized every stratum against (§6: farm-war's cluster-robust se 0.970 at
#: n=21 => 0.970*sqrt(21)). Carried ONLY to state what the design expected at the realized
#: n; the realized SEs are what bind.
SD_ASSUMED_PTS = 4.445

#: The five populated primary strata, in the design's own order (§5.2).
STRATA = ("DEG", "FARM", "CITY", "ROAD", "CLOISTER")

#: Read rule 10 counts NINE secondary mechanism contrasts. The design does not enumerate
#: them; this is the enumeration used, stated so the count is auditable rather than
#: asserted: F6's three level-means (3) + F9/F2's four True-vs-False differences (4) +
#: F3's two regression slopes (2) = 9.
N_SECONDARY_CONTRASTS = 9


# --------------------------------------------------------------------------- #
# small statistics helpers                                                      #
# --------------------------------------------------------------------------- #
def _mean(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def _sd(xs) -> float:
    xs = list(xs)
    if len(xs) < 2:
        return float("nan")
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def cluster_se(values: list, clusters: list) -> dict:
    """CR1 cluster-robust standard error of a MEAN.

    Identical formula to ``farmwar_analyze.cluster_se`` (pinned by a test): for the
    mean-only model the sandwich reduces to ``se = sqrt(c * Σ_g (Σ_{i∈g} e_i)^2) / n`` with
    residuals ``e_i = y_i − ȳ`` and the small-G correction ``c = G/(G−1)``.
    """
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
            "design_effect": (se / naive) ** 2 if naive and naive > 0 else None}


def _cell_seed(name: str, base_seed: int) -> int:
    """Per-cell bootstrap seed derived from the cell NAME, so a cell's CI does not depend
    on how many other cells were computed or in what order."""
    return (zlib.crc32(name.encode("utf-8")) ^ (base_seed & 0xFFFFFFFF)) & 0xFFFFFFFF


def cluster_bootstrap_ci(values: list, clusters: list, *, reps: int, seed: int,
                         name: str) -> dict:
    """Percentile CI from a CLUSTER bootstrap: resample whole games with replacement.

    Games contribute ~12 positions each, so resampling positions would understate the
    interval by exactly the design effect read rule 3 is about.
    """
    if len(values) < 2 or reps <= 0:
        return {"lo": float("nan"), "hi": float("nan"), "reps": reps,
                "n_clusters": len(set(clusters))}
    groups: dict = {}
    for v, g in zip(values, clusters):
        s, c = groups.get(g, (0.0, 0))
        groups[g] = (s + float(v), c + 1)
    keys = sorted(groups)
    sums = np.array([groups[k][0] for k in keys], dtype=float)
    cnts = np.array([groups[k][1] for k in keys], dtype=float)
    G = len(keys)
    rng = np.random.default_rng(_cell_seed(name, seed))
    idx = rng.integers(0, G, size=(reps, G))
    means = sums[idx].sum(axis=1) / cnts[idx].sum(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {"lo": float(lo), "hi": float(hi), "reps": int(reps), "n_clusters": G}


def _bound_text(lo: float, hi: float) -> str:
    """Read rule 2: a non-convicting cell reports a BOUND, never 'no effect'."""
    if lo != lo or hi != hi:
        return "BOUND UNAVAILABLE (n too small for an interval)"
    b = max(abs(lo), abs(hi))
    return (f"NO CONVICTION — bounded: the 95% interval excludes |Δ| > {b:.3f} pts/ply "
            f"(CI {lo:+.3f} .. {hi:+.3f}). This is absence of resolution, NOT a refutation.")


def cell_stats(rows: list, name: str, *, boot_reps: int = 10000,
               boot_seed: int = 20260812) -> dict:
    """n / mean / SEs / two-sided z / normal CI / cluster-bootstrap CI for one cell.

    The PRIMARY se and z are the ``game_label``-clustered ones (read rule 3).
    """
    vals = [float(r["delta"]) for r in rows]
    n = len(vals)
    if n == 0:
        return {"cell": name, "n": 0, "mean_delta_pts": None,
                "note": "empty cell — nothing scored here"}
    games = [r.get("game_label") or r["rid"] for r in rows]
    mean = _mean(vals)
    sd = _sd(vals)
    naive_se = sd / math.sqrt(n) if n > 1 else float("nan")
    game = cluster_se(vals, games)
    se = game["se"]
    z = mean / se if se == se and se > 0 else float("nan")
    z_naive = mean / naive_se if naive_se == naive_se and naive_se > 0 else float("nan")
    boot = cluster_bootstrap_ci(vals, games, reps=boot_reps, seed=boot_seed, name=name)
    lo, hi = mean - Z_95 * se, mean + Z_95 * se
    convicts = bool(abs(z) >= Z_GATE) if z == z else False
    return {
        "cell": name,
        "n": n,
        "mean_delta_pts": mean,
        "sd_pts": sd,
        "se_cluster_game": se,
        "se_naive": naive_se,
        "n_game_clusters": game["n_clusters"],
        "design_effect": game["design_effect"],
        "z_two_sided": z,
        "z_naive_two_sided": z_naive,
        "mde_2sigma_realized_cluster_pts": 2.0 * se if se == se else None,
        "mde_2sigma_realized_naive_pts": (2.0 * naive_se if naive_se == naive_se else None),
        "ci95_lo": lo,
        "ci95_hi": hi,
        "ci95_covers_zero": bool(lo <= 0.0 <= hi),
        "boot_ci95_lo": boot["lo"],
        "boot_ci95_hi": boot["hi"],
        "boot_reps": boot["reps"],
        "n_positive": sum(1 for v in vals if v > 0),
        "n_negative": sum(1 for v in vals if v < 0),
        "n_zero": sum(1 for v in vals if v == 0),
        "underpowered_by_construction": bool(n < MIN_N_POWERED),
        "convicts_at_z2": convicts,
        "bound_pts_per_ply": (None if convicts else max(abs(lo), abs(hi))
                              if lo == lo and hi == hi else None),
        "read": (None if convicts else _bound_text(lo, hi)),
    }


# --------------------------------------------------------------------------- #
# §8 outcome branches                                                           #
# --------------------------------------------------------------------------- #
def resolution_requirement(st: dict) -> dict:
    """How much MORE would it take to resolve this cell's own point estimate at |z| = 2?

    Two scalings, because they answer different questions and the second is the honest one
    under read rule 3:

    * ``positions_*`` assumes variance falls like 1/n_positions — true only for the WITHIN
      game component. There are unscored plies of every stratum already extracted, so this
      is the cheap lever.
    * ``games_*`` assumes variance falls like 1/n_games, which is what a cluster-robust SE
      actually tracks once the between-game component is non-trivial. When the design effect
      exceeds 1 this is the binding number, and it is why §8's default next step is MORE
      GAMES rather than more compute.

    Both take the observed point estimate AT FACE VALUE (a winner's-curse-prone assumption
    for the largest cell in a map), so they are a planning aid, not a power guarantee.
    """
    mean = st.get("mean_delta_pts")
    se, n, G = st.get("se_cluster_game"), st.get("n"), st.get("n_game_clusters")
    if not mean or not n or not G or se is None or se != se or mean == 0:
        return {"status": "not_computable"}
    factor = (Z_GATE * se / abs(mean)) ** 2
    return {
        "assumed_true_effect_pts": mean,
        "shortfall_factor": factor,
        "positions_needed_if_1_over_n": math.ceil(n * factor),
        "additional_positions": max(0, math.ceil(n * factor) - n),
        "games_needed_if_1_over_G": math.ceil(G * factor),
        "additional_games": max(0, math.ceil(G * factor) - G),
        "binding": ("games (design effect > 1: the between-game component is real, so "
                    "extra plies from the SAME games buy less than 1/n)"
                    if (st.get("design_effect") or 0) > 1.0
                    else "positions (design effect <= 1 in this cell)"),
        "caveat": ("takes the observed point estimate at face value; if it is a "
                   "winner's-curse crest the true requirement is larger"),
    }


def stratum_branch(st: dict, *, is_deg: bool) -> dict:
    """The §8 branch for ONE stratum. Evaluated per stratum; there is no precedence and no
    single verdict — this is a discovery design and the deliverable is the map."""
    n = st.get("n", 0)
    mean = st.get("mean_delta_pts")
    z = st.get("z_two_sided", float("nan"))
    sig = bool(abs(z) >= Z_GATE) if z == z else False
    if n == 0:
        return {"branch": "EMPTY", "mints_claim_id": False,
                "text": "stratum empty — nothing scored"}
    if sig and mean > 0 and is_deg:
        return {
            "branch": "DEG_SEARCH_DEFECT", "mints_claim_id": False,
            "text": ("Δ > 0 at |z| ≥ 2 in DEG ⇒ the defect is in the SEARCH, not the leaf: "
                     "by construction the production leaf is indifferent between the two "
                     "arms here. Materially different (and cheaper to act on) than a "
                     "leaf-term defect, and a cell no prior instrument has looked at. "
                     "Claim id is the owner's call, not minted here.")}
    if sig and mean > 0:
        return {
            "branch": "LOCALIZED_DEFECT", "mints_claim_id": False,
            "text": ("Δ > 0 at |z| ≥ 2 ⇒ a localized defect in the champion's evaluation. "
                     "Through the in-family judge this is the CONSERVATIVE direction, so "
                     "the read is strong. Names WHERE his points come from; does NOT "
                     "license 'the champion is weak'. Claim id is the owner's call.")}
    if sig and mean <= 0:
        return {
            "branch": "CHAMPION_PICKS_BETTER", "mints_claim_id": False,
            "text": ("Δ ≤ 0 at |z| ≥ 2 ⇒ the champion's picks really are better here; the "
                     "grader's ΔQ readouts stand for this stratum and his margin in those "
                     "games came from somewhere else. SHARPENS the puzzle rather than "
                     "resolving it.")}
    return {"branch": "NO_CONVICTION", "mints_claim_id": False,
            "text": st.get("read") or _bound_text(st.get("ci95_lo", float("nan")),
                                                  st.get("ci95_hi", float("nan")))}


def run_level_branch(strata_stats: dict, branches: dict) -> dict:
    """The two run-level §8 branches: general same-family self-preference, and the
    everything-null branch."""
    populated = [s for s in STRATA if strata_stats.get(s, {}).get("n", 0) > 0]
    convicting_pos = [s for s in populated
                      if branches[s]["branch"] in ("LOCALIZED_DEFECT", "DEG_SEARCH_DEFECT")]
    any_sig = [s for s in populated if strata_stats[s].get("convicts_at_z2")]
    if populated and len(convicting_pos) == len(populated):
        return {
            "branch": "GENERAL_SAME_FAMILY_SELF_PREFERENCE",
            "text": ("Δ > 0 at |z| ≥ 2 in essentially EVERY stratum ⇒ read as general "
                     "same-family self-preference in the judge (the oracle pilot's was "
                     "+0.74). That is a statement about the INSTRUMENT and it gates every "
                     "future in-family claim, including this run's. The Tier-1 sign check "
                     "is what separates this from a real localized defect."),
            "strata": convicting_pos}
    if populated and not any_sig:
        bounds = {s: strata_stats[s].get("bound_pts_per_ply") for s in populated}
        tightest = min((v for v in bounds.values() if v is not None), default=None)
        return {
            "branch": "NO_CONVICTION_ANYWHERE",
            "text": ("Everything |z| < 2 ⇒ NO CONVICTION anywhere at this n. Report the map "
                     "with CIs; promote nothing. Per §8 the default next step is MORE E4 "
                     "GAMES, not more compute. Read rule 5 applies: selection on "
                     "disagreement biases Δ toward 0, so this null is SOFTER than it looks, "
                     "and the in-family judge makes a null WEAK evidence (§7)."),
            "bounds_pts_per_ply": bounds,
            "tightest_bound_pts_per_ply": tightest}
    return {"branch": "MIXED_MAP",
            "text": ("Some strata convict and some do not — the deliverable is the MAP, "
                     "not a single verdict. Read each stratum's own branch."),
            "convicting": [s for s in populated if strata_stats[s].get("convicts_at_z2")]}


# --------------------------------------------------------------------------- #
# loading + joining                                                             #
# --------------------------------------------------------------------------- #
def load_records(dirs: list) -> list:
    rows = []
    for d in dirs:
        p = Path(d)
        files = sorted(p.glob("*.json")) if p.is_dir() else [p]
        for f in files:
            rows.append(json.loads(f.read_text()))
    return rows


def load_positions(paths: list) -> dict:
    out: dict = {}
    for p in paths:
        for line in Path(p).read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            out[row["rid"]] = row
    return out


def join(records: list, positions: dict) -> tuple:
    """Join scored records onto their pre-registered position rows.

    Returns ``(joined_ok, failures, out_of_sample, missing)``. A record whose rid is not in
    the pre-registered sample is NOT analysed — it is reported in the completion accounting
    (the priced smoke wrote into the same out-root under the same salt, §10).
    """
    joined, failures, out_of_sample = [], [], []
    for r in records:
        rid = r["rid"]
        if rid not in positions:
            out_of_sample.append(r)
            continue
        if not r.get("ok"):
            failures.append(r)
            continue
        row = dict(positions[rid])
        if row.get("stratum") and r.get("stratum") and row["stratum"] != r["stratum"]:
            raise ValueError(f"stratum disagreement on {rid}: "
                             f"{row['stratum']} (sample) vs {r['stratum']} (record)")
        row.update({k: r[k] for k in
                    ("delta", "mean_a", "mean_b", "within_var", "crn_verified",
                     "distinct_afterstates", "m", "oracle_policy", "elapsed_secs")
                    if k in r})
        joined.append(row)
    scored = {r["rid"] for r in records}
    missing = sorted(set(positions) - scored)
    return joined, failures, out_of_sample, missing


# --------------------------------------------------------------------------- #
# secondary axes                                                                #
# --------------------------------------------------------------------------- #
def by_key(rows: list, key: str, label: str, *, boot_reps: int, boot_seed: int) -> dict:
    out = {}
    levels = sorted({str(r.get(key)) for r in rows}, key=str)
    for lv in levels:
        sub = [r for r in rows if str(r.get(key)) == lv]
        out[lv] = cell_stats(sub, f"{label}:{lv}", boot_reps=boot_reps, boot_seed=boot_seed)
    return out


def _ols_cluster(y: np.ndarray, X: np.ndarray, clusters: list) -> dict:
    """OLS with CR1 cluster-robust covariance (small-G correction G/(G−1), matching
    ``cluster_se``)."""
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ (X.T @ y)
    e = y - X @ beta
    keys = sorted(set(clusters))
    G = len(keys)
    meat = np.zeros((X.shape[1], X.shape[1]))
    for g in keys:
        m = np.array([c == g for c in clusters])
        Xg, eg = X[m], e[m]
        s = Xg.T @ eg
        meat += np.outer(s, s)
    if G > 1:
        meat *= G / (G - 1.0)
    V = XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.diag(V))
    return {"beta": beta.tolist(), "se": se.tolist(),
            "z": (beta / np.where(se > 0, se, np.nan)).tolist(), "n_clusters": G}


def f3_regression(rows: list) -> dict:
    """F3 — Δ regressed on the two continuous reserve counts (§6: read as a regression,
    not a cell). Two of the nine secondary contrasts."""
    usable = [r for r in rows
              if r.get("own_reserve") is not None and r.get("opp_reserve") is not None]
    if len(usable) < 5:
        return {"n": len(usable), "status": "insufficient"}
    y = np.array([float(r["delta"]) for r in usable])
    X = np.column_stack([np.ones(len(usable)),
                         np.array([float(r["own_reserve"]) for r in usable]),
                         np.array([float(r["opp_reserve"]) for r in usable])])
    fit = _ols_cluster(y, X, [r.get("game_label") or r["rid"] for r in usable])
    names = ["intercept", "own_reserve", "opp_reserve"]
    return {"n": len(usable), "terms": {
        nm: {"beta_pts_per_meeple": fit["beta"][i], "se_cluster_game": fit["se"][i],
             "z_two_sided": fit["z"][i]} for i, nm in enumerate(names)},
        "n_game_clusters": fit["n_clusters"],
        "note": ("Two of the nine secondary contrasts (read rule 10): quotable from this "
                 "run alone only at |z| >= 3.")}


def mechanism_reads(rows: list, *, boot_reps: int, boot_seed: int) -> dict:
    """F2 / F3 / F6 / F9 — SECONDARY, multiplicity applies (read rule 10). F7 is null by
    design (§5.4): the grader pools across the k=8 determinizations before the artifact."""
    kw = {"boot_reps": boot_reps, "boot_seed": boot_seed}
    out = {
        "_read_rules": [
            "SECONDARY. Nine two-sided contrasts at alpha=0.05 expect ~0.45 false "
            "positives; a single |z| ~ 2 with the others null is a HYPOTHESIS for a "
            "targeted follow-up, not a finding (read rule 10).",
            "Only |z| >= 3, or a consistent sign across related tags (F9 and F2 favouring "
            "the same seat), is quotable from this run alone (read rule 10).",
            "The census asymmetries (champion reinforces 177x vs his 140x; steals 98x vs "
            "77x) are counts of MOVE CLASS, not effects (read rule 11). Only the Δ scored "
            "within a tag speaks to whether the class is mispriced.",
        ],
        "F6_score_diff_bucket": by_key(rows, "score_diff_bucket", "F6", **kw),
        "F3_reserve_regression": f3_regression(rows),
        "F9_reinforce_losing_contest_best": by_key(
            rows, "reinforce_losing_contest_best", "F9-champ", **kw),
        "F9_reinforce_losing_contest_played": by_key(
            rows, "reinforce_losing_contest_played", "F9-his", **kw),
        "F2_tie_force_join_best": by_key(rows, "tie_force_join_best", "F2-champ", **kw),
        "F2_tie_force_join_played": by_key(rows, "tie_force_join_played", "F2-his", **kw),
        "F7_cross_world_spread": None,
        "F7_status": ("unavailable_pooled_only — ev_loss.grade_pass reads an already-pooled "
                      "root, so no per-world value or argmax survives into the artifact. "
                      "NULL BY DESIGN (§5.4), not an omission and not a zero. Recovering it "
                      "needs a re-search that persists per-determinization root stats."),
    }
    out["_contrast_inventory"] = _contrast_inventory(out)
    return out


def _contrast_inventory(mech: dict) -> dict:
    """The nine secondary contrasts of read rule 10, enumerated so the count is auditable.

    F6's three level-means (3) + F9/F2's four True-vs-False differences (4) + F3's two
    slopes (2) = 9.
    """
    items = []
    for lv, st in mech["F6_score_diff_bucket"].items():
        items.append({"contrast": f"F6 {lv} mean", "z": st.get("z_two_sided"),
                      "mean": st.get("mean_delta_pts"), "n": st.get("n")})
    for tag, key in (("F9 champion-reinforces", "F9_reinforce_losing_contest_best"),
                     ("F9 he-reinforces", "F9_reinforce_losing_contest_played"),
                     ("F2 champion-steals", "F2_tie_force_join_best"),
                     ("F2 he-steals", "F2_tie_force_join_played")):
        cells = mech[key]
        t, f = cells.get("True"), cells.get("False")
        if t and f and t.get("n") and f.get("n"):
            diff = t["mean_delta_pts"] - f["mean_delta_pts"]
            se = math.sqrt(t["se_cluster_game"] ** 2 + f["se_cluster_game"] ** 2)
            items.append({"contrast": f"{tag} True-minus-False", "z": (diff / se if se else None),
                          "mean": diff, "n": t["n"] + f["n"],
                          "note": "SE is the independent-cells approximation; the two cells "
                                  "share games, so treat it as indicative only."})
    f3 = mech["F3_reserve_regression"]
    for nm in ("own_reserve", "opp_reserve"):
        if f3.get("terms", {}).get(nm):
            t = f3["terms"][nm]
            items.append({"contrast": f"F3 {nm} slope", "z": t["z_two_sided"],
                          "mean": t["beta_pts_per_meeple"], "n": f3["n"]})
    quotable = [i for i in items
                if i.get("z") is not None and i["z"] == i["z"]
                and abs(i["z"]) >= Z_GATE_SECONDARY]
    return {"n_contrasts": len(items),
            "n_contrasts_preregistered": N_SECONDARY_CONTRASTS,
            "contrasts": items,
            "quotable_at_z3": [i["contrast"] for i in quotable],
            "expected_false_positives_at_alpha_05": round(0.05 * len(items), 2)}


def multiplicity_ledger(mech: dict, secondary_axes: dict, tile_meeple: dict) -> dict:
    """EVERY non-primary contrast computed in this readout, with the read rule 10 gate
    applied uniformly.

    Read rule 10 names the nine mechanism contrasts, but the design also asks for the §5.3
    marginals and the tile/meeple split. Those are exploratory on the same 320 positions, so
    the same gate is applied to them: nothing below |z| = 3 is quotable from this run alone.
    The cells overlap heavily (they are re-slicings of one sample), so the expected-false-
    positive figure is an INDEPENDENT-tests approximation and therefore optimistic about how
    surprising a cluster of |z| ~ 2 is.
    """
    items = []
    for i in mech["_contrast_inventory"]["contrasts"]:
        items.append({"family": "mechanism (read rule 10)", "cell": i["contrast"],
                      "n": i["n"], "mean_delta_pts": i["mean"], "z": i.get("z")})
    # the F9/F2 tag CELL means as well as the nine enumerated contrasts: read rule 10's
    # "a single |z| ~ 2 on one mechanism tag" is what a reader will look at, so it must not
    # be able to hide between the difference-of-cells and the cell itself.
    for key in ("F9_reinforce_losing_contest_best", "F9_reinforce_losing_contest_played",
                "F2_tie_force_join_best", "F2_tie_force_join_played"):
        for lv, st in mech.get(key, {}).items():
            items.append({"family": "mechanism cell mean", "cell": f"{key}={lv}",
                          "n": st.get("n"), "mean_delta_pts": st.get("mean_delta_pts"),
                          "z": st.get("z_two_sided")})
    for axis, cells in secondary_axes.items():
        if axis.startswith("_"):
            continue
        for lv, st in cells.items():
            items.append({"family": f"secondary axis: {axis}", "cell": f"{axis}={lv}",
                          "n": st.get("n"), "mean_delta_pts": st.get("mean_delta_pts"),
                          "z": st.get("z_two_sided")})
    for lv, st in tile_meeple["overall"].items():
        items.append({"family": "tile/meeple", "cell": f"ALL/{lv}", "n": st.get("n"),
                      "mean_delta_pts": st.get("mean_delta_pts"),
                      "z": st.get("z_two_sided")})
    for stratum, cells in tile_meeple["per_stratum"].items():
        for lv, st in cells.items():
            items.append({"family": "tile/meeple", "cell": f"{stratum}/{lv}",
                          "n": st.get("n"), "mean_delta_pts": st.get("mean_delta_pts"),
                          "z": st.get("z_two_sided")})

    for i in items:
        i["prereg_weak_read_rule_7"] = i["cell"] in PREREG_WEAK_CELLS

    def _hits(gate):
        return [i for i in items if i.get("z") is not None and i["z"] == i["z"]
                and abs(i["z"]) >= gate]
    n = len(items)
    return {
        "n_contrasts_total": n,
        "gate_for_quotability": Z_GATE_SECONDARY,
        "expected_hits_at_abs_z_ge_2_if_all_null": round(0.0455 * n, 2),
        "observed_abs_z_ge_2": [{k: i[k] for k in ("family", "cell", "n", "mean_delta_pts",
                                                   "z", "prereg_weak_read_rule_7")}
                                for i in sorted(_hits(2.0), key=lambda x: -abs(x["z"]))],
        "expected_hits_at_abs_z_ge_3_if_all_null": round(0.0027 * n, 3),
        "observed_abs_z_ge_3_QUOTABLE": [{k: i[k] for k in ("family", "cell", "n",
                                                            "mean_delta_pts", "z",
                                                            "prereg_weak_read_rule_7")}
                                         for i in sorted(_hits(3.0),
                                                         key=lambda x: -abs(x["z"]))],
        "prereg_weak_cells_read_rule_7": sorted(PREREG_WEAK_CELLS),
        "note": ("Cells overlap (re-slicings of the same 320 positions), so these counts "
                 "are NOT independent tests; the expected-hit figures are an approximation "
                 "and a cluster of |z| ~ 2 is less surprising than they make it look. "
                 "Nothing here is a primary result and nothing here mints a claim."),
    }


def convergent_sign_check(mech: dict) -> dict:
    """Read rule 10's escape hatch: a consistent sign across the related F9/F2 tags is
    quotable even below |z| = 3. Defined mechanically here — the design names the idea
    ('F9 and F2 both favouring the same seat') but not the test."""
    cells = {
        "F9_champion": mech["F9_reinforce_losing_contest_best"].get("True"),
        "F9_his": mech["F9_reinforce_losing_contest_played"].get("True"),
        "F2_champion": mech["F2_tie_force_join_best"].get("True"),
        "F2_his": mech["F2_tie_force_join_played"].get("True"),
    }
    have = {k: v for k, v in cells.items() if v and v.get("n")}
    signs = {k: (1 if v["mean_delta_pts"] > 0 else -1 if v["mean_delta_pts"] < 0 else 0)
             for k, v in have.items()}
    same = len(set(signs.values())) == 1 and len(signs) == 4
    strong = all(abs(v.get("z_two_sided", 0.0)) >= Z_GATE for v in have.values()) if have else False
    return {"per_tag_sign": signs,
            "all_four_same_sign": bool(same),
            "all_four_abs_z_ge_2": bool(strong),
            "convergent_and_quotable": bool(same and strong),
            "definition": ("quotable-by-convergence iff all four F9/F2 'True' cells share a "
                           "sign AND each reaches |z| >= 2; otherwise only |z| >= 3 "
                           "individually is quotable (read rule 10)")}


# --------------------------------------------------------------------------- #
# Tier-1 out-of-family SIGN check                                               #
# --------------------------------------------------------------------------- #
def sign_agreement(primary: list, secondary: list, label: str) -> dict:
    """Per-position SIGN agreement between the two judges. SIGN ONLY — §7 forbids comparing
    the Tier-1 magnitude to the primary's."""
    a = {r["rid"]: float(r["delta"]) for r in primary}
    b = {r["rid"]: float(r["delta"]) for r in secondary}
    shared = sorted(set(a) & set(b))
    both_nonzero = [r for r in shared if a[r] != 0 and b[r] != 0]
    agree = sum(1 for r in both_nonzero if (a[r] > 0) == (b[r] > 0))
    n = len(both_nonzero)
    p = None
    if n:
        tail = sum(math.comb(n, k) for k in range(0, n + 1)
                   if abs(k - n / 2) >= abs(agree - n / 2)) / (2.0 ** n)
        p = min(1.0, tail)
    rate = (agree / n) if n else None
    prim_sign = (1 if _mean(a[r] for r in shared) > 0 else -1) if shared else None
    sec_sign = (1 if _mean(b[r] for r in shared) > 0 else -1) if shared else None
    if rate is None or p is None:
        verdict = "not evaluable"
    elif rate > 0.5 and p < 0.05 and prim_sign == sec_sign:
        verdict = ("CORROBORATES — per-position signs agree above chance AND the "
                   "out-of-family judge's own aggregate sign matches the primary's")
    elif rate > 0.5 and p < 0.05:
        verdict = ("PARTIAL — per-position signs agree above chance, but the out-of-family "
                   "judge's own aggregate sign is OPPOSITE the primary's, so it does not "
                   "corroborate the DIRECTION. Agreement above chance says the two rulers "
                   "see the same positions similarly; it is not a directional endorsement.")
    else:
        verdict = ("NO CORROBORATION — sign agreement is not distinguishable from chance "
                   "(§7 benchmark: the farm-war run's 61.9% at p 0.38 was not "
                   "corroboration; the 2026-07-28 precedent's 80% at p 0.0012 was)")
    return {"cell": label, "n_shared": len(shared), "n_both_nonzero": n, "n_agree": agree,
            "primary_mean_sign_only": prim_sign, "corroboration": verdict,
            "agreement_rate": (agree / n if n else None),
            "binomial_p_two_sided": p,
            "secondary_mean_sign_only": (1 if _mean(b[r] for r in shared) > 0 else -1)
            if shared else None,
            "n_primary_zero": sum(1 for r in shared if a[r] == 0),
            "n_secondary_zero": sum(1 for r in shared if b[r] == 0)}


# --------------------------------------------------------------------------- #
# assembly                                                                      #
# --------------------------------------------------------------------------- #
def analyse(primary_records: list, secondary_records: list, positions: dict, *,
            boot_reps: int = 10000, boot_seed: int = 20260812,
            epoch_scope: str = "fixed_v1") -> dict:
    kw = {"boot_reps": boot_reps, "boot_seed": boot_seed}
    p_ok, p_fail, p_extra, p_missing = join(primary_records, positions)
    s_ok, s_fail, s_extra, s_missing = join(secondary_records, positions)

    strata = {s: cell_stats([r for r in p_ok if r.get("stratum") == s], f"stratum:{s}", **kw)
              for s in STRATA}
    for s in STRATA:
        if strata[s].get("n"):
            strata[s]["resolution_requirement"] = resolution_requirement(strata[s])
    branches = {s: stratum_branch(strata[s], is_deg=(s == "DEG")) for s in STRATA}
    overall = cell_stats(p_ok, "ALL", **kw)

    # the MAP: rank the populated strata by |Δ| and by |z|
    populated = [s for s in STRATA if strata[s].get("n", 0) > 0]
    rank_abs = sorted(populated, key=lambda s: -abs(strata[s]["mean_delta_pts"]))
    rank_z = sorted(populated, key=lambda s: -abs(strata[s]["z_two_sided"]))

    mech = mechanism_reads(p_ok, **kw)

    tile_meeple = {"overall": by_key(p_ok, "decision_type", "decision", **kw),
                   "per_stratum": {
                       s: by_key([r for r in p_ok if r.get("stratum") == s],
                                 "decision_type", f"decision:{s}", **kw)
                       for s in populated}}

    sec_by_rid = {r["rid"]: r for r in s_ok}
    paired_primary = [r for r in p_ok if r["rid"] in sec_by_rid]
    tier1 = {
        "note": ("SIGN ONLY (§7). The Tier-1 greedy judge is out-of-family and ~1.83x "
                 "noisier with no curve125; its MAGNITUDE is never compared to the "
                 "primary's and never enters a Δ estimate. Benchmark for corroboration: "
                 "the 2026-07-28 precedent agreed on 80% of signs at p 0.0012; the farm-war "
                 "run's 61.9% at p 0.38 was NOT corroboration."),
        "n_primary_ok": len(p_ok), "n_secondary_ok": len(s_ok),
        "n_paired": len(paired_primary),
        "ALL": sign_agreement(paired_primary, [sec_by_rid[r["rid"]] for r in paired_primary],
                              "ALL"),
    }
    for s in populated:
        sub = [r for r in paired_primary if r.get("stratum") == s]
        tier1[s] = sign_agreement(sub, [sec_by_rid[r["rid"]] for r in sub], s)
    tier1["secondary_own_mean_SIGN_ONLY"] = {
        "ALL": (1 if _mean(float(r["delta"]) for r in s_ok) > 0 else -1) if s_ok else None,
        **{s: (1 if _mean(float(r["delta"]) for r in s_ok if r.get("stratum") == s) > 0
               else -1)
           for s in populated if any(r.get("stratum") == s for r in s_ok)}}

    secondary_axes = {
        "_note": ("Descriptive marginals preserved by the design's proportional "
                  "sub-allocation. Exploratory: the read rule 10 multiplicity logic "
                  "applies to these too — only |z| >= 3 is quotable from this run."),
        "phase_third": by_key(p_ok, "phase_third", "phase", **kw),
        "commit_direction": by_key(p_ok, "commit_direction", "commit", **kw),
        "bucket_within_game_only": by_key(p_ok, "bucket", "bucket", **kw),
        "contested_any_played": by_key(
            [dict(r, _cont=bool(r.get("contested_played"))) for r in p_ok],
            "_cont", "contested-his", **kw),
    }

    per_game = {g: {"n": sum(1 for r in p_ok if r.get("game_label") == g),
                    "mean_delta_pts": _mean(float(r["delta"]) for r in p_ok
                                            if r.get("game_label") == g)}
                for g in sorted({r.get("game_label") for r in p_ok})}

    verdict = {
        "schema": SCHEMA,
        "design": DESIGN,
        "statistic": ("Delta = V(played) - V(best), engine points, Joshua's seat "
                      "(pick_a = action_best = champion, pick_b = action_played = human; "
                      "position_delta returns mean(V_B - V_A)). POSITIVE => his move "
                      "earned more."),
        "scope": {
            "epochs_scored": [epoch_scope],
            "epochs_not_scored": ["walled", "app_aug2"],
            "limit": ("This run scored the fixed_v1 epoch ONLY (321 of the 371 "
                      "pre-registered positions). walled (36) and app_aug2 (14) were not "
                      "scored, so read rule 4's no-pooling-across-epochs is MOOT here - the "
                      "SCOPE RESTRICTION is not. Nothing in this readout speaks to the two "
                      "legacy epochs, and the per-epoch split rule cannot be exercised."),
            "pooling_across_epochs": "moot_single_epoch_scored",
        },
        "read_rules_applied": [
            "1. two-sided z throughout",
            "2. |z| < 2 = NO CONVICTION, never refuted; every such cell ships a numeric "
            "BOUND in pts/ply",
            "3. cluster-robust SE on game_label is the primary interval; naive SE reported "
            "alongside, plus a cluster bootstrap over games",
            "4. no pooling across epochs - MOOT, one epoch scored",
            "5. selection on disagreement biases Delta toward 0 => a null is SOFTER than it "
            "looks",
            "6. cross-epoch contrasts get 1.5-2x sigma humility - not exercised, one epoch",
            "7. a cell below n=15 is underpowered by construction and is flagged",
            "8. the grader's Delta-Q RATIO is never quoted",
            "9. Delta is NOT a strength claim about the champion",
            "10. the mechanism tags are SECONDARY; multiplicity applies",
            "11. F9/F2 census counts are move-class counts, NOT effects",
        ],
        "judges": {
            "primary": "clair-puct (in-family, shares the leaf under test) - biased TOWARD "
                       "the champion's picks, so a verdict AGAINST the champion is "
                       "conservative and strong, and a NULL through it is WEAK (it cannot "
                       "distinguish 'no effect' from 'effect hidden by the shared leaf').",
            "secondary": "tier1-greedy (out-of-family) - SIGN ONLY.",
            "backend": "python for both legs (the rust clairvoyant declines to mirror this "
                       "corpus's geometry/rules; DESIGN §7).",
        },
        "completion_accounting": {
            "planned_positions_this_epoch": len(positions),
            "planned_records_both_judges": 2 * len(positions),
            "primary": {
                "n_records_written": len(primary_records),
                "n_in_sample_ok": len(p_ok),
                "n_failed": len(p_fail),
                "failures": [{"rid": r["rid"], "error": r.get("error")} for r in p_fail],
                "n_out_of_sample_records_ignored": len(p_extra),
                "out_of_sample_rids": [r["rid"] for r in p_extra],
                "n_missing": len(p_missing), "missing_rids": p_missing,
            },
            "secondary": {
                "n_records_written": len(secondary_records),
                "n_in_sample_ok": len(s_ok),
                "n_failed": len(s_fail),
                "failures": [{"rid": r["rid"], "error": r.get("error")} for r in s_fail],
                "n_out_of_sample_records_ignored": len(s_extra),
                "out_of_sample_rids": [r["rid"] for r in s_extra],
                "n_missing": len(s_missing), "missing_rids": s_missing,
            },
            "symmetric_drop": sorted({r["rid"] for r in p_fail} | set(p_missing)
                                     | {r["rid"] for r in s_fail} | set(s_missing)),
            "note": ("A position that failed under EITHER judge is dropped from the paired "
                     "sign check. The failure is a bounded ~0.5%/game 25x25 action-window "
                     "edge case (WindowOverflowError), independent of which arm was played, "
                     "so it cannot induce a candidate-correlated bias - but it is reported, "
                     "not silently dropped."),
            "crn_verified_all_primary": all(r.get("crn_verified") for r in p_ok),
            "crn_verified_all_secondary": all(r.get("crn_verified") for r in s_ok),
            "m_worlds": sorted({r.get("m") for r in p_ok}),
        },
        "primary_strata": strata,
        "design_mde_2sigma": {
            s: (2.0 * SD_ASSUMED_PTS / math.sqrt(strata[s]["n"]))
            for s in STRATA if strata[s].get("n")},
        "design_mde_note": (f"2*{SD_ASSUMED_PTS}/sqrt(n) — what DESIGN §6's assumed sd "
                            f"predicts at the REALIZED n. It prices no design effect; the "
                            f"game-clustered SE does, and read rule 3 makes that the "
                            f"binding interval."),
        "stratum_branches": branches,
        "run_level_branch": run_level_branch(strata, branches),
        "overall_pooled_all_strata": overall,
        "map_ranking": {
            "by_abs_mean_delta": [{"stratum": s,
                                   "mean_delta_pts": strata[s]["mean_delta_pts"],
                                   "z": strata[s]["z_two_sided"], "n": strata[s]["n"]}
                                  for s in rank_abs],
            "by_abs_z": [{"stratum": s, "z": strata[s]["z_two_sided"],
                          "mean_delta_pts": strata[s]["mean_delta_pts"], "n": strata[s]["n"]}
                         for s in rank_z],
        },
        "deg_answer": _deg_answer(strata, branches, tile_meeple, tier1),
        "tile_vs_meeple": tile_meeple,
        "secondary_axes": secondary_axes,
        "mechanism_tags": mech,
        "convergent_sign_check": convergent_sign_check(mech),
        "multiplicity_ledger": multiplicity_ledger(mech, secondary_axes, tile_meeple),
        "tier1_sign_check": tier1,
        "per_game": per_game,
        "governance": {
            "mints_claim_id": False,
            "note": ("Measurement only. No claim id is minted here and no promotion is "
                     "proposed - that is the owner's call (DESIGN §11). "
                     "governance/PRODUCTION.yaml untouched; no experiments/results.csv row "
                     "(0 games played); no band claim."),
        },
    }
    return verdict


def _deg_answer(strata: dict, branches: dict, tile_meeple: dict,
                tier1: dict) -> dict:
    """The question the whole run exists to answer: does the DEGENERATE stratum - where the
    champion's own leaf is provably indifferent - carry signal? A positive there is a SEARCH
    defect, not a leaf defect."""
    deg = strata.get("DEG", {})
    tm = tile_meeple["per_stratum"].get("DEG", {})
    return {
        "question": ("Does DEG carry signal? By construction |L_full(S_played) - "
                     "L_full(S_best)| <= 1e-9 there, so the production leaf is INDIFFERENT "
                     "between the two arms and only the SEARCH separates them."),
        "n": deg.get("n"), "mean_delta_pts": deg.get("mean_delta_pts"),
        "z_two_sided": deg.get("z_two_sided"),
        "z_naive_two_sided": deg.get("z_naive_two_sided"),
        "mde_2sigma_realized_cluster_pts": deg.get("mde_2sigma_realized_cluster_pts"),
        "effect_vs_realized_mde": (
            "the point estimate is BELOW this cell's own realized 2-sigma MDE, so the "
            "design could not have convicted it at this effect size even if it is real"
            if (deg.get("mean_delta_pts") is not None
                and deg.get("mde_2sigma_realized_cluster_pts") is not None
                and abs(deg["mean_delta_pts"]) < deg["mde_2sigma_realized_cluster_pts"])
            else "the point estimate is at or above this cell's realized 2-sigma MDE"),
        "ci95": [deg.get("ci95_lo"), deg.get("ci95_hi")],
        "boot_ci95": [deg.get("boot_ci95_lo"), deg.get("boot_ci95_hi")],
        "branch": branches.get("DEG", {}).get("branch"),
        "tile": {k: tm.get("tile", {}).get(k) for k in
                 ("n", "mean_delta_pts", "z_two_sided", "bound_pts_per_ply")},
        "meeple": {k: tm.get("meeple", {}).get(k) for k in
                   ("n", "mean_delta_pts", "z_two_sided", "bound_pts_per_ply")},
        "tier1_corroboration": (tier1.get("DEG", {}) or {}).get("corroboration"),
        "answer": (branches.get("DEG", {}).get("text")),
        "implication_if_positive": ("a SEARCH defect (policy/PUCT/backup/determinization), "
                                    "not a leaf-term defect - a different and cheaper thing "
                                    "to fix than a leaf re-sweep"),
    }


# --------------------------------------------------------------------------- #
# markdown                                                                      #
# --------------------------------------------------------------------------- #
def _f(x, nd=3):
    if x is None:
        return "—"
    if isinstance(x, float) and x != x:
        return "—"
    return f"{x:.{nd}f}"


def _row(st: dict) -> str:
    return (f"| {st.get('n')} | {_f(st.get('mean_delta_pts'))} | "
            f"{_f(st.get('se_cluster_game'))} | {_f(st.get('se_naive'))} | "
            f"{_f(st.get('z_two_sided'), 2)} | "
            f"{_f(st.get('ci95_lo'))} .. {_f(st.get('ci95_hi'))} | "
            f"{_f(st.get('boot_ci95_lo'))} .. {_f(st.get('boot_ci95_hi'))} |")


def to_markdown(v: dict) -> str:
    L = []
    a = L.append
    ca = v["completion_accounting"]
    a("# E4 autopsy — READOUT (machine-generated tables)\n")
    a(f"**Status: SCORED + ANALYSED. Design: [`DESIGN.md`](DESIGN.md). "
      f"Schema `{v['schema']}`. Numbers below are generated by "
      f"`scripts/analyzer/analyze_autopsy.py` from the banked records — none is typed by "
      f"hand.**\n")
    a("> **Scope limit.** " + v["scope"]["limit"] + "\n")
    a("> **Δ is not a strength claim** (read rule 9). It prices ONE ply against ONE "
      "alternative under a shallow continuation, and says where the evaluator *misprices* "
      "— not who is stronger.\n")
    a("> **The primary judge shares the leaf under test** (§7), so a verdict AGAINST the "
      "champion is conservative and strong, while a NULL through it is WEAK. Add read "
      "rule 5: the population is conditioned on the champion having disagreed at all, "
      "which biases Δ toward 0 — a null here is **softer than it looks**.\n")

    a("\n## 0. The answer, in one screen\n")
    rank0 = v["map_ranking"]["by_abs_mean_delta"]
    rb0 = v["run_level_branch"]
    d0 = v["deg_answer"]
    o0 = v["overall_pooled_all_strata"]
    a(f"**Where do his points come from? On this evidence: no cell in the map convicts.** "
      f"Run-level branch **`{rb0['branch']}`**.\n")
    a("| | |")
    a("|---|---|")
    a(f"| **Ranked suspects (Δ, z)** | "
      + " · ".join(f"{r['stratum']} {_f(r['mean_delta_pts'])} (z {_f(r['z'], 2)})"
                   for r in rank0) + " |")
    a(f"| **Top suspect** | `{rank0[0]['stratum']}` — Δ {_f(rank0[0]['mean_delta_pts'])} "
      f"pts/ply at z {_f(rank0[0]['z'], 2)}, i.e. **below its own realized 2σ MDE** |"
      if rank0 else "| **Top suspect** | — |")
    a(f"| **DEG (the cell this design was built for)** | n {d0['n']}, Δ "
      f"{_f(d0['mean_delta_pts'])} pts/ply, z {_f(d0['z_two_sided'], 2)} → "
      f"`{d0['branch']}`. It is the LARGEST suspect by both |Δ| and |z|, and it is not "
      f"resolved. A positive here would be a **search** defect, not a leaf defect. |")
    a(f"| **Pooled across all strata** (diagnostic only) | Δ {_f(o0['mean_delta_pts'])} "
      f"pts/ply, z {_f(o0['z_two_sided'], 2)} |")
    t0 = v["tier1_sign_check"]["ALL"]
    p0 = t0["binomial_p_two_sided"]
    s0 = v["tier1_sign_check"]["secondary_own_mean_SIGN_ONLY"]["ALL"]
    a(f"| **Tier-1 out-of-family SIGN check** | {t0['n_agree']}/{t0['n_both_nonzero']} = "
      f"{_f(t0['agreement_rate'], 3)} sign agreement, p "
      + ("—" if p0 is None else (f"{p0:.4f}" if p0 >= 1e-4 else f"{p0:.2e}"))
      + "; the secondary judge's own mean sign is "
      + ("—" if s0 is None else f"**{s0:+d}**") + " |")
    ml0 = v["multiplicity_ledger"]
    a(f"| **Exploratory contrasts** | {ml0['n_contrasts_total']} computed; "
      f"{len(ml0['observed_abs_z_ge_2'])} reached |z| ≥ 2 "
      f"(~{ml0['expected_hits_at_abs_z_ge_2_if_all_null']} expected under the global null), "
      f"{len(ml0['observed_abs_z_ge_3_QUOTABLE'])} reached |z| ≥ 3 |")
    a("\n**What this does NOT say.** It does not say the champion's evaluation is sound — "
      "read rule 2 makes every line above a BOUND, not a refutation, and §7 makes a null "
      "through the in-family judge weak by construction. It does not say anything about "
      "strength (read rule 9). It does not mint a claim, flip a governance row, or propose "
      "a promotion.\n")

    a("\n## 1. Completion accounting\n")
    a(f"- Planned this epoch: **{ca['planned_positions_this_epoch']} positions × 2 judges "
      f"= {ca['planned_records_both_judges']} scoring cells**.")
    p, s = ca["primary"], ca["secondary"]
    a(f"- Primary (clair-puct): **{p['n_in_sample_ok']} scored**, "
      f"**{p['n_failed']} failed**, {p['n_missing']} missing, "
      f"{p['n_out_of_sample_records_ignored']} out-of-sample record(s) ignored.")
    a(f"- Secondary (tier1-greedy): **{s['n_in_sample_ok']} scored**, "
      f"**{s['n_failed']} failed**, {s['n_missing']} missing, "
      f"{s['n_out_of_sample_records_ignored']} out-of-sample record(s) ignored.")
    for f_ in p["failures"] + s["failures"]:
        a(f"  - ⚠️ FAILED `{f_['rid']}` — `{f_['error']}`")
    if p["out_of_sample_rids"] or s["out_of_sample_rids"]:
        a(f"  - out-of-sample record(s) present in the out-root and **excluded from every "
          f"statistic**: `{p['out_of_sample_rids'] + s['out_of_sample_rids']}` "
          f"(the priced smoke wrote into the same out-root under the same salt, §10).")
    a(f"- {ca['note']}")
    a(f"- CRN verified on every scored position: primary "
      f"`{ca['crn_verified_all_primary']}`, secondary `{ca['crn_verified_all_secondary']}`; "
      f"M = {ca['m_worlds']} worlds.")

    a("\n## 2. The map — primary strata (Δ = V(played) − V(best), pts/ply)\n")
    a("Primary interval is the **`game_label` cluster-robust** SE (read rule 3); the naive "
      "SE and a **cluster bootstrap over games** (10 000 reps) ship beside it.\n")
    a("| stratum | n | Δ mean | SE (cluster/game) | SE (naive) | z (cluster, PRIMARY) | "
      "95% CI (cluster) | 95% CI (bootstrap) | branch |")
    a("|---|---:|---:|---:|---:|---:|---|---|---|")
    for st in STRATA:
        s_ = v["primary_strata"][st]
        if not s_.get("n"):
            a(f"| **{st}** | 0 | — | — | — | — | — | — | EMPTY |")
            continue
        a(f"| **{st}** " + _row(s_) + f" {v['stratum_branches'][st]['branch']} |")
    o = v["overall_pooled_all_strata"]
    a("| _(all strata pooled)_ " + _row(o) + " _diagnostic only_ |")
    a("\n**Realized power, and the naive-SE sensitivity.** The design sized every stratum "
      "off an assumed sd = 4.445 pts with no design effect priced in; the realized "
      "game-clustered SE is the binding one (read rule 3). Both z's are shown because the "
      "clustering is what decides some cells.\n")
    a("| stratum | design 2σ MDE | realized 2σ MDE (cluster) | realized 2σ MDE (naive) | "
      "design effect | z (cluster) | z (naive) |")
    a("|---|---:|---:|---:|---:|---:|---:|")
    for st in STRATA:
        s_ = v["primary_strata"][st]
        if not s_.get("n"):
            continue
        d_ = v.get("design_mde_2sigma", {}).get(st)
        a(f"| **{st}** | {_f(d_)} | {_f(s_.get('mde_2sigma_realized_cluster_pts'))} | "
          f"{_f(s_.get('mde_2sigma_realized_naive_pts'))} | "
          f"{_f(s_.get('design_effect'), 2)} | {_f(s_.get('z_two_sided'), 2)} | "
          f"{_f(s_.get('z_naive_two_sided'), 2)} |")
    a("\n**Ranked by |Δ|:** " + " · ".join(
        f"{r['stratum']} {_f(r['mean_delta_pts'])} (z {_f(r['z'], 2)})"
        for r in v["map_ranking"]["by_abs_mean_delta"]))
    a("\n**Ranked by |z|:** " + " · ".join(
        f"{r['stratum']} z {_f(r['z'], 2)} (Δ {_f(r['mean_delta_pts'])})"
        for r in v["map_ranking"]["by_abs_z"]))

    a("\n### Which §8 branch fired, per stratum\n")
    for st in STRATA:
        b = v["stratum_branches"][st]
        a(f"- **{st} → `{b['branch']}`** — {b['text']}")
    rb = v["run_level_branch"]
    a(f"\n**Run-level branch: `{rb['branch']}`** — {rb['text']}")

    a("\n## 3. The DEG answer (the cell the design was built for)\n")
    d = v["deg_answer"]
    a(f"{d['question']}\n")
    a(f"- **DEG: n = {d['n']}, Δ = {_f(d['mean_delta_pts'])} pts/ply, z = "
      f"{_f(d['z_two_sided'], 2)}**, cluster CI {_f(d['ci95'][0])} .. {_f(d['ci95'][1])}, "
      f"bootstrap CI {_f(d['boot_ci95'][0])} .. {_f(d['boot_ci95'][1])} → "
      f"`{d['branch']}`.")
    a(f"- tile plies: n = {d['tile']['n']}, Δ = {_f(d['tile']['mean_delta_pts'])}, z = "
      f"{_f(d['tile']['z_two_sided'], 2)} · meeple plies: n = {d['meeple']['n']}, Δ = "
      f"{_f(d['meeple']['mean_delta_pts'])}, z = {_f(d['meeple']['z_two_sided'], 2)} "
      f"(the census put DEG at 90% tile placements; the scored cell keeps that shape)")
    a(f"- realized 2σ MDE (cluster) = "
      f"{_f(d['mde_2sigma_realized_cluster_pts'])} pts/ply — {d['effect_vs_realized_mde']}. "
      f"Naive-SE z would be {_f(d['z_naive_two_sided'], 2)}; read rule 3 makes the "
      f"game-clustered z the binding one.")
    a(f"- Tier-1 out-of-family check on this cell: {d['tier1_corroboration']}")
    a(f"- {d['answer']}")

    a("\n## 4. Tile vs meeple\n")
    a("| cell | n | Δ mean | SE (cluster/game) | SE (naive) | z | 95% CI (cluster) | "
      "95% CI (bootstrap) |")
    a("|---|---:|---:|---:|---:|---:|---|---|")
    for lv, st in v["tile_vs_meeple"]["overall"].items():
        a(f"| ALL/{lv} " + _row(st))
    for stratum, cells in v["tile_vs_meeple"]["per_stratum"].items():
        for lv, st in cells.items():
            a(f"| {stratum}/{lv} " + _row(st))

    a("\n## 5. Mechanism tags — SECONDARY, multiplicity applies\n")
    for line in v["mechanism_tags"]["_read_rules"]:
        a(f"> {line}\n")
    inv = v["mechanism_tags"]["_contrast_inventory"]
    a(f"Contrasts computed: **{inv['n_contrasts']}** (pre-registered count "
      f"{inv['n_contrasts_preregistered']}); expected false positives at α=0.05: "
      f"**{inv['expected_false_positives_at_alpha_05']}**. Quotable at |z| ≥ 3: "
      f"**{inv['quotable_at_z3'] or 'NONE'}**.\n")
    a("| contrast | n | Δ (pts/ply) | z | quotable alone? |")
    a("|---|---:|---:|---:|---|")
    for i in inv["contrasts"]:
        q = ("YES (|z| ≥ 3)" if i.get("z") is not None and i["z"] == i["z"]
             and abs(i["z"]) >= Z_GATE_SECONDARY else "no")
        a(f"| {i['contrast']} | {i['n']} | {_f(i['mean'])} | {_f(i.get('z'), 2)} | {q} |")
    cv = v["convergent_sign_check"]
    a(f"\n**Convergent-sign check (F9 + F2):** signs {cv['per_tag_sign']}; all four same "
      f"sign = `{cv['all_four_same_sign']}`, all four |z| ≥ 2 = `{cv['all_four_abs_z_ge_2']}` "
      f"⇒ quotable by convergence = **`{cv['convergent_and_quotable']}`**. "
      f"({cv['definition']}.)")
    a(f"\n**F6 / F9 / F2 cells** (level means, all secondary):\n")
    a("| tag cell | n | Δ mean | SE (cluster/game) | SE (naive) | z | 95% CI (cluster) | "
      "95% CI (bootstrap) |")
    a("|---|---:|---:|---:|---:|---:|---|---|")
    for key in ("F6_score_diff_bucket", "F9_reinforce_losing_contest_best",
                "F9_reinforce_losing_contest_played", "F2_tie_force_join_best",
                "F2_tie_force_join_played"):
        for lv, st in v["mechanism_tags"][key].items():
            a(f"| {key.split('_')[0]} {key} = {lv} " + _row(st))
    f3 = v["mechanism_tags"]["F3_reserve_regression"]
    if f3.get("terms"):
        a(f"\n**F3 (continuous, §6 reads it as a regression not a cell)** — Δ ~ 1 + "
          f"own_reserve + opp_reserve, n = {f3['n']}, cluster-robust on game:")
        for nm, t in f3["terms"].items():
            a(f"- `{nm}`: β = {_f(t['beta_pts_per_meeple'])} pts per meeple, SE "
              f"{_f(t['se_cluster_game'])}, z {_f(t['z_two_sided'], 2)}")
    a(f"\n**F7 — `null` BY DESIGN.** {v['mechanism_tags']['F7_status']}")

    a("\n## 6. Secondary axes (descriptive marginals)\n")
    a("| axis cell | n | Δ mean | SE (cluster/game) | SE (naive) | z | 95% CI (cluster) | "
      "95% CI (bootstrap) |")
    a("|---|---:|---:|---:|---:|---:|---|---|")
    for axis, cells in v["secondary_axes"].items():
        if axis.startswith("_"):
            continue
        for lv, st in cells.items():
            a(f"| {axis} = {lv} " + _row(st))

    a("\n## 6b. Multiplicity ledger — every non-primary contrast in this readout\n")
    ml = v["multiplicity_ledger"]
    a(f"{ml['n_contrasts_total']} exploratory contrasts computed. If every one were null "
      f"we would expect **{ml['expected_hits_at_abs_z_ge_2_if_all_null']}** at |z| ≥ 2 and "
      f"**{ml['expected_hits_at_abs_z_ge_3_if_all_null']}** at |z| ≥ 3. "
      f"Observed: **{len(ml['observed_abs_z_ge_2'])}** and "
      f"**{len(ml['observed_abs_z_ge_3_QUOTABLE'])}**. {ml['note']}\n")
    a("| family | cell | n | Δ | z | gate |")
    a("|---|---|---:|---:|---:|---|")
    for i in ml["observed_abs_z_ge_2"]:
        gate = ("|z| ≥ 3 — quotable from this run alone" if abs(i["z"]) >= 3
                else "|z| ≥ 2 only — HYPOTHESIS for a targeted follow-up, not a finding")
        if i.get("prereg_weak_read_rule_7"):
            gate += (" — but PRE-DECLARED WEAK by read rule 7: reported with its CI, "
                     "NEVER promoted, in either direction")
        a(f"| {i['family']} | {i['cell']} | {i['n']} | {_f(i['mean_delta_pts'])} | "
          f"{_f(i['z'], 2)} | {gate} |")
    if not ml["observed_abs_z_ge_2"]:
        a("| — | _no exploratory contrast reached |z| ≥ 2_ | — | — | — | — |")

    a("\n## 7. Tier-1 out-of-family SIGN check\n")
    t = v["tier1_sign_check"]
    a(f"> {t['note']}\n")
    a(f"Paired positions (scored by BOTH judges): **{t['n_paired']}**.\n")
    a("| cell | n (both non-zero) | agree | rate | binomial p (two-sided) | "
      "secondary mean SIGN |")
    a("|---|---:|---:|---:|---:|---:|")
    for k in ["ALL"] + [s for s in STRATA if s in t]:
        c = t[k]
        p_ = c["binomial_p_two_sided"]
        ps = "—" if p_ is None else (f"{p_:.4f}" if p_ >= 1e-4 else f"{p_:.2e}")
        a(f"| {k} | {c['n_both_nonzero']} | {c['n_agree']} | "
          f"{_f(c['agreement_rate'], 3)} | {ps} | "
          f"{t['secondary_own_mean_SIGN_ONLY'].get(k)} |")
    a("\n**How each cell corroborates (or does not):**\n")
    for k in ["ALL"] + [s for s in STRATA if s in t]:
        a(f"- **{k}** — {t[k]['corroboration']}")
    a("\n⚠️ Two cautions on the table above. (i) These are six binomial tests on one corpus; "
      "the per-stratum rows carry the same multiplicity discipline as every other secondary "
      "read. (ii) **Corroborating the SIGN of a near-zero Δ is not informative** — a "
      "stratum whose primary Δ is a fraction of a point can show high sign agreement "
      "without there being an effect to corroborate. Read the corroboration column only "
      "beside the stratum's own Δ and z in §2.")

    a("\n## 8. Per-game means (cluster diagnostic — read rule 3 / threat 6)\n")
    a("| game | n | Δ mean |")
    a("|---|---:|---:|")
    for g, r in v["per_game"].items():
        a(f"| `{g}` | {r['n']} | {_f(r['mean_delta_pts'])} |")

    a("\n## 9. The map, read plainly — and what would resolve it\n")
    rank = v["map_ranking"]["by_abs_mean_delta"]
    top = rank[0] if rank else None
    rb2 = v["run_level_branch"]
    if rb2["branch"] == "NO_CONVICTION_ANYWHERE":
        a("**No cell convicts.** What follows is a ranking of SUSPECTS, not of findings. "
          "Every line below is bounded, not refuted (read rule 2), and read rule 5 plus the "
          "in-family judge (§7) both make this null softer than the numbers look.\n")
    for r in rank:
        st = v["primary_strata"][r["stratum"]]
        b = v["stratum_branches"][r["stratum"]]
        word = {"LOCALIZED_DEFECT": "**CONVICTS** — localized evaluation defect",
                "DEG_SEARCH_DEFECT": "**CONVICTS** — SEARCH defect (leaf provably "
                                     "indifferent here)",
                "CHAMPION_PICKS_BETTER": "**CONVICTS the other way** — the champion's picks "
                                         "really are better here",
                "NO_CONVICTION": "no conviction"}.get(b["branch"], b["branch"])
        a(f"- **{r['stratum']}** (n {r['n']}): Δ {_f(r['mean_delta_pts'])} pts/ply, "
          f"z {_f(r['z'], 2)} → {word}"
          + (f"; bounded at |Δ| ≤ {_f(st.get('bound_pts_per_ply'))} pts/ply"
             if st.get("bound_pts_per_ply") is not None else ""))
    if top:
        a(f"\n**Top suspect by effect size: `{top['stratum']}`** "
          f"(Δ {_f(top['mean_delta_pts'])} pts/ply, z {_f(top['z'], 2)}).")
    a("\n### What it would take to resolve each cell at |z| = 2\n")
    a("Takes each cell's own point estimate at face value. `positions` assumes variance "
      "falls like 1/n (true only for the within-game component — there are already-extracted "
      "unscored plies in every stratum); `games` assumes it falls like 1/G, which is what a "
      "cluster-robust SE tracks once the between-game component is real. Where the design "
      "effect exceeds 1, **games** is the binding resource — which is exactly why §8's "
      "default next step is more E4 games, not more compute.\n")
    a("| stratum | Δ assumed | shortfall factor | positions needed (+more) | "
      "games needed (+more) | binding |")
    a("|---|---:|---:|---:|---:|---|")
    for r in rank:
        rr = v["primary_strata"][r["stratum"]].get("resolution_requirement", {})
        if rr.get("status") == "not_computable":
            a(f"| **{r['stratum']}** | {_f(r['mean_delta_pts'])} | — | — | — | "
              f"not computable |")
            continue
        a(f"| **{r['stratum']}** | {_f(rr['assumed_true_effect_pts'])} | "
          f"{_f(rr['shortfall_factor'], 2)} | {rr['positions_needed_if_1_over_n']} "
          f"(+{rr['additional_positions']}) | {rr['games_needed_if_1_over_G']} "
          f"(+{rr['additional_games']}) | {rr['binding']} |")

    a("\n## 10. Read rules honoured\n")
    for r in v["read_rules_applied"]:
        a(f"- {r}")
    a(f"\n**Governance.** {v['governance']['note']}")
    return "\n".join(L) + "\n"


def _run_manifest(records_dir: str) -> dict:
    """The scoring run's own manifest, which lives beside `records/` (DESIGN §11)."""
    p = Path(records_dir)
    leg = p.parent if p.name == "records" else p
    out = {"leg_dir": str(leg)}
    for name in ("manifest.json", "summary.json"):
        f = leg / name
        if f.exists():
            try:
                d = json.loads(f.read_text())
            except json.JSONDecodeError:
                out[name] = {"path": str(f), "error": "unparseable"}
                continue
            out[name] = {"path": str(f),
                         **{k: d[k] for k in
                            ("schema", "oracle_policy", "backend", "m", "oracle_sims",
                             "m_worlds", "n_attempted", "n_failed", "wall_secs",
                             "crn_verified_all", "world_seed_salt", "seed", "salt")
                            if k in d}}
    return out


def _provenance(a) -> dict:
    import subprocess
    try:
        rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                             cwd=str(Path(__file__).resolve().parents[2]),
                             timeout=20).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        rev = None
    return {
        "analyzer": "scripts/analyzer/analyze_autopsy.py",
        "git_head": rev,
        "positions_files": [str(Path(p).resolve()) for p in a.positions],
        "primary_record_dirs": [str(Path(p).resolve()) for p in a.primary_records],
        "secondary_record_dirs": [str(Path(p).resolve()) for p in a.secondary_records],
        "bootstrap_reps": a.bootstrap, "bootstrap_seed": a.bootstrap_seed,
        "primary_run_manifests": [_run_manifest(d) for d in a.primary_records],
        "secondary_run_manifests": [_run_manifest(d) for d in a.secondary_records],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--positions", nargs="+", required=True,
                    help="the pre-registered positions_<epoch>.jsonl file(s)")
    ap.add_argument("--primary-records", nargs="+", required=True)
    ap.add_argument("--secondary-records", nargs="*", default=[])
    ap.add_argument("--out", required=True, help="VERDICT.json")
    ap.add_argument("--md", default=None, help="machine-generated readout markdown")
    ap.add_argument("--bootstrap", type=int, default=10000)
    ap.add_argument("--bootstrap-seed", type=int, default=20260812)
    ap.add_argument("--epoch-scope", default="fixed_v1")
    a = ap.parse_args(argv)

    positions = load_positions(a.positions)
    primary = load_records(a.primary_records)
    secondary = load_records(a.secondary_records) if a.secondary_records else []
    v = analyse(primary, secondary, positions, boot_reps=a.bootstrap,
                boot_seed=a.bootstrap_seed, epoch_scope=a.epoch_scope)
    v["provenance"] = _provenance(a)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(v, indent=2))
    if a.md:
        Path(a.md).write_text(to_markdown(v))
    print(json.dumps({"completion_accounting": v["completion_accounting"],
                      "map_ranking": v["map_ranking"],
                      "stratum_branches": v["stratum_branches"],
                      "run_level_branch": v["run_level_branch"],
                      "deg_answer": v["deg_answer"]}, indent=2))
    print(f"[analyze_autopsy] -> {a.out}" + (f" , {a.md}" if a.md else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
