#!/usr/bin/env python3
"""PROBE B §4A — matched fair@D vs clairvoyant@D VALUE TARGETS over the FULL
10,067 sibling-set pool (the controlled Gate-B diagnostic).
docs/PROBE_B_FAIR_INFO_SPEC.md §4A.

WHY A SEPARATE SCRIPT FROM build_fair_targets.py
------------------------------------------------
build_fair_targets.py is the §4 dynamic-RANGE kill-check: it samples the small
1616-root qprobe and compares the fair spread to the *h6400* clairvoyant action_q
already on the record. That h6400 reference is depth-6400 — using it as the §4A
baseline would CONFOUND depth (6400 vs the fair 800) with clairvoyance. §4A needs a
clean ONE-VARIABLE comparison, so this script:

  (a) reads roots from the FULL 10,067 sibling-set pool CL-037 used
      (qprobe_A/probe.jsonl joined to pool_A.jsonl for the checksum), in the SAME
      order → SAME roots + SAME group ordering as the CL-037 gate.
  (b) computes, per root and per child action, BOTH targets at a MATCHED depth D:
        - FAIR@D      : K determinizations of the known bag, fair (reshuffled,
                        fresh-tree-per-det = the fair_isolate pattern) HeuristicMCTS,
                        determinization-averaged child Q  (root-player POV).
        - CLAIRVOYANT@D: ONE non-determinized HeuristicMCTS on the TRUE deck (the
                        base MCTS descends the real upcoming tiles — it "sees" the
                        future), SAME leaf, SAME sims D. This is the matched
                        clairvoyant reference — depth held equal, ONLY clairvoyance
                        differs.
      The v2.9 root value is emitted for both too (root_value_fair / _clair).
  (c) supports --root-start / --root-count SHARDING so the full gen splits across
      boxes; merge = concatenate the per-shard jsonl (see --merge below).

The fair primitive (_reshuffled_board / _fair_root_targets) is imported from
build_fair_targets.py — NOT re-implemented. HeuristicMCTS has no fair_chance kwarg
(that flag lives on NeuralMCTS); the fair labels here use the v2.9 HEURISTIC leaf
teacher, so the fair behaviour is produced by the manual reshuffle+fresh-tree
pattern, which is exactly the fair_isolate semantics (clear-per-determinization).

OUTPUT (one jsonl row per successfully-labelled root; group order preserved):
  {seed, ply, phase, k_remaining, legal_n, group_idx (position in the 10,067 pool),
   n_fair_children, n_clair_children,
   fair_root_value, clair_root_value,
   fair_action_q:{a: q}, clair_action_q:{a: q},
   fair_action_range, clair_action_range, h6400_action_q:{a:q} (for reference)}

The retarget step (retarget_4a.py) matches these rows to the CL-037 dataset_both
aux.npz by (game_seed, ply) + action, swapping oracle_q → fair or clair. Everything
else in the dataset (obs planes, scalars, leaf_q, group_id, split) stays identical.

NET-FREE, CPU-parallel, nice -n 19.

USAGE
-----
  # one shard (roots [START, START+COUNT) of the 10,067 pool):
  nice -n 19 .venv/bin/python scripts/probe_b/build_fair_targets_4a.py \
      --root-start 0 --root-count 5034 --K 12 --sims 800 --workers 14 \
      --out measurement/probe_b_4a/shardA.jsonl

  # merge shards into one target file:
  .venv/bin/python scripts/probe_b/build_fair_targets_4a.py --merge \
      --shards measurement/probe_b_4a/shardA.jsonl measurement/probe_b_4a/shardB.jsonl \
      --out measurement/probe_b_4a/targets_full.jsonl
"""
from __future__ import annotations

import os
# --- frozen v2.9 (Bmild_cap8) leaf: byte-identical to build_fair_targets.py /
#     step1_dump.py so fair@D and clair@D use the SAME leaf as the CL-037 gate.
#     Must be set BEFORE any carcassonne import. ---
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
from collections import defaultdict
from pathlib import Path

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "probe_b"))

import numpy as np
from multiprocessing import get_context

