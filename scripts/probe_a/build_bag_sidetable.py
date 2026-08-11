#!/usr/bin/env python3
"""PROBE A — MILESTONE 2.5 bag/deck-composition side-table (for the 3A gate).

The 3A independence gate needs the 32-dim bag histogram as a BOARD-LEVEL
side-input to the structured head. The existing component dataset
(build_component_dataset.py) has no bag column. Rather than rebuild the whole
(N,24) matrix, we emit ONLY the (n_boards, 32) bag histogram, board-for-board
ALIGNED to component_ds.npz by REUSING build_component_dataset's exact
enumeration (`replay_to(seed,ply,checksum)` + the same legal / dedup / skip-
terminal loop). Emission order is identical, so bag[k] is the bag for board k of
component_ds (same board_offsets index).

We REUSE the existing 32-dim extraction from step2_leaf's dependency chain
(step1_planes.bag_histogram — the frozen 32-type census that step2_leaf's
build_dataset.bag_histogram is itself imported from); we do NOT rebuild it.

Alignment guard: we also re-emit oracle_q + game_seed per board and assert they
match component_ds.npz byte-for-byte before writing. If the enumeration ever
drifts, this aborts LOUDLY.

  nice -n 19 .venv/bin/python -u scripts/probe_a/build_bag_sidetable.py \
      --ds /home/doctor/carc_probe_a/component_ds --workers 30
"""
from __future__ import annotations
import os
# --- GUARD env — VERBATIM from build_component_dataset.py (v2.9 7fc930b8) ------ #
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

import argparse, json, sys, time
from pathlib import Path
from multiprocessing import get_context

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "feature_planes_gate"))
sys.path.insert(0, str(REPO / "scripts" / "probe_a"))

import eval_hybrid_handoff as EH
from gen_endgame_positions import replay_to
# The FROZEN 32-type bag histogram (Step-1; asserts 32 types / 72 tiles at import).
# This is the SAME extraction step2_leaf.build_dataset.bag_histogram is imported
# from — reused verbatim, not rebuilt.
from step1_planes import bag_histogram, N_BAG  # noqa: E402

HG = REPO / "measurement" / "high_gap_distillation"
_W: dict = {}


def _worker_init():
    _W["game"] = EH.Game(enable_legal_moves_cache=True, include_farm_scalars=True)


