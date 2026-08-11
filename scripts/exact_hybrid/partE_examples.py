#!/usr/bin/env python3
"""Part E — endgame mechanism examples (solver-grounded, NO re-solve).

Uses the Part B regret output directly: the K=2 positions where RoD1 plays a SUBOPTIMAL
move (the leaks the exact tail fixes). The exact optimal move is recovered for free from
h3200 whenever h3200 itself is optimal (~83% of cases, per Part B); the rest are flagged
"both-suboptimal". Reconstruction is a fast replay (no solve) to decode move TYPES + the
board context (phase, meeples, scores). Coarse mechanism label from the move-type pair.

  python scripts/exact_hybrid/partE_examples.py --regret-dir <partb_regret/rod1> --topn 40
"""
from __future__ import annotations
import os
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_MEEPLE_K", "2.0")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse, csv, json, math, sys
from collections import Counter
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

from gen_endgame_positions import replay_to
from gen_endgame_multisource import replay_actions
from carcassonne_ai import action_space as A


def W_from_mask(L: int) -> int:
    # action_size(W) = W*W*4 + 11  ->  W = sqrt((L-11)/4)
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


def mechanism(rod_t, ex_t):
    if ex_t == "UNKNOWN":
        return "both-suboptimal (exact differs from both; needs solve)"
    if rod_t == "meeple_PASS" and ex_t.startswith("meeple"):
        return "under-deployment (RoD1 passes a meeple; exact places one)"
    if rod_t.startswith("meeple") and ex_t == "meeple_PASS":
        return "over-commit (RoD1 places a meeple; exact passes)"
    if "FARMER" in rod_t and "FARMER" not in ex_t:
        return "late farmer over-commit (RoD1 claims a field; exact does not)"
    if "FARMER" in ex_t and "FARMER" not in rod_t:
        return "missed farm claim (exact takes a field; RoD1 does not)"
    if "cloister" in ex_t or "cloister" in rod_t:
        return "cloister timing"
    if rod_t == "tile_place" and ex_t == "tile_place":
        return "last-tile placement / scoring-conversion (different placement)"
    if rod_t.startswith("meeple") and ex_t.startswith("meeple") and rod_t != ex_t:
        return "meeple-target (same phase, different feature)"
    return f"other ({rod_t} vs {ex_t})"


def reconstruct(rec):
    if rec.get("actions") is not None:
        return replay_actions(rec["seed"], rec["actions"])
    return replay_to(rec["seed"], rec["ply"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--regret-dir", required=True)
    ap.add_argument("--suite", default=str(REPO / "measurement/level2/l23_positions.jsonl"))
    ap.add_argument("--topn", type=int, default=40)
    ap.add_argument("--out", default=str(REPO / "measurement/exact_endgame_hybrid/partE_examples"))
    args = ap.parse_args(argv)

    suite = {json.loads(l)["gen_id"]: json.loads(l) for l in open(args.suite)}

    cands = []
    for p in sorted(Path(args.regret_dir).glob("*_k2.json")):
        try:
            d = json.load(open(p))
        except Exception:
            continue
        gt = d.get("gt", {}).get("clairvoyant") or d.get("gt", {}).get("marginalized")
        if not gt or not gt.get("solved"):
            continue
        pa = gt.get("per_agent", {})
        rod, h = pa.get("iter8", {}), pa.get("heur@3200", {})
        if rod.get("regret") is None or rod.get("match", True):
            continue
        cands.append((float(rod["regret"]), d, rod, h))
    cands.sort(key=lambda x: -x[0])
    cands = cands[: args.topn]

    rows = []
    for regret, d, rod, h in cands:
        rec = suite.get(d["gen_id"])
        if rec is None:
            continue
        game, board = reconstruct(rec)
        mask = game.get_valid_moves(board)
        W = W_from_mask(len(mask))
        h_optimal = bool(h.get("match"))
        rod_t = classify(d.get("moves", {}).get("iter8"), W)
        h_t = classify(d.get("moves", {}).get("heur@3200"), W)
        ex_t = h_t if h_optimal else "UNKNOWN"
        mover = board.state.current_player
        sc = d.get("scores") or list(board.state.scores)
        rows.append(dict(
            seed=d["seed"], ply=d["ply"], k=d["k_remaining"], phase=board.state.phase.name,
            score_self=sc[mover], score_opp=sc[1 - mover],
            meeples_self=int(board.state.meeples[mover]), legal_n=d.get("legal_n"),
            rod1_move=rod_t, h3200_move=h_t, exact_move=ex_t,
            rod1_regret=round(regret, 2), h3200_optimal=h_optimal,
            value_spread=gt_get(d, "value_spread"),
            mechanism=mechanism(rod_t, ex_t)))

    outd = Path(args.out)
    outd.parent.mkdir(parents=True, exist_ok=True)
    cols = list(rows[0].keys()) if rows else []
    with open(str(outd) + ".csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in rows:
            w.writerow(r)
    mh = Counter(r["mechanism"] for r in rows)
    h_opt = sum(1 for r in rows if r["h3200_optimal"])
    L = [f"# Part E — endgame mechanism examples (top {len(rows)} RoD1-suboptimal K=2 positions)", "",
         "Solver-grounded (Part B regret): positions where RoD1 plays a SUBOPTIMAL endgame move.",
         "'rod1_regret' = points RoD1 loses vs exact; exact_move = h3200's move where h3200 is",
         "optimal (the common case), else UNKNOWN. Move types are coarse (action-range decode).", "",
         "## Mechanism histogram"]
    for m, c in mh.most_common():
        L.append(f"- {c:>3}  {m}")
    L += ["", f"## h3200 already-optimal on these RoD1 mistakes: **{h_opt}/{len(rows)} "
          f"({100*h_opt/max(len(rows),1):.0f}%)** — i.e. the deep heuristic ALREADY makes the fix",
          "the exact solver would; exact play and h3200 mostly agree on how to repair RoD1's leak.", "",
          "## Top examples (by RoD1 regret)",
          "seed | ply | k | phase | self-opp | meep | legal | RoD1 | h3200 | exact | regret | h3200_opt | mechanism",
          "--- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---"]
    for r in rows[:25]:
        L.append(f"{r['seed']} | {r['ply']} | {r['k']} | {r['phase']} | {r['score_self']}-{r['score_opp']} | "
                 f"{r['meeples_self']} | {r['legal_n']} | {r['rod1_move']} | {r['h3200_move']} | {r['exact_move']} | "
                 f"{r['rod1_regret']} | {r['h3200_optimal']} | {r['mechanism']}")
    open(str(outd) + "_digest.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n[written] {outd}.csv  +  {outd}_digest.md")
    return 0


def gt_get(d, key):
    gt = d.get("gt", {}).get("clairvoyant") or d.get("gt", {}).get("marginalized") or {}
    return (gt.get("difficulty") or {}).get(key)


if __name__ == "__main__":
    raise SystemExit(main())
