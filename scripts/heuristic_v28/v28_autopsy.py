#!/usr/bin/env python3
"""Mechanistic autopsy for the Phase-4 survivors (addendum requirement).

Operationalizes "why does v2.7 fail / does the patch fix a real structural class," separate
from Elo/agreement. For each survivor:
  - line autopsy: force the v2.7 pick and the patch pick; for the EXACT-solved K=2 endgame the
    "strong continuation" IS the solver, so the divergence = the regret difference at final scoring.
  - counterfactual: mutate the mechanism's driving condition (slack for completion; tiles/t0 for
    meeple) and check the preference changes AS PREDICTED.

v28_completion: endgame K=2 (exact) — deck-aware closure should flip picks toward optimal ONLY where
  the closure is deck-limited. Counterfactual = slack sweep {off,1,2,3,4}.
v28_meeple: midgame recovered cases — recovery scaling should depend on tiles_remaining.
  Counterfactual = t0 sweep {0, 36, 72, 10000}.

Out: measurement/heuristic_v28/V28_AUTOPSY_DATA.json (cases + counterfactuals; the .md is hand-written)
"""
from __future__ import annotations
import os, sys, json, random
import dataclasses as dc
from multiprocessing import get_context

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "heuristic_v28"))
sys.path.insert(0, os.path.join(REPO, "scripts", "level2"))
import v28_configs; v28_configs.set_prod_env()
import numpy as np
from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.virtual_score_v2 import virtual_score_v2, DEFAULT_CONFIG
from gen_endgame_positions import replay_to
from build_action_audit_dataset import _resolve_turn

END_DS = os.path.join(REPO, "measurement/pre_tool_audit/ACTION_AUDIT_DATASET.jsonl")
MID_POS = os.path.join(REPO, "measurement/midgame_reference/MIDGAME_POSITION_SAMPLE.jsonl")
MID_LAB = os.path.join(REPO, "measurement/midgame_reference/MIDGAME_REFERENCE_LABELS.jsonl")
OUT = os.path.join(REPO, "measurement/heuristic_v28/V28_AUTOPSY_DATA.json")

SLACKS = [0.0, 1.0, 2.0, 3.0, 4.0]          # 0 == v2.7 (off)
T0S = [0, 36, 72, 10000]


def _resolved_leaf(game, board, action, cfg):
    mover = board.state.current_player
    child, _ = game.get_next_state(board, int(action))
    ps, _ = _resolve_turn(game, child, mover)
    return virtual_score_v2(ps.state, mover, cfg), ps.state


def _argmax(game, board, cfg):
    mover = board.state.current_player
    legal = np.flatnonzero(game.get_valid_moves(board))
    ba, bv = None, None
    for a in legal:
        v, _ = _resolved_leaf(game, board, a, cfg)
        if bv is None or v > bv:
            bv, ba = v, int(a)
    return ba


def _end_worker(rec):
    try:
        g, b = replay_to(rec["source_game_seed"], rec["ply"])
        reg = {int(a["action"]): a["solver_regret_clair"] for a in rec["actions"]
               if a.get("solver_regret_clair") is not None}
        v27 = v28_configs.build_variants(["v27_baseline"])["v27_baseline"]
        # slack counterfactual: pick + regret at each slack
        sweep = {}
        for s in SLACKS:
            cfg = v27 if s == 0.0 else dc.replace(v27, closure_continuous_slack=s)
            a = _argmax(g, b, cfg)
            sweep[str(s)] = {"action": a, "regret": reg.get(a)}
        a27 = sweep["0.0"]["action"]
        a_comp = sweep["3.0"]["action"]
        detail = None
        if a27 != a_comp:
            comp_cfg = dc.replace(v27, closure_continuous_slack=3.0)
            v27_on_27, _ = _resolved_leaf(g, b, a27, v27)
            v27_on_comp, _ = _resolved_leaf(g, b, a_comp, v27)
            comp_on_27, _ = _resolved_leaf(g, b, a27, comp_cfg)
            comp_on_comp, _ = _resolved_leaf(g, b, a_comp, comp_cfg)
            detail = {
                "position_id": rec["position_id"], "k": rec["k_remaining"],
                "v27_pick": a27, "v27_pick_regret": reg.get(a27),
                "comp_pick": a_comp, "comp_pick_regret": reg.get(a_comp),
                "leaf_v27_on_v27pick": v27_on_27, "leaf_v27_on_comppick": v27_on_comp,
                "leaf_comp_on_v27pick": comp_on_27, "leaf_comp_on_comppick": comp_on_comp,
                "deck_size": len(b.state.deck),
            }
        return {"position_id": rec["position_id"], "sweep": sweep, "detail": detail}
    except Exception as e:
        return {"_error": f"{rec['position_id']}: {type(e).__name__}: {e}"}


