#!/usr/bin/env python3
"""Part E — endgame mechanism examples (solver-grounded).

Sources the K=2 endgame positions where RoD1 plays SUBOPTIMALLY (the costly mistakes
the exact tail fixes). For the top-N by RoD1 regret, re-solve to get the exact optimal
move + child-value spread, decode RoD1 / h3200 / exact moves into readable types, and
attach a COARSE mechanism label (move-type + scoring context). This is the controlled,
solver-truth version of "what does exact play do that RoD1/h3200 do not".

  python scripts/exact_hybrid/partE_examples.py --regret-dir <partb_regret/rod1> \
      --topn 40 --out measurement/exact_endgame_hybrid/partE_examples
"""
from __future__ import annotations
import os
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("CARCASSONNE_V25_MEEPLE_K", "2.0")   # score the v2.8 agents
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse, csv, json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

import endgame_solver as S
from gen_endgame_positions import replay_to
from gen_endgame_multisource import replay_actions
from carcassonne_ai import action_space as A
from wingedsheep.carcassonne.objects.game_phase import GamePhase


def classify(idx: int, W: int) -> str:
    """Coarse move-type label from the action index."""
    if idx == A.tile_pass_index(W):
        return "tile_PASS"
    if idx < A.tile_pass_index(W):
        return "tile_place"
    nb = A.meeple_normal_base(W)
    fb = A.meeple_farmer_base(W)
    pb = A.meeple_pass_index(W)
    if idx == pb:
        return "meeple_PASS"
    if nb <= idx < fb:
        side = A.NORMAL_SIDES[idx - nb].name
        return f"meeple_{'cloister' if side == 'CENTER' else 'normal_' + side}"
    if fb <= idx < pb:
        return f"meeple_FARMER_{A.FARMER_SIDES[idx - fb].name}"
    return f"idx{idx}"


def mechanism(rod_type, exact_type, regret, k):
    """Coarse mechanism label for RoD1's mistake vs exact (move-type heuristic)."""
    if rod_type == "meeple_PASS" and exact_type.startswith("meeple"):
        return "under-deployment (wasted meeple — RoD1 passes, exact places)"
    if rod_type.startswith("meeple") and exact_type == "meeple_PASS":
        return "over-commit (RoD1 places a meeple exact judges wasteful)"
    if "FARMER" in rod_type and "FARMER" not in exact_type:
        return "late farmer over-commit (RoD1 claims a field, exact does not)"
    if "FARMER" in exact_type and "FARMER" not in rod_type:
        return "missed farm claim (exact takes a field, RoD1 does not)"
    if rod_type == "tile_place" and exact_type == "tile_place":
        return "tile-placement / scoring-conversion (different last-tile placement)"
    if "cloister" in exact_type or "cloister" in rod_type:
        return "cloister timing"
    return f"other ({rod_type} vs {exact_type})"


