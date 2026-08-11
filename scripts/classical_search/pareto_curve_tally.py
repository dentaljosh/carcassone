#!/usr/bin/env python3
"""Assemble the budget/elo Pareto curve from whatever cells have landed.

Applies the read-out rules from measurement/classical_search/PARETO_CURVE_PREREG.md
VERBATIM -- it does not invent a summary:

  * reports BOTH statistics per cell (winrate z AND deck-paired margin z);
  * computes the within-tier allocation contrast as a true DECK-MATCHED delta over
    the shared seed band (cells 1+2 share 60e9, cells 3+4 share 62e9) from the
    per-game records -- the CL-054 double-CRN method, NOT a difference of absolutes;
  * pools a tier into one n=800 estimate ONLY if that delta is |z| < 1 (rule 3);
  * plots against MEASURED per-move cost, converted to % of the 900 s tournament
    clock (docs/research/TOURNAMENT_TIMING_2026-07-26.md);
  * runs the validity guards and refuses to report a cell that fails one.

Field names were taken from the EMITTER (eval_fair_puct.py `_summarize` return and
the per-game record dict), not guessed.

Usage:  .venv/bin/python scripts/classical_search/pareto_curve_tally.py [--share PATH]
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import pathlib
import statistics
import sys

# Pre-registered cells in curve order: (dirname, k_dets, sims, band_e9, tier)
CELLS = [
    ("pareto_k4x172_688_vs_deploy", 4, 172, 62, "0.25x"),
    ("pareto_k2x344_688_vs_deploy", 2, 344, 62, "0.25x"),
    ("pareto_k4x344_1376_vs_deploy", 4, 344, 60, "0.5x"),
    ("pareto_k2x688_1376_vs_deploy", 2, 688, 60, "0.5x"),
    ("pareto_k4x1376_5504_vs_deploy", 4, 1376, 64, "2x"),
]
CLOCK_SECS = 900.0                  # 15 min per player, sudden death, no increment
DEPLOY_TOTAL = 2752
# The deploy champion's UNLOADED per-move cost + per-game solver time, measured by
# distill_strong_iter03_cost_probe_unloaded_w2 (results.csv) and used to build the
# clock table in docs/research/TOURNAMENT_TIMING_2026-07-26.md. This is the anchor
# the whole cost axis hangs on -- see candidate_clock().
DEPLOY_UNLOADED_MS_PER_MOVE = 2752.0
DEPLOY_SOLVER_SECS = 34.0
# The champion's leaf env as recorded in every valid cell's manifest. The DEFINITIVE
# curve125 check is the harness's own "BOTH SIDES curve125: YES" line, captured in
# the queue log; this is the cross-check available from the run directory alone.
EXPECTED_LEAF_ENV = {
    "CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V25_VALUE_BLEND": "0", "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
}


def cell_dir(share: pathlib.Path, name: str) -> pathlib.Path:
    return share / "classical_search" / name


def load_summary(d: pathlib.Path):
    p = d / "summary.json"
    if not p.exists():
        return None
    with p.open() as fh:
        return json.load(fh)


def load_games(d: pathlib.Path) -> list[dict]:
    out = []
    for f in glob.glob(str(d / "seed*.json")):
        try:
            with open(f) as fh:
                out.append(json.load(fh))
        except (json.JSONDecodeError, OSError):
            pass          # a game still being written; skipped, not fatal
    return out


def leaf_guard(d: pathlib.Path) -> list[str]:
    """Cross-check the recorded leaf env against the champion's."""
    p = d / "manifest.json"
    if not p.exists():
        return ["manifest.json missing — leaf provenance unverifiable"]
    with p.open() as fh:
        env = (json.load(fh) or {}).get("leaf_env", {})
    if env != EXPECTED_LEAF_ENV:
        diff = {k: (env.get(k), v) for k, v in EXPECTED_LEAF_ENV.items() if env.get(k) != v}
        return [f"leaf env differs from champion: {diff}"]
    return []


def guards(summ: dict, games: list[dict]) -> list[str]:
    """Pre-registered validity guards. Failing one makes a cell INVALID, not negative."""
    bad = []
    n = summ.get("n", 0)
    if n < 400:
        bad.append(f"short cell: {n}/400 games")
    ct = summ.get("champ_timeouts", 0) or 0
    ot = sum(g.get("opp_timeouts", 0) or 0 for g in games)
    if ct or ot:
        bad.append(f"solver timeouts: candidate {ct}, opponent {ot}")
    # deck_hash consistency: every record sharing a seed must agree on the deck.
    by_seed: dict[int, set] = {}
    for g in games:
        by_seed.setdefault(g["seed"], set()).add(g.get("deck_hash"))
    mism = sum(1 for v in by_seed.values() if len(v) > 1)
    if mism:
        bad.append(f"deck_hash mismatches: {mism} seeds")
    return bad


def per_deck_margin(games: list[dict]) -> dict:
    """Seat-balanced margin per deck. `diff` is already candidate-minus-opponent."""
    by_deck: dict = {}
    for g in games:
        by_deck.setdefault(g["deck_hash"], []).append(g["diff"])
    return {dh: statistics.fmean(v) for dh, v in by_deck.items() if len(v) == 2}


def deck_matched_delta(a: list[dict], b: list[dict]):
    """CL-054 double-CRN: paired difference of seat-balanced margins over shared decks."""
    ma, mb = per_deck_margin(a), per_deck_margin(b)
    shared = sorted(set(ma) & set(mb))
    if len(shared) < 30:
        return None
    d = [ma[k] - mb[k] for k in shared]
    mean = statistics.fmean(d)
    se = statistics.stdev(d) / math.sqrt(len(d)) if len(d) > 1 else float("nan")
    return mean, se, (mean / se if se else float("nan")), len(shared)


