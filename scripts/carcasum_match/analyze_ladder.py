#!/usr/bin/env python3
"""Read-out for the CARCASUM RUNG-2 BUDGET LADDER — the analyzer named in
``measurement/carcasum_rung2_prep/DESIGN.md`` §7 and cited by
``READ_RULE.md`` and ``WORKERS.conf::ADJUDICATOR``.

Separate from ``match.py``'s own ``summarize()`` on purpose, same relationship
``scripts/jcz_match/analyze.py`` has to ``jcz_match/match.py``'s ``summarize()``
(that one runs inside the fleet driver and answers "did the run go OK"; this one
is the ANALYSIS). Two things this file does that ``match.py``'s own
``summarize()`` does not:

* **Median AND mean playouts/turn, pooled from the raw per-move
  ``carcasum_playouts`` fields** — ``match.py``'s ``summarize()`` emits only
  ``opp_driver_playouts_per_turn_mean`` (a per-game-mean average), and this
  project's own design text (``PREREG.md`` §2.1, ``LAUNCH_PROCEDURE.md`` §5)
  says median is the load-bearing statistic, precisely because the mean is
  skewed ~3x by full-random-rollout endgame plies. ``match.py`` is NOT edited
  by this cell (DESIGN.md §7); this is a second, standalone tool.
* **The cross-rung fit.** A weighted least-squares regression of deck-paired
  margin against log2(playouts) across rung 0 (r1's already-collected corpus)
  plus whichever of rungs A/B/C pass the READ_RULE.md §3 preconditions, the
  fitted crossover B* (with its delta-method standard error), and the
  READ_RULE.md §4 D/K/A/B branch decision.

Usage (real read-out, once games exist):
    .venv/bin/python scripts/carcasum_match/analyze_ladder.py \\
        --rung0 measurement/carcasum_match_20260823/games.jsonl \\
        --rungA measurement/carcasum_rung2_20260823/rungA/games.jsonl --playouts-a 65536 \\
        --rungB measurement/carcasum_rung2_20260823/rungB/games.jsonl --playouts-b 131072 \\
        --rungC measurement/carcasum_rung2_20260823/rungC/games.jsonl --playouts-c 262144

Usage (self-test against ONLY rung 0 — no ladder fit possible with one point,
prints the per-rung stats and the "insufficient points" readout; useful to
sanity-check the median/mean pooling against a real archive before freezing):
    .venv/bin/python scripts/carcasum_match/analyze_ladder.py --rung0 <path>

Usage (math self-test, no archives at all — verifies the WLS/crossover/z_interp
arithmetic against hand-computable numbers, see ``_selftest()``):
    .venv/bin/python scripts/carcasum_match/analyze_ladder.py --selftest
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: READ_RULE.md §3.1 — imported vocabulary, not redefined (same discipline
#: match.py's own module docstring states for its REAL/CLASSIFIED taxonomy).
REAL_DIVERGENCE_CLASSES = frozenset({
    "SCORE_FINAL", "FARM_SCORE_FINAL", "MEEPLE_LEGALITY", "MEEPLE_SLOT_UNMAPPED",
    "LEGALITY_OURS_EXTRA", "HARNESS_ERROR", "DRIVER_REJECT", "SEAT_DESYNC",
    "COORD_FRAME_MISMATCH",
})

VOID_RATE_BAR = 0.01          # READ_RULE.md §3.1 — 1% of a rung's own games
G_N_FLOOR_FRACTION = 0.80     # READ_RULE.md §3 G-N
G_MODE_TOLERANCE_PCT = 5.0    # READ_RULE.md §3 G-MODE


# --------------------------------------------------------------------------- #
# loading                                                                      #
# --------------------------------------------------------------------------- #
def load(path: Path | str) -> list[dict]:
    """Same torn-last-line tolerance as jcz_match/analyze.py's own loader."""
    out = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _wr_to_elo(wr: float) -> float | None:
    if wr <= 0.0 or wr >= 1.0:
        return None
    return -400.0 * math.log10(1.0 / wr - 1.0)


