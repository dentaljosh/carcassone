#!/usr/bin/env python3
"""Value Resurrection Pilot — Stage 1+2+3: build sibling sets + LEAF AUDIT (gate 1).

Reuses the EXISTING h6400_v2.9 sibling labels (no new search):
  - qprobe_A/probe.jsonl  : per-root h6400_v2.9 `action_q` (root-POV adjusted Q over the
                            id-deduped *visited* legal children), teacher_best, q_gap_1_2, ...
  - pool_A.jsonl          : the replay-verified root metadata (`checksum`, phase, scores, ...)
joined on (seed, ply)  →  10,067 sibling sets.

For each root S we reconstruct (game, board) = replay_to(seed, ply), enumerate the legal
children (id-deduped, canonical = lowest action id per unique child state — SAME convention
the labeler used), and score each child with the FROZEN v2.9 leaf (Bmild_cap8, config_hash
7fc930b82801cb43), root-player POV:
    L0(child) = -tanh( virtual_score_v2(child.state, child.state.current_player, cfg) / 15 )
(terminal child → -clip(true terminal score sign); leaf-independent).

Then we ask the Stage-3 question: **does the v2.9 leaf rank these siblings like h6400?**
Metrics per root, computed over the TEACHER-VISITED children (the set h6400 has a Q for —
favourable to the leaf, since unvisited children are ones h6400 pruned):
    top1   = leaf-argmax child == teacher-argmax child
    top3   = teacher-best in the leaf's top-3 by L0
    tau    = Kendall-tau(L0, teacher_Q) over the sibling set
    regret = teacher_Q[teacher_best] - teacher_Q[leaf_pick]   (>=0, in teacher units)
Plus `leaf_picks_unvisited` = the leaf's argmax over ALL legal children is one h6400 never
explored (a leaf value-blindness signal).

NET-FREE, CPU-parallel.  Writes:
  <out>/leaf_audit_rows.jsonl     per-root rows
  <out>/leaf_audit_summary.json   overall + by-phase + regret x gap-tier crosstab
"""
from __future__ import annotations
import os
os.environ["CARCASSONNE_V25_CAP"] = "8"
os.environ["CARCASSONNE_V25_OPP_CAP"] = "8"
os.environ["CARCASSONNE_V25_DROP_THREE_OPEN"] = "0"
os.environ["CARCASSONNE_V29_MEEPLE_CURVE"] = "-8,-4,-1,0,2,3,4,5"
os.environ["CARCASSONNE_V25_MEEPLE_K"] = "2.0"          # inert under the curve
os.environ["CARCASSONNE_USE_FLAT_LEAF"] = "1"
os.environ["CARCASSONNE_USE_CY_REPR"] = "1"
os.environ["CARCASSONNE_V25_VALUE_BLEND"] = "0"
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse, dataclasses as dc, hashlib, json, math, sys, time
from collections import Counter, defaultdict
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
FROZEN_V29_HASH = "7fc930b82801cb43"
_W: dict = {}


def _cfg_hash(cfg):
    d = {k: (list(v) if isinstance(v, tuple) else v) for k, v in dc.asdict(cfg).items()
         if not (k == "bag_close" and v is False)}  # v2.10 bag_close default-off == frozen v2.9 substrate
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def _provenance_guard():
    cfg = EH._heur_leaf_cfg(2.0)
    h = _cfg_hash(cfg)
    print(f"[provenance] v2.9 leaf config_hash = {h}  (frozen v2.9 = {FROZEN_V29_HASH})")
    assert h == FROZEN_V29_HASH, f"LEAF NOT v2.9 bmild_cap8 (got {h})"
    return cfg


def _worker_init():
    _W["cfg"] = EH._heur_leaf_cfg(2.0)


def _leaf_root_pov(game, board, action, cfg, root_player):
    """Static v2.9 leaf value of the child after `action`, from the FIXED root player's
    seat (root-POV). Turn-structure-robust: a TILES-phase action does NOT flip
    current_player in this engine (verified: 1816/1816 children keep the mover), so the
    blanket 'negate for opponent-to-move' of forced_move.py is WRONG here. Evaluating
    every child from root_player's seat matches the teacher's action_q convention
    (q = c.Q if same-mover else -c.Q  =>  root-POV)."""
    child, _ = game.get_next_state(board, int(action))
    st = child.state
    ended = game.get_game_ended(child, root_player)
    if ended != 0:
        return max(-1.0, min(1.0, float(ended))), game.string_representation(child)
    h = math.tanh(virtual_score_v2(st, root_player, cfg) / 15.0)
    return h, game.string_representation(child)