def reconstruct(rec):
    if rec.get("actions") is not None:
        return replay_actions(rec["seed"], rec["actions"])
    return replay_to(rec["seed"], rec["ply"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--regret-dir", required=True, help="partb_regret/rod1 (has iter8=RoD1 moves)")
    ap.add_argument("--suite", default=str(REPO / "measurement/level2/l23_positions.jsonl"))
    ap.add_argument("--topn", type=int, default=40)
    ap.add_argument("--budget", type=int, default=2_000_000)
    ap.add_argument("--out", default=str(REPO / "measurement/exact_endgame_hybrid/partE_examples"))
    args = ap.parse_args(argv)

    # index the suite by gen_id for reconstruction
    suite = {}
    for line in open(args.suite):
        r = json.loads(line)
        suite[r["gen_id"]] = r

    # collect RoD1-suboptimal K=2 positions from the regret output, sorted by regret
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
        rod = pa.get("iter8", {})       # iter8 key == the loaded net == RoD1 in this dir
        if rod.get("regret") is None or rod.get("match", True):
            continue                    # only RoD1-suboptimal (the fixable mistakes)
        cands.append((float(rod["regret"]), d))
    cands.sort(key=lambda x: -x[0])
    cands = cands[: args.topn]

    rows = []
    for regret, d in cands:
        gen_id = d["gen_id"]
        rec = suite.get(gen_id)
        if rec is None:
            continue
        game, board = reconstruct(rec)
        W = board.state.board[0].__len__() if False else None  # window via action_space
        # window size from the game wrapper
        Wsz = game.window_size if hasattr(game, "window_size") else 25
        res = S.solve(game, board, mode="clairvoyant", budget=args.budget, alphabeta=True)
        exact = int(min(res.optimal_actions))
        moves = d.get("moves", {})
        rod_mv = moves.get("iter8"); h_mv = moves.get("heur@3200")
        rod_t = classify(int(rod_mv), Wsz) if rod_mv is not None and rod_mv >= 0 else "NA"
        h_t = classify(int(h_mv), Wsz) if h_mv is not None and h_mv >= 0 else "NA"
        ex_t = classify(exact, Wsz)
        phase = board.state.phase.name
        mover = board.state.current_player
        sc = d.get("scores") or list(board.state.scores)
        rows.append(dict(
            gen_id=gen_id, seed=d["seed"], ply=d["ply"], k=d["k_remaining"], phase=phase,
            to_move=mover, score_self=sc[mover], score_opp=sc[1 - mover],
            meeples_self=int(board.state.meeples[mover]), legal_n=d.get("legal_n"),
            rod1_move=rod_t, h3200_move=h_t, exact_move=ex_t,
            rod1_regret=round(regret, 2),
            h3200_optimal=bool(d["gt"].get("clairvoyant", {}).get("per_agent", {}).get("heur@3200", {}).get("match")),
            value_spread=d["gt"].get("clairvoyant", {}).get("difficulty", {}).get("value_spread"),
            mechanism=mechanism(rod_t, ex_t, regret, d["k_remaining"]),
        ))

    outd = Path(args.out)
    outd.parent.mkdir(parents=True, exist_ok=True)
    csvp = str(outd) + ".csv"
    cols = list(rows[0].keys()) if rows else []
    with open(csvp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in rows:
            w.writerow(r)
    # digest: mechanism histogram + the top examples
    from collections import Counter
    mh = Counter(r["mechanism"] for r in rows)
    L = [f"# Part E — endgame mechanism examples (top {len(rows)} RoD1-suboptimal K=2 positions)", "",
         "Solver-grounded: positions where RoD1 plays a SUBOPTIMAL endgame move (the mistakes the",
         "exact tail fixes). 'rod1_regret' = points RoD1 loses vs exact. 'h3200_optimal' = did the",
         "deep heuristic already play optimally here.", "",
         "## Mechanism histogram (coarse, move-type-based)"]
    for m, c in mh.most_common():
        L.append(f"- {c:>3}  {m}")
    h_opt = sum(1 for r in rows if r["h3200_optimal"])
    L += ["", f"## h3200 already-optimal on these RoD1-mistakes: {h_opt}/{len(rows)} "
          f"({100*h_opt/max(len(rows),1):.0f}%) — i.e. the deep heuristic mostly ALREADY makes the fix",
          "", "## Top examples (by RoD1 regret)",
          "seed | ply | k | phase | self-opp | meep | RoD1 | h3200 | exact | regret | h3200_opt | mechanism",
          "--- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---"]
    for r in rows[:25]:
        L.append(f"{r['seed']} | {r['ply']} | {r['k']} | {r['phase']} | {r['score_self']}-{r['score_opp']} | "
                 f"{r['meeples_self']} | {r['rod1_move']} | {r['h3200_move']} | {r['exact_move']} | "
                 f"{r['rod1_regret']} | {r['h3200_optimal']} | {r['mechanism']}")
    digestp = str(outd) + "_digest.md"
    open(digestp, "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n[written] {csvp}\n[written] {digestp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