from gen_endgame_positions import replay_to
from carcassonne_ai.mcts import HeuristicMCTS
# reuse the fair determinization primitive — DO NOT re-implement it:
from build_fair_targets import _fair_root_targets   # noqa: E402

HG = REPO / "measurement" / "high_gap_distillation"
QPROBE_A = HG / "scaled" / "qprobe_A" / "probe.jsonl"
POOL_A = HG / "scaled" / "pool_A.jsonl"

_W: dict = {}


# --------------------------------------------------------------------------- #
# Clairvoyant@D primitive: ONE non-determinized HeuristicMCTS on the TRUE deck.
# The base MCTS descends the engine's real upcoming tiles (fair_chance is a
# NeuralMCTS-only flag; the plain heuristic search already "sees" the future),
# so this is the matched clairvoyant reference at the SAME sims / SAME leaf.
# --------------------------------------------------------------------------- #
def _clair_root_targets(game, board, sims: int, seed: int, cfg):
    key = game.string_representation(board)
    m = HeuristicMCTS(game=game, simulations=sims, seed=seed,
                      heur_leaf="v2_7", leaf_cfg=cfg)
    m.clear()
    m.search(board)                      # descends the TRUE deck (clairvoyant)
    root = m._nodes[key]
    root_value = float(root.Q)           # root-player POV
    aggN: dict[int, float] = defaultdict(float)
    aggW: dict[int, float] = defaultdict(float)
    _seen = set()
    for a in sorted(root.children):
        c = root.children[a]
        if c.N <= 0 or id(c) in _seen:
            continue
        _seen.add(id(c))
        sw = c.W if c.player_to_move == root.player_to_move else -c.W
        aggN[int(a)] += c.N
        aggW[int(a)] += sw
    action_q = {a: (aggW[a] / aggN[a]) for a in aggN if aggN[a] > 0}
    return root_value, action_q, len(action_q)


# --------------------------------------------------------------------------- #
# Worker
# --------------------------------------------------------------------------- #
def _worker_init(K, sims):
    import eval_hybrid_handoff as EH
    _W["cfg"] = EH._heur_leaf_cfg(2.0)   # v2.9 Bmild_cap8 (matches CL-037 labels)
    _W["K"] = int(K)
    _W["sims"] = int(sims)


def _process(rec):
    try:
        seed, ply = int(rec["seed"]), int(rec["ply"])
        game, board = replay_to(seed, ply)
        # checksum-verify the replay landed on the canonical root (pool_A carries it)
        if rec.get("checksum") and game.string_representation(board) != rec["checksum"]:
            return {"_error": f"{seed}:{ply} checksum_mismatch"}
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask)
        if legal.size < 2:
            return {"_error": f"{seed}:{ply} <2 legal"}

        cfg = _W["cfg"]; K = _W["K"]; sims = _W["sims"]

        # FAIR@D (determinization-averaged, fresh-tree-per-det = fair_isolate pattern)
        fair_rv, _per_det, fair_aq, n_fair = _fair_root_targets(
            game, board, K, sims, seed * 13 + ply, cfg)
        # CLAIRVOYANT@D (single true-deck search, SAME leaf, SAME sims)
        clair_rv, clair_aq, n_clair = _clair_root_targets(
            game, board, sims, seed * 977 + ply, cfg)

        if n_fair < 2 or n_clair < 2:
            return {"_error": f"{seed}:{ply} <2 children (fair={n_fair} clair={n_clair})"}

        fair_qs = sorted(fair_aq.values(), reverse=True)
        clair_qs = sorted(clair_aq.values(), reverse=True)
        h6400 = {int(a): float(v) for a, v in rec.get("action_q", {}).items()}

        return {
            "seed": seed, "ply": ply, "phase": rec.get("phase"),
            "k_remaining": rec.get("k_remaining"), "legal_n": int(legal.size),
            "group_idx": int(rec["group_idx"]),
            "n_fair_children": n_fair, "n_clair_children": n_clair,
            "fair_root_value": fair_rv, "clair_root_value": clair_rv,
            "fair_action_q": {int(a): float(v) for a, v in fair_aq.items()},
            "clair_action_q": {int(a): float(v) for a, v in clair_aq.items()},
            "fair_action_range": float(fair_qs[0] - fair_qs[-1]),
            "clair_action_range": float(clair_qs[0] - clair_qs[-1]),
            "h6400_action_q": h6400,
        }
    except Exception as e:  # noqa: BLE001
        return {"_error": f"{rec.get('seed')}:{rec.get('ply')} {type(e).__name__}: {e}"}


