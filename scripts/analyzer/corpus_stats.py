#!/usr/bin/env python3
"""Phase-5 analyzer, slice 1: the champion-corpus descriptive-stats catalog.

Replays a games jsonl (the `(deck_seed, actions)` root_replay contract) and emits
a self-describing JSON catalog plus a compact markdown table. Pure replay — no
search, no network, no leaf eval — so the whole thing is deterministic and cheap
(~0.12 s/game single-threaded).

    scripts/analyzer/corpus_stats.py CORPUS.jsonl -o OUT_DIR --label champ449 \
        --corpus-note "champion-vs-champion self-play, k4x688 (2752/move)"

The JSON is the source of truth: `e4_diff.py` percentile-ranks a human game
against `per_seat` / `per_game`, and every number in any report must be
traceable back to a field here. Stat definitions live in `replay_stats`'s module
docstring and are copied into the JSON's `definitions` block so a reader of the
artifact alone can interpret it.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "measurement_infra"))

SCHEMA = "carcassonne-analyzer-corpus-stats/v1"

DEFINITIONS = {
    "replay": "Pure (deck_seed, actions) replay via scripts/measurement_infra/root_replay. "
              "No search. Terminal scores are verified against the corpus's recorded "
              "scores where present (replay_scores_match).",
    "turn": "One player's tile ply plus its meeple ply (the engine's tile-phase "
            "PassAction path collapses to a single ply; both are one turn here).",
    "k_remaining": "len(state.deck) at the START of a turn = tiles still to be drawn "
                   "after this one. Bands are ABSOLUTE: early k>=48, mid 24<=k<48, late k<24.",
    "tercile": "early/mid/late by thirds of THIS game's turn count. Reported alongside "
               "k-bands because the two disagree whenever a game ends early.",
    "returned": "A meeple leaves state.placed_meeples during play. The engine only does "
                "this in remove_meeples_and_collect_points, so returned == scored during play.",
    "stranded_nonfarmer": "A normal meeple (city/road/cloister) still on the board in the "
                          "meeple-intact terminal state. THE stranding metric.",
    "stranded_all": "Includes farmers. Farmers are unrecoverable BY DESIGN in Base+Farmers, "
                    "so this is a board-occupancy figure, not an error rate. Do not quote it "
                    "as one.",
    "meeple_turns_locked": "Sum over stranded non-farmer meeples of (n_turns - place_turn): "
                           "turns of meeple capital tied up in features that never paid during play.",
    "points_per_meeple_turn": "Corpus rate: total during-play points won by RETURNED meeples "
                              "divided by the meeple-turns those returned meeples occupied. "
                              "The conversion factor for pricing stranding in points.",
    "score_flow": "during_play (banked before the terminating move) + incomplete (unfinished "
                  "city/road/cloister paid at end) + farms. Computed by replaying with "
                  "PointsCollector.count_final_scores stubbed so the terminal state keeps its "
                  "meeples, then attributing via aux_targets.extract_terminal_ownership. "
                  "Reconciled against the true final scores; split_ok=False if it does not add up.",
    "completion": "A city/road/cloister that becomes finished during play. Identified by its "
                  "frozen coordinate set (union-find root ids are not stable across calls); a "
                  "finished feature can never grow, so first sighting == closure turn. "
                  "scored=False means it closed with nobody on it.",
}

GAME_SCALARS = ["n_turns", "n_completions", "n_cities_closed", "n_roads_closed",
                "n_cloisters_closed", "mean_city_size", "mean_road_size",
                "max_city_size", "score_margin_abs", "total_points"]

# The seat scalars promoted into the headline markdown table.
SEAT_HEADLINE = [
    "final_score", "during_play", "incomplete_pts", "farm_pts",
    "during_play_frac", "farm_pts_frac",
    "n_meeples_placed", "n_farmers_placed", "deploy_rate",
    "stranded_nonfarmer", "stranding_rate_nonfarmer", "meeple_turns_locked",
    "first_farm_turn", "first_farm_k_remaining", "mean_farm_turn",
    "farm_pts_per_farmer", "n_farmers_early", "n_farmers_mid", "n_farmers_late",
    "mean_meeples_in_hand", "min_meeples_in_hand", "n_features_won",
    "mean_city_size_won", "mean_road_size_won", "pts_per_meeple_placed",
]


def _one(job):
    """Worker: replay one game -> (game_scalars, [seat_scalars], per-game detail)."""
    deck_seed, actions, recorded, game_id = job
    from replay_stats import replay_game_stats, game_scalars, seat_scalars
    st = replay_game_stats(deck_seed, actions, recorded_scores=recorded, game_id=game_id)
    seats = [seat_scalars(st, p) for p in range(st.n_players)]
    detail = {
        "completions": [{k: v for k, v in e.items() if k != "returned_keys"}
                        for e in st.completions],
        "meeples": st.meeples,
        "turns": [{k: t[k] for k in ("turn", "player", "k_remaining", "move_type",
                                     "meeples_in_hand", "open_city", "open_road",
                                     "open_cloister", "meeples_on_board")}
                  for t in st.turns],
        "score_flow": st.score_flow,
    }
    g = game_scalars(st)
    g.update({"game_id": game_id, "deck_seed": deck_seed,
              "replay_scores_match": st.replay_scores_match, "split_ok": st.split_ok,
              "final_scores": st.final_scores})
    return g, seats, detail


def _dist(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    def q(f):
        if len(xs) == 1:
            return xs[0]
        i = f * (len(xs) - 1)
        lo, hi = int(i), min(int(i) + 1, len(xs) - 1)
        return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)
    return {"n": len(xs), "mean": statistics.fmean(xs),
            "sd": statistics.stdev(xs) if len(xs) > 1 else 0.0,
            "min": xs[0], "p5": q(.05), "p25": q(.25), "p50": q(.50),
            "p75": q(.75), "p95": q(.95), "max": xs[-1]}


def _hist(xs):
    h = {}
    for x in xs:
        h[str(x)] = h.get(str(x), 0) + 1
    return dict(sorted(h.items(), key=lambda kv: int(kv[0])))


def aggregate(games, seats, details, label, corpus_path, corpus_note, source_meta):
    from replay_stats import PHASES, TERRAINS, tercile

    all_comp = [e for d in details for e in d["completions"]]
    all_meeples = [m for d in details for m in d["meeples"]]
    all_turns = [t for d in details for t in d["turns"]]

    # --- move-type mix, pooled over all seats, both segmentations ------------ #
    n_turns_by_game = {g["game_id"]: g["n_turns"] for g in games}
    mix = {"by_k_band": {}, "by_tercile": {}, "segmentation_agreement": None}
    _agree = _tot = 0
    for d, g in zip(details, games):
        nt = g["n_turns"]
        for t in d["turns"]:
            kb = ("early" if t["k_remaining"] >= 48 else
                  "mid" if t["k_remaining"] >= 24 else "late")
            tc = tercile(t["turn"], nt)
            _tot += 1
            _agree += (kb == tc)
            for seg, ph in (("by_k_band", kb), ("by_tercile", tc)):
                b = mix[seg].setdefault(ph, {"n_turns": 0, **{k: 0 for k in TERRAINS},
                                             "pass": 0})
                b["n_turns"] += 1
                b[t["move_type"]] = b.get(t["move_type"], 0) + 1
    mix["segmentation_agreement"] = _agree / _tot if _tot else None
    for seg in ("by_k_band", "by_tercile"):
        for ph, b in mix[seg].items():
            n = b["n_turns"]
            b["frac"] = {k: (b[k] / n if n else None) for k in list(TERRAINS) + ["pass"]}
            b["deploy_rate"] = (n - b["pass"]) / n if n else None

    # --- completed-feature size distributions -------------------------------- #
    feat = {}
    for terr in ("city", "road", "cloister"):
        sel = [e for e in all_comp if e["terrain"] == terr]
        feat[terr] = {
            "n_closed_total": len(sel),
            "per_game_mean": len(sel) / len(games) if games else None,
            "size_hist": _hist([e["size"] for e in sel]),
            "size_dist": _dist([e["size"] for e in sel]),
            "points_dist": _dist([e["points"] for e in sel]),
            "frac_unscored": (sum(1 for e in sel if not e["scored"]) / len(sel)
                              if sel else None),
            "closure_turn_dist": _dist([e["turn"] for e in sel]),
            "by_k_band": {ph: {"n": sum(1 for e in sel if e["k_band"] == ph),
                               "size_dist": _dist([e["size"] for e in sel
                                                   if e["k_band"] == ph])}
                          for ph in PHASES},
        }
    feat["city"]["shields_dist"] = _dist([e["shields"] for e in all_comp
                                          if e["terrain"] == "city"])

    # --- meeple economy + openness curves, by turn index --------------------- #
    max_turn = max((t["turn"] for t in all_turns), default=0)
    curve = {"turn": [], "mean_meeples_in_hand": [], "mean_meeples_on_board": [],
             "mean_open_city": [], "mean_open_road": [], "mean_open_cloister": [],
             "n_samples": []}
    by_turn = {}
    for t in all_turns:
        by_turn.setdefault(t["turn"], []).append(t)
    for i in range(max_turn + 1):
        sel = by_turn.get(i, [])
        if not sel:
            continue
        curve["turn"].append(i)
        curve["n_samples"].append(len(sel))
        curve["mean_meeples_in_hand"].append(
            statistics.fmean([x for t in sel for x in t["meeples_in_hand"]]))
        curve["mean_meeples_on_board"].append(
            statistics.fmean([t["meeples_on_board"] for t in sel]))
        for k, src in (("mean_open_city", "open_city"), ("mean_open_road", "open_road"),
                       ("mean_open_cloister", "open_cloister")):
            curve[k].append(statistics.fmean([t[src] for t in sel]))

    # --- stranding ----------------------------------------------------------- #
    nonfarm = [m for m in all_meeples if m["terrain"] != "farm"]
    farmers = [m for m in all_meeples if m["terrain"] == "farm"]
    returned = [m for m in nonfarm if not m["stranded"]]
    ret_turns = sum(m["locked_turns"] for m in returned)
    ret_points = sum(m["points_earned"] for m in returned)
    ppmt = ret_points / ret_turns if ret_turns else None
    stranded_nf = [m for m in nonfarm if m["stranded"]]
    stranding = {
        "n_nonfarm_placed": len(nonfarm),
        "n_nonfarm_stranded": len(stranded_nf),
        "rate_nonfarmer": len(stranded_nf) / len(nonfarm) if nonfarm else None,
        "n_farmers_placed": len(farmers),
        "rate_all_incl_farmers": (sum(1 for m in all_meeples if m["stranded"])
                                  / len(all_meeples) if all_meeples else None),
        "by_placement_k_band": {
            ph: {"n_placed": sum(1 for m in nonfarm if m["place_k_band"] == ph),
                 "n_stranded": sum(1 for m in stranded_nf if m["place_k_band"] == ph),
                 "rate": (sum(1 for m in stranded_nf if m["place_k_band"] == ph)
                          / max(1, sum(1 for m in nonfarm if m["place_k_band"] == ph)))}
            for ph in PHASES},
        "by_placement_tercile": {
            ph: {"n_placed": sum(1 for m in nonfarm if m["place_tercile"] == ph),
                 "n_stranded": sum(1 for m in stranded_nf if m["place_tercile"] == ph),
                 "rate": (sum(1 for m in stranded_nf if m["place_tercile"] == ph)
                          / max(1, sum(1 for m in nonfarm if m["place_tercile"] == ph)))}
            for ph in PHASES},
        "by_terrain": {
            terr: {"n_placed": sum(1 for m in nonfarm if m["terrain"] == terr),
                   "n_stranded": sum(1 for m in stranded_nf if m["terrain"] == terr),
                   "rate": (sum(1 for m in stranded_nf if m["terrain"] == terr)
                            / max(1, sum(1 for m in nonfarm if m["terrain"] == terr)))}
            for terr in ("city", "road", "cloister")},
        "locked_turns_dist_stranded": _dist([m["locked_turns"] for m in stranded_nf]),
        "locked_turns_dist_returned": _dist([m["locked_turns"] for m in returned]),
        "points_per_meeple_turn": ppmt,
        "returned_meeple_turns": ret_turns,
        "returned_points": ret_points,
        "stranded_meeple_turns": sum(m["locked_turns"] for m in stranded_nf),
    }
    # --- the during-play cost of stranding ---------------------------------- #
    # GROSS: what the stranded meeple-turns would have earned had they been
    # redeployed at the corpus's own realised during-play rate. This is an upper
    # read — it assumes a productive alternative placement always existed.
    # It also OVERSTATES the loss on its own, because a stranded meeple is not
    # idle: it collects the unfinished-feature payout at game end. NET subtracts
    # that. Quote NET unless you mean the gross opportunity figure.
    n_seats_ = 2 * len(games) if games else 0
    gross = ((stranding["stranded_meeple_turns"] * ppmt) / n_seats_
             if (ppmt and n_seats_) else None)
    inc_per_seat = (sum(f["incomplete"] for d in details for f in d["score_flow"])
                    / n_seats_) if n_seats_ else None
    stranding.update({
        "stranding_cost_gross_pts_per_seat": gross,
        "incomplete_pts_earned_per_seat": inc_per_seat,
        "stranding_cost_net_pts_per_seat": (
            gross - inc_per_seat if (gross is not None and inc_per_seat is not None)
            else None),
    })

    # --- farm timing ---------------------------------------------------------- #
    first_farms = [s["first_farm_turn"] for s in seats if s["first_farm_turn"] is not None]
    farm = {
        "n_farmers_total": len(farmers),
        "per_seat_mean": len(farmers) / len(seats) if seats else None,
        "placement_turn_dist": _dist([m["place_turn"] for m in farmers]),
        "placement_turn_hist": _hist([m["place_turn"] for m in farmers]),
        "placement_k_band_counts": {ph: sum(1 for m in farmers if m["place_k_band"] == ph)
                                    for ph in PHASES},
        "placement_k_band_frac": {ph: (sum(1 for m in farmers if m["place_k_band"] == ph)
                                       / len(farmers) if farmers else None)
                                  for ph in PHASES},
        "first_farm_turn_dist": _dist(first_farms),
        "first_farm_turn_hist": _hist(first_farms),
        "seats_with_no_farmer": sum(1 for s in seats if s["first_farm_turn"] is None),
        "farm_meeple_turns_locked_dist": _dist([m["locked_turns"] for m in farmers]),
        "farm_pts_per_farmer_dist": _dist([s["farm_pts_per_farmer"] for s in seats]),
    }

    seat_keys = sorted({k for s in seats for k in s})
    out = {
        "schema": SCHEMA,
        "label": label,
        "corpus_path": str(corpus_path),
        "corpus_note": corpus_note,
        "source_meta": source_meta,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_games": len(games),
        "n_seats": len(seats),
        "integrity": {
            "replay_scores_match": sum(1 for g in games if g["replay_scores_match"] is True),
            "replay_scores_mismatch": sum(1 for g in games
                                          if g["replay_scores_match"] is False),
            "replay_scores_unchecked": sum(1 for g in games
                                           if g["replay_scores_match"] is None),
            "split_ok": sum(1 for g in games if g["split_ok"]),
            "split_failed": sum(1 for g in games if not g["split_ok"]),
        },
        "definitions": DEFINITIONS,
        "game_dist": {k: _dist([g.get(k) for g in games]) for k in GAME_SCALARS},
        "seat_dist": {k: _dist([s.get(k) for s in seats]) for k in seat_keys},
        "move_mix": mix,
        "completed_features": feat,
        "curves": curve,
        "stranding": stranding,
        "farm_timing": farm,
        "score_flow_dist": {k: _dist([s[k] for s in seats])
                            for k in ("during_play", "incomplete_pts", "farm_pts",
                                      "final_score")},
        "per_game": games,
        "per_seat": seats,
    }
    return out


def to_markdown(cat) -> str:
    L = []
    A = L.append
    A(f"# Corpus stats — `{cat['label']}`")
    A("")
    A(f"**Corpus:** `{cat['corpus_path']}` — {cat['corpus_note']}  ")
    A(f"**Games:** {cat['n_games']} ({cat['n_seats']} seats) · "
      f"generated {cat['generated_at']} · schema `{cat['schema']}`  ")
    itg = cat["integrity"]
    A(f"**Integrity:** replay scores match {itg['replay_scores_match']}/"
      f"{cat['n_games']} (mismatch {itg['replay_scores_mismatch']}, "
      f"unchecked {itg['replay_scores_unchecked']}) · score split reconciles "
      f"{itg['split_ok']}/{cat['n_games']}")
    A("")
    A("Every number below is a field of the companion JSON. Definitions: see its "
      "`definitions` block (stranding is **non-farmer** unless it says otherwise — "
      "farmers are unrecoverable by design).")
    A("")

    A("## Seat-level distributions (both seats pooled)")
    A("")
    A("| stat | mean | sd | p5 | p50 | p95 |")
    A("|---|---:|---:|---:|---:|---:|")
    for k in SEAT_HEADLINE:
        d = cat["seat_dist"].get(k)
        if not d:
            continue
        A(f"| {k} | {d['mean']:.3g} | {d['sd']:.3g} | {d['p5']:.3g} | "
          f"{d['p50']:.3g} | {d['p95']:.3g} |")
    A("")

    A("## Move-type mix by phase")
    A("")
    agr = cat["move_mix"]["segmentation_agreement"]
    A(f"The two segmentations label the same turn identically **{agr:.4f}** of the time. "
      "They coincide exactly whenever every game runs the full 72 tiles (turns 0–23 ↔ "
      "k 71–48, 24–47 ↔ k 47–24, 48–71 ↔ k 23–0); they only diverge for short games. "
      "Both are printed anyway so the reader can see that, and so the tables stay "
      "comparable against a corpus where games DO end early.")
    A("")
    for seg, title in (("by_k_band", "k_remaining bands (absolute: early ≥48, mid 24–47, late <24)"),
                       ("by_tercile", "turn terciles (relative to each game's length)")):
        A(f"**{title}**")
        A("")
        A("| phase | turns | city | road | farm | cloister | pass | deploy rate |")
        A("|---|---:|---:|---:|---:|---:|---:|---:|")
        for ph in ("early", "mid", "late"):
            b = cat["move_mix"][seg].get(ph)
            if not b:
                continue
            f = b["frac"]
            A(f"| {ph} | {b['n_turns']} | {f['city']:.3f} | {f['road']:.3f} | "
              f"{f['farm']:.3f} | {f['cloister']:.3f} | {f['pass']:.3f} | "
              f"{b['deploy_rate']:.3f} |")
        A("")

    A("## Completed-feature sizes (closed during play)")
    A("")
    A("| feature | closed/game | mean size | p50 | p95 | max | mean pts | closed w/ nobody on it |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|")
    for terr in ("city", "road", "cloister"):
        f = cat["completed_features"][terr]
        sd, pd = f["size_dist"], f["points_dist"]
        if not sd:
            continue
        A(f"| {terr} | {f['per_game_mean']:.2f} | {sd['mean']:.2f} | {sd['p50']:.3g} | "
          f"{sd['p95']:.3g} | {sd['max']} | {pd['mean']:.2f} | {f['frac_unscored']:.3f} |")
    A("")
    A("Completed-size histograms (tiles → count):")
    A("")
    for terr in ("city", "road"):
        A(f"- **{terr}**: " + ", ".join(
            f"{k}:{v}" for k, v in cat["completed_features"][terr]["size_hist"].items()))
    A("")

    A("## Stranding (non-farmer meeples never returned)")
    A("")
    s = cat["stranding"]
    A(f"- overall rate **{s['rate_nonfarmer']:.3f}** "
      f"({s['n_nonfarm_stranded']}/{s['n_nonfarm_placed']} non-farmer deployments)")
    A(f"- including farmers (occupancy, NOT an error rate): "
      f"{s['rate_all_incl_farmers']:.3f}")
    A(f"- points per meeple-turn earned by returned meeples: "
      f"**{s['points_per_meeple_turn']:.4f}** "
      f"({s['returned_points']} pts / {s['returned_meeple_turns']} meeple-turns)")
    A(f"- stranded meeple-turns: {s['stranded_meeple_turns']} → gross opportunity "
      f"{s['stranding_cost_gross_pts_per_seat']:.1f} pts/seat/game at that rate, "
      f"minus the {s['incomplete_pts_earned_per_seat']:.1f} pts/seat those stranded "
      f"meeples DO collect at game end = **net {s['stranding_cost_net_pts_per_seat']:.1f} "
      f"pts/seat/game**. Upper read: it assumes a productive alternative placement "
      f"always existed.")
    A("")
    A("| placement band | non-farmer placed | stranded | rate |")
    A("|---|---:|---:|---:|")
    for ph in ("early", "mid", "late"):
        b = s["by_placement_k_band"][ph]
        A(f"| {ph} | {b['n_placed']} | {b['n_stranded']} | {b['rate']:.3f} |")
    A("")
    A("| terrain | placed | stranded | rate |")
    A("|---|---:|---:|---:|")
    for terr in ("city", "road", "cloister"):
        b = s["by_terrain"][terr]
        A(f"| {terr} | {b['n_placed']} | {b['n_stranded']} | {b['rate']:.3f} |")
    A("")

    A("## Farm timing")
    A("")
    fm = cat["farm_timing"]
    d = fm["first_farm_turn_dist"]
    A(f"- farmers per seat: **{fm['per_seat_mean']:.2f}** "
      f"({fm['n_farmers_total']} total; {fm['seats_with_no_farmer']} seats played none)")
    if d:
        A(f"- **first** farmer turn: mean {d['mean']:.1f}, p5 {d['p5']:.0f}, "
          f"p50 {d['p50']:.0f}, p95 {d['p95']:.0f}")
    pd = fm["placement_turn_dist"]
    A(f"- ALL farmer placements, turn: mean {pd['mean']:.1f}, p5 {pd['p5']:.0f}, "
      f"p50 {pd['p50']:.0f}, p95 {pd['p95']:.0f}")
    fr = fm["placement_k_band_frac"]
    A(f"- by band: early {fr['early']:.3f} · mid {fr['mid']:.3f} · late {fr['late']:.3f}")
    fp = fm["farm_pts_per_farmer_dist"]
    if fp:
        A(f"- farm points per farmer: mean {fp['mean']:.2f}, p50 {fp['p50']:.2f}")
    A("")

    A("## Score flow (per seat)")
    A("")
    A("| bucket | mean | sd | p5 | p50 | p95 |")
    A("|---|---:|---:|---:|---:|---:|")
    for k in ("during_play", "incomplete_pts", "farm_pts", "final_score"):
        d = cat["score_flow_dist"][k]
        A(f"| {k} | {d['mean']:.2f} | {d['sd']:.2f} | {d['p5']:.3g} | {d['p50']:.3g} | "
          f"{d['p95']:.3g} |")
    A("")

    A("## Meeple economy + openness (mean over corpus, by turn)")
    A("")
    c = cat["curves"]
    A("| turn | meeples in hand | meeples on board | open cities | open roads | open cloisters |")
    A("|---:|---:|---:|---:|---:|---:|")
    step = max(1, len(c["turn"]) // 12)
    for i in range(0, len(c["turn"]), step):
        A(f"| {c['turn'][i]} | {c['mean_meeples_in_hand'][i]:.2f} | "
          f"{c['mean_meeples_on_board'][i]:.2f} | {c['mean_open_city'][i]:.2f} | "
          f"{c['mean_open_road'][i]:.2f} | {c['mean_open_cloister'][i]:.2f} |")
    A("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus", help="games jsonl (deck_seed + actions per line)")
    ap.add_argument("-o", "--out-dir", required=True)
    ap.add_argument("--label", required=True, help="short corpus label, e.g. champ449")
    ap.add_argument("--corpus-note", default="", help="one-line provenance for the report")
    ap.add_argument("--workers", type=int, default=4,
                    help="process pool size (default 4; the box is shared)")
    ap.add_argument("--limit", type=int, default=0, help="first N games only (debug)")
    args = ap.parse_args()

    from root_replay import load_games
    recs = load_games(args.corpus)
    if args.limit:
        recs = recs[:args.limit]
    print(f"[corpus_stats] {len(recs)} games from {args.corpus}", flush=True)

    # Corpus-level provenance: the config fields the generator stamped on each row.
    keys = ("gen", "k_dets", "sims_per_det", "total_budget_per_move", "leaf",
            "leaf_hash_runtime", "code_rev", "exact_max_k", "champion_id",
            "sims_effective", "k_dets_effective", "start_rule", "grid_rule")
    source_meta = {}
    for k in keys:
        vals = {json.dumps(r.meta[k]) for r in recs if k in r.meta}
        if vals:
            source_meta[k] = (json.loads(next(iter(vals))) if len(vals) == 1
                              else f"<{len(vals)} distinct values>")

    jobs = [(r.deck_seed, r.actions,
             ([r.meta["score_p0"], r.meta["score_p1"]]
              if "score_p0" in r.meta and "score_p1" in r.meta else None),
             r.game_id) for r in recs]

    t0 = time.time()
    games, seats, details = [], [], []
    if args.workers > 1:
        import multiprocessing as mp
        with mp.Pool(args.workers) as pool:
            for i, (g, ss, d) in enumerate(pool.imap(_one, jobs, chunksize=8)):
                games.append(g); seats.extend(ss); details.append(d)
                if (i + 1) % 100 == 0:
                    print(f"  {i+1}/{len(jobs)}  {time.time()-t0:.0f}s", flush=True)
    else:
        for i, job in enumerate(jobs):
            g, ss, d = _one(job)
            games.append(g); seats.extend(ss); details.append(d)
    print(f"[corpus_stats] replayed in {time.time()-t0:.1f}s", flush=True)

    cat = aggregate(games, seats, details, args.label, args.corpus,
                    args.corpus_note, source_meta)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    jp = out / f"CORPUS_STATS_{args.label}.json"
    mp_ = out / f"CORPUS_STATS_{args.label}.md"
    jp.write_text(json.dumps(cat, indent=1))
    mp_.write_text(to_markdown(cat))
    print(f"[corpus_stats] wrote {jp} ({jp.stat().st_size/1e6:.1f} MB) and {mp_}")
    itg = cat["integrity"]
    print(f"[corpus_stats] integrity: scores match {itg['replay_scores_match']}, "
          f"mismatch {itg['replay_scores_mismatch']}, split_ok {itg['split_ok']}/"
          f"{cat['n_games']}")
    if itg["replay_scores_mismatch"] or itg["split_failed"]:
        print("[corpus_stats] WARNING: integrity failures present — see per_game rows")


if __name__ == "__main__":
    os.nice(19)
    main()