def _process(rec):
    """MIRRORS build_component_dataset._process EXACTLY (same enumeration order),
    but emits the 32-dim bag + oracle_q + seed per non-terminal child board."""
    try:
        seed = int(rec["seed"]); ply = int(rec["ply"])
        game, board = replay_to(seed, ply)
        if game.string_representation(board) != rec["checksum"]:
            return {"_error": f"{seed}:{ply} checksum_mismatch"}
        pstate = board.state
        root_player = pstate.current_player
        aq = {int(k): float(v) for k, v in rec["action_q"].items()}
        legal = np.flatnonzero(game.get_valid_moves(board)).astype(int)
        if legal.size < 2:
            return {"_error": f"{seed}:{ply} <2 legal"}

        bags, oqs = [], []
        seen = set()
        for a in legal:
            a = int(a)
            if a not in aq:
                continue
            child, _ = game.get_next_state(board, a)
            cs = game.string_representation(child)
            if cs in seen:
                continue
            seen.add(cs)
            cstate = child.state
            ended = game.get_game_ended(child, root_player)
            if ended != 0:
                continue
            bags.append(bag_histogram(cstate).astype(np.float32))
            oqs.append(aq[a])
        if len(bags) < 1:
            return {"_error": f"{seed}:{ply} 0 non-terminal children"}
        # emit the WHOLE set as one record (seed,ply key) so we can join to the ref
        # by (seed,ply,within-set-rank) — ORDER-INDEPENDENT of imap completion order.
        return {"seed": seed, "ply": ply, "bags": bags, "oracle_q": oqs}
    except Exception as e:
        import traceback
        return {"_error": f"{rec.get('seed')}:{rec.get('ply')} {type(e).__name__}: {e}",
                "_tb": traceback.format_exc()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ds", default="/home/doctor/carc_probe_a/component_ds",
                    help="component_ds dir (aligns to its board order + validates)")
    ap.add_argument("--probe", default=str(HG / "scaled" / "qprobe_A" / "probe.jsonl"))
    ap.add_argument("--pool", default=str(HG / "scaled" / "pool_A.jsonl"))
    ap.add_argument("--out", default=None, help="default: <ds>/bag_sidetable.npz")
    ap.add_argument("--workers", type=int, default=30)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    dsdir = Path(args.ds)
    out = Path(args.out) if args.out else dsdir / "bag_sidetable.npz"
    ref = np.load(dsdir / "component_ds.npz", allow_pickle=False)
    ref_oq = ref["oracle_q"].astype(np.float32)
    ref_gs = ref["game_seed"].astype(np.int64)
    ref_ply = ref["ply"].astype(np.int64)
    ref_gid = ref["group_id"].astype(np.int64)
    n_ref = len(ref_oq)
    limited = bool(args.limit)
    print(f"[align] component_ds has {n_ref} boards; bag joined by (seed,ply,rank).")

    checks = {}
    for line in open(args.pool):
        r = json.loads(line); checks[(r["seed"], r["ply"])] = r["checksum"]
    recs = []
    for line in open(args.probe):
        r = json.loads(line); key = (r["seed"], r["ply"])
        if key in checks:
            r["checksum"] = checks[key]; recs.append(r)
    if args.limit:
        recs = recs[: args.limit]
    print(f"[load] {len(recs)} sibling sets  workers={args.workers}")

    # Collect per-set bag lists keyed by (seed,ply). Order-INDEPENDENT: we then
    # place each board into the ref's slot by (seed,ply,within-set-rank). Both
    # builders share the IDENTICAL `for a in legal` + dedup + skip-terminal loop,
    # so within-set rank order matches board-for-board.
    t0 = time.time()
    by_key: dict = {}       # (seed,ply) -> (bags list, oq list)
    nerr = 0; sample_errs = []
    ctx = get_context("fork")
    with ctx.Pool(args.workers, initializer=_worker_init) as pool:
        for i, o in enumerate(pool.imap_unordered(_process, recs, chunksize=8)):
            if "_error" in o:
                nerr += 1
                if len(sample_errs) < 8:
                    sample_errs.append(o["_error"])
                continue
            by_key[(o["seed"], o["ply"])] = (o["bags"], o["oracle_q"])
            if (i + 1) % 2000 == 0:
                print(f"  {i+1}/{len(recs)} sets={len(by_key)} err={nerr} "
                      f"{time.time()-t0:.0f}s", flush=True)
    dt = time.time() - t0
    n_boards = sum(len(v[0]) for v in by_key.values())
    print(f"[done] sets={len(by_key)} boards={n_boards} err={nerr} in {dt:.0f}s")
    if sample_errs:
        print("  sample errors:", sample_errs)

    # ---- JOIN into ref order by (seed,ply,within-set-rank). ------------------- #
    # ref boards for a given (seed,ply) are contiguous (one group) and in emission
    # rank order; assign the r-th ref board of a (seed,ply) the r-th produced bag.
    bag_out = np.zeros((n_ref, N_BAG), np.float32)
    oq_join = np.zeros(n_ref, np.float32)
    rank_ctr: dict = {}
    filled = np.zeros(n_ref, bool)
    n_missing_key = 0
    for k in range(n_ref):
        key = (int(ref_gs[k]), int(ref_ply[k]))
        rank = rank_ctr.get(key, 0)
        rank_ctr[key] = rank + 1
        v = by_key.get(key)
        if v is None:
            n_missing_key += 1
            continue          # only expected under --limit (partial set of keys)
        bags, oqs = v
        if rank >= len(bags):
            raise SystemExit(f"RANK OVERFLOW at ref board {k} key={key} "
                             f"rank={rank} >= produced {len(bags)} — enumeration drift.")
        bag_out[k] = bags[rank]
        oq_join[k] = oqs[rank]
        filled[k] = True

    fmask = filled
    n_filled = int(fmask.sum())
    oq_ok = np.allclose(oq_join[fmask], ref_oq[fmask], atol=1e-6)
    print(f"[align-check] filled {n_filled}/{n_ref} boards; oracle_q match on filled={oq_ok}"
          + (f"  (limit mode: {n_missing_key} boards from un-processed sets left zero)" if limited else ""))
    if not oq_ok:
        n_mis = int(np.sum(~np.isclose(oq_join[fmask], ref_oq[fmask], atol=1e-6)))
        raise SystemExit(
            f"BAG SIDE-TABLE MISALIGNED: {n_mis} oracle_q mismatches on the "
            f"(seed,ply,rank) join. Within-set board order drifted from "
            f"build_component_dataset — do NOT use.")
    if not limited and n_filled != n_ref:
        raise SystemExit(f"INCOMPLETE: only {n_filled}/{n_ref} boards filled without --limit.")

    np.savez_compressed(out, bag=bag_out, oracle_q=oq_join, game_seed=ref_gs,
                        filled=filled)
    print(f"[out] {out}  bag.shape={bag_out.shape}  (JOIN by (seed,ply,rank) PASSED)")
    print(f"      bag fresh-frac mean over filled = {bag_out[fmask].mean():.3f}  "
          f"(endgame boards -> low)")


if __name__ == "__main__":
    main()