def candidate_clock(summ: dict, games: list[dict]) -> float:
    """Whole-game seconds the CANDIDATE would burn on its own tournament clock.

    ⚠️ NOT computed from the cell's absolute ms/move. Those are measured UNDER LOAD
    (W16 x 2 boxes), and loaded latencies overstate deployed cost -- the exact
    distinction the CL-067 cost thread turned on (4.29x at W28 / 5.48x at W48 /
    4.24x UNLOADED at W2). Taking them literally inflates the clock by ~1.30x:
    it puts the 4x teacher at 17.5 min against its published 13.6, and the 8x
    config at 34.8 against 26.7.

    Instead: every cell's OPPONENT is the deploy champion, so the in-run
    candidate/opponent ratio is contention-CANCELLING (both sides pay the same
    queue). Anchor that ratio on the champion's MEASURED UNLOADED per-move cost
    and the deployed cost follows. Validated against the published table: the
    teacher's 4.07x ratio -> 11.2 s/move -> 13.6 min -> 91% of clock, exactly.
    """
    cand_ms = summ.get("champ_prefix_ms_per_move")
    opp_ms = summ.get("rung_ms_per_move")          # head-to-head => the champion's own counter
    if not cand_ms or not opp_ms:
        return float("nan")
    ratio = cand_ms / opp_ms
    moves = statistics.fmean([g.get("champ_prefix_moves", 70) for g in games]) if games else 70.0
    return (ratio * DEPLOY_UNLOADED_MS_PER_MOVE / 1000.0) * moves + DEPLOY_SOLVER_SECS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--share", default="/mnt/c/carc-shared")
    args = ap.parse_args()
    share = pathlib.Path(args.share)

    rows, by_tier = [], {}
    for name, kd, sims, band, tier in CELLS:
        d = cell_dir(share, name)
        summ = load_summary(d)
        if summ is None:
            n_done = len(glob.glob(str(d / "seed*.json")))
            st = f"in progress ({n_done}/400)" if n_done else "not started"
            rows.append((tier, f"k{kd}x{sims}", kd * sims, None, None, None, None, None, st))
            continue
        games = load_games(d)
        bad = guards(summ, games) + leaf_guard(d)
        clk = candidate_clock(summ, games)
        rows.append((tier, f"k{kd}x{sims}", kd * sims, summ.get("elo"),
                     summ.get("elo_sig_1sigma"), summ.get("winrate_z"), summ.get("paired_z"),
                     100.0 * clk / CLOCK_SECS, "INVALID: " + "; ".join(bad) if bad else "ok"))
        if not bad:
            by_tier.setdefault(tier, []).append((name, summ, games))

    print("\n=== BUDGET/ELO PARETO CURVE vs the DEPLOY CHAMPION (k4x688 = 2752) ===")
    print("deploy champion is the 0-elo anchor by construction, at 26% of a 900 s clock.\n")
    hdr = (f"{'tier':>6} {'alloc':>10} {'total':>6} {'elo':>8} {'1sig':>6} "
           f"{'wr_z':>6} {'marg_z':>7} {'%clock':>7}  status")
    print(hdr); print("-" * len(hdr))
    for tier, alloc, total, elo, sig, wz, mz, pct, st in rows:
        if elo is None:
            print(f"{tier:>6} {alloc:>10} {total:>6} {'-':>8} {'-':>6} {'-':>6} {'-':>7} {'-':>7}  {st}")
        else:
            print(f"{tier:>6} {alloc:>10} {total:>6} {elo:>+8.1f} {sig or 0:>6.1f} "
                  f"{wz or 0:>+6.2f} {mz or 0:>+7.2f} {pct:>6.1f}%  {st}")

    print("\n=== ALLOCATION CONTRAST — deck-matched over the shared band (rule 2) ===")
    for tier, cells in sorted(by_tier.items()):
        if len(cells) < 2:
            print(f"{tier}: {len(cells)} valid cell — contrast needs both allocations.")
            continue
        (n1, s1, g1), (n2, s2, g2) = cells[0], cells[1]
        a1 = f"k{s1.get('candidate_k_dets', s1['k_dets'])}x{s1.get('candidate_sims', s1['sims'])}"
        a2 = f"k{s2.get('candidate_k_dets', s2['k_dets'])}x{s2.get('candidate_sims', s2['sims'])}"
        res = deck_matched_delta(g1, g2)
        if res is None:
            print(f"{tier}: too few shared complete decks for a paired delta yet.")
            continue
        mean, se, z, nd = res
        print(f"{tier}: {a1} - {a2} = {mean:+.3f} pts/deck (se {se:.3f}, z {z:+.2f}, {nd} shared decks)")
        if abs(z) < 1.0:
            e1, e2 = s1["elo"], s2["elo"]
            v1, v2 = s1["elo_sig_1sigma"] ** 2, s2["elo_sig_1sigma"] ** 2
            pooled = (e1 / v1 + e2 / v2) / (1 / v1 + 1 / v2)
            psig = math.sqrt(1 / (1 / v1 + 1 / v2))
            print(f"       |z|<1 => POOL (rule 3, pre-registered): the {tier} budget costs "
                  f"{pooled:+.1f} +/- {psig:.1f} elo vs deploy (n=800)")
        else:
            print(f"       |z|>=1 => DO NOT POOL; allocation matters at this budget.")

    print("\nRule 5: the expected sign is NEGATIVE. A positive low-budget cell is a")
    print("config-bug red flag (wrong side / wrong leaf / seat imbalance) — check the")
    print("manifest before believing it.  Rule 6: nothing here promotes anything.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
