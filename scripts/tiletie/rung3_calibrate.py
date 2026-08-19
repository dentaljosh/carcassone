#!/usr/bin/env python3
"""RUNG 3 (`J > 4`) successor prereg — the R5-1 REQUIRED PRE-RUN, counts-only
calibration sweep (`measurement/tiearb_widening_20260817/rung3_r5/DESIGN.md`).

WHAT THIS IS FOR. R4's S2 stratum voided on `G-DISJOINT`'s digest bound (29
exclusions against a bound of 6, ALL at ply 2 — `PREREG_FAILURE_S2.md`). The
bound was a FIXED fraction of `n`; the finding it missed is that collision
DENSITY is not a constant of the generator, it grows with games mined. R5-1
replaces the fixed bound with a scale-aware one, `bound(G) = d_model(G) x M`
(`M = 3`, pre-committed in DESIGN §R5-1.2 BEFORE any density is fitted), and
gates it with a 5% saturation guard (§R5-1.3). Both need `d_model(G)` FITTED
from real counts at **>= 4 nested corpus scales** — that fit is what this
script produces. §R5-2 additionally asks for the SAME counts recomputed at
each of a small committed set of ply floors `k`, so the READ_RULE drafter can
see how much collision mass a `--min-ply k` predicate removes.

WHAT THIS IS NOT. Per DESIGN §R5-1.1: "No generation, no scoring, no champ
picks — counts only". This script does NOT generate games, does NOT run
playouts, does NOT run oracle/champ scoring, and does NOT re-run the leaf
census. It reads position records that were **already mined** (the leg1
board-census jsonl `run_census.py` / `build_positions.py` already produce —
`positions_*_leg1.jsonl`, "leg1 carries EVERY position exactly once ... so
leg1 is the complete board census of a corpus", `gate_disjoint.py`'s own
comment) and recomputes COUNTS over nested game-scale prefixes of that
existing output. "Re-mine" in DESIGN §R5-1.1 means this recomputation, not a
fresh census run — the class `PREREG_FAILURE.md` §3.3 established as
non-leaking.

DIGESTS ARE NEVER RE-IMPLEMENTED HERE. Every `sha256(checksum)` computation in
this module goes through `gate_disjoint.load_digest_map` / `load_digests` —
the same functions `G-DISJOINT` itself uses. A second, slightly different
digest implementation is exactly how a prior transposition bug got in
(`emit_digest_exclusions.py`'s `digest_of` duplicated the hash instead of
importing it); this module imports the gate's functions and computes no hash
of its own.

DISCLOSURE. Like `gate_disjoint.py`, this is COUNTS ONLY: no checksum value
and no full rid ever appears in the emitted JSON, with one narrow exception —
the ply histograms are counts, but a bound check on a fitted curve is not an
identity leak by construction (nothing here names WHICH positions collided).

Usage
-----
    python scripts/tiletie/rung3_calibrate.py \\
        --legs-dir measurement/tiearb_widening_20260817/shared_run_r4/corpus/positions_s2 \\
        --scales 500 1500 3000 5340 \\
        --ply-floors 0 1 2 3 4 \\
        --out measurement/tiearb_widening_20260817/rung3_r5/CALIBRATION.json

`--legs-dir` may repeat; each is expanded with `--leg-glob` (default
`positions_*_leg1.jsonl`, `gate_disjoint.py`'s own convention) via
`gate_disjoint.leg_paths`. `--legs` (repeatable) names explicit files instead,
for callers that already have the leg-file list in hand.

Exit codes
    0   sweep computed; at least one requested ply floor clears the 5% guard
    1   sweep computed, but NO ply floor clears the guard (§R5-1.3: the design
        is VOID before it is built — the report is still written)
    2   an input is missing / malformed, or the sweep's own preconditions
        (>= 4 scales, distinct, in-range) are violated
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

REPO = Path(__file__).resolve().parents[2]

import gate_disjoint as GD                                          # noqa: E402

#: DESIGN R5-1.2 — the ONE number chosen before the sweep runs, committed in
#: the DESIGN doc itself. Exposed on the CLI for sensitivity checks only; it
#: does NOT change what DESIGN.md committed.
DEFAULT_M = 3.0
#: DESIGN R5-1.3 — "if d_model(G_governed) > 5%, the corpus design is VOID".
DEFAULT_SATURATION_PCT = 5.0
#: DESIGN R5-2.2's "smallest ply floor" search needs a small COMMITTED set of
#: candidates, not an open-ended scan. k=0 is "no floor" (today's rule).
DEFAULT_PLY_FLOORS = (0, 1, 2, 3, 4)
#: DESIGN R5-1.1's own default leg glob — leg1 is the complete board census.
DEFAULT_LEG_GLOB = "positions_*_leg1.jsonl"

REQUIRED_FIELDS = ("rid", "checksum", "ply", "deck_seed")


class CalibrationError(RuntimeError):
    """An input is missing/malformed, or the sweep's own preconditions are
    violated (>= 4 distinct in-range scales). Fail loud, never coerce — this
    mirrors `gate_disjoint.GateInputError`'s role for `G-DISJOINT`."""


