#!/usr/bin/env python3
"""Value Resurrection Pilot — Stage 4 dataset builder.

Builds the per-child feature dataset for training V1-V5 learned value/ranking candidates
on top of the v2.9 leaf, reusing the EXISTING h6400_v2.9 sibling labels (no new search).

For each (seed, ply) sibling set in qprobe_A ∩ pool_A (10,067 roots):
  replay_to(seed, ply) -> root; enumerate id-deduped legal children; for each child store
    child_obs    encode_board(child.state, root_player, child.offset)        (C,W,W) f16
    child_scalars encode_scalars(...)                                         (S,)    f16
    oracle_q     h6400_v2.9 root-POV Q (from action_q)                        f32   <- TARGET base
    leaf_q       tanh(virtual_score_v2(child, root_player, v2.9cfg)/15)       f32   <- for offline gate
    group_id     unique per root (sibling set)                               i32
    game_seed/ply/phase/q_gap                                                provenance
Only TEACHER-VISITED children (action id in action_q) are kept (the set h6400 has a Q for),
exactly matching leaf_audit.py.

The trainer (scripts/value_ranking_train.py) consumes `oracle_q` directly; per-variant
targets (V1 residual = oracle_q - leaf_q; V2 advantage = oracle_q - group_mean; V4 listwise
on absolute oracle_q) are derived at train time from these stored arrays — no re-dump.

NET-FREE, CPU-parallel.  Writes <out>/rows.npz + meta.json.
"""
from __future__ import annotations
import os
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

import argparse, json, math, random, sys, time
from pathlib import Path
from multiprocessing import get_context

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
import eval_hybrid_handoff as EH
from gen_endgame_positions import replay_to
from carcassonne_ai.virtual_score_v2 import virtual_score_v2

HG = REPO / "measurement" / "high_gap_distillation"
_W: dict = {}


def _worker_init():
    _W["cfg"] = EH._heur_leaf_cfg(2.0)
    _W["game"] = EH.Game(enable_legal_moves_cache=True, include_farm_scalars=True)


