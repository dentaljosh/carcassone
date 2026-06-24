#!/usr/bin/env python3
"""Part D — root-action deeper-search audit.

For each position in the multi-phase suite, run each agent and harvest the ROOT
decision + search statistics, so we can ask: does deeper heuristic search (h6400/
h12800) produce STABLE new decisions vs h3200, or just search noise? And where do
the learned agents (RoD1) agree with the shallow ruler but not the deep one?

Agents (byte-identical to the eval agents via eval_hybrid_handoff constructors):
  h800 h1600 h3200 h6400 h12800  = HeuristicMCTS(sims=N, v2.8 leaf, meeple_k=2.0)
  rod1                           = iter8 NeuralMCTS (sims=200, c_puct=3, rs=0.25, v2.8)

Per (position, agent) we record: chosen action (= best_action, what it would PLAY),
top action visit-share, top-k (action,share), visit entropy (nats), visit concentration
(= top share), a root value estimate (best child Q in root perspective), legal_n.

Reconstruct each board with the canonical replay_to(seed, ply); verify vs the stored
checksum. Resumable: one JSON per position under <out>/pos/.

  python scripts/deeper_search/root_audit_deep.py \
      --positions measurement/deeper_search_ruler/multiphase_positions.jsonl \
      --agents h3200,h6400,h12800,rod1 --workers 16 \
      --ckpt /mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.pt \
      --out measurement/deeper_search_ruler/root_audit
"""
from __future__ import annotations
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
import argparse, json, math, sys
from pathlib import Path
from multiprocessing import get_context

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

# importing eval_hybrid_handoff sets the v2.7 base leaf env (CAP=12, FLAT_LEAF, ...)
import eval_hybrid_handoff as EH
from gen_endgame_positions import replay_to
from carcassonne_ai.mcts import HeuristicMCTS

_W = {}


def _heur_sims(name):
    return int(name[1:]) if name.startswith("h") and name[1:].isdigit() else None


def _harvest(mcts, board, game):
    """Run search at this root and harvest the decision + stats from the visit dict."""
    mcts.clear()
    visits = mcts.search(board)              # {action: N}
    chosen = mcts.best_action(board)         # reuses the tree; (Q,N) selection = what it plays
    tot = sum(visits.values()) or 1
    items = sorted(visits.items(), key=lambda kv: -kv[1])
    share = {a: n / tot for a, n in visits.items()}
    ent = -sum(p * math.log(p) for p in share.values() if p > 0)
    # root value estimate: chosen child's Q in the root's perspective
    val = None
    try:
        root = mcts._nodes.get(game.string_representation(board))
        if root is not None and chosen in root.children:
            c = root.children[chosen]
            val = float(c.Q if c.player_to_move == root.player_to_move else -c.Q)
    except Exception:
        pass
    return {
        "chosen": int(chosen),
        "chosen_share": round(float(share.get(chosen, 0.0)), 4),
        "top_share": round(float(items[0][1] / tot), 4),
        "entropy": round(float(ent), 4),
        "n_children": len(visits),
        "topk": [[int(a), round(n / tot, 4)] for a, n in items[:5]],
        "value": round(val, 4) if val is not None else None,
    }


def _worker_init(agents, ckpt, meeple_k):
    import torch
    torch.set_num_threads(1)
    _W["agents"] = agents
    _W["meeple_k"] = meeple_k
    _W["net"] = None
    if "rod1" in agents:
        ck = torch.load(ckpt, map_location="cpu", weights_only=False)
        ns = int(ck.get("n_scalar_features", 10))
        from carcassonne_ai.network import CarcassonneNet
        net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                             n_scalar_features=ns,
                             value_global_pool=bool(ck.get("value_global_pool", False)))
        net.load_state_dict(ck["model_state"]); net.train(False)
        _W["net"] = net; _W["ns"] = ns; _W["farm"] = ns > 10


def _audit_one(arg):
    out_dir, rec = arg
    pos_path = Path(out_dir) / "pos" / f"{rec['gen_id']}_k{rec['k_remaining']}.json"
    if pos_path.exists():
        try:
            return json.load(open(pos_path))
        except Exception:
            pos_path.unlink(missing_ok=True)
    import torch
    game, board = replay_to(rec["seed"], rec["ply"])
    # integrity: reconstructed board must match the stored checksum
    if game.string_representation(board) != rec["checksum"]:
        return {"gen_id": rec["gen_id"], "k": rec["k_remaining"], "error": "checksum_mismatch"}
    mk = _W["meeple_k"]
    out = {k: rec[k] for k in ("gen_id", "seed", "ply", "k_remaining", "phase",
                               "to_move", "legal_n", "score_margin_abs", "placed_farmers")}
    out["meeples_free"] = rec.get("meeples_free")
    out["agents"] = {}
    for name in _W["agents"]:
        sims = _heur_sims(name)
        if sims is not None:
            seed = rec["seed"] * 13 + sims          # deterministic, agent-distinct
            m = HeuristicMCTS(game=game, simulations=sims, seed=seed,
                              heur_leaf="v2_7", leaf_cfg=EH._heur_leaf_cfg(mk))
            out["agents"][name] = _harvest(m, board, game)
        elif name == "rod1":
            farm = _W.get("farm", False)
            gf = EH.Game(enable_legal_moves_cache=True, include_farm_scalars=farm)
            from carcassonne_ai.evaluators import make_single_evaluator
            base = make_single_evaluator(_W["net"], torch.device("cpu"), gf)
            m = EH._make_iter8_mcts(base, gf, rec["seed"] * 13 + 1, mk)
            # rod1 plays on the farm-scalar game; reconstruct its board view
            _, board_f = replay_to(rec["seed"], rec["ply"])
            out["agents"][name] = _harvest(m, board_f, gf)
    pos_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = pos_path.with_suffix(".tmp")
    json.dump(out, open(tmp, "w")); tmp.replace(pos_path)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--positions", required=True)
    ap.add_argument("--agents", default="h3200,h6400,h12800,rod1")
    ap.add_argument("--ckpt", default="/mnt/c/carc-shared/rod_v28_continuation/ckpt/iter_01.pt")
    ap.add_argument("--meeple-k", type=float, default=2.0)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0, help="cap positions (0=all; smoke)")
    ap.add_argument("--out", default="measurement/deeper_search_ruler/root_audit")
    args = ap.parse_args(argv)
    agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    recs = [json.loads(l) for l in open(args.positions)]
    if args.limit:
        recs = recs[: args.limit]
    out = Path(args.out); (out / "pos").mkdir(parents=True, exist_ok=True)
    json.dump({"agents": agents, "meeple_k": args.meeple_k, "ckpt": args.ckpt,
               "n_positions": len(recs), "positions_file": args.positions},
              open(out / "audit_manifest.json", "w"), indent=2)
    print(f"root-audit: {len(recs)} positions x {agents}  ({args.workers} workers) -> {out}")
    ctx = get_context("fork")
    results, done = [], 0
    with ctx.Pool(args.workers, initializer=_worker_init,
                  initargs=(agents, args.ckpt, args.meeple_k)) as pool:
        for r in pool.imap_unordered(_audit_one, [(str(out), rec) for rec in recs], chunksize=1):
            results.append(r); done += 1
            if done % 50 == 0 or done == len(recs):
                print(f"  {done}/{len(recs)} positions audited", flush=True)
    json.dump(results, open(out / "all_positions.json", "w"))
    print(f"[written] {out}/all_positions.json  ({len(results)} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