# --------------------------------------------------------------------------- #
# per-rung stats                                                               #
# --------------------------------------------------------------------------- #
def per_rung_stats(records: list[dict], *, assigned_playouts: int | None = None) -> dict:
    """Deck-paired margin/SEM, win rate/elo, void ledger, and — the point of
    this file — median AND mean realized playouts/turn pooled from every
    real opponent turn's ``carcasum_playouts`` field, plus the G-MODE
    deviation check against ``assigned_playouts`` if given."""
    voids: dict[str, int] = {}
    real_divergences: dict[str, int] = {}
    for r in records:
        if r.get("void"):
            voids[r["void"]] = voids.get(r["void"], 0) + 1
        for cls, n in (r.get("counts") or {}).items():
            if cls in REAL_DIVERGENCE_CLASSES and n:
                real_divergences[cls] = real_divergences.get(cls, 0) + int(n)

    ok = [r for r in records if not r.get("void") and r.get("winner")]
    wins = sum(1 for r in ok if r["winner"] == "champ")
    draws = sum(1 for r in ok if r["winner"] == "draw")
    n = len(ok)

    by_deck: dict[int, dict[int, list[int]]] = {}
    for r in ok:
        by_deck.setdefault(int(r["deck_seed"]), {}).setdefault(
            int(r["champ_seat"]), []).append(int(r["margin_champ_minus_opp"]))
    paired = []
    for seats in by_deck.values():
        if len(seats) == 2:
            paired.append(sum(sum(v) / len(v) for v in seats.values()) / 2.0)
    mean_p = sum(paired) / len(paired) if paired else None
    var_p = (sum((x - mean_p) ** 2 for x in paired) / (len(paired) - 1)
             if paired and len(paired) > 1 else None)
    sem_p = (var_p / len(paired)) ** 0.5 if var_p is not None else None

    # THE POINT: pool every real opponent turn's carcasum_playouts, not the
    # per-game pre-aggregated mean field.
    pooled_playouts = [
        m["carcasum_playouts"]
        for r in records if not r.get("void")
        for m in (r.get("moves") or [])
        if "carcasum_playouts" in m
    ]
    median_playouts = st.median(pooled_playouts) if pooled_playouts else None
    mean_playouts = st.mean(pooled_playouts) if pooled_playouts else None

    void_rate = (sum(voids.values()) / len(records)) if records else None
    real_rate = (sum(real_divergences.values()) / len(records)) if records else None

    g_mode_dev_pct = None
    g_mode_pass = None
    if median_playouts is not None and assigned_playouts:
        g_mode_dev_pct = 100.0 * abs(median_playouts - assigned_playouts) / assigned_playouts
        g_mode_pass = g_mode_dev_pct <= G_MODE_TOLERANCE_PCT

    return {
        "n_records": len(records), "n_scored": n, "voids": voids,
        "real_divergences": real_divergences,
        "void_rate": void_rate, "real_divergence_rate": real_rate,
        "wins": wins, "draws": draws, "losses": n - wins - draws,
        "win_rate": (wins + 0.5 * draws) / n if n else None,
        "elo_from_win_rate": _wr_to_elo((wins + 0.5 * draws) / n) if n else None,
        "n_paired_decks": len(paired),
        "paired_margin_mean": mean_p,
        "paired_margin_sem": sem_p,
        "pooled_opp_turns": len(pooled_playouts),
        "median_opp_playouts_per_turn": median_playouts,
        "mean_opp_playouts_per_turn": mean_playouts,
        "assigned_playouts": assigned_playouts,
        "g_mode_deviation_pct": g_mode_dev_pct,
        "g_mode_pass": g_mode_pass,
    }


def gate_g_n(stats: dict, n_decks_target: int) -> bool:
    return stats["n_paired_decks"] >= math.floor(G_N_FLOOR_FRACTION * n_decks_target)


def gate_d_void(stats: dict) -> bool:
    """True if THIS rung is clean enough to survive (READ_RULE.md §3.1's
    per-rung 1% bar). Returns False -> the rung is void-contaminated."""
    vr = stats.get("void_rate") or 0.0
    rr = stats.get("real_divergence_rate") or 0.0
    return vr <= VOID_RATE_BAR and rr <= VOID_RATE_BAR