# --------------------------------------------------------------------------- #
# loading — metadata only. The DIGEST itself is computed exactly once, inside #
# `gate_disjoint.load_digest_map`, and never recomputed in this module.       #
# --------------------------------------------------------------------------- #
def load_meta(paths) -> dict:
    """`rid -> {ply, deck_seed, root_id}` off the same leg jsonl file(s)
    `gate_disjoint.load_digest_map` reads. Metadata only — no hashing."""
    out: dict = {}
    for p in paths:
        p = Path(p)
        if not p.is_file():
            raise CalibrationError(f"leg file not found: {p}")
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CalibrationError(f"{p}:{i}: not JSON ({exc})") from exc
            missing = [k for k in REQUIRED_FIELDS if k not in rec]
            if missing:
                raise CalibrationError(
                    f"{p}:{i}: missing required field(s) {missing} — the "
                    "calibration sweep needs rid/checksum/ply/deck_seed on "
                    "every record")
            rid = str(rec["rid"])
            out[rid] = {
                "ply": int(rec["ply"]),
                "deck_seed": int(rec["deck_seed"]),
                "root_id": str(rec.get("root_id") or rec["deck_seed"]),
            }
    return out


def committed_game_order(meta: dict, *, order_seed=None) -> list:
    """The nested-prefix GAME order: distinct `deck_seed`s. Default is
    ascending numeric order — deterministic with no RNG, and matches how the
    campaign's extension bands are contiguous seed ranges, so a numeric prefix
    already IS a meaningful "first G games mined" slice. `order_seed` requests
    a seeded shuffle instead (`random.Random(seed)` — never wall-clock), for a
    representative-sample reading rather than a seed-contiguous one; passing
    the SAME seed always reproduces the SAME order."""
    seeds = sorted({m["deck_seed"] for m in meta.values()})
    if order_seed is not None:
        rng = random.Random(int(order_seed))
        rng.shuffle(seeds)
    return seeds


