#!/usr/bin/env python3
"""Hard-position policy-repair — Stage 0+1: MINE + LABEL.

For each fixed root (seed+ply from a multiphase pool), run the v2.9 rulers
HeuristicMCTS@3200 (classify) + HeuristicMCTS@6400 (deep teacher), tag whether
they DISAGREE on the top move, and emit a training row whose POLICY TARGET is the
h6400 visit distribution. Labeling is NET-FREE (pure heuristic MCTS) → trivially
CPU-parallel, shardable across boxes.

Outputs (under --out, default measurement/hard_policy_repair):
  data/{train,val,test}/iter_00/seed_*.npz   train_iter.py-format npz, SPLIT BY
                                             disagreement (hard=disagree, ord=agree)
  manifest_{train,val,test}.jsonl            per-state metadata + h3200/h6400 labels
                                             + h6400 visit dist over legal (for KL/lean)

The npz carry the standard 8 keys (boards/scalars/policies/values/valid_masks/
ownership/aux_mask/group_id). ownership=zeros + value=0 + group_id=-1: a POLICY-only
fine-tune zeroes those losses (--aux-weight 0 --value-loss-weight 0).

Frozen v2.9 leaf (Bmild_cap8) env is HARD-SET below before any carcassonne import,
exactly as the autopsy harness — so the rulers are genuine v2.9.
"""
from __future__ import annotations
import os
os.environ["CARCASSONNE_V25_CAP"] = "8"
os.environ["CARCASSONNE_V25_OPP_CAP"] = "8"
os.environ["CARCASSONNE_V25_DROP_THREE_OPEN"] = "0"
os.environ["CARCASSONNE_V29_MEEPLE_CURVE"] = "-8,-4,-1,0,2,3,4,5"
os.environ["CARCASSONNE_V25_MEEPLE_K"] = "2.0"            # inert under the curve
os.environ["CARCASSONNE_USE_FLAT_LEAF"] = "1"
os.environ["CARCASSONNE_USE_CY_REPR"] = "1"               # bit-exact, faster encode
os.environ["CARCASSONNE_V25_VALUE_BLEND"] = "0"
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse, json, math, sys, time
from pathlib import Path
from multiprocessing import get_context

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

import numpy as np
import eval_hybrid_handoff as EH
from gen_endgame_positions import replay_to
from carcassonne_ai.mcts import HeuristicMCTS
from carcassonne_ai.aux_targets import OWNERSHIP_PLANES

RULERS = {"h3200": 3200, "h6400": 6400}
_W: dict = {}


def _provenance():
    import dataclasses as dc
    cfg = EH._heur_leaf_cfg(2.0)
    fields = {f.name: getattr(cfg, f.name) for f in dc.fields(cfg)}
    print("[provenance] ruler leaf_cfg (must be v2.9 Bmild_cap8):")
    for k in ("bonus_cap", "opp_cap", "drop_three_open", "v29_meeple_curve", "meeple_k"):
        if k in fields:
            print(f"    {k} = {fields[k]}")
    try:
        from carcassonne_ai.virtual_score_v2 import config_hash
        print(f"    config_hash = {config_hash(cfg)}  (frozen v2.9 = 7fc930b82801cb43)")
    except Exception:
        pass


def _worker_init():
    # One encode-Game per worker (farm scalars ON -> 12-wide, matches RoD nets).
    _W["game"] = EH.Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    _W["cfg"] = EH._heur_leaf_cfg(2.0)


def _process(rec):
    try:
        game, board = replay_to(rec["seed"], rec["ply"])
        if game.string_representation(board) != rec["checksum"]:
            return {"_error": f"{rec['gen_id']}: checksum_mismatch"}
        gf = _W["game"]
        cfg = _W["cfg"]
        seed = rec["seed"]
        cur = board.state.current_player
        mask = gf.get_valid_moves(board)
        A = int(mask.shape[0])
        legal = np.flatnonzero(mask).astype(int)
        if legal.size == 0:
            return {"_error": f"{rec['gen_id']}: no_legal"}

        choices, dists = {}, {}
        for name, sims in RULERS.items():
            m = HeuristicMCTS(game=game, simulations=sims, seed=seed * 13 + sims,
                              heur_leaf="v2_7", leaf_cfg=cfg)
            m.clear()
            visits = m.search(board)
            choices[name] = int(m.best_action(board))
            tot = sum(visits.values()) or 1
            dists[name] = {int(a): visits[a] / tot for a in visits}

        disagree = choices["h3200"] != choices["h6400"]

        # POLICY TARGET = h6400 visit dist, clipped to the snapshot mask (mirrors
        # selfplay.play_one_selfplay_game lines 287-307).
        policy = np.zeros(A, dtype=np.float32)
        kept = 0.0
        for a, p in dists["h6400"].items():
            if 0 <= a < A and mask[a]:
                policy[a] = float(p); kept += float(p)
        if kept > 0:
            policy /= kept
        else:
            policy[legal] = 1.0 / legal.size

        obs, scalars = gf.get_canonical_form(board, cur)
        # compact h6400 dist over legal for the metric (KL/lean); keep small
        h6400_legal = {int(a): round(float(policy[a]), 6) for a in legal if policy[a] > 0}

        row = {
            "gen_id": rec.get("gen_id"), "seed": seed, "ply": rec.get("ply"),
            "phase": rec.get("phase"), "k_remaining": rec.get("k_remaining"),
            "score_margin_abs": rec.get("score_margin_abs"),
            "meeples_free": rec.get("meeples_free"), "legal_n": int(legal.size),
            "h3200_choice": choices["h3200"], "h6400_choice": choices["h6400"],
            "disagree": bool(disagree),
            "h6400_dist": h6400_legal,
            # heavy arrays (popped out before the manifest is written)
            "_board": obs.astype(np.float32), "_scalars": scalars.astype(np.float32),
            "_policy": policy, "_mask": mask.astype(bool),
        }
        return row
    except Exception as e:
        return {"_error": f"{rec.get('gen_id')}: {type(e).__name__}: {e}"}


