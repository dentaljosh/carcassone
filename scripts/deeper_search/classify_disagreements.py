#!/usr/bin/env python3
"""Part E — mechanism classification of deeper-search disagreements.

Reads the audit disagreements.csv (h12800/h6400 != h3200, convergence-flagged), reconstructs each
position (replay_to), decodes the MOVE TYPE of the shallow (h3200) choice vs the deep (h12800/h6400)
choice, and assigns a coarse mechanism class. Prioritises CONVERGED (stable) disagreements and
late_mid/pre_endgame. Produces a histogram + a representative-examples table for the report.

Mechanism classes (spec): meeple economy/reserve, premature meeple spend, profitable claim refusal,
city completion/race, road completion, cloister timing, farm commitment, farm denial, opponent
blocking, tempo, endgame conversion setup, score-now-vs-future, high-branching tactical, other.

  python scripts/deeper_search/classify_disagreements.py \
      measurement/deeper_search_ruler/root_audit/disagreements.csv \
      --out measurement/deeper_search_ruler/root_audit/partE
"""
from __future__ import annotations
import os
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_MEEPLE_K", "2.0")
os.environ.setdefault("OMP_NUM_THREADS", "1")
import argparse, csv, math, sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
from gen_endgame_positions import replay_to
from carcassonne_ai import action_space as A


def W_from_mask(L):
    return int(round(math.sqrt((L - 11) / 4)))


def classify(idx, W):
    if idx is None or idx < 0:
        return "NA"
    idx = int(idx)
    if idx == A.tile_pass_index(W):
        return "tile_PASS"
    if idx < A.tile_pass_index(W):
        return "tile_place"
    nb, fb, pb = A.meeple_normal_base(W), A.meeple_farmer_base(W), A.meeple_pass_index(W)
    if idx == pb:
        return "meeple_PASS"
    if nb <= idx < fb:
        s = A.NORMAL_SIDES[idx - nb].name
        return "meeple_cloister" if s == "CENTER" else f"meeple_{s}"
    if fb <= idx < pb:
        return f"meeple_FARMER_{A.FARMER_SIDES[idx - fb].name}"
    return f"idx{idx}"


def mechanism(sh, dp):
    """Coarse mechanism from the (shallow_type, deep_type) pair."""
    if "FARMER" in dp and "FARMER" not in sh:
        return "farm commitment (deep claims a field; shallow does not)"
    if "FARMER" in sh and "FARMER" not in dp:
        return "farm denial / refusal (shallow claims a field; deep does not)"
    if sh == "meeple_PASS" and dp.startswith("meeple"):
        return "profitable claim (deep places a meeple; shallow passes)"
    if sh.startswith("meeple") and dp == "meeple_PASS":
        return "premature-spend avoidance (deep passes; shallow places a meeple)"
    if "cloister" in dp or "cloister" in sh:
        return "cloister timing"
    if sh == "tile_place" and dp == "tile_place":
        return "tile placement (same phase, different square = blocking/conversion/tempo)"
    if sh.startswith("meeple") and dp.startswith("meeple") and sh != dp:
        return "meeple target (same phase, different feature = city/road/farm choice)"
    if sh == "tile_PASS" or dp == "tile_PASS":
        return "tile-pass (no legal placement / forced)"
    return f"other ({sh} vs {dp})"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("disagreements")
    ap.add_argument("--out", default="measurement/deeper_search_ruler/root_audit/partE")
    ap.add_argument("--converged-only", action="store_true", help="classify only stable (converged) ones")
    ap.add_argument("--topn", type=int, default=120)
    args = ap.parse_args(argv)
    rows = list(csv.DictReader(open(args.disagreements)))
    if args.converged_only:
        rows = [r for r in rows if r.get("converged_deep", "").lower() in ("true", "1")]
    rows = rows[: args.topn]
    deep_col = "h12800_chosen" if rows and rows[0].get("h12800_chosen") not in (None, "", "None") else "h6400_chosen"

    out_rows = []
    for r in rows:
        seed, ply = int(r["seed"]), int(r["ply"])
        game, board = replay_to(seed, ply)
        W = W_from_mask(len(game.get_valid_moves(board)))
        sh_t = classify(int(r["h3200_chosen"]), W) if r.get("h3200_chosen") not in (None, "", "None") else "NA"
        dp_raw = r.get(deep_col)
        dp_t = classify(int(dp_raw), W) if dp_raw not in (None, "", "None") else "NA"
        out_rows.append({
            "gen_id": r["gen_id"], "seed": seed, "ply": ply, "k": r["k_remaining"], "phase": r["phase"],
            "legal_n": r["legal_n"], "score_margin_abs": r["score_margin_abs"], "meeples_free": r.get("meeples_free"),
            "converged": r.get("converged_deep"), "h3200_move": sh_t, "deep_move": dp_t,
            "rod1_matches_deep": r.get("rod1_matches_deep"),
            "mechanism": mechanism(sh_t, dp_t),
            "affects_winloss_guess": "margin-only" if r["phase"] == "endgame" else "possible W/L",
        })
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with open(str(outp) + ".csv", "w", newline="") as f:
        if out_rows:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys())); w.writeheader()
            for r in out_rows:
                w.writerow(r)
    mh = Counter(r["mechanism"] for r in out_rows)
    L = [f"# Part E — mechanism classification ({len(out_rows)} deep-vs-h3200 disagreements"
         + (", converged-only" if args.converged_only else "") + ")", "",
         "## Mechanism histogram"]
    for m, c in mh.most_common():
        L.append(f"- {c:>3}  {m}")
    L += ["", "## By phase",
          "  " + "  ".join(f"{ph}:{sum(1 for r in out_rows if r['phase']==ph)}"
                           for ph in ["opening", "midgame", "late_mid", "pre_endgame", "endgame"]),
          "", "## Representative examples",
          "seed | ply | k | phase | legal | margin | h3200 | deep | conv | rod1==deep | mechanism",
          "--- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---"]
    for r in out_rows[:30]:
        L.append(f"{r['seed']} | {r['ply']} | {r['k']} | {r['phase']} | {r['legal_n']} | {r['score_margin_abs']} | "
                 f"{r['h3200_move']} | {r['deep_move']} | {r['converged']} | {r['rod1_matches_deep']} | {r['mechanism']}")
    (Path(str(outp) + "_digest.md")).write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n[written] {outp}.csv + {outp}_digest.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
