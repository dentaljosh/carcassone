#!/usr/bin/env python3
"""High-gap distillation — Stage 2 GATE, part 1: per-action Q probe.

Re-label the existing replay-verified multiphase pool with the v2.9 deep teacher
HeuristicMCTS@6400 and extract, for each root, the per-legal-action **adjusted Q**
(root-player perspective) from the id-deduped root children — exactly the extraction
validated in probe_q_separation.py. The prior hard-policy-repair run stored only the
visit distribution; the decision-relevance question needs the Q-values.

NET-FREE (pure heuristic MCTS) → CPU-parallel. Emits two row-aligned outputs under
--out/qprobe:
  probe.jsonl          per-root: teacher_best (Q-argmax), ruler_choice (best_action),
                       q_best/q_second/q_gap_1_2/q_gap_1_med, action_q map, visit share,
                       teacher entropy, + all pool metadata
  data/iter_00/*.npz   boards/scalars/valid_masks (train_iter encode), SAME order as
                       probe.jsonl, so analyze_signal_density.py forwards the students
                       without re-replaying the engine.

Frozen v2.9 leaf (Bmild_cap8) env hard-set below before any carcassonne import.
"""
from __future__ import annotations
import os
os.environ["CARCASSONNE_V25_CAP"] = "8"
os.environ["CARCASSONNE_V25_OPP_CAP"] = "8"
os.environ["CARCASSONNE_V25_DROP_THREE_OPEN"] = "0"
os.environ["CARCASSONNE_V29_MEEPLE_CURVE"] = "-8,-4,-1,0,2,3,4,5"
os.environ["CARCASSONNE_V25_MEEPLE_K"] = "2.0"            # inert under the curve
os.environ["CARCASSONNE_USE_FLAT_LEAF"] = "1"
os.environ["CARCASSONNE_USE_CY_REPR"] = "1"
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

TEACHER_SIMS = 6400
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
        if legal.size < 2:
            return {"_error": f"{rec['gen_id']}: <2 legal"}

        m = HeuristicMCTS(game=game, simulations=TEACHER_SIMS, seed=seed * 13 + TEACHER_SIMS,
                          heur_leaf="v2_7", leaf_cfg=cfg)
        m.clear()
        visits = m.search(board)
        ruler_choice = int(m.best_action(board))               # ranks by (q, N)

        rk = game.string_representation(board)
        root = m._nodes[rk]
        action_q, action_n = {}, {}
        _seen = set()
        for a in sorted(root.children):
            c = root.children[a]
            if c.N <= 0 or id(c) in _seen:
                continue
            _seen.add(id(c))
            q = c.Q if c.player_to_move == root.player_to_move else -c.Q
            action_q[int(a)] = float(q)
            action_n[int(a)] = int(c.N)
        if len(action_q) < 2:
            return {"_error": f"{rec['gen_id']}: <2 visited children"}

        qs = sorted(action_q.values(), reverse=True)
        q_best, q_second = qs[0], qs[1]
        q_med = float(np.median(qs))
        teacher_best = max(action_q, key=lambda k: action_q[k])  # Q-argmax (gap-consistent)

        # teacher visit entropy + top share (over legal) — context, not a target
        tot = sum(visits.values()) or 1
        vshare = {int(a): visits[a] / tot for a in visits}
        ent = -sum(p * math.log(p) for p in vshare.values() if p > 0)
        top_share = max(vshare.values()) if vshare else 0.0

        obs, scalars = gf.get_canonical_form(board, cur)
        row = {
            "gen_id": rec.get("gen_id"), "seed": seed, "ply": rec.get("ply"),
            "phase": rec.get("phase"), "k_remaining": rec.get("k_remaining"),
            "score_margin_abs": rec.get("score_margin_abs"),
            "meeples_free": rec.get("meeples_free"), "legal_n": int(legal.size),
            "source_agent": rec.get("source_agent"),
            "teacher_best": teacher_best, "ruler_choice": ruler_choice,
            "q_best": round(q_best, 6), "q_second": round(q_second, 6),
            "q_gap_1_2": round(q_best - q_second, 6),
            "q_gap_1_med": round(q_best - q_med, 6),
            "q_range": round(q_best - qs[-1], 6),
            "top_share": round(top_share, 5), "entropy": round(ent, 4),
            "action_q": {int(a): round(v, 6) for a, v in action_q.items()},
            # heavy arrays (popped before manifest write)
            "_board": obs.astype(np.float32), "_scalars": scalars.astype(np.float32),
            "_mask": mask.astype(bool),
        }
        return row
    except Exception as e:
        return {"_error": f"{rec.get('gen_id')}: {type(e).__name__}: {e}"}


def _write_npz(rows, out_dir: Path, chunk: int = 200):
    it = out_dir / "iter_00"
    it.mkdir(parents=True, exist_ok=True)
    W = rows[0]["_board"].shape[-1]
    for ci in range(0, len(rows), chunk):
        grp = rows[ci:ci + chunk]
        n = len(grp)
        np.savez_compressed(
            it / f"seed_{ci:06d}.npz",
            boards=np.stack([r["_board"] for r in grp]),
            scalars=np.stack([r["_scalars"] for r in grp]),
            valid_masks=np.stack([r["_mask"] for r in grp]),
        )


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--positions",
                    default=str(REPO / "measurement/deeper_search_ruler/multiphase_positions.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", default=str(REPO / "measurement/high_gap_distillation/qprobe"))
    args = ap.parse_args(argv)

    _provenance()
    recs = [json.loads(l) for l in open(args.positions)]
    if args.limit:
        recs = recs[:args.limit]
    print(f"[probe] {len(recs)} roots x h{TEACHER_SIMS}_v2.9  W={args.workers}", flush=True)

    t0 = time.perf_counter()
    ctx = get_context("fork")
    rows = []
    done = 0
    with ctx.Pool(args.workers, initializer=_worker_init) as pool:
        for r in pool.imap_unordered(_process, recs, chunksize=1):
            rows.append(r); done += 1
            if done % 50 == 0 or done == len(recs):
                el = time.perf_counter() - t0
                print(f"  {done}/{len(recs)} ({el/done:.2f}s/root, "
                      f"~{(len(recs)-done)*el/max(done,1)/60:.1f} min left)", flush=True)

    errs = [r for r in rows if "_error" in r]
    good = [r for r in rows if "_error" not in r]
    print(f"[probe] {len(good)} labeled, {len(errs)} errors, "
          f"{(time.perf_counter()-t0)/60:.1f} min", flush=True)
    if errs:
        print(f"[probe] sample errors: {[e['_error'] for e in errs[:5]]}", flush=True)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    _write_npz(good, out / "data")
    with open(out / "probe.jsonl", "w") as fh:
        for r in good:
            fh.write(json.dumps({k: v for k, v in r.items() if not k.startswith("_")}) + "\n")

    # quick net-free read (Q-gap density, no students yet)
    gaps = np.array([r["q_gap_1_2"] for r in good])
    for thr in (0.005, 0.010, 0.020, 0.040):
        f = float((gaps >= thr).mean())
        print(f"  Q-gap >= {thr:.3f}:  {int((gaps>=thr).sum()):4d} / {len(good)}  ({f*100:.1f}%)", flush=True)
    print(f"  Q-gap mean {gaps.mean():.4f} median {np.median(gaps):.4f} "
          f"p90 {np.percentile(gaps,90):.4f}", flush=True)
    print(f"[probe] wrote {out/'probe.jsonl'} + npz under {out/'data'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