def main():
    ctx = get_context("fork")
    end = [json.loads(l) for l in open(END_DS)
           if json.loads(l)["k_remaining"] == 2 and json.loads(l)["recon_ok"]]
    with ctx.Pool(14) as pool:
        res = [r for r in pool.imap_unordered(_end_worker, end, chunksize=4) if "_error" not in r]

    # slack counterfactual aggregate: top-1 (regret==0) at each slack
    slack_top1 = {}
    for s in SLACKS:
        regs = [r["sweep"][str(s)]["regret"] for r in res if r["sweep"][str(s)]["regret"] is not None]
        slack_top1[str(s)] = round(sum(1 for x in regs if x == 0.0) / len(regs), 4) if regs else None
    # flip accounting v2.7(slack0) vs completion(slack3)
    flips = [r["detail"] for r in res if r["detail"]]
    better = sum(1 for d in flips if d["comp_pick_regret"] is not None and d["v27_pick_regret"] is not None
                 and d["comp_pick_regret"] < d["v27_pick_regret"])
    worse = sum(1 for d in flips if d["comp_pick_regret"] is not None and d["v27_pick_regret"] is not None
                and d["comp_pick_regret"] > d["v27_pick_regret"])

    # ---- v28_meeple midgame recovered cases + t0 counterfactual ----
    labels = {json.loads(l)["position_id"]: json.loads(l) for l in open(MID_LAB)}
    positions = {json.loads(l)["position_id"]: json.loads(l) for l in open(MID_POS)}
    meeple_cases = []
    # recovered = v28_meeple pick == teacher but v27 pick != teacher
    for pid, lab in labels.items():
        if pid not in positions:
            continue
        pos = positions[pid]
        random.seed(pos["source_game_seed"])
        g = Game(enable_legal_moves_cache=True); b = g.get_init_board()
        for a in pos["prefix"]:
            b, _ = g.get_next_state(b, int(a))
        v27 = v28_configs.build_variants(["v27_baseline"])["v27_baseline"]
        v27_pick = _argmax_simple(g, b, v27)
        if v27_pick == lab["heur3200_choice"]:
            continue
        # t0 sweep with k=2.0
        sweep = {}
        for t0 in T0S:
            cfg = dc.replace(v27, v28_meeple_k=2.0, v28_meeple_recovery_t0=t0)
            sweep[str(t0)] = _argmax_simple(g, b, cfg)
        if any(sweep[str(t0)] == lab["heur3200_choice"] for t0 in T0S):
            meeple_cases.append({
                "position_id": pid, "band": pos["band"], "tiles_remaining": pos["tiles_remaining"],
                "teacher": lab["heur3200_choice"], "v27_pick": v27_pick,
                "t0_sweep": {k: v for k, v in sweep.items()},
                "recovered_at_t0": [t0 for t0 in T0S if sweep[str(t0)] == lab["heur3200_choice"]],
            })

    out = {
        "v28_completion_endgame": {
            "n_positions": len(res),
            "slack_counterfactual_top1": slack_top1,
            "flips_vs_v27": {"n": len(flips), "toward_optimal": better, "away": worse},
            "flip_cases": flips[:12],
        },
        "v28_meeple_midgame": {
            "n_recovered_cases": len(meeple_cases),
            "cases": meeple_cases[:12],
        },
    }
    json.dump(out, open(OUT, "w"), indent=2)
    print("=== v28_completion endgame K=2 ===")
    print("slack top-1 sweep (0=v2.7):", slack_top1)
    print(f"flips vs v2.7: n={len(flips)} toward_optimal={better} away={worse}")
    print("=== v28_meeple midgame ===")
    print(f"recovered cases: {len(meeple_cases)}")
    for c in meeple_cases[:6]:
        print(f"  {c['position_id']:28} band={c['band']:11} tiles={c['tiles_remaining']:3} "
              f"recovered_at_t0={c['recovered_at_t0']}")
    print(f"\nwrote -> {OUT}")


def _argmax_simple(game, board, cfg):
    mover = board.state.current_player
    legal = np.flatnonzero(game.get_valid_moves(board))
    ba, bv = None, None
    for a in legal:
        a = int(a)
        child, _ = game.get_next_state(board, a)
        v = virtual_score_v2(child.state, mover, cfg)
        if bv is None or v > bv:
            bv, ba = v, a
    return ba


if __name__ == "__main__":
    main()