def _process(rec):
    try:
        seed = int(rec["seed"]); ply = int(rec["ply"])
        game, board = replay_to(seed, ply)
        if game.string_representation(board) != rec["checksum"]:
            return {"_error": f"{seed}:{ply} checksum_mismatch"}
        cfg = _W["cfg"]; gf = _W["game"]
        root_player = board.state.current_player
        aq = {int(k): float(v) for k, v in rec["action_q"].items()}
        legal = np.flatnonzero(game.get_valid_moves(board)).astype(int)
        if legal.size < 2:
            return {"_error": f"{seed}:{ply} <2 legal"}

        seen = set()
        obs_l, sca_l, h6_l, leaf_l = [], [], [], []
        for a in legal:
            a = int(a)
            if a not in aq:            # keep only teacher-visited canonical children
                continue
            child, _ = game.get_next_state(board, a)
            cs = game.string_representation(child)
            if cs in seen:
                continue
            seen.add(cs)
            ended = game.get_game_ended(child, root_player)
            if ended != 0:
                leaf = max(-1.0, min(1.0, float(ended)))
            else:
                leaf = math.tanh(virtual_score_v2(child.state, root_player, cfg) / 15.0)
            obs, sca = gf.get_canonical_form(child, root_player)
            obs_l.append(obs.astype(np.float16))
            sca_l.append(np.asarray(sca, dtype=np.float16))
            h6_l.append(aq[a])
            leaf_l.append(float(leaf))

        if len(h6_l) < 2:
            return {"_error": f"{seed}:{ply} <2 mapped children"}
        return {
            "seed": seed, "ply": ply, "phase": rec.get("phase", "?"),
            "q_gap": float(rec.get("q_gap_1_2", 0.0)),
            "obs": np.stack(obs_l), "sca": np.stack(sca_l),
            "h6": np.asarray(h6_l, dtype=np.float32),
            "leaf": np.asarray(leaf_l, dtype=np.float32),
        }
    except Exception as e:
        return {"_error": f"{rec.get('seed')}:{rec.get('ply')} {type(e).__name__}: {e}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qprobe", default=str(HG / "scaled" / "qprobe_A" / "probe.jsonl"))
    ap.add_argument("--pool", default=str(HG / "scaled" / "pool_A.jsonl"))
    ap.add_argument("--out", default="/mnt/c/carc-shared/value_resurrection/dataset_v29_h6400")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-groups", type=int, default=0,
                    help="cap #roots (seed-shuffled) to bound RAM; 0=all. logged in meta.")
    args = ap.parse_args()

    checks = {}
    for line in open(args.pool):
        r = json.loads(line); checks[(r["seed"], r["ply"])] = r["checksum"]
    recs = []
    for line in open(args.qprobe):
        r = json.loads(line); key = (r["seed"], r["ply"])
        if key in checks:
            r["checksum"] = checks[key]; recs.append(r)
    n_avail = len(recs)
    if args.max_groups and len(recs) > args.max_groups:
        random.Random(0).shuffle(recs)
        recs = recs[: args.max_groups]
    if args.limit:
        recs = recs[: args.limit]
    print(f"[load] {len(recs)}/{n_avail} sibling sets (cap={args.max_groups})  workers={args.workers}")

    t0 = time.time()
    OBS, SCA, H6, LEAF, GID, GS, PLY, PH, GAP = [], [], [], [], [], [], [], [], []
    gid = 0; nerr = 0; nrow = 0
    ctx = get_context("fork")
    with ctx.Pool(args.workers, initializer=_worker_init) as pool:
        for i, out in enumerate(pool.imap_unordered(_process, recs, chunksize=8)):
            if "_error" in out:
                nerr += 1
                continue
            m = out["obs"].shape[0]
            OBS.append(out["obs"]); SCA.append(out["sca"])
            H6.append(out["h6"]); LEAF.append(out["leaf"])
            GID.append(np.full(m, gid, np.int32)); GS.append(np.full(m, out["seed"], np.int64))
            PLY.append(np.full(m, out["ply"], np.int16)); GAP.append(np.full(m, out["q_gap"], np.float32))
            PH.append(np.array([out["phase"]] * m, dtype="<U12"))
            gid += 1; nrow += m
            if (i + 1) % 2000 == 0:
                print(f"  {i+1}/{len(recs)} groups={gid} rows={nrow} err={nerr} {time.time()-t0:.0f}s")
    dt = time.time() - t0
    print(f"[done] groups={gid} rows={nrow} err={nerr} in {dt:.0f}s")

    outd = Path(args.out); outd.mkdir(parents=True, exist_ok=True)
    obs = np.concatenate(OBS); sca = np.concatenate(SCA)
    np.savez_compressed(
        outd / "rows.npz",
        child_obs=obs, child_scalars=sca,
        oracle_q=np.concatenate(H6), leaf_q=np.concatenate(LEAF),
        group_id=np.concatenate(GID), game_seed=np.concatenate(GS),
        ply=np.concatenate(PLY), phase=np.concatenate(PH), q_gap=np.concatenate(GAP),
    )
    meta = {"n_rows": int(nrow), "n_groups": int(gid), "n_groups_avail": int(n_avail),
            "max_groups_cap": int(args.max_groups),
            "n_games": int(len(set(s for s in np.concatenate(GS).tolist()))),
            "obs_shape": list(obs.shape[1:]), "n_scalar": int(sca.shape[1]),
            "teacher": "h6400_v2.9", "leaf": "v2.9_bmild_cap8", "v29_hash": "7fc930b82801cb43",
            "source": args.qprobe, "n_err": int(nerr)}
    (outd / "meta.json").write_text(json.dumps(meta, indent=2))
    print("meta:", meta)


if __name__ == "__main__":
    main()
