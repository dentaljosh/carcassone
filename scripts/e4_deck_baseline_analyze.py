#!/usr/bin/env python3
"""E4 deck baseline — the pre-registered analysis.

Reads the self-play JSONL written by `scripts/e4_deck_baseline.py` plus the 12
`fixed_v1` E4 archives, and computes exactly what
`measurement/e4_deck_baseline_20260807/SPEC.md` pre-registered:

  d_i   = mean seat-0 self-play margin of deck i over its K replicates (se_i = sd_i/sqrt(K))
  m_i   = Joshua's own realized seat-0 margin on deck i
  adj_i = m_i - beta * (d_i - mean(d))        for beta in {1, beta_hat}
  beta_hat = Cov(m, d) / Var(d)

SIGN: positive = seat 0 = Joshua ahead, in every field.

⚠️ THE ADJUSTMENT IS CENTRED, so `mean(adj) == mean(m)` for ANY beta — the three
estimates share one point estimate and differ only in their **se**. Precision is the
whole deliverable; the readout says so in those words.

HEADLINE RULE (pre-registered): the headline is whichever of `unadjusted` / `beta_hat`
has the SMALLER realized se. beta=1 is reported for completeness and is never the
headline. beta_hat's se pays ddof=2 for the estimated beta.

Pure stdlib maths (no numpy dependency) so the estimator is unit-testable without the
engine. Usage:
    .venv/bin/python scripts/e4_deck_baseline_analyze.py \
        --jsonl measurement/e4_deck_baseline_20260807/selfplay.jsonl --json out.json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


# --------------------------------------------------------------------------- #
# small-stats helpers (stdlib only)                                            #
# --------------------------------------------------------------------------- #
def mean(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs)


def var(xs, ddof: int = 1) -> float:
    xs = list(xs)
    n = len(xs)
    if n - ddof <= 0:
        return float("nan")
    mu = mean(xs)
    return sum((x - mu) ** 2 for x in xs) / (n - ddof)


def sd(xs, ddof: int = 1) -> float:
    v = var(xs, ddof)
    return math.sqrt(v) if v == v and v >= 0 else float("nan")


def cov(xs, ys, ddof: int = 1) -> float:
    xs, ys = list(xs), list(ys)
    n = len(xs)
    if n - ddof <= 0:
        return float("nan")
    mx, my = mean(xs), mean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (n - ddof)


def corr(xs, ys) -> float:
    sx, sy = sd(xs), sd(ys)
    if not (sx > 0 and sy > 0):
        return float("nan")
    return cov(xs, ys) / (sx * sy)


# --------------------------------------------------------------------------- #
# the estimator (unit-tested against synthetic data with a known deck effect)  #
# --------------------------------------------------------------------------- #
def control_variate(m: list[float], d: list[float]) -> dict:
    """The three pre-registered estimates of mean(m), with their se's.

    `m` = the human margins, `d` = the deck values, aligned by deck.
    Returns point estimates (all equal, by construction of the centred form), se's,
    beta_hat with its own se, and the realized variance-reduction ratio."""
    n = len(m)
    if n != len(d) or n < 3:
        raise ValueError(f"need >=3 aligned pairs; got {n} and {len(d)}")
    dbar = mean(d)
    dc = [x - dbar for x in d]

    vd = var(d)
    beta_hat = cov(m, d) / vd if vd > 0 else 0.0

    def adjusted(beta, ddof):
        adj = [mi - beta * ci for mi, ci in zip(m, dc)]
        return adj, mean(adj), sd(adj, ddof=ddof) / math.sqrt(n)

    adj1, pt1, se1 = adjusted(1.0, 1)
    adjb, ptb, seb = adjusted(beta_hat, 2)      # ddof=2: pay for the estimated beta
    _, _, seb_ddof1 = adjusted(beta_hat, 1)     # comparable-convention companion

    se_raw = sd(m) / math.sqrt(n)
    # OLS se(beta): sqrt( SSE/(n-2) / Sxx )
    sse = sum((a - ptb) ** 2 for a in adjb)
    sxx = sum(c * c for c in dc)
    se_beta = math.sqrt((sse / (n - 2)) / sxx) if sxx > 0 else float("nan")

    r = corr(m, d)
    est = {
        "n": n,
        "unadjusted": {"estimate": mean(m), "se": se_raw, "sd": sd(m)},
        "beta1": {"beta": 1.0, "estimate": pt1, "se": se1, "sd": sd(adj1),
                  "adjusted": adj1},
        "beta_hat": {"beta": beta_hat, "se_beta": se_beta,
                     "estimate": ptb, "se": seb, "se_ddof1": seb_ddof1,
                     "sd": sd(adjb, ddof=1), "adjusted": adjb},
        "corr_m_d": r,
        "r_squared": r * r if r == r else float("nan"),
        # realized variance reduction: <1 means the adjustment HELPED.
        "var_ratio_beta1": (se1 / se_raw) ** 2 if se_raw > 0 else float("nan"),
        "var_ratio_beta_hat": (seb / se_raw) ** 2 if se_raw > 0 else float("nan"),
        # supplementary, explicitly NOT the headline (SPEC): the absolute deck tilt.
        "mean_deck_value": dbar,
        "uncentred_beta1_estimate": mean([mi - di for mi, di in zip(m, d)]),
    }
    est["headline"] = "beta_hat" if seb < se_raw else "unadjusted"
    est["headline_se"] = min(seb, se_raw)
    est["adjustment_helped"] = bool(seb < se_raw)
    return est


def deck_summaries(records: list[dict]) -> dict:
    """deck_seed -> {n, mean, sd, se, margins} over the self-play replicates."""
    by: dict[int, list[int]] = {}
    for r in records:
        by.setdefault(int(r["deck_seed"]), []).append(int(r["margin_seat0_minus_seat1"]))
    out = {}
    for seed, ms in by.items():
        s = sd(ms) if len(ms) > 1 else float("nan")
        out[seed] = {
            "n": len(ms), "margins": sorted(ms),
            "mean": mean(ms), "sd": s,
            "se": (s / math.sqrt(len(ms))) if len(ms) > 1 else float("nan"),
        }
    return out


def deck_effect_icc(decks: dict) -> dict:
    """Do these decks differ at all beyond replicate noise?

    between-deck variance of the TRUE deck effect ~= Var(d_hat) - mean(se_i^2)
    (the sampling noise the K-replicate mean carries), and ICC = sigma2_deck /
    (sigma2_deck + sigma2_within)."""
    dh = [v["mean"] for v in decks.values()]
    within = [v["sd"] ** 2 for v in decks.values() if v["sd"] == v["sd"]]
    ses = [v["se"] ** 2 for v in decks.values() if v["se"] == v["se"]]
    s2_within = mean(within) if within else float("nan")
    v_dhat = var(dh)
    s2_deck = v_dhat - (mean(ses) if ses else 0.0)
    icc = (s2_deck / (s2_deck + s2_within)) if (s2_deck + s2_within) > 0 else float("nan")
    return {
        "sd_deck_values_observed": sd(dh),
        "var_deck_values_observed": v_dhat,
        "mean_within_deck_var": s2_within,
        "sd_within_deck": math.sqrt(s2_within) if s2_within == s2_within else float("nan"),
        "var_deck_effect_est": s2_deck,
        "sd_deck_effect_est": math.sqrt(s2_deck) if s2_deck > 0 else 0.0,
        "icc_selfplay": icc,
        "note": ("var_deck_effect_est <= 0 means the observed spread of deck means is "
                 "no larger than replicate noise alone: these decks are "
                 "INDISTINGUISHABLE at this K."),
    }


# --------------------------------------------------------------------------- #
def load_jsonl(path) -> list[dict]:
    recs = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line:
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                pass                      # torn last line from a dirty crash
    return recs


def analyze(jsonl_path, archive_dir=None, profile="fixed_v1") -> dict:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from e4_deck_baseline import DEFAULT_ARCHIVES, select_archives

    archives = select_archives(archive_dir or DEFAULT_ARCHIVES, profile)
    recs = load_jsonl(jsonl_path)
    decks = deck_summaries(recs)

    rows, m, d = [], [], []
    missing = []
    for a in archives:
        seed = a["deck_seed"]
        if seed not in decks:
            missing.append(seed)
            continue
        v = decks[seed]
        rows.append({
            "deck_seed": seed, "archive_file": a["file"],
            "human_scores": a["scores"],
            "human_margin": a["margin_seat0_minus_seat1"],
            "deck_value": v["mean"], "deck_value_se": v["se"],
            "deck_value_sd": v["sd"], "k_replicates": v["n"],
            "selfplay_margins": v["margins"],
            "terrain": "downhill" if v["mean"] > 0 else "uphill",
        })
        m.append(float(a["margin_seat0_minus_seat1"]))
        d.append(float(v["mean"]))

    # `m`/`d`/`rows` are built in the SAME order, so index i is deck rows[i]; attach
    # the adjusted values BEFORE re-sorting the table for display.
    est = control_variate(m, d) if len(m) >= 3 else {"error": "too few decks"}
    if "beta_hat" in est:
        for i, r in enumerate(rows):
            r["adj_beta1"] = est["beta1"]["adjusted"][i]
            r["adj_beta_hat"] = est["beta_hat"]["adjusted"][i]
    rows.sort(key=lambda r: r["deck_value"])

    spm = [r["secs_per_move"] for r in recs if "secs_per_move" in r]
    return {
        "schema": "carcassonne-e4-deck-baseline-analysis/v1",
        "jsonl": str(jsonl_path),
        "profile": profile,
        "sign_convention": "positive = seat 0 = Joshua ahead (scores[0] - scores[1])",
        "n_selfplay_games": len(recs),
        "n_decks": len(rows),
        "missing_decks": missing,
        "per_deck": rows,
        "deck_spread": deck_effect_icc({r["deck_seed"]: decks[r["deck_seed"]] for r in rows}),
        "estimates": est,
        "selfplay_cost": {"mean_secs_per_move": mean(spm) if spm else None,
                          "n": len(spm)},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", required=True)
    ap.add_argument("--archives", default=None)
    ap.add_argument("--profile", default="fixed_v1")
    ap.add_argument("--json", default=None, help="write the full analysis here")
    args = ap.parse_args(argv)

    res = analyze(args.jsonl, args.archives, args.profile)
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=1))
    e = res["estimates"]
    print(f"n_decks={res['n_decks']}  games={res['n_selfplay_games']}  "
          f"({res['sign_convention']})")
    print(f"  unadjusted : {e['unadjusted']['estimate']:+.2f} +- {e['unadjusted']['se']:.2f}")
    print(f"  beta=1     : {e['beta1']['estimate']:+.2f} +- {e['beta1']['se']:.2f}")
    print(f"  beta_hat   : {e['beta_hat']['estimate']:+.2f} +- {e['beta_hat']['se']:.2f}"
          f"   (beta_hat={e['beta_hat']['beta']:+.3f} +- {e['beta_hat']['se_beta']:.3f})")
    print(f"  corr(m,d)={e['corr_m_d']:+.3f}  var_ratio(beta_hat)={e['var_ratio_beta_hat']:.3f}"
          f"  HEADLINE={e['headline']}  helped={e['adjustment_helped']}")
    ds = res["deck_spread"]
    print(f"  deck spread: sd(d_hat)={ds['sd_deck_values_observed']:.2f} "
          f"vs within-deck sd={ds['sd_within_deck']:.2f}  "
          f"icc_selfplay={ds['icc_selfplay']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
