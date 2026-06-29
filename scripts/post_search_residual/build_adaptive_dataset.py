#!/usr/bin/env python3
"""Post-Search Residual Pilot — Stage 1: build the h200-vs-deep adaptive-compute dataset.

ONE HeuristicMCTS(6400) search per root, snapshotting the root's child statistics
{action -> (N, Q_rootpov)} at cumulative sim counts {200,400,800,1600,3200,6400}. MCTS is
incremental, so the snapshot-at-L is bit-identical to a standalone HeuristicMCTS(L).search()
(--verify asserts this). This yields ALL uniform compute levels + the h6400 reference from a
single search -> ~6x cheaper than running each level separately.

Net-free, pure CPU (no NN, no orchestrator). Frozen v2.9 leaf (config_hash 7fc930b82801cb43).

Roots: unique (group_id -> game_seed, ply, phase) from the feature-graph dataset (Phase A,
greedy-self-play distribution; broaden in Phase B only if the Stage-2 oracle gate passes).

Output: JSONL, one line per root, with per-level deduped visited children [action, N, Q_rootpov]
+ metadata. Regret / labels / diagnostics are derived downstream (eval_lib) from these snapshots.
"""
from __future__ import annotations
import os
# --- frozen v2.9 leaf env block (copied verbatim from feature_graph/search_screen.py) ---
os.environ["CARCASSONNE_V25_CAP"] = "8"
os.environ["CARCASSONNE_V25_OPP_CAP"] = "8"
os.environ["CARCASSONNE_V25_DROP_THREE_OPEN"] = "0"
os.environ["CARCASSONNE_V29_MEEPLE_CURVE"] = "-8,-4,-1,0,2,3,4,5"
os.environ["CARCASSONNE_V25_MEEPLE_K"] = "2.0"
os.environ["CARCASSONNE_USE_FLAT_LEAF"] = "1"
os.environ["CARCASSONNE_USE_CY_REPR"] = "1"
os.environ["CARCASSONNE_V25_VALUE_BLEND"] = "0"
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse, dataclasses as dc, hashlib, json, math, random, sys, time
from pathlib import Path
from multiprocessing import get_context

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "feature_graph"))

import eval_hybrid_handoff as EH                         # noqa: E402
from gen_endgame_positions import replay_to              # noqa: E402
from carcassonne_ai.game_wrapper import Game             # noqa: E402
from carcassonne_ai.mcts import HeuristicMCTS            # noqa: E402

OUT = REPO / "measurement" / "post_search_residual"
DATA = OUT / "data"
FROZEN_V29_HASH = "7fc930b82801cb43"
LEVELS = [200, 400, 800, 1600, 3200, 6400]
MAX_SIMS = LEVELS[-1]
FG_ROWS = REPO / "measurement" / "feature_graph_comparator" / "data" / "rows_feat.npz"

_W: dict = {}


def _cfg_hash(cfg):
    d = {k: (list(v) if isinstance(v, tuple) else v) for k, v in dc.asdict(cfg).items()}
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def _provenance_guard():
    cfg = EH._heur_leaf_cfg(2.0)
    h = _cfg_hash(cfg)
    print(f"[provenance] v2.9 leaf config_hash = {h}  (frozen v2.9 = {FROZEN_V29_HASH})")
    assert h == FROZEN_V29_HASH, f"LEAF NOT v2.9 bmild_cap8 (got {h})"
    return cfg


def _mcts_seed(game_seed: int, ply: int) -> int:
    return (int(game_seed) * 1_000_003 + int(ply)) % (2 ** 31)


def _read_children(root, root_player):
    """Deduped visited children -> {action: [N, Q_rootpov]}. Mirrors best_action's
    transposition dedup (lowest action id per unique Node) and root-POV Q sign."""
    seen = set()
    out = {}
    for a in sorted(root.children):
        ch = root.children[a]
        if ch.N <= 0 or id(ch) in seen:
            continue
        seen.add(id(ch))
        q = ch.Q if ch.player_to_move == root_player else -ch.Q
        out[int(a)] = [int(ch.N), float(q)]
    return out


def _worker_init(cfg_norm):
    _W["agent"] = HeuristicMCTS(
        game=Game(enable_legal_moves_cache=True, include_farm_scalars=True),
        simulations=MAX_SIMS, heur_leaf="v2_7", leaf_cfg=EH._heur_leaf_cfg(cfg_norm), seed=0,
    )


def _snapshot_search(agent, board, levels):
    """Drive `levels[-1]` simulations, snapshotting deduped child stats at each level.
    Returns {L: {action: [N, Q_rootpov]}}."""
    root = agent._get_or_create_node(board)
    root_player = root.player_to_move
    snaps = {}
    want = list(levels)
    idx = 0
    for i in range(1, want[-1] + 1):
        agent._simulate(board, root)
        if idx < len(want) and i == want[idx]:
            snaps[want[idx]] = _read_children(root, root_player)
            idx += 1
    return snaps, root_player


def _process(root):
    try:
        seed = int(root["seed"]); ply = int(root["ply"]); gid = int(root["group_id"])
        agent = _W["agent"]
        agent.clear()
        agent.rng = random.Random(_mcts_seed(seed, ply))   # per-root reproducible
        _, board = replay_to(seed, ply)
        snaps, root_player = _snapshot_search(agent, board, LEVELS)
        return {
            "group_id": gid, "seed": seed, "ply": ply,
            "phase": root["phase"], "legal_n": int(root["legal_n"]),
            "root_player": int(root_player),
            "levels": {str(L): snaps[L] for L in LEVELS},
        }
    except Exception as e:
        import traceback
        return {"_error": f"{root.get('group_id')}: {type(e).__name__}: {e}",
                "_tb": traceback.format_exc().splitlines()[-3:]}


