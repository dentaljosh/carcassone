#!/usr/bin/env python3
"""Phase-5 analyzer, slice 1b: diff ONE E4 human-vs-champion game against a corpus.

    scripts/analyzer/e4_diff.py measurement/e4_games/XXXX.json \
        --corpus measurement/analyzer_20260802/CORPUS_STATS_champ449.json \
        -o measurement/analyzer_20260802

Reads an Android archive (`carcassonne-android-archive/v1`), replays it with the
same pure-replay machinery `corpus_stats` used, and answers three questions:

1. **Where does each seat sit in the corpus distribution?** Percentile rank of
   every seat scalar against the corpus's pooled champion-seat sample, with a
   flag when it falls outside p5..p95.
2. **How do the two seats in THIS game differ?** The within-game human-vs-champion
   split. This is the *paired* comparison — same board, same deck, same tiles — so
   it is immune to tile luck in a way the corpus percentile is not.
3. **The three biggest divergences, in plain language.**

⚠️ Two confounds are stated in every report rather than corrected for:

* **Opponent conditioning.** The corpus is champion-vs-champion. An E4 human seat
  is playing *against* a champion, and the champion seat in an E4 game is playing
  *against a human* — so neither E4 seat is drawn from the corpus's population.
  A champion-seat percentile that looks extreme may be measuring the opponent.
  The within-game split (question 2) is the robust half of this report.
* **Grading epoch.** Archives before the 2026-08-01 build play the k4×688 mobile
  carve-out on the walled grid with a random start tile; later ones carry
  `start_rule`/`grid_rule`/full k8×1376. The fields are echoed in the header;
  a corpus at a different budget is a different reference.
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "measurement_infra"))

SCHEMA = "carcassonne-analyzer-e4-diff/v1"

# Stats where the plain-language layer knows which direction is "more".
# (key, human-readable phrase, higher_is: what a high value means)
NARRATIVE = {
    "stranding_rate_nonfarmer": ("meeple stranding rate", "more meeples left out to dry"),
    "meeple_turns_locked": ("meeple-turns locked in stranded meeples", "more dead capital"),
    "first_farm_turn": ("turn of the first farmer", "farms claimed later"),
    "n_farmers_placed": ("farmers played", "more farm investment"),
    "farm_pts": ("farm points", "more of the score came from fields"),
    "farm_pts_frac": ("share of score from farms", "score leans on farms"),
    "during_play_frac": ("share of score banked during play", "score came from closures"),
    "during_play": ("points banked during play", "more closed features"),
    "incomplete_pts": ("points from unfinished features at the end", "more left open"),
    "deploy_rate": ("fraction of turns that placed a meeple", "deploys more often"),
    "mean_meeples_in_hand": ("mean meeples in hand", "holds meeples back"),
    "min_meeples_in_hand": ("lowest meeple supply reached", "never ran dry"),
    "n_features_won": ("features won", "won more features"),
    "mean_city_size_won": ("mean size of cities won", "bigger cities"),
    "mean_road_size_won": ("mean size of roads won", "longer roads"),
    "pts_per_meeple_placed": ("points per meeple placed", "each meeple earned more"),
    "n_meeples_placed": ("meeples placed", "more deployments"),
    "final_score": ("final score", "won by more"),
    "farm_pts_per_farmer": ("farm points per farmer", "each farmer paid more"),
    "n_farmers_early": ("farmers placed early (k>=48)", "early field claims"),
    "n_farmers_mid": ("farmers placed mid-game (24<=k<48)", "mid-game farm wars"),
    "n_farmers_late": ("farmers placed late (k<24)", "endgame field grabs"),
}

# Fields excluded from the divergence ranking: structural counts that are equal
# by construction between the two seats of one game, or per-phase turn counts.
_SKIP = {"n_turns"}


def percentile_rank(sample_sorted, x):
    """Fraction of the corpus sample at or below x, in [0, 1]."""
    if not sample_sorted or x is None:
        return None
    lo = bisect.bisect_left(sample_sorted, x)
    hi = bisect.bisect_right(sample_sorted, x)
    return (lo + hi) / (2.0 * len(sample_sorted))


def load_e4(path):
    """An Android archive -> the fields the replay needs, plus grading provenance."""
    a = json.loads(Path(path).read_text())
    if a.get("schema") not in (None, "carcassonne-android-archive/v1"):
        print(f"[e4_diff] WARNING: unexpected schema {a.get('schema')!r}")
    return {
        "path": str(path),
        "deck_seed": int(a["deck_seed"]),
        "actions": [int(x) for x in a["actions"]],
        "human_player": int(a.get("human_player", 0)),
        "recorded_scores": [int(x) for x in a.get("scores", [])] or None,
        "recorded_breakdown": (a.get("result") or {}).get("breakdown"),
        "provenance": {k: a.get(k) for k in
                       ("champion_id", "leaf_hash", "sims_effective", "k_dets_effective",
                        "opponent", "opponent_name", "finished_at", "start_rule",
                        "grid_rule", "budget_note", "verify")},
        "result": a.get("result"),
    }


def build_report(e4, cat, out_name):
    from replay_stats import replay_game_stats, game_scalars, seat_scalars, tercile

    st = replay_game_stats(e4["deck_seed"], e4["actions"],
                           recorded_scores=e4["recorded_scores"],
                           game_id=out_name)
    hp = e4["human_player"]
    cp = 1 - hp
    seats = {"human": seat_scalars(st, hp), "champion": seat_scalars(st, cp)}
    gsc = game_scalars(st)

    # Corpus samples, sorted once per key.
    corpus_seats = cat["per_seat"]
    samples = {}
    for k in seats["human"]:
        vals = sorted(s[k] for s in corpus_seats
                      if isinstance(s.get(k), (int, float)))
        if vals:
            samples[k] = vals

    rows = []
    for k in sorted(seats["human"]):
        if k in _SKIP or k not in samples:
            continue
        h, c = seats["human"][k], seats["champion"][k]
        if not isinstance(h, (int, float)) and not isinstance(c, (int, float)):
            continue
        d = cat["seat_dist"].get(k) or {}
        rows.append({
            "stat": k,
            "human": h, "champion": c,
            "delta_human_minus_champ": (h - c) if (isinstance(h, (int, float))
                                                   and isinstance(c, (int, float))) else None,
            "human_pct": percentile_rank(samples[k], h),
            "champion_pct": percentile_rank(samples[k], c),
            "corpus_mean": d.get("mean"), "corpus_sd": d.get("sd"),
            "corpus_p5": d.get("p5"), "corpus_p95": d.get("p95"),
            "human_z": ((h - d["mean"]) / d["sd"]
                        if isinstance(h, (int, float)) and d.get("sd") else None),
            "champion_z": ((c - d["mean"]) / d["sd"]
                           if isinstance(c, (int, float)) and d.get("sd") else None),
            "human_outside_p5_p95": (
                bool(isinstance(h, (int, float)) and d.get("p5") is not None
                     and (h < d["p5"] or h > d["p95"]))),
        })

    # Divergence ranking: |z| of the HUMAN seat against the champion-seat corpus,
    # restricted to stats the narrative layer can phrase, so the headline is
    # always readable. Ties broken by the within-game gap in sd units.
    narrated = [r for r in rows if r["stat"] in NARRATIVE and r["human_z"] is not None]
    narrated.sort(key=lambda r: -abs(r["human_z"]))
    top = narrated[:3]

    lines = []
    for r in top:
        name, high_means = NARRATIVE[r["stat"]]
        z = r["human_z"]
        direction = "ABOVE" if z > 0 else "BELOW"
        pct = r["human_pct"] * 100
        gap = r["delta_human_minus_champ"]
        gapstr = ""
        if gap is not None and r["corpus_sd"]:
            gapstr = (f" In THIS game the human seat is {gap:+.3g} vs the champion "
                      f"seat's {r['champion']:.3g} ({gap / r['corpus_sd']:+.1f} sd).")
        lines.append(
            f"**{name}** — human {r['human']:.3g} vs corpus mean {r['corpus_mean']:.3g} "
            f"({z:+.1f} sd, {direction} the champion corpus, {pct:.0f}th percentile). "
            f"High = {high_means}.{gapstr}")

    return {
        "schema": SCHEMA,
        "e4_path": e4["path"],
        "corpus_label": cat["label"],
        "corpus_path": cat["corpus_path"],
        "corpus_note": cat["corpus_note"],
        "corpus_n_seats": cat["n_seats"],
        "provenance": e4["provenance"],
        "human_player": hp,
        "replay_scores_match": st.replay_scores_match,
        "split_ok": st.split_ok,
        "final_scores": st.final_scores,
        "recorded_scores": e4["recorded_scores"],
        "recorded_breakdown": e4["recorded_breakdown"],
        "replayed_score_flow": st.score_flow,
        "game_scalars": gsc,
        "seat_scalars": seats,
        "rows": rows,
        "top_divergences": lines,
        "completions": [{k: v for k, v in c.items() if k != "returned_keys"}
                        for c in st.completions],
        "meeples": st.meeples,
        "confounds": [
            "The corpus is champion-vs-champion; neither E4 seat is drawn from that "
            "population (the human faces a champion, the champion faces a human). "
            "Percentiles are descriptive, not a test.",
            "Grading epoch: check provenance.sims_effective / k_dets_effective / "
            "start_rule / grid_rule against the corpus's source_meta before reading "
            "the champion seat's percentiles as a budget statement.",
        ],
    }


def to_markdown(rep, cat):
    L = []
    A = L.append
    p = rep["provenance"]
    A(f"# E4 diff — `{Path(rep['e4_path']).name}`")
    A("")
    A(f"**Corpus reference:** `{rep['corpus_label']}` "
      f"({rep['corpus_n_seats']} champion seats) — {rep['corpus_note']}  ")
    A(f"**This game:** human = seat {rep['human_player']} · "
      f"final {rep['final_scores']} (recorded {rep['recorded_scores']}, "
      f"replay match `{rep['replay_scores_match']}`) · score split reconciles "
      f"`{rep['split_ok']}`  ")
    A(f"**Grading epoch:** champion `{p.get('champion_id')}` · "
      f"budget k{p.get('k_dets_effective')}×{p.get('sims_effective')} · "
      f"start_rule `{p.get('start_rule')}` · grid_rule `{p.get('grid_rule')}` "
      f"(`None` = pre-2026-08-01 build: walled grid, random start)")
    A("")
    A("## The three biggest divergences")
    A("")
    for i, l in enumerate(rep["top_divergences"], 1):
        A(f"{i}. {l}")
    A("")
    A("## Read this first")
    A("")
    for c in rep["confounds"]:
        A(f"- {c}")
    A("")

    A("## Score flow, this game")
    A("")
    A("| seat | during play | unfinished | farms | total |")
    A("|---|---:|---:|---:|---:|")
    for lbl, idx in (("human", rep["human_player"]),
                     ("champion", 1 - rep["human_player"])):
        f = rep["replayed_score_flow"][idx]
        A(f"| {lbl} (seat {idx}) | {f['during_play']} | {f['incomplete']} | "
          f"{f['farms']} | {f['total']} |")
    cm = rep["corpus_note"]
    d = cat["score_flow_dist"]
    A(f"| *corpus mean* | {d['during_play']['mean']:.1f} | "
      f"{d['incomplete_pts']['mean']:.1f} | {d['farm_pts']['mean']:.1f} | "
      f"{d['final_score']['mean']:.1f} |")
    A("")

    A("## Every stat: this game vs the champion corpus")
    A("")
    A("`pct` = percentile within the pooled champion-seat sample. "
      "`!` marks a human value outside p5..p95.")
    A("")
    A("| stat | human | pct | champion | pct | Δ h−c | corpus mean | p5 | p95 | |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|:--|")
    def fmt(x):
        if x is None:
            return "—"
        return f"{x:.3g}" if isinstance(x, float) else str(x)
    for r in sorted(rep["rows"], key=lambda r: (r["stat"].startswith(("kband", "tercile")),
                                                r["stat"])):
        A(f"| {r['stat']} | {fmt(r['human'])} | "
          f"{('%.0f' % (r['human_pct']*100)) if r['human_pct'] is not None else '—'} | "
          f"{fmt(r['champion'])} | "
          f"{('%.0f' % (r['champion_pct']*100)) if r['champion_pct'] is not None else '—'} | "
          f"{fmt(r['delta_human_minus_champ'])} | {fmt(r['corpus_mean'])} | "
          f"{fmt(r['corpus_p5'])} | {fmt(r['corpus_p95'])} | "
          f"{'!' if r['human_outside_p5_p95'] else ''} |")
    A("")

    A("## Meeple ledger, this game")
    A("")
    A("| seat | terrain | placed turn | returned turn | locked turns | pts | stranded |")
    A("|---|---|---:|---:|---:|---:|:--|")
    for m in sorted(rep["meeples"], key=lambda m: (m["player"], m["place_turn"])):
        who = "human" if m["player"] == rep["human_player"] else "champion"
        A(f"| {who} | {m['terrain']} | {m['place_turn']} | "
          f"{m['return_turn'] if m['return_turn'] is not None else '—'} | "
          f"{m['locked_turns']} | {m['points_earned']} | "
          f"{'YES' if m['stranded'] else ''} |")
    A("")

    A("## Features closed during play")
    A("")
    A("| turn | k left | feature | size | pts | winner |")
    A("|---:|---:|---|---:|---:|---|")
    for c in rep["completions"]:
        w = ("nobody" if not c["winners"] else
             "/".join("human" if x == rep["human_player"] else "champion"
                      for x in c["winners"]))
        A(f"| {c['turn']} | {c['k_remaining']} | {c['terrain']} | {c['size']} | "
          f"{c['points']} | {w} |")
    A("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archive", help="an E4 phone archive json")
    ap.add_argument("--corpus", required=True, help="CORPUS_STATS_*.json")
    ap.add_argument("-o", "--out-dir", required=True)
    ap.add_argument("--name", default=None, help="output basename (default: archive stem)")
    args = ap.parse_args()

    cat = json.loads(Path(args.corpus).read_text())
    e4 = load_e4(args.archive)
    name = args.name or Path(args.archive).stem
    rep = build_report(e4, cat, name)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"E4_DIFF_{name}_vs_{cat['label']}"
    (out / f"{stem}.json").write_text(json.dumps(rep, indent=1))
    (out / f"{stem}.md").write_text(to_markdown(rep, cat))
    print(f"[e4_diff] wrote {out/stem}.json / .md")
    print(f"[e4_diff] replay match={rep['replay_scores_match']} "
          f"split_ok={rep['split_ok']} scores={rep['final_scores']}")
    for l in rep["top_divergences"]:
        print("  - " + l.replace("**", ""))


if __name__ == "__main__":
    os.nice(19)
    main()