# --------------------------------------------------------------------------- #
# counts at one (scale, ply-floor) cell                                        #
# --------------------------------------------------------------------------- #
def collisions_at(meta: dict, rid_digest: dict, *, game_prefix: set, ply_floor: int = 0) -> dict:
    """Positions + collisions restricted to `game_prefix` (a set of
    `deck_seed`) and `ply >= ply_floor`.

    Two collision counts are reported, deliberately distinct:

      * `n_pairwise_collisions` — literal PAIRS: `sum(C(k, 2))` over digest
        groups of size `k >= 2`.
      * `n_exclusions` — the DESIGN's own vocabulary (R4's "29 exclusions
        against a bound of 6"): `sum(k - 1)`, i.e. how many positions would be
        DROPPED if one representative per digest group is kept. This is the
        number the R4-3 exclusion bound and `density` are defined against —
        verified by reproducing R4's own arithmetic: bound = ceil(0.005 x
        1100) = 6 against the "S2 at 700" -> "S2 at 1100"-shaped option, and
        29 / 1100 = 2.636%, exactly R5-1's quoted governed-scale density.

    The excluded member of each colliding group is the one NOT kept by
    `emit_digest_exclusions.py`'s own INTERNAL-DUPES rule: keep the
    lexicographically SMALLEST rid, exclude the rest. Reusing that rule (not
    inventing a new one) keeps this sweep's counts comparable to what the real
    corpus build would actually drop.
    """
    kept_rids = [rid for rid, m in meta.items()
                 if m["deck_seed"] in game_prefix and m["ply"] >= ply_floor]
    groups: dict = {}
    for rid in kept_rids:
        d = rid_digest.get(rid)
        if d is None:
            continue
        groups.setdefault(d, []).append(rid)

    n_pairs = 0
    n_exclusions = 0
    excluded_ply_hist: Counter = Counter()
    touched_ply_hist: Counter = Counter()
    n_groups_collided = 0
    for rids in groups.values():
        k = len(rids)
        if k < 2:
            continue
        n_groups_collided += 1
        n_pairs += k * (k - 1) // 2
        n_exclusions += k - 1
        ordered = sorted(rids)
        excluded = ordered[1:]
        for r in rids:
            touched_ply_hist[meta[r]["ply"]] += 1
        for r in excluded:
            excluded_ply_hist[meta[r]["ply"]] += 1

    n_positions = len(kept_rids)
    density = (n_exclusions / n_positions) if n_positions else None
    return {
        "n_games": len(game_prefix),
        "n_positions": n_positions,
        "n_digest_groups_collided": n_groups_collided,
        "n_pairwise_collisions": n_pairs,
        "n_exclusions": n_exclusions,
        "density": density,
        "collision_ply_histogram_touched": dict(sorted(touched_ply_hist.items())),
        "collision_ply_histogram_excluded": dict(sorted(excluded_ply_hist.items())),
    }


# --------------------------------------------------------------------------- #
# d_model(G) — log-log OLS power-law fit (DESIGN R5-1's own illustrative form) #
# --------------------------------------------------------------------------- #
def fit_power_law(points) -> dict:
    """`d_model(G) = a * G**b`, fit by ordinary least squares on `ln(d)` vs
    `ln(G)`. Needs >= 2 usable points (`G > 0`, `d > 0`); the caller is
    responsible for having supplied >= 4 SCALES (`R5-1.1`) — this function
    only enforces what it itself needs to compute a line.

    ⚠️ DESIGN R5-1 is explicit that a two-point fit is an ILLUSTRATION, not a
    fit: "two points determine a line through two points; they cannot
    distinguish G^1.46 from a curve that bends." `r_squared` is reported so a
    reader can see whether >= 4 points actually behaves like one power law
    rather than trusting the exponent blind.
    """
    pts = [(float(g), float(d)) for g, d in points if g and d and g > 0 and d > 0]
    if len(pts) < 2:
        raise CalibrationError(
            "power-law fit needs >= 2 scales with nonzero density; got "
            f"{len(pts)} usable point(s) out of {len(points)} scale(s)")
    xs = [math.log(g) for g, _ in pts]
    ys = [math.log(d) for _, d in pts]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        raise CalibrationError("power-law fit needs >= 2 DISTINCT scales")
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    ln_a = my - b * mx
    a = math.exp(ln_a)
    resid = [y - (ln_a + b * x) for x, y in zip(xs, ys)]
    ss_res = sum(r * r for r in resid)
    ss_tot = sum((y - my) ** 2 for y in ys)
    r_squared = (1.0 - ss_res / ss_tot) if ss_tot > 0 else None
    return {
        "form": "d_model(G) = a * G**b (log-log OLS)",
        "a": a, "b": b, "n_points": n, "r_squared": r_squared,
        "points_used": [{"G": g, "d": d} for g, d in pts],
    }


def d_model_value(fit: dict, g) -> float:
    return fit["a"] * (float(g) ** fit["b"])