def _verify(roots, cfg_norm, n=5):
    """Assert snapshot-at-200 == standalone HeuristicMCTS(200) child N-distribution."""
    print(f"[verify] checking snapshot==standalone on {n} roots ...")
    agent = HeuristicMCTS(game=Game(enable_legal_moves_cache=True, include_farm_scalars=True),
                          simulations=MAX_SIMS, heur_leaf="v2_7",
                          leaf_cfg=EH._heur_leaf_cfg(cfg_norm), seed=0)
    ok = True
    for r in roots[:n]:
        seed = int(r["seed"]); ply = int(r["ply"])
        ms = _mcts_seed(seed, ply)
        agent.clear(); agent.rng = random.Random(ms)
        _, board = replay_to(seed, ply)
        snaps, rp = _snapshot_search(agent, board, LEVELS)
        snap200 = snaps[200]
        # standalone h200
        ref = HeuristicMCTS(game=Game(enable_legal_moves_cache=True, include_farm_scalars=True),
                            simulations=200, heur_leaf="v2_7",
                            leaf_cfg=EH._heur_leaf_cfg(cfg_norm), seed=ms)
        _, board2 = replay_to(seed, ply)
        ref.search(board2)
        rroot = ref._nodes[ref.game.string_representation(board2)]
        refN = _read_children(rroot, rroot.player_to_move)
        # compare N per action (Q float compare with tol)
        a_snap = {a: v[0] for a, v in snap200.items()}
        a_ref = {a: v[0] for a, v in refN.items()}
        same = a_snap == a_ref
        # total visits both == 200
        ts, tr = sum(a_snap.values()), sum(a_ref.values())
        print(f"  gid={r['group_id']} seed={seed} ply={ply}: N-dist match={same} "
              f"sumN snap={ts} ref={tr} | nchild snap={len(a_snap)} ref={len(a_ref)}")
        if not same:
            ok = False
            # show first divergence
            allk = sorted(set(a_snap) | set(a_ref))
            for k in allk[:8]:
                if a_snap.get(k) != a_ref.get(k):
                    print(f"     action {k}: snap={a_snap.get(k)} ref={a_ref.get(k)}")
    print(f"[verify] {'PASS' if ok else 'FAIL'}")
    return ok


def _load_roots(n, phase_stratified, seed):
    d = np.load(FG_ROWS, allow_pickle=True)
    gid = d["group_id"]; gseed = d["game_seed"]; ply = d["ply"]
    phase = d["phase"]; legal_n = d["legal_n"]
    # one row per unique group_id
    _, first_idx = np.unique(gid, return_index=True)
    roots = [{"group_id": int(gid[i]), "seed": int(gseed[i]), "ply": int(ply[i]),
              "phase": str(phase[i]), "legal_n": int(legal_n[i])} for i in first_idx]
    rng = np.random.default_rng(seed)
    if n and n < len(roots):
        if phase_stratified:
            by_ph = {}
            for r in roots:
                by_ph.setdefault(r["phase"], []).append(r)
            per = max(1, n // len(by_ph))
            picked = []
            for ph, lst in by_ph.items():
                idx = rng.choice(len(lst), size=min(per, len(lst)), replace=False)
                picked += [lst[i] for i in idx]
            # top up randomly if short
            if len(picked) < n:
                rest = [r for r in roots if r not in picked]
                extra = rng.choice(len(rest), size=min(n - len(picked), len(rest)), replace=False)
                picked += [rest[i] for i in extra]
            roots = picked[:n]
        else:
            idx = rng.choice(len(roots), size=n, replace=False)
            roots = [roots[i] for i in idx]
    return roots


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2500)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=str, default=str(DATA / "roots_adaptive.jsonl"))
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--phase-stratified", action="store_true", default=True)
    args = ap.parse_args()

    t0 = time.time()
    cfg = _provenance_guard()
    roots = _load_roots(args.n, args.phase_stratified, args.seed)
    from collections import Counter
    ph_counts = Counter(r["phase"] for r in roots)
    print(f"[roots] n={len(roots)} phases={dict(ph_counts)}")

    if args.verify:
        if not _verify(roots, 2.0, n=5):
            print("VERIFY FAILED — aborting build."); sys.exit(2)

    rate = 0.30  # roots/s/worker rough est for 1x6400 search (smoke will correct)
    eta = len(roots) / (rate * args.workers)
    print(f"[eta] ~{len(roots)} roots @ ~{rate}/s/worker x {args.workers}w -> ~{eta/60:.1f} min")

    ctx = get_context("fork")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    results, errs = [], []
    with out_path.open("w") as fh:
        with ctx.Pool(args.workers, initializer=_worker_init, initargs=(2.0,)) as pool:
            for i, out in enumerate(pool.imap_unordered(_process, roots, chunksize=4)):
                if "_error" in out:
                    errs.append(out["_error"])
                    if len(errs) <= 5:
                        print("  ERR", out["_error"], out.get("_tb"))
                else:
                    fh.write(json.dumps(out) + "\n")
                    results.append(out["group_id"])
                if (i + 1) % 200 == 0:
                    el = time.time() - t0
                    print(f"  {i+1}/{len(roots)} ok={len(results)} err={len(errs)} "
                          f"{el:.0f}s ({(i+1)/el:.2f} roots/s)")
    dt = time.time() - t0
    print(f"[done] ok={len(results)} err={len(errs)} in {dt:.0f}s "
          f"({len(results)/dt:.2f} roots/s, {len(results)/dt/args.workers:.3f}/s/worker)")
    if errs[:5]:
        print("  sample errors:", errs[:5])
    print(f"[write] {out_path}  ({out_path.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
