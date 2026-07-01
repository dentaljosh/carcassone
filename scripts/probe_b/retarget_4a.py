#!/usr/bin/env python3
"""PROBE B §4A — RETARGET the CL-037 dataset onto fair@D / clair@D value targets.
docs/PROBE_B_FAIR_INFO_SPEC.md §4A.

THE ONE-VARIABLE SWAP
---------------------
CL-037's gate trained a RankNet on dataset_both, using oracle_q (the h6400
clairvoyant teacher action_q) as the ranking target and leaf_q as the α=0 leaf.
§4A asks: does that gate's verdict (α≈0 inert; bag-ablation −19.7%) change when the
value TARGET is swapped from clairvoyant to FAIR — everything else identical.

This script builds a NEW dataset directory whose obs planes / scalars / leaf_q /
group_id / game_seed / ply / phase are BYTE-IDENTICAL to the source CL-037 dataset
(same rows, same order), and whose ONLY changed array is oracle_q, rewritten to the
§4A fair@D or clair@D per-child action target. step1_train.py then runs UNCHANGED on
it — so fair-vs-clair is a pure target swap, matched on depth D (unlike the h6400
oracle_q, which is depth-6400).

ROW → ACTION reconstruction (deterministic, verified): step1_dump._process
enumerated each group's rows as sorted(legal) filtered to teacher-Q'd children with
string-repr dedup. Replaying that exact enumeration from replay_to(seed, ply)
recovers the per-row action, in row order, bit-for-bit (checked: group0 oracle_q
reproduced to the decimal). Each row's oracle_q is then set to
{fair,clair}_action_q[action] from the §4A targets file. Rows whose group is not in
the targets file are DROPPED (lets a 150-root subset build a small dataset); rows
whose action is missing from the target dict are dropped and the group is kept only
if ≥2 rows survive (mirrors step1_dump's <2-children guard).

USAGE
-----
  # build the two sibling datasets (fair + clair) from a targets jsonl:
  nice -n 19 .venv/bin/python scripts/probe_b/retarget_4a.py \
      --src-dataset /home/doctor/carc_step1_gate/dataset_both \
      --targets measurement/probe_b_4a/targets_n150.jsonl \
      --target-kind fair  --out /home/doctor/carc_step1_gate/ds4a_fair_n150
  nice -n 19 .venv/bin/python scripts/probe_b/retarget_4a.py \
      --src-dataset /home/doctor/carc_step1_gate/dataset_both \
      --targets measurement/probe_b_4a/targets_n150.jsonl \
      --target-kind clair --out /home/doctor/carc_step1_gate/ds4a_clair_n150

NET-FREE, CPU-parallel (row→action replay), nice -n 19.
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

import argparse
import json
import sys
import time
from pathlib import Path
from multiprocessing import get_context

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "feature_planes_gate"))

_W: dict = {}


def _worker_init():
    import eval_hybrid_handoff as EH
    _W["game"] = EH.Game(enable_legal_moves_cache=True, include_farm_scalars=True)


def _row_actions(rec):
    """Replay step1_dump's exact per-row action enumeration for one (seed, ply).
    Returns the ordered list of actions (row order) whose oracle_q the aux holds.
    """
    from gen_endgame_positions import replay_to
    try:
        seed = int(rec["seed"]); ply = int(rec["ply"])
        game = _W["game"]
        _, board = replay_to(seed, ply)
        aq_keys = set(rec["_aq_keys"])  # h6400 action_q keys == teacher-Q'd children
        legal = np.flatnonzero(game.get_valid_moves(board)).astype(int)
        seen = set(); acts = []
        for a in legal:
            a = int(a)
            if a not in aq_keys:
                continue
            child, _ = game.get_next_state(board, a)
            cs = game.string_representation(child)
            if cs in seen:
                continue
            seen.add(cs); acts.append(a)
        return {"seed": seed, "ply": ply, "acts": acts, "group_idx": rec["group_idx"]}
    except Exception as e:  # noqa: BLE001
        return {"_error": f"{rec.get('seed')}:{rec.get('ply')} {type(e).__name__}: {e}",
                "group_idx": rec.get("group_idx")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="retarget_4a")
    ap.add_argument("--src-dataset", required=True,
                    help="CL-037 dataset dir (dataset_both) — obs/scalars/leaf reused")
    ap.add_argument("--targets", required=True, help="§4A targets jsonl (build_fair_targets_4a)")
    ap.add_argument("--target-kind", choices=["fair", "clair"], required=True)
    ap.add_argument("--out", required=True, help="new dataset dir")
    ap.add_argument("--workers", type=int, default=14)
    args = ap.parse_args(argv)

    src = Path(args.src_dataset)
    meta = json.loads((src / "meta.json").read_text())
    aux = np.load(src / "aux.npz", allow_pickle=False)
    C = int(meta["n_chan"]); W = int(meta["W"])
    obs = np.memmap(src / meta.get("obs_file", "child_obs.f16"),
                    dtype=np.float16, mode="r",
                    shape=(int(meta["n_rows"]), C, W, W))

    gid = aux["group_id"]; gs = aux["game_seed"]; ply = aux["ply"]
    oq = aux["oracle_q"].astype(np.float32); lq = aux["leaf_q"].astype(np.float32)
    sca = np.asarray(aux["child_scalars"]); phase = aux["phase"]; qgap = aux["q_gap"]

    # rows for each group_id, in row order
    order = np.argsort(gid, kind="stable")
    grp_rows: dict[int, list[int]] = {}
    for i in order:
        grp_rows.setdefault(int(gid[i]), []).append(int(i))

    # load §4A targets keyed by (game_seed, ply).  NOTE: the CL-037 aux.npz group_id
    # is assigned in imap_unordered COMPLETION order, NOT the qprobe order, so the
    # targets file's group_idx (qprobe position) does NOT equal the aux group_id.
    # Match on (seed, ply), which is unique across all 10,067 roots.
    tk = f"{args.target_kind}_action_q"
    tgt_by_sp = {}
    for line in open(args.targets):
        r = json.loads(line)
        tgt_by_sp[(int(r["seed"]), int(r["ply"]))] = r
    # map each source group_id -> its (seed, ply)
    grp_sp = {g: (int(gs[rows_i[0]]), int(ply[rows_i[0]]))
              for g, rows_i in grp_rows.items()}
    covered = [g for g, sp in grp_sp.items() if sp in tgt_by_sp]
    print(f"[retarget] src groups={len(grp_rows)} | targets file roots={len(tgt_by_sp)} | "
          f"matched src groups={len(covered)} | kind={args.target_kind}", flush=True)

    # build the (seed, ply, aq_keys) worklist ONLY for matched groups, so the
    # row→action replay is limited to the covered subset.  tgt_rows re-keys the
    # matched targets by SOURCE group_id for the assembly loop below.
    tgt_rows = {}
    work = []
    for g in covered:
        sp = grp_sp[g]
        r = tgt_by_sp[sp]
        tgt_rows[g] = r
        aq_keys = list((r.get("h6400_action_q") or r.get(tk)).keys())
        work.append({"seed": sp[0], "ply": sp[1],
                     "group_idx": g, "_aq_keys": [int(k) for k in aq_keys]})

    t0 = time.perf_counter()
    ctx = get_context("fork")
    act_map = {}; errs = []
    with ctx.Pool(args.workers, initializer=_worker_init) as pool:
        for out in pool.imap_unordered(_row_actions, work, chunksize=8):
            if "_error" in out:
                errs.append(out["_error"]); continue
            act_map[out["group_idx"]] = out["acts"]
    print(f"[retarget] row→action replay: {len(act_map)} groups in "
          f"{time.perf_counter()-t0:.0f}s (err={len(errs)})", flush=True)

    # assemble the retargeted subset, group by group (obs streamed to disk)
    outd = Path(args.out); outd.mkdir(parents=True, exist_ok=True)
    fobs = open(outd / "child_obs.f16", "wb")
    SCA, OQ, LEAF, GID, GS, PLY, PH, GAP = [], [], [], [], [], [], [], []
    new_gid = 0; nrow = 0; skipped = 0
    for g_idx in sorted(act_map):
        rows_i = grp_rows[g_idx]
        acts = act_map[g_idx]
        if len(acts) != len(rows_i):
            # enumeration drift (should not happen — verified reproducible). Skip loudly.
            skipped += 1
            continue
        tgt = tgt_rows[g_idx][f"{args.target_kind}_action_q"]
        tgt = {int(k): float(v) for k, v in tgt.items()}
        keep = [(ri, a) for ri, a in zip(rows_i, acts) if a in tgt]
        if len(keep) < 2:
            skipped += 1
            continue
        row_idx = np.array([ri for ri, _ in keep])
        new_oq = np.array([tgt[a] for _, a in keep], dtype=np.float32)
        # obs for these rows (gather from the full memmap → contiguous f16)
        o = np.ascontiguousarray(obs[row_idx], dtype=np.float16)
        fobs.write(o.tobytes())
        m = len(keep)
        SCA.append(sca[row_idx]); OQ.append(new_oq); LEAF.append(lq[row_idx])
        GID.append(np.full(m, new_gid, np.int32)); GS.append(gs[row_idx])
        PLY.append(ply[row_idx]); PH.append(phase[row_idx]); GAP.append(qgap[row_idx])
        new_gid += 1; nrow += m
    fobs.close()

    np.savez(outd / "aux.npz",
             child_scalars=np.concatenate(SCA), oracle_q=np.concatenate(OQ),
             leaf_q=np.concatenate(LEAF), group_id=np.concatenate(GID),
             game_seed=np.concatenate(GS), ply=np.concatenate(PLY),
             phase=np.concatenate(PH), q_gap=np.concatenate(GAP))
    new_meta = dict(meta)
    new_meta.update({
        "n_rows": int(nrow), "n_groups": int(new_gid),
        "obs_file": "child_obs.f16",
        "probe_b_4a_target_kind": args.target_kind,
        "probe_b_4a_targets_file": str(args.targets),
        "probe_b_4a_src_dataset": str(src),
        "teacher": f"probe_b_4a_{args.target_kind}@D (retargeted; NOT h6400)",
    })
    (outd / "meta.json").write_text(json.dumps(new_meta, indent=2))
    print(f"[retarget] wrote {new_gid} groups / {nrow} rows (skipped {skipped}) "
          f"kind={args.target_kind} -> {outd}", flush=True)
    print(f"[retarget] oracle_q now = {args.target_kind}@D action target; "
          f"leaf_q/obs/scalars/split UNCHANGED from CL-037.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
