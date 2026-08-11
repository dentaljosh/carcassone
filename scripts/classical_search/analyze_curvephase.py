#!/usr/bin/env python3
"""Part-C beta ladder: the FITTED WITHIN-DECK SLOPE, and the pre-registered C-readings.

Pre-registration: measurement/curve_shape_scope_20260809/PREREG_DRAFT.md Part C.

  "Primary statistic for Part C is the FITTED WITHIN-DECK SLOPE of `margin` on beta
   across the five points -- not any individual cell."

WHY WITHIN-DECK. All five cells share ONE band, so every deck is played in every cell.
Deck identity is therefore a paired factor and differencing it out removes the deck-luck
variance that dominates a single cell at n=200 (~+/-24.6 elo at 1 sigma; +/-17.4 is the
n=400 figure and does NOT apply here). The line across the ladder is the measurement;
the individual cells are underpowered BY DESIGN and must not be read as five verdicts.

MARGIN SIGN -- READ THIS BEFORE TOUCHING `deck_margins`. The harness ALREADY emits
`diff` as CANDIDATE MINUS OPPONENT: `eval_fair_puct.py` computes
`diff = (s0 - s1) if a_seat == 0 else (s1 - s0)`, and its own manifest schema note says
`"diff": "candidate - opponent (per game, from the candidate's a_seat)"`. Its `_paired_z`
averages the two seatings' `diff` per deck with NO seat flip. So this analyzer must NOT
apply a second flip. (It did until 2026-08-10: `diff * (+1 if a_seat==0 else -1)` cancelled
the candidate's advantage between the two seatings of every deck, which made the primary
statistic blind to beta by construction. Found by adversarial review before any valid
readout; the `mean_margin_recomputed` vs `paired_mean_margin` tripwire below exists so the
same class of bug can never again reach a verdict silently.)
A deck's seat-balanced margin is the mean over its two seatings, which cancels seat advantage.

ESTIMATOR. Deck-demeaned OLS of margin on beta (equivalent to deck fixed effects), with
a CLUSTER-ROBUST sandwich SE on deck -- the same discipline the oracle-price read uses,
because a deck contributes five correlated points.

C-readings, in the prereg's order:
  C-KILL      |slope z| < 2.0            -> NO LINEAR PHASE EFFECT EXCEEDING ~+/-22 elo at
                                            beta = +/-0.6 at this instrument's resolution.
                                            A BOUNDED null, not "the phase axis is dead".
  C-RECONFIRM slope significantly NEGATIVE -> v28 reconfirmed on clean ground; axis closes.
  C-FIRE      slope z >= 2.0 (either sign) -> one n=400 fresh-deck confirm at the best-fit
                                            beta; escalate only if margin_z >= 2.0 there.

⚠️ The beta=0 cell is ALSO the wiring gate. PREREG AMENDMENT 1 (2026-08-10) amends the bar
   to `|paired margin z| < 2.0 AND |elo| < 50` -- margin z primary (the robust within-band
   statistic of record), the elo bound retained as a gross-wiring backstop at a correctly
   scaled 2 sigma for n=200. The retired `|elo| < 25` bar was inherited from Part A's n=400
   cells, where it sits at 1.44 sigma; at n=200 it sits at 1.01 sigma of its own instrument
   (~31% false-abort on a TRUE-ZERO identity cell) and it duly false-fired on band 1.15e11.
⚠️ A cell under 90% completion is VOID and is excluded from the fit (stated in output).
⚠️ MANIFEST ENFORCEMENT (prereg §6.2 / §8): every cell's manifest must show
   rules_profile fixed_v1, r9_env_ok, backend rust, and the ladder's single band_seed_start;
   the beta=0 cell must carry the PRODUCTION leaf hash and every beta!=0 cell must carry a
   hash distinct from production AND from each other (the free positive control that the
   phase knob actually reached the leaf). One void non-identity cell -> excluded and noted;
   two -> ABORT-STAGE; a void identity cell -> INSTRUMENT-BROKEN.
"""
import argparse
import json
import math
from pathlib import Path

CELLS = {"bm0p6": -0.6, "bm0p3": -0.3, "b0p0": 0.0, "b0p3": 0.3, "b0p6": 0.6}
IDENTITY = "b0p0"