# --------------------------------------------------------------------------- #
# the ladder fit — weighted least squares, delta-method crossover SE          #
# --------------------------------------------------------------------------- #
def wls_fit(xs: list[float], ys: list[float], sems: list[float]) -> dict:
    """Weighted least squares, weight_i = 1/sem_i^2. Returns beta0, beta1 and
    their variances/covariance from the normal equations — closed form for
    simple weighted linear regression, no numpy dependency (stdlib only, same
    constraint match.py's module docstring states for its own module-level
    imports)."""
    w = [1.0 / (s * s) for s in sems]
    sw = sum(w)
    swx = sum(wi * xi for wi, xi in zip(w, xs))
    swy = sum(wi * yi for wi, yi in zip(w, ys))
    swxx = sum(wi * xi * xi for wi, xi in zip(w, xs))
    swxy = sum(wi * xi * yi for wi, xi, yi in zip(w, xs, ys))
    denom = sw * swxx - swx * swx
    if denom == 0:
        raise ValueError("degenerate design (all x equal or n<2) — cannot fit")
    beta1 = (sw * swxy - swx * swy) / denom
    beta0 = (swxx * swy - swx * swxy) / denom
    # Var/Cov of (beta0, beta1) from (X'WX)^-1 for the 2x2 design matrix
    # [[sw, swx],[swx, swxx]] — standard weighted-OLS closed form.
    var_beta1 = sw / denom
    var_beta0 = swxx / denom
    cov_beta01 = -swx / denom
    return {
        "beta0": beta0, "beta1": beta1,
        "var_beta0": var_beta0, "var_beta1": var_beta1, "cov_beta01": cov_beta01,
        "se_beta0": var_beta0 ** 0.5, "se_beta1": var_beta1 ** 0.5,
        "z_slope": beta1 / (var_beta1 ** 0.5) if var_beta1 > 0 else None,
        "n_points": len(xs),
    }


def crossover(fit: dict) -> dict:
    """x* = -beta0/beta1 (READ_RULE.md §1), with its delta-method SE."""
    b0, b1 = fit["beta0"], fit["beta1"]
    if b1 == 0:
        return {"x_star": None, "se_x_star": None, "b_star": None}
    x_star = -b0 / b1
    var_x = (1.0 / (b1 * b1)) * (
        fit["var_beta0"]
        + x_star * x_star * fit["var_beta1"]
        + 2 * x_star * fit["cov_beta01"]
    )
    se_x = var_x ** 0.5 if var_x >= 0 else None
    return {
        "x_star": x_star,
        "se_x_star": se_x,
        "b_star": (2 ** x_star) if x_star is not None else None,
    }


def z_interp(x_star: float, se_x_star: float, x0: float, x3: float) -> float:
    """READ_RULE.md §1 — the SMALLER of x*'s distance to either bracket edge,
    in SE units."""
    if not se_x_star:
        return float("nan")
    return min(x_star - x0, x3 - x_star) / se_x_star


# --------------------------------------------------------------------------- #
# READ_RULE.md §4 branch decision                                             #
# --------------------------------------------------------------------------- #
def decide_branch(fit: dict, cross: dict, x0: float, x3: float) -> dict:
    """⚠️ SIGN CONVENTION, load-bearing: margin = champion - Carcasum, so a
    GENUINE closing-the-gap trend as playout budget rises is a NEGATIVE slope
    (beta1 < 0) — margin shrinking toward, and through, zero. A flat or
    POSITIVE slope means more search budget does not (or does not credibly)
    bring Carcasum closer, which is what "saturation" means here. `z_slope`
    is reported with the natural sign of beta1 (negative when beta1<0); the
    "credibly closing" test is therefore `z_slope <= -2`, not `z_slope >= 2`.
    """
    b1, z_slope = fit["beta1"], fit["z_slope"]
    x_star = cross["x_star"]

    if x_star is not None and x_star < x0:
        return {"branch": "U-UNREADABLE",
                "reason": ("fitted crossover falls BELOW rung 0's own budget — "
                           "contradicts rung 0's own directly-measured sign "
                           "(READ_RULE.md §4 edge case). Flag for design review.")}

    credibly_closing = b1 is not None and b1 < 0 and z_slope is not None and z_slope <= -2
    not_crossed_in_range = x_star is None or x_star >= x3

    if b1 is None or b1 >= 0 or (not credibly_closing and not_crossed_in_range):
        return {"branch": "K-SATURATION",
                "reason": ("Carcasum saturates below the champion at this budget "
                           "range; better-but-saturating ruler. STOP.")}

    zi = z_interp(x_star, cross["se_x_star"], x0, x3) if x_star is not None else None
    if x_star is not None and x0 <= x_star <= x3 and zi is not None and zi >= 2:
        return {"branch": "A-USABLE-PRICE", "z_interp": zi,
                "reason": (f"B* = {cross['b_star']:.0f} playouts is the program's "
                            "first external-currency price of the champion.")}

    if x_star is not None and x_star > x3 and credibly_closing:
        return {"branch": "B-BOUND",
                "reason": (f"B* > {2 ** x3:.0f} playouts; slope is credibly "
                            "negative (z_slope<=-2, genuinely closing) but the "
                            "crossing is past the tested range. Queue a 16x rung "
                            "as an OWNER decision.")}

    return {"branch": "U-UNREADABLE",
            "reason": "no branch condition matched cleanly — review by hand."}


