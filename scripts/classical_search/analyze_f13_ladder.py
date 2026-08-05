#!/usr/bin/env python3
"""F13 exact-K ladder — the PRE-REGISTERED analysis (written before any cell ran).

Prereg of record (BINDING): measurement/exact_k_ladder_20260803/PREREG_DRAFT.md
Cells written by:           scripts/classical_search/f13_ladder_launcher.sh
                            -> scripts/classical_search/eval_puct_priors.py
Tail machinery / censoring: scripts/classical_search/exact_tail.py (imported, never
                            reimplemented — `censored_rate` is the pre-registered
                            statistic and this script must not fork a second copy).

WHAT THIS COMPUTES, AND WHY IT IS FIXED BEFORE THE DATA EXISTS
--------------------------------------------------------------
Per rung (K=2 control, K=3, K=5, K=6 vs the K=4 incumbent):
  n / W-D-L / winrate, elo +/- 1sigma, the deck-paired seat-balanced margin and its
  paired z, cap-hit counters, and the pre-registered censored rate.

The PRIMARY statistic (prereg "Design"; memory `feedback_trend_beats_underpowered_steps`)
is the WITHIN-BAND TREND across rungs: the per-deck slope of the seat-balanced margin
against K, fitted on the decks that ALL entering rungs share (CRN). It is deliberately
NOT an across-cell regression of the per-rung means: the rungs share a band by design,
so the deck draw is common and a naive fit throws away the pairing that makes the
contrast the robust class. If the decks turn out NOT to be shared, this script REFUSES
to report a trend rather than reporting a wrong one.

Everything is recomputed from the per-game records (`seed<12d>_a<seat>.json`), not read
off `summary.json` — and then CROSS-CHECKED against `summary.json`, with any discrepancy
surfaced as a warning. (House rule: read the emitter before writing the parser.)

DECISION MAP (prereg, as amended 2026-08-04). Branch 4 is checked FIRST and DOMINATES.
  4. K=2 control rung reads > +2 sigma  -> INSTRUMENT ALARM: halt and audit; every
     other conclusion is SUPPRESSED. (Also fires if the INCUMBENT arm hit a wall cap:
     its K<=4 tail is uncapped by construction.)
  2. a K>=5 rung >= +2 sigma UNCENSORED, or the trend slope z >= +2 -> per the
     2026-08-04 amendment this does NOT fund the endgame net: it buys a CONFIRM cell
     at the DEPLOY budget 11008 on fresh decks of a NEW band. Only a surviving confirm
     funds the net.
  3. censored-positive (signal but cap-hit rate > 20%) -> raise caps x3 on that rung,
     n=200 re-run, re-enter the map.
  1. all rungs' paired-margin z < +2 AND trend slope z < +2 -> the June null
     generalizes, powered and modern-era; the endgame-net lever is STILLBORN.
     (A null at the 2750 screen budget is the STRONGER conclusion and transfers
     upward — prereg amendment.)

POWER, PRINTED BESIDE EVERY ESTIMATE so a null is never over-read as "no effect":
n=400 deck-paired resolves roughly +/-12 elo at 1 sigma; the realised per-rung 1 sigma
and the 2-sigma minimum detectable effect are printed per rung from the data itself.

Usage
-----
  python3 scripts/classical_search/analyze_f13_ladder.py \
      --out-root /mnt/c/carc-shared/exact_k_ladder --band 106000000000 \
      --verdict-json measurement/exact_k_ladder_20260803/VERDICT.json

  # or point at explicit cells:
  python3 scripts/classical_search/analyze_f13_ladder.py CELL_DIR [CELL_DIR ...]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exact_tail as et  # noqa: E402

SCHEMA = "f13_ladder_analysis/1"
PREREG = "measurement/exact_k_ladder_20260803/PREREG_DRAFT.md"

# Pre-registered thresholds. Z_FIRE is the "+2 sigma" of the decision map; it is a
# ONE-SIDED threshold on a signed statistic (positive == deeper exactness helps).
Z_FIRE = 2.0
CONTROL_K = 2           # the negative-control rung
INCUMBENT_K = 4         # production's clairvoyant tail == the both-sides base
SCREEN_SIMS = 2750      # prereg amendment: the ladder runs at the A/B SCREEN budget
DEPLOY_SIMS = 11008     # ... and a positive buys a confirm at the DEPLOY budget
NOMINAL_PAIRED_1SIGMA_ELO = 12.0   # n=400 deck-paired, the standing house figure


# --------------------------------------------------------------------------- #
# loading                                                                      #
# --------------------------------------------------------------------------- #
def _read_json(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def load_cell(d: Path) -> dict:
    """Load one rung's directory: manifest + summary + every per-game record."""
    d = Path(d)
    manifest = _read_json(d / "manifest.json") or {}
    summary = _read_json(d / "summary.json") or {}
    games = []
    for p in sorted(d.glob("seed*_a*.json")):
        g = _read_json(p)
        if isinstance(g, dict) and "diff" in g:
            games.append(g)
    cfg = manifest.get("config") or {}
    tail = cfg.get("exact_tail") or {}
    rp = manifest.get("rules_profile") or {}

    # The AUTHORITATIVE per-arm K is config.exact_tail (the block F13 added) — for BOTH
    # manifest generations, which is why it stays the source of truth here:
    #   * OLD manifests (emitted before 2026-08-04) stamp the CANDIDATE's `exact_k` into
    #     the round-robin `config.opponent` block as well, so the incumbent's K reads
    #     WRONG there. Those cells are on disk and immutable.
    #   * NEW manifests stamp the opponent's resolved `_opp_exact_k` correctly.
    # Reading exact_tail parses both generations identically; reading config.opponent
    # would silently mis-report every pre-fix cell. Do NOT "upgrade" this to the
    # candidate/opponent blocks (tests/test_analyze_f13_ladder.py pins both generations).
    cand_k = tail.get("cand_exact_k")
    opp_k = tail.get("opp_exact_k")
    if cand_k is None and games:
        cand_k = max(int(g.get("cand_tail_k", 0)) for g in games)
    if opp_k is None and games:
        opp_k = max(int(g.get("champ_tail_k", 0)) for g in games)
    if cand_k is None:
        m = re.search(r"k(\d+)\s*$", d.name)
        cand_k = int(m.group(1)) if m else None

    return {
        "dir": str(d),
        "name": d.name,
        "manifest": manifest,
        "summary": summary,
        "games": games,
        "cand_k": None if cand_k is None else int(cand_k),
        "opp_k": None if opp_k is None else int(opp_k),
        "band": cfg.get("seed_start"),
        "exp_id": cfg.get("exp_id"),
        "n_planned": cfg.get("n"),
        "cand_sims": cfg.get("cand_sims"),
        "champ_sims": cfg.get("champ_sims"),
        "wall_caps": tail.get("wall_caps") or {},
        "k_floor": tail.get("k_floor"),
        "solver": tail.get("solver"),
        "ladder_engaged": bool(tail.get("ladder_engaged")),
        "rules_profile": rp.get("name"),
        "r9_env_ok": rp.get("r9_env_ok"),
        "code_rev": manifest.get("code_rev"),
    }


