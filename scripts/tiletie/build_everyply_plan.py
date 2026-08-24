#!/usr/bin/env python3
"""Build the EVERY-PLY ROLLOUT ARBITRATION probe's sampling frame and position order.

Pure plan surgery, exactly in the spirit of ``build_tiearb_plan.py``: it scores
nothing, searches nothing, runs no engine and reads no oracle VALUE. It is a
**query over a tracked census jsonl** plus a seeded draw, and it is the first
stage of the SIZE-1 screen described in
``measurement/everyply_probe_20260823/DESIGN.md``.

What it does, in order:

  1. **Frame** -- reads
     ``measurement/tiearb_widening_20260817/census/tile_gap_rows.jsonl`` (31,827
     tile plies of the 449 ``champ449`` champion-selfplay games) and takes the
     **non-tied** class (``tie_exact == false``). DESIGN §2.1's population table is
     re-derived here and asserted, so a census that ever changes cannot silently
     re-base the design (``--no-expect`` for tests only).
  2. **Strata** -- cuts the non-tied class by leaf ``gap = top1 - top2`` into
     A (0 < gap <= 0.25) / B (0.25 < gap <= 1.5) / C (gap > 1.5), DESIGN §2.2.
  3. **Holdout** -- reserves ``--holdout-frac`` of the *games* (the cluster unit)
     by seeded split **before** any position is drawn, DESIGN §6.4.
  4. **Draw** -- allocates ``--n`` over the strata by the committed
     ``f = (0.25, 0.375, 0.375)`` (largest-remainder), and fills each quota from a
     single global seeded shuffle subject to a **global cap of ``--cap-per-game``
     positions per game**, so the root-cluster design effect stays ~1.0.
  5. **Order** -- one committed seeded permutation of the drawn rids, cut into
     ``--chunks`` near-equal sequential chunks. Every completed-chunk prefix is a
     uniform random subsample, so a partially-completed run is still readable at
     its realized ``n`` (the ``build_tiearb_plan``/``build_oof_plan`` property,
     same ``chunk_slices`` partition arithmetic).
  6. **Emit** -- ``FRAME.json``, ``HOLDOUT_GAMES.json``, ``POSITION_ORDER.json``,
     ``SELECTION.jsonl``, ``PLAN_SUMMARY.json``.

It deliberately STOPS before arm-set construction. The arms need a *fresh
production champion search* per position (DESIGN §3.2) and are built by the
corpus stage, which consumes ``SELECTION.jsonl``; nothing in this file needs a
champion, a leaf, or the engine.

⛔ Writes nothing outside ``--out-dir``. Claims no band (DESIGN §8 / BAND_NOTE.md).
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

DEFAULT_CENSUS = REPO / "measurement/tiearb_widening_20260817/census/tile_gap_rows.jsonl"
DEFAULT_OUT = REPO / "measurement/everyply_probe_20260823"

SCHEMA = "carcassonne-everyply-plan/v1"

#: DESIGN §6.4 -- ONE committed seed for the root split, the draw and the order.
PERMUTATION_SEED = 20260823

#: DESIGN §2.2 -- stratum cuts on the leaf gap. Half-open on the low side; the
#: non-tied class has gap > 0 by construction (asserted below).
STRATA = ("A", "B", "C")
GAP_CUTS = {"A": (0.0, 0.25), "B": (0.25, 1.5), "C": (1.5, float("inf"))}

#: DESIGN §2.3 -- the committed allocation. NOT proportional: it over-samples the
#: near-tie stratum A at a measured variance price of sum(w^2/f) (see below).
ALLOCATION_F = {"A": 0.25, "B": 0.375, "C": 0.375}

#: DESIGN §2.1 -- the frame as measured on the tracked census, asserted at build
#: time so the design cannot be silently re-based by a changed census file.
EXPECT_TOTAL_TILE_PLIES = 31827
EXPECT_GAMES = 449
EXPECT_TIED = 20322
EXPECT_NONTIED = 11505
EXPECT_STRATUM_N = {"A": 1147, "B": 4936, "C": 5422}

#: DESIGN §7.1 -- realized per-position dispersion recomputed from
#: ``measurement/tiearb_20260816/per_position.jsonl``. Prices the se(kappa) table
#: this script PRINTS; it prices no estimate and enters no statistic.
SD_PER_CHANGED_POSITION = 1.8115
STRATIFICATION_SE_PENALTY = 1.06
Q_GRID = (0.50, 0.76, 0.90)

#: DESIGN §5 cost brackets (lo / central / hi), all realized on disk, none modelled.
C_IF_BRACKET = (1.5999, 2.0, 2.35)          # clair-puct rust, worker-s/playout
C_ARB = 0.178232                            # tier1-greedy rust, worker-s/playout
T_CHAMP_BRACKET = (13.7552, 19.0, 25.0)     # champion re-search, s/position
M_SEL_BRACKET = (1.8, 2.2, 2.6)             # selective pricing multiplier 2*(Abar-1)
M_WORLDS = 32                               # DESIGN §3.1 -- M = 32, not 128
K_ARMS = 4                                  # DESIGN §3.1 -- K = J = 4
M_FULL = 2 * (K_ARMS - 1)                   # full-arm-set playout multiplier = 6.0


# --------------------------------------------------------------------------- #
# frame                                                                        #
# --------------------------------------------------------------------------- #
def load_census(path) -> list:
    """Every row of the tracked census jsonl, in file order."""
    rows = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def stratum_of(gap: float) -> str:
    """A / B / C by DESIGN §2.2's gap cuts. Raises on a non-positive gap."""
    if gap <= 0.0:
        raise ValueError(f"gap {gap!r} is not positive -- not a non-tied ply")
    for s in STRATA:
        lo, hi = GAP_CUTS[s]
        if lo < gap <= hi:
            return s
    raise ValueError(f"gap {gap!r} fell through the cuts")


