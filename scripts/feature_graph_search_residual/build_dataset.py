#!/usr/bin/env python3
"""FGSR Stage 2 — full graph dataset over the 10,351 residual roots.

For every root in roots_mcts.jsonl (filtered to the psr_lib.load_roots set — >=2
visited children at the reference), replay -> decompose -> extract_graph +
extract_action_nodes. NET-FREE, CPU-parallel (fork Pool, nice -n 19 from the
launcher). No deep search, no training, no engine/v2.9/PRODUCTION.yaml change.

Outputs under measurement/feature_graph_search_residual/data/:

  rows_feat.npz   — the per-(root,child) ACTION-NODE feature matrix (graph-lite +
                    the model's primary signal). Mirrors the comparator's npz so
                    psr_lib / eval_lib grouping + labels work unchanged:
      feat        (n_rows, 50) float32   — the 50 comparator scalars (FEAT_NAMES)
      group_id    (n_rows,)    int32     — root id (== roots_mcts group_id)
      action_id   (n_rows,)    int32
      game_seed   (n_rows,)    int64     — for seed_split (no-leakage)
      game_id     (n_rows,)    int64
      ply         (n_rows,)    int16
      phase       (n_rows,)    <U12
      n200,n800,n6400      (n_rows,) int32   — stored visit counts
      q200,q800,q6400      (n_rows,) float32 — stored Q_rootpov (tanh-Q)
      in_h200     (n_rows,)    int8      — child explored by h200?
      leaf_q      (n_rows,)    float32   — static v2.9 leaf-Q of the child
      feat_names  (50,)        <U40

  graphs.pkl      — {group_id: compact_graph} typed-graph store (for the GNN, G1+).
                    Each compact_graph = {"nodes": {type: list[attr_dict]},
                    "edges": {type: list[(s_t,s_i,d_t,d_i)]}, "meta": {...}}.
                    Pickle (graphs are heterogeneous, variable-size; npz is awkward).

  manifest.json   — full resolved config (leaf hash, sources, counts, format, git rev).

Labels are NOT baked in — they are derivable from the stored q200/q6400 via psr_lib
(regret(hL) = max_a q6400[a] - q6400[sel(hL)]; pos_strong = q_gap_6400>=0.02 &
regret200>=0.02). Storing raw Q keeps the dataset label-scheme-agnostic.
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))
from snapshot import set_frozen_v29_env, frozen_v29_cfg, FROZEN_V29_HASH  # noqa: E402
set_frozen_v29_env()

import argparse  # noqa: E402
import json  # noqa: E402
import pickle  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from multiprocessing import get_context  # noqa: E402

import numpy as np  # noqa: E402

for _p in (REPO / "src", REPO / "scripts", REPO / "scripts" / "feature_graph_search_residual",
           REPO / "scripts" / "post_search_residual", REPO / "scripts" / "feature_graph"):
    sys.path.insert(0, str(_p))

import psr_lib  # noqa: E402

DATA_SRC = REPO / "measurement" / "post_search_residual" / "data"
OUT = REPO / "measurement" / "feature_graph_search_residual" / "data"
ROOTS = DATA_SRC / "roots_mcts.jsonl"
GAMES = DATA_SRC / "games_mcts.jsonl"

# Worker globals (fork inherits the module; these are set in _init).
_W: dict = {}


def _init():
    # import inside worker so the engine + extractor are loaded once per process
    import extract_graph as EG
    from measurement_infra import load_games_dict
    _W["EG"] = EG
    _W["games"] = load_games_dict(str(GAMES))


def _process(raw):
    """raw: a roots_mcts.jsonl record (dict). Returns extraction payload or _error."""
    try:
        EG = _W["EG"]
        from measurement_infra import replay_actions
        gid = int(raw["group_id"])
        seed = int(raw["seed"])
        game_id = int(raw["game_id"])
        ply = int(raw["ply"])
        rp = int(raw["root_player"])
        actions = _W["games"][game_id]
        game, board = replay_actions(seed, actions, ply)
        state = board.state
        if state.current_player != rp:
            return {"_error": f"{gid}: current_player {state.current_player} != root_player {rp}"}
        graph, anodes, feat_names = EG.extract_root(game, board, raw, root_player=rp)
        if len(anodes) < 2:
            return {"_error": f"{gid}: <2 action nodes"}
        # compact the graph for pickling: strip nothing (already plain dicts)
        return {
            "group_id": gid, "seed": seed, "game_id": game_id, "ply": ply,
            "phase": raw.get("phase", "?"),
            "graph": graph,
            "anodes": anodes,
            "feat_names": feat_names,
        }
    except Exception as e:
        import traceback
        return {"_error": f"{raw.get('group_id')}: {type(e).__name__}: {e}",
                "_tb": traceback.format_exc()}


def _git_rev():
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    cfg = frozen_v29_cfg()  # asserts config_hash == FROZEN_V29_HASH
    print(f"[build] leaf {FROZEN_V29_HASH}  workers={args.workers}")

    # the canonical 10,351 root set (filtered, derived) — but we need the RAW records
    rows = psr_lib.load_roots(str(ROOTS))
    keep = {(r["game_id"], r["ply"]) for r in rows}
    raws = []
    for line in ROOTS.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if (int(r["game_id"]), int(r["ply"])) in keep:
            raws.append(r)
    if args.limit:
        raws = raws[: args.limit]
    print(f"[build] {len(raws)} roots to extract")

    t0 = time.time()
    FEAT = []
    GID, AID, GS, GAMEID, PLY, PH = [], [], [], [], [], []
    N200, N800, N6400, Q200, Q800, Q6400, INH200, LEAFQ = [], [], [], [], [], [], [], []
    graphs = {}
    feat_names = None
    nerr = 0
    sample_errs = []
    node_hist = []  # (n_nodes, n_edges, n_action_nodes) per root

    ctx = get_context("fork")
    with ctx.Pool(args.workers, initializer=_init) as pool:
        for i, out in enumerate(pool.imap_unordered(_process, raws, chunksize=16)):
            if "_error" in out:
                nerr += 1
                if len(sample_errs) < 8:
                    sample_errs.append(out["_error"])
                    if "_tb" in out and len(sample_errs) <= 2:
                        print(out["_tb"])
                continue
            gid = out["group_id"]
            anodes = out["anodes"]
            if feat_names is None:
                feat_names = out["feat_names"]
            m = len(anodes)
            FEAT.append(np.stack([an["feat"] for an in anodes]))
            AID.append(np.array([an["action_id"] for an in anodes], np.int32))
            N200.append(np.array([an["n200"] for an in anodes], np.int32))
            N800.append(np.array([an["n800"] for an in anodes], np.int32))
            N6400.append(np.array([an["n6400"] for an in anodes], np.int32))
            Q200.append(np.array([an["q200_rootpov"] for an in anodes], np.float32))
            Q800.append(np.array([an["q800_rootpov"] for an in anodes], np.float32))
            Q6400.append(np.array([an["q6400_rootpov"] for an in anodes], np.float32))
            INH200.append(np.array([1 if an["in_h200"] else 0 for an in anodes], np.int8))
            LEAFQ.append(np.array([an["leaf_q"] for an in anodes], np.float32))
            GID.append(np.full(m, gid, np.int32))
            GS.append(np.full(m, out["seed"], np.int64))
            GAMEID.append(np.full(m, out["game_id"], np.int64))
            PLY.append(np.full(m, out["ply"], np.int16))
            PH.append(np.array([out["phase"]] * m, dtype="<U12"))
            graphs[gid] = out["graph"]
            node_hist.append((out["graph"]["meta"]["n_nodes"],
                              out["graph"]["meta"]["n_edges"], m))
            if (i + 1) % 1000 == 0:
                print(f"  {i+1}/{len(raws)} roots  err={nerr}  {time.time()-t0:.0f}s")
    dt = time.time() - t0
    nrow = int(sum(a.shape[0] for a in FEAT))
    print(f"[done] roots={len(graphs)} rows={nrow} err={nerr} in {dt:.0f}s "
          f"({len(raws)/max(dt,1):.0f} roots/s)")
    if sample_errs:
        print("  sample errors:", sample_errs)

    OUT.mkdir(parents=True, exist_ok=True)
    feat = np.concatenate(FEAT)
    gs = np.concatenate(GS)
    np.savez_compressed(
        OUT / "rows_feat.npz",
        feat=feat,
        group_id=np.concatenate(GID), action_id=np.concatenate(AID),
        game_seed=gs, game_id=np.concatenate(GAMEID),
        ply=np.concatenate(PLY), phase=np.concatenate(PH),
        n200=np.concatenate(N200), n800=np.concatenate(N800), n6400=np.concatenate(N6400),
        q200=np.concatenate(Q200), q800=np.concatenate(Q800), q6400=np.concatenate(Q6400),
        in_h200=np.concatenate(INH200), leaf_q=np.concatenate(LEAFQ),
        feat_names=np.array(feat_names, dtype="<U40"),
    )
    with (OUT / "graphs.pkl").open("wb") as fh:
        pickle.dump(graphs, fh, protocol=pickle.HIGHEST_PROTOCOL)

    # node/edge distribution stats
    nn = np.array([h[0] for h in node_hist])
    ne = np.array([h[1] for h in node_hist])
    na = np.array([h[2] for h in node_hist])
    rows_npz_bytes = (OUT / "rows_feat.npz").stat().st_size
    graphs_pkl_bytes = (OUT / "graphs.pkl").stat().st_size

    # decisive-tail / label counts over the roots actually built (join by group_id)
    present_gids = set(graphs.keys())
    derived_present = [r for r in rows if r["group_id"] in present_gids]
    n_decisive = sum(1 for r in derived_present if r["sel"][200] != r["sel"][6400])
    n_pos_strong = sum(1 for r in derived_present if r["pos_strong"])
    n_pos_medium = sum(1 for r in derived_present if r["pos_medium"])
    from collections import Counter
    phase_counts = Counter(r["phase"] for r in derived_present)

    manifest = {
        "pilot": "FGSR (Feature-Graph Search-Residual) Stage 2 dataset",
        "git_rev": _git_rev(),
        "leaf_config_hash": FROZEN_V29_HASH,
        "leaf": "v2.9 bmild_cap8 (flat_leaf, USE_FLAT_LEAF=1, USE_CY_REPR=1)",
        "net_free": True, "ran_search": False, "trained_model": False,
        "source": {
            "roots": str(ROOTS.relative_to(REPO)),
            "games": str(GAMES.relative_to(REPO)),
            "features_tierB": str((DATA_SRC / "features_mcts.jsonl").relative_to(REPO)),
        },
        "n_roots": len(graphs), "n_action_rows": nrow, "n_errors": nerr,
        "n_decisive_tail": int(n_decisive),
        "n_pos_strong": int(n_pos_strong), "n_pos_medium": int(n_pos_medium),
        "phase_counts": dict(phase_counts),
        "feat_names": feat_names,
        "n_feat": len(feat_names),
        "levels_stored": [200, 800, 6400],
        "levels_available_in_source": [200, 400, 800, 1600, 3200, 6400],
        "node_stats": {"mean": float(nn.mean()), "p50": float(np.percentile(nn, 50)),
                       "p90": float(np.percentile(nn, 90)), "max": int(nn.max())},
        "edge_stats": {"mean": float(ne.mean()), "p50": float(np.percentile(ne, 50)),
                       "p90": float(np.percentile(ne, 90)), "max": int(ne.max())},
        "action_node_stats": {"mean": float(na.mean()), "p50": float(np.percentile(na, 50)),
                              "p90": float(np.percentile(na, 90)), "max": int(na.max())},
        "files": {
            "rows_feat.npz": {"bytes": rows_npz_bytes,
                              "desc": "per-(root,child) action-node feature matrix + stored Q"},
            "graphs.pkl": {"bytes": graphs_pkl_bytes,
                           "desc": "typed feature graphs keyed by group_id (pickle)"},
        },
        "labels_note": ("labels NOT baked in; derive via psr_lib from stored q200/q6400 "
                        "(regret(hL)=maxQ6400 - Q6400[sel(hL)]; pos_strong = q_gap_6400>=0.02 "
                        "& regret200>=0.02). Stored raw Q keeps the dataset label-agnostic."),
        "leakage_note": ("split by game_seed via psr_lib.seed_split / eval_lib.seed_split — no root "
                         "crosses a split; all children of a root share its group_id+game_seed so "
                         "grouping is leak-free."),
        "schema": "measurement/feature_graph_search_residual/FGSR_SCHEMA.md",
        "build_wallclock_s": round(dt, 1), "workers": args.workers,
        "fold_choices": [
            "open_boundary folded into feature open_edges/open_ends + sentinel edges",
            "tile recency omitted (not on state); move recency on action nodes",
            "road open_ends = has-open binary",
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("[out]", OUT / "rows_feat.npz", f"({rows_npz_bytes/1e6:.1f} MB)")
    print("[out]", OUT / "graphs.pkl", f"({graphs_pkl_bytes/1e6:.1f} MB)")
    print("[out]", OUT / "manifest.json")
    print(json.dumps({k: manifest[k] for k in
                      ("n_roots", "n_action_rows", "n_decisive_tail", "n_pos_strong",
                       "n_errors", "node_stats", "edge_stats", "build_wallclock_s")},
                     indent=2))


if __name__ == "__main__":
    main()
