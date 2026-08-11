#!/usr/bin/env python3
"""Step-1 representation gate — SINGLE-PASS multi-mode dataset builder.

Identical enumeration / POV / labels to step1_dump.py (and byte-identical to the
CL-033 dump_dataset.py for the baseline channels), but it computes the expensive
shared work — replay_to, child enumeration, get_canonical_form, leaf eval — ONCE
per child and emits the baseline arrays plus the appended farm planes and bag
scalars as SEPARATE arrays. The four primary modes (none/farm/bag/both) are then
just column slices of one npz; `both_shuffled` is derived post-hoc. This avoids
re-running the (dominant) replay+encode cost four times.

Writes <root>/dataset_<mode>/rows.npz for mode in {none,farm,bag,both,both_shuffled}.
NET-FREE, CPU-parallel (W30).
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
sys.path.insert(0, str(REPO / "scripts" / "feature_planes_gate"))
import eval_hybrid_handoff as EH
from gen_endgame_positions import replay_to
from carcassonne_ai.virtual_score_v2 import virtual_score_v2
from step1_planes import farm_connectivity_planes, bag_histogram, N_FARM_PLANES, N_BAG

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
        obs_l, sca_l, farm_l, bag_l, h6_l, leaf_l = [], [], [], [], [], []
        for a in legal:
            a = int(a)
            if a not in aq:
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
            off = child.offset; Wd = off.size
            fp = farm_connectivity_planes(child.state, root_player, off, Wd)
            bag = bag_histogram(child.state)
            obs_l.append(obs.astype(np.float16))
            sca_l.append(np.asarray(sca, dtype=np.float16))
            farm_l.append(fp.astype(np.float16))
            bag_l.append(bag.astype(np.float16))
            h6_l.append(aq[a])
            leaf_l.append(float(leaf))

        if len(h6_l) < 2:
            return {"_error": f"{seed}:{ply} <2 mapped children"}
        return {
            "seed": seed, "ply": ply, "phase": rec.get("phase", "?"),
            "q_gap": float(rec.get("q_gap_1_2", 0.0)),
            "obs": np.stack(obs_l), "sca": np.stack(sca_l),
            "farm": np.stack(farm_l), "bag": np.stack(bag_l),
            "h6": np.asarray(h6_l, dtype=np.float32),
            "leaf": np.asarray(leaf_l, dtype=np.float32),
        }
    except Exception as e:
        return {"_error": f"{rec.get('seed')}:{rec.get('ply')} {type(e).__name__}: {e}"}


def _save(outd, obs, sca, oq, leaf, grp, gs, ply, ph, gap, meta):
    outd.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        outd / "rows.npz",
        child_obs=obs, child_scalars=sca, oracle_q=oq, leaf_q=leaf,
        group_id=grp, game_seed=gs, ply=ply, phase=ph, q_gap=gap)
    (outd / "meta.json").write_text(json.dumps(meta, indent=2))


def _cross_group_perm(grp, rng):
    """Permutation that maps every row to a row in a DIFFERENT group."""
    n = len(grp)
    order = rng.permutation(n)
    perm = np.roll(order, 1)[np.argsort(order)]
    for i in range(n):
        if grp[perm[i]] == grp[i]:
            for j in range(n):
                if grp[perm[j]] != grp[i] and grp[perm[i]] != grp[j]:
                    perm[i], perm[j] = perm[j], perm[i]
                    break
    return perm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qprobe", default=str(HG / "scaled" / "qprobe_A" / "probe.jsonl"))
    ap.add_argument("--pool", default=str(HG / "scaled" / "pool_A.jsonl"))
    ap.add_argument("--root", default="/mnt/c/carc-shared/feature_planes_gate")
    ap.add_argument("--workers", type=int, default=30)
    ap.add_argument("--limit", type=int, default=0)
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
    if args.limit:
        recs = recs[: args.limit]
    print(f"[load] {len(recs)}/{n_avail} sibling sets workers={args.workers}", flush=True)

    t0 = time.time()
    OBS, SCA, FARM, BAG, H6, LEAF, GID, GS, PLY, PH, GAP = ([] for _ in range(11))
    gid = 0; nerr = 0; nrow = 0
    ctx = get_context("fork")
    with ctx.Pool(args.workers, initializer=_worker_init) as pool:
        for i, out in enumerate(pool.imap_unordered(_process, recs, chunksize=8)):
            if "_error" in out:
                nerr += 1
                continue
            m = out["obs"].shape[0]
            OBS.append(out["obs"]); SCA.append(out["sca"])
            FARM.append(out["farm"]); BAG.append(out["bag"])
            H6.append(out["h6"]); LEAF.append(out["leaf"])
            GID.append(np.full(m, gid, np.int32)); GS.append(np.full(m, out["seed"], np.int64))
            PLY.append(np.full(m, out["ply"], np.int16)); GAP.append(np.full(m, out["q_gap"], np.float32))
            PH.append(np.array([out["phase"]] * m, dtype="<U12"))
            gid += 1; nrow += m
            if (i + 1) % 2000 == 0:
                print(f"  {i+1}/{len(recs)} groups={gid} rows={nrow} err={nerr} "
                      f"{time.time()-t0:.0f}s", flush=True)
    print(f"[enum-done] groups={gid} rows={nrow} err={nerr} in {time.time()-t0:.0f}s", flush=True)

    obs = np.concatenate(OBS); sca = np.concatenate(SCA)
    farm = np.concatenate(FARM); bag = np.concatenate(BAG)
    oq = np.concatenate(H6); leaf = np.concatenate(LEAF)
    grp = np.concatenate(GID); gs = np.concatenate(GS)
    ply = np.concatenate(PLY); ph = np.concatenate(PH); gap = np.concatenate(GAP)

    obs_farm = np.concatenate([obs, farm], axis=1)
    sca_bag = np.concatenate([sca, bag], axis=1)

    base_meta = {"n_rows": int(nrow), "n_groups": int(gid), "n_groups_avail": int(n_avail),
                 "n_games": int(len(set(gs.tolist()))),
                 "teacher": "h6400_v2.9", "leaf": "v2.9_bmild_cap8",
                 "v29_hash": "7fc930b82801cb43", "source": args.qprobe, "n_err": int(nerr)}
    root = Path(args.root)

    def meta(mode, o, s, nf, nb, ncsame=-1):
        m = dict(base_meta); m.update(
            {"mode": mode, "obs_shape": list(o.shape[1:]), "n_scalar": int(s.shape[1]),
             "n_farm_planes": nf, "n_bag_scalars": nb, "neg_control_same_group": ncsame})
        return m

    _save(root / "dataset_none", obs, sca, oq, leaf, grp, gs, ply, ph, gap,
          meta("none", obs, sca, 0, 0))
    _save(root / "dataset_farm", obs_farm, sca, oq, leaf, grp, gs, ply, ph, gap,
          meta("farm", obs_farm, sca, N_FARM_PLANES, 0))
    _save(root / "dataset_bag", obs, sca_bag, oq, leaf, grp, gs, ply, ph, gap,
          meta("bag", obs, sca_bag, 0, N_BAG))
    _save(root / "dataset_both", obs_farm, sca_bag, oq, leaf, grp, gs, ply, ph, gap,
          meta("both", obs_farm, sca_bag, N_FARM_PLANES, N_BAG))

    # negative control: scramble the appended farm planes + bag scalars across groups
    rng = np.random.default_rng(12345)
    perm = _cross_group_perm(grp, rng)
    obs_farm_sh = obs_farm.copy()
    obs_farm_sh[:, obs.shape[1]:, :, :] = obs_farm[perm][:, obs.shape[1]:, :, :]
    sca_bag_sh = sca_bag.copy()
    sca_bag_sh[:, sca.shape[1]:] = sca_bag[perm][:, sca.shape[1]:]
    ncsame = int(np.sum(grp[perm] == grp))
    print(f"[neg-control] residual same-group={ncsame}/{len(grp)}", flush=True)
    _save(root / "dataset_both_shuffled", obs_farm_sh, sca_bag_sh, oq, leaf, grp, gs, ply, ph, gap,
          meta("both_shuffled", obs_farm_sh, sca_bag_sh, N_FARM_PLANES, N_BAG, ncsame))

    print(f"[done] wrote 5 datasets to {root} in {time.time()-t0:.0f}s total", flush=True)


if __name__ == "__main__":
    main()