# --------------------------------------------------------------------------- #
# self-test — verifies the arithmetic against hand-computable numbers,        #
# WITHOUT touching any archive or spending any band (DESIGN.md's "no runs     #
# beyond the smoke" constraint; this is pure math, not a game).               #
# --------------------------------------------------------------------------- #
def _selftest() -> int:
    # A perfectly linear synthetic ladder: margin = 20 - 1*x, so it crosses
    # zero at x=20 exactly, with tiny uniform SEMs -> se(x*) should be small
    # and z_interp comfortably >= 2 when x0..x3 brackets 20.
    xs = [15.0, 16.0, 17.0, 18.0]
    ys = [5.0, 4.0, 3.0, 2.0]        # slope exactly -1, intercept 20
    sems = [1.0, 1.0, 1.0, 1.0]
    fit = wls_fit(xs, ys, sems)
    assert abs(fit["beta1"] - (-1.0)) < 1e-9, fit
    assert abs(fit["beta0"] - 20.0) < 1e-9, fit
    cross = crossover(fit)
    assert abs(cross["x_star"] - 20.0) < 1e-9, cross
    print("[selftest] exact-fit crossover OK: x*=%.4f b*=%.1f" % (cross["x_star"], cross["b_star"]))

    # Same slope/intercept but x0..x3 = 15..18 (crossover at 20 is OUTSIDE the
    # bracket) -> branch decision must be B (credible slope, beyond x3), not A.
    decision = decide_branch(fit, cross, x0=15.0, x3=18.0)
    assert decision["branch"] == "B-BOUND", decision
    print("[selftest] out-of-bracket crossover -> B-BOUND OK")

    # A flat (non-rising) ladder -> K-SATURATION.
    ys_flat = [4.0, 4.0, 4.0, 4.0]
    fit_flat = wls_fit(xs, ys_flat, sems)
    cross_flat = crossover(fit_flat) if fit_flat["beta1"] != 0 else {"x_star": None, "se_x_star": None, "b_star": None}
    decision_flat = decide_branch(fit_flat, cross_flat, x0=15.0, x3=18.0)
    assert decision_flat["branch"] == "K-SATURATION", decision_flat
    print("[selftest] flat ladder -> K-SATURATION OK")

    # A ladder that crosses cleanly INSIDE the bracket -> A-USABLE-PRICE.
    ys_in = [2.0, 1.0, -0.4, -1.4]   # crosses near x~16.7, well inside [15,18]
    sems_tight = [0.3, 0.3, 0.3, 0.3]
    fit_in = wls_fit(xs, ys_in, sems_tight)
    cross_in = crossover(fit_in)
    decision_in = decide_branch(fit_in, cross_in, x0=15.0, x3=18.0)
    assert decision_in["branch"] == "A-USABLE-PRICE", decision_in
    print("[selftest] in-bracket crossover -> A-USABLE-PRICE OK (x*=%.3f)" % cross_in["x_star"])

    print("[selftest] ALL PASS")
    return 0


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rung0", default=None, help="r1's frozen games.jsonl (rung 0)")
    ap.add_argument("--rungA", default=None)
    ap.add_argument("--rungB", default=None)
    ap.add_argument("--rungC", default=None)
    ap.add_argument("--playouts-a", type=int, default=65536)
    ap.add_argument("--playouts-b", type=int, default=131072)
    ap.add_argument("--playouts-c", type=int, default=262144)
    ap.add_argument("--n-decks-target", type=int, default=100,
                    help="per new-rung target deck count (WORKERS.conf N_DECKS); "
                         "rung 0 uses 200 (its own r1 target)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    if not args.rung0:
        print("FATAL: --rung0 is required unless --selftest", file=sys.stderr)
        return 2

    rung_defs = [("rung0", args.rung0, math.log2(32551), 200, None)]  # DESIGN.md §1, unrounded x0
    if args.rungA:
        rung_defs.append(("rungA", args.rungA, math.log2(args.playouts_a), args.n_decks_target, args.playouts_a))
    if args.rungB:
        rung_defs.append(("rungB", args.rungB, math.log2(args.playouts_b), args.n_decks_target, args.playouts_b))
    if args.rungC:
        rung_defs.append(("rungC", args.rungC, math.log2(args.playouts_c), args.n_decks_target, args.playouts_c))

    report: dict = {"rungs": {}}
    usable = []   # (name, x, margin, sem)
    dropped = []
    for name, path, x, n_target, assigned in rung_defs:
        recs = load(path)
        stats = per_rung_stats(recs, assigned_playouts=assigned)
        stats["x_log2_playouts"] = x
        report["rungs"][name] = stats

        reasons = []
        if not gate_d_void(stats):
            reasons.append("D-void/divergence-rate-over-bar")
        if not gate_g_n(stats, n_target):
            reasons.append("G-N-below-80pct-floor")
        if assigned is not None and stats["g_mode_pass"] is False:
            reasons.append("G-MODE-deviation-over-5pct")
        if stats["paired_margin_mean"] is None or stats["paired_margin_sem"] in (None, 0):
            reasons.append("no-usable-paired-margin/sem")

        if reasons:
            dropped.append({"rung": name, "reasons": reasons})
        else:
            usable.append((name, x, stats["paired_margin_mean"], stats["paired_margin_sem"]))

    report["dropped"] = dropped
    n_new_usable = sum(1 for name, *_ in usable if name != "rung0")

    if n_new_usable < 2:
        report["branch"] = "D-UNREADABLE"
        report["reason"] = (f"only {n_new_usable}/3 new rungs usable — "
                             "READ_RULE.md §3.1 requires >=2 new rungs plus rung 0.")
    else:
        xs = [x for _, x, _, _ in usable]
        ys = [m for _, _, m, _ in usable]
        sems = [s for _, _, _, s in usable]
        fit = wls_fit(xs, ys, sems)
        cross = crossover(fit)
        x0, x3 = min(xs), max(xs)
        decision = decide_branch(fit, cross, x0, x3)
        report["fit"] = fit
        report["crossover"] = cross
        report["x0"] = x0
        report["x3"] = x3
        report["branch"] = decision["branch"]
        report["reason"] = decision["reason"]
        if "z_interp" in decision:
            report["z_interp"] = decision["z_interp"]

    if args.json:
        print(json.dumps(report, indent=1, default=str))
    else:
        for name, stats in report["rungs"].items():
            print(f"[{name}] n_scored={stats['n_scored']} paired_margin="
                  f"{stats['paired_margin_mean']} +/- {stats['paired_margin_sem']} "
                  f"median_playouts={stats['median_opp_playouts_per_turn']} "
                  f"mean_playouts={stats['mean_opp_playouts_per_turn']} "
                  f"g_mode_pass={stats['g_mode_pass']}")
        if report["dropped"]:
            print("DROPPED:", report["dropped"])
        print(f"\nBRANCH: {report['branch']}")
        print(f"REASON: {report['reason']}")
        if "fit" in report:
            print(f"fit: beta0={report['fit']['beta0']:.4f} beta1={report['fit']['beta1']:.4f} "
                  f"z_slope={report['fit']['z_slope']}")
            print(f"crossover: x*={report['crossover']['x_star']} "
                  f"B*={report['crossover']['b_star']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