def _kendall_tau(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    c = d = 0
    for i in range(n):
        xi, yi = xs[i], ys[i]
        for j in range(i + 1, n):
            s = (xi - xs[j]) * (yi - ys[j])
            if s > 0:
                c += 1
            elif s < 0:
                d += 1
    tot = c + d
    return (c - d) / tot if tot else None


def _process(rec):
    try:
        seed = int(rec["seed"]); ply = int(rec["ply"])
        game, board = replay_to(seed, ply)
        if game.string_representation(board) != rec["checksum"]:
            return {"_error": f"{seed}:{ply} checksum_mismatch"}
        cfg = _W["cfg"]
        aq = {int(k): float(v) for k, v in rec["action_q"].items()}
        mask = game.get_valid_moves(board)
        legal = np.flatnonzero(mask).astype(int)
        if legal.size < 2:
            return {"_error": f"{seed}:{ply} <2 legal"}

        # enumerate id-deduped canonical children (lowest action id per unique child state)
        root_player = board.state.current_player
        seen = set()
        canon = []          # (action_id, L0, child_str)
        for a in legal:
            L0, cstr = _leaf_root_pov(game, board, a, cfg, root_player)
            if cstr in seen:
                continue
            seen.add(cstr)
            canon.append((int(a), L0, cstr))

        # teacher-visited subset = canonical children whose action id is in action_q
        evald = [(a, L0) for (a, L0, _) in canon if a in aq]
        n_eval = len(evald)
        # alignment check: teacher action ids that didn't map to a canonical child
        canon_ids = {a for (a, _, _) in canon}
        unmapped = sum(1 for a in aq if a not in canon_ids)
        if n_eval < 2:
            return {"_error": f"{seed}:{ply} <2 mapped visited children",
                    "unmapped": unmapped, "n_canon": len(canon)}

        teacher_best = max(aq, key=lambda k: aq[k])
        q_best = aq[teacher_best]
        leaf_top = max(evald, key=lambda t: t[1])[0]
        # leaf argmax over ALL legal children (incl. teacher-unvisited)
        leaf_all_top = max(canon, key=lambda t: t[1])[0]
        leaf_picks_unvisited = int(leaf_all_top not in aq)

        regret = q_best - aq[leaf_top]
        top1 = int(leaf_top == teacher_best)
        leaf_top3 = [a for (a, _) in sorted(evald, key=lambda t: t[1], reverse=True)[:3]]
        top3 = int(teacher_best in leaf_top3)
        L0s = [L0 for (_, L0) in evald]
        Qs = [aq[a] for (a, _) in evald]
        tau = _kendall_tau(L0s, Qs)

        return {
            "seed": seed, "ply": ply,
            "phase": rec.get("phase"),
            "k_remaining": rec.get("k_remaining"),
            "score_margin_abs": rec.get("score_margin_abs"),
            "legal_n": int(rec.get("legal_n", legal.size)),
            "n_canon": len(canon), "n_eval": n_eval, "unmapped": unmapped,
            "teacher_best": int(teacher_best),
            "teacher_best_row": int(rec.get("teacher_best", -1)),
            "q_best": float(q_best),
            "q_gap_1_2": float(rec.get("q_gap_1_2", 0.0)),
            "leaf_top": int(leaf_top),
            "regret": float(regret),
            "top1": top1, "top3": top3,
            "tau": (float(tau) if tau is not None else None),
            "leaf_picks_unvisited": leaf_picks_unvisited,
        }
    except Exception as e:
        return {"_error": f"{rec.get('seed')}:{rec.get('ply')} {type(e).__name__}: {e}"}


def _gap_tier(g):
    if g >= 0.040: return "very_strong>=0.04"
    if g >= 0.020: return "strong>=0.02"
    if g >= 0.010: return "medium>=0.01"
    if g >= 0.005: return "weak>=0.005"
    return "near-tie<0.005"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qprobe", default=str(HG / "scaled" / "qprobe_A" / "probe.jsonl"))
    ap.add_argument("--pool", default=str(HG / "scaled" / "pool_A.jsonl"))
    ap.add_argument("--out", default=str(REPO / "measurement" / "value_resurrection_pilot" / "data"))
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    cfg = _provenance_guard()

    checks = {}
    for line in open(args.pool):
        r = json.loads(line)
        checks[(r["seed"], r["ply"])] = r["checksum"]
    recs = []
    for line in open(args.qprobe):
        r = json.loads(line)
        key = (r["seed"], r["ply"])
        if key in checks:
            r["checksum"] = checks[key]
            recs.append(r)
    if args.limit:
        recs = recs[: args.limit]
    print(f"[load] {len(recs)} joined sibling sets  (workers={args.workers})")

    t0 = time.time()
    ctx = get_context("fork")
    rows, errs = [], []
    with ctx.Pool(args.workers, initializer=_worker_init) as pool:
        for i, out in enumerate(pool.imap_unordered(_process, recs, chunksize=16)):
            if "_error" in out:
                errs.append(out["_error"])
            else:
                rows.append(out)
            if (i + 1) % 2000 == 0:
                print(f"  {i+1}/{len(recs)}  ok={len(rows)} err={len(errs)}  {time.time()-t0:.0f}s")
    dt = time.time() - t0
    print(f"[done] ok={len(rows)} err={len(errs)} in {dt:.0f}s ({len(recs)/max(dt,1):.0f}/s)")
    if errs[:5]:
        print("  sample errors:", errs[:5])

    outd = Path(args.out); outd.mkdir(parents=True, exist_ok=True)
    with open(outd / "leaf_audit_rows.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    # ---- aggregate ----
    def agg(sub):
        if not sub:
            return {}
        taus = [r["tau"] for r in sub if r["tau"] is not None]
        reg = [r["regret"] for r in sub]
        return {
            "n": len(sub),
            "top1": round(np.mean([r["top1"] for r in sub]), 4),
            "top3": round(np.mean([r["top3"] for r in sub]), 4),
            "tau_mean": round(float(np.mean(taus)), 4) if taus else None,
            "regret_mean": round(float(np.mean(reg)), 5),
            "regret_median": round(float(np.median(reg)), 5),
            "leaf_neq_teacher": round(np.mean([1 - r["top1"] for r in sub]), 4),
            "leaf_picks_unvisited": round(np.mean([r["leaf_picks_unvisited"] for r in sub]), 4),
        }

    summary = {"overall": agg(rows)}
    summary["by_phase"] = {ph: agg([r for r in rows if r["phase"] == ph])
                           for ph in ["opening", "midgame", "late_mid", "pre_endgame", "endgame"]}
    summary["by_gap_tier"] = {t: agg([r for r in rows if _gap_tier(r["q_gap_1_2"]) == t])
                              for t in ["near-tie<0.005", "weak>=0.005", "medium>=0.01",
                                        "strong>=0.02", "very_strong>=0.04"]}
    # the Stage-3 proceed gate: leaf-top != teacher-top AND regret >= thresholds
    def gate(min_reg):
        return sum(1 for r in rows if r["top1"] == 0 and r["regret"] >= min_reg)
    summary["gate"] = {
        "n_leaf_neq_teacher": sum(1 for r in rows if r["top1"] == 0),
        "n_regret_ge_0.01": gate(0.01),
        "n_regret_ge_0.02": gate(0.02),
        "n_regret_ge_0.04": gate(0.04),
        # decisive subset: teacher-confident (gap>=0.02) AND leaf has real regret
        "n_gap002_and_regret002": sum(1 for r in rows
                                      if r["q_gap_1_2"] >= 0.02 and r["regret"] >= 0.02),
        "n_endgame_regret002": sum(1 for r in rows
                                   if r["phase"] in ("pre_endgame", "endgame") and r["regret"] >= 0.02),
    }
    summary["provenance"] = {"leaf_config_hash": _cfg_hash(cfg), "teacher": "h6400_v2.9",
                             "qprobe": args.qprobe, "pool": args.pool,
                             "n_in": len(recs), "n_ok": len(rows), "n_err": len(errs)}
    with open(outd / "leaf_audit_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("\n==== LEAF AUDIT SUMMARY ====")
    print("overall :", summary["overall"])
    print("gate    :", summary["gate"])
    for ph, v in summary["by_phase"].items():
        print(f"  phase {ph:12s}: {v}")
    for t, v in summary["by_gap_tier"].items():
        print(f"  gap   {t:18s}: {v}")


if __name__ == "__main__":
    main()