# --------------------------------------------------------------------------- #
# the sweep                                                                     #
# --------------------------------------------------------------------------- #
def run_calibration(*, legs, scales, ply_floors=DEFAULT_PLY_FLOORS, m=DEFAULT_M,
                    saturation_pct=DEFAULT_SATURATION_PCT, order_seed=None,
                    g_governed=None) -> dict:
    """The full R5-1 + R5-2 sweep. `legs` = leg jsonl file paths (already
    mined). `scales` = >= 4 nested corpus scales, in GAMES. `ply_floors` = the
    committed candidate `k` set (R5-2.2)."""
    scales = sorted({int(g) for g in scales}) if scales else []
    if len(scales) < 4:
        raise CalibrationError(
            f"DESIGN R5-1.1 requires >= 4 nested corpus scales; got "
            f"{len(scales)} distinct value(s): {scales}")

    digest_map, n_lines = GD.load_digest_map(legs)
    meta = load_meta(legs)
    rid_digest = {rid: d for d, rids in digest_map.items() for rid in rids}

    order = committed_game_order(meta, order_seed=order_seed)
    n_games_total = len(order)
    if n_games_total == 0:
        raise CalibrationError("no games found in the supplied leg file(s)")
    if scales[-1] > n_games_total:
        raise CalibrationError(
            f"largest requested scale {scales[-1]} exceeds the "
            f"{n_games_total} distinct game(s) found in the supplied leg "
            "file(s) — a scale is a PREFIX of the corpus, never a request "
            "for more games than exist")

    ply_floors = sorted({int(k) for k in ply_floors})
    if not ply_floors:
        raise CalibrationError("--ply-floors needs at least one candidate k")

    by_ply_floor = {}
    for k in ply_floors:
        per_scale = {}
        for g in scales:
            prefix = set(order[:g])
            per_scale[g] = collisions_at(meta, rid_digest, game_prefix=prefix,
                                         ply_floor=k)
        points = [(g, per_scale[g]["density"]) for g in scales]
        try:
            fit = fit_power_law(points)
        except CalibrationError as exc:
            fit = {"error": str(exc)}

        g_gov = int(g_governed) if g_governed is not None else scales[-1]
        d_gov = d_model_value(fit, g_gov) if "a" in fit else None
        bound = (d_gov * m) if d_gov is not None else None
        saturation_void = (d_gov is not None) and (d_gov * 100.0 > saturation_pct)

        by_ply_floor[str(k)] = {
            "ply_floor": k,
            "per_scale": {str(g): per_scale[g] for g in scales},
            "d_model_fit": fit,
            "g_governed": g_gov,
            "d_model_at_governed": d_gov,
            "bound_m": m,
            "bound_at_governed": bound,
            "saturation_guard_pct": saturation_pct,
            "saturation_void": saturation_void,
            "n_positions_at_max_scale": per_scale[scales[-1]]["n_positions"],
            "n_exclusions_at_max_scale": per_scale[scales[-1]]["n_exclusions"],
            "collision_ply_histogram_excluded_at_max_scale":
                per_scale[scales[-1]]["collision_ply_histogram_excluded"],
        }

    # R5-2.2's FIRST conjunct only: smallest k clearing the 5% guard at the
    # largest scale. The SECOND conjunct (retained supply meets FLOORS.json's
    # floor) cannot be evaluated here — R5-8's own sequence writes
    # FLOORS.json FROM this sweep's output, so it does not exist yet.
    recommended_k = next(
        (k for k in ply_floors if not by_ply_floor[str(k)]["saturation_void"]),
        None)

    return {
        "schema": "carcassonne-rung3-r5-calibration/v1",
        "design_doc": "measurement/tiearb_widening_20260817/rung3_r5/DESIGN.md",
        "purpose": "R5-1.1's REQUIRED PRE-RUN counts-only density sweep + "
                   "R5-2's ply-floor knob. COUNTS ONLY -- no generation, no "
                   "playouts, no scoring, no champ picks.",
        "config": {
            "legs": [str(p) for p in legs],
            "scales": scales,
            "ply_floors": ply_floors,
            "m_pre_committed": m,
            "saturation_guard_pct": saturation_pct,
            "order_seed": order_seed,
            "order": ("sorted ascending deck_seed" if order_seed is None
                      else f"seeded shuffle (random.Random({order_seed}))"),
            "n_games_total_in_corpus": n_games_total,
            "n_position_records_total": sum(len(v) for v in digest_map.values()),
            "n_leg_lines_total": n_lines,
        },
        "by_ply_floor": by_ply_floor,
        "recommended_ply_floor_k": recommended_k,
        "recommended_ply_floor_k_note": (
            "smallest floor in --ply-floors clearing the 5% saturation guard "
            "at the largest scale (R5-1.3). The SECOND R5-2.2 conjunct -- "
            "retained supply meeting FLOORS.json's floor -- is NOT checked "
            "here: FLOORS.json is written FROM this sweep's output (R5-8), "
            "so it does not exist yet. Check it separately once a FLOORS.json "
            "row is chosen."
            if recommended_k is not None else
            "NO ply floor in --ply-floors clears the 5% saturation guard at "
            "the largest scale. Per R5-1.3 this means the corpus design is "
            "VOID before it is built -- a bigger bound is not the fix."),
    }


