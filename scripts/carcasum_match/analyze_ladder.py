#!/usr/bin/env python3
"""Read-out for the CARCASUM RUNG-2 BUDGET LADDER — the analyzer named in
``measurement/carcasum_rung2_prep/DESIGN.md`` §7 and cited by
``READ_RULE.md`` and ``WORKERS.conf::ADJUDICATOR``.

Separate from ``match.py``'s own ``summarize()`` on purpose, same relationship
``scripts/jcz_match/analyze.py`` has to ``jcz_match/match.py``'s ``summarize()``.
Three things this file does that ``match.py``'s own ``summarize()`` does not:

* **Median AND mean playouts/turn**, pooled from the raw per-move
  ``carcasum_playouts`` fields (``match.py``'s ``summarize()`` emits only the
  per-game-mean average — the named defect this cell's design corrects).
* **The WITHIN-DECK slope estimator** (PRE-LAUNCH AMENDMENT, 2026-08-23) — the
  estimator of record for rungs D0/A/B/C, which share ONE 100-deck set
  (READ_RULE.md §1.1). For each shared deck, its own margin at each rung it
  has data for is regressed against log2(playouts) INDEPENDENTLY of every
  other deck, and the per-deck slopes are averaged — the CRN analogue of the
  paired-margin trick (differencing the SAME unit across conditions cancels
  that unit's own variance) extended from a single difference to a slope.
  Anchored at D0 (the cheapest shared-deck rung) for the crossover intercept.
  Rung 0 (r1) shares NO decks with D0/A/B/C (disjoint band, 142e9 vs 143e9)
  so it CANNOT enter this estimator — it re-enters only as an independent
  cross-check on the fitted line's backward extrapolation (§READ_RULE.md
  §1.1), never as an input to the primary branch decision.
* **The kill-only interim futility test** (same amendment) — a one-sided,
  early-stop-only check on the AGGREGATE cross-rung fit (the one estimator
  that CAN include rung 0 from the first new rung on, since it needs no
  deck-matching), run after each completed rung.

Usage (real read-out, once games exist):
    .venv/bin/python scripts/carcasum_match/analyze_ladder.py \\
        --rung0 measurement/carcasum_match_20260823/games.jsonl \\
        --rungD0 measurement/carcasum_rung2_20260823/rungD0/games.jsonl --playouts-d0 16384 \\
        --rungA  measurement/carcasum_rung2_20260823/rungA/games.jsonl  --playouts-a  65536 \\
        --rungB  measurement/carcasum_rung2_20260823/rungB/games.jsonl  --playouts-b  131072 \\
        --rungC  measurement/carcasum_rung2_20260823/rungC/games.jsonl  --playouts-c  262144

Usage (interim, kill-only, called by run_cells.sh after each rung's DONE):
    .venv/bin/python scripts/carcasum_match/analyze_ladder.py --interim \\
        --rung0 <path> --rungD0 <path> [--rungA <path> ...]
    # exit 42 if the interim futility test FIRES (stop the ladder); exit 0 otherwise.

Usage (math self-test, no archives, no band spent):
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

#: READ_RULE.md §3.1 — imported vocabulary, not redefined.
REAL_DIVERGENCE_CLASSES = frozenset({
    "SCORE_FINAL", "FARM_SCORE_FINAL", "MEEPLE_LEGALITY", "MEEPLE_SLOT_UNMAPPED",
    "LEGALITY_OURS_EXTRA", "HARNESS_ERROR", "DRIVER_REJECT", "SEAT_DESYNC",
    "COORD_FRAME_MISMATCH",
})

VOID_RATE_BAR = 0.01          # READ_RULE.md §3.1 — 1% of a rung's own games
G_N_FLOOR_FRACTION = 0.80     # READ_RULE.md §3 G-N
G_MODE_TOLERANCE_PCT = 5.0    # READ_RULE.md §3 G-MODE
INTERIM_EXIT_FIRED = 42       # run_cells.sh's stop-the-ladder signal

RUNG0_X = math.log2(32551)    # DESIGN.md §1 — unrounded, r1's own measured median


# --------------------------------------------------------------------------- #
# loading                                                                      #
# --------------------------------------------------------------------------- #
def load(path: Path | str) -> list[dict]:
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
    """Deck-paired margin/SEM (aggregate AND per-deck), win rate/elo, void
    ledger, median+mean realized playouts/turn, G-MODE deviation."""
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
    paired_by_deck: dict[int, float] = {}
    for deck, seats in by_deck.items():
        if len(seats) == 2:
            paired_by_deck[deck] = sum(sum(v) / len(v) for v in seats.values()) / 2.0
    paired = list(paired_by_deck.values())
    mean_p = sum(paired) / len(paired) if paired else None
    var_p = (sum((x - mean_p) ** 2 for x in paired) / (len(paired) - 1)
             if paired and len(paired) > 1 else None)
    sem_p = (var_p / len(paired)) ** 0.5 if var_p is not None else None

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
        "paired_margin_by_deck": paired_by_deck,
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
    vr = stats.get("void_rate") or 0.0
    rr = stats.get("real_divergence_rate") or 0.0
    return vr <= VOID_RATE_BAR and rr <= VOID_RATE_BAR


# --------------------------------------------------------------------------- #
# AGGREGATE weighted least squares — the estimator that CAN include rung 0    #
# from the start (no deck-matching needed), used for the interim test and as  #
# a SECONDARY witness on the final read (READ_RULE.md §1.2).                  #
# --------------------------------------------------------------------------- #
def wls_fit(xs: list[float], ys: list[float], sems: list[float]) -> dict:
    """Weighted least squares, weight_i = 1/sem_i^2. Closed form, stdlib only."""
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
    b0, b1 = fit["beta0"], fit["beta1"]
    if b1 == 0:
        return {"x_star": None, "se_x_star": None, "b_star": None}
    x_star = -b0 / b1
    var_x = (1.0 / (b1 * b1)) * (
        fit["var_beta0"] + x_star * x_star * fit["var_beta1"] + 2 * x_star * fit["cov_beta01"])
    se_x = var_x ** 0.5 if var_x >= 0 else None
    return {"x_star": x_star, "se_x_star": se_x, "b_star": (2 ** x_star) if x_star is not None else None}


def z_interp(x_star: float, se_x_star: float, x0: float, x3: float) -> float:
    if not se_x_star:
        return float("nan")
    return min(x_star - x0, x3 - x_star) / se_x_star


def interim_futility(fit: dict) -> bool:
    """READ_RULE.md §5 (amendment). KILL-ONLY: fires iff the slope point
    estimate is non-negative AND that reading is credible (z_slope >= +2.0).
    A negative-but-not-yet-significant slope (inconclusive) or a
    significantly negative (genuinely closing) slope NEVER fires — kill-only
    means only a confidently WRONG-signed reading stops the ladder early.
    ⚠️ Multiple-look caveat, named not solved: up to 3 interim checks (after
    D0, A, B) each at z>=2 inflate the naive false-early-kill rate versus a
    single look; this is a documented conservatism gap, not corrected by an
    alpha-spending adjustment here (out of scope for this amendment)."""
    b1, z = fit.get("beta1"), fit.get("z_slope")
    return b1 is not None and b1 >= 0 and z is not None and z >= 2.0


# --------------------------------------------------------------------------- #
# WITHIN-DECK slope — the estimator of record for D0/A/B/C (amendment §3)     #
# --------------------------------------------------------------------------- #
def within_deck_slope(shared_rungs: list[tuple[str, float, dict[int, float]]]) -> dict:
    """`shared_rungs`: [(rung_name, x, {deck_seed: margin}), ...] for rungs that
    share the SAME 100-deck set (D0/A/B/C). For each deck present in >=2
    rungs, fits an OLS slope across THAT DECK's own (x, margin) points only —
    a within-unit regression, the slope analogue of a paired difference (it
    cancels the deck's own baseline variance the same way a paired margin
    cancels deck variance). The per-deck slopes are then averaged with a
    standard SEM-of-the-mean over the deck population — decks are i.i.d.
    draws, so this is a legitimate SE, not an approximation borrowed from
    residual variance."""
    all_decks: set[int] = set()
    for _, _, by_deck in shared_rungs:
        all_decks |= set(by_deck.keys())

    per_deck_slope: dict[int, float] = {}
    for deck in all_decks:
        pts = [(x, by_deck[deck]) for _, x, by_deck in shared_rungs if deck in by_deck]
        if len(pts) < 2:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        xbar, ybar = sum(xs) / len(xs), sum(ys) / len(ys)
        sxx = sum((x - xbar) ** 2 for x in xs)
        if sxx == 0:
            continue
        sxy = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys))
        per_deck_slope[deck] = sxy / sxx

    slopes = list(per_deck_slope.values())
    n = len(slopes)
    if n == 0:
        return {"mean_slope": None, "sem_slope": None, "z_slope": None,
                "n_decks_with_slope": 0, "per_deck_slope": per_deck_slope}
    mean_slope = sum(slopes) / n
    if n < 2:
        return {"mean_slope": mean_slope, "sem_slope": None, "z_slope": None,
                "n_decks_with_slope": n, "per_deck_slope": per_deck_slope}
    var_slope = sum((s - mean_slope) ** 2 for s in slopes) / (n - 1)
    sem_slope = (var_slope / n) ** 0.5
    z_slope = mean_slope / sem_slope if sem_slope > 0 else None
    return {"mean_slope": mean_slope, "sem_slope": sem_slope, "z_slope": z_slope,
            "n_decks_with_slope": n, "per_deck_slope": per_deck_slope}


def crossover_anchored(x0: float, margin0: float, sem_margin0: float,
                       mean_slope: float, sem_slope: float) -> dict:
    """x* solving `margin0 + mean_slope*(x - x0) = 0` -> `x* = x0 - margin0/mean_slope`,
    anchored at D0 (x0=the cheapest shared-deck rung, margin0=its own AGGREGATE
    deck-paired margin — §READ_RULE.md §1.1). Delta-method SE, treating margin0
    and mean_slope as independent (an approximation: margin0 is the plain
    aggregate at D0, mean_slope is built from WITHIN-deck differences — related
    but not identical statistics; named, not resolved further here)."""
    if mean_slope == 0:
        return {"x_star": None, "se_x_star": None, "b_star": None}
    x_star = x0 - margin0 / mean_slope
    d_dm0 = -1.0 / mean_slope
    d_dslope = margin0 / (mean_slope * mean_slope)
    var_x = (d_dm0 ** 2) * (sem_margin0 ** 2) + (d_dslope ** 2) * (sem_slope ** 2)
    se_x = var_x ** 0.5
    return {"x_star": x_star, "se_x_star": se_x, "b_star": 2 ** x_star}


# --------------------------------------------------------------------------- #
# READ_RULE.md §4 branch decision — PRIMARY (within-deck) estimator           #
# --------------------------------------------------------------------------- #
def decide_branch(mean_slope, z_slope, cross: dict, x0: float, x3: float) -> dict:
    """⚠️ SIGN CONVENTION, load-bearing: margin = champion - Carcasum, so a
    GENUINE closing trend is a NEGATIVE slope. `z_slope` carries the natural
    sign of `mean_slope`; "credibly closing" is `z_slope <= -2`."""
    x_star = cross["x_star"]

    if x_star is not None and x_star < x0:
        return {"branch": "U-UNREADABLE",
                "reason": ("fitted crossover falls BELOW the anchor rung's own "
                           "budget — contradicts the anchor's own directly-measured "
                           "sign (READ_RULE.md §4 edge case). Flag for design review.")}

    credibly_closing = (mean_slope is not None and mean_slope < 0
                        and z_slope is not None and z_slope <= -2)
    not_crossed_in_range = x_star is None or x_star >= x3

    if mean_slope is None or mean_slope >= 0 or (not credibly_closing and not_crossed_in_range):
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
                            "negative (genuinely closing) but the crossing is "
                            "past the tested range. Queue a 16x rung as an "
                            "OWNER decision.")}

    return {"branch": "U-UNREADABLE",
            "reason": "no branch condition matched cleanly — review by hand."}


# --------------------------------------------------------------------------- #
# self-test                                                                    #
# --------------------------------------------------------------------------- #
def _selftest() -> int:
    # ---- aggregate WLS + crossover + branch (pre-amendment math, unchanged) --
    xs = [15.0, 16.0, 17.0, 18.0]
    ys = [5.0, 4.0, 3.0, 2.0]
    sems = [1.0, 1.0, 1.0, 1.0]
    fit = wls_fit(xs, ys, sems)
    assert abs(fit["beta1"] - (-1.0)) < 1e-9, fit
    cross = crossover(fit)
    assert abs(cross["x_star"] - 20.0) < 1e-9, cross
    print("[selftest] aggregate exact-fit crossover OK: x*=%.4f b*=%.1f" % (cross["x_star"], cross["b_star"]))

    d = decide_branch(fit["beta1"], fit["z_slope"], cross, x0=15.0, x3=18.0)
    assert d["branch"] == "B-BOUND", d
    print("[selftest] aggregate out-of-bracket, credibly closing -> B-BOUND OK")

    ys_flat = [4.0] * 4
    fit_flat = wls_fit(xs, ys_flat, sems)
    cross_flat = {"x_star": None, "se_x_star": None, "b_star": None}
    d_flat = decide_branch(fit_flat["beta1"], fit_flat["z_slope"], cross_flat, x0=15.0, x3=18.0)
    assert d_flat["branch"] == "K-SATURATION", d_flat
    print("[selftest] flat ladder -> K-SATURATION OK")

    ys_in = [2.0, 1.0, -0.4, -1.4]
    sems_tight = [0.3] * 4
    fit_in = wls_fit(xs, ys_in, sems_tight)
    cross_in = crossover(fit_in)
    d_in = decide_branch(fit_in["beta1"], fit_in["z_slope"], cross_in, x0=15.0, x3=18.0)
    assert d_in["branch"] == "A-USABLE-PRICE", d_in
    print("[selftest] in-bracket crossover -> A-USABLE-PRICE OK (x*=%.3f)" % cross_in["x_star"])

    # ---- interim futility (kill-only), amendment ------------------------------
    # (a) confidently wrong-signed (RISING, tight SEMs) -> FIRES. 2-point WLS:
    # beta1 = (y2-y1)/(x2-x1) exactly, se_beta1 = sem*sqrt(2) at x-spacing 1 and
    # equal sems -- z = (y2-y1)/(sem*sqrt(2)) = 1.0/(0.3*1.41421) = 2.357 >= 2.
    fit_2pt_flat = wls_fit([15.0, 16.0], [4.0, 5.0], [0.3, 0.3])
    assert interim_futility(fit_2pt_flat) is True, fit_2pt_flat
    print("[selftest] interim: confidently rising 2-pt (z=%.3f) -> FIRES OK" % fit_2pt_flat["z_slope"])

    # (b) right-signed (closing) even if not hugely significant -> NEVER fires
    fit_2pt_closing_weak = wls_fit([15.0, 16.0], [4.0, 3.5], [2.0, 2.0])
    assert interim_futility(fit_2pt_closing_weak) is False, fit_2pt_closing_weak
    print("[selftest] interim: right-signed (closing), weak -> does NOT fire OK")

    # (c) wrong-signed but NOT confident (wide SEMs) -> does NOT fire (inconclusive)
    fit_2pt_rising_wide = wls_fit([15.0, 16.0], [4.0, 4.5], [3.0, 3.0])
    assert interim_futility(fit_2pt_rising_wide) is False, fit_2pt_rising_wide
    print("[selftest] interim: wrong-signed but not confident -> does NOT fire (inconclusive) OK")

    # ---- within-deck slope, hand-computed --------------------------------------
    # 3 decks, 4 rungs (x=14,16,17,18 for D0/A/B/C). Deck 1: perfectly linear
    # slope -1. Deck 2: perfectly linear slope -2. Deck 3: only 2 rungs present
    # (D0, A), slope exactly -0.5 between them.
    by_deck_d0 = {1: 10.0, 2: 20.0, 3: 5.0}
    by_deck_a  = {1: 8.0,  2: 16.0, 3: 4.0}
    by_deck_b  = {1: 7.0,  2: 14.0}
    by_deck_c  = {1: 6.0,  2: 12.0}
    shared = [("D0", 14.0, by_deck_d0), ("A", 16.0, by_deck_a),
              ("B", 17.0, by_deck_b), ("C", 18.0, by_deck_c)]
    wd = within_deck_slope(shared)
    assert wd["n_decks_with_slope"] == 3, wd
    assert abs(wd["per_deck_slope"][1] - (-1.0)) < 1e-9, wd
    assert abs(wd["per_deck_slope"][2] - (-2.0)) < 1e-9, wd
    assert abs(wd["per_deck_slope"][3] - (-0.5)) < 1e-9, wd
    expected_mean = (-1.0 + -2.0 + -0.5) / 3.0
    assert abs(wd["mean_slope"] - expected_mean) < 1e-9, wd
    print("[selftest] within-deck slope hand-computed OK: mean=%.4f (n_decks=%d)"
          % (wd["mean_slope"], wd["n_decks_with_slope"]))

    cr = crossover_anchored(x0=14.0, margin0=10.0, sem_margin0=0.5,
                            mean_slope=wd["mean_slope"], sem_slope=wd["sem_slope"])
    # x* = 14 - 10/mean_slope ; mean_slope ~ -1.1667 -> x* ~ 14 + 8.5714 = 22.5714
    assert cr["x_star"] > 14.0, cr
    print("[selftest] within-deck anchored crossover OK: x*=%.4f b*=%.1f" % (cr["x_star"], cr["b_star"]))

    print("[selftest] ALL PASS")
    return 0


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rung0", default=None, help="r1's frozen games.jsonl (rung 0, cross-check only)")
    ap.add_argument("--rungD0", default=None)
    ap.add_argument("--rungA", default=None)
    ap.add_argument("--rungB", default=None)
    ap.add_argument("--rungC", default=None)
    ap.add_argument("--playouts-d0", type=int, default=16384)
    ap.add_argument("--playouts-a", type=int, default=65536)
    ap.add_argument("--playouts-b", type=int, default=131072)
    ap.add_argument("--playouts-c", type=int, default=262144)
    ap.add_argument("--n-decks-target", type=int, default=100)
    ap.add_argument("--interim", action="store_true",
                    help="kill-only early-stop check on the AGGREGATE fit; "
                         "exits 42 if it FIRES, 0 otherwise (see run_cells.sh)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    if not args.rung0:
        print("FATAL: --rung0 is required unless --selftest", file=sys.stderr)
        return 2

    shared_defs = []  # (name, path, x, playouts) for D0/A/B/C only
    for name, path, x_playouts, assigned in (
        ("rungD0", args.rungD0, args.playouts_d0, args.playouts_d0),
        ("rungA", args.rungA, args.playouts_a, args.playouts_a),
        ("rungB", args.rungB, args.playouts_b, args.playouts_b),
        ("rungC", args.rungC, args.playouts_c, args.playouts_c),
    ):
        if path:
            shared_defs.append((name, path, math.log2(x_playouts), assigned))

    rung0_stats = per_rung_stats(load(args.rung0), assigned_playouts=None)
    rung0_stats["x_log2_playouts"] = RUNG0_X

    report: dict = {"rungs": {"rung0": rung0_stats}}
    aggregate_points = []  # (x, margin, sem) always eligible to include rung0
    if not gate_d_void(rung0_stats) or rung0_stats["paired_margin_sem"] in (None, 0):
        pass  # rung 0 known-good in practice; still checked, never assumed
    else:
        aggregate_points.append((RUNG0_X, rung0_stats["paired_margin_mean"], rung0_stats["paired_margin_sem"]))

    shared_stats = []  # (name, x, stats) for gate-passing shared-deck rungs
    for name, path, x, assigned in shared_defs:
        stats = per_rung_stats(load(path), assigned_playouts=assigned)
        stats["x_log2_playouts"] = x
        report["rungs"][name] = stats
        ok = (gate_d_void(stats) and gate_g_n(stats, args.n_decks_target)
              and stats.get("g_mode_pass") is not False
              and stats["paired_margin_mean"] is not None
              and stats["paired_margin_sem"] not in (None, 0))
        if ok:
            shared_stats.append((name, x, stats))
            aggregate_points.append((x, stats["paired_margin_mean"], stats["paired_margin_sem"]))
        else:
            report.setdefault("dropped", []).append(name)

    # --- interim mode: aggregate fit only, kill-only exit code -----------------
    if args.interim:
        if len(aggregate_points) < 2:
            print(f"[interim] only {len(aggregate_points)} usable point(s) — cannot fit, NOT firing.")
            return 0
        xs = [p[0] for p in aggregate_points]
        ys = [p[1] for p in aggregate_points]
        sems = [p[2] for p in aggregate_points]
        fit = wls_fit(xs, ys, sems)
        fired = interim_futility(fit)
        print(f"[interim] n_points={len(xs)} beta1={fit['beta1']:.4f} z_slope={fit['z_slope']}")
        print(f"[interim] {'FIRES -- STOP THE LADDER' if fired else 'does not fire -- continue'}")
        return INTERIM_EXIT_FIRED if fired else 0

    # --- full read-out: SECONDARY aggregate witness -----------------------------
    if len(aggregate_points) >= 2:
        xs = [p[0] for p in aggregate_points]
        ys = [p[1] for p in aggregate_points]
        sems = [p[2] for p in aggregate_points]
        agg_fit = wls_fit(xs, ys, sems)
        agg_cross = crossover(agg_fit)
        report["aggregate_fit_secondary"] = agg_fit
        report["aggregate_crossover_secondary"] = agg_cross

    # --- PRIMARY: within-deck slope over D0/A/B/C, anchored at the cheapest ----
    if len(shared_stats) >= 2:
        shared_stats.sort(key=lambda t: t[1])  # by x, ascending
        shared_tuples = [(name, x, stats["paired_margin_by_deck"]) for name, x, stats in shared_stats]
        wd = within_deck_slope(shared_tuples)
        report["within_deck_slope_primary"] = {k: v for k, v in wd.items() if k != "per_deck_slope"}
        report["within_deck_n_decks"] = wd["n_decks_with_slope"]

        anchor_name, anchor_x, anchor_stats = shared_stats[0]
        x0 = anchor_x
        x3 = shared_stats[-1][1]
        if wd["mean_slope"] is not None and wd["sem_slope"]:
            cross = crossover_anchored(x0, anchor_stats["paired_margin_mean"],
                                       anchor_stats["paired_margin_sem"],
                                       wd["mean_slope"], wd["sem_slope"])
            report["primary_crossover"] = cross
            decision = decide_branch(wd["mean_slope"], wd["z_slope"], cross, x0, x3)
            report["branch"] = decision["branch"]
            report["reason"] = decision["reason"]
            if "z_interp" in decision:
                report["z_interp"] = decision["z_interp"]

            # rung 0 cross-check (never a branch input)
            if wd["mean_slope"]:
                predicted_at_rung0 = anchor_stats["paired_margin_mean"] + wd["mean_slope"] * (RUNG0_X - x0)
                report["rung0_crosscheck"] = {
                    "predicted_margin_at_rung0_x": predicted_at_rung0,
                    "measured_margin_at_rung0": rung0_stats["paired_margin_mean"],
                    "diff": (predicted_at_rung0 - rung0_stats["paired_margin_mean"])
                            if rung0_stats["paired_margin_mean"] is not None else None,
                }
        else:
            report["branch"] = "D-UNREADABLE"
            report["reason"] = "within-deck slope undefined (insufficient shared decks with >=2 rung points)"
    else:
        report["branch"] = "D-UNREADABLE"
        report["reason"] = (f"only {len(shared_stats)}/4 shared-deck rungs usable — "
                             "need >=2 of D0/A/B/C for the within-deck estimator.")

    if args.json:
        print(json.dumps(report, indent=1, default=str))
    else:
        for name, stats in report["rungs"].items():
            print(f"[{name}] n_scored={stats['n_scored']} paired_margin="
                  f"{stats['paired_margin_mean']} +/- {stats['paired_margin_sem']} "
                  f"median_playouts={stats['median_opp_playouts_per_turn']} "
                  f"g_mode_pass={stats.get('g_mode_pass')}")
        if report.get("dropped"):
            print("DROPPED:", report["dropped"])
        if "within_deck_slope_primary" in report:
            wd = report["within_deck_slope_primary"]
            print(f"within-deck slope (PRIMARY): mean={wd['mean_slope']} sem={wd['sem_slope']} "
                  f"z={wd['z_slope']} n_decks={wd['n_decks_with_slope']}")
        if "primary_crossover" in report:
            print(f"primary crossover: x*={report['primary_crossover']['x_star']} "
                  f"B*={report['primary_crossover']['b_star']}")
        if "rung0_crosscheck" in report:
            print("rung0 cross-check (witness only):", report["rung0_crosscheck"])
        print(f"\nBRANCH: {report.get('branch')}")
        print(f"REASON: {report.get('reason')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
