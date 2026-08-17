#!/usr/bin/env python3
"""Readout for a `match.py` archive — the champion-vs-JCloisterZone match.

Separate from ``match.py``'s own ``summarize()`` on purpose: that one runs inside the
fleet driver and answers "did the run go OK". This one is the ANALYSIS, and it is the
file to point a verdict at.

Three things it does that the driver's summary does not:

* **Elo, with the right sigma.** Win rate is converted to elo only as a courtesy
  statistic; the load-bearing number is the DECK-PAIRED margin, because pairing the two
  seatings of a deck removes the deck draw — the dominant variance component — and
  CLAUDE.md names within-band deck-paired contrasts as the robust class. Note the
  unpaired elo sigma quoted here is the WITHIN-band figure (695*sqrt(0.25/n)); nothing
  in this file is a cross-band contrast, so the 1.8-2.2x over-dispersion rider does not
  apply. It WOULD apply to anyone comparing this band against another.
* **The divergence ledger.** Every ply of every game ran the legality + score +
  partition diff. A win rate from an archive with a non-empty REAL ledger is partly a
  rules result, so the ledger is printed next to the number, never in a footnote.
* **Seat balance.** Reported per seat, because a deck-paired design is only unbiased if
  both seatings actually completed; a crash mid-run can leave orphan half-pairs, and
  those decks are excluded from the paired statistic rather than silently half-counted.

Usage:
    .venv/bin/python scripts/jcz_match/analyze.py measurement/jcz_match_20260809/confirm.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
from collections import Counter
from pathlib import Path


def wr_to_elo(wr: float) -> float | None:
    """Standard logistic conversion. Undefined at a clean sweep, so return None rather
    than an infinity that would later be formatted as a number."""
    if wr <= 0.0 or wr >= 1.0:
        return None
    return -400.0 * math.log10(1.0 / wr - 1.0)


def load(path: Path) -> list[dict]:
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:      # a torn last line from a dirty crash
            continue
    return out


def analyze(records: list[dict]) -> dict:
    scored = [r for r in records if not r.get("void") and r.get("winner")]
    voids = Counter(r["void"] for r in records if r.get("void"))

    wins = sum(1 for r in scored if r["winner"] == "champ")
    draws = sum(1 for r in scored if r["winner"] == "draw")
    losses = sum(1 for r in scored if r["winner"] == "jcz")
    n = len(scored)
    wr = (wins + 0.5 * draws) / n if n else None

    # deck-paired margin: per deck, the mean over the two seatings
    by_deck: dict[int, dict[int, list[int]]] = {}
    for r in scored:
        by_deck.setdefault(int(r["deck_seed"]), {}).setdefault(
            int(r["champ_seat"]), []).append(int(r["margin_champ_minus_jcz"]))
    paired = [st.mean([st.mean(v) for v in seats.values()])
              for seats in by_deck.values() if len(seats) == 2]
    half_pairs = [d for d, seats in by_deck.items() if len(seats) != 2]

    p_mean = st.mean(paired) if paired else None
    p_sem = (st.stdev(paired) / math.sqrt(len(paired))
             if len(paired) > 1 else None)
    p_z = (p_mean / p_sem) if (p_mean is not None and p_sem) else None

    margins = [r["margin_champ_minus_jcz"] for r in scored]
    counts: Counter = Counter()
    real: Counter = Counter()
    for r in records:
        counts.update(r.get("counts") or {})
        real.update(r.get("real") or {})

    per_seat = {}
    for cs in (0, 1):
        rs = [r for r in scored if int(r["champ_seat"]) == cs]
        if not rs:
            continue
        per_seat[cs] = {
            "n": len(rs),
            "wins": sum(1 for r in rs if r["winner"] == "champ"),
            "draws": sum(1 for r in rs if r["winner"] == "draw"),
            "mean_margin": st.mean(r["margin_champ_minus_jcz"] for r in rs),
        }

    def _m(key):
        vals = [r[key] for r in records if r.get(key) is not None]
        return st.mean(vals) if vals else None

    out = {
        "n_records": len(records), "n_scored": n, "voids": dict(voids),
        "wins": wins, "draws": draws, "losses": losses,
        "win_rate": wr,
        "elo_unpaired": wr_to_elo(wr) if wr is not None else None,
        "elo_sigma_1s": 695.0 * math.sqrt(0.25 / n) if n else None,
        "n_paired_decks": len(paired),
        "half_pair_decks": half_pairs,
        "paired_margin_mean": p_mean, "paired_margin_sem": p_sem, "paired_margin_z": p_z,
        "unpaired_margin_mean": st.mean(margins) if margins else None,
        "unpaired_margin_sd": st.stdev(margins) if len(margins) > 1 else None,
        "per_seat": per_seat,
        "divergence_counts": dict(counts), "divergence_real": dict(real),
        "final_agree_all": all(r.get("final_agree") for r in scored),
        "replay_ok_all": all(r.get("replay_ok") for r in scored),
        "ms_per_move_champ": _m("ms_per_move_champ"),
        "ms_per_move_jcz": _m("ms_per_move_jcz"),
        "wall_secs_per_game": _m("wall_secs"),
    }
    ta = tiearb_block(records)
    if ta is not None:
        out["tiearb"] = ta
    return out


def tiearb_block(records: list[dict]) -> dict | None:
    """THE FIRING LEDGER for a tie-arbiter cell, or ``None`` when no game carries the
    telemetry — a legacy archive's readout is then byte-identical to before.

    Mirrors ``eval_fair_puct``'s cell-level block, and it is not a courtesy statistic:
    ⚠️ READ_RULE `G-FIRE` VOIDS the cell when ``phi < 1.0``. A surface that never fired
    grades a champion-vs-champion null wearing the shape of a real match, so this block
    is printed next to the win rate, never in a footnote — exactly like the divergence
    ledger above it.

    ``phi`` = fired tile plies PER GAME. ``phi_effective`` discounts it by the FAIL-SOFT
    error rate, because a ply that errored fell back to the champion's own pick: it was
    counted as fired but did not arbitrate, and only the effective figure states how
    much of the cell's play the surface actually touched. ⚠️ Games are counted over ALL
    records that carry telemetry, VOIDS INCLUDED — the arbiter ran in a voided game
    too, and dropping those would flatter ``phi``.
    """
    ta = [r["champ_tiearb"] for r in records if r.get("champ_tiearb")]
    if not ta:
        return None
    games = len(ta)
    fired = sum(int(t["fired_plies"]) for t in ta)
    tile = sum(int(t["tile_plies"]) for t in ta)
    chg = sum(int(t["pickchanges"]) for t in ta)
    arms = sum(int(t["arms_total"]) for t in ta)
    playouts = sum(int(t["playouts_total"]) for t in ta)
    secs = sum(float(t["secs"]) for t in ta)
    errs = sum(int(t.get("errors") or 0) for t in ta)
    partial = sum(int(t.get("partial_argmax") or 0) for t in ta)
    err_rate = errs / max(1, fired + errs)
    phi = fired / max(1, games)
    return {
        "tiearb_games": games,
        "tiearb_fired_plies_total": fired,
        "tiearb_tile_plies_total": tile,
        "phi": phi,
        "error_rate_on_fired": err_rate,
        "phi_effective": phi * (1.0 - err_rate),
        "fire_rate_on_tile_plies": fired / max(1, tile),
        "pickchanges_total": chg,
        "pickchange_rate": chg / max(1, fired),
        "mean_arms": arms / max(1, fired),
        "playouts_total": playouts,
        "secs_total": secs,
        "secs_per_game": secs / max(1, games),
        "errors_total": errs,
        "first_error": next((t.get("first_error") for t in ta
                             if t.get("first_error")), None),
        # READ_RULE §0.F `G-PLY`. Expected 0; ABSENT or NON-ZERO voids the cell, so it
        # is emitted unconditionally on every arbiter cell.
        "partial_argmax_total": partial,
        "max_plies": sorted({int(t.get("max_plies") or 0) for t in ta}),
        "modes": sorted({str(t["mode"]) for t in ta}),
        "B": sorted({int(t["B"]) for t in ta}),
        "J": sorted({int(t["J"]) for t in ta}),
        "G_FIRE_floor": 1.0,
        "G_FIRE_fired": bool(phi < 1.0),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archive")
    ap.add_argument("--json", action="store_true", help="machine-readable only")
    args = ap.parse_args(argv)

    recs = load(Path(args.archive))
    a = analyze(recs)
    if args.json:
        print(json.dumps(a, indent=1, sort_keys=True))
        return 0

    def f(x, nd=2):
        return "n/a" if x is None else f"{x:.{nd}f}"

    print(f"archive           {args.archive}")
    print(f"records           {a['n_records']}  scored={a['n_scored']}  voids={a['voids'] or '{}'}")
    print(f"W/D/L             {a['wins']}/{a['draws']}/{a['losses']}")
    print(f"win rate          {f(a['win_rate'], 4)}   -> elo {f(a['elo_unpaired'], 1)} "
          f"(1 sigma ~ +/-{f(a['elo_sigma_1s'], 1)}, within-band)")
    print(f"DECK-PAIRED       {f(a['paired_margin_mean'])} +/- {f(a['paired_margin_sem'])} pts "
          f"(z {f(a['paired_margin_z'])})  over {a['n_paired_decks']} decks")
    if a["half_pair_decks"]:
        print(f"  !! half-pairs   {len(a['half_pair_decks'])} decks excluded (one seating only)")
    print(f"unpaired margin   {f(a['unpaired_margin_mean'])}  sd {f(a['unpaired_margin_sd'])}")
    for cs, d in sorted(a["per_seat"].items()):
        print(f"  champ_seat={cs}     n={d['n']} W={d['wins']} D={d['draws']} "
              f"mean margin {f(d['mean_margin'])}")
    print(f"divergences       counts={a['divergence_counts'] or '{}'}  "
          f"REAL={a['divergence_real'] or '{}'}")
    print(f"score agreement   final_agree_all={a['final_agree_all']}  "
          f"replay_ok_all={a['replay_ok_all']}")
    print(f"timing            champ {f(a['ms_per_move_champ'], 0)} ms/move   "
          f"JCZ {f(a['ms_per_move_jcz'], 1)} ms/move   "
          f"{f(a['wall_secs_per_game'], 1)} s/game")
    t = a.get("tiearb")
    if t:
        print(f"TIE ARBITER       {t['tiearb_games']} games  mode(s) "
              f"{'/'.join(t['modes'])} B={t['B']} J={t['J']}")
        print(f"  phi             {f(t['phi'])} fired tile plies/game "
              f"(effective {f(t['phi_effective'])}; "
              f"{t['tiearb_fired_plies_total']}/{t['tiearb_tile_plies_total']} of "
              f"tile plies)")
        print(f"  pick-change     {f(t['pickchange_rate'], 3)} "
              f"({t['pickchanges_total']} of {t['tiearb_fired_plies_total']})   "
              f"mean arms {f(t['mean_arms'])}   {f(t['secs_per_game'], 1)} s/game")
        if t["errors_total"]:
            print(f"  !! FAIL-SOFT    {t['errors_total']} arbiter errors "
                  f"(rate on fired {f(t['error_rate_on_fired'], 4)}; fell back to the "
                  f"champion's pick; first: {str(t['first_error'])[:120]})")
        if t["partial_argmax_total"]:
            print(f"  ** G-PLY        {t['partial_argmax_total']} plies took an "
                  "argmax over FEWER than B completed worlds — the CRN pairing across "
                  "arms is broken and this cell is U-UNREADABLE (READ_RULE 0.F).")
        if t["G_FIRE_fired"]:
            print("  ** G-FIRE       phi < 1.0 — THE ARBITRATION SURFACE IS "
                  "EFFECTIVELY INERT AND THIS CELL IS U-UNREADABLE (READ_RULE 3). "
                  "Do NOT read it as a null.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