# governance/PRODUCTION.yaml champion `puct_priors_v29_bmild_cap8` leaf (prereg §3).
PROD_LEAF_HASH = "a36d2e15a3b3d71d"
REQ_RULES_PROFILE = "fixed_v1"
REQ_BACKEND = "rust"
MARGIN_TOL = 1e-6

# Amended wiring gate (PREREG AMENDMENT 1, 2026-08-10). margin z is PRIMARY.
GATE_MARGIN_Z = 2.0
GATE_ELO = 50.0


class TripwireError(RuntimeError):
    """The analyzer's per-deck recomputation disagrees with the harness's own summary."""


def dig(d, *path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def deck_margins(cell_dir: Path):
    """seed -> seat-balanced candidate-minus-opponent margin (only decks with both seats).

    `diff` is ALREADY candidate-minus-opponent (see the module docstring) -- do not flip it.
    """
    per = {}
    for f in cell_dir.glob("seed*.json"):
        if "summary" in f.name:
            continue
        try:
            g = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if "diff" not in g or "a_seat" not in g:
            continue
        m = float(g["diff"])
        per.setdefault(int(g["seed"]), {})[int(g["a_seat"])] = m
    return {s: (v[0] + v[1]) / 2.0 for s, v in per.items() if 0 in v and 1 in v}


def read_manifest(cell_dir: Path):
    p = cell_dir / "manifest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def manifest_facts(m: dict) -> dict:
    """Pull the prereg §8 fields out of the harness manifest, tolerating both shapes.

    `config.cand_leaf_hash` is the canonical key eval_fair_puct always writes; the nested
    blocks are fallbacks for manifest generations that predate it (same fallback ladder as
    the Part-A sibling analyze_curveshape.py).
    """
    rp = m.get("rules_profile") or {}
    backend = (dig(m, "config", "backend", "name")
               or dig(m, "config", "champion", "backend")
               or m.get("backend"))
    if isinstance(backend, dict):
        backend = backend.get("name")
    cand_cfg = dig(m, "config", "cand_leaf_cfg") or {}
    champ_cfg = dig(m, "config", "champion", "leaf_cfg") or {}
    # The beta=0 cell injects the DEFAULTS, and the cand_leaf_cfg block the harness stamps
    # for a non-drift cell omits the phase keys entirely; champion.leaf_cfg carries the
    # resolved value in that case. An absent key means "leaf default", i.e. 0.0.
    beta = cand_cfg.get("v29_phase_beta")
    beta_src = "cand_leaf_cfg"
    if beta is None:
        beta = champ_cfg.get("v29_phase_beta")
        beta_src = "champion.leaf_cfg"
    if beta is None:
        beta, beta_src = 0.0, "absent (leaf default)"
    norm = cand_cfg.get("v29_phase_norm")
    if norm is None:
        norm = champ_cfg.get("v29_phase_norm")
    return {
        "rules_profile": rp.get("name"),
        "r9_env_ok": rp.get("r9_env_ok"),
        "backend": backend,
        "cand_leaf_hash": (dig(m, "config", "cand_leaf_hash")
                           or dig(m, "config", "cand_curve_drift", "leaf_hash")
                           or dig(m, "config", "leaf_hash")),
        "opp_leaf_hash": (dig(m, "config", "opp_leaf_hash")
                          or dig(m, "config", "opponent", "leaf_hash")),
        "band_seed_start": dig(m, "config", "band_seed_start"),
        "manifest_phase_beta": beta,
        "manifest_phase_beta_source": beta_src,
        "manifest_phase_norm": norm,
        "code_rev": m.get("code_rev") or dig(m, "config", "code_rev"),
    }


def check_tripwire(cid, recomputed, summary_margin):
    """The bug-class tripwire: our per-deck recomputation MUST equal the harness's own.

    A disagreement means the analyzer and the emitter no longer share a sign convention or
    a pairing rule -- exactly the 2026-08-10 double-flip failure. Hard error: a Part-C
    verdict computed on a statistic that does not reproduce the harness's is worthless.
    """
    if recomputed is None or summary_margin is None:
        return
    d = abs(float(recomputed) - float(summary_margin))
    if d > MARGIN_TOL:
        raise TripwireError(
            f"cell {cid}: mean_margin_recomputed = {float(recomputed)!r} disagrees with "
            f"summary.json paired_mean_margin = {float(summary_margin)!r} "
            f"(|difference| {d:.6g} > {MARGIN_TOL:g}). The analyzer's per-deck margin no "
            "longer reproduces the harness's own paired statistic -- check the `diff` sign "
            "convention in deck_margins() (eval_fair_puct emits `diff` ALREADY as "
            "candidate-minus-opponent; a second flip cancels the effect between seatings) "
            "and the both-seatings pairing rule. Refusing to report a verdict.")


def fit_within_deck_slope(points):
    """points: list of (deck, beta, margin). Deck-demeaned OLS + cluster-robust SE on deck."""
    by_deck = {}
    for d, b, m in points:
        by_deck.setdefault(d, []).append((b, m))
    # keep only decks observed at >=2 distinct betas -- a deck seen once carries no slope
    by_deck = {d: v for d, v in by_deck.items() if len({b for b, _ in v}) >= 2}
    if not by_deck:
        return None
    num = den = 0.0
    for d, v in by_deck.items():
        bb = sum(b for b, _ in v) / len(v)
        mm = sum(m for _, m in v) / len(v)
        for b, m in v:
            num += (b - bb) * (m - mm)
            den += (b - bb) ** 2
    if den <= 0:
        return None
    slope = num / den
    # cluster-robust sandwich: meat = sum_d (sum_i x_it * e_it)^2, bread = 1/den
    meat = 0.0
    for d, v in by_deck.items():
        bb = sum(b for b, _ in v) / len(v)
        mm = sum(m for _, m in v) / len(v)
        s = 0.0
        for b, m in v:
            x = b - bb
            s += x * ((m - mm) - slope * x)
        meat += s * s
    se = math.sqrt(meat) / den if meat > 0 else float("nan")
    return {"slope": slope, "se": se, "z": (slope / se) if se and se == se and se > 0 else float("nan"),
            "n_decks": len(by_deck), "n_points": sum(len(v) for v in by_deck.values())}


def collect(root: Path, prefix: str, n_expected: int):
    """Build the per-cell rows: summary stats, recomputed per-deck margins, manifest facts."""
    cells = []
    for cid, beta in CELLS.items():
        d = root / f"{prefix}{cid}"
        sp = d / "summary.json"
        row = {"cell": cid, "beta": beta, "present": sp.exists(), "void": False,
               "void_reasons": []}
        if sp.exists():
            s = json.loads(sp.read_text())
            row.update(n=s.get("n"), elo=s.get("elo"), elo_sig=s.get("elo_sig_1sigma"),
                       paired_z=s.get("paired_z"),
                       paired_mean_margin=s.get("paired_mean_margin"))
            row["completion"] = (s.get("n", 0) / n_expected) if n_expected else 0
        if d.exists():
            dm = deck_margins(d)
            row["_deck_margins"] = dm
            row["n_decks_paired"] = len(dm)
            if dm:
                row["mean_margin_recomputed"] = sum(dm.values()) / len(dm)
            m = read_manifest(d)
            if m is None:
                row["manifest"] = None
            else:
                row["manifest"] = manifest_facts(m)
        cells.append(row)
    return cells


def adjudicate_manifests(cells):
    """prereg §6.2 + §8 manifest enforcement. Returns (band, provenance_problem)."""
    present = [c for c in cells if c.get("present")]
    unreadable = [c["cell"] for c in present if c.get("manifest") is None
                  or c["manifest"].get("cand_leaf_hash") is None]
    if unreadable:
        # ⚠️ MISSING evidence is NOT CONTRADICTING evidence (the Part-A sibling's lesson):
        # an unreadable manifest is a defect in THIS script's lookup, not proof the
        # instrument is broken, and calling it INSTRUMENT-BROKEN burns a band for a bug.
        return None, (
            f"cells whose manifest / cand_leaf_hash could not be read: {unreadable}. This is "
            "an ANALYZER path defect, not an instrument verdict: fix the lookup and re-read. "
            "The cells' games are unaffected and are NOT void.")

    # one band for the whole ladder (within-band deck-matched is the whole design)
    ident = next((c for c in present if c["cell"] == IDENTITY), None)
    bands = [c["manifest"]["band_seed_start"] for c in present]
    band = (ident["manifest"]["band_seed_start"] if ident else None)
    if band is None and bands:
        band = max(set(bands), key=bands.count)

    hashes = {}
    for c in present:
        f = c["manifest"]
        bad = []
        if f["rules_profile"] != REQ_RULES_PROFILE:
            bad.append(f"rules_profile={f['rules_profile']!r} != {REQ_RULES_PROFILE!r}")
        if not f["r9_env_ok"]:
            bad.append(f"r9_env_ok={f['r9_env_ok']!r}")
        if f["backend"] != REQ_BACKEND:
            bad.append(f"backend={f['backend']!r} != {REQ_BACKEND!r}")
        if band is not None and f["band_seed_start"] != band:
            bad.append(f"band_seed_start={f['band_seed_start']!r} != ladder band {band!r}")
        # free positive control: the phase knob must have MOVED the leaf, and by the
        # right amount -- an identity-hash beta!=0 cell means the knob never landed.
        h = f["cand_leaf_hash"]
        if c["cell"] == IDENTITY:
            if h != PROD_LEAF_HASH:
                bad.append(f"identity cell cand_leaf_hash={h!r} != production "
                           f"{PROD_LEAF_HASH!r}")
        else:
            if h == PROD_LEAF_HASH:
                bad.append(f"beta={c['beta']} cell carries the PRODUCTION leaf hash "
                           f"{PROD_LEAF_HASH!r} -- the phase knob never reached the leaf")
            elif h in hashes:
                bad.append(f"cand_leaf_hash {h!r} is shared with cell {hashes[h]!r} -- "
                           "two distinct betas resolved to one leaf")
        if h is not None and h != PROD_LEAF_HASH:
            hashes.setdefault(h, c["cell"])
        mb = f["manifest_phase_beta"]
        if mb is None or abs(float(mb) - c["beta"]) > 1e-9:
            bad.append(f"manifest v29_phase_beta={mb!r} != cell beta {c['beta']} "
                       f"(source: {f['manifest_phase_beta_source']})")
        if bad:
            c["void"] = True
            c["void_reasons"].extend(bad)
    return band, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run-root", default="/mnt/c/carc-shared/curvephase_ladder")
    ap.add_argument("--prefix", default="cp_")
    ap.add_argument("--n-expected", type=int, default=200)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    root = Path(a.run_root)

    cells = collect(root, a.prefix, a.n_expected)
    notes = []

    # ---- the tripwire, BEFORE any statistic is read out of these cells ----
    for c in cells:
        check_tripwire(c["cell"], c.get("mean_margin_recomputed"), c.get("paired_mean_margin"))

    band, provenance_problem = adjudicate_manifests(cells)

    # ---- completion guard (prereg §6.4) folds into the same void bookkeeping ----
    for c in cells:
        if c.get("present") and c.get("completion", 0) < 0.90:
            c["void"] = True
            c["void_reasons"].append(
                f"completion {c.get('completion', 0):.0%} < 90% (prereg §6.4)")

    points = []
    for c in cells:
        if c.get("present") and not c["void"]:
            for seed, m in (c.get("_deck_margins") or {}).items():
                points.append((seed, c["beta"], m))
    for c in cells:
        c.pop("_deck_margins", None)
        if c["void"]:
            notes.append(f"{c['cell']}: VOID -> excluded from the fit ({'; '.join(c['void_reasons'])})")

    ident = next((c for c in cells if c["cell"] == IDENTITY), None)
    gate, gate_why = "PENDING", "identity cell has not completed"
    if ident and ident.get("present"):
        mz, elo = ident.get("paired_z"), ident.get("elo")
        ok_mz = mz is not None and abs(float(mz)) < GATE_MARGIN_Z
        ok_elo = elo is not None and abs(float(elo)) < GATE_ELO
        gate = "OK" if (ok_mz and ok_elo and not ident["void"]) else "INSTRUMENT-BROKEN"
        gate_why = (f"identity cell: paired margin z {mz}, elo {elo} "
                    f"(amended bar: |margin z| < {GATE_MARGIN_Z} AND |elo| < {GATE_ELO:.0f}; "
                    "margin z primary -- PREREG AMENDMENT 1)")

    void_non_identity = [c["cell"] for c in cells
                         if c["void"] and c["cell"] != IDENTITY and c.get("present")]

    fit = fit_within_deck_slope(points) if points else None
    verdict, why = "PENDING", "not all cells complete"

    if provenance_problem:
        verdict, why = "PROVENANCE-UNREADABLE", provenance_problem
    elif gate == "INSTRUMENT-BROKEN":
        reasons = "; ".join(ident["void_reasons"]) if ident["void"] else ""
        verdict, why = "INSTRUMENT-BROKEN", (
            f"beta=0 identity cell fails the amended wiring gate -- {gate_why}"
            + (f"; identity manifest void: {reasons}" if reasons else "")
            + " => ladder VOID")
    elif len(void_non_identity) >= 2:
        verdict, why = "ABORT-STAGE", (
            f"{len(void_non_identity)} void non-identity cells {void_non_identity} "
            "(prereg §6.2: two void cells abort the stage)")
    elif fit and sum(1 for c in cells if c.get("present")) == len(CELLS):
        z = fit["z"]
        if z == z and abs(z) >= 2.0:
            if z < 0:
                verdict, why = "C-RECONFIRM", (
                    f"slope {fit['slope']:+.4f} pts/deck per unit beta, z {z:+.2f} -- significantly "
                    "NEGATIVE. v28's finding is RECONFIRMED on clean ground with the magnitude "
                    "confound removed; the phase axis closes permanently.")
            else:
                verdict, why = "C-FIRE", (
                    f"slope {fit['slope']:+.4f}, z {z:+.2f} >= 2.0 => run ONE n=400 fresh-deck "
                    "confirm at the best-fit beta; escalate only if margin_z >= 2.0 there.")
        else:
            verdict, why = "C-KILL", (
                f"fitted within-deck slope {fit['slope']:+.4f} pts/deck per unit beta, "
                f"se {fit['se']:.4f}, z {z:+.2f} -- |z| < 2.0 => NO LINEAR PHASE EFFECT "
                "EXCEEDING ~+/-22 elo AT beta = +/-0.6 (endpoint spread ~45 elo) at THIS "
                "INSTRUMENT'S RESOLUTION. This is a BOUNDED null and must be written up as "
                "one -- NEVER as 'the phase axis is dead'. It is nonetheless materially "
                "stronger than the 2026-06-22 v28 kill (one unbracketed endpoint, magnitude "
                "confounded), because this ladder is signed, bracketed and E[f]=1 "
                "renormalized: it BOUNDS the linear phase effect rather than excluding it.")
        if len(void_non_identity) == 1:
            why += (f" [NOTE: cell {void_non_identity[0]} is VOID and was excluded from the "
                    "fit (prereg §6.2, one void cell).]")

    notes.append("Primary statistic is the FITTED WITHIN-DECK SLOPE; the five cells are "
                 "underpowered individually BY DESIGN (n=200 ~ +/-24.6 elo at 1 sigma; the "
                 "+/-17.4 figure is n=400 and does not apply) and must not be read as five "
                 "verdicts.")
    notes.append("E[f]=1 renormalization is the ONLY thing licensing this retry of the v28 "
                 "kill; the norms are computed over the PLY-k distribution while the leaf is "
                 "evaluated ~one mean-search-depth BELOW the root, so the magnitude confound "
                 "is PARTIALLY TRADED, not removed (order <=5-17 elo of monotone spread, "
                 "biased toward the reconfirm direction). Bounded language only.")
    notes.append("Wiring gate is PREREG AMENDMENT 1 (2026-08-10): |paired margin z| < 2.0 AND "
                 "|elo| < 50, margin z primary. The retired |elo| < 25 bar is an n=400 bar and "
                 "false-fired on band 1.15e11 at n=200.")
    out = {"verdict": verdict, "why": why, "identity_gate": gate, "identity_gate_why": gate_why,
           "band_seed_start": band, "void_cells": [c["cell"] for c in cells if c["void"]],
           "slope_fit": fit, "cells": cells, "notes": notes}
    txt = json.dumps(out, indent=2, default=str)
    print(txt)
    if a.out:
        Path(a.out).write_text(txt + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