def nontied_rows(rows: list) -> list:
    """The arbitrable population: TILE plies, not exactly tied, >= 2 legal arms.

    DESIGN §2.1 measured ZERO non-tied tile plies with ``n_legal < 2``; the filter
    is kept so the property is enforced rather than assumed.
    """
    out = []
    for r in rows:
        if r.get("ply_class") != "TILE":
            continue
        if r.get("tie_exact"):
            continue
        if int(r.get("n_legal", 0)) < 2:
            continue
        out.append(r)
    return out


def rid_of(row: dict) -> str:
    """Stable position id. One census row is one (game, ply), so this is unique."""
    return f"ep_{row['game_id']}_{row['ply']}"


def frame_report(rows: list) -> dict:
    """DESIGN §2.1/§2.2's population tables, re-derived from the census itself."""
    tile = [r for r in rows if r.get("ply_class") == "TILE"]
    tied = [r for r in tile if r.get("tie_exact")]
    nt = nontied_rows(rows)
    games = sorted({r["game_id"] for r in tile})
    by_s = {s: [r for r in nt if stratum_of(float(r["gap"])) == s] for s in STRATA}
    n_nt = len(nt)
    cdf = {}
    for cut in (0.05, 0.10, 0.25, 0.50, 1.0, 1.5, 2.0, 3.0, 5.0):
        cdf[str(cut)] = sum(1 for r in nt if float(r["gap"]) <= cut) / n_nt
    legals = sorted(int(r["n_legal"]) for r in nt)
    return {
        "census_rows": len(rows),
        "tile_plies": len(tile),
        "games": len(games),
        "tied_exact": len(tied),
        "nontied": n_nt,
        "nontied_forced_n_legal_lt_2": sum(
            1 for r in tile if not r.get("tie_exact") and int(r.get("n_legal", 0)) < 2),
        "per_game": {
            "all_tile_plies": len(tile) / len(games),
            "tied_exact": len(tied) / len(games),
            "nontied": n_nt / len(games),
            "nontied_per_seat": n_nt / len(games) / 2.0,
        },
        "strata": {
            s: {
                "n": len(by_s[s]),
                "share_of_nontied": len(by_s[s]) / n_nt,
                "per_game_per_seat": len(by_s[s]) / len(games) / 2.0,
                "phase_bucket": dict(Counter(r["phase_bucket"] for r in by_s[s])),
            } for s in STRATA
        },
        "gap_cdf_over_nontied": cdf,
        "n_legal": {
            "mean": sum(legals) / len(legals),
            "median": legals[len(legals) // 2],
            "p90": legals[int(0.90 * (len(legals) - 1))],
            "max": legals[-1],
        },
    }


def assert_frame(report: dict) -> None:
    """Refuse to build against a census that no longer matches DESIGN §2.1."""
    checks = [
        ("tile_plies", report["tile_plies"], EXPECT_TOTAL_TILE_PLIES),
        ("games", report["games"], EXPECT_GAMES),
        ("tied_exact", report["tied_exact"], EXPECT_TIED),
        ("nontied", report["nontied"], EXPECT_NONTIED),
    ] + [(f"stratum_{s}", report["strata"][s]["n"], EXPECT_STRATUM_N[s]) for s in STRATA]
    bad = [(k, got, want) for k, got, want in checks if got != want]
    if bad:
        raise SystemExit(
            "REFUSING: the census no longer reproduces DESIGN §2.1's frame: "
            + "; ".join(f"{k}={got} (design says {want})" for k, got, want in bad))
    if report["nontied_forced_n_legal_lt_2"] != 0:
        raise SystemExit(
            "REFUSING: DESIGN §2.1 asserts ZERO non-tied tile plies with n_legal < 2; "
            f"found {report['nontied_forced_n_legal_lt_2']}")


# --------------------------------------------------------------------------- #
# allocation, split, draw                                                      #
# --------------------------------------------------------------------------- #
def allocate(n: int, f: dict = ALLOCATION_F) -> dict:
    """Largest-remainder integer allocation of `n` over the strata by `f`."""
    if n < 0:
        raise ValueError("n must be >= 0")
    exact = {s: n * f[s] for s in STRATA}
    base = {s: int(exact[s]) for s in STRATA}
    left = n - sum(base.values())
    # Tie-break on EQUAL remainders runs C -> B -> A (reverse stratum order). That is
    # not cosmetic: DESIGN §2.3's committed n=900 allocation is 225/337/338, i.e. the
    # single leftover seat at f=(.25,.375,.375) goes to C, not to B.
    order = sorted(STRATA, key=lambda s: (-(exact[s] - base[s]), -STRATA.index(s)))
    for s in order[:left]:
        base[s] += 1
    if sum(base.values()) != n:
        raise AssertionError("allocation lost positions")
    return base


def variance_price(w: dict, f: dict = ALLOCATION_F) -> float:
    """sum(w_s^2 / f_s) -- DESIGN §2.3's se-inflation factor vs proportional (1.0)."""
    return sum(w[s] ** 2 / f[s] for s in STRATA)


def split_games(games: list, frac: float, seed: int = PERMUTATION_SEED) -> dict:
    """Seeded holdout split over the CLUSTER unit (the game), drawn BEFORE any
    position is selected. DESIGN §6.4."""
    order = sorted(games)
    random.Random(seed + 1).shuffle(order)
    k = int(round(frac * len(order)))
    hold = set(order[:k])
    return {"holdout": sorted(hold), "dev": sorted(g for g in order if g not in hold)}


def draw(nt: list, quota: dict, cap_per_game: int, seed: int = PERMUTATION_SEED) -> list:
    """Fill each stratum's quota from ONE global seeded shuffle, subject to a
    GLOBAL per-game cap. Returns the drawn census rows.

    The single shuffle is what makes the cap unbiased across strata: no stratum
    gets first refusal on a game's slots by virtue of being processed first.
    """
    pool = sorted(nt, key=rid_of)
    random.Random(seed).shuffle(pool)
    taken_by_game: Counter = Counter()
    got = {s: 0 for s in STRATA}
    out = []
    for r in pool:
        s = stratum_of(float(r["gap"]))
        if got[s] >= quota[s]:
            continue
        if taken_by_game[r["game_id"]] >= cap_per_game:
            continue
        out.append(r)
        got[s] += 1
        taken_by_game[r["game_id"]] += 1
        if all(got[s2] >= quota[s2] for s2 in STRATA):
            break
    short = {s: quota[s] - got[s] for s in STRATA if got[s] < quota[s]}
    if short:
        raise SystemExit(
            f"REFUSING: the cap-{cap_per_game}-per-game draw could not fill "
            f"{short} -- widen --cap-per-game or lower --n")
    return out


def committed_order(rids: list, seed: int = PERMUTATION_SEED) -> list:
    """ONE shuffle of the SORTED rid list. Nothing else. (build_tiearb_plan §5.)"""
    order = sorted(rids)
    random.Random(seed).shuffle(order)
    return order


def chunk_slices(order: list, chunks: int) -> list:
    """`chunks` near-equal contiguous slices. Copied verbatim from
    ``build_tiearb_plan.chunk_slices`` -- same exact partition property."""
    if chunks < 1:
        raise ValueError("chunks must be >= 1")
    n = len(order)
    out, start = [], 0
    for i in range(chunks):
        stop = ((i + 1) * n) // chunks
        out.append(order[start:stop])
        start = stop
    if sum(len(c) for c in out) != n:
        raise AssertionError("chunking lost positions")
    return out


# --------------------------------------------------------------------------- #
# power + cost, both printed, neither an estimate                              #
# --------------------------------------------------------------------------- #
def se_kappa(n: int, q: float, penalty: float = STRATIFICATION_SE_PENALTY) -> float:
    """DESIGN §7.1: se(kappa) = penalty * 1.8115 * sqrt(q) / sqrt(n).

    ⚠️ The ``penalty`` (1.06) is the price of POPULATION-REWEIGHTING a
    non-proportional allocation, so it belongs to the POOLED estimate ONLY.
    A WITHIN-STRATUM se reweights nothing and must be called with
    ``penalty=1.0`` -- that is why DESIGN §6.3's per-stratum figures at n=900
    read 0.105 / 0.086 / 0.086 rather than 1.06x those. Getting this backwards
    inflates every per-stratum se by 6%.
    """
    if n <= 0:
        raise ValueError("n must be > 0")
    return penalty * SD_PER_CHANGED_POSITION * (q ** 0.5) / (n ** 0.5)


def se_kappa_stratum(n: int, q: float) -> float:
    """Within-stratum se -- no reweighting, hence NO stratification penalty."""
    return se_kappa(n, q, penalty=1.0)


def cost_table(n_pool: int, n_priced: int) -> dict:
    """SIZE-1 line items in worker-hours (lo / central / hi), DESIGN §5.2.

    Uses the repo's own cost model shape (``build_positions.cost_plan``):
        playouts    = sum_p 2*(A_p - 1)*M
        worker_secs = playouts * c + n * t_champ
    """
    out = {}
    for i, tag in enumerate(("lo", "central", "hi")):
        c_if, t_champ, m_sel = C_IF_BRACKET[i], T_CHAMP_BRACKET[i], M_SEL_BRACKET[i]
        corpus_s = n_pool * t_champ
        arb_s = n_pool * M_FULL * M_WORLDS * C_ARB
        if_s = n_priced * m_sel * M_WORLDS * c_if
        out[tag] = {
            "c_if_worker_s_per_playout": c_if,
            "t_champ_secs": t_champ,
            "m_sel": m_sel,
            "corpus_build_wh": corpus_s / 3600.0,
            "arb_judge_wh": arb_s / 3600.0,
            "if_pricing_selective_wh": if_s / 3600.0,
            "total_wh": (corpus_s + arb_s + if_s) / 3600.0,
        }
    return out


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def build(census_path, out_dir, *, n, cap_per_game, holdout_frac, chunks,
          seed=PERMUTATION_SEED, expect=True, n_priced=None) -> dict:
    rows = load_census(census_path)
    report = frame_report(rows)
    if expect:
        assert_frame(report)

    nt = nontied_rows(rows)
    w = {s: report["strata"][s]["share_of_nontied"] for s in STRATA}
    quota = allocate(n)
    games = sorted({r["game_id"] for r in nt})
    split = split_games(games, holdout_frac, seed)
    holdout = set(split["holdout"])

    drawn = draw(nt, quota, cap_per_game, seed)
    order = committed_order([rid_of(r) for r in drawn])
    cuts = chunk_slices(order, chunks)
    chunk_of = {rid: i for i, c in enumerate(cuts, 1) for rid in c}

    flat = [rid for c in cuts for rid in c]
    if sorted(flat) != sorted(order) or len(flat) != len(set(flat)):
        raise SystemExit("REFUSING: chunks do not partition the drawn order exactly")

    by_rid = {rid_of(r): r for r in drawn}
    if len(by_rid) != len(drawn):
        raise SystemExit("REFUSING: duplicate rid in the draw")

    sel_rows = []
    for rid in order:
        r = by_rid[rid]
        sel_rows.append({
            "rid": rid,
            "game_id": r["game_id"],
            "deck_seed": r["deck_seed"],
            "ply": r["ply"],
            "seat": r["seat"],
            "k_remaining": r["k_remaining"],
            "n_legal": r["n_legal"],
            "gap": r["gap"],
            "top1": r["top1"],
            "top2": r["top2"],
            "phase_bucket": r["phase_bucket"],
            "stratum": stratum_of(float(r["gap"])),
            "slice": "holdout" if r["game_id"] in holdout else "dev",
            "chunk": chunk_of[rid],
        })

    realized = Counter(x["stratum"] for x in sel_rows)
    realized_f = {s: realized[s] / len(sel_rows) for s in STRATA}
    dev_f = {s: sum(1 for x in sel_rows if x["stratum"] == s and x["slice"] == "dev")
             for s in STRATA}
    per_game = Counter(x["game_id"] for x in sel_rows)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "FRAME.json").write_text(json.dumps({
        "schema": SCHEMA,
        "census": str(census_path),
        "design_doc": "measurement/everyply_probe_20260823/DESIGN.md",
        "read_rule": "measurement/everyply_probe_20260823/READ_RULE.md",
        "note": ("DESIGN §2.1/§2.2's population tables, RE-DERIVED from the tracked "
                 "census at build time. This is a query, not a run: no engine, no "
                 "champion, no judge, no value."),
        "population": report,
    }, indent=1, sort_keys=True))

    (out_dir / "HOLDOUT_GAMES.json").write_text(json.dumps({
        "schema": SCHEMA,
        "seed": seed + 1,
        "frac": holdout_frac,
        "n_games_total": len(games),
        "n_holdout_games": len(split["holdout"]),
        "note": ("DESIGN §6.4 -- the split is over the CLUSTER unit (the game) and is "
                 "drawn BEFORE any position is selected and BEFORE any leg runs. It "
                 "enters E-FUND ONLY as the blind sign-consistency conjunct."),
        **split,
    }, indent=1, sort_keys=True))

    (out_dir / "POSITION_ORDER.json").write_text(json.dumps({
        "schema": SCHEMA,
        "seed": seed,
        "n": len(order),
        "chunks": chunks,
        "chunk_sizes": [len(c) for c in cuts],
        "note": ("ONE committed shuffle of the SORTED rid list, written BEFORE launch "
                 "and cut into sequential chunks. Every completed-chunk prefix is a "
                 "uniform random subsample, so a partial run is an unbiased read at "
                 "its realized n -- at CHUNK granularity only, never line granularity."),
        "order": order,
    }, indent=1, sort_keys=True))

    with open(out_dir / "SELECTION.jsonl", "w") as fh:
        for x in sel_rows:
            fh.write(json.dumps(x, sort_keys=True) + "\n")

    n_priced = int(n_priced if n_priced is not None else n)
    summary = {
        "schema": SCHEMA,
        "design_doc": "measurement/everyply_probe_20260823/DESIGN.md",
        "read_rule": "measurement/everyply_probe_20260823/READ_RULE.md",
        "permutation_seed": seed,
        "size": "SIZE-1 (MVS kill-screen)",
        "n_pool": len(sel_rows),
        "n_priced_planned": n_priced,
        "cap_per_game": cap_per_game,
        "chunks": chunks,
        "m_worlds": M_WORLDS,
        "k_arms": K_ARMS,
        "judges": {"ARB": "tier1-greedy (rust, B=16)", "IF": "clair-puct (rust, 100 sims)"},
        "population_weights_w": w,
        "committed_allocation_f": ALLOCATION_F,
        "quota": quota,
        "realized_allocation": dict(realized),
        "realized_f": realized_f,
        "max_abs_f_deviation_pp": max(
            abs(realized_f[s] - ALLOCATION_F[s]) * 100.0 for s in STRATA),
        "variance_price_sum_w2_over_f": variance_price(w),
        "se_inflation_vs_proportional": variance_price(w) ** 0.5,
        "dev_counts_by_stratum": dev_f,
        "n_holdout_positions": sum(1 for x in sel_rows if x["slice"] == "holdout"),
        "n_dev_positions": sum(1 for x in sel_rows if x["slice"] == "dev"),
        "n_games_touched": len(per_game),
        "max_positions_per_game": max(per_game.values()),
        "se_kappa_table": {
            str(nn): {str(q): se_kappa(nn, q) for q in Q_GRID}
            for nn in (400, len(sel_rows), 600, 900)
        },
        "cost_wh": cost_table(len(sel_rows), n_priced),
        "governance": ("0 games on every branch. NO deck band is claimed and NO "
                       "governance/BAND_REGISTRY.csv row is owed -- every position is an "
                       "offline replay of the already-claimed, already-retired band "
                       "28000000000 by an opponent-free instrument. See BAND_NOTE.md."),
    }
    (out_dir / "PLAN_SUMMARY.json").write_text(json.dumps(summary, indent=1, sort_keys=True))
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--census", default=str(DEFAULT_CENSUS))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--n", type=int, default=450,
                    help="SIZE-1 pool size (DESIGN §5.3)")
    ap.add_argument("--n-priced", type=int, default=400,
                    help="positions carried to IF pricing (DESIGN §5.3); costs only")
    ap.add_argument("--cap-per-game", type=int, default=2)
    ap.add_argument("--holdout-frac", type=float, default=0.25)
    ap.add_argument("--chunks", type=int, default=4)
    ap.add_argument("--seed", type=int, default=PERMUTATION_SEED)
    ap.add_argument("--no-expect", action="store_true",
                    help="skip the DESIGN §2.1 frame assertion (TESTS ONLY)")
    a = ap.parse_args(argv)

    summary = build(a.census, a.out_dir, n=a.n, cap_per_game=a.cap_per_game,
                    holdout_frac=a.holdout_frac, chunks=a.chunks, seed=a.seed,
                    expect=not a.no_expect, n_priced=a.n_priced)
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
