"""F3 §2–4 — the PIMC-vs-exact-oracle comparison harness (the deliverable script).

For each mined root, at MATCHED production root budget (k4x688):
  1. reconstruct + checksum-verify the board (greedy replay_to or champion replay_actions);
  2. solve(mode="marginalized") -> exact child_values / V* / optimal set (BudgetExceeded
     -> completed=False, reported as coverage);
  3. capture the k4x688 PIMC once (per-world matrix) -> the four selectors (§3.1);
  4. score every selector's regret vs the exact optimum + top-action agreement + coverage;
  5. localize strategy fusion: Phi(pooled-Q pick) via cross-world continuation replay (§3.3);
  6. persist ONE self-describing Candidate-4 record per root (§4): exact labels + PIMC
     observables + residual targets + features. RESUMABLE (skip roots already written).

Pure CPU, net-free. Fork pool across roots; per-root marginalized solve is single-thread.
RAM is the binding constraint (§5.3/§5.4): CARCASSONNE_TT_CAP set, per-root node budget,
W <= RAM/~2GB. A budget-hit root is recorded completed=False and counts as missing coverage
(a KILL verdict is invalid if coverage is low — analyze.py enforces this).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import env_preamble  # noqa: E402,F401  (production leaf env before carcassonne_ai)

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

import argparse  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402

import numpy as np  # noqa: E402

import endgame_solver as S  # noqa: E402
import gen_endgame_positions as GEP  # noqa: E402
import root_replay as RR  # noqa: E402
from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai import sighted_planes as SP  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import make_heuristic_prior_evaluator  # noqa: E402

import pimc_capture as PC  # noqa: E402
import fusion as FU  # noqa: E402

# fork-inherited worker context (a module-level dict; set in main before the pool).
_CTX: dict = {}


def _root_id(rec: dict) -> str:
    if "game_id" in rec:
        return f"g{rec['game_id']}_p{rec['ply']}"
    return f"s{rec['seed']}_p{rec['ply']}"


def _reconstruct(rec: dict):
    """(game, board) from a provenance record — champion (actions) or greedy (seed,ply)."""
    if "actions" in rec:
        return RR.replay_actions(int(rec["deck_seed"]), rec["actions"], int(rec["ply"]))
    return GEP.replay_to(int(rec["seed"]), int(rec["ply"]))


def _mover_pov(v: float, to_move: int) -> float:
    """P0-perspective solver value -> mover perspective (higher = better for mover)."""
    return v if to_move == 0 else -v


def score_root(rec: dict) -> dict:
    cfg = _CTX["cfg"]
    budget = _CTX["budget"]
    k_dets = _CTX["k_dets"]
    sims = _CTX["sims"]
    agent_seed = _CTX["agent_seed"]
    decided_eps = _CTX["decided_eps"]
    fusion_thresh = _CTX["fusion_thresh"]

    rid = _root_id(rec)
    try:
        game, board = _reconstruct(rec)
    except Exception as e:  # noqa
        return {"root_id": rid, "_error": f"recon {type(e).__name__}: {e}"}
    if game.string_representation(board) != rec["checksum"]:
        return {"root_id": rid, "_error": "checksum_mismatch"}

    to_move = int(board.state.current_player)
    legal = np.flatnonzero(game.get_valid_moves(board)).astype(int).tolist()
    if len(legal) < 2:
        return {"root_id": rid, "_skip": "<2 legal"}

    # --- 2. exact marginalized solve --------------------------------------------
    t0 = time.perf_counter()
    completed = True
    try:
        res = S.solve(game, board, mode="marginalized", budget=budget, alphabeta=False)
    except S.BudgetExceeded:
        return {"root_id": rid, "completed": False, "k_remaining": rec["k_remaining"],
                "solve_secs": round(time.perf_counter() - t0, 2), "budget": budget,
                "note": "budget_hit (counts as missing coverage)"}
    solve_secs = time.perf_counter() - t0
    cv = {int(a): float(v) for a, v in res.child_values.items()}
    vstar = float(res.value)
    optimal = [int(a) for a in res.optimal_actions]
    mover_vals = {a: _mover_pov(v, to_move) for a, v in cv.items()}
    spread = max(mover_vals.values()) - min(mover_vals.values())
    decided = bool(spread < decided_eps)

    # --- 3. capture the k4x688 PIMC once (per-world matrix) ----------------------
    evaluator = make_heuristic_prior_evaluator(game, cfg)
    cap = PC.capture_pimc(game, board, cfg, evaluator, k_dets=k_dets, sims=sims,
                          seed=agent_seed, move_idx=int(rec["ply"]),
                          keep_policy=True)
    picks = PC.all_picks(cap)

    # --- 4. score every selector vs the exact optimum ---------------------------
    def _reg(a):
        return float(S.regret_of(res, int(a))) if a in cv else None
    selectors = {}
    for name, a in picks.items():
        selectors[name] = {
            "pick": int(a),
            "regret": _reg(a),
            "in_optimal": bool(a in optimal),
            "coverage": int(cap.coverage.get(a, 0)),
        }
    # coverage of the exact-best action (is the right move systematically under-covered?)
    best_cov = max((cap.coverage.get(a, 0) for a in optimal), default=0)

    # --- 5. localize strategy fusion on the pooled-Q pick -----------------------
    pq = picks["pooled_q"]
    try:
        fus = FU.engine_fusion_premium(cap, pq, game, aggregator="mean")
        fus_min = FU.engine_fusion_premium(cap, pq, game, aggregator="min")["phi"]
        phi = fus["phi"]
        fusion_flag = FU.flag_fusion(phi, pq, pq, optimal, threshold=fusion_thresh)
    except Exception as e:  # noqa - fusion is a diagnostic; never lose the root over it
        fus = {"phi": None, "_error": f"{type(e).__name__}: {e}"}
        fus_min, phi, fusion_flag = None, None, False
    coverage_flag = bool(cap.coverage.get(pq, 0) <= 1)

    # --- 6. Candidate-4 labels: residual target + features (§4) ------------------
    leaf_cfg = cfg.leaf_cfg
    residual = {}
    leaf_p0 = {}
    for a in legal:
        child, _ = game.get_next_state(board, int(a))
        lv = float(flat_leaf.flat_virtual_score_v2_float(child.state, 0, leaf_cfg))
        leaf_p0[a] = lv
        if a in cv:
            residual[a] = cv[a] - lv       # exact - leaf, P0-POV points
    bag_hist = SP.bag_histogram(board.state).astype(float).tolist()

    # per-world matrix serialized {action: [N, Q]}
    worlds_ser = [{int(a): [int(N), float(Q)] for a, (N, Q) in w.matrix.items()}
                  for w in cap.worlds]

    return {
        "root_id": rid,
        "completed": True,
        "decided": decided,
        # identity / provenance
        "source_agent": rec.get("source_agent"),
        "seed": rec.get("seed"), "game_id": rec.get("game_id"),
        "deck_seed": rec.get("deck_seed"), "ply": int(rec["ply"]),
        "checksum": rec["checksum"], "k_remaining": int(rec["k_remaining"]),
        "to_move": to_move, "bag_multiset": rec["bag_multiset"],
        "bag_size": int(rec["bag_size"]), "in_hand_tile": rec.get("in_hand_tile"),
        "known_order": rec.get("known_order"), "strata": rec.get("strata"),
        "top2_q_gap": rec.get("top2_q_gap"),
        "budget": budget, "nodes": int(res.nodes), "solve_secs": round(solve_secs, 3),
        "legal_n": len(legal), "value_spread_mover": round(float(spread), 4),
        # exact labels
        "vstar": vstar, "optimal_actions": optimal,
        "child_values": {int(a): v for a, v in cv.items()},
        # PIMC observables
        "picks": selectors,
        "pooled_agg_n": {int(a): float(n) for a, n in cap.agg_n.items()},
        "pooled_agg_w": {int(a): float(w) for a, w in cap.agg_w.items()},
        "coverage": {int(a): int(c) for a, c in cap.coverage.items()},
        "exact_best_coverage": int(best_cov),
        "per_world_matrix": worlds_ser,
        "per_world_root_value": [float(w.root_value) for w in cap.worlds],
        # fusion attribution (§3.3)
        "fusion_phi_mean": (None if fus.get("phi") is None else float(fus["phi"])),
        "fusion_phi_min": (None if fus_min is None else float(fus_min)),
        "fusion_flag": bool(fusion_flag),
        "coverage_flag": coverage_flag,     # selection-bias mechanism (c(pick)<=1)
        # Candidate-4
        "leaf_value_p0": {int(a): v for a, v in leaf_p0.items()},
        "residual_target_p0": {int(a): v for a, v in residual.items()},
        "bag_histogram": bag_hist,
        "k_dets": k_dets, "sims_per_det": sims, "agent_seed": agent_seed,
    }


def _worker(rec_and_dir):
    rec, out_dir = rec_and_dir
    rid = _root_id(rec)
    dest = out_dir / f"{rid}.json"
    if dest.exists():
        return ("skip", rid)
    try:
        out = score_root(rec)
    except Exception as e:  # noqa - one bad root must not kill the suite
        out = {"root_id": rid, "_error": f"{type(e).__name__}: {e}",
               "traceback": traceback.format_exc()}
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out))
    tmp.rename(dest)      # atomic publish (resume-safe)
    status = "error" if "_error" in out else ("skip" if "_skip" in out else "ok")
    return (status, rid)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--roots", required=True, help="mined roots.jsonl (from mine_roots.py)")
    ap.add_argument("--out-dir", required=True, help="per-root record dir (resumable)")
    ap.add_argument("--budget", type=int, default=2_000_000, help="per-root solver node budget")
    ap.add_argument("--k-dets", type=int, default=4)
    ap.add_argument("--sims", type=int, default=688, help="sims per determinization (k4x688)")
    ap.add_argument("--agent-seed", type=int, default=101)
    ap.add_argument("--decided-eps", type=float, default=0.5,
                    help="mover-perspective child spread below this = effectively decided (§1.4b)")
    ap.add_argument("--fusion-thresh", type=float, default=FU.DEFAULT_FUSION_THRESHOLD)
    ap.add_argument("--workers", type=int, default=4, help="fork pool size (RAM-bound: W<=RAM/~2GB)")
    ap.add_argument("--tt-cap", type=int, default=None,
                    help="CARCASSONNE_TT_CAP override (freeze-at-cap; correctness-neutral)")
    ap.add_argument("--limit", type=int, default=None, help="only the first N roots (smoke)")
    args = ap.parse_args(argv)

    if args.tt_cap is not None:
        os.environ["CARCASSONNE_TT_CAP"] = str(args.tt_cap)

    with open(args.roots) as f:
        roots = [json.loads(l) for l in f if l.strip()]
    if args.limit:
        roots = roots[: args.limit]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Prove the production leaf ONCE (R1/R7-class guard) and share the cfg via fork.
    _cfg, _evaluator, manifest = PC.build_champion_eval(
        Game(enable_legal_moves_cache=True), verify=True)
    (out_dir / "champion_manifest.json").write_text(json.dumps(manifest, indent=2))

    _CTX.update(cfg=_cfg, budget=args.budget, k_dets=args.k_dets, sims=args.sims,
                agent_seed=args.agent_seed, decided_eps=args.decided_eps,
                fusion_thresh=args.fusion_thresh)

    # run manifest for the suite
    (out_dir / "suite_manifest.json").write_text(json.dumps({
        "roots_file": str(args.roots), "n_roots": len(roots),
        "budget": args.budget, "k_dets": args.k_dets, "sims_per_det": args.sims,
        "total_sims": args.k_dets * args.sims, "agent_seed": args.agent_seed,
        "decided_eps": args.decided_eps, "fusion_thresh": args.fusion_thresh,
        "tt_cap": os.environ.get("CARCASSONNE_TT_CAP", "0"),
        "champion_config_hash": manifest["search"]["config_hash"],
    }, indent=2))

    from multiprocessing import get_context
    ctx = get_context("fork")
    counts = {"ok": 0, "skip": 0, "error": 0}
    tasks = [(r, out_dir) for r in roots]
    t0 = time.perf_counter()
    with ctx.Pool(args.workers) as pool:
        for i, (status, rid) in enumerate(pool.imap_unordered(_worker, tasks, chunksize=1), 1):
            counts[status] = counts.get(status, 0) + 1
            if i % 10 == 0 or i == len(tasks):
                el = time.perf_counter() - t0
                print(f"  {i}/{len(tasks)}  ok={counts['ok']} skip={counts['skip']} "
                      f"err={counts['error']}  {el:.0f}s", flush=True)
    print(f"done: {counts}  ->  {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