def discover_cells(out_root: Path, band: int | None, prefix: str | None) -> list[Path]:
    """Every F13 cell directory under `out_root` (optionally filtered to one band).

    The band filter is what keeps the throwaway SMOKE bands (launcher: BAND+9e8 and
    +9e8+1000) out of the ladder — a smoke cell must never enter a verdict.
    """
    out = []
    for man in sorted(Path(out_root).glob("*/manifest.json")):
        d = man.parent
        if prefix and not d.name.startswith(prefix):
            continue
        m = _read_json(man) or {}
        cfg = m.get("config") or {}
        tail = cfg.get("exact_tail") or {}
        if not tail.get("ladder_engaged"):
            continue
        if band is not None and int(cfg.get("seed_start", -1)) != int(band):
            continue
        out.append(d)
    return out


# --------------------------------------------------------------------------- #
# per-rung statistics (formulas mirrored from eval_puct_priors._summary)        #
# --------------------------------------------------------------------------- #
def deck_margins(games: list[dict]) -> dict[int, float]:
    """Per-deck SEAT-BALANCED margin: (diff@seat0 + diff@seat1) / 2, cand - opponent.

    Mirrors `eval_puct_priors._paired_z`: only decks with BOTH seats count, and
    watchdog-abandoned games (`game_timeout`) are excluded from every strength stat
    (their board is non-terminal, so their `diff` is not an outcome).
    """
    by_seed: dict[int, dict[int, int]] = {}
    for g in games:
        if g.get("game_timeout"):
            continue
        by_seed.setdefault(int(g["seed"]), {})[int(g["a_seat"])] = int(g["diff"])
    return {s: (v[0] + v[1]) / 2.0 for s, v in by_seed.items() if 0 in v and 1 in v}


def _paired(margins: dict[int, float]) -> tuple[float | None, float | None,
                                                float | None, int]:
    """(mean margin, se, z, n_decks) — the harness's paired estimator, verbatim."""
    ds = list(margins.values())
    if len(ds) < 2:
        return None, None, None, len(ds)
    mean = sum(ds) / len(ds)
    var = sum((x - mean) ** 2 for x in ds) / (len(ds) - 1)
    se = math.sqrt(var / len(ds))
    z = (mean / se) if se > 0 else float("nan")
    return mean, se, z, len(ds)