def _write_npz_shards(rows, split_dir: Path, chunk: int = 200):
    """Write train_iter.py-format npz under split_dir/iter_00/seed_NNN.npz."""
    it = split_dir / "iter_00"
    it.mkdir(parents=True, exist_ok=True)
    if not rows:
        return 0
    W = rows[0]["_board"].shape[-1]
    for ci in range(0, len(rows), chunk):
        grp = rows[ci:ci + chunk]
        n = len(grp)
        boards = np.stack([r["_board"] for r in grp])
        scalars = np.stack([r["_scalars"] for r in grp])
        policies = np.stack([r["_policy"] for r in grp])
        masks = np.stack([r["_mask"] for r in grp])
        A = policies.shape[1]
        np.savez_compressed(
            it / f"seed_{ci:06d}.npz",
            boards=boards, scalars=scalars, policies=policies,
            values=np.zeros(n, dtype=np.float32),
            valid_masks=masks,
            ownership=np.zeros((n, OWNERSHIP_PLANES, W, W), dtype=np.float32),
            aux_mask=np.ones(n, dtype=bool),
            group_id=np.full(n, -1, dtype=np.int64),
        )
    return len(rows)


def _write_manifest(rows, path: Path):
    with open(path, "w") as fh:
        for r in rows:
            d = {k: v for k, v in r.items() if not k.startswith("_")}
            fh.write(json.dumps(d) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--positions",
                    default=str(REPO / "measurement/deeper_search_ruler/multiphase_positions.jsonl"))
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--test-frac", type=float, default=0.15)
    ap.add_argument("--split-seed", type=int, default=7)
    ap.add_argument("--out", default=str(REPO / "measurement/hard_policy_repair"))
    args = ap.parse_args(argv)

    _provenance()
    recs = [json.loads(l) for l in open(args.positions)]
    if args.nshards > 1:
        recs = recs[args.shard::args.nshards]
    if args.limit:
        recs = recs[:args.limit]
    print(f"[mine] {len(recs)} roots (shard {args.shard}/{args.nshards}) "
          f"x (h3200+h6400 v2.9) W={args.workers}", flush=True)

    t0 = time.perf_counter()
    ctx = get_context("fork")
    rows, done = [], 0
    with ctx.Pool(args.workers, initializer=_worker_init) as pool:
        for r in pool.imap_unordered(_process, recs, chunksize=1):
            rows.append(r); done += 1
            if done % 50 == 0 or done == len(recs):
                el = time.perf_counter() - t0
                print(f"  {done}/{len(recs)} ({el/done:.2f}s/root, "
                      f"~{(len(recs)-done)*el/max(done,1)/60:.1f} min left)", flush=True)
    errs = [r for r in rows if "_error" in r]
    good = [r for r in rows if "_error" not in r]
    print(f"[mine] {len(good)} labeled, {len(errs)} errors, "
          f"{(time.perf_counter()-t0)/60:.1f} min", flush=True)
    if errs:
        print(f"[mine] sample errors: {[e['_error'] for e in errs[:3]]}", flush=True)

    hard = [r for r in good if r["disagree"]]
    ordn = [r for r in good if not r["disagree"]]
    print(f"[mine] hard(disagree)={len(hard)} ({len(hard)/max(len(good),1)*100:.0f}%)  "
          f"ordinary={len(ordn)}", flush=True)

    # Deterministic split of the HARD states into train/val/test.
    rng = np.random.RandomState(args.split_seed)
    idx = rng.permutation(len(hard))
    nv = int(round(args.val_frac * len(hard)))
    nt = int(round(args.test_frac * len(hard)))
    test_h = [hard[i] for i in idx[:nt]]
    val_h = [hard[i] for i in idx[nt:nt + nv]]
    train_h = [hard[i] for i in idx[nt + nv:]]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    # Hard splits -> training npz + manifests
    _write_npz_shards(train_h, out / "data" / "train")
    _write_npz_shards(val_h, out / "data" / "val")
    _write_npz_shards(test_h, out / "data" / "test")
    _write_manifest(train_h, out / "manifest_train.jsonl")
    _write_manifest(val_h, out / "manifest_val.jsonl")
    _write_manifest(test_h, out / "manifest_test.jsonl")
    # Ordinary states: npz (for the P2 mix) + manifest (for the Stage 5 regression set)
    _write_npz_shards(ordn, out / "data" / "ordinary")
    _write_manifest(ordn, out / "manifest_ordinary.jsonl")

    print(f"[mine] split: train_hard={len(train_h)} val_hard={len(val_h)} "
          f"test_hard={len(test_h)} ordinary={len(ordn)}", flush=True)
    print(f"[mine] wrote npz + manifests under {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
