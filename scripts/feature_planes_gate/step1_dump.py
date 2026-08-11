#!/usr/bin/env python3
"""Step-1 representation gate — dataset builder (CL-033 harness + extra planes).

STREAMING rewrite (2026-06-29, after the accumulate+concatenate model OOM'd the
WSL VM): the dataset is ~314,911 child rows; one mode's obs is ~30 GB, and the
old `np.concatenate(OBS)` doubled it (~61 GB) → VM teardown. Here ONLY the obs
planes (the 4-D (N,C,W,W) block) are STREAMED to a raw float16 file per group, so
the parent never holds the full array. Everything else (scalars ~27 MB, oracle_q,
leaf_q, ids, phase) is tiny and kept in RAM, written to aux.npz at the end. Peak
parent RAM = workers + a single group's obs buffer ≈ a few GB beyond the worker
pool → W=30 safe on local; a sharded subset is safe on the 11 GB laptop.

SAME 10,067 roots / replay_to / teacher-Q'd child enumeration / root-POV
oracle_q,leaf_q,group_id,game_seed,phase as scripts/rod_v2/value_resurrection/
dump_dataset.py. The ONLY signal change is the appended structural planes:

  --mode none   (== CL-033 baseline)            obs (78,W,W)   sca (12,)
  --mode farm   + farm_connectivity_planes       obs (81,W,W)   sca (12,)
  --mode bag    + bag_histogram                  obs (78,W,W)   sca (44,)
  --mode both   both                             obs (81,W,W)   sca (44,)

Root sharding for multi-box runs: --shard IDX --nshards N takes recs[IDX::N].
Each shard writes <out>/{child_obs.f16, aux.npz, meta.json}; merge with
step1_merge.py (cat the .f16 + concat+renumber the aux arrays).

Output (per <out> dir):
  child_obs.f16   raw float16, shape (n_rows, C, W, W) row-major, groups contiguous
  aux.npz         child_scalars, oracle_q, leaf_q, group_id, game_seed, ply, phase, q_gap
  meta.json       {n_rows, n_chan, W, n_scalar, mode, shard, ...}

The both_shuffled negative control is a SEPARATE streaming post-pass
(step1_negctrl.py) run only if a +planes mode passes — not built here.

NET-FREE, CPU-parallel.
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

import argparse, json, math, sys, time
from pathlib import Path
from multiprocessing import get_context

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "feature_planes_gate"))
import eval_hybrid_handoff as EH
from gen_endgame_positions import replay_to
from carcassonne_ai.virtual_score_v2 import virtual_score_v2
from step1_planes import farm_connectivity_planes, bag_histogram, N_FARM_PLANES, N_BAG

HG = REPO / "measurement" / "high_gap_distillation"
_W: dict = {}
_MODE = "none"


def _worker_init(mode):
    global _MODE  # noqa: PLW0603
    _MODE = mode
    _W["cfg"] = EH._heur_leaf_cfg(2.0)
    _W["game"] = EH.Game(enable_legal_moves_cache=True, include_farm_scalars=True)


def _process(rec):
    """Return one group's rows: obs (m,C,W,W) f16 + small per-child arrays."""
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

        add_farm = _MODE in ("farm", "both")
        add_bag = _MODE in ("bag", "both")

        seen = set()
        obs_l, sca_l, h6_l, leaf_l = [], [], [], []
        for a in legal:
            a = int(a)
            if a not in aq:            # keep only teacher-Q'd canonical children
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
            obs = obs.astype(np.float16)
            sca = np.asarray(sca, dtype=np.float16)
            if add_farm:
                off = child.offset; W = off.size
                fp = farm_connectivity_planes(child.state, root_player, off, W)
                obs = np.concatenate([obs, fp.astype(np.float16)], axis=0)
            if add_bag:
                bag = bag_histogram(child.state).astype(np.float16)
                sca = np.concatenate([sca, bag], axis=0)
            obs_l.append(obs)
            sca_l.append(sca)
            h6_l.append(aq[a])
            leaf_l.append(float(leaf))

        if len(h6_l) < 2:
            return {"_error": f"{seed}:{ply} <2 mapped children"}
        return {
            "seed": seed, "ply": ply, "phase": rec.get("phase", "?"),
            "q_gap": float(rec.get("q_gap_1_2", 0.0)),
            "obs": np.stack(obs_l),                      # (m,C,W,W) f16 — STREAMED
            "sca": np.stack(sca_l).astype(np.float16),   # (m,S)   f16 — RAM (small)
            "h6": np.asarray(h6_l, dtype=np.float32),
            "leaf": np.asarray(leaf_l, dtype=np.float32),
        }
    except Exception as e:
        return {"_error": f"{rec.get('seed')}:{rec.get('ply')} {type(e).__name__}: {e}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qprobe", default=str(HG / "scaled" / "qprobe_A" / "probe.jsonl"))
    ap.add_argument("--pool", default=str(HG / "scaled" / "pool_A.jsonl"))
    ap.add_argument("--mode", choices=["none", "farm", "bag", "both"], default="none")
    ap.add_argument("--out", default="")
    ap.add_argument("--workers", type=int, default=30)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    out = args.out or f"/mnt/c/carc-shared/feature_planes_gate/dataset_{args.mode}"
    if args.nshards > 1:
        out = f"{out}/shard{args.shard}"
    outd = Path(out); outd.mkdir(parents=True, exist_ok=True)

    checks = {}
    for line in open(args.pool):
        r = json.loads(line); checks[(r["seed"], r["ply"])] = r["checksum"]
    recs = []
    for line in open(args.qprobe):
        r = json.loads(line); key = (r["seed"], r["ply"])
        if key in checks:
            r["checksum"] = checks[key]; recs.append(r)
    n_avail = len(recs)
    if args.nshards > 1:                      # deterministic root shard (no overlap)
        recs = recs[args.shard::args.nshards]
    if args.limit:
        recs = recs[: args.limit]
    print(f"[load] mode={args.mode} shard={args.shard}/{args.nshards} "
          f"{len(recs)}/{n_avail} sibling sets workers={args.workers} -> {out}",
          flush=True)

    obs_path = outd / "child_obs.f16"
    fobs = open(obs_path, "wb")               # STREAM obs here, group by group
    SCA, H6, LEAF, GID, GS, PLY, PH, GAP = [], [], [], [], [], [], [], []
    gid = 0; nerr = 0; nrow = 0
    C = W = None
    t0 = time.time()
    ctx = get_context("fork")
    with ctx.Pool(args.workers, initializer=_worker_init, initargs=(args.mode,)) as pool:
        for i, rec in enumerate(pool.imap_unordered(_process, recs, chunksize=8)):
            if "_error" in rec:
                nerr += 1
                continue
            obs = rec["obs"]                      # (m,C,W,W) f16
            if C is None:
                C, W = int(obs.shape[1]), int(obs.shape[2])
            # stream this group's obs straight to disk; do NOT retain it
            fobs.write(np.ascontiguousarray(obs, dtype=np.float16).tobytes())
            m = obs.shape[0]
            SCA.append(rec["sca"]); H6.append(rec["h6"]); LEAF.append(rec["leaf"])
            GID.append(np.full(m, gid, np.int32)); GS.append(np.full(m, rec["seed"], np.int64))
            PLY.append(np.full(m, rec["ply"], np.int16))
            GAP.append(np.full(m, rec["q_gap"], np.float32))
            PH.append(np.array([rec["phase"]] * m, dtype="<U12"))
            gid += 1; nrow += m
            if (i + 1) % 2000 == 0:
                print(f"  {i+1}/{len(recs)} groups={gid} rows={nrow} err={nerr} "
                      f"{time.time()-t0:.0f}s", flush=True)
    fobs.close()
    dt = time.time() - t0
    print(f"[done] groups={gid} rows={nrow} err={nerr} in {dt:.0f}s "
          f"obs_bytes={obs_path.stat().st_size/1e9:.1f}GB", flush=True)

    # everything except obs is tiny -> one aux.npz
    np.savez(
        outd / "aux.npz",
        child_scalars=np.concatenate(SCA), oracle_q=np.concatenate(H6),
        leaf_q=np.concatenate(LEAF), group_id=np.concatenate(GID),
        game_seed=np.concatenate(GS), ply=np.concatenate(PLY),
        phase=np.concatenate(PH), q_gap=np.concatenate(GAP),
    )
    n_scalar = int(SCA[0].shape[1]) if SCA else 0
    meta = {"mode": args.mode, "shard": args.shard, "nshards": args.nshards,
            "n_rows": int(nrow), "n_groups": int(gid), "n_groups_avail": int(n_avail),
            "n_chan": int(C or 0), "W": int(W or 0), "n_scalar": n_scalar,
            "n_farm_planes": N_FARM_PLANES if args.mode in ("farm", "both") else 0,
            "n_bag_scalars": N_BAG if args.mode in ("bag", "both") else 0,
            "obs_dtype": "float16", "obs_file": "child_obs.f16",
            "teacher": "h6400_v2.9", "leaf": "v2.9_bmild_cap8", "v29_hash": "7fc930b82801cb43",
            "source": args.qprobe, "n_err": int(nerr)}
    (outd / "meta.json").write_text(json.dumps(meta, indent=2))
    print("meta:", json.dumps(meta), flush=True)


if __name__ == "__main__":
    main()