def censoring(games: list[dict]) -> dict:
    """The pre-registered censoring block, via exact_tail's OWN functions.

    Deliberately computed over ALL games INCLUDING watchdog-abandoned ones — matching
    `eval_puct_priors.f13_cell_block`: censoring is a statement about the SOLVER's
    behaviour, not about the strength sample.
    """
    rs = [g for g in games if g.get("f13_on")]
    if not rs:
        return {}

    def side(pfx: str) -> dict:
        return {
            "exact_k": max(int(g.get(f"{pfx}_tail_k", 0)) for g in rs),
            "eff_k_min": min(int(g.get(f"{pfx}_eff_k_final", 0)) for g in rs),
            "latch_solves": sum(int(g.get(f"{pfx}_latch_solves", 0)) for g in rs),
            "capped_attempts": sum(int(g.get(f"{pfx}_capped_attempts", 0)) for g in rs),
            "cap_hits": sum(int(g.get(f"{pfx}_cap_hits", 0)) for g in rs),
            "fallback_depth": sum(int(g.get(f"{pfx}_fallback_depth", 0)) for g in rs),
            "games_with_cap_hit": sum(1 for g in rs
                                      if int(g.get(f"{pfx}_cap_hits", 0)) > 0),
            "max_solve_secs": max((float(g.get(f"{pfx}_max_solve_secs", 0.0))
                                   for g in rs), default=0.0),
        }

    block = et.censoring_block(side("cand"), side("champ"))
    block["games"] = len(rs)
    return block


def rung_stats(cell: dict) -> dict:
    """Everything the prereg asks for, per rung, recomputed from per-game records."""
    games = cell["games"]
    played = [g for g in games if not g.get("game_timeout")]
    n = len(played)
    w = sum(1 for g in played if g.get("won_by_cand"))
    dr = sum(1 for g in played if g.get("drew"))
    losses = n - w - dr
    out = dict(cell)
    out.pop("games", None)
    out.pop("manifest", None)
    out.update({
        "n": n, "W": w, "D": dr, "L": losses,
        "game_timeouts": len(games) - n,
        "winrate": float("nan"), "winrate_z": float("nan"),
        "elo": float("nan"), "elo_sig_1sigma": float("nan"),
        "elo_mde_2sigma": float("nan"), "avg_diff": float("nan"),
    })
    if n:
        wr = (w + 0.5 * dr) / n
        wr_se = math.sqrt(0.25 / n)
        out["winrate"] = wr
        out["winrate_z"] = (wr - 0.5) / wr_se
        out["avg_diff"] = sum(int(g["diff"]) for g in played) / n
        if 0 < wr < 1:
            elo = 400.0 * math.log10(wr / (1 - wr))
            sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
        else:
            elo, sig = math.copysign(800.0, wr - 0.5), float("nan")
        out["elo"] = elo
        out["elo_sig_1sigma"] = sig
        out["elo_mde_2sigma"] = 2.0 * sig

    margins = deck_margins(games)
    mean, se, z, npair = _paired(margins)
    out.update({
        "paired_mean_margin": mean, "paired_se": se, "paired_z": z,
        "n_paired": npair,
        "margin_mde_2sigma": (2.0 * se) if se is not None else None,
    })

    cen = censoring(games)
    cand = cen.get("candidate", {})
    out.update({
        "latch_solves": cand.get("latch_solves"),
        "capped_attempts": cand.get("capped_attempts"),
        "cap_hits": cand.get("cap_hits"),
        "fallback_depth": cand.get("fallback_depth"),
        "games_with_cap_hit": cand.get("games_with_cap_hit"),
        "eff_k_min": cand.get("eff_k_min"),
        "max_solve_secs": cand.get("max_solve_secs"),
        "censored_rate": cen.get("censored_rate"),
        "censored_rate_capped": cen.get("censored_rate_capped"),
        "censored": bool(cen.get("censored")),
        "censor_threshold": cen.get("threshold", et.CENSOR_THRESHOLD),
        "censor_banner": cen.get("banner", ""),
        "opponent_cap_hits_alarm": bool(cen.get("opponent_cap_hits_alarm")),
        "opponent_cap_hits": (cen.get("opponent") or {}).get("cap_hits"),
    })
    out["stamp"] = ("NOT-A-VERDICT" if out["censored"] else "ok")
    out["_margins"] = margins
    return out