# --------------------------------------------------------------------------- #
# The FULL 10,067 pool loader (SAME join step1_dump.py uses → SAME roots/order).
# --------------------------------------------------------------------------- #
def _load_full_pool():
    checks = {}
    for line in open(POOL_A):
        r = json.loads(line); checks[(r["seed"], r["ply"])] = r["checksum"]
    recs = []
    for i, line in enumerate(open(QPROBE_A)):
        r = json.loads(line); key = (r["seed"], r["ply"])
        if key in checks:
            r["checksum"] = checks[key]
        r["group_idx"] = len(recs)     # position == CL-037 group ordering
        recs.append(r)
    return recs


# --------------------------------------------------------------------------- #
# Merge
# --------------------------------------------------------------------------- #
def _merge(shards, out):
    seen = set(); rows = []
    for sh in shards:
        for line in open(sh):
            r = json.loads(line)
            gi = r["group_idx"]
            if gi in seen:
                continue
            seen.add(gi); rows.append(r)
    rows.sort(key=lambda r: r["group_idx"])
    with open(out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"[merge] {len(shards)} shards -> {len(rows)} unique roots -> {out}", flush=True)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="build_fair_targets_4a")
    ap.add_argument("--root-start", type=int, default=0,
                    help="first root index in the 10,067 pool (inclusive)")
    ap.add_argument("--root-count", type=int, default=0,
                    help="number of roots to label from --root-start (0 = to end)")
    ap.add_argument("--K", type=int, default=12, help="fair determinizations per root")
    ap.add_argument("--sims", type=int, default=800, help="matched depth D (fair AND clair)")
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--out", type=str, required=True, help="output jsonl (this shard)")
    ap.add_argument("--merge", action="store_true", help="merge mode (concat --shards)")
    ap.add_argument("--shards", nargs="*", default=[], help="shard jsonls to merge")
    args = ap.parse_args(argv)

    if args.merge:
        return _merge(args.shards, args.out)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pool = _load_full_pool()
    n_total = len(pool)
    end = n_total if args.root_count <= 0 else min(n_total, args.root_start + args.root_count)
    shard = pool[args.root_start:end]
    print(f"[4a] full pool={n_total} | shard roots [{args.root_start}, {end}) = "
          f"{len(shard)} | K={args.K} sims={args.sims} workers={args.workers}", flush=True)
    print(f"[4a] cost ~= roots*(K+1)*sims = "
          f"{len(shard)*(args.K+1)*args.sims:,} leaf searches", flush=True)

    t0 = time.perf_counter()
    ctx = get_context("spawn")
    rows, errs = [], []
    with ctx.Pool(processes=args.workers, initializer=_worker_init,
                  initargs=(args.K, args.sims)) as pool_:
        done = 0
        with open(args.out, "w") as fh:
            for r in pool_.imap_unordered(_process, shard, chunksize=1):
                done += 1
                if "_error" in r:
                    errs.append(r["_error"])
                else:
                    rows.append(r)
                    fh.write(json.dumps(r) + "\n")
                    fh.flush()
                if done % 10 == 0 or done == len(shard):
                    el = time.perf_counter() - t0
                    print(f"  {done}/{len(shard)} ({el/done:.2f}s/root, "
                          f"~{(len(shard)-done)*el/done/60:.1f} min left) "
                          f"| ok={len(rows)} err={len(errs)}", flush=True)

    dt = time.perf_counter() - t0
    print(f"\n[4a] shard done: ok={len(rows)} err={len(errs)} in {dt/60:.1f} min "
          f"({dt/max(1,len(shard)):.2f}s/root) -> {args.out}", flush=True)
    if errs:
        print(f"[4a] first 5 errors:")
        for e in errs[:5]:
            print("  ", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