# --------------------------------------------------------------------------- #
# CLI                                                                           #
# --------------------------------------------------------------------------- #
def _resolve_legs(a) -> list:
    legs = []
    for d in (a.legs_dir or ()):
        legs.extend(GD.leg_paths(d, a.leg_glob))
    for f in (a.legs or ()):
        p = Path(f)
        if not p.is_file():
            raise CalibrationError(f"--legs file not found: {p}")
        legs.append(p)
    if not legs:
        raise CalibrationError("need at least one of --legs-dir / --legs")
    return legs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--legs-dir", action="append", default=None, metavar="DIR",
                    help="a positions dir (repeatable), expanded with "
                         "--leg-glob via gate_disjoint.leg_paths")
    ap.add_argument("--legs", action="append", default=None, metavar="FILE",
                    help="an explicit leg jsonl file (repeatable)")
    ap.add_argument("--leg-glob", default=DEFAULT_LEG_GLOB)
    ap.add_argument("--scales", type=int, nargs="+", required=True, metavar="G",
                    help="'>=4 nested corpus scales (games), e.g. "
                         "--scales 500 1500 3000 5340")
    ap.add_argument("--ply-floors", type=int, nargs="+",
                    default=list(DEFAULT_PLY_FLOORS),
                    help=f"candidate ply floors k (default "
                         f"{list(DEFAULT_PLY_FLOORS)})")
    ap.add_argument("--m", type=float, default=DEFAULT_M,
                    help=f"the R5-1.2 pre-committed multiple (default "
                         f"{DEFAULT_M}; exposed for sensitivity checks -- "
                         "does not change DESIGN.md's own committed value)")
    ap.add_argument("--saturation-guard-pct", type=float,
                    default=DEFAULT_SATURATION_PCT)
    ap.add_argument("--order-seed", type=int, default=None,
                    help="seeded shuffle of the committed game order; "
                         "default: sorted ascending deck_seed")
    ap.add_argument("--g-governed", type=int, default=None,
                    help="scale the bound/guard are evaluated at; default: "
                         "the largest --scales value")
    ap.add_argument("--out", required=True, help="CALIBRATION.json path")
    a = ap.parse_args(argv)

    try:
        legs = _resolve_legs(a)
        report = run_calibration(
            legs=legs, scales=a.scales, ply_floors=a.ply_floors, m=a.m,
            saturation_pct=a.saturation_guard_pct, order_seed=a.order_seed,
            g_governed=a.g_governed)
    except (CalibrationError, GD.GateInputError) as exc:
        print(f"\n{'=' * 70}\n[rung3-calibrate] COULD NOT EVALUATE: {exc}\n"
              f"{'=' * 70}", file=sys.stderr)
        return 2

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(report, indent=2, sort_keys=True))

    for k in report["config"]["ply_floors"]:
        blk = report["by_ply_floor"][str(k)]
        d = blk["d_model_at_governed"]
        bnd = blk["bound_at_governed"]
        d_s = "n/a" if d is None else f"{d * 100:.3f}%"
        bnd_s = "n/a" if bnd is None else f"{bnd * 100:.3f}%"
        print(f"[rung3-calibrate] k={k:2d}  d_model(G={blk['g_governed']}) = "
              f"{d_s:>10s}  bound(M={blk['bound_m']}) = {bnd_s:>10s}  "
              f"saturation_void={blk['saturation_void']}")
    print(f"[rung3-calibrate] recommended_ply_floor_k = "
          f"{report['recommended_ply_floor_k']}")
    print(f"[rung3-calibrate] -> {a.out}")

    if report["recommended_ply_floor_k"] is None:
        print(f"\n{'=' * 70}\n[rung3-calibrate] ***** NO PLY FLOOR CLEARS THE "
              f"5% GUARD *****\n[rung3-calibrate] Per DESIGN R5-1.3, the "
              f"corpus design is VOID before it is built.\n{'=' * 70}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