def crosscheck(rung: dict, summary: dict) -> list[str]:
    """Recomputed-vs-emitted discrepancies (the parser is not trusted over the emitter)."""
    warns = []
    if not summary:
        return ["no summary.json in %s — stats are recomputed-only" % rung["name"]]
    for key, mine, tol in (("n", rung["n"], 0), ("W", rung["W"], 0),
                           ("D", rung["D"], 0), ("L", rung["L"], 0)):
        theirs = summary.get(key)
        if theirs is not None and abs(int(theirs) - int(mine)) > tol:
            warns.append(f"{rung['name']}: summary.json {key}={theirs} but per-game "
                         f"records give {mine} (partial/racing cell?)")
    for key, mine in (("paired_z", rung["paired_z"]),
                      ("paired_mean_margin", rung["paired_mean_margin"]),
                      ("elo", rung["elo"])):
        theirs = summary.get(key)
        if theirs is None or mine is None:
            continue
        if not math.isfinite(float(theirs)) or not math.isfinite(float(mine)):
            continue
        if abs(float(theirs) - float(mine)) > 1e-6 * max(1.0, abs(float(theirs))) + 1e-3:
            warns.append(f"{rung['name']}: summary.json {key}={theirs:.4f} vs "
                         f"recomputed {mine:.4f}")
    return warns


# --------------------------------------------------------------------------- #
# the PRIMARY statistic: the within-band, deck-matched trend across rungs       #
# --------------------------------------------------------------------------- #
def trend(rungs: list[dict], *, include_identity_anchor: bool = False,
          min_shared_frac: float = 0.5) -> dict:
    """Per-deck slope of the seat-balanced margin against K, on the SHARED decks.

    For each deck s common to every entering rung, the within-deck OLS slope is

        b_s = sum_r (K_r - Kbar) * d_{r,s} / sum_r (K_r - Kbar)^2

    and the reported slope is mean(b_s) with se = sd(b_s)/sqrt(S), z = slope/se.
    That is the CRN estimator: the deck draw is differenced out exactly, which is the
    whole reason the prereg puts all rungs on one band. A naive regression of the
    per-rung MEANS against K would ignore the pairing and be both wrong-variance and
    (given the measured 1.8-2.2x cross-band over-dispersion) over-confident.

    `include_identity_anchor` optionally adds the structural K=4 point at margin 0
    (candidate == incumbent). It is OFF by default: K=4 is an identity, not a measured
    cell, and a zero-variance anchor would shrink the se of a slope no data supports.

    Returns a dict that always carries `ok`; when `ok` is False, `refusal` says why —
    this function REFUSES rather than reporting a trend the pairing cannot support.
    """
    res = {"ok": False, "refusal": None, "rungs_used": [], "k": [],
           "n_shared_decks": 0, "slope": None, "se": None, "z": None,
           "include_identity_anchor": bool(include_identity_anchor),
           "per_rung_mean_on_shared": {}}
    usable = [r for r in rungs if r.get("cand_k") is not None and r.get("_margins")]
    if len(usable) < 2:
        res["refusal"] = (f"only {len(usable)} rung(s) carry per-deck margins; a trend "
                          f"needs >= 2 rungs")
        return res

    bands = {r.get("band") for r in usable}
    if len(bands) > 1:
        res["refusal"] = (f"rungs span MULTIPLE seed bands {sorted(map(str, bands))} — "
                          f"the prereg's within-band deck-matched contrast does not "
                          f"exist across bands (cross-band z's are over-dispersed "
                          f"1.8-2.2x). REFUSING to report a trend.")
        return res

    ks = [int(r["cand_k"]) for r in usable]
    if len(set(ks)) < 2:
        res["refusal"] = f"all entering rungs share K={ks[0]}; a slope in K is undefined"
        return res

    shared = set(usable[0]["_margins"])
    for r in usable[1:]:
        shared &= set(r["_margins"])
    percell = [len(r["_margins"]) for r in usable]
    res["n_shared_decks"] = len(shared)
    res["per_rung_deck_counts"] = dict(zip([r["name"] for r in usable], percell))
    if len(shared) < 2:
        res["refusal"] = (f"the rungs share {len(shared)} deck(s) "
                          f"(per-rung deck counts {percell}) — the decks are NOT shared "
                          f"across rungs, so the pre-registered within-band deck-matched "
                          f"trend DOES NOT EXIST. REFUSING to report a trend; do not "
                          f"substitute an across-cell regression, it ignores the CRN "
                          f"structure the design rests on.")
        return res
    if len(shared) < min_shared_frac * max(percell):
        res["warning"] = (f"only {len(shared)} of {max(percell)} decks are shared across "
                          f"rungs ({len(shared)/max(percell):.0%}) — the trend is fitted "
                          f"on a thin common subset; treat with the same humility as an "
                          f"unpaired contrast")

    decks = sorted(shared)
    kk = list(ks)
    cols = [[r["_margins"][s] for s in decks] for r in usable]
    if include_identity_anchor:
        kk = kk + [INCUMBENT_K]
        cols = cols + [[0.0] * len(decks)]
    K = np.asarray(kk, dtype=float)
    M = np.asarray(cols, dtype=float)              # (rungs, decks)
    kc = K - K.mean()
    denom = float((kc ** 2).sum())
    if denom <= 0:
        res["refusal"] = "zero variance in K across the entering rungs"
        return res
    b = (kc[:, None] * M).sum(axis=0) / denom      # per-deck slope, pts per unit K
    slope = float(b.mean())
    se = float(b.std(ddof=1) / math.sqrt(len(b))) if len(b) > 1 else float("nan")
    res.update({
        "ok": True,
        "rungs_used": [r["name"] for r in usable],
        "k": kk,
        "slope": slope,
        "se": se,
        "z": (slope / se) if se and se > 0 else float("nan"),
        "slope_mde_2sigma": (2.0 * se) if se and math.isfinite(se) else None,
        "units": "points of seat-balanced margin per +1 K",
        "per_rung_mean_on_shared": {r["name"]: float(np.mean(c))
                                    for r, c in zip(usable, cols[:len(usable)])},
        "estimator": ("per-deck within-deck OLS slope on shared decks (CRN); "
                      "mean +/- sd/sqrt(S)"),
    })
    return res


# --------------------------------------------------------------------------- #
# the decision map                                                             #
# --------------------------------------------------------------------------- #
def decide(rungs: list[dict], tr: dict) -> dict:
    """Evaluate the pre-registered decision map. Branch 4 is checked FIRST and, when
    it fires, SUPPRESSES every other conclusion."""
    fired: list[dict] = []
    alarms: list[str] = []

    def z_of(r):
        z = r.get("paired_z")
        return z if (z is not None and math.isfinite(z)) else None

    # ---- BRANCH 4 (checked first, dominates) --------------------------------- #
    control = [r for r in rungs if r.get("cand_k") == CONTROL_K]
    for r in control:
        z = z_of(r)
        if z is not None and z > Z_FIRE:
            alarms.append(f"K={CONTROL_K} negative-control rung reads z={z:+.2f} "
                          f"(> +{Z_FIRE:g}): a SHALLOWER tail beats production.")
    for r in rungs:
        if r.get("opponent_cap_hits_alarm"):
            alarms.append(f"{r['name']}: the INCUMBENT arm hit a wall cap "
                          f"({r.get('opponent_cap_hits')} hits) — its K<={INCUMBENT_K} "
                          f"tail is uncapped by construction.")
    if alarms:
        return {
            "primary_branch": 4,
            "label": "INSTRUMENT ALARM — halt and audit",
            "action": ("Halt. Audit the harness before interpreting ANYTHING. Per the "
                       "prereg this branch dominates: no other branch may be reported "
                       "as a finding while it is live."),
            "alarms": alarms,
            "suppressed": True,
            "fired": [{"branch": 4, "why": a} for a in alarms],
        }

    # ---- BRANCH 2 (uncensored positive, or trend positive) ------------------- #
    deep_pos_uncensored = [r for r in rungs
                           if r.get("cand_k") is not None and r["cand_k"] >= 5
                           and not r.get("censored")
                           and (z_of(r) or -math.inf) >= Z_FIRE]
    trend_pos = bool(tr.get("ok") and tr.get("z") is not None
                     and math.isfinite(tr["z"]) and tr["z"] >= Z_FIRE)
    # ---- BRANCH 3 (censored-positive) ---------------------------------------- #
    deep_pos_censored = [r for r in rungs
                         if r.get("cand_k") is not None and r["cand_k"] >= 5
                         and r.get("censored")
                         and (z_of(r) or -math.inf) >= Z_FIRE]

    for r in deep_pos_uncensored:
        fired.append({"branch": 2, "why": f"{r['name']} (K={r['cand_k']}) paired z="
                                          f"{z_of(r):+.2f} >= +{Z_FIRE:g}, uncensored"})
    if trend_pos:
        fired.append({"branch": 2, "why": f"trend slope z={tr['z']:+.2f} >= +{Z_FIRE:g}"})
    for r in deep_pos_censored:
        fired.append({"branch": 3, "why": f"{r['name']} (K={r['cand_k']}) paired z="
                                          f"{z_of(r):+.2f} but CENSORED at rate "
                                          f"{r.get('censored_rate'):.3f}"})

    if deep_pos_uncensored or trend_pos:
        act = (f"AMENDED 2026-08-04: this does NOT fund the endgame net. The ladder ran "
               f"at the A/B SCREEN budget SIMS={SCREEN_SIMS}, and a positive at a weaker "
               f"champion sibling does NOT transfer (the known low-sims inflation "
               f"pattern). It buys ONE thing: a CONFIRM cell at the DEPLOY budget "
               f"{DEPLOY_SIMS} on FRESH decks of a NEW registered band. Only a confirm "
               f"that survives funds the endgame-net design.")
        if deep_pos_censored:
            act += (" Additionally, branch 3 applies to the censored rung(s) below: "
                    "raise caps x3 there, n=200 re-run, re-enter the map.")
        return {"primary_branch": 2,
                "label": "SCREEN-POSITIVE -> buy the 11008 confirm on a fresh band",
                "action": act, "alarms": [], "suppressed": False, "fired": fired}

    if deep_pos_censored:
        return {"primary_branch": 3,
                "label": "CENSORED-POSITIVE — not a verdict",
                "action": ("Raise the per-solve wall caps x3 on the affected rung(s) "
                           "ONLY, re-run at n=200, then re-enter this decision map. "
                           "The point estimate carries the not-a-verdict banner "
                           "regardless of z."),
                "alarms": [], "suppressed": False, "fired": fired}

    # ---- BRANCH 1 (the powered null) ----------------------------------------- #
    incomplete = []
    if not tr.get("ok"):
        incomplete.append(f"the trend statistic is unavailable ({tr.get('refusal')})")
    missing = [r["name"] for r in rungs if z_of(r) is None]
    if missing:
        incomplete.append(f"rungs without a paired z: {missing}")
    censored_names = [r["name"] for r in rungs if r.get("censored")]
    if censored_names:
        incomplete.append(f"censored rung(s) carry no verdict either way: "
                          f"{censored_names}")
    if incomplete:
        return {"primary_branch": None,
                "label": "INCOMPLETE — branch 1 cannot be claimed yet",
                "action": ("Nothing in the map fires positive, but the null branch "
                           "requires the trend AND every rung to be readable: "
                           + "; ".join(incomplete)),
                "alarms": [], "suppressed": False, "fired": fired}

    return {"primary_branch": 1,
            "label": "POWERED NULL — the June null generalizes",
            "action": (f"Every rung's paired-margin z < +{Z_FIRE:g} and the trend slope "
                       f"z < +{Z_FIRE:g}. Per the 2026-08-04 amendment a null at the "
                       f"SCREEN budget {SCREEN_SIMS} is the STRONGER conclusion and "
                       f"TRANSFERS upward to {DEPLOY_SIMS} (a weaker prefix leaves an "
                       f"exact tail MORE room, not less). Stamp the exact:K row final; "
                       f"the endgame-net lever is STILLBORN; no further endgame-"
                       f"exactness work."),
            "alarms": [], "suppressed": False,
            "fired": [{"branch": 1, "why": "all rung z and the trend z below +2"}]}


# --------------------------------------------------------------------------- #
# rendering                                                                    #
# --------------------------------------------------------------------------- #
def _f(x, fmt="%.2f", na="-"):
    if x is None:
        return na
    try:
        v = float(x)
    except (TypeError, ValueError):
        return na
    return na if not math.isfinite(v) else (fmt % v)


def render_markdown(rungs: list[dict], tr: dict, dec: dict, warnings: list[str],
                    meta: dict, tr_all: dict | None = None) -> str:
    L = []
    L.append("# F13 exact-K ladder — pre-registered analysis")
    L.append("")
    L.append(f"Prereg (binding): `{PREREG}`  ·  generated {meta['generated_utc']}")
    L.append(f"Band: `{meta.get('band')}`  ·  screen budget SIMS="
             f"{meta.get('cand_sims')}  ·  incumbent K={INCUMBENT_K}  ·  "
             f"rules profile `{meta.get('rules_profile')}` (r9_env_ok="
             f"{meta.get('r9_env_ok')})")
    L.append("")
    L.append("| rung | K | n | W-D-L | wr | elo | ±1σ | 2σ MDE | margin/deck | ±1σ | "
             "paired z | decks | latch | caps | censored | stamp |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rungs:
        L.append("| {name} | {k} | {n} | {w}-{d}-{l} | {wr} | {elo} | {sig} | {mde} | "
                 "{mg} | {mse} | {pz} | {np_} | {latch} | {caps} | {cr} | {st} |".format(
                     name=r["name"], k=r.get("cand_k"), n=r["n"], w=r["W"], d=r["D"],
                     l=r["L"], wr=_f(r["winrate"], "%.3f"), elo=_f(r["elo"], "%+.1f"),
                     sig=_f(r["elo_sig_1sigma"], "%.1f"),
                     mde=_f(r["elo_mde_2sigma"], "%.1f"),
                     mg=_f(r["paired_mean_margin"], "%+.2f"),
                     mse=_f(r["paired_se"], "%.2f"), pz=_f(r["paired_z"], "%+.2f"),
                     np_=r["n_paired"], latch=r.get("latch_solves"),
                     caps=r.get("cap_hits"), cr=_f(r.get("censored_rate"), "%.3f"),
                     st=("⚠️ " + r["stamp"] if r["censored"] else r["stamp"])))
    L.append("")
    for r in rungs:
        if r["censored"]:
            L.append(f"- ⚠️ **{r['name']}**: {r['censor_banner']}")
    L.append("")
    L.append("## Power (so a null is never over-read as \"no effect\")")
    L.append("")
    L.append(f"House figure: n=400 deck-paired resolves ≈ ±{NOMINAL_PAIRED_1SIGMA_ELO:g} "
             f"elo at 1σ; ±35 elo is the 2σ verdict floor at n=400 UNPAIRED. "
             f"Realised per rung:")
    for r in rungs:
        L.append(f"- `{r['name']}`: elo {_f(r['elo'], '%+.1f')} ± "
                 f"{_f(r['elo_sig_1sigma'], '%.1f')} (2σ MDE ±"
                 f"{_f(r['elo_mde_2sigma'], '%.1f')} elo); paired margin "
                 f"{_f(r['paired_mean_margin'], '%+.2f')} ± {_f(r['paired_se'], '%.2f')} "
                 f"pts/deck over {r['n_paired']} decks (2σ MDE ±"
                 f"{_f(r.get('margin_mde_2sigma'), '%.2f')} pts). "
                 f"An effect smaller than the MDE is UNRESOLVED, not absent.")
    L.append("")
    L.append("## Primary statistic — within-band deck-matched trend across rungs")
    L.append("")
    if tr.get("ok"):
        L.append(f"Slope **{_f(tr['slope'], '%+.3f')} ± {_f(tr['se'], '%.3f')}** "
                 f"{tr['units']}, **z = {_f(tr['z'], '%+.2f')}** "
                 f"(2σ MDE ±{_f(tr.get('slope_mde_2sigma'), '%.3f')}); "
                 f"{tr['n_shared_decks']} shared decks; K = {tr['k']}; "
                 f"rungs {tr['rungs_used']}.")
        L.append("")
        L.append(f"Estimator: {tr['estimator']}. Identity anchor K={INCUMBENT_K} "
                 f"included: {tr['include_identity_anchor']}.")
        if tr.get("warning"):
            L.append("")
            L.append(f"- ⚠️ {tr['warning']}")
    else:
        L.append(f"**NO TREND REPORTED.** {tr.get('refusal')}")
    L.append("")
    if tr_all is not None and tr_all.get("rungs_used") != tr.get("rungs_used"):
        L.append(f"Diagnostic fit over ALL rungs (censored included — **does not "
                 f"decide**): " + (f"slope {_f(tr_all['slope'], '%+.3f')}, z = "
                                   f"{_f(tr_all['z'], '%+.2f')}, rungs "
                                   f"{tr_all['rungs_used']}."
                                   if tr_all.get("ok")
                                   else f"unavailable — {tr_all.get('refusal')}"))
        L.append("")
    L.append("## Decision map — which branch fires")
    L.append("")
    if dec.get("primary_branch") == 4:
        L.append("### 🚨 BRANCH 4 — INSTRUMENT ALARM (dominates; all other "
                 "conclusions SUPPRESSED)")
    elif dec.get("primary_branch") is None:
        L.append(f"### {dec['label']}")
    else:
        L.append(f"### BRANCH {dec['primary_branch']} — {dec['label']}")
    L.append("")
    for a in dec.get("alarms", []):
        L.append(f"- 🚨 {a}")
    for f in dec.get("fired", []):
        L.append(f"- branch {f['branch']}: {f['why']}")
    L.append("")
    L.append(dec["action"])
    if warnings:
        L.append("")
        L.append("## Warnings")
        L.append("")
        for w in warnings:
            L.append(f"- ⚠️ {w}")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
def analyze(cell_dirs, *, include_identity_anchor: bool = False) -> dict:
    cells = [load_cell(d) for d in cell_dirs]
    cells = [c for c in cells if c["games"] or c["summary"]]
    cells.sort(key=lambda c: (c["cand_k"] is None, c["cand_k"] or 0))

    warnings: list[str] = []
    rungs = []
    for c in cells:
        r = rung_stats(c)
        warnings += crosscheck(r, c["summary"])
        if r.get("opp_k") not in (None, INCUMBENT_K):
            warnings.append(f"{r['name']}: incumbent arm is K={r['opp_k']}, not the "
                            f"pre-registered K={INCUMBENT_K}")
        if r.get("cand_k") == INCUMBENT_K:
            warnings.append(f"{r['name']}: K={INCUMBENT_K} is the IDENTITY, not a cell "
                            f"— excluded from the ladder")
        if r.get("rules_profile") != "fixed_v1" or r.get("r9_env_ok") is not True:
            warnings.append(f"{r['name']}: rules profile "
                            f"{r.get('rules_profile')!r}/r9_env_ok="
                            f"{r.get('r9_env_ok')!r} is not the pre-registered "
                            f"fixed_v1 + CARCASSONNE_FIX_R9=1")
        if r.get("cand_sims") not in (None, SCREEN_SIMS):
            warnings.append(f"{r['name']}: cand_sims={r.get('cand_sims')} is not the "
                            f"amended screen budget {SCREEN_SIMS}")
        if r.get("n_planned") and r["n"] < int(r["n_planned"]):
            warnings.append(f"{r['name']}: PARTIAL cell — {r['n']}/{r['n_planned']} "
                            f"games; every estimate below is under-powered")
        rungs.append(r)

    ladder = [r for r in rungs if r.get("cand_k") != INCUMBENT_K]
    bands = {r.get("band") for r in ladder}
    if len(bands) > 1:
        warnings.append(f"rungs span multiple bands {sorted(map(str, bands))} — the "
                        f"within-band design is violated")
    # The trend that DECIDES is fitted on the UNCENSORED rungs only: a censored rung
    # carries a not-a-verdict banner "regardless of z" (prereg), and a statistic it
    # feeds inherits that. The all-rungs fit is reported alongside, diagnostically.
    uncensored = [r for r in ladder if not r.get("censored")]
    tr = trend(uncensored, include_identity_anchor=include_identity_anchor)
    tr["scope"] = "uncensored rungs only (the deciding fit)"
    tr_all = trend(ladder, include_identity_anchor=include_identity_anchor)
    tr_all["scope"] = "ALL rungs incl. censored (diagnostic only — does NOT decide)"
    if len(uncensored) != len(ladder):
        warnings.append(
            f"{len(ladder) - len(uncensored)} censored rung(s) excluded from the "
            f"deciding trend fit (their point estimate is not a verdict regardless "
            f"of z); the all-rungs fit is reported as a diagnostic only")
    dec = decide(ladder, tr)

    meta = {
        "schema": SCHEMA,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prereg": PREREG,
        "band": next(iter(bands)) if len(bands) == 1 else sorted(map(str, bands)),
        "cand_sims": ladder[0].get("cand_sims") if ladder else None,
        "rules_profile": ladder[0].get("rules_profile") if ladder else None,
        "r9_env_ok": ladder[0].get("r9_env_ok") if ladder else None,
        "incumbent_k": INCUMBENT_K,
        "screen_sims": SCREEN_SIMS,
        "deploy_sims": DEPLOY_SIMS,
        "z_fire": Z_FIRE,
        "censor_threshold": et.CENSOR_THRESHOLD,
        "nominal_paired_1sigma_elo_n400": NOMINAL_PAIRED_1SIGMA_ELO,
    }
    public = []
    for r in ladder:
        d = {k: v for k, v in r.items() if not k.startswith("_")}
        d.pop("summary", None)
        public.append(d)
    return {"meta": meta, "rungs": public, "trend": tr, "trend_all_rungs": tr_all,
            "decision": dec, "warnings": warnings,
            "markdown": render_markdown(ladder, tr, dec, warnings, meta,
                                        tr_all=tr_all)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cells", nargs="*", help="explicit per-rung cell directories")
    ap.add_argument("--out-root", help="share dir holding the per-rung cells "
                                       "(e.g. /mnt/c/carc-shared/exact_k_ladder)")
    ap.add_argument("--band", type=int, help="seed band; only cells whose manifest "
                                             "stamps this seed_start are used")
    ap.add_argument("--prefix", default=None,
                    help="cell-dirname prefix filter (launcher default: f13_fixed_v1_)")
    ap.add_argument("--verdict-json", default=None,
                    help="where to write VERDICT.json (default: <out-root>/"
                         "F13_VERDICT.json, or ./F13_VERDICT.json)")
    ap.add_argument("--include-identity-anchor", action="store_true",
                    help="add the structural K=4 margin-0 point to the trend fit "
                         "(OFF by default: K=4 is an identity, not a measured cell)")
    args = ap.parse_args(argv)

    dirs = [Path(c) for c in args.cells]
    if args.out_root:
        dirs += discover_cells(Path(args.out_root), args.band, args.prefix)
    dirs = list(dict.fromkeys(dirs))
    if not dirs:
        print("no F13 cells found (pass cell dirs, or --out-root [--band])",
              file=sys.stderr)
        return 2

    res = analyze(dirs, include_identity_anchor=args.include_identity_anchor)
    print(res["markdown"])

    vpath = Path(args.verdict_json) if args.verdict_json else (
        Path(args.out_root) / "F13_VERDICT.json" if args.out_root
        else Path("F13_VERDICT.json"))
    vpath.parent.mkdir(parents=True, exist_ok=True)
    payload = {k: v for k, v in res.items() if k != "markdown"}
    vpath.write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n[verdict] wrote {vpath}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
